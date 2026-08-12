"""Scene intake: Marble bundle -> pipeline artifacts, in the BUNDLE FRAME.
Deterministic, no per-scene anything. Run once per scene:

    python frame_bootstrap.py --scene <scene>

(out/<scene>/bundle_path.txt must point at the downloaded bundle folder.)

THE FRAME CONTRACT (settled 2026-08-06 with the user; evidence trail in
docs/plans/PLAN_SCENE2_LIVING.md):
  - The Marble bundle is TRUSTED: every harvested world ships one uniform
    y-down encode (318-world header sweep): floor at +y, physical up = -y.
    This equals the convention the pipeline was tuned on (old bedroom), so
    ALL legacy constants apply: A2 pano mapping, raw_to_render rot180-
    about-z, viewer display rz=180.
  - splat-transform's spz->ply conversion applies a hidden rot180-about-x.
    Intake UNDOES it in the same command (-r 180,0,0), so gen_raw.ply ==
    the bundle frame exactly. A collider, when present, therefore needs NO
    transform: byte-copy. (The 07-07 manual bedroom download was a
    deprecated Marble encode — grandfathered reference data.)

THE COLLIDER IS OPTIONAL (user rulings 2026-08-11, PLAN_COLLIDER_OPTIONAL
+ REVIEW_LOG R-S2-110/111). 284 of the 318 harvested worlds have no
collider at all, and the paired-floor census showed the collider's floor
is the WORSE measurement wherever the two disagree (its skirt hangs up to
56 cm below a level where the splat has almost no points). So:
  - floor_y/ceiling_y are measured FROM THE SPLAT on every scene — the
    same clip + histogram room_shell uses at stage 11 (the function is
    imported from room_shell, never duplicated), so the camera stands on
    the same floor the shell will later confirm.
  - a collider, when present, still runs the trusted-bundle agreement
    check. A disagreement CONDEMNS THE COLLIDER, NOT THE WORLD (user
    ruling): it is reported and recorded, the collider is NOT registered,
    and the scene runs as colliderless. It no longer refuses the scene.
  - a missing .spz is still fatal. There is no scene without the splat.

Writes:
  gen_raw.ply                (spz converted + un-rotated, if not present)
  collider_registered.glb    (byte-copy — ONLY if a collider is present
  collider_registration.json  AND it agrees with the splat)
  frame_bootstrap.json       (floor_y/ceiling_y measured from the splat —
                              floor_y > ceiling_y numerically, y-down —
                              up = [0,-1,0]; floor_source + the collider
                              check's verdict recorded; pano_stitch's
                              frame source)
"""
import argparse
import json
import shutil
import subprocess
from pathlib import Path

import numpy as np

import paths

UNROTATE = ["-r", "180,0,0"]     # undo the converter's rot180-about-x
BOUNDS_MARGIN = 0.5              # m, agreement-check tolerance

#: How much of the point cloud's outer tail the agreement check ignores,
#: per axis per side. The check asks "is the collider inside the splat",
#: and a splat has stray specks well outside the room, so some trimming
#: is needed or the bound is meaningless.
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
#: USER RULING 2026-08-11: "the world can mostly be trusted, we can
#: widen the margin." Applied on the percentile rather than the margin,
#: per the measurement above. Census: docs/REVIEW_LOG.md R-S2-97.
#: Since R-S2-111 a failed check no longer refuses the scene — it
#: condemns the collider and the scene runs colliderless.
BOUNDS_TAIL_PCT = 0.05           # %, per axis per side


