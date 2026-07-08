"""
Segmentation PoC on the GPU-rendered views of the GENERATED splat
(out/<scene>/views/gpu_yaw*.webp).

Stack: GroundingDINO (text-prompted open-vocab boxes) + SAM (masks from boxes),
both via HuggingFace transformers on the Windows python (torch 2.6 cu124).

Outputs per view (to out/<scene>/seg/):
  <view>_boxes.png     boxes + labels overlay
  <view>_masks.png     SAM masks overlay
  detections.json      all detections (label, score, box) per view
"""
import argparse, json
from pathlib import Path
import numpy as np
import torch
from PIL import Image

import paths

HERE = Path(__file__).parent

# per-room detection vocab (GroundingDINO wants lowercase, period-separated),
# matched to the generation prompts in runners/
PROMPTS = {
    "playroom": ("shelf. bookshelf. window. rug. carpet. cabinet. door. "
                 "stuffed animal. toy. box. basket. picture. lamp. ceiling light."),
    "bedroom": ("bed. nightstand. wardrobe. dresser. lamp. window. door. "
                "rug. pillow. curtain. picture. chair. ceiling light."),
    "livingroom": ("sofa. couch. armchair. coffee table. television. rug. lamp. "
                   "window. curtain. bookshelf. picture. plant. cushion. door."),
    "kitchen": ("dining table. chair. cabinet. refrigerator. sink. countertop. "
                "stove. oven. window. door. lamp. picture."),
}

GENERIC_PROMPT = ("bed. chair. table. sofa. wardrobe. window. door. lamp. rug. "
                  "television. nightstand. shelf. picture. curtain.")

ap = argparse.ArgumentParser()
ap.add_argument("--scene", default="playroom")
ap.add_argument("--views-dir", default="", help="override views directory")
ap.add_argument("--glob", default="gpu_yaw*.webp", help="view filename glob")
ap.add_argument("--out-dir", default="", help="override output directory")
ap.add_argument("--prompt", default="", help="override detection vocab")
ap.add_argument("--box-thr", type=float, default=0.35,
                help="GroundingDINO box threshold (lower for promised-but-missed words)")
args = ap.parse_args()
sc = args.scene

VIEWS_DIR = Path(args.views_dir) if args.views_dir else paths.views_dir(sc)
VIEWS = sorted(VIEWS_DIR.glob(args.glob))
OUT = Path(args.out_dir) if args.out_dir else paths.seg_dir(sc)
OUT.mkdir(parents=True, exist_ok=True)

DEVICE = "cuda" if torch.cuda.is_available() else "cpu"
print(f"device: {DEVICE}  scene: {sc}  views: {len(VIEWS)}", flush=True)

PROMPT = args.prompt if args.prompt else PROMPTS.get(sc, GENERIC_PROMPT)

# ---------------- GroundingDINO (dedicated API — the zero-shot pipeline
# mis-handles grounding-dino: whole-image boxes) ----------------
from transformers import AutoProcessor, GroundingDinoForObjectDetection

print("loading GroundingDINO...", flush=True)
gd_proc = AutoProcessor.from_pretrained("IDEA-Research/grounding-dino-base")
gd = GroundingDinoForObjectDetection.from_pretrained("IDEA-Research/grounding-dino-base").to(DEVICE)
gd.eval()

def detect(img, prompt, box_thr=0.35, text_thr=0.25):
    inputs = gd_proc(images=img, text=prompt, return_tensors="pt").to(DEVICE)
    with torch.no_grad():
        outputs = gd(**inputs)
    res = gd_proc.post_process_grounded_object_detection(
        outputs, inputs["input_ids"], threshold=box_thr, text_threshold=text_thr,
        target_sizes=[img.size[::-1]])[0]
    dets = []
    for score, label, box in zip(res["scores"], res["text_labels"] if "text_labels" in res else res["labels"], res["boxes"]):
        x0, y0, x1, y1 = [float(v) for v in box]
        dets.append({"label": str(label), "score": float(score),
                     "box": {"xmin": x0, "ymin": y0, "xmax": x1, "ymax": y1}})
    return dets

# ---------------- SAM ----------------
from transformers import SamModel, SamProcessor

print("loading SAM...", flush=True)
sam = SamModel.from_pretrained("facebook/sam-vit-base").to(DEVICE)
sam_proc = SamProcessor.from_pretrained("facebook/sam-vit-base")

# ---------------- helpers ----------------
def draw_boxes(img, dets):
    from PIL import ImageDraw, ImageFont
    im = img.copy()
    d = ImageDraw.Draw(im)
    for det in dets:
        b = det["box"]
        d.rectangle([b["xmin"], b["ymin"], b["xmax"], b["ymax"]], outline=(255, 40, 40), width=3)
        d.text((b["xmin"] + 4, b["ymin"] + 4), f'{det["label"]} {det["score"]:.2f}', fill=(255, 40, 40))
    return im

def overlay_masks(img, masks):
    rng = np.random.default_rng(0)
    base = np.asarray(img).astype(np.float32)
    for m in masks:
        color = rng.uniform(60, 255, 3)
        base[m] = 0.55 * base[m] + 0.45 * color
    return Image.fromarray(base.astype(np.uint8))

# ---------------- run ----------------
all_dets = {}
for vp in VIEWS:
    name = vp.stem
    img = Image.open(vp).convert("RGB")
    print(f"\n=== {name} ===", flush=True)

    dets = detect(img, PROMPT, box_thr=args.box_thr)
    # keep it readable
    dets = sorted(dets, key=lambda d: -d["score"])[:20]
    for d in dets:
        print(f'  {d["label"]:18s} {d["score"]:.2f}  {d["box"]}', flush=True)
    all_dets[name] = dets

    draw_boxes(img, dets).save(OUT / f"{name}_boxes.png")

    if dets:
        boxes = [[[d["box"]["xmin"], d["box"]["ymin"], d["box"]["xmax"], d["box"]["ymax"]] for d in dets]]
        inputs = sam_proc(img, input_boxes=boxes, return_tensors="pt").to(DEVICE)
        with torch.no_grad():
            outs = sam(**inputs, multimask_output=False)
        masks = sam_proc.image_processor.post_process_masks(
            outs.pred_masks.cpu(), inputs["original_sizes"].cpu(), inputs["reshaped_input_sizes"].cpu())[0]
        masks = masks.squeeze(1).numpy().astype(bool)  # (n, H, W)
        overlay_masks(img, list(masks)).save(OUT / f"{name}_masks.png")
        np.save(OUT / f"{name}_masks.npy", masks)

with open(OUT / "detections.json", "w") as f:
    json.dump(all_dets, f, indent=2)
print("\nwrote", OUT / "detections.json", flush=True)
