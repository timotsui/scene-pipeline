"""
Depth-lift: 2D detections+masks -> 3D object boxes -> scene_manifest.json.

The missing middle of the extraction pipeline (README status: "2D segmentation
-> lift -> scene_manifest.json"). Consumes what already exists on disk:

  out/<scene>/views/gpu_*.json      camera sidecars from week5 shot.py (pos/look/up/fov/res)
  out/<scene>/seg/<view>_masks.npy  SAM masks, (n, H, W) bool, SAME ORDER as detections.json
  out/<scene>/seg/detections.json   GroundingDINO detections per view

Depth comes from a vectorized point z-buffer over the splat means (the week5
render_view python loop is minutes/view at 900x900; this is seconds and depth
is all we need — README: "splat-transform for RGB, numpy renderer for
depth/unproject only"). Per-mask depths are median/IQR-trimmed so SAM edge
bleed and splat floaters fall out, then unprojected to world and merged
across views by label+3D-overlap.

Run:  python lift_views.py --scene playroom
Outputs: out/<scene>/scene_manifest.json + out/<scene>/seg/manifest_plan_<scene>.png
"""
import argparse, json
from collections import defaultdict
from pathlib import Path
import numpy as np

import paths

HERE = Path(__file__).parent
r3 = paths.load_r3()

# collapse GroundingDINO near-synonyms before cross-view merging
SYNONYMS = {"carpet": "rug", "bookshelf": "shelf", "ceiling light": "lamp",
            "stuffed animal": "toy", "couch": "sofa", "tv": "television",
            "bedside table": "nightstand", "closet": "wardrobe"}

MIN_MASK_PX = 400          # ignore slivers
MAX_LIFT_PX = 30000        # subsample cap per mask
MERGE_IOU = 0.20           # 3D aabb IoU to merge same-label detections
SCORE_MIN = 0.35           # drop weak detections before lifting


def depth_zbuffer(xyz, cam, near=0.2):
    """Nearest-surface depth via point splat of the gaussian means, 3x3 footprint."""
    u, v, z = cam.project(xyz)
    ok = (z > near) & np.isfinite(u) & np.isfinite(v)
    u, v, z = u[ok], v[ok], z[ok]
    ui, vi = np.round(u).astype(np.int64), np.round(v).astype(np.int64)
    depth = np.full((cam.h, cam.w), np.inf, np.float32)
    for dy in (-1, 0, 1):
        for dx in (-1, 0, 1):
            uu, vv = ui + dx, vi + dy
            inb = (uu >= 0) & (uu < cam.w) & (vv >= 0) & (vv < cam.h)
            np.minimum.at(depth, (vv[inb], uu[inb]), z[inb])
    return depth


def unproject_px(cam, us, vs, ds):
    """Vectorized pixel->world (r3.unproject is scalar-shaped)."""
    x = (us - cam.cx) / cam.f * ds
    y = -(vs - cam.cy) / cam.f * ds
    pts_cam = np.stack([x, y, ds], axis=1).astype(np.float32)
    return cam.pos + pts_cam @ cam.R


def aabb_of(pts):
    lo = np.percentile(pts, 2, axis=0)
    hi = np.percentile(pts, 98, axis=0)
    return lo, hi


# Axis-sign hypotheses relating the RAW ply frame to the RENDER frame (what the
# shot.py webps, SuperSplat, and the generator pano show). History: a 2-hypothesis
# calibration (as-is vs x-mirror) picked mirX 2026-07-05, but the raw-space viewer
# showed gen plys upside-down-but-not-mirrored; the 4-hypothesis correlation
# (debug_frame_hypotheses.py) has rot180 (-x,-y,+z; standard 3DGS/COLMAP y-down)
# winning every view on bedroom_s1 (0.91-0.96) and 8/10 views on realplayroom.
FRAME_HYPS = [("identity", np.array([1.0, 1.0, 1.0], np.float32)),
              ("mirX",     np.array([-1.0, 1.0, 1.0], np.float32)),
              ("mirY",     np.array([1.0, -1.0, 1.0], np.float32)),
              ("rot180",   np.array([-1.0, -1.0, 1.0], np.float32))]


