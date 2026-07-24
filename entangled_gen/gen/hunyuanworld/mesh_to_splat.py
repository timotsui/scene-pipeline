"""mesh_to_splat.py — HunyuanWorld scenegen meshes -> gaussian-splat ply.

DRAFT 2026-07-06, UNTESTED (written overnight before any mesh existed).
Verify on the first real scenegen output before trusting.

demo_scenegen.py writes out/<scene>/scenegen/mesh_layer{0,1,2}.ply — open3d
vertex-colored triangle meshes (layer 0 = sky/bg, higher = fg layers). The
lift pipeline consumes 3DGS plys (rendertools/03_render.py load_splat needs
x,y,z + f_dc_0..2 + opacity(logit) + scale_0..2(log); SuperSplat/viewer like
nx,ny,nz + rot too). This samples each mesh area-uniformly, interpolates
vertex colors, synthesizes isotropic gaussians (radius from global sample
density), unions the layers, writes binary_little_endian gen_raw.ply.

Usage (HunyuanWorld env):
  python mesh_to_splat.py <scene>            # e.g. bedroom_hw1
  python mesh_to_splat.py <scene> --points 3000000 --radius-mult 1.5
Reads  OUT/<scene>/scenegen/mesh_layer*.ply
Writes OUT/<scene>/gen_raw.ply   (paths.ply() location; refuses to overwrite
                                  unless --force)
"""
import argparse
import glob
import os
import sys

import numpy as np
import open3d as o3d

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import paths  # noqa: E402  (entangled_gen/paths.py — OUT from local_paths.json)


def _wsl(p):
    """Windows drive path -> /mnt form (this script runs under WSL)."""
    s = str(p).replace("\\", "/")
    return f"/mnt/{s[0].lower()}{s[2:]}" if len(s) > 1 and s[1] == ":" else s


OUT = _wsl(paths.OUT)
C0 = 0.28209479177387814


def sample_layer(mesh_path, n_points):
    mesh = o3d.io.read_triangle_mesh(mesh_path)
    if not mesh.has_triangles():
        print(f"  {os.path.basename(mesh_path)}: no triangles, skipped")
        return None, 0.0
    area = mesh.get_surface_area()
    if not mesh.has_vertex_colors():
        print(f"  WARNING {os.path.basename(mesh_path)}: no vertex colors -> gray")
        mesh.paint_uniform_color([0.5, 0.5, 0.5])
    pc = mesh.sample_points_uniformly(number_of_points=max(n_points, 1000))
    return pc, area


def write_gs_ply(path, xyz, rgb, radius, opacity=0.95):
    n = xyz.shape[0]
    logit_op = float(np.log(opacity / (1 - opacity)))
    fields = [
        ("x", xyz[:, 0]), ("y", xyz[:, 1]), ("z", xyz[:, 2]),
        ("nx", np.zeros(n)), ("ny", np.zeros(n)), ("nz", np.zeros(n)),
        ("f_dc_0", (rgb[:, 0] - 0.5) / C0),
        ("f_dc_1", (rgb[:, 1] - 0.5) / C0),
        ("f_dc_2", (rgb[:, 2] - 0.5) / C0),
        ("opacity", np.full(n, logit_op)),
        ("scale_0", np.log(radius)), ("scale_1", np.log(radius)),
        ("scale_2", np.log(radius)),
        ("rot_0", np.ones(n)), ("rot_1", np.zeros(n)),
        ("rot_2", np.zeros(n)), ("rot_3", np.zeros(n)),
    ]
    header = ["ply", "format binary_little_endian 1.0", f"element vertex {n}"]
    header += [f"property float {name}" for name, _ in fields]
    header.append("end_header")
    data = np.stack([np.asarray(v, dtype="<f4") for _, v in fields], axis=1)
    with open(path, "wb") as f:
        f.write(("\n".join(header) + "\n").encode("ascii"))
        data.astype("<f4").tofile(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("scene")
    ap.add_argument("--points", type=int, default=3_000_000,
                    help="total points across all layers (area-weighted)")
    ap.add_argument("--radius-mult", type=float, default=1.5,
                    help="gaussian radius = mult * sqrt(area_per_sample)")
    ap.add_argument("--force", action="store_true")
    args = ap.parse_args()

    sg = os.path.join(OUT, args.scene, "scenegen")
    out_ply = os.path.join(OUT, args.scene, "gen_raw.ply")
    meshes = sorted(glob.glob(os.path.join(sg, "mesh_layer*.ply")))
    if not meshes:
        sys.exit(f"no mesh_layer*.ply in {sg}")
    if os.path.exists(out_ply) and not args.force:
        sys.exit(f"{out_ply} exists (use --force)")

    # first pass: areas -> area-proportional point budgets
    areas = []
    for m in meshes:
        mesh = o3d.io.read_triangle_mesh(m)
        areas.append(mesh.get_surface_area() if mesh.has_triangles() else 0.0)
    total_area = sum(areas) or 1.0

    xyz_all, rgb_all, rad_all = [], [], []
    for m, area in zip(meshes, areas):
        if area <= 0:
            continue
        n_pts = int(args.points * area / total_area)
        pc, _ = sample_layer(m, n_pts)
        if pc is None:
            continue
        xyz = np.asarray(pc.points, dtype=np.float32)
        rgb = np.asarray(pc.colors, dtype=np.float32)
        # per-layer isotropic radius from its own sample density
        r = args.radius_mult * float(np.sqrt(area / max(len(xyz), 1)))
        xyz_all.append(xyz)
        rgb_all.append(np.clip(rgb, 0, 1))
        rad_all.append(np.full(len(xyz), max(r, 1e-4), dtype=np.float32))
        print(f"  {os.path.basename(m)}: area={area:.1f} pts={len(xyz)} r={r:.4f}")

    xyz = np.concatenate(xyz_all)
    rgb = np.concatenate(rgb_all)
    rad = np.concatenate(rad_all)
    write_gs_ply(out_ply, xyz, rgb, rad)
    print(f"OK {out_ply}: {len(xyz)} gaussians from {len(meshes)} layers")


if __name__ == "__main__":
    main()
