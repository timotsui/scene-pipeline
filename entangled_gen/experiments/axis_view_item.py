"""
AXIS VIEW (2026-08-04, user: "show me in visual what is the axis of
the shelf"): one top-down render of an item in place, overlaid with

  YELLOW = the mesh's footprint rectangle (its axis-aligned extents)
           + an arrow along its detected LONG axis
  CYAN   = the fit box's footprint rectangle + its long-axis arrow

plus the measured extents and the 1.2x rule verdict, so the axis
detection is judgeable in one look. Display only.

Run:  python experiments/axis_view_item.py --scene bedroom_marble \
          --item obj_032
Out:  out/<scene>/compose/fit_rotate_test/<item>_axis.png
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "compose"))
import paths  # noqa: E402
import trimesh  # noqa: E402
from rotation_check import (load_scene, render_frame, project)  # noqa: E402
from place import look_at_pose  # noqa: E402

RES = 960
ELONG = 1.2


def font(sz):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/arial.ttf", sz)
    except Exception:
        return ImageFont.load_default()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--item", required=True)
    args = ap.parse_args()

    cdir, nodes, by_item, shell, wx, wz, room_c = load_scene(args.scene)
    fp = json.loads((cdir / "fitted_preview.json").read_text(
        encoding="utf-8"))
    pl = next(p for p in fp["placed"] if p["id"] == args.item)
    man = json.loads(paths.manifest(args.scene).read_text(
        encoding="utf-8"))
    r2r = np.array(man["frame"].get("raw_to_render", [1, 1, 1]),
                   np.float32)
    blo = np.asarray(pl["fit_box"]["aabb_min"], np.float32) * r2r
    bhi = np.asarray(pl["fit_box"]["aabb_max"], np.float32) * r2r
    blo, bhi = np.minimum(blo, bhi), np.maximum(blo, bhi)

    tgt = by_item[args.item]
    allb = np.vstack([m.bounds for m in tgt])
    mlo, mhi = allb.min(axis=0), allb.max(axis=0)

    red = []
    for m in tgt:
        c = m.copy()
        c.visual = trimesh.visual.ColorVisuals(
            c, vertex_colors=[220, 60, 50, 255])
        red.append(c)
    others = [m for k, v in by_item.items() if k != args.item
              for m in v]

    ctr = (np.minimum(mlo, blo) + np.maximum(mhi, bhi)) / 2
    span = float(max(np.maximum(mhi, bhi)[0] - np.minimum(mlo, blo)[0],
                     np.maximum(mhi, bhi)[2] - np.minimum(mlo, blo)[2]))
    dist = 3.5
    fov = float(np.degrees(2 * np.arctan((span / 2 + 0.5) / dist)))
    # offset ONLY along +z so the camera's projected up = world -z and
    # image axes stay parallel to the room's x/z (a diagonal offset
    # rolls the whole view and every rectangle reads slanted)
    eye = np.array([ctr[0], ctr[1] + dist, ctr[2] + 0.4])
    look = np.array([ctr[0], ctr[1], ctr[2]])
    img = render_frame(shell + others + red, eye, look, fov,
                       res=RES).convert("RGB")
    pose = look_at_pose(eye, look, [0, 1, 0])
    d = ImageDraw.Draw(img)

    def rect(lo3, hi3, y, col, w):
        pts = [(lo3[0], y, lo3[2]), (hi3[0], y, lo3[2]),
               (hi3[0], y, hi3[2]), (lo3[0], y, hi3[2])]
        uv = project(pose, fov, RES, pts)
        if len(uv) == 4:
            d.polygon(uv, outline=col, width=w)
        return uv

    def arrow(p0, p1, col, w, label=None, lab_off=(6, -22)):
        uv = project(pose, fov, RES, [p0, p1])
        if len(uv) != 2:
            return
        (x0, y0), (x1, y1) = uv
        d.line([x0, y0, x1, y1], fill=col, width=w)
        v = np.array([x1 - x0, y1 - y0], float)
        L = np.linalg.norm(v)
        if L > 1e-3:
            v /= L
            n = np.array([-v[1], v[0]])
            for tip, sgn in ((np.array([x1, y1]), -1),
                             (np.array([x0, y0]), 1)):
                a = tip + sgn * v * 16 + n * 8
                b = tip + sgn * v * 16 - n * 8
                d.polygon([tuple(tip), tuple(a), tuple(b)], fill=col)
        if label:
            d.text(((x0 + x1) / 2 + lab_off[0],
                    (y0 + y1) / 2 + lab_off[1]),
                   label, fill=col, font=font(22), stroke_width=2,
                   stroke_fill=(0, 0, 0))

    ytop = mhi[1] + 0.02
    mc = (mlo + mhi) / 2
    bc = (blo + bhi) / 2
    mex, mez = mhi[0] - mlo[0], mhi[2] - mlo[2]
    bex, bez = bhi[0] - blo[0], bhi[2] - blo[2]

    rect(mlo, mhi, ytop, (255, 220, 60), 5)
    rect(blo, bhi, ytop + 0.01, (60, 220, 255), 5)

    m_long = "x" if mex > mez * ELONG else ("z" if mez > mex * ELONG
                                            else None)
    b_long = "x" if bex > bez * ELONG else ("z" if bez > bex * ELONG
                                            else None)
    # long-axis arrows through the centers, on top of the footprints
    if m_long == "x" or (m_long is None and mex >= mez):
        arrow((mlo[0], ytop, mc[2]), (mhi[0], ytop, mc[2]),
              (255, 220, 60), 6, f"mesh {'LONG ' if m_long else ''}x "
              f"{mex:.2f} m")
    if m_long == "z" or (m_long is None and mez > mex):
        arrow((mc[0], ytop, mlo[2]), (mc[0], ytop, mhi[2]),
              (255, 220, 60), 6, f"mesh {'LONG ' if m_long else ''}z "
              f"{mez:.2f} m", lab_off=(10, 0))
    if b_long == "x" or (b_long is None and bex >= bez):
        arrow((blo[0], ytop + 0.01, bc[2]), (bhi[0], ytop + 0.01, bc[2]),
              (60, 220, 255), 6, f"box {'LONG ' if b_long else ''}x "
              f"{bex:.2f} m")
    if b_long == "z" or (b_long is None and bez > bex):
        arrow((bc[0], ytop + 0.01, blo[2]), (bc[0], ytop + 0.01, bhi[2]),
              (60, 220, 255), 6, f"box {'LONG ' if b_long else ''}z "
              f"{bez:.2f} m", lab_off=(10, 20))

    hdr = [
        f"{args.item} {pl['name']} -- TOP-DOWN. yellow = mesh "
        f"footprint, cyan = fit box",
        f"mesh {mex:.2f} x {mez:.2f} m  ratio "
        f"{max(mex, mez) / min(mex, mez):.2f} "
        f"-> long axis {m_long or 'none (near-square)'}   |   box "
        f"{bex:.2f} x {bez:.2f} m  ratio "
        f"{max(bex, bez) / min(bex, bez):.2f} "
        f"-> long axis {b_long or 'none'}",
        f"aligned: {('YES -- both ' + m_long) if m_long and m_long == b_long else 'no/na'}"
        f"   |   short-axis overhang: mesh "
        f"{min(mex, mez):.2f} m vs box {min(bex, bez):.2f} m",
    ]
    y = 8
    for line in hdr:
        d.text((10, y), line, fill=(255, 255, 255), font=font(20),
               stroke_width=2, stroke_fill=(0, 0, 0))
        y += 27

    odir = cdir / "fit_rotate_test"
    odir.mkdir(exist_ok=True)
    out_p = odir / f"{args.item}_axis.png"
    img.save(out_p)
    print(f"[axis-view] wrote {out_p}")


if __name__ == "__main__":
    main()
