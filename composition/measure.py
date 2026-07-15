"""Measure TRUE mesh extents + canonical-yaw fix for shortlisted assets.

The thor_metadata bbox lies for a fat minority of assets (open window
shutters: annotation z=14cm, mesh z=54cm — found 2026-07-14 when placements
blew out of their boxes). And a lot of meshes are authored ROTATED in their
own frame (user-confirmed 2026-07-15: many sit 45 deg off-axis), which
inflates the horizontal AABB up to x sqrt(2) per axis — poisoning fit, scale
AND placement. This walks a scene's shortlists2 uids, loads each pkl mesh
once, finds the yaw about y that minimizes the footprint's bounding-rectangle
area (exact: min-area rectangle of the convex hull), and records BOTH the fix
and the post-fix y-up extents (cm) in dataset-level caches. assets_thor.
load_asset applies the yaw fix on load, so every consumer (thumbs, place2,
viewers) sees the squared mesh; retrieve.catalog() overrides size_yup_cm from
the size cache.

Run: python measure.py --scene <sc>   (only cache misses are loaded)
Chain note: run BEFORE retrieve2 for full effect; newly-shortlisted uids are
unmeasured until the next pass (annotation is the recall filter, the cache
the precision upgrade).
"""
import json

import numpy as np
import trimesh

from assets_thor import load_asset
from comp_paths import MESH_YAW
from comp_paths import paths
from thumbs import THUMBS

SIZES = THUMBS / "_mesh_sizes.json"
ROBUST = THUMBS / "_mesh_robust.json"
YAW_MIN_SHRINK = 0.92   # accept a fix only if footprint area shrinks >=8%
                        # (round meshes have no defined yaw — leave them be)
ROBUST_FRAC = 0.995     # robust extents contain this fraction of surface area
ROBUST_FLAG = 0.90      # any-axis robust/full ratio below this = outlier
                        # geometry is inflating the asset's box (census flag)


def load_cache():
    return json.loads(SIZES.read_text()) if SIZES.exists() else {}


def load_yaws():
    return json.loads(MESH_YAW.read_text()) if MESH_YAW.exists() else {}


def _xz_area(pts, ang):
    """Footprint AABB area after rotating (x,z) points as rotation_matrix(
    ang, [0,1,0]) would: x' = x c + z s, z' = -x s + z c."""
    c, s = np.cos(ang), np.sin(ang)
    x = pts[:, 0] * c + pts[:, 1] * s
    z = -pts[:, 0] * s + pts[:, 1] * c
    return float(np.ptp(x) * np.ptp(z))


def footprint_yaw(mesh):
    """Yaw about +y (degrees, in [-45, 45)) squaring the mesh's footprint to
    its own axes, or 0.0 if no candidate shrinks the area enough. The optimal
    rectangle from trimesh.bounds.oriented_bounds_2D gives the angle up to
    sign/90-deg ambiguity; candidates are resolved numerically."""
    pts = mesh.vertices[:, [0, 2]]
    try:
        to_origin, _ = trimesh.bounds.oriented_bounds_2D(pts)
    except Exception:
        return 0.0
    b = float(np.arctan2(to_origin[1, 0], to_origin[0, 0]))
    cands = {np.deg2rad((np.rad2deg(a) + 45.0) % 90.0 - 45.0)
             for a in (b, -b)}
    best = min(cands, key=lambda a: _xz_area(pts, a))
    if _xz_area(pts, best) >= YAW_MIN_SHRINK * _xz_area(pts, 0.0):
        return 0.0
    return round(np.rad2deg(best), 2)


def load_robust():
    return json.loads(ROBUST.read_text()) if ROBUST.exists() else {}


