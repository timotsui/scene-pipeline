"""GRAVITY — the closing settle pass (R-S2-168, user 2026-08-13:
"at last we need to put the objects through gravity so everything
rests on something ... just a simple make sure everything is snapped
and supported").

CONTRACT:
  gets     the placed meshes (fitted_preview.glb + .json), the
           supported_by chains, the frame floor
  decides  each floor-tier item's final HEIGHT: the mesh settles until
           it RESTS on its supporter's real mesh surface (or the
           floor) — down when floating, up when embedded
  mistake  a pillow hovering over the bed; a lamp half-sunk into its
           nightstand; a wall picture yanked to the floor (wall/
           ceiling mounts are EXEMPT — gravity does not apply)

MECHANISM: 2 cm height-map columns from surface samples. Per item,
dy = min over overlapping footprint columns of (item bottom −
supporter top), translated away. Items settle in SUPPORT-DEPTH order
(floor-supported hosts first, riders after, so riders land on settled
hosts — computed lazily so a settled host's NEW surface is what its
rider sees). No supporter surface under the footprint → the floor,
flagged. Receipts in compose/fit_gravity.json; the GLB is updated in
place (the viewer serves it live).

Frames: math in RENDER (y up, raw * r2r); GLB nodes are RAW; the
applied translation converts back per component (r2r self-inverse).

Run:  python compose/fit_gravity.py --scene <sc> [--dry-run]
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

PITCH = 0.02      # m — the same lattice pitch the fit loop measures on
N_SAMP = 20000    # surface samples per mesh for the height maps
SETTLED_TOL = 0.005   # m — closer than this = already resting


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()
    cdir = paths.compose_dir(a.scene)
    fr = paths.frame_block(a.scene)
    r2r = np.asarray(fr["raw_to_render"], dtype=np.float64)
    floor_render = float(fr["floor_y"]) * r2r[1]

    fp = json.loads((cdir / "fitted_preview.json").read_text("utf-8"))
    items = {i["id"]: i for i in (fp.get("placed") or [])}
    sb = json.loads((cdir / "supported_by.json").read_text("utf-8"))
    top = {}
    for o in sb["objects"]:
        t = (o.get("supported_by") or [{}])[0]
        if t.get("supporter"):
            top[o["id"]] = t["supporter"]

    scene = trimesh.load(cdir / "fitted_preview.glb")
    nodes_of = {}
    for nn in scene.graph.nodes_geometry:
        iid = str(nn).rsplit("_t", 1)[0]
        nodes_of.setdefault(iid, []).append(nn)

    def item_mesh(iid):
        ms = []
        for nn in nodes_of.get(iid, []):
            T, g = scene.graph[nn]
            m = scene.geometry[g].copy()
            m.apply_transform(T)
            ms.append(m)
        return trimesh.util.concatenate(ms) if ms else None

    def depth(iid, d=0):
        s = top.get(iid)
        if s is None or str(s).startswith("arch_") or d > 4:
            return d
        return depth(s, d + 1)

    def col_map(mesh, keep_max):
        pts, _ = trimesh.sample.sample_surface(mesh, N_SAMP)
        pr = pts * r2r
        cols = np.floor(pr[:, [0, 2]] / PITCH).astype(np.int64)
        keys = cols[:, 0] * 1_000_000 + cols[:, 1]
        m = {}
        for k, y in zip(keys, pr[:, 1]):
            cur = m.get(k)
            if cur is None or (y > cur if keep_max else y < cur):
                m[k] = float(y)
        return m

    order = sorted(items, key=lambda i: (depth(i), i))
    rec = []
    n_moved = 0
    for iid in order:
        it = items[iid]
        if it.get("mount") != "floor":
            rec.append({"id": iid, "name": it.get("name"),
                        "verdict": "exempt", "mount": it.get("mount")})
            continue
        mesh = item_mesh(iid)
        if mesh is None:
            continue
        bm = col_map(mesh, keep_max=False)
        sup = top.get(iid, "arch_floor")
        dy, sup_used, n_cols = None, None, 0
        if not str(sup).startswith("arch_") and sup in nodes_of:
            sm = col_map(item_mesh(sup), keep_max=True)
            gaps = [bm[k] - sm[k] for k in bm if k in sm]
            if gaps:
                dy = min(gaps)
                sup_used = sup
                n_cols = len(gaps)
        if dy is None:
            dy = min(bm.values()) - floor_render
            sup_used = "arch_floor"
            n_cols = len(bm)
            if not str(sup).startswith("arch_"):
                sup_used = "arch_floor (supporter had no surface "
                sup_used += f"under the footprint: {sup})"
        row = {"id": iid, "name": it.get("name"),
               "supporter": sup_used, "contact_columns": n_cols,
               "dy_m": round(float(dy), 4)}
        if abs(dy) < SETTLED_TOL:
            row["verdict"] = "already resting"
        elif a.dry_run:
            row["verdict"] = "WOULD settle"
        else:
            move_raw = np.array([0.0, -dy, 0.0]) * r2r
            for nn in nodes_of[iid]:
                T, g = scene.graph[nn]
                T2 = np.asarray(T, dtype=np.float64).copy()
                T2[:3, 3] += move_raw
                scene.graph.update(frame_to=nn, matrix=T2, geometry=g)
            row["verdict"] = ("settled DOWN" if dy > 0
                              else "lifted to rest")
            n_moved += 1
            print(f"[gravity] {iid} ({it.get('name')}): "
                  f"{row['verdict']} {abs(dy):.3f} m onto {sup_used} "
                  f"({n_cols} contact columns)", flush=True)
        rec.append(row)

    if not a.dry_run and n_moved:
        (cdir / "fitted_preview.glb").write_bytes(
            scene.export(file_type="glb"))
    (cdir / "fit_gravity.json").write_text(json.dumps({
        "scene": a.scene, "built": str(date.today()),
        "generated_by": "compose/fit_gravity.py (R-S2-168)",
        "dry_run": bool(a.dry_run),
        "n_items": len(rec), "n_moved": n_moved,
        "items": rec}, indent=1), encoding="utf-8")
    print(f"[gravity] {n_moved} item(s) settled of {len(rec)} "
          f"examined -> fit_gravity.json"
          + (" (DRY RUN, nothing written to the GLB)"
             if a.dry_run else ""), flush=True)


if __name__ == "__main__":
    main()
