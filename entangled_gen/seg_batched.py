"""Batched-vocabulary detection (user idea 2026-07-26): GroundingDINO's
confidence drops sharply with prompt length (measured on the picture wall:
30-term prompt -> 5 paintings at 0.35-0.37; 3-term prompt -> 21 at
0.37-0.48). So: split the vocab into small batches (~5 terms), run one pass
per batch per image, canonicalize labels, then per-image same-label overlap
dedup across batches. Synonyms are spread across DIFFERENT batches
(round-robin) so they never compete inside one prompt; canonicalization
merges them afterward.

Output contract identical to seg_views.py (detections.json + <view>_masks.npy
+ overlay pngs), so the lift machinery consumes it unmodified.

Run:  python seg_batched.py --scene bedroom_marble \
          --views-dir OUT/bedroom_marble/rig_sp0/crops --glob "pano_*.webp" \
          --out-dir OUT/bedroom_marble/rig_sp0/seg_batched --pace 2
"""
import argparse, json, time
from pathlib import Path
import numpy as np
from PIL import Image

import paths
from vocab_from_prompt import canonicalize
from seg_views import draw_boxes, overlay_masks

BATCH = 5
TOPK = 30
IOU_NMS = 0.5


def iou2d(a, b):
    x0 = max(a["xmin"], b["xmin"]); y0 = max(a["ymin"], b["ymin"])
    x1 = min(a["xmax"], b["xmax"]); y1 = min(a["ymax"], b["ymax"])
    if x1 <= x0 or y1 <= y0:
        return 0.0
    inter = (x1 - x0) * (y1 - y0)
    va = (a["xmax"] - a["xmin"]) * (a["ymax"] - a["ymin"])
    vb = (b["xmax"] - b["xmin"]) * (b["ymax"] - b["ymin"])
    return inter / (va + vb - inter + 1e-9)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--views-dir", required=True)
    ap.add_argument("--glob", default="*.webp")
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--box-thr", type=float, default=0.35)
    ap.add_argument("--topk", type=int, default=TOPK)
    ap.add_argument("--pace", type=float, default=2.0)
    a = ap.parse_args()

    vj = json.loads((paths.scene_dir(a.scene) / "vocab.json")
                    .read_text(encoding="utf-8"))
    canon = list(vj["canonical"])
    syn = vj.get("synonyms", {})   # detector-phrasing alternatives -> canonical
    terms = [t.strip() for t in vj["queries"]["gdino"].split(".") if t.strip()]
    # round-robin so a concept's synonyms (appended at the list's end by the
    # vocab expansion) land in different batches
    n_b = (len(terms) + BATCH - 1) // BATCH
    batches = [terms[i::n_b] for i in range(n_b)]
    print(f"[segb] {len(terms)} terms -> {n_b} batches of ~{BATCH}:", flush=True)
    for bt in batches:
        print(f"  {'. '.join(bt)}.", flush=True)

    views = sorted(Path(a.views_dir).glob(a.glob))
    out = Path(a.out_dir)
    out.mkdir(parents=True, exist_ok=True)

    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    from transformers import (AutoProcessor, GroundingDinoForObjectDetection,
                              SamModel, SamProcessor)
    gd_proc = AutoProcessor.from_pretrained("IDEA-Research/grounding-dino-base")
    gd = GroundingDinoForObjectDetection.from_pretrained(
        "IDEA-Research/grounding-dino-base").to(dev)
    gd.eval()
    sam = SamModel.from_pretrained("facebook/sam-vit-base").to(dev)
    sam_proc = SamProcessor.from_pretrained("facebook/sam-vit-base")

    unmapped = set()
    all_dets = {}
    for vp in views:
        name = vp.stem
        img = Image.open(vp).convert("RGB")
        raw = []
        for bt in batches:
            prompt = ". ".join(bt) + "."
            inputs = gd_proc(images=img, text=prompt,
                             return_tensors="pt").to(dev)
            with torch.no_grad():
                outputs = gd(**inputs)
            res = gd_proc.post_process_grounded_object_detection(
                outputs, inputs["input_ids"], threshold=a.box_thr,
                text_threshold=0.25, target_sizes=[img.size[::-1]])[0]
            labels = (res["text_labels"] if "text_labels" in res
                      else res["labels"])
            for score, label, box in zip(res["scores"], labels, res["boxes"]):
                x0, y0, x1, y1 = [float(v) for v in box]
                lab = canonicalize(str(label), canon, syn) or ""
                if not lab:
                    unmapped.add(str(label))
                    continue
                raw.append({"label": lab, "label_raw": str(label),
                            "score": float(score),
                            "box": {"xmin": x0, "ymin": y0,
                                    "xmax": x1, "ymax": y1}})
            time.sleep(0.3)
        # cross-batch dedup: same canonical label, high overlap -> keep best
        raw.sort(key=lambda d: -d["score"])
        kept = []
        for d in raw:
            if any(k["label"] == d["label"]
                   and iou2d(k["box"], d["box"]) > IOU_NMS for k in kept):
                continue
            kept.append(d)
        kept = kept[:a.topk]
        all_dets[name] = kept
        print(f"[segb] {name}: {len(raw)} raw -> {len(kept)} after dedup "
              f"(top {', '.join(sorted({d['label'] for d in kept[:8]}))})",
              flush=True)
        draw_boxes(img, kept).save(out / f"{name}_boxes.png")
        if kept:
            boxes = [[[d["box"]["xmin"], d["box"]["ymin"],
                       d["box"]["xmax"], d["box"]["ymax"]] for d in kept]]
            sinp = sam_proc(img, input_boxes=boxes,
                            return_tensors="pt").to(dev)
            with torch.no_grad():
                souts = sam(**sinp, multimask_output=False)
            masks = sam_proc.image_processor.post_process_masks(
                souts.pred_masks.cpu(), sinp["original_sizes"].cpu(),
                sinp["reshaped_input_sizes"].cpu())[0]
            masks = masks.squeeze(1).numpy().astype(bool)
            overlay_masks(img, list(masks)).save(out / f"{name}_masks.png")
            np.save(out / f"{name}_masks.npy", masks)
        # persist after every view — a hard power cut loses at most the
        # in-flight view, never the completed ones (08-06 crash lesson)
        (out / "detections.json").write_text(json.dumps(all_dets, indent=2))
        time.sleep(a.pace)

    print(f"[segb] wrote {out / 'detections.json'}", flush=True)
    if unmapped:
        print(f"[segb] labels with no canonical mapping (dropped): "
              f"{sorted(unmapped)}", flush=True)


if __name__ == "__main__":
    main()
