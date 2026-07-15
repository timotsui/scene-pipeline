"""Amodal box extension — METHOD COMPARISON (extraction-stage experiment).

Lifted boxes are truncated where objects are occluded in the 4 views (bed
hides the shelf's legs). The occluded geometry exists in the Marble world, so
three candidate fixes are computed side by side for every non-wall box, all
v1 downward-only (the shelf-legs case):

  splat     column occupancy from gen_raw.ply points: walk 10 cm elevation
            slabs below the box bottom inside the (shrunk) footprint; extend
            while slab density holds up vs the box's own median slab density.
  collider  same column walk on points sampled from the Marble bundle
            collider mesh; the collider->raw sign transform is auto-picked
            over the 8 flips by bbox IoU vs the splat (printed — LOW IoU
            MEANS THE REGISTRATION GATE FAILED, distrust the boxes).
  prior     unconditional floor-snap for floor-contact labels — the naive
            baseline the occupancy methods must beat.

Writes out/<scene>/amodal_boxes.json (raw box + per-method box + changed
flag); the viewer's per-method toggles draw the changed ones against the raw
manifest layer. No manifest is modified — comparison only.

Run: python amodal_boxes.py --scene bedroom_marble
"""
import argparse
import json
from pathlib import Path

import numpy as np

import paths

r3 = paths.load_r3()

WALL_LABELS = {"window", "door", "curtain", "picture", "poster", "poter"}
FLOOR_TOKENS = {"shelf", "bed", "chair", "desk", "table", "wardrobe", "sofa",
                "rug", "planter", "bookshelf", "dresser", "cabinet", "stool"}
SLAB = 0.10          # elevation slab height (m)
SHRINK = 0.85        # footprint shrink so neighbors don't feed the column
KEEP_FRAC = 0.25     # slab keeps the column alive at this fraction of ref
SNAP_FLOOR = 0.12    # bottom closer than this to the floor snaps to 0
MIN_GAIN = 0.05      # smaller extensions count as unchanged


def column_extend(pts_xz, pts_e, lo, hi, floor_y, sy):
    """Walk slabs below the box bottom; return new bottom elevation or None."""
    e_lo = sy * (np.array([lo[1], hi[1]]) - floor_y)
    b0, b1 = float(e_lo.min()), float(e_lo.max())
    cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
    hx, hz = (hi[0] - lo[0]) / 2 * SHRINK, (hi[2] - lo[2]) / 2 * SHRINK
    fp = ((np.abs(pts_xz[:, 0] - cx) <= hx)
          & (np.abs(pts_xz[:, 1] - cz) <= hz))
    e = pts_e[fp]
    if e.size == 0:
        return None
    # reference density: median occupied-slab count inside the box itself
    nref = max(1, int(np.ceil((b1 - b0) / SLAB)))
    ref_counts = [np.count_nonzero((e >= b0 + i * SLAB) & (e < b0 + (i + 1) * SLAB))
                  for i in range(nref)]
    ref = np.median([c for c in ref_counts if c > 0] or [0])
    if ref == 0:
        return None
    bottom = b0
    while bottom > 0:
        n = np.count_nonzero((e >= bottom - SLAB) & (e < bottom))
        if n < KEEP_FRAC * ref:
            break
        bottom -= SLAB
    bottom = max(bottom, 0.0)
    if bottom <= SNAP_FLOOR:
        bottom = 0.0
    return bottom if (b0 - bottom) >= MIN_GAIN else None


def new_aabb(lo, hi, bottom_e, floor_y, sy):
    lo, hi = list(lo), list(hi)
    y = floor_y + sy * bottom_e          # elevation -> raw y
    if sy < 0:
        hi[1] = max(hi[1], y)
    else:
        lo[1] = min(lo[1], y)
    return lo, hi


