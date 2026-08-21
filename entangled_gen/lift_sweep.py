"""Splat-base lift over the analyzer sweep frames (PLAN_SPLAT_RECENTER.md).

Same-artifact end to end: views are splat renders (analyzer job frames),
depth is the splat z-buffer, cameras are the job's transforms.json under the
G1-verified convention — no collider, no pano, no registration tax.

G2 (--frame / auto): lift ONE frame's detections and project the boxes back
into that frame + 2 same-standpoint neighbors for user judgment.
G3 (--all): full-sweep lift with per-axis edge trust + containment merge
(ported from the pano recenter experiment) -> scene_manifest_sweep.json +
seg_sweep/lift_pool.json (per-detection pool, feeds the G4 recenter round)
+ floor-gap stats.

Run:  python lift_sweep.py --scene bedroom_marble            (G2, auto frame)
      python lift_sweep.py --scene bedroom_marble --all      (G3)
"""
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

import paths
from lift_views import depth_zbuffer, unproject_px, aabb_of, iou3d, SYNONYMS, \
    MIN_MASK_PX, MAX_LIFT_PX, SCORE_MIN
from lift_pano import SKIP_LABELS
from vocab_from_prompt import canonicalize
from analyzer.cams_from_transforms import cams_for_job, MatCam

r3 = paths.load_r3()

EDGE_TOL = 3.0          # px from the frame border that flags a clipped edge
CONTAIN_MERGE = 0.50    # containment fraction that merges (partial-in-whole)
MERGE_IOU = 0.20
# whole-frame degenerate guard (2026-08-06, living scene #2): image-denoting
# query words ("photo") make the detector box the ENTIRE crop — that is the
# view, not an object observation. Measured separation: degenerates 0.99-1.0
# of frame vs <=~0.50 for every legitimate class.
FRAME_COVER_MAX = 0.95
# nearest-sufficient-cluster depth selection (2026-08-06): masks always hold
# see-through pixels (between chair legs, window glass, silhouette rim) whose
# depth is the BACKGROUND; a spread-scaled trim widens with the bleed instead
# of cutting it. Depths gap-split into clusters; background sits past a gap.
DEPTH_GAP = 0.40        # m of empty ray = cluster boundary (contiguous keeps)
CLUSTER_FRAC = 0.25     # min mask fraction for a cluster to count as the object
BOUND_NAMES = ["xlo", "xhi", "ylo", "yhi", "zlo", "zhi"]

PALETTE = [(230, 60, 60), (60, 130, 230), (60, 190, 90), (240, 160, 40),
           (170, 90, 230), (240, 90, 180), (90, 210, 210), (160, 160, 60),
           (250, 250, 250), (140, 90, 50)]


def edge_trust(box, cam):
    """6 bools (xlo xhi ylo yhi zlo zhi): a detection box clipped at a frame
    edge distrusts the one 3D aabb bound along the world axis most aligned
    with that edge's outward camera direction (per-axis rule, ported from the
    pano recenter experiment). cam.R rows = right/up/forward in world."""
    trust = [True] * 6
    edges = []
    if box["xmin"] <= EDGE_TOL:
        edges.append(-cam.R[0])
    if box["xmax"] >= cam.w - EDGE_TOL:
        edges.append(cam.R[0])
    if box["ymin"] <= EDGE_TOL:
        edges.append(cam.R[1])          # image top = world up
    if box["ymax"] >= cam.h - EDGE_TOL:
        edges.append(-cam.R[1])
    for e in edges:
        ax = int(np.argmax(np.abs(e)))
        b = 2 * ax + (1 if e[ax] > 0 else 0)
        trust[b] = False
    return trust, len(edges) > 0


MAD_BOUND_M = 0.40      # member-bound outlier gate: |v - median| beyond
MAD_BOUND_K = 3.0       # max(0.40 m, 3*MAD) with n>=4 votes = one member's
#                         bleed, not a completion of partial views
#                         (2026-08-06 fix C: a single bleeding member could
#                         still own a face — q=0.05 INTERPOLATES from the
#                         extreme at small n: obj_042 z, obj_053 plant)


def _mad_keep(vals):
    """Drop bound votes that sit implausibly far from the member consensus.
    Only with n>=4 (below that a median is not a consensus)."""
    if len(vals) < 4:
        return vals
    med = float(np.median(vals))
    mad = float(np.median(np.abs(np.asarray(vals) - med)))
    thr = max(MAD_BOUND_M, MAD_BOUND_K * mad)
    kept = [v for v in vals if abs(v - med) <= thr]
    return kept or vals


