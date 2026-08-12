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
from arch_walls import wall_axis_planes  # noqa: E402

TOL = 0.005      # m -- bounds: deeper than this = finding
PITCH = 0.02     # m -- clip lattice cell
CONTACT_CELLS = 4   # overlap cells at/below this = contact, not clip

#: THE ALLOWED CLIPPING MARGIN (user ruling 2026-08-11C, R-S2-117):
#: "i dont want to fix the asset library. so lets just have good margins
#: for clipping. i think visually as long as its not obvious it will be
#: ok." Overlaps at/below this VOLUME are acceptable touches - reported
#: under `contacts` (recorded, never hidden), not worked by the declip
#: solver, and not counted as clips. Above it = a clip.
#: 0.5 L is the STARTING value; the calibration is the user's EYE, so it
#: moves on their say-so after looking, not on any measurement here.
#: (Asset junk slivers - broken mesh pieces the user declined to fix at
#: the library - are the designed beneficiary.)
ALLOW_L = 0.5
ALLOW_CELLS = int(ALLOW_L / (PITCH ** 3 * 1000))   # 62 cells at 2 cm


def load_placed(scene):
    """fitted_preview.glb -> {item id: one concatenated render-frame
    mesh} (tiles merged; same to_render convention as rotation_check)."""
    cdir = paths.compose_dir(scene)
    man = {"frame": paths.frame_block(scene)}
    graph = json.loads((paths.scene_dir(scene) / "scene_graph.json")
                       .read_text(encoding="utf-8"))
    r2r = np.array(man["frame"].get("raw_to_render", [1, 1, 1]), np.float32)
    to_render = np.diag([r2r[0], r2r[1], r2r[2], 1.0])

    xs_raw, zs_raw, floor_raw, ceil_raw = wall_axis_planes(graph["nodes"])
    wx = sorted((xs_raw[0] * r2r[0], xs_raw[-1] * r2r[0]))
    wz = sorted((zs_raw[0] * r2r[2], zs_raw[-1] * r2r[2]))
    fy, cy = sorted((floor_raw * r2r[1], ceil_raw * r2r[1]))

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

    mounts = {p["id"]: p.get("mount") for p in fp["placed"]}
    items, cells, aabbs = [], {}, {}
    for oid, m in sorted(by_item.items()):
        bf = bounds_findings(m.vertices, wx, wz, fy, cy)
        # WALL-MOUNTED ITEMS MAY SIT INSIDE THEIR WALL (user ruling
        # 2026-08-12, R-S2-122: "wall objects should be able to be
        # behind the walls, like [an] in-wall wardrobe"). Recessed and
        # built-in furniture legitimately extends past the wall plane,
        # so wall-plane depth is not a finding for them; floor and
        # ceiling violations still are.
        if mounts.get(oid) == "wall":
            bf = [b for b in bf if not b["plane"].startswith("wall_")]
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
                continue        # a mere touch: not even worth recording
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
    # the allowed margin (see ALLOW_L above): small overlaps are
    # acceptable touches, recorded apart so nothing is hidden
    clips = [p for p in pairs if p["overlap_cells"] > ALLOW_CELLS]
    contacts = [p for p in pairs if p["overlap_cells"] <= ALLOW_CELLS]

    out = {"scene": args.scene, "built": str(date.today()),
           "generated_by": "compose/fit_check.py",
           "graph_fingerprint": paths.graph_fingerprint(args.scene),
           "note": "v1 report only: bounds (vertex-exact vs shell "
                   "planes, TOL 5 mm) + pairwise clip (2 cm lattice, "
                   "<=4 shared cells = contact). Overlaps at/below the "
                   f"allowed margin ({ALLOW_L} L, user ruling R-S2-117) "
                   "are `contacts`; only larger ones are `clips`. No "
                   "fixes applied.",
           "params": {"tol_m": TOL, "pitch_m": PITCH,
                      "contact_cells": CONTACT_CELLS,
                      "allow_l": ALLOW_L, "allow_cells": ALLOW_CELLS},
           "elapsed_s": round(time.time() - t0, 1),
           "items": items, "clips": clips, "contacts": contacts}
    out_p = cdir / "fit_check.json"
    out_p.write_text(json.dumps(out, indent=1), encoding="utf-8")

    pairs = clips          # the print loop below reports real clips
    print(f"[fit_check] {len(items)} items: {n_bounds} out of bounds, "
          f"{len(clips)} clipping pairs + {len(contacts)} allowed "
          f"touches (margin {ALLOW_L} L) ({time.time() - t0:.0f}s) "
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
