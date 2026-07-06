"""Pull + decode a shortlist of InteriorGS candidate scenes, render a top-down comparison.
Leaves room_uncompressed.ply in each scene folder (ready to drag into SuperSplat)."""
import json, numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from huggingface_hub import hf_hub_download, login
from decompress_interiorgs import decompress
import os
if os.environ.get("HF_TOKEN"):  # else: cached huggingface-cli login
    login(os.environ["HF_TOKEN"], add_to_git_credential=False)
REPO = "spatialverse/InteriorGS"
RAW = Path("data/raw/InteriorGS")

CANDS = [   # (scene, my-note)
    ("0182_840104", "lounge — varied, least table-dominated"),
    ("0143_840060", "balanced — wardrobe/teatable/fan"),
    ("0028_839947", "living/dining — fireplace+sofa"),
    ("0202_840156", "dining/living + plants"),
    ("0089_839957", "cafe/bar — varied"),
    ("0160_840075", "bedroom-ish — beds/wardrobe/cabinet"),
    ("0096_839964", "bedroom-ish — bed/sofa/shelf"),
]
C0 = 0.28209479177387814

def load_unc(path):
    f=open(path,"rb"); f.readline(); f.readline(); names=[]; n=None
    while True:
        l=f.readline().strip()
        if l.startswith(b"element vertex"): n=int(l.split()[-1])
        elif l.startswith(b"property"): names.append(l.split()[2].decode())
        elif l==b"end_header": break
    d=np.frombuffer(f.read(n*len(names)*4),dtype="<f4").reshape(n,len(names))
    c=lambda k: d[:,names.index(k)]
    xyz=np.stack([c("x"),c("y"),c("z")],1)
    rgb=np.clip(0.5+C0*np.stack([c("f_dc_0"),c("f_dc_1"),c("f_dc_2")],1),0,1)
    alpha=1/(1+np.exp(-c("opacity")))
    return xyz,rgb,alpha

fig, axes = plt.subplots(2, 4, figsize=(18, 9))
for ax,(s,note) in zip(axes.flat, CANDS):
    d = RAW/s
    for fn in ["3dgs_compressed.ply","labels.json","occupancy.png","structure.json"]:
        hf_hub_download(REPO, f"{s}/{fn}", repo_type="dataset", local_dir=str(RAW))
    dst = d/"room_uncompressed.ply"
    if not dst.exists():
        decompress(d/"3dgs_compressed.ply", dst)
    xyz,rgb,alpha = load_unc(dst)
    m = alpha>0.5; idx=np.where(m)[0]
    idx=np.random.default_rng(0).choice(idx, min(120000,idx.size), replace=False)
    ax.scatter(xyz[idx,0], xyz[idx,1], c=rgb[idx], s=0.5, linewidths=0)
    ax.set_aspect("equal"); ax.invert_yaxis()
    ax.set_title(f"{s}\n{note}", fontsize=9)
for ax in axes.flat[len(CANDS):]: ax.axis("off")
fig.suptitle("InteriorGS candidate rooms — top-down (Z-up)", fontsize=14)
fig.tight_layout(); fig.savefig("outputs/07_candidate_rooms_topdown.png", dpi=100)
print("saved outputs/07_candidate_rooms_topdown.png")
print("uncompressed plys ready in:", ", ".join(s for s,_ in CANDS))
