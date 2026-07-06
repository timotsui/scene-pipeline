"""Snow-speckle diagnosis: same yaw270 view, three render variants."""
import importlib.util
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
W5 = HERE / "rendertools"  # local copies (2026-07-05); week5 originals frozen
spec = importlib.util.spec_from_file_location("render03", W5 / "03_render.py")
r3 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(r3)

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

PLY = HERE / "out" / "playroom" / "gen_raw.ply"
OUT = HERE / "out" / "playroom" / "views"

xyz, rgb, alpha, radius = r3.load_splat(str(PLY), opacity_min=0.3)
print(f"opacity>=0.3 keeps {len(xyz):,}", flush=True)

pos, look, up = (0, 0, 0), (np.sin(np.radians(270)), 0, np.cos(np.radians(270))), (0, 1, 0)

for tag, rmul in (("r1", 1.0), ("r2", 2.0), ("r3", 3.0)):
    img = r3.render_view(xyz, rgb, alpha, radius * rmul, pos, look, up=up, fov=75, w=640, h=480)
    img = img[0] if isinstance(img, tuple) else img
    plt.imsave(OUT / f"yaw270_{tag}.png", np.clip(img, 0, 1))
    print("wrote", tag, flush=True)
