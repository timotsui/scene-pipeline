"""COMPASS DRAWN ON THE IMAGE -- renders only, user eyeball (2026-08-04).

Instead of describing the compass in words, draw it: a floor-level compass
rose (N/E/S/W arrows, 0.6 m long) at the target object's footprint,
projected through the SAME camera into BOTH panels -- the mirror-corrected
photograph and the isolated same-camera render. Same camera => same pixel
coords => the identical rose lands identically in both, so "faces S" means
the visible S arrow, not a mental one.

N = +z, E = +x in the render frame (the same table compass_anchors and
implied_degrees use, so the arithmetic check stays valid).

Writes compose/rotation_check/compass_demo_<oid>.png. NO model calls.

  python compass_overlay_test.py [--item obj_008]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps

HERE = Path(__file__).parent
EG = HERE.parent
sys.path.insert(0, str(EG))
sys.path.insert(0, str(EG / "compose"))
import paths  # noqa: E402
from rotation_check import (  # noqa: E402
    load_scene, render_layered, project, resolve_reference, load_swap_map,
    detection_cam_render_frame, GAP, REF_W,
)
from place import look_at_pose  # noqa: E402

ARROWS = {"N": (0.0, 0.0, 1.0), "E": (1.0, 0.0, 0.0),
          "S": (0.0, 0.0, -1.0), "W": (-1.0, 0.0, 0.0)}
ARM = 0.6          # metres


def draw_compass(img, pose, fov, res, origin, col_n=(255, 80, 80),
                 col=(255, 255, 255)):
    """Floor compass rose at `origin`, projected like everything else.
    N is tinted so the rose's orientation is unmistakable."""
    d = ImageDraw.Draw(img)
    o_uv = project(pose, fov, res, [origin])
    if not o_uv:
        return img
    ox, oy = o_uv[0]
    for name, v in ARROWS.items():
        tip = (origin[0] + v[0] * ARM, 0.0, origin[2] + v[2] * ARM)
        uv = project(pose, fov, res, [tip])
        if not uv:
            continue
        tx, ty = uv[0]
        c = col_n if name == "N" else col
        d.line([ox, oy, tx, ty], fill=c, width=4)
        # arrowhead: two short back-strokes
        bx, by = ox - tx, oy - ty
        n = max((bx * bx + by * by) ** 0.5, 1e-6)
        bx, by = bx / n * 14, by / n * 14
        for s in (0.45, -0.45):
            d.line([tx, ty, tx + bx - by * s, ty + by + bx * s],
                   fill=c, width=4)
        lx, ly = tx + (tx - ox) * 0.12, ty + (ty - oy) * 0.12
        d.rectangle([lx - 11, ly - 11, lx + 11, ly + 11], fill=(0, 0, 0))
        d.text((lx - 5, ly - 8), name, fill=c)
    d.ellipse([ox - 4, oy - 4, ox + 4, oy + 4], fill=col)
    return img


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--item", default="obj_008")
    args = ap.parse_args()
    oid = args.item

    sd = paths.scene_dir(args.scene)
    rig = sd / "rig_sp0"
    eye_raw = json.loads((rig / "pano_selfrender_meta.json")
                         .read_text(encoding="utf-8"))["eye_raw"]
    cdir, nodes, by_item, shell, wx, wz, room_c = load_scene(args.scene)
    swap_map = load_swap_map(cdir)

    mem, orig_name = resolve_reference(oid, nodes, swap_map)
    if not mem:
        raise SystemExit(f"[compass] {oid} has no reference")
    side_p = rig / "crops" / f"{mem['view']}.json"
    if not side_p.exists():
        side_p = sd / "pano_crops" / f"{mem['view']}.json"
    side = json.loads(side_p.read_text(encoding="utf-8"))
    eye, look, fov = detection_cam_render_frame(side, eye_raw)
    pose = look_at_pose(np.asarray(eye, float), np.asarray(look, float),
                        [0, 1, 0])

    tgt = by_item[oid]
    allb = np.vstack([m.bounds for m in tgt])
    lo, hi = allb.min(0), allb.max(0)
    origin = ((lo[0] + hi[0]) / 2, 0.0, (lo[2] + hi[2]) / 2)

    # photo panel: mirror-corrected, box, then the rose
    photo_p = rig / "crops" / f"{mem['view']}.webp"
    if not photo_p.exists():
        photo_p = sd / "pano_crops" / f"{mem['view']}.webp"
    photo = Image.open(photo_p).convert("RGB")
    if photo.size != (REF_W, REF_W):
        photo = photo.resize((REF_W, REF_W))
    photo = ImageOps.mirror(photo)
    b = mem.get("box_2d")
    if b and len(b) == 4:
        d = ImageDraw.Draw(photo)
        x0, x1 = REF_W - b[2], REF_W - b[0]
        d.rectangle([x0 - 3, b[1] - 3, x1 + 3, b[3] + 3],
                    outline=(255, 220, 0), width=5)
        d.text((x0, max(0, b[1] - 16)), oid, fill=(255, 220, 0))
    photo = draw_compass(photo, pose, fov, REF_W, origin)

    render = render_layered(shell, tgt, eye, look, fov, REF_W)
    render = draw_compass(render, pose, fov, REF_W, origin)

    sheet = Image.new("RGB", (REF_W * 2 + GAP, REF_W + 30), (25, 25, 25))
    sheet.paste(photo, (0, 30))
    sheet.paste(render, (REF_W + GAP, 30))
    d = ImageDraw.Draw(sheet)
    d.text((8, 9), f"REAL room, mirror corrected -- compass at {oid}'s "
                   "footprint (N tinted red)", fill=(255, 255, 60))
    d.text((REF_W + GAP + 8, 9), "RECONSTRUCTION, same camera, isolated -- "
                                 "the IDENTICAL compass", fill=(255, 255, 60))
    out = cdir / "rotation_check" / f"compass_demo_{oid}.png"
    sheet.save(out)
    print(f"[compass] wrote {out}")


if __name__ == "__main__":
    main()
