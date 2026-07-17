"""Deterministic mesh-collision check on a composed state — solid voxel
occupancy overlap (same method family as entangled_gen/collider_register.py;
no new deps — python-fcl is an install risk on this pinned env).

Per instance the RENDER-frame mesh is built exactly as place2 places it
(perm, uniform fit scale, mount, yaw), voxelized at PITCH and filled solid
(surface-sample fallback when fill fails on junk geometry) — solid fill is
what catches full containment, where surfaces never cross. Voxels snap to a
GLOBAL grid so any two instances' sets are comparable; sets are cached
in-process on the placement signature, so a nudge only re-voxelizes the
moved instance.

Pair score: shared voxels / the smaller instance's voxel count, plus the
shared volume in liters. Genuine surface CONTACT (book on shelf, bed against
wall) shares a thin sheet and stays under RATIO_MAX; real interpenetration
blows past it. Same-group pairs (tiled siblings) share a boundary plane by
construction and are always excluded.

CLI diagnostic: python collide.py --scene <sc>  — prints the collision table
of the scene's current composed_state2.json.
"""
import argparse
import json

import numpy as np
import trimesh

import place2
from comp_paths import paths

PITCH = 0.03        # m, voxel edge
RATIO_MAX = 0.05    # shared / smaller-instance voxels: above = collision
SURF_SAMPLES = 20000

_CACHE = {}


def _iid(e):
    return f'{e["group"]}.{e["part"]}'


def _sig(e):
    return json.dumps([e["uid"], e["perm"], e.get("yaw", 0.0), e["center"],
                       e["size"], e["mount"]])


def voxels_of(e, fr):
    """-> (set of global-grid int coords, lo, hi) for one placed instance."""
    sig = _sig(e)
    if sig not in _CACHE:
        r2r = fr.get("raw_to_render", [1.0, 1.0, 1.0])
        mesh = place2.placed_mesh(e["uid"], e["perm"], e["size"], e["center"],
                                  e["mount"], fr["floor_y"], r2r,
                                  yaw_deg=e.get("yaw", 0.0))
        try:
            pts = mesh.voxelized(PITCH).fill().points
        except Exception:
            pts, _ = trimesh.sample.sample_surface(mesh, SURF_SAMPLES)
        g = np.floor(np.asarray(pts) / PITCH).astype(np.int64)
        _CACHE[sig] = (set(map(tuple, g)), g.min(0), g.max(0))
    return _CACHE[sig]


def report(state, fr, only=None, boxes=False):
    """Pairwise collisions, worst first: [{a, b, ratio, liters, voxels}].
    only = iid or set of iids — restrict to pairs touching those instances
    (what the loop needs after a single edit). boxes=True adds the
    RENDER-frame AABB of the shared voxels (overlap_lo/overlap_hi, meters)
    — what the viewer's collision layer draws."""
    if isinstance(only, str):
        only = {only}
    ent = state["objects"]
    out = []
    for i in range(len(ent)):
        for j in range(i + 1, len(ent)):
            a, b = ent[i], ent[j]
            if a["group"] == b["group"]:
                continue
            ia, ib = _iid(a), _iid(b)
            if only and not (ia in only or ib in only):
                continue
            va, la, ha = voxels_of(a, fr)
            vb, lb, hb = voxels_of(b, fr)
            if (la > hb + 1).any() or (lb > ha + 1).any():   # broad phase
                continue
            shared = va & vb
            if not shared:
                continue
            ratio = len(shared) / max(1, min(len(va), len(vb)))
            row = {"a": ia, "b": ib, "ratio": round(ratio, 4),
                   "liters": round(len(shared) * PITCH ** 3 * 1000, 2),
                   "voxels": len(shared)}
            if boxes:
                g = np.asarray(sorted(shared), np.int64)
                row["overlap_lo"] = [round(float(v), 3)
                                     for v in g.min(0) * PITCH]
                row["overlap_hi"] = [round(float(v), 3)
                                     for v in (g.max(0) + 1) * PITCH]
            out.append(row)
    return sorted(out, key=lambda r: -r["ratio"])


def worst(state, fr, only=None):
    """Worst pair touching `only` (or overall), or None if collision-free."""
    rows = report(state, fr, only=only)
    return rows[0] if rows else None


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--state", default="composed_state2.json")
    ap.add_argument("--export", action="store_true",
                    help="also write package/collisions.json (pairs + "
                         "overlap boxes) for the 3D viewer's collision layer")
    args = ap.parse_args()
    man = json.loads(paths.manifest(args.scene).read_text())
    state = json.loads(
        (paths.package_dir(args.scene) / args.state).read_text())
    rows = report(state, man["frame"], boxes=args.export)
    labels = {_iid(e): e["label"] for e in state["objects"]}
    if not rows:
        print("[collide] no colliding pairs")
    for r in rows:
        flag = " COLLISION" if r["ratio"] > RATIO_MAX else ""
        print(f'[collide] {r["a"]} ({labels[r["a"]]}) x {r["b"]} '
              f'({labels[r["b"]]}): ratio {r["ratio"]:.3f}, '
              f'{r["liters"]} L, {r["voxels"]} vox{flag}')
    if args.export:
        data = {"state": args.state, "pitch": PITCH, "ratio_max": RATIO_MAX,
                "frame": "render",
                "pairs": [{**r, "label_a": labels[r["a"]],
                           "label_b": labels[r["b"]]} for r in rows]}
        outf = paths.package_dir(args.scene) / "collisions.json"
        outf.write_text(json.dumps(data, indent=1))
        print(f"[collide] wrote {outf}")
