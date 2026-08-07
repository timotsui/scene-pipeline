"""Parallax retake — carve ray-streak boxes with a second standpoint
(PROTOTYPE 2026-08-06, user idea "different viewpoint, only the overlap
is the object").

WHY: the whole rig is ONE standpoint (every crop is a resample of one
pano), so all views share the same rays — the box's extent along the ray
comes only from splat z-buffer depth, which leaks through thin geometry
(porosity: 41% of the book-mask pixels measured the floor behind it, in a
gapless ramp no statistic can cut). A camera at a genuinely different
position sees that streak side-on: its own measurement of the object is
streaked along ITS ray instead, and the INTERSECTION of the two boxes
kills both streaks (each box is correct in the dimensions perpendicular
to its own ray).

UNIFORM, NO SUSPECTS: runs on every resolved node (no human flags, no
tuned trigger — prime directive). Per node:
  1. side eye: rotate the pano-eye->object direction 90 deg about y,
     stand off at ~2.2x the box's largest dim, clamped inside the shell
  2. render via the WSL gsplat renderer (batch, resumable)
  3. mini-G1 corr check on every retake camera (house rule >= 0.25)
  4. GroundingDINO re-detect the node's name in the retake, best overlap
     with the reprojected box; SAM -> mask
  5. lift the mask (lift_frame: same cluster+trim rules) -> side box
  6. carved = intersection(original, side box)
Degrades conservatively at every step: corr fail / no re-detection /
empty intersection -> keep the original box, record status. Output is a
PREVIEW (report + viewer manifest); nothing canonical is touched.

Run:  python experiments/parallax_retake.py --scene living_marble
      [--only obj_004,obj_039] [--res 768]
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
from sweep_recenter import corr_check, c2w_from_eye_aim  # noqa: E402
from analyzer.cams_from_transforms import MatCam  # noqa: E402

CORR_MIN = 0.25
DET_THR = 0.20
WALL_PAD = 0.30


def to_wsl(p):
    p = str(Path(p).resolve())
    return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")


def shell_bounds(sd):
    sh = json.loads((sd / "room_shell.json").read_text())
    # walls are in upright frame; raw = upright * r2r (r2r self-inverse)
    r2r = sh["frame"]["raw_to_render"]
    xs, zs = [], []
    for w in sh["walls"]:
        v = w["plane_upright_m"]
        (xs if w["axis"] == "x" else zs).append(
            v * (r2r[0] if w["axis"] == "x" else r2r[2]))
    return (min(xs), max(xs), min(zs), max(zs),
            sh["ceiling_y_raw"], sh["floor_y_raw"])


def make_cam(eye, aim, fov, res):
    M = c2w_from_eye_aim(eye, aim, [0.0, -1.0, 0.0])
    R = np.stack([M[:3, 0], -M[:3, 1], M[:3, 2]])   # rows right, up, fwd
    f = res / (2 * math.tan(math.radians(fov) / 2))
    return MatCam(R, np.asarray(eye, np.float64), f, res / 2, res / 2, res, res)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--only", default="", help="comma list of node ids")
    ap.add_argument("--res", type=int, default=768)
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    rdir = sd / "parallax_retake"
    rdir.mkdir(exist_ok=True)

    g = json.loads((sd / "scene_graph.json").read_text(encoding="utf-8"))
    nodes = g["resolved"]["nodes"]
    if a.only:
        want = set(a.only.split(","))
        nodes = [n for n in nodes if n["id"] in want]
    eye0 = json.loads((sd / "rig_sp0" / "pano_selfrender_meta.json")
                      .read_text())["eye_raw"]
    XLO, XHI, ZLO, ZHI, CEIL, FLOOR = shell_bounds(sd)

    # ---- plan side cameras (A = first viable side, B = the other side) ----
    def clamp_eye(eye, cy):
        eye[0] = float(np.clip(eye[0], XLO + WALL_PAD, XHI - WALL_PAD))
        eye[2] = float(np.clip(eye[2], ZLO + WALL_PAD, ZHI - WALL_PAD))
        eye[1] = min(max(cy - 0.2, CEIL + 0.35), FLOOR - 0.35)
        return eye

    plans, targets = [], []
    for n in nodes:
        geo = n["geometry"]
        c = np.array(geo["center"])
        half = max(geo["size"]) / 2
        d0 = c - np.array(eye0)
        d0[1] = 0
        if np.linalg.norm(d0) < 0.3:
            d0 = np.array([1.0, 0, 0])
        d0 /= np.linalg.norm(d0)
        dist = float(np.clip(2.2 * max(half * 2, 0.4), 1.0, 3.5))
        eyes = []
        # NEAR-perpendicular, not perpendicular (user 2026-08-06): a thin
        # object viewed exactly edge-on is a line no detector can find.
        # 65 deg off the original ray keeps 91% of the parallax (sin65)
        # while 42% of the face stays visible (cos65).
        for sgn in (1, -1):
            th = math.radians(65.0) * sgn
            ca, sa = math.cos(th), math.sin(th)
            dirv = np.array([ca * d0[0] + sa * d0[2], 0,
                             -sa * d0[0] + ca * d0[2]])
            eyes.append(clamp_eye(c - dirv * dist, c[1]))
        dist_act = float(np.linalg.norm(np.array(eyes[0]) - c))
        fov = float(np.clip(math.degrees(
            2 * math.atan(1.5 * max(half, 0.15) / dist_act)), 35, 75))
        plans.append({"id": n["id"], "name": n["name"], "eye": list(eyes[0]),
                      "eye_b": list(eyes[1]), "aim": [float(v) for v in c],
                      "fov": fov, "geo": geo})
        targets.append({"name": n["id"], "label": n["name"],
                        "eye": list(map(float, eyes[0])),
                        "aim": [float(v) for v in c], "fov": fov})

    tf = rdir / "retake_targets.json"
    tf.write_text(json.dumps(targets, indent=1))
    missing = [p for p in plans if not (rdir / f"{p['id']}.png").exists()]
    if missing:
        print(f"[retake] rendering {len(missing)}/{len(plans)} side views "
              f"via WSL gsplat ...", flush=True)
        cmd = ("wsl -d Ubuntu-24.04 -- bash -c \"cd /root/splat_analyzer && "
               "/root/miniconda3/envs/splatanalyzer/bin/python "
               f"'{to_wsl(HERE / 'analyzer' / 'render_targets_wsl.py')}' "
               f"--targets '{to_wsl(tf)}' --ply '{to_wsl(paths.ply(a.scene))}' "
               f"--out '{to_wsl(rdir)}' --res {a.res}\"")
        subprocess.run(cmd, check=True, timeout=3600, shell=True)

    print("[retake] loading splat ...", flush=True)
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

    # ---- original-rig plumbing for the point-level refilter ----
    from lift_views import unproject_px
    from pano_lift import crop_cam_raw
    from lift_views import depth_zbuffer
    man = json.loads((sd / "scene_manifest_pano2c_rc_f30.json").read_text())
    f30_by_id = {o["id"]: o for o in man["objects"]}
    pool = json.loads((sd / "rig_sp0" / "lift_poolc.json").read_text())["pool"]
    dets_all = json.loads((sd / "rig_sp0" / "seg_batched20" /
                           "detections.json").read_text())
    _vdepth, _vcam, _vmasks = {}, {}, {}

    def view_cam(view):
        if view not in _vcam:
            side = json.loads((sd / "rig_sp0" / "crops" / f"{view}.json")
                              .read_text())
            _vcam[view] = crop_cam_raw(side, eye0)
        return _vcam[view]

    def view_depth(view):
        if view not in _vdepth:
            _vdepth[view] = depth_zbuffer(xyz, view_cam(view), near=0.2)
        return _vdepth[view]

    def member_mask(m):
        view = m["view"]
        if view not in _vmasks:
            f = sd / "rig_sp0" / "seg_batched20" / f"{view}_masks.npy"
            _vmasks[view] = np.load(f) if f.exists() else None
        masks = _vmasks[view]
        if masks is None:
            return None
        for i, d in enumerate(dets_all.get(view, [])):
            if all(abs(d["box"][k] - m["box"][k]) < 1.0 for k in m["box"]):
                return masks[i] if i < len(masks) else None
        return None

    def refilter_points(node, ax, interval):
        """The user's overlap idea at POINT level: keep only the original
        masks' 3D points inside the side-view-established ray interval;
        re-derive the whole box from the survivors (fixes the vertical
        bloat too — leaked points fail the interval test)."""
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
                if not len(vs):
                    continue
                ds = dep[vs, us]
                pts = unproject_px(view_cam(m["view"]),
                                   us.astype(np.float32),
                                   vs.astype(np.float32), ds)
                keep = ((pts[:, ax] >= interval[0] - 0.05)
                        & (pts[:, ax] <= interval[1] + 0.05))
                if keep.any():
                    pts_all.append(pts[keep])
        if not pts_all:
            return None
        P = np.concatenate(pts_all)
        if len(P) < 50:
            return None
        lo = np.percentile(P, 1, axis=0)
        hi = np.percentile(P, 99, axis=0)
        return lo, hi

    def attempt(p, eye, png):
        """One retake attempt from one side eye. Returns a rec dict."""
        nid, geo = p["id"], p["geo"]
        rec = {"id": nid, "name": p["name"], "eye": list(eye),
               "fov": p["fov"],
               "before": {"size": geo["size"], "aabb_min": geo["aabb_min"],
                          "aabb_max": geo["aabb_max"]}}
        if not png.exists():
            rec["status"] = "no_render"
            return rec
        cam = make_cam(eye, p["aim"], p["fov"], a.res)
        # corr_check compares at 192 px and expects a 192-scaled camera
        # (same contract as pano_lift's scale=192/960 call)
        s = 192.0 / a.res
        cam192 = MatCam(cam.R, cam.pos, cam.f * s, cam.cx * s, cam.cy * s,
                        192, 192)
        corr = corr_check(xyz, rgb, cam192, png)
        rec["corr"] = round(corr, 3)
        if corr < CORR_MIN:
            rec["status"] = "corr_fail"
            return rec
        lo, hi = np.array(geo["aabb_min"]), np.array(geo["aabb_max"])
        corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                            for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
        u, v, z = cam.project(corners)
        ok = z > 0.2
        if not ok.any():
            rec["status"] = "behind_cam"
            return rec
        pb = [float(np.clip(u[ok].min(), 0, a.res)),
              float(np.clip(v[ok].min(), 0, a.res)),
              float(np.clip(u[ok].max(), 0, a.res)),
              float(np.clip(v[ok].max(), 0, a.res))]
        img = Image.open(png).convert("RGB")
        inputs = gd_proc(images=img, text=p["name"] + ".",
                         return_tensors="pt").to(dev)
        with torch.no_grad():
            outputs = gd(**inputs)
        det = gd_proc.post_process_grounded_object_detection(
            outputs, inputs["input_ids"], threshold=DET_THR,
            text_threshold=0.25, target_sizes=[img.size[::-1]])[0]
        best, best_ov = None, 0.0
        for score, box in zip(det["scores"], det["boxes"]):
            b = [float(x) for x in box]
            ix0, iy0 = max(b[0], pb[0]), max(b[1], pb[1])
            ix1, iy1 = min(b[2], pb[2]), min(b[3], pb[3])
            inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
            area = (b[2] - b[0]) * (b[3] - b[1]) + 1e-9
            ov = inter / area
            if ov > best_ov:
                best_ov, best = ov, {"score": float(score), "box": {
                    "xmin": b[0], "ymin": b[1], "xmax": b[2], "ymax": b[3]}}
        if best is None or best_ov < 0.3:
            rec["status"] = "no_redetect"
            return rec
        boxes = [[[best["box"]["xmin"], best["box"]["ymin"],
                   best["box"]["xmax"], best["box"]["ymax"]]]]
        sinp = sam_proc(img, input_boxes=boxes, return_tensors="pt").to(dev)
        with torch.no_grad():
            souts = sam(**sinp, multimask_output=False)
        mask = sam_proc.image_processor.post_process_masks(
            souts.pred_masks.cpu(), sinp["original_sizes"].cpu(),
            sinp["reshaped_input_sizes"].cpu())[0].squeeze(1).numpy()[0] > 0
        lifted = lift_frame(xyz, cam, [dict(best, label=p["name"])],
                            mask[None], view=f"retake_{nid}", keep_pts=False,
                            min_score=DET_THR)
        if not lifted:
            rec["status"] = "lift_empty"
            return rec
        slo, shi = np.array(lifted[0]["lo"]), np.array(lifted[0]["hi"])
        # axis-aware trust: a view is untrusted only ALONG ITS OWN RAY —
        # the retake establishes the original's ray-axis interval (the
        # side view measures that axis laterally, i.e. trusted).
        d0h = np.array(p["aim"]) - np.array(eye0)
        ax_or = 0 if abs(d0h[0]) >= abs(d0h[2]) else 2
        interval = (max(lo[ax_or], slo[ax_or]), min(hi[ax_or], shi[ax_or]))
        if interval[1] <= interval[0]:
            rec["status"] = "no_overlap"
            rec["side_box"] = {"lo": slo.tolist(), "hi": shi.tolist()}
            return rec
        rec["side_box"] = {"lo": [round(float(x), 4) for x in slo],
                           "hi": [round(float(x), 4) for x in shi],
                           "det_score": best["score"]}
        # v2: point-level refilter through the established interval — the
        # original views' own points, restricted to the true depth slab,
        # re-derive every axis (kills the vertical streak as well)
        node = next(n for n in nodes if n["id"] == nid)
        ref = refilter_points(node, ax_or, interval)
        if ref is not None:
            ilo, ihi = ref
            rec["method"] = "point_refilter"
        else:
            ilo, ihi = np.array(lo), np.array(hi)
            ilo[ax_or], ihi[ax_or] = interval
            rec["method"] = "axis_carve"
        rec["status"] = "carved"
        rec["after"] = {"aabb_min": [round(float(x), 4) for x in ilo],
                        "aabb_max": [round(float(x), 4) for x in ihi],
                        "size": [round(float(h - l), 4)
                                 for l, h in zip(ilo, ihi)]}
        return rec

    FAIL = ("no_render", "corr_fail", "behind_cam", "no_redetect",
            "lift_empty", "no_overlap")
    results = {}
    for p in plans:
        rec = attempt(p, p["eye"], rdir / f"{p['id']}.png")
        results[p["id"]] = rec
        if rec["status"] == "carved":
            print(f"[retake] {p['id']:8s} {p['name']:16s} "
                  f"corr {rec.get('corr', 0):+.2f} {rec['method']} "
                  f"{[round(v, 2) for v in rec['before']['size']]} -> "
                  f"{[round(v, 2) for v in rec['after']['size']]}", flush=True)
        else:
            print(f"[retake] {p['id']} A-side {rec['status']} — trying B",
                  flush=True)

    # ---- plan-B pass: re-render failures from the other side ----
    retry = [p for p in plans if results[p["id"]]["status"] in FAIL]
    if retry:
        tb = [{"name": p["id"] + "_b", "label": p["name"],
               "eye": list(map(float, p["eye_b"])),
               "aim": p["aim"], "fov": p["fov"]} for p in retry
              if not (rdir / f"{p['id']}_b.png").exists()]
        if tb:
            tfb = rdir / "retake_targets_b.json"
            tfb.write_text(json.dumps(tb, indent=1))
            print(f"[retake] B-side: rendering {len(tb)} views ...", flush=True)
            cmd = ("wsl -d Ubuntu-24.04 -- bash -c \"cd /root/splat_analyzer && "
                   "/root/miniconda3/envs/splatanalyzer/bin/python "
                   f"'{to_wsl(HERE / 'analyzer' / 'render_targets_wsl.py')}' "
                   f"--targets '{to_wsl(tfb)}' "
                   f"--ply '{to_wsl(paths.ply(a.scene))}' "
                   f"--out '{to_wsl(rdir)}' --res {a.res}\"")
            subprocess.run(cmd, check=True, timeout=3600, shell=True)
        for p in retry:
            rec = attempt(p, p["eye_b"], rdir / f"{p['id']}_b.png")
            if rec["status"] == "carved":
                rec["side"] = "B"
                results[p["id"]] = rec
                print(f"[retake] {p['id']:8s} {p['name']:16s} B-side "
                      f"{rec['method']} "
                      f"{[round(v, 2) for v in rec['before']['size']]} -> "
                      f"{[round(v, 2) for v in rec['after']['size']]}",
                      flush=True)
            else:
                results[p["id"]]["status_b"] = rec["status"]
                print(f"[retake] {p['id']} B-side {rec['status']} — kept "
                      f"original, flagged", flush=True)
    results = list(results.values())

    report = {"scene": a.scene, "stage": "parallax_retake", "res": a.res,
              "params": {"CORR_MIN": CORR_MIN, "DET_THR": DET_THR},
              "n_nodes": len(plans),
              "n_carved": sum(1 for r in results if r["status"] == "carved"),
              "by_status": {},
              "results": results}
    for r in results:
        report["by_status"][r["status"]] = \
            report["by_status"].get(r["status"], 0) + 1
    (rdir / "retake_report.json").write_text(json.dumps(report, indent=1))

    objs = []
    for r in results:
        if r["status"] != "carved":
            continue
        af = r["after"]
        objs.append({"id": r["id"], "label": r["name"] + " (carved)",
                     "score": 1.0, "aabb_min": af["aabb_min"],
                     "aabb_max": af["aabb_max"],
                     "center": [round((l + h) / 2, 4) for l, h in
                                zip(af["aabb_min"], af["aabb_max"])],
                     "size": af["size"], "n_detections": 2, "views": [],
                     "flags": ["parallax_carved"]})
    man = {"scene": a.scene, "source": "experiments/parallax_retake.py preview",
           "frame": {"space": "raw", "up": [0.0, -1.0, 0.0]},
           "n_objects": len(objs), "objects": objs}
    (sd / "scene_manifest_parallax_preview.json").write_text(
        json.dumps(man, indent=2))
    print(f"[retake] {report['n_carved']}/{len(plans)} carved; statuses "
          f"{report['by_status']}; report -> parallax_retake/retake_report.json")


if __name__ == "__main__":
    main()