def group_box(members, q=0.0):
    """Per-axis fused bounds: each bound comes from members that measured it
    un-clipped; falls back to all members (flagged weak) if none did.

    q=0 -> UNION (min-los / max-his). Measured 2026-07-26: union is a
    max-statistic — box volume inflates with member count (corr(log n, log
    inflation) = +0.84 on the G3 pool; 21+ members -> median 4.2x). q=0.1
    -> soft quantile (10th pct of los / 90th of his): still completes
    partial views, but one bleeding mask can no longer own a face.
    MAD gate (_mad_keep) runs before the quantile: a far-outlier vote is a
    bleed, and a quantile only dilutes it instead of removing it."""
    lo = np.empty(3); hi = np.empty(3)
    weak = []
    for ax in range(3):
        los = [m["lo"][ax] for m in members if m["trust"][2 * ax]]
        his = [m["hi"][ax] for m in members if m["trust"][2 * ax + 1]]
        if not los:
            los = [m["lo"][ax] for m in members]; weak.append(BOUND_NAMES[2 * ax])
        if not his:
            his = [m["hi"][ax] for m in members]; weak.append(BOUND_NAMES[2 * ax + 1])
        los = _mad_keep(los)
        his = _mad_keep(his)
        if q > 0:
            lo[ax] = np.percentile(los, 100 * q)
            hi[ax] = np.percentile(his, 100 * (1 - q))
        else:
            lo[ax] = min(los); hi[ax] = max(his)
    return lo, hi, weak


def containment(lo1, hi1, lo2, hi2):
    ilo, ihi = np.maximum(lo1, lo2), np.minimum(hi1, hi2)
    if np.any(ihi <= ilo):
        return 0.0
    return float(np.prod(ihi - ilo) /
                 (min(np.prod(hi1 - lo1), np.prod(hi2 - lo2)) + 1e-9))


def merge_per_axis(pool, q=0.0):
    """Greedy same-label grouping by 3D IoU OR containment, most-trusted /
    highest-score anchors first; per-axis trusted bound fusion (q: see
    group_box — 0 = union, 0.1 = robust quantile)."""
    used = [False] * len(pool)
    objects = []
    order = sorted(range(len(pool)),
                   key=lambda i: (-sum(pool[i]["trust"]), -pool[i]["score"]))
    for i in order:
        if used[i]:
            continue
        grp = [pool[i]]; grp_idx = [i]; used[i] = True; changed = True
        while changed:
            changed = False
            glo, ghi, _ = group_box(grp, q)
            for j in order:
                if used[j] or pool[j]["label"] != pool[i]["label"]:
                    continue
                jlo, jhi = np.array(pool[j]["lo"]), np.array(pool[j]["hi"])
                if (iou3d(glo, ghi, jlo, jhi) > MERGE_IOU
                        or containment(glo, ghi, jlo, jhi) > CONTAIN_MERGE):
                    grp.append(pool[j]); grp_idx.append(j)
                    used[j] = True; changed = True
        lo, hi, weak = group_box(grp, q)
        flags = [f"lower_bound_{w}" for w in weak]
        if any(g.get("source") == "recenter" for g in grp):
            flags.append("recenter_supported")
        objects.append({
            "id": f"obj_{len(objects):03d}", "label": grp[0]["label"],
            "score": round(max(g["score"] for g in grp), 3),
            "aabb_min": [round(float(v), 3) for v in lo],
            "aabb_max": [round(float(v), 3) for v in hi],
            "center": [round(float(v), 3) for v in (lo + hi) / 2],
            "size": [round(float(v), 3) for v in hi - lo],
            "views": sorted({g["view"] for g in grp}),
            "n_detections": len(grp),
            "n_whole": sum(1 for g in grp if not g["trunc"]),
            "members": grp_idx,     # pool indices — exact provenance
            "flags": flags})
    return objects


