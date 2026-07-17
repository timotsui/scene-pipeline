"""Render the judge-camera views of a scene's splat (full-room coverage).

Why: the refinement loop (composition/loop.py) verifies each edit by
comparing splat renders ("original") against mesh renders ("recreation")
from the SAME cameras. The old 4-view set (gpu_yaw*, horizontal, 90 deg
apart, fov 75) cannot see the floor within ~2.1 m of the camera or the
four 15-deg wedges between views, so edits placed there render zero
changed pixels and get auto-rejected (2026-07-15B handoff).

This tiles the viewing sphere from the ONE standpoint the splat looks
best from (the capture point, eye height):
  - 6 views 60 deg apart, tilted down (look height 0.85 m): walls +
    floor beyond ~1.3 m, overlapping, no wedge gaps
  - 1 straight-down view (fov 85): the floor disk under the camera

Writes views/judge_yaw{000..300}.webp + judge_down.webp with the same
.json sidecar format as rendertools/shot.py (cam/look/up/fov/near/res),
so place2/loop can consume them unchanged. gpu_yaw* files are NOT
touched — they carry detection provenance.

Usage:  python render_judge_views.py --scene bedroom_marble [--force]
"""
import argparse
import csv
import json
import math
import subprocess
import time

import paths

CAM = (0.0, 1.6, 0.0)     # render frame (y up, floor ~0): same standpoint as gpu_yaw*
LOOK_DIST = 3.0           # ring look targets: 3 m out ...
LOOK_H = 0.85             # ... at 0.85 m height -> ~14 deg down-tilt
RING_FOV = 75.0           # matches gpu_yaw*; 6 x 75 deg at 60-deg spacing overlaps
DOWN_FOV = 85.0           # floor visible to ~1.5 m radius, overlaps the ring's ~1.3 m
RES = "900x900"
NEAR = 0.2
BACKGROUND = "0.08,0.08,0.1"   # same as shot.py

META_COLS = ["file", "time", "preset", "cam", "look", "up", "fov", "near",
             "box", "sphere", "res", "ply"]  # shot.py's shots.csv schema


def rig():
    """[(name, cam, look, up, fov)] — the judge cameras."""
    views = []
    for yaw in range(0, 360, 60):
        th = math.radians(yaw)
        look = (LOOK_DIST * math.sin(th), LOOK_H, LOOK_DIST * math.cos(th))
        views.append((f"judge_yaw{yaw:03d}", CAM, look, (0, 1, 0), RING_FOV))
    # straight down; up vector just fixes image orientation (any horizontal works)
    views.append(("judge_down", CAM, (0.0, 0.0, 0.0), (0, 0, -1), DOWN_FOV))
    return views


def fmt(v):
    return ",".join(f"{c:g}" for c in v)


def record(out, meta):
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    manifest = out.parent / "shots.csv"
    header = not manifest.exists()
    with manifest.open("a", newline="") as f:
        w = csv.writer(f)
        if header:
            w.writerow(META_COLS)
        w.writerow([meta[c] for c in META_COLS])


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scene", required=True)
    ap.add_argument("--gpu", default="0")
    ap.add_argument("--force", action="store_true",
                    help="re-render views that already exist")
    a = ap.parse_args()

    ply = paths.ply(a.scene)
    if not ply.exists():
        raise SystemExit(f"no splat: {ply}")
    vdir = paths.views_dir(a.scene)
    vdir.mkdir(parents=True, exist_ok=True)

    for name, cam, look, up, fov in rig():
        out = vdir / f"{name}.webp"
        if out.exists() and not a.force:
            print(f"skip {out.name} (exists)")
            continue
        cmd = ["splat-transform", "-w", "-g", a.gpu, str(ply),
               "--camera", fmt(cam), "--look-at", fmt(look), "--up", fmt(up),
               "--fov", str(fov), "--near", str(NEAR),
               "--resolution", RES, "--background", BACKGROUND, str(out)]
        print(f"rendering {out.name}  cam={fmt(cam)} look={fmt(look)} "
              f"up={fmt(up)} fov={fov} ...", flush=True)
        subprocess.run(cmd, check=True, shell=True, timeout=600)
        record(out, {"file": out.name,
                     "time": time.strftime("%Y-%m-%d %H:%M:%S"),
                     "preset": "judge_rig", "cam": fmt(cam), "look": fmt(look),
                     "up": fmt(up), "fov": fov, "near": NEAR, "box": "",
                     "sphere": "", "res": RES, "ply": str(ply)})
    print("done ->", vdir)


if __name__ == "__main__":
    main()
