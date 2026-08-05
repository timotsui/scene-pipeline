"""
ROTATE VIEW (2026-08-04, user: "I am most interested in obj_032 -- let
me see the rotation results"): render one flagged item at chosen yaws
so the user can judge what the fit_rotate_test numbers actually look
like. Target tinted red, everything else at its current pose, two
cameras per angle (whole-room top-down + the item camera). Numbers per
angle re-measured with the fit_check machinery and printed on the
sheet. Display only -- nothing written to the preview.

Run:  python experiments/rotate_view_item.py --scene bedroom_marble \
          --item obj_032 --degs 0,22.5,45
Out:  out/<scene>/compose/fit_rotate_test/<item>_sheet.png
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE.parent / "compose"))
import paths  # noqa: E402
import trimesh  # noqa: E402
from fit_check import (cell_keys, bounds_findings, PITCH,  # noqa: E402
                       CONTACT_CELLS)
from rotation_check import (load_scene, render_frame,  # noqa: E402
                            item_cams)

RES = 640


def yaw_about_m(mesh, center, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    R = np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0],
                  [0, 0, 0, 1]])
    T1 = np.eye(4); T1[:3, 3] = -np.asarray(center)
    T2 = np.eye(4); T2[:3, 3] = np.asarray(center)
    m = mesh.copy()
    m.apply_transform(T2 @ R @ T1)
    return m


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--item", required=True)
    ap.add_argument("--degs", default="0,22.5,45")
    ap.add_argument("--no-tint", action="store_true",
                    help="natural textures instead of the red tint")
    args = ap.parse_args()
    degs = [float(d) for d in args.degs.split(",")]

    cdir, nodes, by_item, shell, wx, wz, room_c = load_scene(args.scene)
    graph = json.loads((paths.scene_dir(args.scene) / "scene_graph.json")
                       .read_text(encoding="utf-8"))
    man = json.loads(paths.manifest(args.scene).read_text(
        encoding="utf-8"))
    r2r = np.array(man["frame"].get("raw_to_render", [1, 1, 1]),
                   np.float32)
    planes = {n["id"]: n["geometry"]["plane"]["value_raw"]
              for n in graph["nodes"] if n["id"].startswith("arch_")}
    fy, cy = sorted((planes["arch_floor"] * r2r[1],
                     planes["arch_ceiling"] * r2r[1]))

    tgt = by_item[args.item]
    others = [m for k, v in by_item.items() if k != args.item
              for m in v]
    ocells = np.unique(np.concatenate(
        [cell_keys(trimesh.util.concatenate(v) if len(v) > 1 else v[0])
         for k, v in by_item.items() if k != args.item]))

    allb = np.vstack([m.bounds for m in tgt])
    lo, hi = allb.min(axis=0), allb.max(axis=0)
    ctr = (lo + hi) / 2
    diag = float(np.linalg.norm(hi - lo))

    # red-tinted copies of the target so it pops in context renders
    def tinted(ms):
        out = []
        for m in ms:
            c = m.copy()
            c.visual = trimesh.visual.ColorVisuals(
                c, vertex_colors=[220, 60, 50, 255])
            out.append(c)
        return out

    eyeA, fovA = item_cams(ctr, diag, room_c)["A"]
    top_eye = np.array([room_c[0] + 0.3, fy + 4.5, room_c[2] + 0.3])

    rows = []
    for deg in degs:
        spun = [yaw_about_m(m, ctr, deg) for m in tgt]
        merged = (trimesh.util.concatenate(spun) if len(spun) > 1
                  else spun[0])
        bf = bounds_findings(merged.vertices, wx, wz, fy, cy)
        oob = sum(f["depth_mm"] for f in bf)
        inter = np.intersect1d(cell_keys(merged), ocells,
                               assume_unique=True)
        clip = max(0, len(inter) - CONTACT_CELLS) * PITCH ** 3 * 1000
        red = spun if args.no_tint else tinted(spun)
        top = render_frame(shell + others + red, top_eye, ctr, 55,
                           res=RES)
        obl = render_frame(shell + others + red, eyeA, ctr, fovA,
                           res=RES)
        label = (f"{deg:+.1f} deg   out-of-bounds "
                 f"{oob:.0f} mm   clip {clip:.1f} L")
        rows.append((label, top, obl))
        print(f"  {label}")

    W, H, PAD, HDR = RES, RES, 8, 34
    sheet = Image.new("RGB", (W * 2 + PAD * 3,
                              (H + HDR + PAD) * len(rows) + PAD),
                      (16, 16, 16))
    d = ImageDraw.Draw(sheet)
    y = PAD
    for label, top, obl in rows:
        d.text((PAD + 4, y + 8), label + "   (left: top-down, "
               "right: item camera; red = " + args.item + ")",
               fill=(255, 220, 120))
        sheet.paste(top, (PAD, y + HDR))
        sheet.paste(obl, (W + PAD * 2, y + HDR))
        y += H + HDR + PAD
    odir = cdir / "fit_rotate_test"
    odir.mkdir(exist_ok=True)
    out_p = odir / (f"{args.item}_sheet"
                    + ("_natural" if args.no_tint else "") + ".png")
    sheet.save(out_p)
    print(f"[rotate-view] wrote {out_p}")


if __name__ == "__main__":
    main()
