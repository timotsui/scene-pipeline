"""G4 — adaptive recenter on splat renders (PLAN_SPLAT_RECENTER.md).

For every G3 object with a weak bound (no member measured that side
un-clipped), take ONE aimed splat render: point at the object's merged-box
center, zoom to fit (1.8x margin), STEP BACK along the view ray if fitting
would need fov > 95 deg (the upgrade the pano could never do). Re-detect
(GPU, paced), lift with the same z-buffer mask lift, merge round 2 over the
combined pool -> scene_manifest_sweep_rc.json.

Frame discipline: renders are made by shot.py (splat-transform) with cameras
GIVEN in the RAW frame (--up 0,-1,0 for marble bundles), and every render is
verified by a mini-G1 (color z-buffer correlation vs the webp) BEFORE its
detections are lifted — no unverified frame crossing (house rule).

Run:  python sweep_recenter.py --scene bedroom_marble
      (resumable: skips renders + seg already on disk)
"""
import argparse, json, subprocess, sys, time
from pathlib import Path
import numpy as np
from PIL import Image

import paths
from lift_views import iou3d
from lift_sweep import lift_frame, merge_per_axis, containment

r3 = paths.load_r3()
HERE = Path(__file__).parent

FOV_MIN, FOV_MAX = 45.0, 110.0
FOV_STEP_BACK = 95.0     # step back rather than exceed this
FOV_TARGET = 85.0        # fov after stepping back
MARGIN = 1.8
RES = 768
MAX_TARGETS = 40
PACE_RENDER = 2.0        # GPU pacing (laptop hard-crash mitigation 07-25)
CORR_MIN = 0.25          # mini-G1 acceptance per render


def c2w_from_eye_aim(eye, aim, up_w):
    """OpenCV c2w from eye/aim + world up — MUST match the copy in
    analyzer/render_targets_wsl.py (deterministic, so a lost annotation can
    be recomputed on the Windows side)."""
    eye = np.asarray(eye, np.float64)
    fwd = np.asarray(aim, np.float64) - eye
    fwd /= np.linalg.norm(fwd)
    up_w = np.asarray(up_w, np.float64)
    right = np.cross(fwd, up_w)
    n = np.linalg.norm(right)
    if n < 1e-6:
        right = np.cross(fwd, [1.0, 0.0, 0.0])
        n = np.linalg.norm(right)
    right /= n
    down = np.cross(fwd, right)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = right, down, fwd, eye
    return M