def splat_floor_ceiling(xyz, e_p1, e_p99):
    """floor_y/ceiling_y (RAW frame, y-down) measured from the splat.

    EXACTLY room_shell's stage-11 measurement, on the same clip: points
    to upright, clipped to the robust extents ± SEARCH (floaters leaking
    through openings once dragged the histogram split 10 m off —
    room_shell.py:201-208), then measure_floor_ceiling — IMPORTED from
    room_shell so the two stages can never disagree by construction."""
    import room_shell
    r2r = np.array([-1.0, -1.0, 1.0])
    up = xyz * r2r
    ext_lo = np.minimum(e_p1 * r2r, e_p99 * r2r) - room_shell.SEARCH
    ext_hi = np.maximum(e_p1 * r2r, e_p99 * r2r) + room_shell.SEARCH
    pts = up[np.all((up >= ext_lo) & (up <= ext_hi), axis=1)]
    if not len(pts):
        raise SystemExit("[intake] no splat points inside the robust "
                         "extents — the splat is degenerate, refusing")
    floor_up, ceil_up = room_shell.measure_floor_ceiling(pts)
    return -floor_up, -ceil_up       # back to raw y-down


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
    if not spz:
        raise SystemExit(f"[intake] bundle has no .spz in {bundle} — "
                         f"there is no scene without the splat")

    ply = paths.ply(sc)
    if not ply.exists():
        print(f"[intake] converting {spz[0].name} -> gen_raw.ply "
              f"(un-rotating the converter's frame change)", flush=True)
        subprocess.run(["splat-transform", str(spz[0]), *UNROTATE, str(ply)],
                       check=True, shell=True)

    r3 = paths.load_r3()
    xyz, *_ = r3.load_splat(str(ply), opacity_min=0.3)
    e_p1 = np.percentile(xyz, 1, axis=0).round(3)
    e_p99 = np.percentile(xyz, 99, axis=0).round(3)

    # THE FLOOR AND CEILING — from the splat, every scene (R-S2-111)
    floor_y, ceil_y = splat_floor_ceiling(xyz, e_p1, e_p99)

    # THE COLLIDER — optional; checked and registered only when it agrees
    collider_rec = {"present": bool(glb), "registered": False,
                    "check": None}
    if glb:
        import trimesh
        mesh = trimesh.load(glb[0], force="mesh")
        m_lo, m_hi = mesh.bounds
        s_lo = np.percentile(xyz, BOUNDS_TAIL_PCT, axis=0) - BOUNDS_MARGIN
        s_hi = np.percentile(xyz, 100 - BOUNDS_TAIL_PCT, axis=0) \
            + BOUNDS_MARGIN
        if (m_lo < s_lo).any() or (m_hi > s_hi).any():
            # Overshoot per axis is what distinguishes a wrong frame
            # (metres, several axes) from a collider grazing a thinly-
            # rendered corner (centimetres, one axis) — BOUNDS_TAIL_PCT.
            over_lo = np.maximum(s_lo - m_lo, 0.0)
            over_hi = np.maximum(m_hi - s_hi, 0.0)
            worst = float(max(over_lo.max(), over_hi.max()))
            axes = ", ".join(
                f"{ax}_{side} by {v:.2f} m"
                for ax, lo, hi in zip("xyz", over_lo, over_hi)
                for side, v in (("min", lo), ("max", hi)) if v > 0)
            print(f"[intake] COLLIDER CONDEMNED, SCENE CONTINUES: the "
                  f"collider reaches outside the splat by up to "
                  f"{worst:.2f} m ({axes}).\n"
                  f"  A disagreeing collider says the COLLIDER is wrong, "
                  f"not the world (user ruling 2026-08-11). It is NOT "
                  f"registered; this scene runs colliderless, floor from "
                  f"the splat like every other.", flush=True)
            collider_rec.update({
                "check": "fail",
                "collider": glb[0].name,
                "worst_overshoot_m": round(worst, 3),
                "overshoot_axes": axes})
        else:
            shutil.copyfile(glb[0], sd / "collider_registered.glb")
            (sd / "collider_registration.json").write_text(json.dumps(
                {"scene": sc, "collider": glb[0].name,
                 "method": "trusted bundle frame (identity; ply un-rotated "
                           "to the bundle frame at conversion)",
                 "T": np.eye(4).tolist(), "scale": 1.0}, indent=1))
            collider_rec.update({
                "check": "pass", "registered": True,
                "collider": glb[0].name,
                "collider_floor_y": round(float(m_hi[1]), 3),
                "collider_ceiling_y": round(float(m_lo[1]), 3)})
    if not collider_rec["registered"]:
        # a registered collider from an earlier run of a scene whose
        # collider is now absent or condemned would be a lie on disk
        for stale in ("collider_registered.glb", "collider_registration.json"):
            f = sd / stale
            if f.exists():
                print(f"[intake] removing stale {stale} — this scene is "
                      f"colliderless now", flush=True)
                f.unlink()

    (sd / "frame_bootstrap.json").write_text(json.dumps(
        {"scene": sc, "source": "scene intake (frame_bootstrap.py)",
         "space": "raw",
         "up": [0.0, -1.0, 0.0],
         "floor_y": round(floor_y, 3), "ceiling_y": round(ceil_y, 3),
         "extent_p1": e_p1.tolist(), "extent_p99": e_p99.tolist(),
         "raw_to_render": [-1.0, -1.0, 1.0],
         "floor_source": "splat",
         "collider": collider_rec,
         "note": "BUNDLE frame == pipeline frame (y-down, physical up = "
                 "-y). floor/ceiling measured from the splat (room_shell's "
                 "own clip + histogram, R-S2-111) — fine for camera "
                 "placement; room_shell re-measures at stage 11 with the "
                 "same function. raw_to_render = toolchain constant "
                 "(frame contract), not calibrated."},
        indent=1))
    coll_word = ("collider = byte-copy" if collider_rec["registered"] else
                 ("collider CONDEMNED (check fail)"
                  if collider_rec["check"] == "fail" else "no collider"))
    print(f"[intake] {sc}: floor {floor_y:.3f} > ceiling {ceil_y:.3f} "
          f"(y-down, splat-measured)  {coll_word}  [OK]", flush=True)


if __name__ == "__main__":
    main()
