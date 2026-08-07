"""Candidate-pool parallax retake (2026-08-06, the promotion candidate —
user design refined over R-S2-22..24).

Per resolved node, a POOL of candidate aimed views:
  4 near-cardinal   (world axes +/-x, +/-z, rotated 20 deg off-axis —
                     exact cardinals hit axis-aligned thin objects edge-on)
  1 near-top        (looking down, tilted 20 deg off vertical — footprint
                     king: both its image axes are horizontal)
  2 near-perp       (+/-65 deg off the original observation ray)

Candidate CULL is fully general (user rule — no special-cased views):
  in-bounds  : eye inside the measured room shell (0.3 m pad)
  empty-space: < EMPTY_MAX splat points within 0.3 m of the eye
(the bottom view dies naturally: below the floor = out of bounds.)

Survivors render in ONE WSL gsplat batch; each is verified (mini-G1 corr,
192-scaled) then re-detected (GroundingDINO on the node's name, highest
score overlapping the reprojected box, whole-frame degenerates excluded)
and SAM-masked. Every verified view contributes its HORIZONTAL lateral
band(s) — point-based 2/98 pct projections perpendicular to its ray (the
top view contributes two orthogonal bands). Vertical is deliberately
unconstrained (partial side masks crush; bottoms belong to support_clip).
One point refilter composes all bands over the ORIGINAL sp0 mask points;
box refit at 1/99 pct. Keeps (flagged) only when the whole pool fails.

Run:  python experiments/pool_retake.py --scene living_marble
      [--only obj_004,...] [--res 768]
"""
import argparse
import json
import math
import subprocess
from pathlib import Path

import numpy as np
from PIL import Image

import sys
HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402
from lift_sweep import lift_frame  # noqa: E402
from lift_views import depth_zbuffer, unproject_px  # noqa: E402
from pano_lift import crop_cam_raw  # noqa: E402
from sweep_recenter import corr_check, c2w_from_eye_aim  # noqa: E402
from analyzer.cams_from_transforms import MatCam  # noqa: E402

CORR_MIN = 0.12          # gross-breakage catch only: cameras are DEFINED
#                          through the twice-verified c2w convention; 0.25
#                          punished flat content (tabletop from above)
DET_THR = 0.20
WALL_PAD = 0.30
EMPTY_R = 0.30
EMPTY_MAX = 1500         # cheap pre-filter LOOSER than the verifier: a
#                          sphere grazing a sofa edge is a usable camera
OFF_AXIS = 10.0          # near-cardinal / near-top tilt (deg) — "more
#                          cardinal" (user): the good lens + clip-top plan
#                          fallback reduce the edge-on exposure
PERP = 65.0              # near-perpendicular (deg off the original ray)
FOV_GOOD = 55.0          # natural-perspective lens for side views; the
#                          stand-off distance derives from it, not vice versa
BAND_PAD = 0.05


def to_wsl(p):
    p = str(Path(p).resolve())
    return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")


def shell_bounds(sd):
    sh = json.loads((sd / "room_shell.json").read_text())
    r2r = sh["frame"]["raw_to_render"]
    xs, zs = [], []
    for w in sh["walls"]:
        v = w["plane_upright_m"] * (r2r[0] if w["axis"] == "x" else r2r[2])
        (xs if w["axis"] == "x" else zs).append(v)
    return (min(xs), max(xs), min(zs), max(zs),
            sh["ceiling_y_raw"], sh["floor_y_raw"])


def make_cam(eye, aim, fov, res):
    M = c2w_from_eye_aim(eye, aim, [0.0, -1.0, 0.0])
    R = np.stack([M[:3, 0], -M[:3, 1], M[:3, 2]])
    f = res / (2 * math.tan(math.radians(fov) / 2))
    return MatCam(R, np.asarray(eye, np.float64), f, res / 2, res / 2,
                  res, res)


