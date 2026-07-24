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


# ---- background-source resolver (integration directive 2026-07-21) --------
# The cut lane (entangled_gen/cut/) removes an object's Gaussians from the
# scene splat, leaving out/<scene>/cut/<obj>[_vN]/background.ply — the scene
# with the object cleanly gone, layout-identical to gen_raw.ply. When such a
# background exists, compositing meshes over IT (instead of the original
# splat) kills the ghost problem the tinted-floor clean view works around.

_CUT_NON_OBJECT_DIRS = {"dataset", "bg_renders", "integration_demo"}


def find_cut_background(sc):
    """Newest cut background.ply for a scene, or None.

    Selection rule (documented for the auto mode): candidates are
    out/<scene>/cut/<name>/background.ply for every <name> except the
    dataset/cache/demo folders; winner = NEWEST background.ply by mtime.
    A re-cut variant (obj_004_v2) is always written after its base
    (obj_004), so variants supersede automatically — i.e. for the current
    single-object cuts, "newest" = the most complete cut available.
    Revisit when multi-object cuts land (Step 12 merges cuts)."""
    cdir = paths.scene_dir(sc) / "cut"
    if not cdir.is_dir():
        return None
    cands = [d / "background.ply" for d in cdir.iterdir()
             if d.is_dir() and d.name not in _CUT_NON_OBJECT_DIRS
             and (d / "background.ply").exists()]
    return max(cands, key=lambda p: p.stat().st_mtime) if cands else None


def resolve_background(sc, mode="auto"):
    """Resolve a --background mode -> (composite_views splat_bg value, cut
    background.ply or None). Modes:
      auto     = cut background when the scene has one, else the EXISTING
                 tinted-floor clean path (pipeline never breaks on un-cut
                 scenes/objects)
      cut      = require the cut background (error if absent) — test override
      tinted   = the existing clean path, unconditionally — test override
      original = original splat behind the meshes (the ghost problem)"""
    if mode == "original":
        return True, None
    if mode == "tinted":
        return "clean", None
    bg = find_cut_background(sc)
    if bg is None:
        if mode == "cut":
            raise SystemExit(f"--background cut: no cut background under "
                             f"{paths.scene_dir(sc) / 'cut'}")
        print("[place2] background auto: no cut background -> tinted-floor "
              "clean path", flush=True)
        return "clean", None
    print(f"[place2] background {mode}: cut background {bg}", flush=True)
    return "cut", bg


def _cut_bg_image(sc, bg_ply, meta, metaf):
    """Background image for ONE camera in cut mode. Reuse the cut lane's
    existing after_<view>.png (render_cut_review.py rendered background.ply
    from all 15 review cameras — read-only reuse) when present at the right
    resolution; else render background.ply through this camera with
    splat-transform into cut/bg_renders/<variant>/ — a cache OUTSIDE the
    read-only cut outputs. Same renderer/fov/near/background color as
    cut/render_cut_review.py, so reused and fresh images match."""
    if bg_ply is None:
        bg_ply = find_cut_background(sc)
    w, h = (int(t) for t in meta["res"].split("x"))
    have = bg_ply.parent / "renders" / f"after_{metaf.stem}.png"
    if have.exists() and Image.open(have).size == (w, h):
        return have
    cache = paths.scene_dir(sc) / "cut" / "bg_renders" / bg_ply.parent.name
    cache.mkdir(parents=True, exist_ok=True)
    png = cache / f"{metaf.stem}.png"
    if png.exists():
        return png
    import subprocess
    webp = cache / f"{metaf.stem}.webp"
    cmd = ["splat-transform", "-w", "-g", "0", str(bg_ply),
           "--camera", meta["cam"], "--look-at", meta["look"],
           "--up", meta["up"], "--fov", str(meta["fov"]),
           "--near", str(meta.get("near", 0.2)),
           "--resolution", meta["res"], "--background", "0.08,0.08,0.1",
           str(webp)]
    print(f"[place2] rendering cut background for {metaf.stem} ...",
          flush=True)
    subprocess.run(cmd, check=True, shell=True, timeout=600)
    Image.open(webp).convert("RGB").save(png)
    return png


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
                    splat_bg=True, sidecars=None, cut_bg=None):
    """splat_bg: True = real splat behind the meshes (canonical in-context
    view), False = flat grey (C7 loop judge: the splat in the composite
    masked missing/changed meshes from the VLM), "clean" = mesh-only over a
    synthetic floor (representation view — no gsplat anywhere; the carved-
    splat background was tried 2026-07-17 and rejected on cutout quality),
    "cut" = the CUT background splat behind the meshes (the object's
    Gaussians removed by the cut lane — no ghost; cut_bg = background.ply
    from resolve_background, else the newest cut is found automatically).
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
        if not imgf.exists():   # cut/dataset sidecars keep images next door
            alt = metaf.parent.parent / "images" / meta["file"]
            imgf = alt if alt.exists() else imgf
        if splat_bg is True and not imgf.exists():
            continue
        w, h = (int(t) for t in meta["res"].split("x"))
        if splat_bg is True:
            bg = Image.open(imgf).convert("RGBA")
        elif splat_bg == "cut":
            bg = Image.open(_cut_bg_image(sc, cut_bg, meta, metaf)
                            ).convert("RGBA")
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
    ap.add_argument("--background",
                    choices=["auto", "cut", "tinted", "original"],
                    default=None,
                    help="render the EXISTING composed_state2.json over a "
                         "RESOLVED background -> composed2b_view_*. auto = "
                         "cut background.ply when the scene has one, else "
                         "the tinted-floor clean path; cut/tinted/original "
                         "force one source for testing. Default behavior "
                         "(no flag) is untouched.")
    args = ap.parse_args()
    if args.background:
        state = json.loads((paths.package_dir(args.scene)
                            / "composed_state2.json").read_text())
        splat_bg, cut_bg = resolve_background(args.scene, args.background)
        composite_views(args.scene, state, prefix="composed2b_view_",
                        splat_bg=splat_bg, cut_bg=cut_bg)
    elif args.clean:
        state = json.loads((paths.package_dir(args.scene)
                            / "composed_state2.json").read_text())
        composite_views(args.scene, state, prefix="composed2c_view_",
                        splat_bg="clean")
    else:
        run(args.scene)
