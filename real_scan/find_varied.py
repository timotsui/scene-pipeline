"""Rank single-room InteriorGS scenes by discrete-furniture variety (not dominated by one object)."""
import json, collections, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from huggingface_hub import hf_hub_download, login
import os
if os.environ.get("HF_TOKEN"):  # else: cached huggingface-cli login
    login(os.environ["HF_TOKEN"], add_to_git_credential=False)
REPO = "spatialverse/InteriorGS"

single = [f.parent.name for f in Path("triage_struct").glob("*/structure.json")
          if len(json.load(open(f)).get("rooms", [])) == 1]

def footprint(bb):
    if not bb: return 0.0
    xs = [c["x"] for c in bb]; ys = [c["y"] for c in bb]
    return (max(xs)-min(xs)) * (max(ys)-min(ys))

rows = []
for s in single:
    p = Path(f"triage/{s}/labels.json")
    if not p.exists():  # only the ones already pulled
        continue
    lb = json.load(open(p))
    # furniture = footprint 0.1..6 m2 (excludes tiny clutter AND the room/floor itself)
    furn = collections.Counter(o.get("label","?") for o in lb
                               if 0.1 < footprint(o.get("bounding_box")) < 6.0)
    if not furn: continue
    total = sum(furn.values()); distinct = len(furn)
    dominance = furn.most_common(1)[0][1] / total   # 1.0 = one category dominates
    rows.append((s, distinct, total, dominance, furn))

# want: many distinct cats, NOT dominated by a single category, modest total (not 100s of clutter)
rows = [r for r in rows if r[3] < 0.45 and 6 <= r[2] <= 60]
rows.sort(key=lambda r: -r[1])
print(f"varied single-room scenes (after filter): {len(rows)}")
print("--- top by distinct furniture categories ---")
for s, distinct, total, dom, furn in rows[:14]:
    print(f"{s} | {distinct} cats, {total} pieces, dom {dom:.0%} | " +
          ", ".join(f"{k}×{v}" for k, v in furn.most_common(8)))

top = rows[:8]
fig, axes = plt.subplots(2, 4, figsize=(16, 9))
for ax, (s, distinct, total, dom, furn) in zip(axes.flat, top):
    op = hf_hub_download(REPO, f"{s}/occupancy.png", repo_type="dataset", local_dir="triage")
    ax.imshow(plt.imread(op))
    ax.set_title(f"{s}  ({distinct} cats)\n" + ", ".join(list(furn)[:6]), fontsize=8); ax.axis("off")
fig.suptitle("Single-room scenes with most discrete furniture variety", fontsize=14)
fig.tight_layout(); fig.savefig("outputs/06_varied_candidates.png", dpi=95)
print("saved outputs/06_varied_candidates.png")
