"""The killer figure's two missing panels — splat + edit.

Panel A  <scene>_splat_persp.png  the ORIGINAL world, rendered as a
         deliberately rough point scatter (user direction: low quality,
         so the reader is not side-tracked by splat prettiness), same
         persp camera as the product shots, ceiling-clipped, room-clipped.
Panel C  <scene>_edit_persp.png   the composed scene with a two-line edit
         applied: the largest-footprint mesh pulled toward the room
         centre, the second-largest removed. Same walls/floor/clip/render
         path as eval_renders. Panel B is the existing product shot.

Compute-only (reads gen_raw.ply, the GLB, the shell); nothing re-run.

Run:  python eval_killer_panels.py --scene natural_living
"""
import argparse
import math

import numpy as np
from PIL import Image

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


def edit_panel(scene, out_png):
    meshes, poly, _ = er.ours_scene(scene)
    boundary = er.clean_boundary(poly)
    center, half = er.frame_of(boundary)

    areas = []
    for k, m in enumerate(meshes):
        e = m.bounding_box.extents          # plan frame: x, y footprint
        areas.append((float(e[0] * e[1]), k))
    areas.sort(reverse=True)
    move_k = areas[0][1]
    drop_k = areas[1][1]

    xs = [p[0] for p in boundary]
    ys = [p[1] for p in boundary]
    room_c = np.array([(min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2])
    mc = meshes[move_k].bounding_box.centroid[:2]
    vec = room_c - mc
    L = np.linalg.norm(vec)
    step = vec / L * min(1.4, 0.45 * L) if L > 1e-6 else np.zeros(2)
    mv = meshes[move_k].copy()
    mv.apply_translation([step[0], step[1], 0.0])
    print(f"[killer] moved mesh #{move_k} "
          f"(footprint {areas[0][0]:.2f} m2) by {np.linalg.norm(step):.2f} m; "
          f"removed mesh #{drop_k} (footprint {areas[1][0]:.2f} m2)")

    edited = [mv if k == move_k else m
              for k, m in enumerate(meshes) if k != drop_k]
    walls = er.wall_mesh(boundary)
    floor = er.floor_mesh(boundary)
    edited = er.clip_to_room(edited, boundary) + [walls, floor]
    er.render(edited, [walls, floor], center, half, True, out_png)
    print(f"[killer] {out_png.name}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    a = ap.parse_args()
    er.OUT_DIR.mkdir(parents=True, exist_ok=True)
    splat_panel(a.scene, er.OUT_DIR / f"{a.scene}_splat_persp.png")
    edit_panel(a.scene, er.OUT_DIR / f"{a.scene}_edit_persp.png")


if __name__ == "__main__":
    main()
