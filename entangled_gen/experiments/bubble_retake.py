"""Parallax retake v2 — aimed crops from BUBBLE-standpoint panos
(2026-08-06, user design: R-S2-22 retake mechanics + R-S2-23 bubble
standpoints, two offsets so no object sits parallax-blind along one
baseline).

Per resolved node x per bubble rig (rig_sp1 +x, rig_sp2 +z):
  1. aimed shot resampled from that rig's pano on CPU (pano_recenter's
     exact shot convention: fwd_p = unit(center - eye) * MIRROR, fov fit)
  2. mini-G1 corr on the shot camera (house rule, 192-scaled)
  3. GroundingDINO re-detect the node's name, best overlap with the
     reprojected original box; SAM -> mask; lift -> side box
  4. each successful side view contributes a PRISM: its box with its own
     dominant-ray axis released to infinity (a view is untrusted only
     along its own ray)
  5. the ORIGINAL sp0 mask points are filtered through ALL prisms and the
     box refit from survivors (1/99 pct) — "only the overlap is the
     object" at point level

No per-object GPU renders (both panos are one WSL render each, reusable);
degrades conservatively: no successful side view -> original kept +
flagged for far-render escalation. PREVIEW output only.

Run:  python experiments/bubble_retake.py --scene living_marble
      [--rigs rig_sp1,rig_sp2] [--only obj_004,...]
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
from PIL import Image

import sys
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402
from lift_sweep import lift_frame  # noqa: E402
from lift_views import depth_zbuffer, unproject_px  # noqa: E402
from pano_lift import crop_cam_raw, MIRROR  # noqa: E402
from sweep_recenter import corr_check  # noqa: E402
from analyzer.cams_from_transforms import MatCam  # noqa: E402
from crop_pano import crop_dirs, sample_equirect  # noqa: E402

RES = 960
CORR_MIN = 0.25
DET_THR = 0.20
FOV_MIN, FOV_MAX = 35.0, 75.0
MARGIN = 1.5
PAD = 0.05          # m of slack around each prism face


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--rigs", default="rig_sp1,rig_sp2")
    ap.add_argument("--only", default="")
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    outdir = sd / "bubble_retake"
    outdir.mkdir(exist_ok=True)

    g = json.loads((sd / "scene_graph.json").read_text(encoding="utf-8"))
    nodes = g["resolved"]["nodes"]
    if a.only:
        want = set(a.only.split(","))
        nodes = [n for n in nodes if n["id"] in want]

    rigs = []
    for rn in a.rigs.split(","):
        rig = sd / rn.strip()
        meta = json.loads((rig / "pano_selfrender_meta.json").read_text())
        rigs.append({"name": rn.strip(), "dir": rig,
                     "eye": np.array(meta["eye_raw"], float), "pano": None})

    print("[bubble] loading splat ...", flush=True)
    r3 = paths.load_r3()
    xyz, rgb, _a, _r = r3.load_splat(str(paths.ply(a.scene)), opacity_min=0.3)

    import torch
    dev = "cuda" if torch.cuda.is_available() else "cpu"
    from transformers import (AutoProcessor, GroundingDinoForObjectDetection,
                              SamModel, SamProcessor)
    gd_proc = AutoProcessor.from_pretrained("IDEA-Research/grounding-dino-base")
    gd = GroundingDinoForObjectDetection.from_pretrained(
        "IDEA-Research/grounding-dino-base").to(dev)
    gd.eval()
    sam = SamModel.from_pretrained("facebook/sam-vit-base").to(dev)
    sam_proc = SamProcessor.from_pretrained("facebook/sam-vit-base")

    # ---- original-rig plumbing for the refilter (same as retake v1) ----
    eye0 = json.loads((sd / "rig_sp0" / "pano_selfrender_meta.json")
                      .read_text())["eye_raw"]
    man = json.loads((sd / "scene_manifest_pano2c_rc_f30.json").read_text())
    f30_by_id = {o["id"]: o for o in man["objects"]}
    pool = json.loads((sd / "rig_sp0" / "lift_poolc.json").read_text())["pool"]
    dets_all = json.loads((sd / "rig_sp0" / "seg_batched20" /
                           "detections.json").read_text())
    _vd, _vc, _vm = {}, {}, {}

    def view_cam(view):
        if view not in _vc:
            side = json.loads((sd / "rig_sp0" / "crops" / f"{view}.json")
                              .read_text())
            _vc[view] = crop_cam_raw(side, eye0)
        return _vc[view]

    def view_depth(view):
        if view not in _vd:
            _vd[view] = depth_zbuffer(xyz, view_cam(view), near=0.2)
        return _vd[view]

    def member_mask(m):
        view = m["view"]
        if view not in _vm:
            f = sd / "rig_sp0" / "seg_batched20" / f"{view}_masks.npy"
            _vm[view] = np.load(f) if f.exists() else None
        masks = _vm[view]
        if masks is None:
            return None
        for i, d in enumerate(dets_all.get(view, [])):
            if all(abs(d["box"][k] - m["box"][k]) < 1.0 for k in m["box"]):
                return masks[i] if i < len(masks) else None
        return None

    def node_points(node):
        pts_all = []
        for fid in node.get("members", []):
            fo = f30_by_id.get(fid)
            if not fo:
                continue
            for mi in fo.get("members", []):
                if mi >= len(pool):
                    continue
                m = pool[mi]
                mk = member_mask(m)
                if mk is None:
                    continue
                dep = view_depth(m["view"])
                valid = mk & np.isfinite(dep)
                vs, us = np.nonzero(valid)
                if len(vs):
                    pts_all.append(unproject_px(
                        view_cam(m["view"]), us.astype(np.float32),
                        vs.astype(np.float32), dep[vs, us]))
        return np.concatenate(pts_all) if pts_all else None

    def side_view(rig, p_node):
        """Aimed shot from one bubble rig -> (prism_lo, prism_hi, info) or
        (None, None, reason). Prism = side box, ray axis released."""
        nid = p_node["id"]
        geo = p_node["geometry"]
        c = np.array(geo["center"], float)
        d_raw = c - rig["eye"]
        dist = float(np.linalg.norm(d_raw))
        r = float(np.linalg.norm(geo["size"])) / 2
        need = math.degrees(2 * math.atan(MARGIN * r / max(dist, 1e-6)))
        if need > FOV_MAX or dist < 0.4:
            return None, None, "too_close"
        fov = float(np.clip(need, FOV_MIN, FOV_MAX))
        fwd_p = (d_raw / dist) * MIRROR
        name = f"{rig['name']}_{nid}"
        shot = outdir / f"{name}.webp"
        side = {"file": shot.name, "cam": "0,0,0",
                "look": ",".join(f"{v:.6f}" for v in fwd_p),
                "up": "0,1,0", "fov": fov, "res": f"{RES}x{RES}"}
        (outdir / f"{name}.json").write_text(json.dumps(side, indent=2))
        if not shot.exists():
            if rig["pano"] is None:
                Image.MAX_IMAGE_PIXELS = None
                rig["pano"] = np.asarray(Image.open(
                    rig["dir"] / "pano_selfrender.png").convert("RGB"),
                    np.float32)
            PH, PW = rig["pano"].shape[:2]
            cam_p = r3.Cam([0, 0, 0], fwd_p, [0, 1, 0], fov, RES, RES)
            img = sample_equirect(rig["pano"], crop_dirs(cam_p, RES), PW, PH)
            Image.fromarray(np.clip(img.reshape(RES, RES, 3), 0, 255)
                            .astype(np.uint8)).save(shot, quality=92)
        cam_s = crop_cam_raw(side, list(rig["eye"]), scale=192 / RES)
        corr = corr_check(xyz, rgb, cam_s, shot)
        if corr < CORR_MIN:
            return None, None, f"corr_fail({corr:+.2f})"
        cam = crop_cam_raw(side, list(rig["eye"]))
        lo, hi = np.array(geo["aabb_min"]), np.array(geo["aabb_max"])
        corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                            for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        u, v, z = cam.project(corners)
        ok = z > 0.2
        if not ok.any():
            return None, None, "behind_cam"
        pb = [float(np.clip(u[ok].min(), 0, RES)),
              float(np.clip(v[ok].min(), 0, RES)),
              float(np.clip(u[ok].max(), 0, RES)),
              float(np.clip(v[ok].max(), 0, RES))]
        img = Image.open(shot).convert("RGB")
        inputs = gd_proc(images=img, text=p_node["name"] + ".",
                         return_tensors="pt").to(dev)
        with torch.no_grad():
            outputs = gd(**inputs)
        det = gd_proc.post_process_grounded_object_detection(
            outputs, inputs["input_ids"], threshold=DET_THR,
            text_threshold=0.25, target_sizes=[img.size[::-1]])[0]
        # among detections overlapping the projected box, take the HIGHEST
        # SCORE — the crop is already centered+zoomed on the target, and
        # overlap-maximizing picks whatever big region hides inside the
        # projected STREAK box (the table beat the book). Whole-frame
        # degenerates excluded (same rule as the lift guard).
        best = None
        for score, box in zip(det["scores"], det["boxes"]):
            b = [float(x) for x in box]
            if (b[2] - b[0]) >= 0.95 * RES and (b[3] - b[1]) >= 0.95 * RES:
                continue
            ix0, iy0 = max(b[0], pb[0]), max(b[1], pb[1])
            ix1, iy1 = min(b[2], pb[2]), min(b[3], pb[3])
            inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
            area = (b[2] - b[0]) * (b[3] - b[1]) + 1e-9
            if inter / area < 0.3:
                continue
            if best is None or float(score) > best["score"]:
                best = {"score": float(score), "box": {
                    "xmin": b[0], "ymin": b[1], "xmax": b[2], "ymax": b[3]}}
        if best is None:
            return None, None, "no_redetect"
        boxes = [[[best["box"]["xmin"], best["box"]["ymin"],
                   best["box"]["xmax"], best["box"]["ymax"]]]]
        sinp = sam_proc(img, input_boxes=boxes, return_tensors="pt").to(dev)
        with torch.no_grad():
            souts = sam(**sinp, multimask_output=False)
        mask = sam_proc.image_processor.post_process_masks(
            souts.pred_masks.cpu(), sinp["original_sizes"].cpu(),
            sinp["reshaped_input_sizes"].cpu())[0].squeeze(1).numpy()[0] > 0
        lifted = lift_frame(xyz, cam, [dict(best, label=p_node["name"])],
                            mask[None], view=name, keep_pts=True,
                            min_score=DET_THR)
        if not lifted:
            return None, None, "lift_empty"
        # ORIENTED lateral band (2026-08-06, third iteration): a side view
        # is trustworthy along the horizontal direction PERPENDICULAR to
        # its own ray — axis-aligned prisms fail when rays are diagonal
        # (both bubbles saw the book along -z, both axis-prisms released z,
        # streak survived), and vertical constraints from partial side
        # detections crush boxes (seat-slice sofa). So each view yields one
        # scalar band: project the side box onto l = perp(ray, horizontal);
        # refilter keeps points whose l-projection is inside the band.
        r = d_raw.copy()
        r[1] = 0
        r /= np.linalg.norm(r)
        lvec = np.array([r[2], 0.0, -r[0]])
        # band from the side view's ACTUAL lifted points, not its AABB —
        # an axis-aligned box around a diagonal streak is fat in every
        # direction, so its corners overstate the lateral width; the
        # points themselves are tight perpendicular to the ray
        proj = lifted[0]["pts"] @ lvec
        band = {"l": lvec.tolist(),
                "lo": float(np.percentile(proj, 2) - PAD),
                "hi": float(np.percentile(proj, 98) + PAD)}
        return band, None, f"ok({best['score']:.2f})"

    results = []
    for n in nodes:
        geo = n["geometry"]
        rec = {"id": n["id"], "name": n["name"],
               "before": {"size": geo["size"], "aabb_min": geo["aabb_min"],
                          "aabb_max": geo["aabb_max"]}, "views": {}}
        prisms = []
        for rig in rigs:
            band, _unused, why = side_view(rig, n)
            rec["views"][rig["name"]] = why
            if band is not None:
                prisms.append(band)
        if not prisms:
            rec["status"] = "kept"
            results.append(rec)
            print(f"[bubble] {n['id']:8s} {n['name']:16s} KEPT "
                  f"({rec['views']})", flush=True)
            continue
        P = node_points(n)
        if P is None or len(P) < 50:
            rec["status"] = "kept_no_points"
            results.append(rec)
            continue
        keep = np.ones(len(P), bool)
        for band in prisms:
            proj = P @ np.array(band["l"])
            keep &= (proj >= band["lo"]) & (proj <= band["hi"])
        if keep.sum() < 50:
            rec["status"] = "kept_empty_overlap"
            results.append(rec)
            print(f"[bubble] {n['id']:8s} {n['name']:16s} EMPTY overlap — "
                  f"kept, flagged", flush=True)
            continue
        lo = np.percentile(P[keep], 1, axis=0)
        hi = np.percentile(P[keep], 99, axis=0)
        rec["status"] = "carved"
        rec["n_prisms"] = len(prisms)
        rec["after"] = {"aabb_min": [round(float(v), 4) for v in lo],
                        "aabb_max": [round(float(v), 4) for v in hi],
                        "size": [round(float(b - a_), 4)
                                 for a_, b in zip(lo, hi)]}
        results.append(rec)
        print(f"[bubble] {n['id']:8s} {n['name']:16s} {len(prisms)} prisms "
              f"{[round(v, 2) for v in geo['size']]} -> "
              f"{[round(v, 2) for v in rec['after']['size']]}", flush=True)

    by = {}
    for r in results:
        by[r["status"]] = by.get(r["status"], 0) + 1
    report = {"scene": a.scene, "stage": "bubble_retake",
              "rigs": [r["name"] for r in rigs],
              "params": {"CORR_MIN": CORR_MIN, "DET_THR": DET_THR,
                         "MARGIN": MARGIN, "PAD": PAD},
              "by_status": by, "results": results}
    (outdir / "bubble_report.json").write_text(json.dumps(report, indent=1))

    # full-scene preview manifest (carved where carved, original else)
    objs = []
    for r in results:
        if r["status"] == "carved":
            lo, hi = r["after"]["aabb_min"], r["after"]["aabb_max"]
            label = r["name"] + f" (carved x{r['n_prisms']})"
        else:
            lo, hi = r["before"]["aabb_min"], r["before"]["aabb_max"]
            label = r["name"] + f" (kept: {r['status']})"
        objs.append({"id": r["id"], "label": label, "score": 1.0,
                     "aabb_min": lo, "aabb_max": hi,
                     "center": [round((x + y) / 2, 4) for x, y in zip(lo, hi)],
                     "size": [round(y - x, 4) for x, y in zip(lo, hi)],
                     "n_detections": 1, "views": [], "flags": [r["status"]]})
    manp = {"scene": a.scene,
            "source": "experiments/bubble_retake.py preview (v2: two bubble "
                      "panos, prism point-refilter)",
            "frame": {"space": "raw", "up": [0.0, -1.0, 0.0]},
            "n_objects": len(objs), "objects": objs}
    (sd / "scene_manifest_bubble_preview.json").write_text(
        json.dumps(manp, indent=2))
    print(f"[bubble] statuses {by}; report -> bubble_retake/"
          f"bubble_report.json; preview manifest written", flush=True)


if __name__ == "__main__":
    main()
