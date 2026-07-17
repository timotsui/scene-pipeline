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


def placed_mesh(uid, perm, sub_size, center_raw, mount, floor_y_raw, r2r,
                yaw_deg=0.0):
    """Asset -> RENDER-frame mesh: perm rotation, uniform scale, position.
    The uniform scale is the geometric-mean optimum computed from the REAL
    rotated mesh bounds vs the (sub-)box — never from annotation sizes, which
    lie for a fat minority of assets (window bbox z=14cm, mesh z=54cm).
    yaw_deg (C7 nudge): free rotation about render-frame up (+y) through the
    placed mesh's own bbox center — floor contact survives it."""
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
    if yaw_deg:
        lo, hi = mesh.bounds
        mesh.apply_transform(trimesh.transformations.rotation_matrix(
            np.deg2rad(yaw_deg), [0, 1, 0], (lo + hi) / 2))
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
                        e["mount"], fr["floor_y"], r2r,
                        yaw_deg=e.get("yaw", 0.0))
            for e in state["objects"]]


def _rgba_pass(meshes, meta, w, h):
    """Meshes through the sidecar camera -> transparent RGBA layer."""
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
    return Image.fromarray(color, "RGBA")


def _splat_floor_color(sc, fr):
    """Median splat color in a thin band at floor height, inner 80% of the
    footprint (walls/baseboards out; median rides out floor-object
    gaussians) -> the clean view's floor tint. Grey fallback if starved."""
    r3 = paths.load_r3()
    xyz, rgb, _, _ = r3.load_splat(str(paths.ply(sc)))
    p1, p9 = np.asarray(fr["extent_p1"]), np.asarray(fr["extent_p99"])
    lo, hi = np.minimum(p1, p9), np.maximum(p1, p9)
    pad = 0.1 * (hi - lo)
    m = ((np.abs(xyz[:, 1] - fr["floor_y"]) < 0.03)
         & (xyz[:, 0] > lo[0] + pad[0]) & (xyz[:, 0] < hi[0] - pad[0])
         & (xyz[:, 2] > lo[2] + pad[2]) & (xyz[:, 2] < hi[2] - pad[2]))
    if m.sum() < 100:
        print(f"[place2] floor band starved ({int(m.sum())} pts) — grey",
              flush=True)
        return (205, 205, 205)
    c = tuple(int(round(v * 255)) for v in np.median(rgb[m], 0))
    print(f"[place2] splat floor color {c} from {int(m.sum()):,} pts",
          flush=True)
    return c


def _floor_mesh(fr, color=(205, 205, 205), margin=0.3):
    """Flat floor over the room footprint (clean mode: grounds the meshes
    so nothing sits on air)."""
    r2r = np.asarray(fr.get("raw_to_render", [1.0, 1.0, 1.0]), np.float64)
    p1, p9 = (np.asarray(fr[k]) * r2r for k in ("extent_p1", "extent_p99"))
    lo, hi = np.minimum(p1, p9), np.maximum(p1, p9)
    m = trimesh.creation.box(extents=[hi[0] - lo[0] + 2 * margin, 0.02,
                                      hi[2] - lo[2] + 2 * margin])
    m.apply_translation([(lo[0] + hi[0]) / 2,
                         fr["floor_y"] * r2r[1] - 0.011,  # top just sub-floor
                         (lo[2] + hi[2]) / 2])
    m.visual.face_colors = list(color) + [255]
    return m


def judge_sidecars(sc):
    """Camera sidecars for loop judging: the judge_* rig (full-room
    coverage — 6 tilted yaws + straight-down; rendered by
    entangled_gen/render_judge_views.py) when present, else the legacy 4
    gpu_yaw* detection views (which cannot see the floor within ~2.1 m or
    the 15-deg wedges between views — 2026-07-15B handoff)."""
    vdir = paths.views_dir(sc)
    return (sorted(vdir.glob("judge_*.json"))
            or sorted(vdir.glob("gpu_yaw*.json")))


def composite_views(sc, state, outdir=None, prefix="composed2_view_",
                    splat_bg=True, sidecars=None):
    """splat_bg: True = real splat behind the meshes (canonical in-context
    view), False = flat grey (C7 loop judge: the splat in the composite
    masked missing/changed meshes from the VLM), "clean" = mesh-only over a
    synthetic floor (representation view — no gsplat anywhere; the carved-
    splat background was tried 2026-07-17 and rejected on cutout quality).
    sidecars: camera sidecar .json paths; default = the 4 canonical
    gpu_yaw* views (the loop passes judge_sidecars(sc) instead)."""
    man = json.loads(paths.manifest(sc).read_text())
    meshes = _meshes(state, man["frame"])
    if splat_bg == "clean":
        meshes = [_floor_mesh(man["frame"],
                              _splat_floor_color(sc, man["frame"]))] + meshes
    pkg = outdir or paths.package_dir(sc)
    outs = []
    if sidecars is None:
        sidecars = sorted(paths.views_dir(sc).glob("gpu_yaw*.json"))
    for metaf in sidecars:
        meta = json.loads(metaf.read_text())
        imgf = paths.views_dir(sc) / meta["file"]
        if splat_bg is True and not imgf.exists():
            continue
        w, h = (int(t) for t in meta["res"].split("x"))
        if splat_bg is True:
            bg = Image.open(imgf).convert("RGBA")
        else:
            bg = Image.new("RGBA", (w, h), (232, 232, 232, 255))
        comp = Image.alpha_composite(bg, _rgba_pass(meshes, meta, w, h))
        outf = pkg / f"{prefix}{metaf.stem}.png"
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
    ap.add_argument("--clean", action="store_true",
                    help="render the EXISTING composed_state2.json (loop "
                         "edits kept) mesh-only over a synthetic floor, no "
                         "gsplat -> composed2c_view_*")
    args = ap.parse_args()
    if args.clean:
        state = json.loads((paths.package_dir(args.scene)
                            / "composed_state2.json").read_text())
        composite_views(args.scene, state, prefix="composed2c_view_",
                        splat_bg="clean")
    else:
        run(args.scene)
