"""
FIT CARDINAL TEST (2026-08-04, user rulings after the small-yaw sheet:
(1) clipping is NOT in the rotation objective -- rotate to fit the box
first, clip resolution is a later step; (2) prefer CARDINAL axes: an
elongated object's long axis snaps to the box's long axis): per
flagged fit_check item, evaluate the four cardinal yaws about the box
center, re-seated by mount rule (floor: bottom to box bottom; wall:
re-flushed; ceiling: top to box top), and score ONLY

  - box overhang per horizontal axis (mesh extent - box extent, mm)
  - shell out-of-bounds after re-seating (vertex-exact, mm)

Long-axis-aligned cardinals win ties; facing is NOT scored here (the
facing rule + rotation_check own that). REPORT ONLY.

Run:  python experiments/fit_cardinal_test.py --scene bedroom_marble
Out:  out/<scene>/compose/fit_cardinal_test.json + console table
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
import trimesh  # noqa: E402
from fit_check import load_placed, bounds_findings, TOL  # noqa: E402

ELONG = 1.2   # extent ratio above this = the object/box has a long axis


def yaw_about_m(mesh, center, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    R = np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0],
                  [0, 0, 0, 1]])
    T1 = np.eye(4); T1[:3, 3] = -np.asarray(center)
    T2 = np.eye(4); T2[:3, 3] = np.asarray(center)
    m = mesh.copy()
    m.apply_transform(T2 @ R @ T1)
    return m


def long_axis(ext_x, ext_z):
    if ext_x > ext_z * ELONG:
        return "x"
    if ext_z > ext_x * ELONG:
        return "z"
    return None


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()

    cdir, by_item, wx, wz, fy, cy, r2r = load_placed(args.scene)
    fp = json.loads((cdir / "fitted_preview.json").read_text(
        encoding="utf-8"))
    fc = json.loads((cdir / "fit_check.json").read_text(encoding="utf-8"))
    place = {p["id"]: p for p in fp["placed"]}

    flagged = sorted({it["id"] for it in fc["items"] if it["bounds"]}
                     | {i for p in fc["clips"] for i in (p["a"], p["b"])})

    rows = []
    for oid in flagged:
        pl = place[oid]
        mesh0 = (by_item[oid] if not isinstance(by_item[oid], list)
                 else by_item[oid])
        blo = np.asarray(pl["fit_box"]["aabb_min"], np.float32) * r2r
        bhi = np.asarray(pl["fit_box"]["aabb_max"], np.float32) * r2r
        blo, bhi = np.minimum(blo, bhi), np.maximum(blo, bhi)
        bctr = (blo + bhi) / 2
        bext = bhi - blo
        box_long = long_axis(bext[0], bext[2])

        mlo, mhi = mesh0.bounds
        mext = mhi - mlo
        mesh_long = long_axis(mext[0], mext[2])

        fd = pl.get("front_dir_raw")
        fdir = ((fd[0] * float(r2r[0]), fd[1] * float(r2r[2]))
                if fd else None)

        cands = []
        for deg in (0, 90, 180, 270):
            m = yaw_about_m(mesh0, (mlo + mhi) / 2, deg)
            lo, hi = m.bounds
            ext = hi - lo
            # re-seat in the box: center xz, mount rule on y
            t = np.zeros(3)
            t[0] = bctr[0] - (lo[0] + hi[0]) / 2
            t[2] = bctr[2] - (lo[2] + hi[2]) / 2
            if pl["mount"] == "ceiling":
                t[1] = bhi[1] - hi[1]
            elif pl["mount"] == "wall":
                t[1] = bctr[1] - (lo[1] + hi[1]) / 2
            else:
                t[1] = blo[1] - lo[1]
            m.apply_translation(t)
            if pl["mount"] == "wall" and fdir is not None:
                lo2, hi2 = m.bounds
                d = np.zeros(3)
                if abs(fdir[0]) >= abs(fdir[1]):
                    d[0] = ((wx[0] - lo2[0]) if fdir[0] > 0
                            else (wx[1] - hi2[0]))
                else:
                    d[2] = ((wz[0] - lo2[2]) if fdir[1] > 0
                            else (wz[1] - hi2[2]))
                m.apply_translation(d)
            over = [max(0.0, float(ext[i] - bext[i])) * 1000
                    for i in (0, 2)]
            bf = bounds_findings(m.vertices, wx, wz, fy, cy)
            oob = sum(f["depth_mm"] for f in bf)
            # long-axis alignment after this yaw
            ml = mesh_long if deg in (0, 180) else (
                {"x": "z", "z": "x"}.get(mesh_long) if mesh_long
                else None)
            aligned = (box_long is None or ml is None
                       or ml == box_long)
            cands.append({"deg": deg, "overhang_mm":
                          [round(o, 0) for o in over],
                          "oob_mm": round(oob, 1),
                          "long_axis_aligned": bool(aligned)})
        # pick: aligned first, then least (total overhang + oob)
        cands.sort(key=lambda c: (not c["long_axis_aligned"],
                                  sum(c["overhang_mm"]) + c["oob_mm"]))
        best = cands[0]
        cur = next(c for c in cands if c["deg"] == 0)
        fits = (sum(best["overhang_mm"]) <= TOL * 1000 * 2
                and best["oob_mm"] <= TOL * 1000)
        verdict = ("FITS" if fits else
                   "IMPROVED" if (sum(best["overhang_mm"])
                                  + best["oob_mm"])
                   < 0.95 * (sum(cur["overhang_mm"]) + cur["oob_mm"])
                   else "NO_CARDINAL_FIT")
        rows.append({"id": oid, "name": pl["name"],
                     "mount": pl["mount"],
                     "mesh_long": mesh_long, "box_long": box_long,
                     "as_placed": cur, "best": best,
                     "all": cands, "verdict": verdict})
        print(f"  {oid:14s} {str(pl['name']):22s} "
              f"long m:{str(mesh_long):4s} b:{str(box_long):4s} | "
              f"0deg over {sum(cur['overhang_mm']):5.0f}mm "
              f"oob {cur['oob_mm']:4.0f}mm | best {best['deg']:3d}deg "
              f"over {sum(best['overhang_mm']):5.0f}mm "
              f"oob {best['oob_mm']:4.0f}mm  {verdict}")

    out = {"scene": args.scene, "built": str(date.today()),
           "generated_by": "experiments/fit_cardinal_test.py",
           "note": "cardinal-only rotation feasibility, box-fit + "
                   "bounds objective (NO clip term, user 08-04); "
                   "report only",
           "elapsed_s": round(time.time() - t0, 1),
           "items": rows}
    (cdir / "fit_cardinal_test.json").write_text(
        json.dumps(out, indent=1), encoding="utf-8")
    n = {}
    for r in rows:
        n[r["verdict"]] = n.get(r["verdict"], 0) + 1
    print(f"[cardinal] {len(rows)} items: {n} "
          f"({time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
