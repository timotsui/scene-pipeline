"""Scene intake: Marble bundle -> pipeline artifacts, in the BUNDLE FRAME.
Deterministic, zero estimation, no per-scene anything. Run once per scene:

    python frame_bootstrap.py --scene <scene>

(out/<scene>/bundle_path.txt must point at the downloaded bundle folder.)

THE FRAME CONTRACT (settled 2026-08-06 with the user; evidence trail in
docs/PLAN_SCENE2_LIVING.md):
  - The Marble bundle is TRUSTED: splats.spz and collider.glb ship in ONE
    shared frame (verified by direct spz decode vs glb bounds; the whole
    318-world corpus is one uniform encode — header sweep). That frame is
    y-down: floor at +y, physical up = -y. This equals the convention the
    pipeline was tuned on (old bedroom), so ALL legacy constants apply:
    A2 pano mapping, raw_to_render rot180-about-z, viewer display rz=180.
  - splat-transform's spz->ply conversion applies a hidden rot180-about-x.
    Intake UNDOES it in the same command (-r 180,0,0), so gen_raw.ply ==
    the bundle frame exactly. The collider therefore needs NO transform:
    byte-copy. (The 07-07 manual bedroom download was a deprecated Marble
    encode, stored the other way up — it no longer exists on their CDN;
    old bedroom_marble artifacts are grandfathered reference data.)

Writes:
  gen_raw.ply                (spz converted + un-rotated, if not present)
  collider_registered.glb    (byte-copy of the bundle collider)
  collider_registration.json (T = identity, for CP7-shell + the viewer)
  frame_bootstrap.json       (floor_y/ceiling_y from collider bounds —
                              floor_y > ceiling_y numerically, y-down —
                              up = [0,-1,0]; pano_stitch's frame source)

Self-check (fail loudly, never guess): collider bounds must sit inside
the splat's robust bounds +-0.5 m on every axis.
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

import paths

UNROTATE = ["-r", "180,0,0"]     # undo the converter's rot180-about-x
BOUNDS_MARGIN = 0.5              # m, self-check tolerance

#: How much of the point cloud's outer tail the self-check ignores, per
#: axis per side. The check asks "is the collider inside the splat", and
#: a splat has stray specks well outside the room, so some trimming is
#: needed or the bound is meaningless.
#:
#: ⚠ 0.5 UNTIL 2026-08-11, AND IT WAS THE WRONG KNOB DOING THE WORK.
#: Measured across all 34 harvested worlds that have a collider: at 0.5
#: only 14 passed. But the frame was not the problem — with NO trimming
#: and NO margin, 33 of the 34 colliders sit ENTIRELY INSIDE their splat,
#: and the collider's height matches the splat's to within 1% in 27 of
#: them. What 0.5% was rejecting was a collider reaching into a corner
#: the generator rendered THINLY. The evidence is the splat count at the
#: offending face: 1,700-68,700 for worlds that passed, 0-3,446 for
#: worlds that failed. On the world this was found on, the rejected face
#: had 1,173 splats within 25 cm of it — a wall, not a speck.
#:
#: 0.05 recovers 29 of 34 with BOUNDS_MARGIN untouched. The alternative
#: lever, widening the margin, was measured and rejected: it needs 1.5 m
#: to reach 26 worlds and 3 m to reach 30, and a 3 m tolerance can no
#: longer detect a wrong frame at all, which is the only thing this check
#: exists for.
#:
#: THE CHECK'S REAL JOB IS UNAFFECTED. The one genuinely broken world in
#: the corpus (363c0b4f — collider floating 3.83 m above the highest
#: splat in the scene, ZERO splats within 25 cm of that face) fails at
#: this setting, at the old one, and with no margin at all.
#:
#: USER RULING 2026-08-11: "the world can mostly be trusted, we can
#: widen the margin." Applied on the percentile rather than the margin,
#: per the measurement above. Census: docs/REVIEW_LOG.md R-S2-97.
BOUNDS_TAIL_PCT = 0.05           # %, per axis per side


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
        print(f"[intake] converting {spz[0].name} -> gen_raw.ply "
              f"(un-rotating the converter's frame change)", flush=True)
        subprocess.run(["splat-transform", str(spz[0]), *UNROTATE, str(ply)],
                       check=True, shell=True)

    import trimesh
    mesh = trimesh.load(glb[0], force="mesh")
    m_lo, m_hi = mesh.bounds

    r3 = paths.load_r3()
    xyz, *_ = r3.load_splat(str(ply), opacity_min=0.3)
    s_lo = np.percentile(xyz, BOUNDS_TAIL_PCT, axis=0) - BOUNDS_MARGIN
    s_hi = np.percentile(xyz, 100 - BOUNDS_TAIL_PCT, axis=0) + BOUNDS_MARGIN
    if (m_lo < s_lo).any() or (m_hi > s_hi).any():
        # SAY HOW BADLY, AND ON WHICH AXIS. The old message printed two
        # bounding boxes and left the reader to subtract them by eye, on
        # the stage that is a scene's very first. Overshoot per axis is
        # what actually distinguishes a wrong frame (metres, several
        # axes) from a collider grazing a thinly-rendered corner
        # (centimetres, one axis) — see BOUNDS_TAIL_PCT above.
        over_lo = np.maximum(s_lo - m_lo, 0.0)
        over_hi = np.maximum(m_hi - s_hi, 0.0)
        worst = max(over_lo.max(), over_hi.max())
        axes = ", ".join(
            f"{ax}_{side} by {v:.2f} m"
            for ax, lo, hi in zip("xyz", over_lo, over_hi)
            for side, v in (("min", lo), ("max", hi)) if v > 0)
        raise SystemExit(
            f"[intake] CONTRACT VIOLATION: the collider reaches outside "
            f"the splat by up to {worst:.2f} m ({axes}).\n"
            f"  collider {m_lo.round(2)} .. {m_hi.round(2)}\n"
            f"  splat    {s_lo.round(2)} .. {s_hi.round(2)}  "
            f"(tail {BOUNDS_TAIL_PCT}% trimmed, margin {BOUNDS_MARGIN} m)\n"
            f"  The two files disagree about where this room is, so every "
            f"box measured from them would be wrong. Refusing to guess a "
            f"frame — a square room looks the same upside down, so there "
            f"is nothing here to estimate from.")

    shutil.copyfile(glb[0], sd / "collider_registered.glb")
    (sd / "collider_registration.json").write_text(json.dumps(
        {"scene": sc, "collider": glb[0].name,
         "method": "trusted bundle frame (identity; ply un-rotated to the "
                   "bundle frame at conversion)",
         "T": np.eye(4).tolist(), "scale": 1.0}, indent=1))

    # y-down: floor is the HIGH y bound, ceiling the LOW one (floor_y >
    # ceiling_y numerically — same pattern as the bedroom manifest record)
    floor_y, ceil_y = float(m_hi[1]), float(m_lo[1])
    # Full legacy-frame-block schema so every downstream legacy read
    # (room_shell, envelope, ...) falls back to this file with no schema
    # branch. raw_to_render is the bundle-frame-class CONSTANT (rot180-
    # about-z), defined by the frame contract, never estimated; extents are
    # the splat's robust percentiles (the legacy block's convention).
    e_p1 = np.percentile(xyz, 1, axis=0).round(3)
    e_p99 = np.percentile(xyz, 99, axis=0).round(3)
    (sd / "frame_bootstrap.json").write_text(json.dumps(
        {"scene": sc, "source": "scene intake (frame_bootstrap.py)",
         "space": "raw",
         "up": [0.0, -1.0, 0.0],
         "floor_y": round(floor_y, 3), "ceiling_y": round(ceil_y, 3),
         "extent_p1": e_p1.tolist(), "extent_p99": e_p99.tolist(),
         "raw_to_render": [-1.0, -1.0, 1.0],
         "note": "BUNDLE frame == pipeline frame (y-down, physical up = "
                 "-y). floor/ceiling from collider bounds (skirt-level, "
                 "~3 cm outside true surfaces — fine for camera "
                 "placement; room_shell measures true surfaces later). "
                 "raw_to_render = toolchain constant (frame contract), "
                 "not calibrated."},
        indent=1))
    print(f"[intake] {sc}: floor {floor_y:.3f} > ceiling {ceil_y:.3f} "
          f"(y-down)  collider = byte-copy  [OK]", flush=True)


if __name__ == "__main__":
    main()
