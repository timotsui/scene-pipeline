"""
FIT CHECK v1 (2026-08-04, user ruling: "we just want to make it so that
things are not clipping into each other, and then we are within the
wall bounds"): deterministic physical report over the placed preview
meshes. REPORT ONLY -- no judge calls, no fixes; the fit loop consumes
the findings as verdicts later.

  1. BOUNDS: every placed mesh inside the measured shell (4 wall
     planes + floor + ceiling). Vertex-exact, depths in mm.
  2. CLIP: pairwise interpenetration. AABB prune, then occupied-cell
     overlap on a common 2 cm world lattice (surface voxels + fill
     where the mesh closes; surface-only fallback for junk geometry --
     robust to non-watertight assets). Touching passes; only real
     overlap reports. Lattice resolution bounds what "touch" means
     here: overlaps under ~2 cm read as contact, not clip.

Output: out/<scene>/compose/fit_check.json + console summary.
Run:  python compose/fit_check.py --scene bedroom_marble
"""
import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

TOL = 0.005      # m -- bounds: deeper than this = finding
PITCH = 0.02     # m -- clip lattice cell
CONTACT_CELLS = 4   # overlap cells at/below this = contact, not clip


def load_placed(scene):
    """fitted_preview.glb -> {item id: one concatenated render-frame
    mesh} (tiles merged; same to_render convention as rotation_check)."""
    cdir = paths.compose_dir(scene)
    man = {"frame": paths.frame_block(scene)}
    graph = json.loads((paths.scene_dir(scene) / "scene_graph.json")
                       .read_text(encoding="utf-8"))
    r2r = np.array(man["frame"].get("raw_to_render", [1, 1, 1]), np.float32)
    to_render = np.diag([r2r[0], r2r[1], r2r[2], 1.0])

    planes = {n["id"]: n["geometry"]["plane"]["value_raw"]
              for n in graph["nodes"] if n["id"].startswith("arch_")}
    wx = sorted((planes["arch_wall_x_low"] * r2r[0],
                 planes["arch_wall_x_high"] * r2r[0]))
    wz = sorted((planes["arch_wall_z_low"] * r2r[2],
                 planes["arch_wall_z_high"] * r2r[2]))
    fy, cy = sorted((planes["arch_floor"] * r2r[1],
                     planes["arch_ceiling"] * r2r[1]))

    sc = trimesh.load(cdir / "fitted_preview.glb", force="scene")
    parts = {}
    for gname, geom in sc.geometry.items():
        m = geom.copy()
        m.apply_transform(to_render)
        parts.setdefault(gname.rsplit("_t", 1)[0], []).append(m)
    by_item = {k: (v[0] if len(v) == 1 else trimesh.util.concatenate(v))
               for k, v in parts.items()}
    return cdir, by_item, wx, wz, fy, cy, r2r


def bounds_findings(verts, wx, wz, fy, cy):
    """Depth (m) past each shell plane; only depths > TOL return."""
    probes = {
        "wall_x_low":  wx[0] - verts[:, 0].min(),
        "wall_x_high": verts[:, 0].max() - wx[1],
        "wall_z_low":  wz[0] - verts[:, 2].min(),
        "wall_z_high": verts[:, 2].max() - wz[1],
        "floor":       fy - verts[:, 1].min(),
        "ceiling":     verts[:, 1].max() - cy,
    }
    return [{"plane": k, "depth_mm": round(float(d) * 1000, 1)}
            for k, d in probes.items() if d > TOL]


def cell_keys(mesh):
    """Occupied cells of a mesh on the common world lattice, as int64
    keys. fill() when the voxel shell closes; surface cells otherwise."""
    vg = mesh.voxelized(pitch=PITCH)
    try:
        vg = vg.fill()
    except Exception:
        pass
    idx = np.floor(vg.points / PITCH).astype(np.int64) + (1 << 20)
    return np.unique(idx[:, 0] * (1 << 42) + idx[:, 1] * (1 << 21)
                     + idx[:, 2])


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()

    cdir, by_item, wx, wz, fy, cy, r2r = load_placed(args.scene)
    fp = json.loads((cdir / "fitted_preview.json").read_text(
        encoding="utf-8"))
    names = {p["id"]: p["name"] for p in fp["placed"]}

    items, cells, aabbs = [], {}, {}
    for oid, m in sorted(by_item.items()):
        bf = bounds_findings(m.vertices, wx, wz, fy, cy)
        items.append({"id": oid, "name": names.get(oid),
                      "bounds": bf})
        aabbs[oid] = m.bounds
    n_bounds = sum(1 for it in items if it["bounds"])

    # pairwise clip: AABB prune -> lattice overlap
    ids = sorted(by_item)
    pairs = []
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            alo, ahi = aabbs[a]
            blo, bhi = aabbs[b]
            ov = np.minimum(ahi, bhi) - np.maximum(alo, blo)
            if (ov <= 0).any():
                continue
            for oid in (a, b):
                if oid not in cells:
                    cells[oid] = cell_keys(by_item[oid])
            inter = np.intersect1d(cells[a], cells[b],
                                   assume_unique=True)
            if len(inter) <= CONTACT_CELLS:
                continue
            # AABB-intersection region in the RAW frame (viewer draws
            # raw; render->raw = the same sign flips, then re-sort)
            olo = np.maximum(alo, blo) * r2r
            ohi = np.minimum(ahi, bhi) * r2r
            olo, ohi = np.minimum(olo, ohi), np.maximum(olo, ohi)
            pairs.append({
                "a": a, "a_name": names.get(a),
                "b": b, "b_name": names.get(b),
                "overlap_cells": int(len(inter)),
                "overlap_l": round(float(len(inter)) * PITCH ** 3 * 1000,
                                   2),
                "aabb_overlap_m": [round(float(v), 3) for v in ov],
                "overlap_box_raw": {
                    "mn": [round(float(v), 3) for v in olo],
                    "mx": [round(float(v), 3) for v in ohi]},
            })
    pairs.sort(key=lambda p: -p["overlap_cells"])

    out = {"scene": args.scene, "built": str(date.today()),
           "generated_by": "compose/fit_check.py",
           "graph_fingerprint": paths.graph_fingerprint(args.scene),
           "note": "v1 report only: bounds (vertex-exact vs shell "
                   "planes, TOL 5 mm) + pairwise clip (2 cm lattice, "
                   "<=4 shared cells = contact). No fixes applied.",
           "params": {"tol_m": TOL, "pitch_m": PITCH,
                      "contact_cells": CONTACT_CELLS},
           "elapsed_s": round(time.time() - t0, 1),
           "items": items, "clips": pairs}
    out_p = cdir / "fit_check.json"
    out_p.write_text(json.dumps(out, indent=1), encoding="utf-8")

    print(f"[fit_check] {len(items)} items: {n_bounds} out of bounds, "
          f"{len(pairs)} clipping pairs ({time.time() - t0:.0f}s) "
          f"-> {out_p}")
    for it in items:
        if it["bounds"]:
            worst = max(it["bounds"], key=lambda f: f["depth_mm"])
            print(f"  OOB  {it['id']:14s} {str(it['name']):24s} "
                  f"{worst['plane']} {worst['depth_mm']:.0f}mm")
    for p in pairs[:20]:
        print(f"  CLIP {p['a']:14s} {str(p['a_name']):20s} x "
              f"{p['b']:14s} {str(p['b_name']):20s} "
              f"{p['overlap_l']:.1f} L")


if __name__ == "__main__":
    main()
