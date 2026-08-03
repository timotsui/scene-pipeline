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
    face_deg, face_dot = 0, None
    if face_dir is not None:
        s0 = m.bounds[1] - m.bounds[0]
        sub_w = (hi[0] - lo[0]) / (k if axis == 0 else 1)
        sub_d = (hi[2] - lo[2]) / (k if axis == 2 else 1)
        best = None
        for deg in (0, 90, 180, 270):
            # 0/180 keep the placed footprint EXACTLY -- never gate
            # them (the old gate vetoed 180 whenever the scaled asset
            # legitimately overhung its box, so 12/30 items silently
            # kept arbitrary facing -- the backwards-shelf bug).
            # 90/270 swap extents: allow only if the swap still fits.
            if deg % 180 != 0:
                ex, ez = s0[2], s0[0]
                if ex > sub_w * 1.05 or ez > sub_d * 1.05:
                    continue
            f = yaw_matrix(deg)[:3, :3] @ P[:3, :3] @ np.array(
                [0.0, 0.0, 1.0])
            score = f[0] * face_dir[0] + f[2] * face_dir[1]
            if best is None or score > best[0]:
                best = (score, deg)
        if best:
            face_deg, face_dot = best[1], round(float(best[0]), 2)
            if face_deg:
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
    return out, face_deg, face_dot


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

    # PILLOW EVIDENCE (user GT 08-03: the bed lies SIDE-against the
    # wall, so wall-hug's touching-wall=back assumption broke): a
    # pillow sub marks its host's HEAD end along the host's long
    # horizontal axis; front = the opposite end. Measured scene data
    # (the pillow's recorded box), scene-agnostic, fires only when a
    # pillow sub exists.
    pillow_head = {}   # host id -> unit front (render frame)
    for s in sl.get("subs_deferred", []):
        if "pillow" not in s.get("name", "") or not s.get("box"):
            continue
        hb = next((it for it in sl["items"]
                   if it["id"] == s.get("host")), None)
        if not hb:
            continue
        hlo = np.asarray(hb["box"]["aabb_min"], np.float32) * r2r
        hhi = np.asarray(hb["box"]["aabb_max"], np.float32) * r2r
        hlo, hhi = np.minimum(hlo, hhi), np.maximum(hlo, hhi)
        plo = np.asarray(s["box"]["aabb_min"], np.float32) * r2r
        phi = np.asarray(s["box"]["aabb_max"], np.float32) * r2r
        pc, hc = (plo + phi) / 2, (hlo + hhi) / 2
        ax = 0 if (hhi[0] - hlo[0]) >= (hhi[2] - hlo[2]) else 2
        sign = 1.0 if pc[ax] > hc[ax] else -1.0
        pillow_head[hb["id"]] = ((-sign, 0.0) if ax == 0
                                 else (0.0, -sign))

    def face_dir_of(item_id, lo, hi, mount):
        """(unit xz front direction, evidence source) -- layered by
        evidence strength (obj_096 + obj_032 lessons: witness facing
        is +-45deg quantized and oblique for wall-adjacent things,
        but geometry constrains them completely):
          wall-mounted            -> the wall's inward normal
          wall-HUGGING (box EDGE within 0.15 m of a wall -- center
            distance lied for deep furniture) -> that wall's normal
          else observed witness facing (line-of-sight converted)
          else near-wall / room-middle heuristic (invented adds,
          no_front items). Ceiling items have no facing."""
        if mount == "ceiling":
            return None, None
        # edge gap to each wall: (gap, axis, inward normal)
        walls = [(lo[0] - wx[0], "x", (1.0, 0.0)),
                 (wx[1] - hi[0], "x", (-1.0, 0.0)),
                 (lo[2] - wz[0], "z", (0.0, 1.0)),
                 (wz[1] - hi[2], "z", (0.0, -1.0))]
        # THIN-AXIS RULE (obj_127 door / obj_043 corner-shelf lesson):
        # a wall thing faces along its thin horizontal axis (a door
        # slab's normal, a shelf's depth) -- near a corner the SIDE
        # wall can be nearer by gap than the thing's own wall. Prefer
        # thin-axis walls among the candidates; nearest gap only for
        # near-square boxes or when no thin-axis wall qualifies.
        sx, sz = hi[0] - lo[0], hi[2] - lo[2]
        thin = "x" if sx * 1.3 < sz else "z" if sz * 1.3 < sx else None

        def pick(cands):
            pref = [w for w in cands if w[1] == thin] if thin else []
            g, _, nrm = min(pref or cands)
            return g, nrm

        if mount == "wall":
            return pick(walls)[1], "wall_constraint"
        if item_id in pillow_head:   # measured head-end evidence
            return pillow_head[item_id], "pillow_evidence"
        # 0.30: lift boxes run fat (obj_032 flush shelf measured a
        # 0.23 m edge gap); true huggers here are <= 0.23, the next
        # nearest walls 0.37+, so 0.30 splits them with margin
        hug = [w for w in walls if w[0] < 0.30]
        if hug:
            return pick(hug)[1], "wall_hug"
        d = min(walls)[0]
        n = min(walls)[2]
        if item_id in observed_face:
            return observed_face[item_id], "observed"
        if d < 0.6:
            return n, "heuristic"
        cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
        v = np.array([room_c[0] - cx, room_c[1] - cz])
        L = float(np.hypot(v[0], v[1]))
        return ((v[0] / L, v[1] / L) if L > 1e-6 else None), "heuristic"
    if float(np.prod(r2r)) < 0:
        print("[fit_preview] WARNING: raw_to_render has odd sign count "
              "-- render->raw would MIRROR meshes; check the frame")
    to_raw = np.diag([r2r[0], r2r[1], r2r[2], 1.0])

    scene = trimesh.Scene()
    placed, failed = [], []
    fdir_by = {}   # item id -> decided front (render frame)
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
        fdir, fsrc = face_dir_of(r["id"], lo, hi, r["mount"])
        fdir_by[r["id"]] = fdir
        insts, face_deg, face_dot = place_candidate(
            mesh, c, lo, hi, r["mount"], face_dir=fdir)
        for j, inst in enumerate(insts):
            inst.apply_transform(to_raw)   # render -> raw, baked
            scene.add_geometry(inst,
                               node_name=f'{r["id"]}_t{j}',
                               geom_name=f'{r["id"]}_t{j}')
        placed.append({"id": r["id"], "name": r["name"],
                       "uid": c["uid"], "perm": c.get("perm", "xyz"),
                       "scale": c["scale"], "k": c.get("k", 1),
                       "face_yaw_deg": face_deg,
                       "face_source": fsrc,
                       # dot(achieved front, target); < 0.9 = the
                       # chosen perm cannot reach the target with a
                       # footprint-legal turn -- a FIT-LOOP work item
                       # (orientation must join candidate scoring)
                       "face_dot": face_dot,
                       "face_conflict": (face_dot is not None
                                         and face_dot < 0.9),
                       "front_dir_raw": (
                           [round(float(fdir[0] * float(r2r[0])), 3),
                            round(float(fdir[1] * float(r2r[2])), 3)]
                           if fdir else None),
                       "mount": r["mount"], "score": c["score"]})

    # SUB FACING = HOST INHERITANCE (obj_032 lesson: things in/on a
    # shelf face wherever the shelf faces; their own photo readings
    # are grazing-angle noise). Walk the host chain until it reaches
    # a placed item's decided front; unresolvable hosts (e.g. the
    # ceiling light) leave the sub without a preview front. The sub
    # placement round applies the same contract with real meshes.
    host_of = {s["id"]: s.get("host")
               for s in sl.get("subs_deferred", [])}
    sub_front = {}
    for _ in range(4):   # host chains are short; sub-of-sub resolves
        for sid, h in host_of.items():
            if sid in sub_front or not h:
                continue
            f = fdir_by.get(h) or sub_front.get(h)
            if f:
                sub_front[sid] = f
    subs_front = [{"id": sid, "host": host_of[sid],
                   "face_source": "host_inherit",
                   "front_dir_raw":
                       [round(float(f[0] * float(r2r[0])), 3),
                        round(float(f[1] * float(r2r[2])), 3)]}
                  for sid, f in sorted(sub_front.items())]

    gpath = cdir / "fitted_preview.glb"
    gpath.write_bytes(scene.export(file_type="glb"))
    (cdir / "fitted_preview.json").write_text(json.dumps({
        "scene": args.scene, "built": str(date.today()),
        "generated_by": "compose/fit_preview.py",
        "graph_fingerprint": paths.graph_fingerprint(args.scene),
        "note": "NAIVE #1-candidate placement (no fit loop); RAW-frame "
                "glb for the viewer's fitted-preview layer",
        "elapsed_s": round(time.time() - t0, 1),
        "placed": placed, "subs_front": subs_front, "failed": failed,
    }, indent=1), encoding="utf-8")
    print(f"[fit_preview] wrote {gpath} "
          f"({gpath.stat().st_size / 1e6:.1f} MB, {len(placed)} items, "
          f"{len(failed)} failed, {time.time() - t0:.0f}s)")


if __name__ == "__main__":
    main()
