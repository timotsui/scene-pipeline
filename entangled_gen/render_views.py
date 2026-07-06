"""
First-look renders of the generated splat (playroom_raw.ply) using the week5
CPU renderer (03_render.py). Doubles as the run-8 quality gate and as input
for the 2D-segmentation lift.

LucidDreamer generates its point cloud from cameras at/near the ORIGIN, so the
room surrounds (0,0,0). Generator frame: fullscan poses rotate about +Y => Y is
the vertical axis (sign TBD from the renders).
"""
import sys, importlib.util
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
W5 = HERE / "rendertools"  # local copies (2026-07-05); week5 originals frozen

spec = importlib.util.spec_from_file_location("render03", W5 / "03_render.py")
r3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r3)

PLY = HERE / "out" / "playroom" / "gen_raw.ply"  # GENERATED leg (week5 playroom.ply = real-scan leg)
OUT = HERE / "out" / "playroom" / "views"
OUT.mkdir(parents=True, exist_ok=True)

print("loading splat...", flush=True)
xyz, rgb, alpha, radius = r3.load_splat(str(PLY))
print(f"kept {len(xyz):,} gaussians after opacity filter", flush=True)
lo, hi = np.percentile(xyz, 1, axis=0), np.percentile(xyz, 99, axis=0)
print(f"extent p1..p99: x[{lo[0]:.2f},{hi[0]:.2f}] y[{lo[1]:.2f},{hi[1]:.2f}] z[{lo[2]:.2f},{hi[2]:.2f}]", flush=True)

def save(img, name):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    plt.imsave(OUT / name, np.clip(img, 0, 1))
    print("wrote", OUT / name, flush=True)

# yaw ring from origin, horizontal + slightly down, both up-sign candidates handled
# by just looking at the output (renderer's Cam takes an explicit up vector).
VIEWS = []
for yaw in (0, 90, 180, 270):
    th = np.radians(yaw)
    look = (np.sin(th), 0.0, np.cos(th))
    VIEWS.append((f"yaw{yaw:03d}", (0, 0, 0), look, (0, 1, 0)))

for name, pos, look, up in VIEWS:
    print(f"rendering {name} ...", flush=True)
    out = r3.render_view(xyz, rgb, alpha, radius, pos, look, up=up, fov=75, w=640, h=480)
    img = out[0] if isinstance(out, tuple) else out
    save(img, f"{name}.png")

print("done", flush=True)
