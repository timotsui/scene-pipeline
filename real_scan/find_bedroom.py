"""Triage: among single-room InteriorGS scenes, find bedrooms with varied discrete furniture."""
import json, collections, numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from huggingface_hub import snapshot_download, hf_hub_download, login
import os
if os.environ.get("HF_TOKEN"):  # else: cached huggingface-cli login
    login(os.environ["HF_TOKEN"], add_to_git_credential=False)
REPO = "spatialverse/InteriorGS"

single = [f.parent.name for f in Path("triage_struct").glob("*/structure.json")
          if len(json.load(open(f)).get("rooms", [])) == 1]
print("single-room scenes:", len(single))
snapshot_download(REPO, repo_type="dataset", local_dir="triage",
                  allow_patterns=[f"{s}/labels.json" for s in single])

def footprint(bb):
    if not bb: return 0.0
    xs = [c["x"] for c in bb]; ys = [c["y"] for c in bb]
    return (max(xs)-min(xs)) * (max(ys)-min(ys))

def is_bed(l):
    l = (l or "").lower()
    return "bed" in l and "bedside" not in l and "cabinet" not in l

beds = []
for s in single:
    lb = json.load(open(f"triage/{s}/labels.json"))
    if not any(is_bed(o.get("label")) for o in lb):
        continue
    furn = collections.Counter(o.get("label","?") for o in lb if footprint(o.get("bounding_box")) > 0.08)
    beds.append((s, len(furn), sum(furn.values()), furn))

beds.sort(key=lambda r: -r[1])   # most distinct furniture categories first
print(f"\nBEDROOM single-room scenes: {len(beds)}")
print("--- ranked by distinct furniture categories ---")
for s, distinct, total, furn in beds[:12]:
    top = ", ".join(f"{k}×{v}" for k, v in furn.most_common(8))
    print(f"{s}  | {distinct} cats, {total} furn pieces | {top}")

# contact sheet of the top 8 bedrooms
top = beds[:8]
fig, axes = plt.subplots(2, 4, figsize=(16, 9))
for ax, (s, distinct, total, furn) in zip(axes.flat, top):
    op = hf_hub_download(REPO, f"{s}/occupancy.png", repo_type="dataset", local_dir="triage")
    ax.imshow(plt.imread(op))
    cats = ", ".join(list(furn)[:6])
    ax.set_title(f"{s}\n{distinct} furn cats\n{cats}", fontsize=8); ax.axis("off")
fig.suptitle("Single-room BEDROOM candidates", fontsize=14)
fig.tight_layout(); fig.savefig("outputs/05_bedroom_candidates.png", dpi=95)
print("saved outputs/05_bedroom_candidates.png")
