"""Render an orbit of views around the playroom via splat-transform (GPU), montage them.
Y-up scene; camera circles in X-Z plane at mid-height, looks at robust center."""
import subprocess, numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from pathlib import Path
from PIL import Image

PLY = "data/superspl/playroom.ply"
OUT = Path("views"); OUT.mkdir(exist_ok=True)
CEN = np.array([1.35, -1.33, -2.91])     # robust center (opaque gaussians)
DIST, HEIGHT, FOV, RES = 4.8, 0.6, 65, "800x800"

def render(name, eye, look, up=(0,1,0)):
    dst = OUT / f"{name}.webp"
    cmd = (f'splat-transform -w -q -g 0 "{PLY}" '
           f'--camera {",".join(f"{v:.3f}" for v in eye)} '
           f'--look-at {",".join(f"{v:.3f}" for v in look)} '
           f'--up {",".join(str(v) for v in up)} '
           f'--fov {FOV} --resolution {RES} --background 0.08,0.08,0.1 "{dst}"')
    subprocess.run(cmd, check=True, shell=True)
    return dst

views = {}
for k in range(6):
    ang = np.radians(60*k)
    eye = CEN + np.array([DIST*np.cos(ang), HEIGHT, DIST*np.sin(ang)])
    views[f"orbit_{60*k:03d}"] = render(f"orbit_{60*k:03d}", eye, CEN)
# add a near-top-down (camera above, looking down; up = -Z so image is oriented)
views["topdown"] = render("topdown", CEN + np.array([0, 3.2, 0.01]), CEN, up=(0,0,-1))

fig, ax = plt.subplots(2, 4, figsize=(18, 9))
for a, (name, p) in zip(ax.flat, views.items()):
    a.imshow(Image.open(p).convert("RGB")); a.set_title(name, fontsize=10); a.axis("off")
for a in ax.flat[len(views):]: a.axis("off")
fig.suptitle("Playroom — splat-transform GPU orbit (5s/view)", fontsize=14)
fig.tight_layout(); fig.savefig("outputs/19_orbit.png", dpi=100)
print("saved outputs/19_orbit.png ;", len(views), "views in views/")