def detect_frame(xyz, rgb, views_dir, dets_all, size=192):
    """Per-scene raw->render axis-sign calibration: color z-buffer EVERY detection
    view under each hypothesis and correlate against the actual webp; mean across
    views picks the winner. (Single-view calibration got fooled by a vertically
    quasi-uniform yaw000 close-up — handoff 2026-07-05B.)
    Returns (sign vector, hypothesis name, {name: mean corr}, n_views)."""
    from PIL import Image
    views = [v for v in sorted(dets_all)
             if (views_dir / f"{v}.webp").exists()
             and (views_dir / f"{v}.json").exists()]
    if not views:
        return FRAME_HYPS[0][1], "identity", {}, 0
    sums = {name: 0.0 for name, _ in FRAME_HYPS}
    for view in views:
        meta = json.loads((views_dir / f"{view}.json").read_text())
        cam = r3.Cam([float(t) for t in meta["cam"].split(",")],
                     [float(t) for t in meta["look"].split(",")],
                     [float(t) for t in meta["up"].split(",")],
                     float(meta["fov"]), size, size)
        ref = Image.open(views_dir / f"{view}.webp").convert("L").resize((size, size))
        ref = np.asarray(ref, np.float32)
        ref = (ref - ref.mean()) / (ref.std() + 1e-6)
        for name, sgn in FRAME_HYPS:
            u, v, z = cam.project(xyz * sgn)
            ok = (z > 0.2) & np.isfinite(u) & np.isfinite(v)
            ui = np.round(u[ok]).astype(np.int64)
            vi = np.round(v[ok]).astype(np.int64)
            order = np.argsort(-z[ok])           # painter: near overwrites far
            img = np.zeros((size, size), np.float32)
            uu, vv = ui[order], vi[order]
            inb = (uu >= 0) & (uu < size) & (vv >= 0) & (vv < size)
            img[vv[inb], uu[inb]] = rgb[ok][order][inb].mean(axis=1)
            img = (img - img.mean()) / (img.std() + 1e-6)
            sums[name] += float((img * ref).mean())
    means = {n: s / len(views) for n, s in sums.items()}
    win = max(means, key=means.get)
    sgn = dict(FRAME_HYPS)[win]
    return sgn, win, means, len(views)


def sign_box(lo, hi, sgn):
    """render-space aabb -> RAW-space aabb under the diagonal sign transform
    (self-inverse; negated axes swap their lo/hi corners)."""
    lo2, hi2 = lo * sgn, hi * sgn
    return np.minimum(lo2, hi2), np.maximum(lo2, hi2)


