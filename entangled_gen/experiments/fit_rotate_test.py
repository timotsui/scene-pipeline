"""
FIT ROTATE TEST (2026-08-04, user: "are we able to do small rotations,
say up to 45 degrees, to make the object fit"): measure, per flagged
fit_check item, whether a small yaw (+-45 deg, 7.5 deg steps, about the
item's own center; wall items re-flushed to their wall after) reduces
its physical findings. REPORT ONLY -- the preview is not touched.

Scoring per pose, same machinery as fit_check: shell-bounds penetration
(vertex-exact, mm) + clip volume vs the OTHER items' static occupied
cells (2 cm lattice, litres). Verdict per item: CLEARED (both under
tolerance), IMPROVED, or NO_HELP.

Caveats: tiled items (k>1) rotate as one rigid group; neighbors are
held FIXED at their current poses, so pair fixes that need both to
move will read as partial.

Run:  python experiments/fit_rotate_test.py --scene bedroom_marble
Out:  out/<scene>/compose/fit_rotate_test.json + console table
"""
import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "compose"))
import paths  # noqa: E402
from fit_check import (load_placed, cell_keys, bounds_findings,  # noqa: E402
                       PITCH, TOL, CONTACT_CELLS)

ANGLES = [round(a * 7.5, 1) for a in range(-6, 7)]   # -45..45, 0 included


def yaw_about(mesh, center, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    R = np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0],
                  [0, 0, 0, 1]])
    T1 = np.eye(4); T1[:3, 3] = -np.asarray(center)
    T2 = np.eye(4); T2[:3, 3] = np.asarray(center)
    m = mesh.copy()
    m.apply_transform(T2 @ R @ T1)
    return m


def reflush(mesh, fdir, wx, wz):
    """Wall items: after the spin, push flush again along the wall
    normal (same rule as fit_preview's mesh-flush snap)."""
    lo, hi = mesh.bounds
    d = np.zeros(3)
    if abs(fdir[0]) >= abs(fdir[1]):
        d[0] = (wx[0] - lo[0]) if fdir[0] > 0 else (wx[1] - hi[0])
    else:
        d[2] = (wz[0] - lo[2]) if fdir[1] > 0 else (wz[1] - hi[2])
    mesh.apply_translation(d)
    return mesh


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()

    cdir, by_item, wx, wz, fy, cy, r2r = load_placed(args.scene)
    fp = json.loads((cdir / "fitted_preview.json").read_text(
        encoding="utf-8"))
    fc = json.loads((cdir / "fit_check.json").read_text(encoding="utf-8"))
    names = {p["id"]: p["name"] for p in fp["placed"]}
    mounts = {p["id"]: p["mount"] for p in fp["placed"]}
    fronts = {p["id"]: p.get("front_dir_raw") for p in fp["placed"]}

    flagged = {it["id"] for it in fc["items"] if it["bounds"]}
    for p in fc["clips"]:
        if p["overlap_cells"] > CONTACT_CELLS:
            flagged.add(p["a"]); flagged.add(p["b"])
    flagged = sorted(flagged)

    print(f"[rotate] voxelizing {len(by_item)} items once ...")
    cells = {oid: cell_keys(m) for oid, m in by_item.items()}

    def score(oid, mesh):
        bf = bounds_findings(mesh.vertices, wx, wz, fy, cy)
        oob = sum(f["depth_mm"] for f in bf)
        others = np.concatenate([cells[k] for k in by_item if k != oid])
        others = np.unique(others)
        inter = np.intersect1d(cell_keys(mesh), others,
                               assume_unique=True)
        clip_cells = max(0, len(inter) - CONTACT_CELLS)
        return oob, round(clip_cells * PITCH ** 3 * 1000, 2), bf

    rows = []
    for oid in flagged:
        mesh0 = by_item[oid]
        lo, hi = mesh0.bounds
        ctr = (lo + hi) / 2
        # front_dir_raw is stored in RAW xz; back to render for reflush
        fd = fronts.get(oid)
        fdir = ((fd[0] * float(r2r[0]), fd[1] * float(r2r[2]))
                if fd else None)
        best = None
        base = None
        for deg in ANGLES:
            m = yaw_about(mesh0, ctr, deg) if deg else mesh0.copy()
            if mounts.get(oid) == "wall" and fdir is not None:
                m = reflush(m, fdir, wx, wz)
            oob, clip, bf = score(oid, m)
            if deg == 0:
                base = (oob, clip)
            tot = clip + oob / 10.0        # fixed blend, doc'd in header
            if best is None or tot < best[0]:
                best = (tot, deg, oob, clip)
        _, bdeg, boob, bclip = best
        cleared = boob <= TOL * 1000 and bclip <= 0
        improved = (bclip + boob / 10.0) < 0.95 * (base[1] + base[0] / 10.0)
        verdict = ("CLEARED" if cleared else
                   "IMPROVED" if improved else "NO_HELP")
        rows.append({"id": oid, "name": names.get(oid),
                     "mount": mounts.get(oid),
                     "base_oob_mm": round(base[0], 1),
                     "base_clip_l": base[1],
                     "best_deg": bdeg,
                     "best_oob_mm": round(boob, 1),
                     "best_clip_l": bclip,
                     "verdict": verdict})
        print(f"  {oid:14s} {str(names.get(oid)):22s} "
              f"base oob {base[0]:6.0f}mm clip {base[1]:5.1f}L | "
              f"best {bdeg:+5.1f}deg -> oob {boob:6.0f}mm "
              f"clip {bclip:5.1f}L  {verdict}")

    out = {"scene": args.scene, "built": str(date.today()),
           "generated_by": "experiments/fit_rotate_test.py",
           "note": "small-yaw (-45..45 x 7.5 deg) feasibility per "
                   "flagged fit_check item; neighbors fixed; report "
                   "only, preview untouched",
           "angles": ANGLES,
           "elapsed_s": round(time.time() - t0, 1),
           "items": rows}
    out_p = cdir / "fit_rotate_test.json"
    out_p.write_text(json.dumps(out, indent=1), encoding="utf-8")
    n = {"CLEARED": 0, "IMPROVED": 0, "NO_HELP": 0}
    for r in rows:
        n[r["verdict"]] += 1
    print(f"[rotate] {len(rows)} items: {n['CLEARED']} cleared, "
          f"{n['IMPROVED']} improved, {n['NO_HELP']} no help "
          f"({time.time() - t0:.0f}s) -> {out_p}")


if __name__ == "__main__":
    main()
