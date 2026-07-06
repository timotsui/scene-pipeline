"""
Frame-debug splat: 8 fat gaussians at the corners of a 2 m cube (+/-1 on each
axis), colored so the COLOR IS THE COORDINATE:

    red   channel on  <=>  x = +1
    green channel on  <=>  y = +1
    blue  channel on  <=>  z = +1

    (+1,+1,+1) white    (-1,-1,-1) dark grey   (+1,-1,-1) red
    (-1,+1,-1) green    (-1,-1,+1) blue        (+1,+1,-1) yellow
    (+1,-1,+1) magenta  (-1,+1,+1) cyan

Drop out/_debug/cube8.ply into any renderer (SuperSplat, our viewer, shot.py)
and read the transform straight off the corner colors: greenish corners on top
means y drawn up as-is; greenish on the bottom means the display flips y; etc.

Each corner is a ball of PTS_PER_CORNER jittered gaussians so it is visible in
the point viewer too (prep_scene draws one 1.4 cm sprite per gaussian).

Field layout matches gen_raw.ply exactly (62 floats, SH deg 3 zeros).

Run:  python debug_cube_ply.py
"""
from pathlib import Path
import numpy as np

import paths
from splat_place import write_ply

C0 = 0.28209479177387814
PTS_PER_CORNER = 2000
JITTER = 0.08        # ball radius (m)
SIZE = 0.02          # per-gaussian sigma (m)
OPACITY = 9.0        # logit, sigmoid(9) ~ 0.9999

NAMES = (["x", "y", "z", "nx", "ny", "nz", "f_dc_0", "f_dc_1", "f_dc_2"]
         + [f"f_rest_{i}" for i in range(45)]
         + ["opacity", "scale_0", "scale_1", "scale_2",
            "rot_0", "rot_1", "rot_2", "rot_3"])


def main():
    rng = np.random.default_rng(0)
    rows = []
    for x in (-1.0, 1.0):
        for y in (-1.0, 1.0):
            for z in (-1.0, 1.0):
                rgb = np.array([x > 0, y > 0, z > 0], np.float32)
                rgb = np.maximum(rgb, 0.15)       # black corner -> dark grey
                block = np.zeros((PTS_PER_CORNER, len(NAMES)), np.float32)
                jit = rng.normal(0, JITTER / 2, (PTS_PER_CORNER, 3)).clip(-JITTER, JITTER)
                block[:, 0:3] = np.array([x, y, z], np.float32) + jit
                block[:, 6:9] = (rgb - 0.5) / C0
                block[:, 54] = OPACITY
                block[:, 55:58] = np.log(SIZE)
                block[:, 58] = 1.0                 # identity quaternion
                rows.append(block)
    out = paths.OUT / "_debug" / "cube8.ply"
    out.parent.mkdir(parents=True, exist_ok=True)
    write_ply(out, NAMES, np.concatenate(rows))
    print(f"wrote {out} ({PTS_PER_CORNER * 8} gaussians, 8 corner balls)")
    print("legend: R<=>x+  G<=>y+  B<=>z+   "
          "(white=+++ , darkgrey=--- , red=+-- , green=-+- , blue=--+ , "
          "yellow=++- , magenta=+-+ , cyan=-++)")


if __name__ == "__main__":
    main()
