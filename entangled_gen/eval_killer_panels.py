"""The killer figure's two missing panels — splat + edit.

Panel A  <scene>_splat_persp.png  the ORIGINAL world, rendered as a
         deliberately rough point scatter (user direction: low quality,
         so the reader is not side-tracked by splat prettiness), same
         persp camera as the product shots, ceiling-clipped, room-clipped.
Panel C  <scene>_edit_persp.png   the composed scene with a semantic edit:
         move one named object group and remove another.  Object IDs come
         from the final placement receipt and GLB node names; mesh size is
         never used as a stand-in for identity. Same walls/floor/clip/render
         path as eval_renders. Panel B is the existing product shot.

Compute-only (reads gen_raw.ply, the GLB, the shell); nothing re-run.

Run:  python eval_killer_panels.py --scene natural_living
"""
import argparse
import json
import math

import numpy as np
from PIL import Image
import trimesh

import paths
import eval_renders as er

SH_C0 = 0.28209479177387814
MAX_PTS = 3_000_000
PT = 2                      # point size in px — part of the "rough" look


def load_splat_points(scene):
    """xyz + rgb + opacity from the 62-float 3DGS ply, header-driven."""
    p = paths.scene_dir(scene) / "gen_raw.ply"
    with open(p, "rb") as f:
        props, n = [], 0
        while True:
            line = f.readline().decode("ascii", "replace").strip()
            if line.startswith("element vertex"):
                n = int(line.split()[-1])
            elif line.startswith("property"):
                props.append(line.split()[-1])
            elif line == "end_header":
                break
        data = np.fromfile(f, dtype=np.float32,
                           count=n * len(props)).reshape(n, len(props))
    i = {k: props.index(k) for k in
         ("x", "y", "z", "f_dc_0", "f_dc_1", "f_dc_2", "opacity")}
    xyz = data[:, [i["x"], i["y"], i["z"]]]
    rgb = np.clip(0.5 + SH_C0 * data[:, [i["f_dc_0"], i["f_dc_1"],
                                         i["f_dc_2"]]], 0, 1)
    op = 1.0 / (1.0 + np.exp(-data[:, i["opacity"]]))
    keep = op > 0.3
    xyz, rgb = xyz[keep], rgb[keep]
    if len(xyz) > MAX_PTS:
        sel = np.random.default_rng(0).choice(len(xyz), MAX_PTS, replace=False)
        xyz, rgb = xyz[sel], rgb[sel]
    return xyz, rgb


def camera(scene, boundary):
    (cx, cy), half = er.frame_of(boundary)
    t = math.tan(math.radians(er.PERSP_FOV_DEG) / 2)
    half = half + er.WALL_H * t
    return cx, cy, half / t, t


def splat_panel(scene, out_png):
    _, poly, _ = er.ours_scene(scene)
    boundary = er.clean_boundary(poly)
    cx, cy, eye_h, t = camera(scene, boundary)
    M = er._plan_matrix(scene)

    xyz, rgb = load_splat_points(scene)
    plan = xyz @ M[:3, :3].T + M[:3, 3]
    keep = (plan[:, 2] > -0.3) & (plan[:, 2] < er.WALL_H)
    from matplotlib.path import Path as MplPath
    clip = MplPath(er._offset_poly(
        [tuple(p[:2]) for p in boundary], er.WALL_T + 0.01))
    keep &= clip.contains_points(plan[:, :2])
    plan, rgb = plan[keep], rgb[keep]

    d = eye_h - plan[:, 2]
    u = ((plan[:, 0] - cx) / (d * t) + 1) / 2 * er.RES
    v = (1 - ((plan[:, 1] - cy) / (d * t) + 1) / 2) * er.RES
    ok = (d > 0.1) & (u >= 0) & (u < er.RES - PT) & (v >= 0) & (v < er.RES - PT)
    u, v, d, rgb = u[ok].astype(int), v[ok].astype(int), d[ok], rgb[ok]

    order = np.argsort(-d)                  # far first; near overwrites
    img = np.zeros((er.RES, er.RES, 3), np.uint8)
    col = (rgb[order] * 255).astype(np.uint8)
    uu, vv = u[order], v[order]
    for dy in range(PT):
        for dx in range(PT):
            img[vv + dy, uu + dx] = col
    Image.fromarray(img).save(out_png)
    print(f"[killer] {out_png.name}: {len(uu)} points")


