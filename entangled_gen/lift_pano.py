"""Module 3 of the week8 object-ID pipeline: LIFT — 2D masks -> metric 3D
objects, by ray-casting against the bundle's collider mesh.

Consumes what modules 1-2 left on disk (out/<scene>/):
  pano_crops/<view>.json        crop camera sidecars (all cams at origin)
  seg_pano/detections.json      GroundingDINO detections per crop
  seg_pano/<view>_masks.npy     SAM masks, SAME ORDER as detections

3D comes from geometry, not estimation: every mask pixel is a ray from the
pano camera (origin); rays are intersected with the collider mesh (embree).
Pose contract (A2, user-verified 2026-07-07): p_pano = diag(1,-1,1) @ p_glb
(the glb is mirrored through the ground plane), camera at origin, zero yaw.

Detections are canonicalized (module-1 labels), blob-filtered, depth-trimmed
(SAM edge bleed hits the wall BEHIND the object), then merged across crops by
label + 3D IoU (same convention as lift_views.py).

Outputs:
  out/<scene>/scene_manifest_pano.json      (frame: "pano" — NOT the splat
        raw frame; the mesh<->splat offset is A2b, still unverified. The
        render-path scene_manifest.json is deliberately left untouched
        for the C2 old-vs-new comparison.)
  out/<scene>/seg_pano/manifest_overlay_pano.png   3D boxes drawn on the pano
  out/<scene>/seg_pano/manifest_plan_pano.png      top-down plan vs mesh

  python lift_pano.py --scene bedroom_marble
"""
import argparse, json
from pathlib import Path
import numpy as np

import paths
from vocab_from_prompt import (canonicalize, bundle_prompt_file,
                               extract_vocab, expand_terms)
from crop_pano import crop_dirs

MIRROR_Y = np.diag([1.0, -1.0, 1.0])   # glb -> pano frame (A2)
SCORE_MIN = 0.35
MIN_HITS = 300          # a lifted object needs at least this many mesh hits
MAX_LIFT_PX = 30000     # subsample cap per mask (embree is fast; keeps pts sane)
MERGE_IOU = 0.20        # 3D aabb IoU to merge same-label detections
MAX_MASK_FRAC = 0.55    # drop region-blob detections ("wall art" whole walls)
SKIP_LABELS = {"ladder"}   # vocab artifacts that survived extraction


def aabb_of(pts):
    lo = np.percentile(pts, 2, axis=0)
    hi = np.percentile(pts, 98, axis=0)
    return lo, hi


def iou3d(lo1, hi1, lo2, hi2):
    ilo, ihi = np.maximum(lo1, lo2), np.minimum(hi1, hi2)
    if np.any(ihi <= ilo):
        return 0.0
    inter = np.prod(ihi - ilo)
    v1, v2 = np.prod(hi1 - lo1), np.prod(hi2 - lo2)
    return float(inter / (v1 + v2 - inter + 1e-9))


