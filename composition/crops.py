"""Per-box view crops from the real RGB renders (shared compute helper).

make_crops(sc, boxes): for each manifest box, pick the view where its
projected 3D AABB covers the most on-image area and write two crops into
package/review_crops/: <id>_clean.png (tight, no drawn lines — the CLIP
relevance query) and <id>.png (padded, green box edges — the human view).

Consumers: review_server.py (C4 viewer) and relevance.py (C3 CLIP scoring).
Moved out of review_server.py 2026-07-23 so the compute path does not import
the HTTP server module.
"""
import json

import numpy as np
from PIL import Image, ImageDraw

import comp_paths
from comp_paths import paths

PAD = 0.30          # crop padding as a fraction of the projected rect


def _views_meta(sc):
    out = {}
    for metaf in sorted(paths.views_dir(sc).glob("gpu_yaw*.json")):
        meta = json.loads(metaf.read_text())
        imgf = paths.views_dir(sc) / meta["file"]
        if imgf.exists():
            out[metaf.stem] = (meta, imgf)
    return out


def _project_box(cam, lo, hi, r2r):
    a = np.asarray(lo, np.float32) * r2r
    b = np.asarray(hi, np.float32) * r2r
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                        for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], np.float32)
    u, v, z = cam.project(corners)
    return u, v, z


def make_crops(sc, boxes, force=False):
    r3 = comp_paths.load_r3()
    man = json.loads(paths.manifest(sc).read_text())
    r2r = np.array(man["frame"].get("raw_to_render", [1, 1, 1]), np.float32)
    views = _views_meta(sc)
    cams, imgs = {}, {}
    for stem, (meta, imgf) in views.items():
        w, h = (int(t) for t in meta["res"].split("x"))
        cams[stem] = r3.Cam([float(t) for t in meta["cam"].split(",")],
                            [float(t) for t in meta["look"].split(",")],
                            [float(t) for t in meta["up"].split(",")],
                            float(meta["fov"]), w, h)
    cdir = paths.package_dir(sc) / "review_crops"
    cdir.mkdir(exist_ok=True)
    for b in boxes:
        outf = cdir / f"{b['id']}.png"
        cleanf = cdir / f"{b['id']}_clean.png"
        if outf.exists() and cleanf.exists() and not force:
            continue
        # pick the view where the projected box covers the most on-image area
        best = None
        for stem in (b.get("views") or list(views)):
            if stem not in cams:
                continue
            cam = cams[stem]
            u, v, z = _project_box(cam, b["aabb_min"], b["aabb_max"], r2r)
            ok = z > 0.2
            if ok.sum() < 4:
                continue
            x0 = np.clip(u[ok].min(), 0, cam.w); x1 = np.clip(u[ok].max(), 0, cam.w)
            y0 = np.clip(v[ok].min(), 0, cam.h); y1 = np.clip(v[ok].max(), 0, cam.h)
            area = (x1 - x0) * (y1 - y0)
            if best is None or area > best[0]:
                best = (area, stem, (u, v, z))
        if best is None:
            print(f"[review] {b['id']}: no view sees the box", flush=True)
            continue
        _, stem, (u, v, z) = best
        cam = cams[stem]
        if stem not in imgs:
            imgs[stem] = Image.open(views[stem][1]).convert("RGB")
        ok = z > 0.2
        # clean tight crop first (no drawn lines) — the CLIP relevance query
        x0, x1 = float(u[ok].min()), float(u[ok].max())
        y0, y1 = float(v[ok].min()), float(v[ok].max())
        pxc, pyc = (x1 - x0) * 0.08 + 6, (y1 - y0) * 0.08 + 6
        imgs[stem].crop((int(max(0, x0 - pxc)), int(max(0, y0 - pyc)),
                         int(min(cam.w, x1 + pxc)),
                         int(min(cam.h, y1 + pyc)))).save(cleanf)
        im = imgs[stem].copy()
        dr = ImageDraw.Draw(im)
        for i in range(8):
            for j in range(i + 1, 8):
                if bin(i ^ j).count("1") == 1 and ok[i] and ok[j]:
                    dr.line([(u[i], v[i]), (u[j], v[j])],
                            fill=(40, 230, 90), width=3)
        x0, x1 = float(u[ok].min()), float(u[ok].max())
        y0, y1 = float(v[ok].min()), float(v[ok].max())
        px, py = (x1 - x0) * PAD + 30, (y1 - y0) * PAD + 30
        rect = (int(max(0, x0 - px)), int(max(0, y0 - py)),
                int(min(cam.w, x1 + px)), int(min(cam.h, y1 + py)))
        im.crop(rect).save(outf)
    print(f"[review] crops in {cdir}", flush=True)