def _named_meshes(scene):
    """Return final GLB meshes as (object_id, mesh) in the plan frame."""
    glb = paths.scene_dir(scene) / "compose" / "fitted_preview.glb"
    source = trimesh.load(str(glb), force="scene")
    plan = er._plan_matrix(scene)
    out = []
    # Scene.dump() applies each node transform while preserving the GLB's
    # textured material. Rebuilding meshes from scene.geometry gives the
    # same bounds but drops most texture images in pyrender, making objects
    # appear black against the black background.
    dumped = source.dump()
    nodes = list(source.graph.nodes_geometry)
    if len(dumped) != len(nodes):
        raise ValueError("GLB node/mesh count mismatch; identity is ambiguous")
    for node_name, mesh in zip(nodes, dumped):
        mesh = mesh.copy()
        mesh.apply_transform(plan)
        oid = str(node_name).rsplit("_t", 1)[0]
        out.append((oid, mesh))
    return out


def _object_group(scene, root_id):
    """The named object and any deferred small objects attached to it."""
    shopping = paths.scene_dir(scene) / "compose" / "shopping.json"
    data = json.loads(shopping.read_text(encoding="utf-8"))
    children = {}
    for item in data.get("subs_deferred") or []:
        host = item.get("host") or item.get("anchor")
        if host and item.get("id"):
            children.setdefault(host, []).append(item["id"])
    group, todo = set(), [root_id]
    while todo:
        oid = todo.pop()
        if oid in group:
            continue
        group.add(oid)
        todo.extend(children.get(oid, []))
    return group


def edit_panel(scene, out_png, move_id, drop_id):
    _, poly, _ = er.ours_scene(scene)
    boundary = er.clean_boundary(poly)
    center, half = er.frame_of(boundary)

    receipt = json.loads((paths.scene_dir(scene) / "compose" /
                          "fitted_preview.json").read_text(encoding="utf-8"))
    placed = {item["id"]: item for item in receipt.get("placed") or []}
    for action, oid in (("move", move_id), ("remove", drop_id)):
        if oid not in placed:
            raise ValueError(f"cannot {action} {oid}: not in final placement receipt")

    named = _named_meshes(scene)
    present = {oid for oid, _ in named}
    if move_id not in present or drop_id not in present:
        raise ValueError("semantic edit target is missing from the final GLB: "
                         f"move={move_id in present}, remove={drop_id in present}")
    move_group = _object_group(scene, move_id) & present
    drop_group = _object_group(scene, drop_id) & present
    if move_group & drop_group:
        raise ValueError("move and remove groups overlap")

    xs = [p[0] for p in boundary]
    ys = [p[1] for p in boundary]
    room_c = np.array([(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2])
    move_meshes = [mesh for oid, mesh in named if oid in move_group]
    lo = np.min([mesh.bounds[0] for mesh in move_meshes], axis=0)
    hi = np.max([mesh.bounds[1] for mesh in move_meshes], axis=0)
    mc = ((lo + hi) / 2)[:2]
    vec = room_c - mc
    L = np.linalg.norm(vec)
    step = vec / L * min(1.4, 0.45 * L) if L > 1e-6 else np.zeros(2)

    edited = []
    for oid, mesh in named:
        if oid in drop_group:
            continue
        mesh = mesh.copy()
        if oid in move_group:
            mesh.apply_translation([step[0], step[1], 0.0])
        edited.append(mesh)
    print(f"[killer] moved {move_id} ({placed[move_id].get('name')}) "
          f"with {len(move_group) - 1} attached object(s) by "
          f"{np.linalg.norm(step):.2f} m; removed {drop_id} "
          f"({placed[drop_id].get('name')}) with "
          f"{len(drop_group) - 1} attached object(s)")

    walls = er.wall_mesh(boundary)
    floor = er.floor_mesh(boundary)
    edited = er.clip_to_room(edited, boundary) + [walls, floor]
    er.render(edited, [walls, floor], center, half, True, out_png)
    print(f"[killer] {out_png.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--move-id", default="swap_r2n2_in1",
                    help="final placement ID of the object group to move")
    ap.add_argument("--drop-id", default="obj_012",
                    help="final placement ID of the object group to remove")
    a = ap.parse_args()
    er.OUT_DIR.mkdir(parents=True, exist_ok=True)
    splat_panel(a.scene, er.OUT_DIR / f"{a.scene}_splat_persp.png")
    edit_panel(a.scene, er.OUT_DIR / f"{a.scene}_edit_persp.png",
               a.move_id, a.drop_id)


if __name__ == "__main__":
    main()
