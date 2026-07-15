"""Amodal box extension — METHOD COMPARISON (extraction-stage experiment).

Lifted boxes are truncated where objects are occluded in the 4 views (bed
hides the shelf's legs). The occluded geometry exists in the Marble world, so
three candidate fixes are computed side by side for every non-wall box, all
v1 downward-only (the shelf-legs case):

  splat     column occupancy from gen_raw.ply points: walk 10 cm elevation
            slabs below the box bottom inside the (shrunk) footprint; extend
            while slab density holds up vs the box's own median slab density.
  collider  same column walk on points sampled from the Marble bundle
            collider mesh, placed in the raw frame by collider_register.py
            (run it first; skipped if the scene is unregistered).
            EXPECTED TO ADD NOTHING, and that is the finding: once correctly
            registered (2026-07-15) the collider holds strictly LESS geometry
            under every occluded box than the splat already does — it is a
            mesh derived FROM the splat, so it cannot carry what the splat
            lacks. Kept as a measured negative result, not a live candidate.
  prior     unconditional floor-snap for floor-contact labels — the naive
            baseline the occupancy methods must beat.

Writes out/<scene>/amodal_boxes.json (raw box + per-method box + changed
flag); the viewer's per-method toggles draw the changed ones against the raw
manifest layer. No manifest is modified — comparison only.

Run: python amodal_boxes.py --scene bedroom_marble
"""
import argparse
import json

import numpy as np

import collider_register
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


def load_collider_pts(sc):
    """Collider mesh -> raw-frame sample points via collider_register.py.

    The registration is NOT searched here (it was, until 2026-07-15: best-of-8
    sign flips scored on bbox IoU, which could never register frames whose
    origins are 1.23 m apart — it settled on IoU 0.37 and the resulting
    "collider" boxes in every amodal_boxes.json written before that date are
    garbage). Run `python collider_register.py --scene <sc>` first.
    """
    glb = collider_register.collider_path(sc)
    T = collider_register.load_T(sc)
    if glb is None:
        return None, None
    if T is None:
        print("[amodal] collider present but UNREGISTERED — run "
              "collider_register.py --scene " + sc + " (skipping)", flush=True)
        return None, None
    import trimesh
    mesh = trimesh.load(glb, force="mesh")
    mesh.apply_transform(T)
    reg = json.loads((paths.scene_dir(sc)
                      / "collider_registration.json").read_text())
    print(f"[amodal] collider {glb.name}: registered "
          f"(voxel IoU {reg['metrics']['voxel_iou']:.3f}, splat->surface p50 "
          f"{reg['metrics']['dist_p50']*100:.1f}cm)", flush=True)
    return np.asarray(mesh.sample(300_000), np.float64), reg


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
    cpts, reg = load_collider_pts(sc)
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
           "collider_registration": (reg and {k: reg[k] for k in
                                              ("method", "scale", "metrics")}),
           "methods": methods}
    outf = paths.scene_dir(sc) / "amodal_boxes.json"
    outf.write_text(json.dumps(out, indent=1))
    n = {m: sum(1 for b in v if b["changed"]) for m, v in methods.items()}
    print(f"\n[amodal] changed boxes per method: {n}", flush=True)
    print(f"[amodal] wrote {outf}", flush=True)


if __name__ == "__main__":
    main()
