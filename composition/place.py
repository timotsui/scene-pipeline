"""Stage 3a: place retrieved assets at the proposed boxes and composite them
over the splat views.

Frames: placements are RAW; meshes, cameras, and rendering happen in the
RENDER frame (raw * frame.raw_to_render). Assets are y-up, scaled uniformly to
the box height, bottom-aligned for floor objects, centered for wall objects,
yawed about +y (sign flips with the up-sign so raw yaw means the same physical
turn).

v0 composite: pyrender RGBA over the webp view, no per-pixel occlusion vs the
splat (known limit, see README). Writes composed_view_gpu_yaw*.png and
composed_state.json (the mutable state the jiggle loop edits).
"""
import json

import numpy as np
import trimesh
import pyrender
from PIL import Image

from comp_paths import paths
from assets_thor import load_asset


def look_at_pose(pos, look, up):
    """OpenGL camera pose (camera -Z = viewing direction)."""
    pos, look, up = (np.asarray(a, np.float64) for a in (pos, look, up))
    fwd = look - pos
    fwd /= np.linalg.norm(fwd)
    right = np.cross(fwd, up)
    right /= np.linalg.norm(right)
    true_up = np.cross(right, fwd)
    pose = np.eye(4)
    pose[:3, 0], pose[:3, 1], pose[:3, 2], pose[:3, 3] = right, true_up, -fwd, pos
    return pose


def placed_mesh(uid, center_raw, size_raw, yaw_deg, mount, floor_y_raw, r2r):
    """Load asset, scale/pose it in the RENDER frame."""
    sx, sy, sz = r2r
    mesh = load_asset(uid)
    lo, hi = mesh.bounds
    scale = size_raw[1] / max(hi[1] - lo[1], 1e-6)   # uniform, fit box height
    T = np.eye(4)
    T[:3, :3] = trimesh.transformations.rotation_matrix(
        np.radians(yaw_deg) * (1 if sy > 0 else -1), [0, 1, 0])[:3, :3] * scale
    mesh.apply_transform(T)
    lo, hi = mesh.bounds
    c_r = np.asarray(center_raw, np.float64) * np.asarray(r2r)  # render frame
    if mount == "floor":
        floor_render = floor_y_raw * sy
        target = np.array([c_r[0], floor_render, c_r[2]])
        offset = np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2])
    else:
        target = c_r
        offset = (lo + hi) / 2
    mesh.apply_translation(target - offset)
    return mesh


def composite_views(sc, state, out_prefix="composed_view_"):
    man = json.loads(paths.manifest(sc).read_text())
    fr = man["frame"]
    r2r = fr.get("raw_to_render", [1.0, 1.0, 1.0])
    meshes = []
    for e in state["objects"]:
        if not e.get("uid"):
            continue
        meshes.append(placed_mesh(e["uid"], e["center"], e["size"],
                                  e.get("yaw_deg", 0), e.get("mount", "floor"),
                                  fr["floor_y"], r2r))
    pkg = paths.package_dir(sc)
    outs = []
    for metaf in sorted(paths.views_dir(sc).glob("gpu_yaw*.json")):
        meta = json.loads(metaf.read_text())
        imgf = paths.views_dir(sc) / meta["file"]
        if not imgf.exists():
            continue
        w, h = (int(t) for t in meta["res"].split("x"))
        scene = pyrender.Scene(bg_color=[0, 0, 0, 0],
                               ambient_light=[0.55, 0.55, 0.55])
        for m in meshes:
            scene.add(pyrender.Mesh.from_trimesh(m, smooth=False))
        pose = look_at_pose([float(t) for t in meta["cam"].split(",")],
                            [float(t) for t in meta["look"].split(",")],
                            [float(t) for t in meta["up"].split(",")])
        # sidecar fov is horizontal; square views -> yfov equal, else convert
        hf = np.radians(float(meta["fov"]))
        yfov = 2 * np.arctan(np.tan(hf / 2) * h / w)
        scene.add(pyrender.PerspectiveCamera(yfov=yfov), pose=pose)
        scene.add(pyrender.DirectionalLight(intensity=2.5), pose=pose)
        r = pyrender.OffscreenRenderer(w, h)
        color, _ = r.render(scene, flags=pyrender.RenderFlags.RGBA)
        r.delete()
        bg = Image.open(imgf).convert("RGBA")
        comp = Image.alpha_composite(bg, Image.fromarray(color, "RGBA"))
        outf = pkg / f"{out_prefix}{metaf.stem}.png"
        comp.convert("RGB").save(outf)
        outs.append(outf)
        print(f"[place] wrote {outf}", flush=True)
    return outs


def export_glb(sc, state):
    """Combined mesh scene — the walkable artifact comparable to GLTS's glb.
    Exported in the RENDER (upright) frame."""
    man = json.loads(paths.manifest(sc).read_text())
    fr = man["frame"]
    r2r = fr.get("raw_to_render", [1.0, 1.0, 1.0])
    tscene = trimesh.Scene()
    for i, e in enumerate(state["objects"]):
        if not e.get("uid"):
            continue
        m = placed_mesh(e["uid"], e["center"], e["size"], e.get("yaw_deg", 0),
                        e.get("mount", "floor"), fr["floor_y"], r2r)
        tscene.add_geometry(m, node_name=f'{i}_{e["label"].replace(" ", "_")}')
    outf = paths.package_dir(sc) / "composed_scene.glb"
    tscene.export(outf)
    print(f"[place] wrote {outf}", flush=True)
    return outf


def render(sc):
    """Composite + glb from an existing composed_state.json (any mode)."""
    state = json.loads((paths.package_dir(sc) / "composed_state.json").read_text())
    outs = composite_views(sc, state)
    export_glb(sc, state)
    return outs


def build_state_from_proposal(sc):
    """Augment mode: compose_proposal.json + composed_assets.json -> state."""
    pkg = paths.package_dir(sc)
    prop = json.loads((pkg / "compose_proposal.json").read_text())
    assets = json.loads((pkg / "composed_assets.json").read_text())
    by_idx = {a["placement_idx"]: a for a in assets}
    objects = []
    for i, p in enumerate(prop["placements"]):
        a = by_idx.get(i, {})
        objects.append({**{k: p.get(k) for k in
                           ("label", "center", "size", "yaw_deg", "mount", "reason")},
                        "uid": a.get("uid"), "category": a.get("category")})
    state = {"scene": sc, "mode": "augment", "round": 0, "objects": objects}
    (pkg / "composed_state.json").write_text(json.dumps(state, indent=1))
    return state


def run(sc):
    build_state_from_proposal(sc)
    return render(sc)


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()
    run(args.scene)