def lift_frame(xyz, cam, dets, masks, view="", vocab=None, keep_pts=True,
               min_score=SCORE_MIN):
    """Our standard mask lift (lift_views mechanics) for one sweep frame.
    Returns [{label, score, view, lo, hi, trust, trunc, (pts), box}], RAW."""
    depth = depth_zbuffer(xyz, cam, near=0.2)
    out = []
    for det, mask in zip(dets, masks):
        if det["score"] < min_score:
            continue
        bx = det["box"]
        if ((bx["xmax"] - bx["xmin"]) >= FRAME_COVER_MAX * cam.w
                and (bx["ymax"] - bx["ymin"]) >= FRAME_COVER_MAX * cam.h):
            continue        # whole-frame degenerate (see FRAME_COVER_MAX)
        if vocab is not None:
            label = canonicalize(det["label"], vocab)
            if not label or label not in vocab or label in SKIP_LABELS:
                continue
        else:
            label = SYNONYMS.get(det["label"], det["label"])
        valid = mask & np.isfinite(depth)
        if valid.sum() < MIN_MASK_PX:
            continue
        vs, us = np.nonzero(valid)
        ds = depth[vs, us]
        order = np.argsort(ds)
        sd = ds[order]
        cuts = np.nonzero(np.diff(sd) > DEPTH_GAP)[0]
        bounds = [0, *(cuts + 1), len(sd)]
        need = max(MIN_MASK_PX, int(CLUSTER_FRAC * len(sd)))
        pick = max(range(len(bounds) - 1),
                   key=lambda k: bounds[k + 1] - bounds[k])
        for k in range(len(bounds) - 1):        # nearest wins over biggest
            if bounds[k + 1] - bounds[k] >= need:
                pick = k
                break
        sel = order[bounds[pick]:bounds[pick + 1]]
        us, vs, ds = us[sel], vs[sel], ds[sel]
        # within-cluster spread trim = the pre-2026-08-06 rule; on gap-free
        # masks the cluster is the whole distribution, so behavior (and the
        # bedroom regression) reduces to the old code exactly
        med = np.median(ds)
        iqr = np.subtract(*np.percentile(ds, [75, 25]))
        keep = np.abs(ds - med) <= max(0.4, 2.0 * iqr)
        us, vs, ds = us[keep], vs[keep], ds[keep]
        if len(ds) < MIN_MASK_PX:
            continue
        if len(ds) > MAX_LIFT_PX:
            sel = np.random.default_rng(0).choice(len(ds), MAX_LIFT_PX,
                                                  replace=False)
            us, vs, ds = us[sel], vs[sel], ds[sel]
        pts = unproject_px(cam, us.astype(np.float32), vs.astype(np.float32), ds)
        lo, hi = aabb_of(pts)
        trust, trunc = edge_trust(det["box"], cam)
        rec = {"label": label, "score": det["score"], "view": view,
               "lo": lo, "hi": hi, "trust": trust, "trunc": trunc,
               "box": det["box"]}
        if keep_pts:
            rec["pts"] = pts
        out.append(rec)
    return out


def draw_boxes_into(imgf, cam, lifted, outf, title):
    im = Image.open(imgf).convert("RGB")
    dr = ImageDraw.Draw(im)
    for k, L in enumerate(lifted):
        lo, hi = L["lo"], L["hi"]
        corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                            for y in (lo[1], hi[1]) for z in (lo[2], hi[2])],
                           np.float32)
        u, v, z = cam.project(corners)
        if np.median(z) < 0.2:
            continue
        ok = z > 0.2
        c = PALETTE[k % len(PALETTE)]
        for a in range(8):
            for b in range(a + 1, 8):
                if bin(a ^ b).count("1") == 1 and ok[a] and ok[b]:
                    dr.line([(u[a], v[a]), (u[b], v[b])], fill=c, width=2)
        if ok.any():
            dr.text((float(np.clip(u[ok].min(), 2, cam.w - 90)),
                     float(np.clip(v[ok].min() - 12, 2, cam.h - 12))),
                    f'{L["label"]} {L["score"]:.2f}', fill=c)
    dr.rectangle([0, 0, cam.w, 14], fill=(0, 0, 0))
    dr.text((4, 2), title, fill=(255, 255, 255))
    im.save(outf)
    print(f"[g2] wrote {outf}", flush=True)