def robust_extents(mesh, n=50000, bins=128, alpha=0.10):
    """Per-axis bounds at the surface-area DENSITY edge: scan a fine area
    histogram in from each end and cut where density first reaches alpha x
    the uniform average. Junk sticking out (spikes, stray triangles, thin
    panels) has near-zero area per cm so the bound snaps to the body's edge
    regardless of the junk's TOTAL area — a fixed percentile cut fails when
    the junk carries more area than the trimmed fraction (found on the
    obj_013 triangle-shelf, 2026-07-15). Legit thin parts (lamp arms, legs)
    carry far more area per cm than alpha x average and survive. Samples are
    area-weighted, not vertices (vertex percentiles are tessellation-biased);
    nothing is ever deleted from the mesh."""
    try:
        pts, _ = trimesh.sample.sample_surface(mesh, n, seed=0)
    except TypeError:                          # older trimesh: no seed kwarg
        pts, _ = trimesh.sample.sample_surface(mesh, n)
    lo_f, hi_f = pts.min(0), pts.max(0)
    lo, hi = lo_f.copy(), hi_f.copy()
    for ax in range(3):
        if hi_f[ax] - lo_f[ax] < 1e-9:
            continue
        h, edges = np.histogram(pts[:, ax], bins=bins,
                                range=(lo_f[ax], hi_f[ax]))
        keep = np.flatnonzero(h >= alpha * n / bins)
        if keep.size:
            lo[ax], hi[ax] = edges[keep[0]], edges[keep[-1] + 1]
    return lo, hi


def census(uids):
    """Detector pass, NO behavior change: robust vs full extents per uid (in
    the yaw-fixed frame load_asset serves), cached for the asset viewer."""
    out = load_robust()
    todo = [u for u in dict.fromkeys(uids) if u not in out]
    fail = 0
    for i, uid in enumerate(todo):
        try:
            m = load_asset(uid)
            lo_f, hi_f = m.bounds
            lo, hi = robust_extents(m)
            ratio = (hi - lo) / np.maximum(hi_f - lo_f, 1e-9)
            out[uid] = {"lo": [round(float(v), 4) for v in lo],
                        "hi": [round(float(v), 4) for v in hi],
                        "ratio": [round(float(v), 3) for v in ratio]}
        except Exception as e:
            fail += 1
            print(f"[census] FAIL {uid}: {e}", flush=True)
        if (i + 1) % 50 == 0:
            print(f"[census] {i + 1}/{len(todo)}", flush=True)
    if todo:
        ROBUST.write_text(json.dumps(out))
    flagged = {u: r for u, r in out.items()
               if u in dict.fromkeys(uids) and min(r["ratio"]) < ROBUST_FLAG}
    print(f"[census] {len(todo) - fail} new ({fail} failed); "
          f"{len(flagged)}/{len([u for u in dict.fromkeys(uids) if u in out])} "
          f"flagged (any-axis ratio < {ROBUST_FLAG})", flush=True)
    for u, r in sorted(flagged.items(), key=lambda kv: min(kv[1]["ratio"])):
        print(f"  {u}  ratio x{r['ratio'][0]:.2f} y{r['ratio'][1]:.2f} "
              f"z{r['ratio'][2]:.2f}", flush=True)
    return out


def ensure(uids):
    THUMBS.mkdir(exist_ok=True)
    sizes, yaws = load_cache(), load_yaws()
    todo = [u for u in dict.fromkeys(uids) if u not in yaws]
    fail = fixed = 0
    for i, uid in enumerate(todo):
        try:
            m = load_asset(uid, raw=True)
            yaw = footprint_yaw(m)
            if yaw:
                m.apply_transform(trimesh.transformations.rotation_matrix(
                    np.deg2rad(yaw), [0, 1, 0]))
                fixed += 1
            yaws[uid] = yaw
            lo, hi = m.bounds
            sizes[uid] = [round(float(v) * 100, 1) for v in (hi - lo)]
        except Exception as e:
            fail += 1
            print(f"[measure] FAIL {uid}: {e}", flush=True)
        if (i + 1) % 50 == 0:
            print(f"[measure] {i + 1}/{len(todo)}", flush=True)
    if todo:
        SIZES.write_text(json.dumps(sizes))
        MESH_YAW.write_text(json.dumps(yaws))
    print(f"[measure] measured {len(todo) - fail} ({fixed} yaw-fixed), "
          f"failed {fail}, total cached {len(yaws)}", flush=True)
    return sizes


def scene_uids(sc):
    pkg = paths.package_dir(sc)
    sl = json.loads((pkg / "shortlists2.json").read_text())
    return [c["uid"] for b in sl["boxes"] for c in b["candidates"]]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--census", action="store_true",
                    help="robust-extents detector pass (no behavior change)")
    args = ap.parse_args()
    if args.census:
        census(scene_uids(args.scene))
    else:
        ensure(scene_uids(args.scene))