def roty(v, deg):
    th = math.radians(deg)
    ca, sa = math.cos(th), math.sin(th)
    return np.array([ca * v[0] + sa * v[2], v[1], -sa * v[0] + ca * v[2]])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--only", default="")
    ap.add_argument("--res", type=int, default=768)
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    rdir = sd / "pool_retake"
    rdir.mkdir(exist_ok=True)

    g = json.loads((sd / "scene_graph.json").read_text(encoding="utf-8"))
    nodes = g["resolved"]["nodes"]
    if a.only:
        want = set(a.only.split(","))
        nodes = [n for n in nodes if n["id"] in want]
    eye0 = np.array(json.loads((sd / "rig_sp0" / "pano_selfrender_meta.json")
                               .read_text())["eye_raw"])
    XLO, XHI, ZLO, ZHI, CEIL, FLOOR = shell_bounds(sd)

    print("[pool] loading splat ...", flush=True)
    r3 = paths.load_r3()
    xyz, rgb, _a, _r = r3.load_splat(str(paths.ply(a.scene)), opacity_min=0.3)

    def empty_at(eye):
        d = xyz - eye
        return int((np.einsum("ij,ij->i", d, d) < EMPTY_R * EMPTY_R).sum())

    def in_bounds(eye):
        return (XLO + WALL_PAD < eye[0] < XHI - WALL_PAD
                and ZLO + WALL_PAD < eye[2] < ZHI - WALL_PAD
                and CEIL + WALL_PAD < eye[1] < FLOOR - WALL_PAD)

    # ---- candidate generation + cull ----
    plans, targets = [], []
    for n in nodes:
        geo = n["geometry"]
        c = np.array(geo["center"], float)
        half = max(geo["size"]) / 2
        # good-lens rule (user): fixed natural fov, distance derived
        dist = float(np.clip(
            1.5 * max(half, 0.15) / math.tan(math.radians(FOV_GOOD) / 2),
            1.2, 4.0))
        d0 = c - eye0
        d0[1] = 0
        if np.linalg.norm(d0) < 0.3:
            d0 = np.array([1.0, 0, 0])
        d0 /= np.linalg.norm(d0)
        cands = []
        for k, base in enumerate([np.array([1.0, 0, 0]), np.array([-1.0, 0, 0]),
                                  np.array([0, 0, 1.0]), np.array([0, 0, -1.0])]):
            cands.append((f"card{k}", roty(base, OFF_AXIS)))
        tilt = math.radians(max(OFF_AXIS, 15.0))
        up_dir = np.array([math.sin(tilt) * d0[0], -math.cos(tilt),
                           math.sin(tilt) * d0[2]])   # y-down: -y is up
        cands.append(("top", up_dir / np.linalg.norm(up_dir)))
        for sgn, nm in ((1, "perpA"), (-1, "perpB")):
            cands.append((nm, -roty(d0, sgn * PERP)))
        need = 1.5 * max(half, 0.15) / math.tan(math.radians(FOV_GOOD) / 2)
        frame_clamped = dist < need - 1e-6   # object cannot fit the frame
        views = []
        stand_y = FLOOR - 1.6
        top_ok = False
        for nm, dirv in cands:
            # CARDINAL TO THE OBJECT (user): prefer the camera at the
            # object's own height (face-on), raise toward standing height
            # only when that spot fails the general cull — the cull
            # arbitrates placement, never a fixed eye level
            if nm == "top":
                heights = [max(c[1] + dirv[1] * dist, CEIL + WALL_PAD + 0.05)]
            else:
                heights = [c[1], (c[1] + stand_y) / 2, stand_y]
            eye = None
            for hy in heights:
                cand = c + dirv * dist
                cand[1] = hy
                if in_bounds(cand) and empty_at(cand) <= EMPTY_MAX:
                    eye = cand
                    break
            if eye is None:
                continue
            dist_act = float(np.linalg.norm(eye - c))
            fov = float(np.clip(math.degrees(
                2 * math.atan(1.5 * max(half, 0.15) / dist_act)), 35, 75))
            if nm == "top":
                top_ok = True
            views.append({"view": nm, "eye": [float(v) for v in eye],
                          "fov": fov})
            targets.append({"name": f"{n['id']}_{nm}", "label": n["name"],
                            "eye": [float(v) for v in eye],
                            "aim": [float(v) for v in c], "fov": fov})
        if not top_ok or frame_clamped:
            # clip-top plan view (user: "clip top for plan view if
            # needed"): camera ABOVE the ceiling, ceiling clipped out of
            # the splat — bounds/emptiness don't apply, the clip creates
            # the free space. 10-deg tilt keeps thin-vertical objects
            # from being perfectly edge-on.
            up = np.array([math.sin(math.radians(10)) * d0[0], -1.0,
                           math.sin(math.radians(10)) * d0[2]])
            up /= np.linalg.norm(up)
            # UNCLAMPED stand-off: above the clipped ceiling there is no
            # bounds limit, so even room-scale objects fit the frame
            eye = c + up * max(need, 2.0)
            fov = float(np.clip(math.degrees(
                2 * math.atan(1.5 * max(half, 0.15)
                              / float(np.linalg.norm(eye - c)))), 35, 75))
            views.append({"view": "ctop", "eye": [float(v) for v in eye],
                          "fov": fov, "clip": True})
            targets.append({"name": f"{n['id']}_ctop", "label": n["name"],
                            "eye": [float(v) for v in eye],
                            "aim": [float(v) for v in c], "fov": fov,
                            "clip_y_gt": float(CEIL + 0.08)})
        plans.append({"id": n["id"], "name": n["name"], "geo": geo,
                      "aim": [float(v) for v in c], "views": views})
        print(f"[pool] {n['id']:8s} {n['name']:16s} candidates "
              f"{len(views)} after cull "
              f"({', '.join(v['view'] for v in views)})", flush=True)

    missing = [t for t in targets
               if not (rdir / f"{t['name']}.png").exists()]
    if missing:
        tf = rdir / "pool_targets.json"
        tf.write_text(json.dumps(missing, indent=1))
        print(f"[pool] rendering {len(missing)}/{len(targets)} views ...",
              flush=True)
        cmd = ("wsl -d Ubuntu-24.04 -- bash -c \"cd /root/splat_analyzer && "
               "/root/miniconda3/envs/splatanalyzer/bin/python "
               f"'{to_wsl(HERE / 'analyzer' / 'render_targets_wsl.py')}' "
               f"--targets '{to_wsl(tf)}' --ply '{to_wsl(paths.ply(a.scene))}' "
               f"--out '{to_wsl(rdir)}' --res {a.res}\"")
        subprocess.run(cmd, check=True, timeout=7200, shell=True)

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

    # ---- sp0 plumbing (refilter source) ----
    man = json.loads((sd / "scene_manifest_pano2c_rc_f30.json").read_text())
    f30_by_id = {o["id"]: o for o in man["objects"]}
    pool_j = json.loads((sd / "rig_sp0" / "lift_poolc.json").read_text())["pool"]
    dets_all = json.loads((sd / "rig_sp0" / "seg_batched20" /
                           "detections.json").read_text())
    _vd, _vc, _vm = {}, {}, {}

    def view_cam0(view):
        if view not in _vc:
            side = json.loads((sd / "rig_sp0" / "crops" / f"{view}.json")
                              .read_text())
            _vc[view] = crop_cam_raw(side, list(eye0))
        return _vc[view]

    def view_depth0(view):
        if view not in _vd:
            _vd[view] = depth_zbuffer(xyz, view_cam0(view), near=0.2)
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
        pts = []
        for fid in node.get("members", []):
            fo = f30_by_id.get(fid)
            if not fo:
                continue
            for mi in fo.get("members", []):
                if mi >= len(pool_j):
                    continue
                m = pool_j[mi]
                mk = member_mask(m)
                if mk is None:
                    continue
                dep = view_depth0(m["view"])
                valid = mk & np.isfinite(dep)
                vs, us = np.nonzero(valid)
                if len(vs):
                    pts.append(unproject_px(
                        view_cam0(m["view"]), us.astype(np.float32),
                        vs.astype(np.float32), dep[vs, us]))
        return np.concatenate(pts) if pts else None

    # clipped point set for plan views (ceiling removed, matches the
    # clip_y_gt render)
    _clipm = xyz[:, 1] > (CEIL + 0.08)
    xyz_c, rgb_c = xyz[_clipm], rgb[_clipm]

    def try_view(p, v):
        """One pool view -> list of horizontal band constraints or None."""
        name = f"{p['id']}_{v['view']}"
        png = rdir / f"{name}.png"
        if not png.exists():
            return None, "no_render"
        vx, vr = (xyz_c, rgb_c) if v.get("clip") else (xyz, rgb)
        cam = make_cam(v["eye"], p["aim"], v["fov"], a.res)
        s = 192.0 / a.res
        cam192 = MatCam(cam.R, cam.pos, cam.f * s, cam.cx * s, cam.cy * s,
                        192, 192)
        corr = corr_check(vx, vr, cam192, png)
        if corr < CORR_MIN:
            return None, f"corr_fail({corr:+.2f})"
        geo = p["geo"]
        lo, hi = np.array(geo["aabb_min"]), np.array(geo["aabb_max"])
        corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                            for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        u, vv_, z = cam.project(corners)
        ok = z > 0.2
        if not ok.any():
            return None, "behind_cam"
        pb = [float(np.clip(u[ok].min(), 0, a.res)),
              float(np.clip(vv_[ok].min(), 0, a.res)),
              float(np.clip(u[ok].max(), 0, a.res)),
              float(np.clip(vv_[ok].max(), 0, a.res))]
        img = Image.open(png).convert("RGB")
        inputs = gd_proc(images=img, text=p["name"] + ".",
                         return_tensors="pt").to(dev)
        with torch.no_grad():
            outputs = gd(**inputs)
        det = gd_proc.post_process_grounded_object_detection(
            outputs, inputs["input_ids"], threshold=DET_THR,
            text_threshold=0.25, target_sizes=[img.size[::-1]])[0]
        best = None
        for score, box in zip(det["scores"], det["boxes"]):
            b = [float(x) for x in box]
            if ((b[2] - b[0]) >= 0.95 * a.res
                    and (b[3] - b[1]) >= 0.95 * a.res):
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
            return None, "no_redetect"
        boxes = [[[best["box"]["xmin"], best["box"]["ymin"],
                   best["box"]["xmax"], best["box"]["ymax"]]]]
        sinp = sam_proc(img, input_boxes=boxes, return_tensors="pt").to(dev)
        with torch.no_grad():
            souts = sam(**sinp, multimask_output=False)
        mask = sam_proc.image_processor.post_process_masks(
            souts.pred_masks.cpu(), sinp["original_sizes"].cpu(),
            sinp["reshaped_input_sizes"].cpu())[0].squeeze(1).numpy()[0] > 0
        # evidence overlay for the review page: winning box + mask
        try:
            from PIL import ImageDraw
            ov = img.convert("RGBA")
            layer = Image.new("RGBA", ov.size, (0, 0, 0, 0))
            ys, xs = np.nonzero(mask)
            px = layer.load()
            for yy, xx in zip(ys[::4], xs[::4]):
                px[int(xx), int(yy)] = (0, 255, 90, 100)
            ov = Image.alpha_composite(ov, layer).convert("RGB")
            dr = ImageDraw.Draw(ov)
            bx = best["box"]
            dr.rectangle([bx["xmin"], bx["ymin"], bx["xmax"], bx["ymax"]],
                         outline=(255, 40, 40), width=4)
            ov.save(rdir / f"{name}_det.png")
        except Exception:  # noqa: BLE001 — overlay is best-effort evidence
            pass
        lifted = lift_frame(vx, cam, [dict(best, label=p["name"])],
                            mask[None], view=name, keep_pts=True,
                            min_score=DET_THR)
        if not lifted or lifted[0].get("pts") is None:
            return None, "lift_empty"
        pts = lifted[0]["pts"]
        # EDGE TRUST (user: "extends beyond one square"): a detection box
        # clipped at a frame edge measured NOTHING about that side — the
        # band bound facing a clipped edge is released (same per-axis
        # edge-trust rule the lift itself uses). Both sides clipped on an
        # axis -> no band on that axis.
        tol = 3.0
        bx = best["box"]
        clip_l = bx["xmin"] <= tol
        clip_r = bx["xmax"] >= a.res - tol
        clip_t = bx["ymin"] <= tol
        clip_b = bx["ymax"] >= a.res - tol
        bands = []
        for axis_vec, lo_clip, hi_clip in (
                (cam.R[0], clip_l, clip_r),      # camera-right: u grows +
                (cam.R[1], clip_b, clip_t)):     # camera-up: top = +up
            h = np.array([axis_vec[0], 0.0, axis_vec[2]])
            nh = np.linalg.norm(h)
            if nh < abs(axis_vec[1]):        # more vertical than horizontal
                continue
            if lo_clip and hi_clip:
                continue
            h /= nh
            proj = pts @ h
            bands.append({"l": h.tolist(),
                          "lo": (-1e9 if lo_clip else
                                 float(np.percentile(proj, 2) - BAND_PAD)),
                          "hi": (1e9 if hi_clip else
                                 float(np.percentile(proj, 98) + BAND_PAD))})
        if not bands:
            return None, "no_horizontal_band"
        return bands, f"ok({best['score']:.2f})"

    results = []
    for p in plans:
        rec = {"id": p["id"], "name": p["name"],
               "before": {"size": p["geo"]["size"],
                          "aabb_min": p["geo"]["aabb_min"],
                          "aabb_max": p["geo"]["aabb_max"]},
               "views": {}}
        bands_all = []
        for v in p["views"]:
            bands, why = try_view(p, v)
            rec["views"][v["view"]] = why
            if bands:
                bands_all.extend(bands)
        rec["n_ok"] = sum(1 for w in rec["views"].values()
                          if w.startswith("ok"))
        if not bands_all:
            rec["status"] = "kept"
            results.append(rec)
            print(f"[pool] {p['id']:8s} {p['name']:16s} KEPT "
                  f"({rec['views']})", flush=True)
            continue
        node = next(n for n in nodes if n["id"] == p["id"])
        P = node_points(node)
        if P is None or len(P) < 50:
            rec["status"] = "kept_no_points"
            results.append(rec)
            continue
        keep = np.ones(len(P), bool)
        for b in bands_all:
            proj = P @ np.array(b["l"])
            keep &= (proj >= b["lo"]) & (proj <= b["hi"])
        if keep.sum() < 50:
            rec["status"] = "kept_empty_overlap"
            results.append(rec)
            print(f"[pool] {p['id']:8s} {p['name']:16s} EMPTY overlap — "
                  f"kept, flagged", flush=True)
            continue
        lo = np.percentile(P[keep], 1, axis=0)
        hi = np.percentile(P[keep], 99, axis=0)
        rec["status"] = "carved"
        rec["n_bands"] = len(bands_all)
        rec["after"] = {"aabb_min": [round(float(v), 4) for v in lo],
                        "aabb_max": [round(float(v), 4) for v in hi],
                        "size": [round(float(h_ - l_), 4)
                                 for l_, h_ in zip(lo, hi)]}
        results.append(rec)
        print(f"[pool] {p['id']:8s} {p['name']:16s} "
              f"{rec['n_ok']} views / {len(bands_all)} bands "
              f"{[round(v, 2) for v in p['geo']['size']]} -> "
              f"{[round(v, 2) for v in rec['after']['size']]}", flush=True)

    by = {}
    for r in results:
        by[r["status"]] = by.get(r["status"], 0) + 1
    report = {"scene": a.scene, "stage": "pool_retake",
              "params": {"CORR_MIN": CORR_MIN, "DET_THR": DET_THR,
                         "OFF_AXIS": OFF_AXIS, "PERP": PERP,
                         "EMPTY_MAX": EMPTY_MAX, "WALL_PAD": WALL_PAD},
              "by_status": by, "results": results}
    (rdir / "pool_report.json").write_text(json.dumps(report, indent=1))

    objs = []
    for r in results:
        if r["status"] == "carved":
            lo, hi = r["after"]["aabb_min"], r["after"]["aabb_max"]
            label = r["name"] + f" (carved {r['n_ok']}v)"
        else:
            lo, hi = r["before"]["aabb_min"], r["before"]["aabb_max"]
            label = r["name"] + f" (kept: {r['status']})"
        objs.append({"id": r["id"], "label": label, "score": 1.0,
                     "aabb_min": lo, "aabb_max": hi,
                     "center": [round((x + y) / 2, 4) for x, y in zip(lo, hi)],
                     "size": [round(y - x, 4) for x, y in zip(lo, hi)],
                     "n_detections": 1, "views": [], "flags": [r["status"]]})
    manp = {"scene": a.scene,
            "source": "experiments/pool_retake.py preview (candidate pool: "
                      "4 near-cardinal + near-top + 2 near-perp, general "
                      "bounds/emptiness cull)",
            "frame": {"space": "raw", "up": [0.0, -1.0, 0.0]},
            "n_objects": len(objs), "objects": objs}
    (sd / "scene_manifest_parallax_preview.json").write_text(
        json.dumps(manp, indent=2))
    print(f"[pool] statuses {by}; report -> pool_retake/pool_report.json; "
          f"preview written", flush=True)


if __name__ == "__main__":
    main()