def run_g3(sc, cams, jd, tj, seg, dets_all, xyz):
    """G3: lift all frames, per-axis merge, manifest + pool + floor stats."""
    vocab = None
    vf = paths.scene_dir(sc) / "vocab.json"
    if vf.exists():
        vocab = json.loads(vf.read_text(encoding="utf-8")).get("canonical")
        print(f"[g3] vocab.json: {len(vocab or [])} canonical terms", flush=True)
    pool = []
    n_frames = 0
    for view in sorted(dets_all):
        maskf = seg / f"{view}_masks.npy"
        if not maskf.exists() or not dets_all[view]:
            continue
        fi = int(view.split("_")[-1])
        lifted = lift_frame(xyz, cams[fi], dets_all[view], np.load(maskf),
                            view=view, vocab=vocab, keep_pts=False)
        pool.extend(lifted)
        n_frames += 1
        if n_frames % 25 == 0:
            print(f"[g3] {n_frames} frames, {len(pool)} lifted so far", flush=True)
    n_tr = sum(1 for L in pool if L["trunc"])
    print(f"[g3] lifted {len(pool)} detections from {n_frames} frames "
          f"({n_tr} edge-truncated)", flush=True)

    objects = merge_per_axis(pool)
    print(f"[g3] merged -> {len(objects)} objects", flush=True)

    # frame block: physical floor/ceiling from the splat itself (raw up = -y
    # for marble bundles: floor is the HIGH-y shell)
    ys = xyz[:, 1]
    floor_y = float(np.percentile(ys, 99))
    ceil_y = float(np.percentile(ys, 1))
    man = {"scene": sc, "source": "lift_sweep.py G3 (splat-base)",
           "views": f"analyzer {jd.name} frames + seg_sweep detections",
           "frame": {"space": "raw", "up": [0.0, -1.0, 0.0],
                     "floor_y": round(floor_y, 3), "ceiling_y": round(ceil_y, 3),
                     "camera_convention": "c2w_opencv (G1)",
                     "note": "same-artifact lane: splat renders + splat "
                             "z-buffer depth; per-axis edge trust merge"},
           "n_objects": len(objects), "objects": objects}
    outf = paths.scene_dir(sc) / "scene_manifest_sweep.json"
    outf.write_text(json.dumps(man, indent=2))
    print(f"[g3] wrote {outf}", flush=True)

    # pool sidecar for the G4 recenter round
    pj = [{k: (v.tolist() if isinstance(v, np.ndarray) else v)
           for k, v in L.items() if k != "pts"} for L in pool]
    (seg / "lift_pool.json").write_text(json.dumps(
        {"scene": sc, "floor_y": round(floor_y, 3), "pool": pj}))
    print(f"[g3] wrote {seg / 'lift_pool.json'}", flush=True)

    # floor-gap stats (the G3 acceptance number; yaw4 reference ~ +0.02)
    FL = ("bed", "wardrobe", "desk", "chair", "rug", "mat", "shelf", "table",
          "stool", "pot", "basket", "lamp")
    gaps = np.array([floor_y - o["aabb_max"][1] for o in objects])
    flg = np.array([floor_y - o["aabb_max"][1] for o in objects
                    if any(k in o["label"] for k in FL)])
    print(f"[g3] floor gap all n={len(gaps)}: median {np.median(gaps):+.3f}  "
          f"min {gaps.min():+.3f}", flush=True)
    if len(flg):
        print(f"[g3] floor gap floor-ish n={len(flg)}: median "
              f"{np.median(flg):+.3f}  q25 {np.percentile(flg, 25):+.3f}  "
              f"q75 {np.percentile(flg, 75):+.3f}", flush=True)
    from collections import Counter
    cnt = Counter(o["label"] for o in objects)
    print("[g3] labels:", dict(cnt.most_common()), flush=True)


def print_gap_stats(tag, objects, floor_y):
    # Either array may legitimately be empty — a sparse scene can lift no
    # objects at all, or none whose label is floor-ish (fresh05 lifted 5,
    # all wall-mounted). Same guard as the G3 stats above; this is a
    # report, and a report must never be what kills the funnel.
    FL = ("bed", "wardrobe", "desk", "chair", "rug", "mat", "shelf", "table",
          "stool", "pot", "basket", "lamp")
    gaps = np.array([floor_y - o["aabb_max"][1] for o in objects])
    flg = np.array([floor_y - o["aabb_max"][1] for o in objects
                    if any(k in o["label"] for k in FL)])
    n_weak = sum(1 for o in objects if o["flags"])
    all_s = (f"median {np.median(gaps):+.3f} min {gaps.min():+.3f}"
             if len(gaps) else "(none)")
    fl_s = (f"median {np.median(flg):+.3f} q75 {np.percentile(flg, 75):+.3f}"
            if len(flg) else "(none)")
    print(f"[{tag}] {len(objects)} objects, {n_weak} weak-bound; floor gap "
          f"all: {all_s}; floor-ish n={len(flg)}: {fl_s}", flush=True)


