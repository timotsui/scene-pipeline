"""Thumbnail cache for objathor assets: one 3/4-view render per uid, written
to <OBJATHOR>/_thumbs/<uid>.png (dataset-level cache, scene-independent).

__main__ renders every uid referenced by a scene's shortlists2.json that is
not already cached — safe to re-run, only misses are rendered.
"""
import json

import numpy as np
import pyrender
from PIL import Image

from comp_paths import OBJATHOR, paths
from assets_thor import load_asset
from place import look_at_pose

THUMBS = OBJATHOR / "_thumbs"
SIZE = 256
_AX = {"x": 0, "y": 1, "z": 2}


def thumb_stem(uid, perm="xyz"):
    return uid if perm == "xyz" else f"{uid}_{perm}"


def thumb_path(uid, perm="xyz"):
    return THUMBS / f"{thumb_stem(uid, perm)}.png"


def perm_rotation(perm):
    """4x4 PROPER rotation whose |dims| effect is the axis permutation perm
    (world axis i takes the asset's perm[i] axis); a sign flip absorbs odd
    parity so it is never a mirror."""
    R = np.zeros((3, 3))
    for i, c in enumerate(perm):
        R[i, _AX[c]] = 1.0
    if np.linalg.det(R) < 0:
        R[0] *= -1
    T = np.eye(4)
    T[:3, :3] = R
    return T


def render_thumb(uid, perm="xyz", size=SIZE):
    mesh = load_asset(uid)
    if perm != "xyz":
        mesh.apply_transform(perm_rotation(perm))
    lo, hi = mesh.bounds
    center = (lo + hi) / 2
    radius = float(np.linalg.norm(hi - lo)) / 2
    eye = center + radius * 2.4 * np.array([0.72, 0.45, 0.72])
    scene = pyrender.Scene(bg_color=[1, 1, 1, 1], ambient_light=[0.45] * 3)
    scene.add(pyrender.Mesh.from_trimesh(mesh, smooth=False))
    pose = look_at_pose(eye, center, [0, 1, 0])
    scene.add(pyrender.PerspectiveCamera(yfov=np.radians(40)), pose=pose)
    scene.add(pyrender.DirectionalLight(intensity=3.0), pose=pose)
    side = look_at_pose(center + radius * 2.4 * np.array([-0.7, 0.6, 0.2]),
                        center, [0, 1, 0])
    scene.add(pyrender.DirectionalLight(intensity=1.2), pose=side)
    r = pyrender.OffscreenRenderer(size, size)
    color, _ = r.render(scene, flags=pyrender.RenderFlags.RGBA)
    r.delete()
    bg = Image.new("RGBA", (size, size), (255, 255, 255, 255))
    return Image.alpha_composite(bg, Image.fromarray(color, "RGBA")).convert("RGB")


def ensure(items):
    """Render any uncached (uid, perm) pairs; returns (n_rendered, n_failed)."""
    THUMBS.mkdir(exist_ok=True)
    todo = [it for it in dict.fromkeys(items)
            if not thumb_path(it[0], it[1]).exists()]
    done = fail = 0
    for i, (uid, perm) in enumerate(todo):
        try:
            render_thumb(uid, perm).save(thumb_path(uid, perm))
            done += 1
        except Exception as e:
            fail += 1
            print(f"[thumbs] FAIL {uid} {perm}: {e}", flush=True)
        if (i + 1) % 25 == 0:
            print(f"[thumbs] {i + 1}/{len(todo)}", flush=True)
    print(f"[thumbs] rendered {done}, failed {fail}, "
          f"already cached {len(dict.fromkeys(items)) - len(todo)}", flush=True)
    return done, fail


def scene_items(sc):
    sl = json.loads((paths.package_dir(sc) / "shortlists2.json").read_text())
    return [(r["uid"], r.get("perm", "xyz"))
            for b in sl["boxes"] for r in b["candidates"]]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()
    ensure(scene_items(args.scene))