def corr_check(xyz, rgb, cam, webp, size=192):
    """Color z-buffer through the claimed camera vs the actual render."""
    ref = Image.open(webp).convert("L").resize((size, size))
    ref = np.asarray(ref, np.float32)
    ref = (ref - ref.mean()) / (ref.std() + 1e-6)
    u, v, z = cam.project(xyz)
    ok = (z > 0.2) & np.isfinite(u) & np.isfinite(v)
    ui = np.round(u[ok]).astype(np.int64)
    vi = np.round(v[ok]).astype(np.int64)
    order = np.argsort(-z[ok])
    img = np.zeros((size, size), np.float32)
    uu, vv = ui[order], vi[order]
    inb = (uu >= 0) & (uu < size) & (vv >= 0) & (vv < size)
    img[vv[inb], uu[inb]] = rgb[ok][order][inb].mean(axis=1)
    img = (img - img.mean()) / (img.std() + 1e-6)
    return float((img * ref).mean())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--job", default="")
    ap.add_argument("--max-targets", type=int, default=MAX_TARGETS)
    a = ap.parse_args()
    sc = a.scene
    sd = paths.scene_dir(sc)
    seg = sd / "seg_sweep"
    rcdir = seg / "rc"
    rcdir.mkdir(exist_ok=True)

    man = json.loads((sd / "scene_manifest_sweep.json").read_text())
    poolj = json.loads((seg / "lift_pool.json").read_text())
    pool = poolj["pool"]
    floor_y = poolj["floor_y"]
    from analyzer.cams_from_transforms import cams_for_job
    cams, jd, tj, conv = cams_for_job(sc, a.job)

    # room extents (keep stepped-back eyes inside the room)
    xyz, rgb, _a, _r = r3.load_splat(str(paths.ply(sc)), opacity_min=0.3)
    lo_ext = np.percentile(xyz, 1, axis=0) + 0.15
    hi_ext = np.percentile(xyz, 99, axis=0) - 0.15

    # ---------- targets: weak-bound objects, best first ----------
    weak = [o for o in man["objects"] if o["flags"]]
    weak.sort(key=lambda o: -o["score"])
    weak = weak[:a.max_targets]
    print(f"[g4] {len(weak)} weak-bound targets "
          f"(of {len(man['objects'])} objects)", flush=True)

    def members_of(o):
        olo, ohi = np.array(o["aabb_min"]), np.array(o["aabb_max"])
        out = []
        for L in pool:
            if L["label"] != o["label"]:
                continue
            llo, lhi = np.array(L["lo"]), np.array(L["hi"])
            if (iou3d(olo, ohi, llo, lhi) > 0.2
                    or containment(olo, ohi, llo, lhi) > 0.5):
                out.append(L)
        return out

    tf = rcdir / "targets.json"
    if tf.exists():
        # resume: keep the planned targets (the WSL renderer annotates them
        # with file + c2w; replanning would clobber that). Delete
        # rc/targets.json to replan from scratch.
        targets = json.loads(tf.read_text())
        print(f"[g4] reusing {len(targets)} already-planned targets (resume)",
              flush=True)
        weak = []
    targets = targets if tf.exists() else []
    for o in weak:
        mem = members_of(o)
        if not mem:
            continue
        best = max(mem, key=lambda m: m["score"])
        fi = int(best["view"].split("_")[-1])
        eye = cams[fi].pos.astype(np.float64).copy()
        c = np.array(o["center"], np.float64)
        r = float(np.linalg.norm(o["size"])) / 2
        d = c - eye
        dist = float(np.linalg.norm(d))
        if dist < 1e-6:
            continue
        du = d / dist
        need = np.degrees(2 * np.arctan(MARGIN * r / dist))
        if need > FOV_STEP_BACK:      # step BACK until FOV_TARGET fits
            dist2 = MARGIN * r / np.tan(np.radians(FOV_TARGET / 2))
            eye = c - du * dist2
            eye = np.clip(eye, lo_ext, hi_ext)   # stay inside the room
            dist = float(np.linalg.norm(c - eye))
            need = np.degrees(2 * np.arctan(MARGIN * r / dist))
        fov = float(np.clip(need, FOV_MIN, FOV_MAX))
        targets.append({"obj": o["id"], "label": o["label"], "eye": eye.tolist(),
                        "aim": c.tolist(), "fov": round(fov, 2),
                        "stepped_back": bool(need > FOV_STEP_BACK - 1e-9),
                        "flags": o["flags"], "from_view": best["view"]})
    (rcdir / "targets.json").write_text(json.dumps(targets, indent=1))
    print(f"[g4] {len(targets)} aimed shots planned "
          f"({sum(1 for t in targets if t['stepped_back'])} stepped back)",
          flush=True)

    # ---------- render (analyzer gsplat path in WSL — shot.py/splat-transform
    # FAILED mechanically: blank frames + inconsistent orientation) ----------
    def to_wsl(p):
        p = str(Path(p).resolve())
        return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")
    if not all((rcdir / f"rc_{k:02d}.png").exists()
               for k in range(len(targets))):
        cmd = ("wsl -d Ubuntu-24.04 -- bash -c \"cd /root/splat_analyzer && "
               "/root/miniconda3/envs/splatanalyzer/bin/python "
               f"'{to_wsl(HERE / 'analyzer' / 'render_targets_wsl.py')}' "
               f"--targets '{to_wsl(rcdir / 'targets.json')}' "
               f"--ply '{to_wsl(paths.ply(sc))}' "
               f"--out '{to_wsl(rcdir)}' --res {RES}\"")
        print("[g4] rendering retakes via WSL gsplat ...", flush=True)
        subprocess.run(cmd, check=True, timeout=1200, shell=True)
    targets = json.loads((rcdir / "targets.json").read_text())
    # self-heal annotations (file/c2w) — deterministic from eye/aim, and an
    # interrupted earlier run can leave them missing on already-rendered pngs
    for k, t in enumerate(targets):
        t.setdefault("file", f"rc_{k:02d}.png")
        if "c2w" not in t:
            t["c2w"] = c2w_from_eye_aim(t["eye"], t["aim"],
                                        [0.0, -1.0, 0.0]).tolist()
    (rcdir / "targets.json").write_text(json.dumps(targets, indent=1))

    # ---------- mini-G1: verify every render's camera before lifting ----------
    from analyzer.cams_from_transforms import MatCam, _rows_opencv
    import math

    def cam_of(t, res):
        M = np.array(t["c2w"], np.float64)
        fl = res / (2 * math.tan(math.radians(t["fov"]) / 2))
        return MatCam(_rows_opencv(M), M[:3, 3], fl, res / 2, res / 2, res, res)

    ok_names = []
    for k, t in enumerate(targets):
        webp = rcdir / t["file"]
        corr = corr_check(xyz, rgb, cam_of(t, 192), webp)
        t["g1_corr"] = round(corr, 3)
        status = "ok" if corr >= CORR_MIN else "FAIL"
        if corr >= CORR_MIN:
            ok_names.append(Path(t["file"]).stem)
        print(f"[g4] mini-G1 {t['file']}: corr {corr:+.3f} {status}", flush=True)
    (rcdir / "targets.json").write_text(json.dumps(targets, indent=1))
    print(f"[g4] mini-G1: {len(ok_names)}/{len(targets)} renders verified",
          flush=True)

    # ---------- detect+segment the retakes (GPU, paced) ----------
    rcseg = seg / "rc_seg"
    if not (rcseg / "detections.json").exists():
        import os
        env = dict(os.environ, HF_HUB_OFFLINE="1")
        cmd = [sys.executable, str(HERE / "seg_views.py"), "--scene", sc,
               "--views-dir", str(rcdir), "--glob", "rc_*.png",
               "--out-dir", str(rcseg), "--pace", "2"]
        print("[g4] running detect+SAM on retakes (paced 2s) ...", flush=True)
        subprocess.run(cmd, check=True, timeout=1800, env=env)
    rc_dets = json.loads((rcseg / "detections.json").read_text())

    # ---------- lift retake detections ----------
    vocab = json.loads((sd / "vocab.json").read_text(encoding="utf-8"))\
        .get("canonical")
    rc_pool = []
    for t in targets:
        name = Path(t["file"]).stem
        if name not in ok_names:
            continue        # camera unverified -> its detections don't enter
        maskf = rcseg / f"{name}_masks.npy"
        dets = rc_dets.get(name, [])
        if not maskf.exists() or not dets:
            continue
        cam = cam_of(t, RES)     # the exact c2w the WSL renderer used
        lifted = lift_frame(xyz, cam, dets, np.load(maskf),
                            view=name, vocab=vocab, keep_pts=False)
        # Admission rule (v3): a retake detection enters the pool only if it
        # overlaps an EXISTING same-label object — retakes may CONFIRM and
        # refine the map, never invent objects. (v1 admitted everything:
        # 94 -> 106 objects, weak bounds 18 -> 83, collateral close-up junk.
        # v2 required matching the aimed target's label: ~0 admitted, because
        # close-ups often RE-CLASSIFY the target — itself evidence the
        # weak-bound original was junk; recorded as t["confirmed"].)
        tobj = next(o for o in man["objects"] if o["id"] == t["obj"])
        tlo, thi = np.array(tobj["aabb_min"]), np.array(tobj["aabb_max"])
        kept = []
        confirmed = False
        for L in lifted:
            llo, lhi = np.array(L["lo"]), np.array(L["hi"])
            hit = any(
                L["label"] == o2["label"]
                and (iou3d(np.array(o2["aabb_min"]), np.array(o2["aabb_max"]),
                           llo, lhi) > 0.1
                     or containment(np.array(o2["aabb_min"]),
                                    np.array(o2["aabb_max"]), llo, lhi) > 0.3)
                for o2 in man["objects"])
            if hit:
                L["source"] = "recenter"
                kept.append(L)
            if (L["label"] == tobj["label"]
                    and (iou3d(tlo, thi, llo, lhi) > 0.1
                         or containment(tlo, thi, llo, lhi) > 0.3)):
                confirmed = True
        t["confirmed"] = confirmed
        print(f"[g4] {name}: {len(lifted)} lifted, {len(kept)} admitted, "
              f"target {tobj['id']} {tobj['label']} "
              f"{'CONFIRMED' if confirmed else 'not re-found'}", flush=True)
        rc_pool.extend(kept)
    n_whole = sum(1 for L in rc_pool if not L["trunc"])
    print(f"[g4] retakes admitted: {len(rc_pool)} detections "
          f"({n_whole} un-truncated); targets confirmed: "
          f"{sum(1 for t in targets if t.get('confirmed'))}/{len(targets)}",
          flush=True)
    (rcdir / "targets.json").write_text(json.dumps(targets, indent=1))

    # ---------- merge round 2: sweep pool + retakes ----------
    def rehydrate(L):
        return {**L, "lo": np.array(L["lo"]), "hi": np.array(L["hi"])}
    full = [rehydrate(L) for L in pool] + [
        {**L, "lo": np.array(L["lo"]), "hi": np.array(L["hi"])} for L in rc_pool]
    objects = merge_per_axis(full)
    man2 = {"scene": sc, "source": "sweep_recenter.py G4 (splat-base + "
            "adaptive recenter)", "frame": man["frame"],
            "n_objects": len(objects), "objects": objects}
    outf = sd / "scene_manifest_sweep_rc.json"
    outf.write_text(json.dumps(man2, indent=2))
    print(f"[g4] wrote {outf} ({len(objects)} objects, was "
          f"{len(man['objects'])})", flush=True)

    # ---------- floor-gap acceptance stats ----------
    FL = ("bed", "wardrobe", "desk", "chair", "rug", "mat", "shelf", "table",
          "stool", "pot", "basket", "lamp")
    for tag, objs in (("G3 (before)", man["objects"]), ("G4 (after)", objects)):
        flg = np.array([floor_y - o["aabb_max"][1] for o in objs
                        if any(k in o["label"] for k in FL)])
        n_weak = sum(1 for o in objs if o["flags"])
        print(f"[g4] {tag}: {len(objs)} objects, {n_weak} weak-bound; "
              f"floor-ish gap median {np.median(flg):+.3f} "
              f"q75 {np.percentile(flg, 75):+.3f}", flush=True)


if __name__ == "__main__":
    main()
