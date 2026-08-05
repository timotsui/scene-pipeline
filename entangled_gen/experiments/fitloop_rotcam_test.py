"""PH2 FIT LOOP design experiment (2026-08-03B): ROTATION-CHECK CAMERA
TEST. For 4 representative placed items, render an 8-step FREE-yaw
strip (45 deg steps relative to the placed orientation) from TWO
candidate cameras:
  camA -- the judge standpoint (0, 1.6, 0), same as the 7 judge views
  camB -- a dedicated 3/4 view per item (from the room-center side,
          elevated, framing the item)
The USER judges which camera reads better (standing rule: Claude never
concludes from images). Output strips ->
out/<scene>/compose/review_shots/rotcheck_cam{A,B}_<id>.png

Context = the CURRENT fitted preview (canon picks) + floor + walls;
target item spun about its own vertical center axis.
"""
import json
import sys
from pathlib import Path

import numpy as np
import trimesh
import pyrender
from PIL import Image, ImageDraw

EG = Path(r"D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen")
sys.path.insert(0, str(EG))
import paths  # noqa: E402
sys.path.insert(0, str(paths.REPO_ROOT / "composition"))
from place import look_at_pose  # noqa: E402

SCENE = "bedroom_marble"
ITEMS = ["obj_109", "obj_008", "obj_022", "obj_025"]  # chair, bed, shelf, table
YAW_STEPS = 8                # free spin: 45-deg steps RELATIVE to placed
TILE = 384
GAP = 12
OUTDIR = None  # set in main

cdir = paths.compose_dir(SCENE)
man = json.loads(paths.manifest(SCENE).read_text(encoding="utf-8"))
graph = json.loads((paths.scene_dir(SCENE) / "scene_graph.json")
                   .read_text(encoding="utf-8"))
r2r = np.array(man["frame"].get("raw_to_render", [1, 1, 1]), np.float32)
to_render = np.diag([r2r[0], r2r[1], r2r[2], 1.0])  # raw->render, self-inverse

shell = {n["id"]: n["geometry"]["plane"]["value_raw"]
         for n in graph["nodes"] if n["id"].startswith("arch_")}
wx = sorted((shell["arch_wall_x_low"] * r2r[0],
             shell["arch_wall_x_high"] * r2r[0]))
wz = sorted((shell["arch_wall_z_low"] * r2r[2],
             shell["arch_wall_z_high"] * r2r[2]))
room_c = np.array([(wx[0] + wx[1]) / 2, 0.0, (wz[0] + wz[1]) / 2])


def load_scene_meshes():
    """fitted_preview.glb (raw frame) -> {item_id: [render-frame meshes]}"""
    sc = trimesh.load(cdir / "fitted_preview.glb", force="scene")
    by_item = {}
    for name, geom in sc.geometry.items():
        m = geom.copy()
        m.apply_transform(to_render)
        oid = name.rsplit("_t", 1)[0]
        by_item.setdefault(oid, []).append(m)
    return by_item


def shell_meshes():
    fl = trimesh.creation.box(
        extents=[wx[1] - wx[0] + 0.4, 0.05, wz[1] - wz[0] + 0.4])
    fl.apply_translation([room_c[0], -0.025, room_c[2]])
    walls = []
    H, T = 2.6, 0.05
    for x in wx:
        w = trimesh.creation.box(extents=[T, H, wz[1] - wz[0] + 0.4])
        w.apply_translation([x, H / 2, room_c[2]])
        walls.append(w)
    for z in wz:
        w = trimesh.creation.box(extents=[wx[1] - wx[0] + 0.4, H, T])
        w.apply_translation([room_c[0], H / 2, z])
        walls.append(w)
    for m in [fl] + walls:
        m.visual = trimesh.visual.ColorVisuals(
            m, vertex_colors=[210, 208, 202, 255])
    return [fl] + walls


