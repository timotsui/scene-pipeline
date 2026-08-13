"""MERGE SUB PLACEMENTS — land the sub rounds' placed meshes in the
main fitted preview (R-S2-168 wiring, first half; user 2026-08-13:
"i cant see it in the 3d?").

CONTRACT:
  gets     sub_experiment/<anchor>/cp5_final/{placements.json,
           subs_preview.glb} for every fleet-run anchor
  decides  nothing — it TRANSPORTS: each PLACED sub's mesh nodes are
           copied into fitted_preview.glb (RAW frame both sides,
           verified obj_029 2026-08-13), and a minimal record joins
           fitted_preview.json `placed` (source "sub_round") so the
           gravity pass sees and settles them like everything else
  mistake  double-merging on a re-run (guarded: a sub id already in
           the GLB is skipped, loudly)

The main GLB is backed up ONCE to fitted_preview_presubs.glb.
Run gravity AFTER this (compose/fit_gravity.py) so riders rest on
their hosts' real surfaces.

Run:  python compose/merge_sub_placements.py --scene <sc>
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    a = ap.parse_args()
    cdir = paths.compose_dir(a.scene)
    fr = paths.frame_block(a.scene)
    r2r = np.asarray(fr["raw_to_render"], dtype=np.float64)

    gpath = cdir / "fitted_preview.glb"
    jpath = cdir / "fitted_preview.json"
    bak = cdir / "fitted_preview_presubs.glb"
    if not bak.exists():
        bak.write_bytes(gpath.read_bytes())

    scene = trimesh.load(gpath)
    have = {str(n).rsplit("_t", 1)[0]
            for n in scene.graph.nodes_geometry}
    fp = json.loads(jpath.read_text("utf-8"))
    placed = fp.setdefault("placed", [])
    placed_ids = {p["id"] for p in placed}

    n_added, n_skipped = 0, 0
    for pj in sorted((cdir / "sub_experiment").glob(
            "obj_*/cp5_final/placements.json")):
        rec = json.loads(pj.read_text("utf-8"))
        sglb = pj.parent / "subs_preview.glb"
        if not sglb.exists():
            # an anchor whose subs all died (NO_BOARD etc.) writes no GLB
            continue
        sub_scene = trimesh.load(sglb)
        subs_ok = {s["id"]: s for s in rec["subs"]
                   if s.get("status") == "PLACED"}
        for nn in sub_scene.graph.nodes_geometry:
            sid = str(nn).rsplit("_t", 1)[0]
            base = sid.split("_c")[0]      # tile copies obj_032_c00
            srec = subs_ok.get(sid) or subs_ok.get(base)
            if srec is None:
                continue
            if sid in have:
                n_skipped += 1
                print(f"[merge-subs] {sid} already in the GLB — "
                      f"skipped (re-run guard)", flush=True)
                continue
            T, gname = sub_scene.graph[nn]
            geom = sub_scene.geometry[gname]
            scene.add_geometry(geom, node_name=str(nn),
                               geom_name=f"sub_{gname}",
                               transform=np.asarray(T))
            have.add(sid)
            n_added += 1
            if srec["id"] not in placed_ids:
                br = srec.get("bounds_render") or {}
                lo_r = np.asarray(br.get("lo", [0, 0, 0]), float)
                hi_r = np.asarray(br.get("hi", [0, 0, 0]), float)
                lo_raw = np.minimum(lo_r * r2r, hi_r * r2r)
                hi_raw = np.maximum(lo_r * r2r, hi_r * r2r)
                placed.append({
                    "id": srec["id"], "name": srec["name"],
                    "uid": srec.get("uid"),
                    "source": "sub_round",
                    "anchor": rec["anchor"],
                    "mount": "floor",
                    "fit_box": {"aabb_min": [round(float(v), 3)
                                             for v in lo_raw],
                                "aabb_max": [round(float(v), 3)
                                             for v in hi_raw]}})
                placed_ids.add(srec["id"])
            print(f"[merge-subs] + {sid} ({srec['name']}) on "
                  f"{rec['anchor']} ({rec['anchor_name']})", flush=True)

    if n_added:
        gpath.write_bytes(scene.export(file_type="glb"))
        fp["subs_merged"] = {"date": str(date.today()),
                             "n_added": n_added,
                             "by": "compose/merge_sub_placements.py"}
        jpath.write_text(json.dumps(fp, indent=1), encoding="utf-8")
    print(f"[merge-subs] {n_added} sub mesh(es) merged, "
          f"{n_skipped} skipped -> {gpath.name}. "
          f"Run fit_gravity next so riders rest on their hosts.",
          flush=True)


if __name__ == "__main__":
    main()
