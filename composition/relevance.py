"""C3: CLIP relevance per candidate — the second ranking axis (style/looks).

Two additive fields per candidate in shortlists2.json (contract stays valid
for consumers that ignore them):
- `clip`     image-image: clean view crop (review_crops/<id>_clean.png, no
             drawn box lines) vs the candidate's ORIENTATION-CORRECTED
             thumbnail (uid_<perm>.png when the fit re-upped the asset).
- `clip_txt` text-image: "category. description" vs the same crop — a
             cross-check for misleading thumbnails (low clip + high clip_txt
             = suspect render/orientation, not a wrong asset). Never merged
             into `clip`; combining is the pick stage's job.

Embeddings cache at <objathor>/_thumbs/_clip_vitb16.npz (image keys = thumb
stems, text keys = "txt_<uid>"). Uses transformers'
openai/clip-vit-base-patch16 (already-installed stack; no new deps, torch
untouched). Run: python relevance.py --scene <sc>
"""
import json

import numpy as np
import torch
from PIL import Image
from transformers import CLIPModel, CLIPProcessor

from comp_paths import paths
from thumbs import THUMBS, thumb_stem

MODEL_ID = "openai/clip-vit-base-patch16"
CACHE = THUMBS / "_clip_vitb16.npz"


def _load():
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    model = CLIPModel.from_pretrained(MODEL_ID).to(dev).eval()
    proc = CLIPProcessor.from_pretrained(MODEL_ID)
    return model, proc, dev


def embed_images(files, model, proc, dev, bs=32):
    out = []
    for i in range(0, len(files), bs):
        ims = [Image.open(f).convert("RGB") for f in files[i:i + bs]]
        with torch.no_grad():
            inp = proc(images=ims, return_tensors="pt").to(dev)
            vis = model.vision_model(pixel_values=inp["pixel_values"])
            e = model.visual_projection(vis.pooler_output)
        out.append((e / e.norm(dim=-1, keepdim=True)).cpu().numpy())
    return np.concatenate(out) if out else np.zeros((0, 512), np.float32)


def embed_texts(texts, model, proc, dev, bs=64):
    out = []
    for i in range(0, len(texts), bs):
        with torch.no_grad():
            inp = proc(text=texts[i:i + bs], return_tensors="pt",
                       padding=True, truncation=True).to(dev)
            t = model.text_model(input_ids=inp["input_ids"],
                                 attention_mask=inp["attention_mask"])
            e = model.text_projection(t.pooler_output)
        out.append((e / e.norm(dim=-1, keepdim=True)).cpu().numpy())
    return np.concatenate(out) if out else np.zeros((0, 512), np.float32)


def run(sc):
    pkg = paths.package_dir(sc)
    slf = pkg / "shortlists2.json"
    sl = json.loads(slf.read_text())
    from review_server import make_crops
    make_crops(sc, sl["boxes"])          # ensures the clean query crops exist
    model, proc, dev = _load()

    cache = {}
    if CACHE.exists():
        with np.load(CACHE) as f:
            cache = {k: f[k] for k in f.files}
    cands = [c for b in sl["boxes"] for c in b["candidates"]]
    stems = sorted({thumb_stem(c["uid"], c.get("perm", "xyz")) for c in cands})
    todo = [s for s in stems
            if s not in cache and (THUMBS / f"{s}.png").exists()]
    txt_todo = sorted({c["uid"] for c in cands if f'txt_{c["uid"]}' not in cache})
    if todo:
        emb = embed_images([THUMBS / f"{s}.png" for s in todo], model, proc, dev)
        cache.update(zip(todo, emb))
        print(f"[relevance] embedded {len(todo)} new thumbs", flush=True)
    if txt_todo:
        by_uid = {c["uid"]: c for c in cands}
        emb = embed_texts([f'{by_uid[u]["category"]}. {by_uid[u]["description"]}'
                           for u in txt_todo], model, proc, dev)
        cache.update((f"txt_{u}", e) for u, e in zip(txt_todo, emb))
        print(f"[relevance] embedded {len(txt_todo)} new descriptions", flush=True)
    if todo or txt_todo:
        np.savez(CACHE, **cache)

    cdir = pkg / "review_crops"
    for b in sl["boxes"]:
        cf = cdir / f"{b['id']}_clean.png"
        if not b["candidates"] or not cf.exists():
            continue
        q = embed_images([cf], model, proc, dev)[0]
        for c in b["candidates"]:
            e = cache.get(thumb_stem(c["uid"], c.get("perm", "xyz")))
            t = cache.get(f'txt_{c["uid"]}')
            c["clip"] = round(float(q @ e), 4) if e is not None else None
            c["clip_txt"] = round(float(q @ t), 4) if t is not None else None
        top = sorted((c for c in b["candidates"] if c.get("clip") is not None),
                     key=lambda c: -c["clip"])[:3]
        print(f"[relevance] {b['id']} {b['label']:16s} top: " + " | ".join(
            f"{c['clip']:.3f} {c['description'][:45]}" for c in top), flush=True)
    slf.write_text(json.dumps(sl, indent=1))
    print(f"[relevance] wrote clip scores into {slf}", flush=True)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()
    run(args.scene)
