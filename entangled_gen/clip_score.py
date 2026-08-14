"""CLIP scores for the evaluation renders — the baselines' own metric.

Recipe = GLTS Sec 6.1 (which follows Holodeck): OpenCLIP ViT-L/14
pretrained on LAION-2B, cosine similarity between the top-down render
and "a top-down view of a [scene type]", times 100. Scores every
image in out/eval_renders/<scene>_<side>_<proj>.png, prints the table
and writes out/eval_renders/clip_scores.json.

CPU on purpose: ~44 images take about a minute, and a report tool must
never be the thing that GPU-bursts this machine (POWER_CRASHES.md).

CAVEAT for the paper (EVAL_PLAN_2026-08-13): both sides are OUR
flat-shaded pyrender shots, not the papers' lit Blender/Cycles images —
so scores compare ours-vs-GLTS within this table and are NOT comparable
to the absolute numbers printed in either paper.

Run:  python clip_score.py
"""
import json
from pathlib import Path

import numpy as np
import torch
from PIL import Image

import paths

RENDER_DIR = paths.OUT / "eval_renders"
MODEL = "ViT-L-14"
PRETRAINED = "laion2b_s32b_b82k"
TEMPLATE = "a top-down view of a {t}"

SCENE_TYPE = {
    "natural_living": "living room",
    "blue_living": "living room",
    "living_marble": "living room",
    "sunlit_office": "office",
    "panel_bedroom": "bedroom",
    "arch_bedroom": "bedroom",
    "plaster_bedroom": "bedroom",
    "bedroom_marble": "bedroom",
    "fresh04": "bedroom",       # its Marble prompt: bed, headboard, wardrobe
    "fresh06": "bedroom",
}


def main():
    import open_clip
    device = "cpu"
    model, _, preprocess = open_clip.create_model_and_transforms(
        MODEL, pretrained=PRETRAINED, device=device)
    model.eval()
    tokenizer = open_clip.get_tokenizer(MODEL)

    prompts = {t: TEMPLATE.format(t=t) for t in set(SCENE_TYPE.values())}
    with torch.no_grad():
        toks = tokenizer(list(prompts.values())).to(device)
        tfeat = model.encode_text(toks)
        tfeat = tfeat / tfeat.norm(dim=-1, keepdim=True)
    tvec = {t: tfeat[i] for i, t in enumerate(prompts)}

    rows = {}
    for png in sorted(RENDER_DIR.glob("*_*_*.png")):
        parts = png.stem.rsplit("_", 2)
        if len(parts) != 3:
            continue
        scene, side, proj = parts
        if scene not in SCENE_TYPE:
            continue
        img = preprocess(Image.open(png).convert("RGB")).unsqueeze(0)
        with torch.no_grad():
            f = model.encode_image(img.to(device))
            f = f / f.norm(dim=-1, keepdim=True)
        score = float((f @ tvec[SCENE_TYPE[scene]]).item()) * 100.0
        rows.setdefault(scene, {})[f"{side}_{proj}"] = round(score, 2)
        print(f"[clip] {png.stem:40s} {score:6.2f}")

    cols = ["ours_ortho", "ours_persp", "glts_ortho", "glts_persp"]
    means = {c: round(float(np.mean([r[c] for r in rows.values() if c in r])), 2)
             for c in cols}
    print("\nscene                 " + "  ".join(f"{c:>10s}" for c in cols))
    for sc in SCENE_TYPE:
        if sc not in rows:
            continue
        r = rows[sc]
        print(f"{sc:20s} " + "  ".join(
            f"{r.get(c, float('nan')):10.2f}" if c in r else f"{'—':>10s}"
            for c in cols))
    print(f"{'MEAN':20s} " + "  ".join(f"{means[c]:10.2f}" for c in cols))

    out = {"model": MODEL, "pretrained": PRETRAINED, "template": TEMPLATE,
           "scene_types": SCENE_TYPE, "scores": rows, "means": means,
           "caveat": ("both sides scored on OUR flat-shaded pyrender shots; "
                      "comparable within this table only, never to the "
                      "papers' Cycles-render numbers")}
    (RENDER_DIR / "clip_scores.json").write_text(json.dumps(out, indent=1),
                                                 encoding="utf-8")
    print(f"\n[clip] -> {RENDER_DIR / 'clip_scores.json'}")


if __name__ == "__main__":
    main()
