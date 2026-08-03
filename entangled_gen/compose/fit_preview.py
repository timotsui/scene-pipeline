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


def yaw_matrix(deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    T = np.eye(4)
    T[0, 0], T[0, 2], T[2, 0], T[2, 2] = c, s, -s, c
    return T


def place_candidate(mesh, cand, lo, hi, mount, face_dir=None):
    """One candidate mesh -> (posed instances filling the render-frame
    box [lo, hi] (k tiles along cand's tile axis), chosen facing yaw).

    FACING RULE (08-03, user: bookshelves faced the wall): library
    front convention = asset +z (verified by the user on a 32-asset
    front-view sheet). Among the four compass yaws whose footprint
    still fits the (sub-)box, pick the one pointing the front along
    face_dir (unit xz: away from the nearest wall, else toward the
    room middle)."""
    m = mesh.copy()
    P = perm_rotation(cand.get("perm", "xyz"))
    m.apply_transform(P)
    m.apply_scale(cand["scale"])
    k, axis = cand.get("k", 1), cand.get("axis", 0)
    face_deg = 0
    if face_dir is not None:
        s0 = m.bounds[1] - m.bounds[0]
        sub_w = (hi[0] - lo[0]) / (k if axis == 0 else 1)
        sub_d = (hi[2] - lo[2]) / (k if axis == 2 else 1)
        best = None
        for deg in (0, 90, 180, 270):
            ex, ez = (s0[0], s0[2]) if deg % 180 == 0 else (s0[2], s0[0])
            if ex > sub_w * 1.05 or ez > sub_d * 1.05:
                continue
            f = yaw_matrix(deg)[:3, :3] @ P[:3, :3] @ np.array(
                [0.0, 0.0, 1.0])
            score = f[0] * face_dir[0] + f[2] * face_dir[1]
            if best is None or score > best[0]:
                best = (score, deg)
        if best and best[1]:
            face_deg = best[1]
            m.apply_transform(yaw_matrix(face_deg))
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
    return out, face_deg


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()

    cdir = paths.compose_dir(args.scene)
    sl = json.loads((cdir / "shopping.json").read_text(encoding="utf-8"))
    man = json.loads(paths.manifest(args.scene).read_text(encoding="utf-8"))
    graph = json.loads((paths.scene_dir(args.scene) / "scene_graph.json")
                       .read_text(encoding="utf-8"))
    r2r = np.array(man["frame"].get("raw_to_render", [1, 1, 1]),
                   np.float32)
    shell = {n["id"]: n["geometry"]["plane"]["value_raw"]
             for n in graph["nodes"] if n["id"].startswith("arch_")}
    wx = sorted((shell["arch_wall_x_low"] * r2r[0],
                 shell["arch_wall_x_high"] * r2r[0]))
    wz = sorted((shell["arch_wall_z_low"] * r2r[2],
                 shell["arch_wall_z_high"] * r2r[2]))
    room_c = ((wx[0] + wx[1]) / 2, (wz[0] + wz[1]) / 2)

    # OBSERVED facing (describe pass v8, user ruling: define forward
    # upstream -- the room already shows which way things face). RAW
    # world_dir -> render frame. Detected objects use this; invented
    # adds/swap-ins keep the wall/room-middle heuristic fallback.
    observed_face = {}
    for jn in graph.get("judged", {}).get("nodes", []):
        wd = ((jn.get("appearance") or {}).get("facing") or {})\
            .get("world_dir")
        if wd:
            observed_face[jn["id"]] = (wd[0] * float(r2r[0]),
                                       wd[1] * float(r2r[2]))

    def face_dir_of(item_id, lo, hi, mount):
        """Unit xz direction the item's front should point: the
        OBSERVED direction when the witness saw one, else off the
        nearest wall when hugging one (or wall-mounted), else toward
        the room middle. Ceiling items have no facing."""
        if mount == "ceiling":
            return None
        if item_id in observed_face:
            return observed_face[item_id]
        cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
        walls = [(cx - wx[0], (1.0, 0.0)), (wx[1] - cx, (-1.0, 0.0)),
                 (cz - wz[0], (0.0, 1.0)), (wz[1] - cz, (0.0, -1.0))]
        d, n = min(walls)
        if mount == "wall" or d < 0.6:
            return n
        v = np.array([room_c[0] - cx, room_c[1] - cz])
        L = float(np.hypot(v[0], v[1]))
        return (v[0] / L, v[1] / L) if L > 1e-6 else None
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
        insts, face_deg = place_candidate(
            mesh, c, lo, hi, r["mount"],
            face_dir=face_dir_of(r["id"], lo, hi, r["mount"]))
        for j, inst in enumerate(insts):
            inst.apply_transform(to_raw)   # render -> raw, baked
            scene.add_geometry(inst,
                               node_name=f'{r["id"]}_t{j}',
                               geom_name=f'{r["id"]}_t{j}')
        placed.append({"id": r["id"], "name": r["name"],
                       "uid": c["uid"], "perm": c.get("perm", "xyz"),
                       "scale": c["scale"], "k": c.get("k", 1),
                       "face_yaw_deg": face_deg,
                       "face_source": ("observed"
                                       if r["id"] in observed_face
                                       else "heuristic"),
                       "mount": r["mount"], "score": c["score"]})

    gpath = cdir / "fitted_preview.glb"
    gpath.write_bytes(scene.export(file_type="glb"))
    (cdir / "fitted_preview.json").write_text(json.dumps({
        "scene": args.scene, "built": str(date.today()),
        "generated_by": "compose/fit_preview.py",
        "graph_fingerprint": paths.graph_fingerprint(args.scene),
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