def yaw_about(center, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    R = np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]])
    T1 = np.eye(4); T1[:3, 3] = -center
    T2 = np.eye(4); T2[:3, 3] = center
    return T2 @ R @ T1


def render_frame(meshes, eye, target, fov, res=TILE):
    scene = pyrender.Scene(bg_color=[1, 1, 1, 1], ambient_light=[0.5] * 3)
    for m in meshes:
        scene.add(pyrender.Mesh.from_trimesh(m, smooth=False))
    pose = look_at_pose(np.asarray(eye, float), np.asarray(target, float),
                       [0, 1, 0])
    scene.add(pyrender.PerspectiveCamera(yfov=np.radians(fov)), pose=pose)
    scene.add(pyrender.DirectionalLight(intensity=3.0), pose=pose)
    side = look_at_pose(np.asarray(target, float) + np.array([1.5, 2.5, 1.0]),
                        np.asarray(target, float), [0, 1, 0])
    scene.add(pyrender.DirectionalLight(intensity=1.5), pose=side)
    r = pyrender.OffscreenRenderer(res, res)
    color, _ = r.render(scene)
    r.delete()
    return Image.fromarray(color)


def strip(tiles, labels, out_path):
    W = TILE * len(tiles) + GAP * (len(tiles) - 1)
    im = Image.new("RGB", (W, TILE), (25, 25, 25))
    for i, (t, lab) in enumerate(zip(tiles, labels)):
        d = ImageDraw.Draw(t)
        d.rectangle([0, 0, 30 + 11 * len(lab), 26], fill=(0, 0, 0))
        d.text((8, 5), lab, fill=(255, 255, 60))
        im.paste(t, (i * (TILE + GAP), 0))
    im.save(out_path)
    print(f"[rotcam] wrote {out_path}")


def main():
    outdir = paths.compose_dir(SCENE) / "review_shots"
    outdir.mkdir(exist_ok=True)
    by_item = load_scene_meshes()
    context_static = shell_meshes()

    for oid in ITEMS:
        if oid not in by_item:
            print(f"[rotcam] {oid} not in fitted preview, skipped")
            continue
        target_meshes = by_item[oid]
        others = [m for k, v in by_item.items() if k != oid for m in v]
        allb = np.vstack([m.bounds for m in target_meshes])
        lo, hi = allb.min(0), allb.max(0)
        ctr = (lo + hi) / 2
        diag = float(np.linalg.norm(hi - lo))

        # camA: judge standpoint, eye height, adaptive fov on the item
        eyeA = np.array([0.0, 1.6, 0.0])
        dist = float(np.linalg.norm(ctr - eyeA))
        fovA = float(np.clip(np.degrees(2 * np.arctan2(0.8 * diag, dist)),
                             30, 75))
        # camB: dedicated 3/4 -- from the room-center side, elevated
        horiz = room_c - np.array([ctr[0], 0, ctr[2]])
        horiz[1] = 0
        n = np.linalg.norm(horiz)
        horiz = horiz / n if n > 1e-6 else np.array([1.0, 0, 0])
        eyeB = ctr + horiz * (1.5 * diag) + np.array([0, 0.9 * diag, 0])
        eyeB[1] = max(eyeB[1], 0.6)

        for cam, eye, fov in (("A", eyeA, fovA), ("B", eyeB, 45.0)):
            tiles, labels = [], []
            for i in range(YAW_STEPS):
                deg = i * (360 // YAW_STEPS)
                R = yaw_about(ctr, deg)
                spun = []
                for m in target_meshes:
                    mm = m.copy()
                    mm.apply_transform(R)
                    spun.append(mm)
                img = render_frame(context_static + others + spun,
                                   eye, ctr, fov)
                tiles.append(img)
                labels.append(f"{i + 1}: +{deg}\u00b0")
            strip(tiles, labels, outdir / f"rotcheck_cam{cam}_{oid}.png")


if __name__ == "__main__":
    main()
