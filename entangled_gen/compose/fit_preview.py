"""
FIT PREVIEW (part of the shopping output process, 2026-08-03): place
every anchor's #1 candidate mesh from compose/shopping.json into its
box -- perm rotation + uniform scale + tiling, bottom-aligned (wall
items y-centered, ceiling items top-aligned) -- and write the result
as a RAW-frame GLB the scene viewer serves as its "fitted preview"
layer (viewer/serve.py /fitted_preview.glb, checkbox in the HUD).

This is the NAIVE placement -- no judging, no candidate walking; the
fit loop (next module) will replace the #1-only choice. Re-run after
every shopping.py run to refresh the layer.

Placement happens in the RENDER frame (y up, like the asset meshes),
then the whole scene is rotated into the RAW frame with the manifest's
raw_to_render signs (self-inverse, and rot180-about-z is a PROPER
rotation -- no mirroring) so the viewer needs no browser-side flip.

Output: out/<scene>/compose/fitted_preview.glb + fitted_preview.json
(what was placed: uid / perm / scale / tiles per item).

Run:  python compose/fit_preview.py --scene bedroom_marble
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

sys.path.insert(0, str(paths.REPO_ROOT / "composition"))
from assets_thor import load_asset  # noqa: E402
from thumbs import perm_rotation  # noqa: E402


def place_candidate(mesh, cand, lo, hi, mount):
    """One candidate mesh -> list of posed instances filling the
    render-frame box [lo, hi] (k tiles along cand's tile axis)."""
    m = mesh.copy()
    m.apply_transform(perm_rotation(cand.get("perm", "xyz")))
    m.apply_scale(cand["scale"])
    k, axis = cand.get("k", 1), cand.get("axis", 0)
    step = (hi[axis] - lo[axis]) / k
    out = []
    for i in range(k):
        inst = m.copy()
        blo, bhi = inst.bounds
        ctr = (blo + bhi) / 2
        t = np.zeros(3)
        for ax in (0, 2):
            target = (lo[ax] + hi[ax]) / 2
            if ax == axis:
                target = lo[ax] + step * (i + 0.5)
            t[ax] = target - ctr[ax]
        if mount == "ceiling":
            t[1] = hi[1] - bhi[1]
        elif mount == "wall":
            t[1] = (lo[1] + hi[1]) / 2 - ctr[1]
        else:
            t[1] = lo[1] - blo[1]
        inst.apply_translation(t)
        out.append(inst)
    return out


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()

    cdir = paths.compose_dir(args.scene)
    sl = json.loads((cdir / "shopping.json").read_text(encoding="utf-8"))
    man = json.loads(paths.manifest(args.scene).read_text(encoding="utf-8"))
    r2r = np.array(man["frame"].get("raw_to_render", [1, 1, 1]),
                   np.float32)
    if float(np.prod(r2r)) < 0:
        print("[fit_preview] WARNING: raw_to_render has odd sign count "
              "-- render->raw would MIRROR meshes; check the frame")
    to_raw = np.diag([r2r[0], r2r[1], r2r[2], 1.0])

    scene = trimesh.Scene()
    placed, failed = [], []
    for r in sl["items"]:
        if not r.get("candidates"):
            continue
        c = r["candidates"][0]
        try:
            mesh = load_asset(c["uid"])
        except Exception as ex:
            failed.append({"id": r["id"], "uid": c["uid"],
                           "error": str(ex)[:200]})
            continue
        lo = np.asarray(r["box"]["aabb_min"], np.float32) * r2r
        hi = np.asarray(r["box"]["aabb_max"], np.float32) * r2r
        lo, hi = np.minimum(lo, hi), np.maximum(lo, hi)
        for j, inst in enumerate(place_candidate(mesh, c, lo, hi,
                                                 r["mount"])):
            inst.apply_transform(to_raw)   # render -> raw, baked
            scene.add_geometry(inst,
                               node_name=f'{r["id"]}_t{j}',
                               geom_name=f'{r["id"]}_t{j}')
        placed.append({"id": r["id"], "name": r["name"],
                       "uid": c["uid"], "perm": c.get("perm", "xyz"),
                       "scale": c["scale"], "k": c.get("k", 1),
                       "mount": r["mount"], "score": c["score"]})

    gpath = cdir / "fitted_preview.glb"
    gpath.write_bytes(scene.export(file_type="glb"))
    (cdir / "fitted_preview.json").write_text(json.dumps({
        "scene": args.scene, "built": str(date.today()),
        "generated_by": "compose/fit_preview.py",
        "note": "NAIVE #1-candidate placement (no fit loop); RAW-frame "
                "glb for the viewer's fitted-preview layer",
        "elapsed_s": round(time.time() - t0, 1),
        "placed": placed, "failed": failed,
    }, indent=1), encoding="utf-8")
    print(f"[fit_preview] wrote {gpath} "
          f"({gpath.stat().st_size / 1e6:.1f} MB, {len(placed)} items, "
          f"{len(failed)} failed, {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
