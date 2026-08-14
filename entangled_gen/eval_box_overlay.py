"""Measured-box overlay on the eval product shot — the library-gap figure.

Draws the scene graph's measured boxes (current layer, object nodes only)
as wireframes over the existing <scene>_ours_persp.png product shot, using
exactly eval_renders' camera math, so the paper can show visually that the
SLOTS are measured and right while the assets inside them are the best the
library offered (EVAL_RESULTS_2026-08-13 §5b: 56–80% of placements had no
correctly-sized candidate).

Compute-only: reads the graph, the shell and the already-rendered PNG.
Nothing is re-run. Output: out/eval_renders/<scene>_ours_persp_boxes.png.

Run:  python eval_box_overlay.py --scenes natural_living,sunlit_office
"""
import argparse
import json
import math

import numpy as np
from PIL import Image, ImageDraw

import paths
import eval_renders as er

BOX_RGBA = (255, 140, 0, 230)      # orange, readable on the render
LINE_W = 3

#: the 12 edges of a box given the 8 corners ordered by
#: (min/max x) x (min/max y) x (min/max z) bit pattern
EDGES = [(0, 1), (2, 3), (4, 5), (6, 7),
         (0, 2), (1, 3), (4, 6), (5, 7),
         (0, 4), (1, 5), (2, 6), (3, 7)]


def object_boxes(scene):
    """Current-layer object nodes' raw-frame AABBs (arch nodes skipped)."""
    p = paths.scene_dir(scene) / "scene_graph.json"
    g = json.loads(p.read_text(encoding="utf-8"))
    layer = g["layer"]["canonical"]
    out = []
    for n in g[layer]["nodes"]:
        nid = str(n.get("id", ""))
        if nid.startswith("arch_") or n.get("source") == "envelope":
            continue
        geo = n.get("geometry") or {}
        lo, hi = geo.get("aabb_min"), geo.get("aabb_max")
        if lo and hi:
            out.append((nid, np.array(lo, float), np.array(hi, float)))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", required=True)
    a = ap.parse_args()
    for scene in [s.strip() for s in a.scenes.split(",") if s.strip()]:
        base = er.OUT_DIR / f"{scene}_ours_persp.png"
        if not base.exists():
            print(f"[box_overlay] {scene}: no product shot at {base}; skipped")
            continue
        _, poly, _ = er.ours_scene(scene)
        boundary = er.clean_boundary(poly)
        (cx, cy), half = er.frame_of(boundary)
        t = math.tan(math.radians(er.PERSP_FOV_DEG) / 2)
        half = half + er.WALL_H * t           # eval_renders' persp frame rule
        eye_h = half / t

        M = er._plan_matrix(scene)

        def project(p_raw):
            p = M @ np.append(p_raw, 1.0)
            d = eye_h - p[2]
            if d <= 0.05:
                return None
            x_ndc = (p[0] - cx) / (d * t)
            y_ndc = (p[1] - cy) / (d * t)
            return ((x_ndc + 1) / 2 * er.RES,
                    (1 - (y_ndc + 1) / 2) * er.RES)

        img = Image.open(base).convert("RGBA")
        lay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        dr = ImageDraw.Draw(lay)
        n_drawn = 0
        for nid, lo, hi in object_boxes(scene):
            corners = [np.array([x, y, z]) for x in (lo[0], hi[0])
                       for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
            px = [project(c) for c in corners]
            if any(p is None for p in px):
                continue
            for i, j in EDGES:
                dr.line([px[i], px[j]], fill=BOX_RGBA, width=LINE_W)
            n_drawn += 1
        out = Image.alpha_composite(img, lay).convert("RGB")
        f = er.OUT_DIR / f"{scene}_ours_persp_boxes.png"
        out.save(f)
        print(f"[box_overlay] {f.name}: {n_drawn} boxes drawn")


if __name__ == "__main__":
    main()
