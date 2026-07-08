"""Gate artifact for the week8 pano-detection path: paint every crop's SAM
masks back onto the equirect pano (label-colored, score-labeled) + a montage
of the per-crop box overlays. USER judges these; nothing here concludes.

  python seg_pano_overlay.py --scene bedroom_marble

Outputs (to out/<scene>/seg_pano/):
  pano_overlay.png     equirect with all detections painted in pano space
  crops_boxes.png      montage of the per-crop *_boxes.png
"""
import argparse, hashlib, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

import paths
from crop_pano import crop_dirs

OVERLAY_W = 2304   # half-res pano for the overlay


def label_color(label):
    h = hashlib.md5(label.encode()).digest()
    r, g, b = h[0], h[1], h[2]
    # keep colors bright
    m = max(r, g, b) or 1
    return tuple(int(60 + 195 * c / m) for c in (r, g, b))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--score-min", type=float, default=0.35)
    a = ap.parse_args()

    crops = paths.pano_crops_dir(a.scene)
    seg = paths.seg_pano_dir(a.scene)
    dets_all = json.loads((seg / "detections.json").read_text())

    from vocab_from_prompt import bundle_prompt_file
    panof = next(bundle_prompt_file(a.scene).parent.glob("*_pano.png"))
    Image.MAX_IMAGE_PIXELS = None
    W = OVERLAY_W
    H = W // 2
    pano = Image.open(panof).convert("RGB").resize((W, H), Image.LANCZOS)
    base = np.asarray(pano, np.float32)
    paint = base.copy()
    labels_at = []   # (u, v, label, score)

    r3 = paths.load_r3()
    for view, dets in sorted(dets_all.items()):
        maskf = seg / f"{view}_masks.npy"
        sidef = crops / f"{view}.json"
        if not maskf.exists() or not sidef.exists() or not dets:
            continue
        meta = json.loads(sidef.read_text())
        res = int(meta["res"].split("x")[0])
        cam = r3.Cam([float(t) for t in meta["cam"].split(",")],
                     [float(t) for t in meta["look"].split(",")],
                     [float(t) for t in meta["up"].split(",")],
                     float(meta["fov"]), res, res)
        dirs = crop_dirs(cam, res)                     # (res*res, 3)
        theta = np.arctan2(dirs[:, 0], dirs[:, 2])
        phi = np.arcsin(np.clip(dirs[:, 1], -1, 1))
        pu = ((theta / (2 * np.pi) + 0.5) * W).astype(np.int64) % W
        pv = np.clip(((0.5 - phi / np.pi) * H).astype(np.int64), 0, H - 1)
        masks = np.load(maskf)
        for det, mask in zip(dets, masks):
            if det["score"] < a.score_min:
                continue
            sel = mask.reshape(-1)
            if not sel.any():
                continue
            c = np.array(label_color(det["label"]), np.float32)
            paint[pv[sel], pu[sel]] = 0.55 * paint[pv[sel], pu[sel]] + 0.45 * c
            labels_at.append((int(np.median(pu[sel])), int(np.median(pv[sel])),
                              det["label"], det["score"]))

    im = Image.fromarray(paint.astype(np.uint8))
    dr = ImageDraw.Draw(im)
    for u, v, label, score in labels_at:
        txt = f"{label} {score:.2f}"
        dr.text((u + 1, v + 1), txt, fill=(0, 0, 0))
        dr.text((u, v), txt, fill=(255, 255, 120))
    outp = seg / "pano_overlay.png"
    im.save(outp)
    print(f"wrote {outp}  ({len(labels_at)} painted detections)")

    # ---- montage of per-crop box overlays ----
    boxfs = sorted(seg.glob("pano_*_boxes.png"))
    if boxfs:
        cols, cell = 5, 460
        rows = (len(boxfs) + cols - 1) // cols
        label_h = 18
        M = Image.new("RGB", (cols * cell, rows * (cell + label_h)), (12, 12, 12))
        dm = ImageDraw.Draw(M)
        for i, f in enumerate(boxfs):
            x, y = (i % cols) * cell, (i // cols) * (cell + label_h)
            M.paste(Image.open(f).convert("RGB").resize((cell, cell)), (x, y + label_h))
            dm.text((x + 4, y + 3), f.stem.replace("_boxes", ""), fill=(230, 230, 90))
        outm = seg / "crops_boxes.png"
        M.save(outm)
        print(f"wrote {outm}  ({len(boxfs)} crops)")


if __name__ == "__main__":
    main()
