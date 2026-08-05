"""SAME-CAMERA REFERENCE PAIRS -- renders only, the user-eyeball gate
(2026-08-04, user optimization: "isolate just the object in the test fit,
same camera angle as the reference photo, include walls and floor").

For every placed object with detection evidence: render the FITTED mesh --
target + room shell only, no other objects -- from THE CAMERA THAT TOOK THE
REFERENCE PHOTO, so photo and render are the same view of the same room and
the rotation question needs no cross-view reasoning.

Camera derivation (the mirror-bug family -- so it is CHECKED, not trusted):
  sidecar look d_p (pano frame)  ->  d_raw = (x_p, -y_p, z_p)
      [rig_sp0/pano_selfrender_meta.json, the mapping pano_lift.py has
       lifted 233 objects through]
  eye_raw = (0, -1.571, 0)  (defined by construction)
  raw -> render frame: * raw_to_render = (-1, -1, 1)  (proper, det +1)
  up: pano (0,1,0) -> raw (0,-1,0) -> render (0,1,0)
The pano image is a DEFINED left-right mirror, so the photo panel is
flipped back (and its box redrawn at flipped coords); the true-geometry
render then matches it directly.

NUMERIC SELF-CHECK per object: the fitted box's 8 corners projected into
this camera must land on the detection's recorded box_2d (flipped to
corrected coords). Center offset + IoU printed and recorded -- a frame
mistake shows up as a gross miss, not a vibe.

Writes: compose/rotation_check/refcam/<oid>_pair.png (+ refcam_check.json).
NO model calls. The index page shows the pairs for the user's verdict.

  python refcam_pairs.py [--scene bedroom_marble]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pyrender
from PIL import Image, ImageDraw, ImageOps

HERE = Path(__file__).parent
EG = HERE.parent
sys.path.insert(0, str(EG))
sys.path.insert(0, str(EG / "compose"))
import paths  # noqa: E402
from rotation_check import (  # noqa: E402
    load_scene, render_frame, project, load_swap_map, resolve_reference, GAP,
)
from place import look_at_pose  # noqa: E402

RES = 960
R2R = np.array([-1.0, -1.0, 1.0])


def render_object_rgba(meshes, eye, target, fov, res):
    """The target ALONE on a transparent background -- layered onto the
    shell render afterwards (user 08-04: no shell offsets; a wall-flush
    picture or floor-sunk mat must stay visible even where the proxy slab
    would swallow it in a joint z-buffered render)."""
    scene = pyrender.Scene(bg_color=[0, 0, 0, 0], ambient_light=[0.5] * 3)
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
    color, _ = r.render(scene, flags=pyrender.RenderFlags.RGBA)
    r.delete()
    return Image.fromarray(color, "RGBA")


def detection_cam_render_frame(sidecar, eye_raw):
    """Sidecar (pano frame) -> (eye, look_target, up) in the RENDER frame."""
    d_p = np.array([float(t) for t in sidecar["look"].split(",")])
    d_raw = np.array([d_p[0], -d_p[1], d_p[2]])       # recorded mapping
    eye = np.asarray(eye_raw) * R2R
    fwd = d_raw * R2R
    return eye, eye + fwd, float(sidecar["fov"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--items", default="all")
    args = ap.parse_args()

    sd = paths.scene_dir(args.scene)
    rig = sd / "rig_sp0"
    eye_raw = json.loads((rig / "pano_selfrender_meta.json")
                         .read_text(encoding="utf-8"))["eye_raw"]
    cdir, nodes, by_item, shell, wx, wz, room_c = load_scene(args.scene)
    placed = json.loads((cdir / "fitted_preview.json")
                        .read_text(encoding="utf-8"))["placed"]
    names = {p["id"]: p["name"] for p in placed}
    items = ([p["id"] for p in placed] if args.items == "all"
             else [i.strip() for i in args.items.split(",")])

    odir = cdir / "rotation_check" / "refcam"
    odir.mkdir(parents=True, exist_ok=True)
    swap_map = load_swap_map(cdir)

    rows = []
    for oid in items:
        if oid not in by_item:
            continue
        mem, orig_name = resolve_reference(oid, nodes, swap_map)
        if not mem:
            rows.append({"item": oid, "name": names.get(oid, "?"),
                         "status": "no_reference"})
            print(f"[refcam] {oid} {names.get(oid,'?')}: no reference "
                  "(strict add -- plausibility fallback keeps its stimuli)")
            continue
        view = mem["view"]
        # sidecar: rig crops = the folder detection actually ran on
        side_p = rig / "crops" / f"{view}.json"
        if not side_p.exists():
            side_p = sd / "pano_crops" / f"{view}.json"
        side = json.loads(side_p.read_text(encoding="utf-8"))
        eye, look, fov = detection_cam_render_frame(side, eye_raw)

        # ---- photo panel: detection-source webp, mirrored back, box redrawn
        photo_p = rig / "crops" / f"{view}.webp"
        if not photo_p.exists():
            photo_p = sd / "pano_crops" / f"{view}.webp"
        photo = Image.open(photo_p).convert("RGB")
        if photo.size != (RES, RES):
            photo = photo.resize((RES, RES))
        photo = ImageOps.mirror(photo)
        b = mem.get("box_2d")
        exp_box = None
        if b and len(b) == 4:
            exp_box = [RES - b[2], b[1], RES - b[0], b[3]]
            d = ImageDraw.Draw(photo)
            d.rectangle([exp_box[0] - 3, exp_box[1] - 3,
                         exp_box[2] + 3, exp_box[3] + 3],
                        outline=(255, 220, 0), width=5)
            d.text((exp_box[0], max(0, exp_box[1] - 16)), oid,
                   fill=(255, 220, 0))

        # ---- isolated render, LAYERED: shell pass, then the target alone
        # composited on top so proxy slabs can never swallow it
        tgt = by_item[oid]
        img = render_frame(shell, eye, look, fov, res=RES).convert("RGBA")
        img.alpha_composite(render_object_rgba(tgt, eye, look, fov, RES))
        img = img.convert("RGB")

        # ---- numeric self-check: fitted box vs detection box, same view
        allb = np.vstack([m.bounds for m in tgt])
        lo, hi = allb.min(0), allb.max(0)
        pose = look_at_pose(np.asarray(eye, float), np.asarray(look, float),
                            [0, 1, 0])
        uv = project(pose, fov, RES,
                     [(x, y, z) for x in (lo[0], hi[0])
                      for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        status, off, iou = "no_projection", None, None
        got_box = None
        if uv and exp_box:
            us, vs = [p[0] for p in uv], [p[1] for p in uv]
            got_box = [min(us), min(vs), max(us), max(vs)]
            gcx, gcy = (got_box[0] + got_box[2]) / 2, \
                       (got_box[1] + got_box[3]) / 2
            ecx, ecy = (exp_box[0] + exp_box[2]) / 2, \
                       (exp_box[1] + exp_box[3]) / 2
            off = float(np.hypot(gcx - ecx, gcy - ecy))
            ix0, iy0 = max(got_box[0], exp_box[0]), max(got_box[1], exp_box[1])
            ix1, iy1 = min(got_box[2], exp_box[2]), min(got_box[3], exp_box[3])
            inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
            a1 = (got_box[2] - got_box[0]) * (got_box[3] - got_box[1])
            a2 = (exp_box[2] - exp_box[0]) * (exp_box[3] - exp_box[1])
            iou = float(inter / max(a1 + a2 - inter, 1e-6))
            status = "ok" if iou > 0.2 else "MISS"
            dd = ImageDraw.Draw(img)
            dd.rectangle(got_box, outline=(80, 200, 255), width=3)

        # ---- pair sheet: corrected photo | isolated same-camera render
        sheet = Image.new("RGB", (RES * 2 + GAP, RES + 30), (25, 25, 25))
        sheet.paste(photo, (0, 30))
        sheet.paste(img, (RES + GAP, 30))
        d = ImageDraw.Draw(sheet)
        left_lab = (f"REFERENCE photo -- the ORIGINAL {orig_name} this swap "
                    f"replaced, view {view}, mirror corrected"
                    if orig_name else
                    f"REFERENCE photo -- view {view}, mirror corrected, "
                    f"{oid} outlined")
        d.text((8, 9), left_lab, fill=(255, 255, 60))
        d.text((RES + GAP + 8, 9),
               "PLACED object, ISOLATED, layered over walls+floor, SAME "
               "camera -- blue = its box, must sit on the yellow one",
               fill=(255, 255, 60))
        sheet.save(odir / f"{oid}_pair.png")

        rows.append({"item": oid, "name": names.get(oid, "?"), "view": view,
                     "status": status, "swap_origin": orig_name,
                     "center_off_px": None if off is None else round(off, 1),
                     "iou": None if iou is None else round(iou, 3)})
        print(f"[refcam] {oid:<14}{names.get(oid,'?'):<18} {view:<18}"
              f"{status:<6} off {off if off is None else f'{off:6.1f}'}px  "
              f"iou {iou if iou is None else f'{iou:.3f}'}")

    ok = sum(1 for r in rows if r.get("status") == "ok")
    miss = [r["item"] for r in rows if r.get("status") == "MISS"]
    (odir / "refcam_check.json").write_text(
        json.dumps({"scene": args.scene, "date": "2026-08-04",
                    "note": "same-camera isolated reference pairs; numeric "
                            "box check; NO model calls; user eyeball gate",
                    "rows": rows}, indent=2), encoding="utf-8")
    print(f"\n[refcam] {ok} ok / {len(miss)} MISS"
          + (f" ({miss})" if miss else "")
          + f" / {sum(1 for r in rows if r.get('status')=='no_reference')} "
            f"no-reference -> {odir / 'refcam_check.json'}")


if __name__ == "__main__":
    main()