def run_remerge(sc, q):
    """Re-merge the saved G3 pool with quantile fusion — no re-lift, CPU
    only. Writes scene_manifest_sweep_robust.json (q>0) for side-by-side
    comparison against the union manifest."""
    seg = paths.scene_dir(sc) / "seg_sweep"
    pj = json.loads((seg / "lift_pool.json").read_text())
    pool = pj["pool"]
    print(f"[remerge] {len(pool)} pooled detections, q={q}", flush=True)
    objects = merge_per_axis(pool, q=q)
    suffix = "_robust" if q > 0 else ""
    src = json.loads((paths.scene_dir(sc) / "scene_manifest_sweep.json")
                     .read_text())
    man = {"scene": sc,
           "source": f"lift_sweep.py remerge q={q} "
                     f"({'robust quantile' if q > 0 else 'union'})",
           "views": src.get("views"), "frame": src["frame"],
           "n_objects": len(objects), "objects": objects}
    outf = paths.scene_dir(sc) / f"scene_manifest_sweep{suffix}.json"
    outf.write_text(json.dumps(man, indent=2))
    print(f"[remerge] wrote {outf}", flush=True)
    print_gap_stats("remerge", objects, pj["floor_y"])
    from collections import Counter
    cnt = Counter(o["label"] for o in objects)
    print("[remerge] labels:", dict(cnt.most_common(12)), flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--job", default="")
    ap.add_argument("--frame", type=int, default=-1,
                    help="frame index; default = most detections")
    ap.add_argument("--all", action="store_true", help="G3 full-sweep lift")
    ap.add_argument("--remerge-q", type=float, default=-1.0,
                    help="re-merge the saved pool with this fusion quantile "
                         "(0 = union, 0.1 = robust); no re-lift")
    a = ap.parse_args()
    sc = a.scene

    if a.remerge_q >= 0:
        run_remerge(sc, a.remerge_q)
        return

    cams, jd, tj, conv = cams_for_job(sc, a.job)
    print(f"[g2] cameras: {len(cams)} frames, convention {conv} (G1)", flush=True)
    seg = paths.scene_dir(sc) / "seg_sweep"
    dets_all = json.loads((seg / "detections.json").read_text())

    if a.all:
        print("[g3] loading splat ...", flush=True)
        xyz, rgb, _a, _r = r3.load_splat(str(paths.ply(sc)), opacity_min=0.3)
        print(f"[g3] {len(xyz):,} gaussians", flush=True)
        run_g3(sc, cams, jd, tj, seg, dets_all, xyz)
        return

    if a.frame >= 0:
        fi = a.frame
    else:  # richest frame that has masks on disk
        def n_ok(v):
            return sum(1 for d in dets_all.get(v, []) if d["score"] >= SCORE_MIN)
        cand = [v for v in dets_all if (seg / f"{v}_masks.npy").exists()]
        view = max(cand, key=n_ok)
        fi = int(view.split("_")[-1])
    view = f"frame_{fi:04d}"
    dets = dets_all[view]
    masks = np.load(seg / f"{view}_masks.npy")
    print(f"[g2] frame {fi}: {len(dets)} detections", flush=True)

    print("[g2] loading splat ...", flush=True)
    xyz, rgb, _a, _r = r3.load_splat(str(paths.ply(sc)), opacity_min=0.3)
    print(f"[g2] {len(xyz):,} gaussians", flush=True)

    lifted = lift_frame(xyz, cams[fi], dets, masks)
    print(f"[g2] lifted {len(lifted)} of {len(dets)} detections:", flush=True)
    for L in lifted:
        sz = L["hi"] - L["lo"]
        print(f'  {L["label"]:16s} {L["score"]:.2f}  size '
              f'{sz[0]:.2f}x{sz[1]:.2f}x{sz[2]:.2f}  lo {np.round(L["lo"], 2)}',
              flush=True)

    # overlays: the lifted frame + 2 same-standpoint neighbors
    pos_idx = {int(Path(fr["file_path"]).stem.split("_")[-1]): fr["position_idx"]
               for fr in tj["frames"]}
    same = sorted(i for i, p in pos_idx.items() if p == pos_idx[fi])
    k = same.index(fi)
    neighbors = [same[(k - 1) % len(same)], same[(k + 1) % len(same)]]
    for i in [fi] + neighbors:
        tag = "lifted from" if i == fi else "reprojected into"
        draw_boxes_into(jd / "frames" / f"frame_{i:04d}.png", cams[i], lifted,
                        seg / f"g2_overlay_frame_{i:04d}.png",
                        f"G2 {tag} frame_{fi:04d} -> view frame_{i:04d}")


if __name__ == "__main__":
    main()