def load_collider_pts(sc, splat_xyz):
    """Collider mesh -> raw-frame sample points via best-of-8 sign flip."""
    bp = paths.scene_dir(sc) / "bundle_path.txt"
    if not bp.exists():
        return None, None, 0.0
    bundle = Path(bp.read_text().strip())
    glbs = list(bundle.glob("*_collider.glb")) + list(bundle.glob("*collider*.glb"))
    if not glbs:
        return None, None, 0.0
    import trimesh
    mesh = trimesh.load(glbs[0], force="mesh")
    pts = np.asarray(mesh.sample(300_000), np.float64)
    s_lo = np.percentile(splat_xyz, 1, axis=0)
    s_hi = np.percentile(splat_xyz, 99, axis=0)
    best = None
    for sx in (1, -1):
        for sy_ in (1, -1):
            for sz in (1, -1):
                q = pts * np.array([sx, sy_, sz])
                c_lo, c_hi = np.percentile(q, 1, 0), np.percentile(q, 99, 0)
                inter = np.maximum(0, np.minimum(s_hi, c_hi)
                                   - np.maximum(s_lo, c_lo)).prod()
                union = ((s_hi - s_lo).prod() + (c_hi - c_lo).prod() - inter)
                iou = float(inter / union) if union > 0 else 0.0
                if best is None or iou > best[0]:
                    best = (iou, (sx, sy_, sz), q)
    iou, flip, q = best
    print(f"[amodal] collider {glbs[0].name}: flip {flip}, bbox IoU vs splat "
          f"{iou:.2f}" + ("  <-- REGISTRATION SUSPECT" if iou < 0.5 else ""),
          flush=True)
    return q, flip, iou


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()
    sc = args.scene
    man = json.loads(paths.manifest(sc).read_text())
    fr = man["frame"]
    floor_y, sy = fr["floor_y"], fr.get("raw_to_render", [1, 1, 1])[1]

    xyz, _, _, _ = r3.load_splat(str(paths.scene_dir(sc) / "gen_raw.ply"))
    sources = {"splat": xyz.astype(np.float64)}
    cpts, flip, iou = load_collider_pts(sc, xyz)
    if cpts is not None:
        sources["collider"] = cpts

    pre = {k: (v[:, [0, 2]], sy * (v[:, 1] - floor_y)) for k, v in sources.items()}
    methods = {k: [] for k in list(sources) + ["prior"]}
    print(f"\n{'box':22s} {'raw bottom':>10s} " +
          " ".join(f"{m:>9s}" for m in methods), flush=True)
    for o in man["objects"]:
        lo, hi = o["aabb_min"], o["aabb_max"]
        b0 = min(sy * (lo[1] - floor_y), sy * (hi[1] - floor_y))
        wall = o["label"].strip().lower() in WALL_LABELS
        floorish = bool(set(o["label"].lower().split()) & FLOOR_TOKENS)
        row = {}
        for m, (pxz, pe) in pre.items():
            nb = None if wall else column_extend(pxz, pe, lo, hi, floor_y, sy)
            if nb is not None:
                nlo, nhi = new_aabb(lo, hi, nb, floor_y, sy)
                methods[m].append({"id": o["id"], "label": o["label"],
                                   "aabb_min": nlo, "aabb_max": nhi,
                                   "changed": True,
                                   "bottom_e": round(nb, 3)})
                row[m] = nb
            else:
                methods[m].append({"id": o["id"], "label": o["label"],
                                   "aabb_min": lo, "aabb_max": hi,
                                   "changed": False})
                row[m] = None
        if not wall and floorish and b0 > MIN_GAIN:
            nlo, nhi = new_aabb(lo, hi, 0.0, floor_y, sy)
            methods["prior"].append({"id": o["id"], "label": o["label"],
                                     "aabb_min": nlo, "aabb_max": nhi,
                                     "changed": True, "bottom_e": 0.0})
            row["prior"] = 0.0
        else:
            methods["prior"].append({"id": o["id"], "label": o["label"],
                                     "aabb_min": lo, "aabb_max": hi,
                                     "changed": False})
            row["prior"] = None
        cells = " ".join("      same" if row[m] is None else f"{row[m]:9.2f}"
                         for m in methods)
        print(f"{o['id']} {o['label']:14s} {b0:10.2f} {cells}", flush=True)

    out = {"scene": sc, "floor_y": floor_y, "sy": sy,
           "collider_flip": flip, "collider_iou": round(iou, 3),
           "methods": methods}
    outf = paths.scene_dir(sc) / "amodal_boxes.json"
    outf.write_text(json.dumps(out, indent=1))
    n = {m: sum(1 for b in v if b["changed"]) for m, v in methods.items()}
    print(f"\n[amodal] changed boxes per method: {n}", flush=True)
    print(f"[amodal] wrote {outf}", flush=True)


if __name__ == "__main__":
    main()
