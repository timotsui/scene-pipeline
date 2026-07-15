"""C6 base composition: place every picks2.json winner at its manifest box in
the fit's orientation — the "base" the later refinement passes edit.

Per box (uid from picks2, geometry from shortlists2): load the asset, apply
the fit's `perm` as a proper rotation (thumbs.perm_rotation), scale UNIFORMLY
by the fit's optimal scale (all three axes negotiated — replaces v0's
height-only rule), tile k copies along the fit's axis, then bottom-align on
the floor (mount=floor) or center in the box (wall/free). Facing (0 vs 180
about y) is NOT resolved here — that is a later refinement.

Frames: box coords RAW; meshes/cameras composite in the RENDER frame via
frame.raw_to_render (same contract as place.py). v0 artifacts untouched:
this writes composed_state2.json + composed2_view_gpu_yaw*.png +
composed_scene2.glb.
"""
import json

import numpy as np
import pyrender
import trimesh
from PIL import Image

from assets_thor import load_asset
from comp_paths import paths
from place import look_at_pose
from thumbs import perm_rotation


def _sub_boxes(center, size, axis, k):
    """Split a box into k equal boxes along one horizontal axis (0=x, 2=z)."""
    step = size[axis] / k
    subs = []
    for i in range(k):
        c = list(center)
        c[axis] = center[axis] - size[axis] / 2 + (i + 0.5) * step
        s = list(size)
        s[axis] = step
        subs.append((c, s))
    return subs


def placed_mesh(uid, perm, sub_size, center_raw, mount, floor_y_raw, r2r):
    """Asset -> RENDER-frame mesh: perm rotation, uniform scale, position.
    The uniform scale is the geometric-mean optimum computed from the REAL
    rotated mesh bounds vs the (sub-)box — never from annotation sizes, which
    lie for a fat minority of assets (window bbox z=14cm, mesh z=54cm)."""
    mesh = load_asset(uid)
    mesh.apply_transform(perm_rotation(perm))
    lo, hi = mesh.bounds
    ext = np.maximum(hi - lo, 1e-6)
    scale = float(np.exp(np.mean(np.log(np.asarray(sub_size) / ext))))
    T = np.eye(4)
    T[:3, :3] *= scale
    mesh.apply_transform(T)
    lo, hi = mesh.bounds
    c_r = np.asarray(center_raw, np.float64) * np.asarray(r2r)
    if mount == "floor":
        floor_render = floor_y_raw * r2r[1]
        target = np.array([c_r[0], floor_render, c_r[2]])
        offset = np.array([(lo[0] + hi[0]) / 2, lo[1], (lo[2] + hi[2]) / 2])
    else:                                   # wall / free: center in the box
        target = c_r
        offset = (lo + hi) / 2
    mesh.apply_translation(target - offset)
    return mesh


def build_state(sc):
    """picks2 winners + shortlists2 box geometry -> composed_state2.json."""
    pkg = paths.package_dir(sc)
    sl = json.loads((pkg / "shortlists2.json").read_text())
    picks = json.loads((pkg / "picks2.json").read_text())
    objects = []
    for b in sl["boxes"]:
        p = picks.get(b["id"], {})
        if not p.get("uid"):
            continue
        for i, (c, s) in enumerate(_sub_boxes(b["center"], b["size"],
                                              p["axis"], p["k"])):
            objects.append({"label": b["label"], "group": b["id"], "part": i,
                            "uid": p["uid"], "category": p["category"],
                            "center": c, "size": s, "perm": p["perm"],
                            "scale": p["scale"], "mount": b["mount"]})
    state = {"scene": sc, "mode": "base", "objects": objects}
    (pkg / "composed_state2.json").write_text(json.dumps(state, indent=1))
    print(f"[place2] {len(objects)} instances from "
          f"{sum(1 for v in picks.values() if v.get('uid'))} picks", flush=True)
    return state


def _meshes(state, fr):
    r2r = fr.get("raw_to_render", [1.0, 1.0, 1.0])
    return [placed_mesh(e["uid"], e["perm"], e["size"], e["center"],
                        e["mount"], fr["floor_y"], r2r)
            for e in state["objects"]]


def composite_views(sc, state):
    man = json.loads(paths.manifest(sc).read_text())
    meshes = _meshes(state, man["frame"])
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
        hf = np.radians(float(meta["fov"]))   # horizontal fov -> vertical
        yfov = 2 * np.arctan(np.tan(hf / 2) * h / w)
        scene.add(pyrender.PerspectiveCamera(yfov=yfov), pose=pose)
        scene.add(pyrender.DirectionalLight(intensity=2.5), pose=pose)
        r = pyrender.OffscreenRenderer(w, h)
        color, _ = r.render(scene, flags=pyrender.RenderFlags.RGBA)
        r.delete()
        bg = Image.open(imgf).convert("RGBA")
        comp = Image.alpha_composite(bg, Image.fromarray(color, "RGBA"))
        outf = pkg / f"composed2_view_{metaf.stem}.png"
        comp.convert("RGB").save(outf)
        outs.append(outf)
        print(f"[place2] wrote {outf}", flush=True)
    return outs


def export_glb(sc, state):
    man = json.loads(paths.manifest(sc).read_text())
    tscene = trimesh.Scene()
    for e, m in zip(state["objects"], _meshes(state, man["frame"])):
        name = f'{e["group"]}_{e["part"]}_{e["label"].replace(" ", "_")}'
        tscene.add_geometry(m, node_name=name)
    outf = paths.package_dir(sc) / "composed_scene2.glb"
    tscene.export(outf)
    print(f"[place2] wrote {outf}", flush=True)
    return outf


def run(sc):
    state = build_state(sc)
    outs = composite_views(sc, state)
    export_glb(sc, state)
    return outs


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()
    run(args.scene)