def dir_to_equirect(dirs, W, H):
    theta = np.arctan2(dirs[:, 0], dirs[:, 2])
    phi = np.arcsin(np.clip(dirs[:, 1], -1, 1))
    u = (theta / (2 * np.pi) + 0.5) * W
    v = (0.5 - phi / np.pi) * H
    return u, v


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    a = ap.parse_args()
    sc = a.scene

    crops_dir = paths.pano_crops_dir(sc)
    seg = paths.seg_pano_dir(sc)
    dets_all = json.loads((seg / "detections.json").read_text())

    # module-1 vocabulary (prompt + tag artifacts on disk) — canonicalize()
    # needs it to collapse GroundingDINO token-concat labels ("side table desk")
    vocab = expand_terms(extract_vocab(
        bundle_prompt_file(sc).read_text(encoding="utf-8")))
    tagsf = seg / "tags.json"
    if tagsf.exists():
        vocab += [t for t in json.loads(tagsf.read_text()).get("kept", {})
                  if t not in vocab]

    # ---- mesh (glb -> pano frame) + ray engine ----
    import trimesh
    bundle = bundle_prompt_file(sc).parent
    glbf = next(bundle.glob("*_collider.glb"))
    scene3d = trimesh.load(str(glbf))
    mesh = scene3d.to_mesh() if isinstance(scene3d, trimesh.Scene) else scene3d
    T = np.eye(4); T[:3, :3] = MIRROR_Y
    mesh.apply_transform(T)
    from trimesh.ray.ray_pyembree import RayMeshIntersector
    ray = RayMeshIntersector(mesh)
    mlo, mhi = mesh.bounds
    floor_y, ceil_y = float(mlo[1]), float(mhi[1])
    print(f"[lift] mesh {len(mesh.faces):,} faces (pano frame), "
          f"floor {floor_y:.2f} ceil {ceil_y:.2f}", flush=True)

    r3 = paths.load_r3()
    rng = np.random.default_rng(0)

    # ---- lift every detection ----
    lifted = []   # {label, score, view, lo, hi, pts}
    n_blob = n_weak = n_thin = 0
    for view, dets in sorted(dets_all.items()):
        maskf = seg / f"{view}_masks.npy"
        sidef = crops_dir / f"{view}.json"
        if not maskf.exists() or not sidef.exists() or not dets:
            continue
        meta = json.loads(sidef.read_text())
        res = int(meta["res"].split("x")[0])
        cam = r3.Cam([float(t) for t in meta["cam"].split(",")],
                     [float(t) for t in meta["look"].split(",")],
                     [float(t) for t in meta["up"].split(",")],
                     float(meta["fov"]), res, res)
        dirs_all = crop_dirs(cam, res)          # (res*res, 3) unit, pano frame
        masks = np.load(maskf)
        for det, mask in zip(dets, masks):
            if det["score"] < SCORE_MIN:
                n_weak += 1
                continue
            label = canonicalize(det["label"], vocab)
            if not label or label in SKIP_LABELS:
                continue
            sel = mask.reshape(-1)
            if sel.mean() > MAX_MASK_FRAC:      # region blob, not an object
                n_blob += 1
                continue
            idx = np.nonzero(sel)[0]
            if len(idx) > MAX_LIFT_PX:
                idx = rng.choice(idx, MAX_LIFT_PX, replace=False)
            d = dirs_all[idx]
            locs, iray, itri = ray.intersects_location(
                np.zeros_like(d), d, multiple_hits=False)
            if len(iray) < MIN_HITS:
                n_thin += 1
                continue
            dist = np.linalg.norm(locs, axis=1)
            med = np.median(dist)
            iqr = np.subtract(*np.percentile(dist, [75, 25]))
            keep = np.abs(dist - med) <= max(0.4, 2.0 * iqr)
            pts = locs[keep]
            if len(pts) < MIN_HITS:
                n_thin += 1
                continue
            lo, hi = aabb_of(pts)
            lifted.append({"label": label, "score": det["score"], "view": view,
                           "lo": lo, "hi": hi, "pts": pts,
                           "tris": np.unique(itri[keep])})   # 3D segmentation:
                           # the mesh faces this detection's rays actually hit
    print(f"[lift] {len(lifted)} lifted detections "
          f"(dropped: {n_weak} weak, {n_blob} blobs, {n_thin} thin)", flush=True)

    # ---- greedy cross-crop merge by label + 3D overlap (lift_views convention) ----
    used = [False] * len(lifted)
    objects, obj_pts, obj_tris = [], [], []
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
        lo, hi = aabb_of(pts)
        obj_pts.append(pts)
        obj_tris.append(np.unique(np.concatenate([g["tris"] for g in grp])))
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

    # ---- 3D segmentation: face ownership map + completeness metric ----
    # smaller objects claim contested faces (books win over the bookshelf
    # behind them); -1 = unclaimed face (the module-4 mesh residual)
    face_owner = np.full(len(mesh.faces), -1, np.int32)
    by_size = sorted(range(len(objects)),
                     key=lambda k: -float(np.prod(objects[k]["size"])))
    for k in by_size:               # big first, small overwrite
        face_owner[obj_tris[k]] = k
    areas = mesh.area_faces
    total_area = float(areas.sum())
    claimed_area = float(areas[face_owner >= 0].sum())
    mesh_explained_pct = round(100.0 * claimed_area / total_area, 1)
    seg3d_f = paths.seg_pano_dir(sc) / "seg3d.npz"
    np.savez_compressed(
        seg3d_f, face_owner=face_owner,
        labels=np.array([o["label"] for o in objects]),
        ids=np.array([o["id"] for o in objects]))
    print(f"[lift] 3D seg: {int((face_owner >= 0).sum()):,}/{len(mesh.faces):,} "
          f"faces claimed = {mesh_explained_pct}% of surface area "
          f"(unclaimed = walls/floor/ceiling + module-4 residual) -> {seg3d_f.name}",
          flush=True)

    manifest = {
        "scene": sc,
        "source": {"bundle": str(bundle), "collider": glbf.name,
                   "method": "pano-detect + mesh-raycast (week8 module 3)"},
        "frame": {"space": "pano",
                  "up": [0.0, 1.0, 0.0],
                  "floor_y": round(floor_y, 3),
                  "ceiling_y": round(ceil_y, 3),
                  "glb_to_pano": [[1, 0, 0], [0, -1, 0], [0, 0, 1]],
                  "note": "pano camera at origin (eye height above floor), +y up, "
                          "image center = +Z. NOT the splat raw frame — the "
                          "mesh<->splat offset is unverified (A2b); convert on "
                          "resolution, do not assume."},
        "views_used": sorted(dets_all.keys()),
        "seg3d": {"file": "seg_pano/seg3d.npz",
                  "mesh_explained_pct": mesh_explained_pct},
        "objects": objects,
    }
    for k, o in enumerate(objects):
        o["n_mesh_faces"] = int(len(obj_tris[k]))
        o["surface_area_m2"] = round(float(areas[obj_tris[k]].sum()), 3)
    outf = paths.scene_dir(sc) / "scene_manifest_pano.json"
    outf.write_text(json.dumps(manifest, indent=2))
    print(f"[lift] wrote {outf} ({len(objects)} objects)", flush=True)
    for o in objects:
        print(f'  {o["id"]} {o["label"]:16s} score={o["score"]:.2f} '
              f'size={o["size"]} center={o["center"]} '
              f'dets={o["n_detections"]}', flush=True)

    # ---- overlay: 3D boxes projected onto the pano (equirect) ----
    from PIL import Image, ImageDraw
    Image.MAX_IMAGE_PIXELS = None
    panof = next(bundle.glob("*_pano.png"))
    W, H = 2304, 1152
    im = Image.open(panof).convert("RGB").resize((W, H), Image.LANCZOS)
    dr = ImageDraw.Draw(im)
    PALETTE = [(230, 60, 60), (60, 130, 230), (60, 190, 90), (240, 160, 40),
               (170, 90, 230), (240, 90, 180), (90, 210, 210), (160, 160, 60),
               (250, 250, 250), (140, 90, 50)]
    for k, o in enumerate(objects):
        lo, hi = np.array(o["aabb_min"]), np.array(o["aabb_max"])
        c = PALETTE[k % len(PALETTE)]
        corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                            for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        # sample each aabb edge densely (straight 3D lines curve on equirect)
        for a_ in range(8):
            for b_ in range(a_ + 1, 8):
                if bin(a_ ^ b_).count("1") != 1:
                    continue
                seg_pts = corners[a_] + (corners[b_] - corners[a_]) * np.linspace(0, 1, 48)[:, None]
                dnorm = seg_pts / (np.linalg.norm(seg_pts, axis=1, keepdims=True) + 1e-9)
                u, v = dir_to_equirect(dnorm, W, H)
                for m in range(len(u) - 1):
                    if abs(u[m + 1] - u[m]) > W / 2:    # seam wrap
                        continue
                    dr.line([(u[m], v[m]), (u[m + 1], v[m + 1])], fill=c, width=2)
        ctr = np.array(o["center"], float)
        dn = ctr / (np.linalg.norm(ctr) + 1e-9)
        cu, cv = dir_to_equirect(dn[None, :], W, H)
        txt = f'{o["id"]} {o["label"]}'
        dr.text((float(cu[0]) + 1, float(cv[0]) + 1), txt, fill=(0, 0, 0))
        dr.text((float(cu[0]), float(cv[0])), txt, fill=c)
    ovf = seg / "manifest_overlay_pano.png"
    im.save(ovf)
    print(f"[lift] wrote {ovf}", flush=True)

    # ---- 3D-segmentation viz: equirect of the mesh, faces colored by owner ----
    import hashlib
    W2, H2 = 1152, 576
    us = (np.arange(W2) + 0.5) / W2
    vs = (np.arange(H2) + 0.5) / H2
    theta = (2 * np.pi * (us - 0.5))[None, :]
    phi = (np.pi * (0.5 - vs))[:, None]
    dx = np.cos(phi) * np.sin(theta); dz = np.cos(phi) * np.cos(theta)
    dy = np.sin(phi) * np.ones_like(theta)
    dgrid = np.stack([np.broadcast_to(dx, (H2, W2)),
                      np.broadcast_to(dy, (H2, W2)),
                      np.broadcast_to(dz, (H2, W2))], axis=-1).reshape(-1, 3)
    locs2, iray2, itri2 = ray.intersects_location(
        np.zeros_like(dgrid), dgrid, multiple_hits=False)
    img = np.full((H2 * W2, 3), 25, np.uint8)
    shade = np.abs((mesh.face_normals[itri2] * dgrid[iray2]).sum(axis=1))
    owner = face_owner[itri2]
    def _oc(k):
        h = hashlib.md5(objects[k]["id"].encode()).digest()
        c = np.array([h[0], h[1], h[2]], np.float32)
        return 70 + 185 * c / (c.max() + 1e-6)
    ocolors = np.array([_oc(k) for k in range(len(objects))], np.float32) \
        if objects else np.zeros((0, 3), np.float32)
    base = np.full((len(iray2), 3), 90, np.float32)          # unclaimed = gray
    has = owner >= 0
    base[has] = ocolors[owner[has]]
    img[iray2] = np.clip(base * (0.45 + 0.55 * shade[:, None]), 0, 255).astype(np.uint8)
    seg3d_img = Image.fromarray(img.reshape(H2, W2, 3))
    dr3 = ImageDraw.Draw(seg3d_img)
    for k, o in enumerate(objects):
        ctr = np.array(o["center"], float)
        dn = ctr / (np.linalg.norm(ctr) + 1e-9)
        cu, cv = dir_to_equirect(dn[None, :], W2, H2)
        dr3.text((float(cu[0]), float(cv[0])), o["id"][4:], fill=(255, 255, 255))
    s3f = seg / "seg3d_equirect.png"
    seg3d_img.save(s3f)
    print(f"[lift] wrote {s3f}", flush=True)

    # ---- top-down plan: mesh footprint + boxes ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    vx = mesh.vertices
    band = (vx[:, 1] > floor_y + 0.1) & (vx[:, 1] < ceil_y - 0.1)
    fig, ax = plt.subplots(figsize=(9, 9))
    ax.hist2d(vx[band, 0], vx[band, 2], bins=200, cmap="Greys",
              norm=matplotlib.colors.LogNorm())
    colors = plt.cm.tab10.colors
    for k, o in enumerate(objects):
        lo, hi = o["aabb_min"], o["aabb_max"]
        c = colors[k % 10]
        ax.add_patch(Rectangle((lo[0], lo[2]), hi[0] - lo[0], hi[2] - lo[2],
                               fill=False, edgecolor=c, linewidth=2))
        ax.text(lo[0], lo[2] - 0.05, f'{o["id"]} {o["label"]}', color=c, fontsize=7)
    ax.plot(0, 0, "r*", markersize=14)
    ax.set_aspect("equal")
    ax.invert_yaxis()   # +z down, matching viewer/plan conventions
    ax.set_xlabel("x"); ax.set_ylabel("z (down)")
    ax.set_title(f"{sc}: pano-lifted objects, top-down (star = pano camera)")
    planf = seg / "manifest_plan_pano.png"
    fig.tight_layout(); fig.savefig(planf, dpi=110)
    print(f"[lift] wrote {planf}", flush=True)


if __name__ == "__main__":
    main()