def iou3d(lo1, hi1, lo2, hi2):
    ilo, ihi = np.maximum(lo1, lo2), np.minimum(hi1, hi2)
    if np.any(ihi <= ilo):
        return 0.0
    inter = np.prod(ihi - ilo)
    v1, v2 = np.prod(hi1 - lo1), np.prod(hi2 - lo2)
    return float(inter / (v1 + v2 - inter + 1e-9))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="playroom")
    ap.add_argument("--views-dir", default="")
    ap.add_argument("--seg-dir", default="")
    ap.add_argument("--ply", default="")
    args = ap.parse_args()

    sc = args.scene
    views_dir = Path(args.views_dir) if args.views_dir else paths.views_dir(sc)
    seg_dir = Path(args.seg_dir) if args.seg_dir else paths.seg_dir(sc)
    ply = Path(args.ply) if args.ply else paths.ply(sc)

    dets_all = json.loads((seg_dir / "detections.json").read_text())

    print(f"[lift] loading splat {ply.name} ...", flush=True)
    xyz, rgb, _alpha, _radius = r3.load_splat(str(ply), opacity_min=0.3)
    print(f"[lift] {len(xyz):,} gaussians (opacity>=0.3)", flush=True)

    # per-scene raw->render frame calibration against the actual webp renders;
    # from here on EVERYTHING (depth, boxes, manifest, plan) lives in the RENDER
    # frame (= webp / SuperSplat / generator-pano space, +y up).
    sgn, hyp, corrs, ncal = detect_frame(xyz, rgb, views_dir, dets_all)
    print(f"[lift] frame calib ({ncal} views): "
          + "  ".join(f"{n}={c:.3f}" for n, c in corrs.items())
          + f"  -> {hyp}", flush=True)
    xyz_l = xyz * sgn

    # physical floor/ceiling, reported in RAW coords: in the render frame floor is
    # low y; map back through the y sign. Under rot180 this makes floor_y > ceiling_y
    # in the manifest — correct for the raw frame, where physical up is -y.
    floor_y_r = float(np.percentile(xyz_l[:, 1], 1))
    ceil_y_r = float(np.percentile(xyz_l[:, 1], 99))
    floor_y, ceil_y = float(sgn[1]) * floor_y_r, float(sgn[1]) * ceil_y_r

    # ---- lift every detection ----
    lifted = []  # {label, score, view, lo, hi, pts}
    for view, dets in dets_all.items():
        maskf = seg_dir / f"{view}_masks.npy"
        metaf = views_dir / f"{view}.json"
        if not maskf.exists() or not metaf.exists():
            print(f"[lift] {view}: missing masks or sidecar, skipping", flush=True)
            continue
        meta = json.loads(metaf.read_text())
        w, h = (int(t) for t in meta["res"].split("x"))
        cam = r3.Cam([float(t) for t in meta["cam"].split(",")],
                     [float(t) for t in meta["look"].split(",")],
                     [float(t) for t in meta["up"].split(",")],
                     float(meta["fov"]), w, h)
        depth = depth_zbuffer(xyz_l, cam, near=float(meta.get("near", 0.2)))
        cov = np.isfinite(depth).mean()
        masks = np.load(maskf)
        print(f"[lift] {view}: depth coverage {cov:.0%}, {len(dets)} dets", flush=True)

        for det, mask in zip(dets, masks):
            if det["score"] < SCORE_MIN:
                continue
            label = SYNONYMS.get(det["label"], det["label"])
            valid = mask & np.isfinite(depth)
            if valid.sum() < MIN_MASK_PX:
                continue
            vs, us = np.nonzero(valid)
            ds = depth[vs, us]
            med = np.median(ds)
            iqr = np.subtract(*np.percentile(ds, [75, 25]))
            keep = np.abs(ds - med) <= max(0.4, 2.0 * iqr)
            us, vs, ds = us[keep], vs[keep], ds[keep]
            if len(ds) < MIN_MASK_PX:
                continue
            if len(ds) > MAX_LIFT_PX:
                sel = np.random.default_rng(0).choice(len(ds), MAX_LIFT_PX, replace=False)
                us, vs, ds = us[sel], vs[sel], ds[sel]
            pts = unproject_px(cam, us.astype(np.float32), vs.astype(np.float32), ds)
            lo, hi = aabb_of(pts)
            lifted.append({"label": label, "score": det["score"], "view": view,
                           "lo": lo, "hi": hi, "pts": pts})

    print(f"[lift] {len(lifted)} lifted detections", flush=True)

    # ---- greedy cross-view merge by label + 3D overlap ----
    used = [False] * len(lifted)
    objects = []
    render_boxes = []   # parallel to objects, render space (for overlay drawing)
    order = sorted(range(len(lifted)), key=lambda i: -lifted[i]["score"])
    for i in order:
        if used[i]:
            continue
        grp = [lifted[i]]
        used[i] = True
        changed = True
        while changed:
            changed = False
            glo = np.min([g["lo"] for g in grp], axis=0)
            ghi = np.max([g["hi"] for g in grp], axis=0)
            for j in order:
                if used[j] or lifted[j]["label"] != lifted[i]["label"]:
                    continue
                if iou3d(glo, ghi, lifted[j]["lo"], lifted[j]["hi"]) > MERGE_IOU:
                    grp.append(lifted[j])
                    used[j] = True
                    changed = True
        pts = np.concatenate([g["pts"] for g in grp])
        lo_r, hi_r = aabb_of(pts)                       # render space (webp content)
        render_boxes.append((lo_r, hi_r))               # for the overlay projection
        lo, hi = sign_box(lo_r, hi_r, sgn)              # manifest: RAW ply space
        objects.append({
            "id": f"obj_{len(objects):03d}",
            "label": lifted[i]["label"],
            "score": round(max(g["score"] for g in grp), 3),
            "aabb_min": [round(float(v), 3) for v in lo],
            "aabb_max": [round(float(v), 3) for v in hi],
            "center": [round(float(v), 3) for v in (lo + hi) / 2],
            "size": [round(float(v), 3) for v in hi - lo],
            "n_points": int(len(pts)),
            "views": sorted({g["view"] for g in grp}),
            "n_detections": len(grp),
        })

    manifest = {
        "scene": sc,
        "source_ply": str(ply),
        "frame": {"space": "raw",
                  "up": [0.0, float(sgn[1]), 0.0],
                  "floor_y": round(floor_y, 3),
                  "ceiling_y": round(ceil_y, 3),
                  "extent_p1": [round(float(v), 3) for v in np.percentile(xyz, 1, axis=0)],
                  "extent_p99": [round(float(v), 3) for v in np.percentile(xyz, 99, axis=0)],
                  "raw_to_render": [float(s) for s in sgn],
                  "frame_hypothesis": hyp,
                  "frame_calib_corr": {n: round(c, 3) for n, c in corrs.items()},
                  "calib_views": ncal,
                  "note": "camera rig at origin; ALL coords in RAW ply space. Physical "
                          "up is frame.up (-y under rot180: floor_y > ceiling_y "
                          "numerically). webp/render space = coords * raw_to_render "
                          "(elementwise, self-inverse). User-verified 2026-07-05 via "
                          "cube8.ply: upright world = rot180-about-Z of raw."},
        "views_used": sorted(dets_all.keys()),
        "objects": objects,
    }
    outf = paths.manifest(sc)
    outf.write_text(json.dumps(manifest, indent=2))
    print(f"[lift] wrote {outf} ({len(objects)} objects)", flush=True)
    for o in objects:
        print(f'  {o["id"]} {o["label"]:14s} score={o["score"]:.2f} '
              f'size={o["size"]} center={o["center"]} views={len(o["views"])}', flush=True)

    # ---- project merged boxes back into the RGB views (the real eyeball check:
    # a box that lands on the bed in the photoreal render needs no interpretation) ----
    from PIL import Image, ImageDraw
    PALETTE = [(230, 60, 60), (60, 130, 230), (60, 190, 90), (240, 160, 40),
               (170, 90, 230), (240, 90, 180), (90, 210, 210), (160, 160, 60),
               (250, 250, 250), (140, 90, 50)]
    for view in dets_all:
        imgf = views_dir / f"{view}.webp"
        metaf = views_dir / f"{view}.json"
        if not imgf.exists() or not metaf.exists():
            continue
        meta = json.loads(metaf.read_text())
        w, h = (int(t) for t in meta["res"].split("x"))
        cam = r3.Cam([float(t) for t in meta["cam"].split(",")],
                     [float(t) for t in meta["look"].split(",")],
                     [float(t) for t in meta["up"].split(",")],
                     float(meta["fov"]), w, h)
        im = Image.open(imgf).convert("RGB")
        dr = ImageDraw.Draw(im)
        for k, o in enumerate(objects):
            if view not in o["views"]:
                continue
            lo, hi = render_boxes[k]   # render space = the space the webp content is in
            corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                                for y in (lo[1], hi[1]) for z in (lo[2], hi[2])],
                               np.float32)
            u, v, z = cam.project(corners)
            if np.median(z) < 0.2:
                continue
            ok = z > 0.2
            c = PALETTE[k % len(PALETTE)]
            # AABB edges = corner pairs differing in exactly one axis bit
            for a in range(8):
                for b in range(a + 1, 8):
                    if bin(a ^ b).count("1") == 1 and ok[a] and ok[b]:
                        dr.line([(u[a], v[a]), (u[b], v[b])], fill=c, width=2)
            uu, vv = u[ok], v[ok]
            dr.text((float(np.clip(uu.min(), 2, w - 120)),
                     float(np.clip(vv.min() - 14, 2, h - 14))),
                    f'{o["id"]} {o["label"]}', fill=c)
        ovf = seg_dir / f"manifest_overlay_{view}.png"
        im.save(ovf)
        print(f"[lift] wrote {ovf}", flush=True)

    # ---- top-down plan view for eyeballing ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    # band between physical floor and ceiling, frame-agnostic (raw may have
    # floor_y > ceiling_y since up can be -y)
    ylo, yhi = sorted((floor_y, ceil_y))
    mid = (xyz[:, 1] > ylo + 0.1) & (xyz[:, 1] < yhi - 0.1)
    fig, ax = plt.subplots(figsize=(9, 9))
    hb = ax.hist2d(xyz[mid, 0], xyz[mid, 2], bins=220, cmap="Greys",
                   norm=matplotlib.colors.LogNorm())
    colors = plt.cm.tab10.colors
    for k, o in enumerate(objects):
        lo, hi = o["aabb_min"], o["aabb_max"]
        c = colors[k % 10]
        ax.add_patch(Rectangle((lo[0], lo[2]), hi[0] - lo[0], hi[2] - lo[2],
                               fill=False, edgecolor=c, linewidth=2))
        ax.text(lo[0], lo[2] - 0.05, f'{o["id"]} {o["label"]}', color=c, fontsize=8)
    ax.plot(0, 0, "r*", markersize=14)  # camera rig
    ax.set_aspect("equal")
    # +Z DOWN the image, matching the viewer grid, GUIDE ASCII grid, envelope
    # heatmaps and proposal_plan (matplotlib default +z-up is their mirror).
    ax.invert_yaxis()
    ax.set_xlabel("x"); ax.set_ylabel("z (down)")
    ax.set_title(f"{sc}: lifted objects, top-down (star = rig origin)")
    planf = seg_dir / f"manifest_plan_{sc}.png"
    fig.tight_layout(); fig.savefig(planf, dpi=110)
    print(f"[lift] wrote {planf}", flush=True)


if __name__ == "__main__":
    main()
