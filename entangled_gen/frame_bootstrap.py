"""Scene intake: Marble bundle -> pipeline-frame artifacts. Deterministic,
zero estimation, no per-scene anything. Run once per fresh scene:

    python frame_bootstrap.py --scene <scene>

(out/<scene>/bundle_path.txt must point at the downloaded bundle folder.)

THE FRAME CONTRACT (established 2026-08-06, scene #2 forensics — evidence
trail in docs/PLAN_SCENE2_LIVING.md):
  - The Marble bundle is TRUSTED: splats.spz and collider.glb ship in ONE
    frame (verified by direct spz decode vs glb bounds). No registration,
    no verification stages.
  - splat-transform's spz->ply conversion applies a fixed frame change:
    rot180 about x (y,z negated). Therefore the PIPELINE frame (what
    gen_raw.ply and every downstream stage speak) = rot180x(bundle frame),
    and the collider enters the pipeline through the same constant.
  - In the pipeline frame: up = +y, pano readability mirror = mirror-x
    (signs [-1,1,1]) — DEFINED by the two facts above, not estimated.

Writes:
  gen_raw.ply                (splat-transform, if not already present)
  collider_registered.glb    (bundle collider, rot180x into pipeline frame)
  collider_registration.json (the constant T, for CP7-shell + viewer)
  frame_bootstrap.json       (floor_y/ceiling_y from the rotated collider
                              bounds, up, pano signs — pano_stitch input)

Self-check (honest autonomy, fail loudly): the rotated collider bounds
must sit inside the splat's robust bounds +-0.5 m on every axis; if not,
the bundle violates the contract above and intake REFUSES rather than
guesses.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np
import trimesh

import paths

# rot180 about x: the splat-transform spz->ply frame change (constant)
T_CONVERTER = np.diag([1.0, -1.0, -1.0, 1.0])
PANO_SIGNS = [-1.0, 1.0, 1.0]          # readability mirror, pipeline frame
BOUNDS_MARGIN = 0.5                    # m, self-check tolerance


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    sc = ap.parse_args().scene
    sd = paths.scene_dir(sc)
    sd.mkdir(exist_ok=True)

    bp = sd / "bundle_path.txt"
    if not bp.exists():
        raise SystemExit(f"[intake] {bp} missing — point it at the bundle")
    bundle = Path(bp.read_text(encoding="utf-8-sig").strip())
    spz = sorted(bundle.glob("*.spz"))
    glb = sorted(bundle.glob("*collider*.glb"))
    if not spz or not glb:
        raise SystemExit(f"[intake] bundle incomplete: spz={bool(spz)} "
                         f"collider={bool(glb)} in {bundle}")

    ply = paths.ply(sc)
    if not ply.exists():
        print(f"[intake] converting {spz[0].name} -> gen_raw.ply", flush=True)
        subprocess.run(["splat-transform", str(spz[0]), str(ply)],
                       check=True, shell=True)

    mesh = trimesh.load(glb[0], force="mesh")
    mesh.apply_transform(T_CONVERTER)

    # self-check against the splat (robust bounds only — NOT an estimator)
    r3 = paths.load_r3()
    xyz, *_ = r3.load_splat(str(ply), opacity_min=0.3)
    s_lo = np.percentile(xyz, 0.5, axis=0) - BOUNDS_MARGIN
    s_hi = np.percentile(xyz, 99.5, axis=0) + BOUNDS_MARGIN
    m_lo, m_hi = mesh.bounds
    if (m_lo < s_lo).any() or (m_hi > s_hi).any():
        raise SystemExit(
            f"[intake] CONTRACT VIOLATION: rotated collider bounds "
            f"[{m_lo.round(2)},{m_hi.round(2)}] outside splat bounds "
            f"[{s_lo.round(2)},{s_hi.round(2)}] — this bundle does not "
            f"match the trusted-frame contract; refusing to guess.")

    mesh.export(sd / "collider_registered.glb")
    (sd / "collider_registration.json").write_text(json.dumps(
        {"scene": sc, "collider": glb[0].name,
         "method": "trusted-bundle + converter constant (rot180x)",
         "T": T_CONVERTER.tolist(), "scale": 1.0}, indent=1))

    floor_y, ceil_y = float(m_lo[1]), float(m_hi[1])
    (sd / "frame_bootstrap.json").write_text(json.dumps(
        {"scene": sc, "source": "scene intake (frame_bootstrap.py)",
         "up": [0.0, 1.0, 0.0],
         "floor_y": round(floor_y, 3), "ceiling_y": round(ceil_y, 3),
         "pano_to_raw_signs": PANO_SIGNS,
         "note": "pipeline frame = rot180x(bundle frame); all values are "
                 "defined constants or collider bounds — nothing estimated. "
                 "floor_y/ceiling_y are BOUNDS (skirt-level, ~3 cm outside "
                 "the true surfaces) — good enough for camera placement; "
                 "room_shell measures true surfaces later."}, indent=1))
    print(f"[intake] {sc}: floor {floor_y:.3f}  ceiling {ceil_y:.3f}  "
          f"collider rot180x -> pipeline frame  [OK]", flush=True)


if __name__ == "__main__":
    main()
