"""SP4 — recenter 2.0 on the self-rendered pano (PLAN_SELF_PANO_RIG).

Aimed second-round crops, CPU-resampled from the 8192px self-pano (GPU is
touched only by the detection pass). Three shot purposes per target object:

  completion   weak/truncated bounds -> aimed shot, admit same-label
               overlapping detections to the pool, robust re-merge
  verification single-vote objects -> aimed shot CONFIRMS or REFUTES
               (refuted objects are dropped, with evidence recorded)
  enrichment   container objects (shelf/desk/pencil holder/...) -> zoom in,
               detections contained in the parent become CHILD objects
               (`parent` + `sub_object` flag) — richness lives in a child
               layer, never fragmenting the room-scale merge

Run:  python pano_recenter.py --scene bedroom_marble
Out:  rig_sp0/rc/rc2_*.webp+.json, rig_sp0/rc_seg/, and
      scene_manifest_pano2_rc.json (objects + children).
"""
import argparse, json, math, subprocess, sys
from pathlib import Path
import numpy as np
from PIL import Image

import paths
from crop_pano import sample_equirect, crop_dirs
from lift_sweep import lift_frame, merge_per_axis, print_gap_stats
from lift_views import iou3d
from lift_sweep import containment
from pano_lift import crop_cam_raw, MIRROR
from sweep_recenter import corr_check

r3 = paths.load_r3()
HERE = Path(__file__).parent

RES = 960
FOV_MIN, FOV_MAX = 30.0, 100.0
MARGIN_FIT = 1.8         # completion/verification framing
MARGIN_ZOOM = 1.3        # enrichment framing (tighter: fill with the parent)
GATE_PEAK = 0.40
MERGE_Q = 0.05
MAX_SHOTS = 45
CONTAINERS = ("shelf", "bookshelf", "desk", "side table", "table", "bed",
              "basket", "pencil holder", "pot", "windowsill")
CHILD_CONTAIN = 0.35     # lifted box containment in parent to count as child


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--suffix", default="",
                    help="base-manifest suffix ('b' = the batched-detect "
                         "base -> reads scene_manifest_pano2b_gated.json + "
                         "lift_poolb.json, writes ..pano2b_rc.json)")
    ap.add_argument("--min-score", type=float, default=0.35,
                    help="lift admission floor for retake detections")
    ap.add_argument("--gate-peak", type=float, default=GATE_PEAK,
                    help="children confidence floor")
    ap.add_argument("--max-targets", type=int, default=0,
                    help="shot cap; 0 = UNLIMITED (default — shots are free "
                         "CPU resamples; the old 45 cap silently skipped "
                         "the most dubious late-ID objects)")
    ap.add_argument("--verify-below", type=float, default=0.35,
                    help="verify every object with peak below this (in "
                         "addition to all single-detection objects)")
    a = ap.parse_args()
    sc = a.scene
    sfx = a.suffix
    sd = paths.scene_dir(sc)
    rig = sd / "rig_sp0"
    rcdir = rig / f"rc{sfx}"
    rcdir.mkdir(exist_ok=True)
    meta = json.loads((rig / "pano_selfrender_meta.json").read_text())
    eye = np.array(meta["eye_raw"])
    man = json.loads((sd / f"scene_manifest_pano2{sfx}_gated.json").read_text())
    poolj = json.loads((rig / f"lift_pool{sfx}.json").read_text())
    pool, floor_y = poolj["pool"], poolj["floor_y"]
    vocab = json.loads((sd / "vocab.json").read_text(encoding="utf-8"))\
        .get("canonical")

    # ---------------- target selection ----------------
    targets = []
    skipped_wide = []
    for o in man["objects"]:
        purposes = []
        if o["flags"] or o["n_whole"] == 0:
            purposes.append("completion")
        if o["n_detections"] == 1 or o["score"] < a.verify_below:
            purposes.append("verification")
        if any(k == o["label"] for k in CONTAINERS):
            purposes.append("enrichment")
        if not purposes:
            continue
        c = np.array(o["center"], float)
        d_raw = c - eye
        dist = float(np.linalg.norm(d_raw))
        r = float(np.linalg.norm(o["size"])) / 2
        margin = MARGIN_ZOOM if purposes == ["enrichment"] else MARGIN_FIT
        need = math.degrees(2 * math.atan(margin * r / max(dist, 1e-6)))
        if need > FOV_MAX:
            skipped_wide.append((o["id"], o["label"], round(need, 1)))
            continue
        fov = float(np.clip(need, FOV_MIN, FOV_MAX))
        d_p = (d_raw / dist) * MIRROR      # raw -> pano frame (self-inverse)
        targets.append({"obj": o["id"], "label": o["label"],
                        "purposes": purposes, "fov": round(fov, 2),
                        "fwd_p": d_p.tolist()})
    if a.max_targets > 0:
        targets = targets[:a.max_targets]
    print(f"[sp4] {len(targets)} aimed shots "
          f"({sum(1 for t in targets if 'completion' in t['purposes'])} completion, "
          f"{sum(1 for t in targets if 'verification' in t['purposes'])} verification, "
          f"{sum(1 for t in targets if 'enrichment' in t['purposes'])} enrichment); "
          f"skipped too-wide: {skipped_wide or 'none'}", flush=True)

    # ---------------- shots: CPU resample from the pano ----------------
    Image.MAX_IMAGE_PIXELS = None
    pano = np.asarray(Image.open(rig / "pano_selfrender.png").convert("RGB"),
                      np.float32)
    PH, PW = pano.shape[:2]
    for k, t in enumerate(targets):
        name = f"rc2_{k:02d}"
        t["file"] = f"{name}.webp"
        f = rcdir / t["file"]
        side = {"file": t["file"], "cam": "0,0,0",
                "look": ",".join(f"{v:.6f}" for v in t["fwd_p"]),
                "up": "0,1,0", "fov": t["fov"], "res": f"{RES}x{RES}"}
        (rcdir / f"{name}.json").write_text(json.dumps(side, indent=2))
        if f.exists():
            continue
        cam_p = r3.Cam([0, 0, 0], np.array(t["fwd_p"]), [0, 1, 0],
                       t["fov"], RES, RES)
        img = sample_equirect(pano, crop_dirs(cam_p, RES), PW, PH)
        Image.fromarray(np.clip(img.reshape(RES, RES, 3), 0, 255)
                        .astype(np.uint8)).save(f, quality=92)
    del pano
    print("[sp4] shots resampled (CPU)", flush=True)

    # ---------------- mini-G1 every shot camera ----------------
    print("[sp4] loading splat for camera verification + lift ...", flush=True)
    xyz, rgb, _a, _r = r3.load_splat(str(paths.ply(sc)), opacity_min=0.3)
    ok_names = set()
    for t in targets:
        name = Path(t["file"]).stem
        side = json.loads((rcdir / f"{name}.json").read_text())
        cam_s = crop_cam_raw(side, eye, scale=192 / RES)
        corr = corr_check(xyz, rgb, cam_s, rcdir / t["file"])
        t["g1_corr"] = round(corr, 3)
        if corr >= 0.25:
            ok_names.add(name)
        print(f"[sp4] {t['file']} ({'+'.join(t['purposes'])}, {t['label']}): "
              f"corr {corr:+.3f} {'ok' if corr >= 0.25 else 'FAIL'}",
              flush=True)
    (rcdir / "targets.json").write_text(json.dumps(targets, indent=1))
    print(f"[sp4] verified {len(ok_names)}/{len(targets)}", flush=True)

    # ---------------- detect (GPU, paced) ----------------
    rcseg = rig / f"rc{sfx}_seg"
    if not (rcseg / "detections.json").exists():
        import os
        env = dict(os.environ, HF_HUB_OFFLINE="1")
        cmd = [sys.executable, str(HERE / "seg_views.py"), "--scene", sc,
               "--views-dir", str(rcdir), "--glob", "rc2_*.webp",
               "--out-dir", str(rcseg), "--pace", "2"]
        print("[sp4] detect+SAM on shots (paced 2s) ...", flush=True)
        subprocess.run(cmd, check=True, timeout=3600, env=env)
    rc_dets = json.loads((rcseg / "detections.json").read_text())

    # ---------------- lift shots + route by purpose ----------------
    objs_by_id = {o["id"]: o for o in man["objects"]}

    def overlaps(o, lo, hi, iou_t=0.05, con_t=0.2):
        olo, ohi = np.array(o["aabb_min"]), np.array(o["aabb_max"])
        return (iou3d(olo, ohi, lo, hi) > iou_t
                or containment(olo, ohi, lo, hi) > con_t)

    admitted, children_raw = [], []
    verif = {}
    for t in targets:
        name = Path(t["file"]).stem
        if name not in ok_names:
            continue
        maskf = rcseg / f"{name}_masks.npy"
        dets = rc_dets.get(name, [])
        if not maskf.exists() or not dets:
            if "verification" in t["purposes"]:
                verif[t["obj"]] = False
            continue
        side = json.loads((rcdir / f"{name}.json").read_text())
        cam = crop_cam_raw(side, eye)
        lifted = lift_frame(xyz, cam, dets, np.load(maskf),
                            view=name, vocab=vocab, keep_pts=False,
                            min_score=a.min_score)
        tobj = objs_by_id[t["obj"]]
        found_self = False
        for L in lifted:
            lo, hi = np.array(L["lo"]), np.array(L["hi"])
            same_as_target = (L["label"] == tobj["label"]
                              and overlaps(tobj, lo, hi))
            if same_as_target:
                found_self = True
                # completion = IN-PLACE bound refinement of the target ONLY.
                # (Re-merging admitted close-ups fragmented the room-scale
                # merge every time it was tried — G4 v1/v3 and SP4 first
                # run, weak bounds 6->49. Close-up measurements never enter
                # the pool; they update their own target's bounds.)
                admitted.append({"target": t["obj"], "lo": lo, "hi": hi,
                                 "trust": L["trust"],
                                 "trunc": L["trunc"]})
            # enrichment: contained in the parent, different label -> child
            if ("enrichment" in t["purposes"]
                    and L["label"] != tobj["label"]
                    and L["score"] >= a.gate_peak
                    and containment(np.array(tobj["aabb_min"]),
                                    np.array(tobj["aabb_max"]),
                                    lo, hi) > CHILD_CONTAIN):
                children_raw.append({**L, "parent": tobj["id"]})
        if "verification" in t["purposes"]:
            verif[t["obj"]] = found_self
        print(f"[sp4] {name}: {len(lifted)} lifted -> target "
              f"{tobj['id']} {tobj['label']} "
              f"{'re-found' if found_self else 'NOT re-found'}", flush=True)

    n_confirmed = sum(verif.values())
    print(f"[sp4] {len(admitted)} self-measurements for bound refinement; "
          f"verification {n_confirmed}/{len(verif)} confirmed; "
          f"{len(children_raw)} raw child candidates", flush=True)

    # ---------------- in-place bound refinement + verification -----------
    import copy
    objects = copy.deepcopy(man["objects"])
    by_id = {o["id"]: o for o in objects}
    n_refined = 0
    from lift_sweep import BOUND_NAMES
    for oid in {ad["target"] for ad in admitted}:
        o = by_id[oid]
        mine = [ad for ad in admitted if ad["target"] == oid]
        lo = np.array(o["aabb_min"], float)
        hi = np.array(o["aabb_max"], float)
        touched = False
        for ax in range(3):
            los = [ad["lo"][ax] for ad in mine if ad["trust"][2 * ax]]
            his = [ad["hi"][ax] for ad in mine if ad["trust"][2 * ax + 1]]
            if los and min(los) < lo[ax]:
                lo[ax] = min(los); touched = True
            if his and max(his) > hi[ax]:
                hi[ax] = max(his); touched = True
            for side, vals in ((0, los), (1, his)):
                bn = f"lower_bound_{BOUND_NAMES[2 * ax + side]}"
                if vals and bn in o["flags"]:
                    o["flags"].remove(bn); touched = True
        if touched:
            o["aabb_min"] = [round(float(v), 3) for v in lo]
            o["aabb_max"] = [round(float(v), 3) for v in hi]
            o["center"] = [round(float(v), 3) for v in (lo + hi) / 2]
            o["size"] = [round(float(v), 3) for v in hi - lo]
            if "recenter_refined" not in o["flags"]:
                o["flags"].append("recenter_refined")
            o["n_detections"] += len(mine)
            o["n_whole"] += sum(1 for ad in mine if not ad["trunc"])
            n_refined += 1
    refuted_ids = [oid for oid, okd in verif.items() if not okd]
    objects = [o for o in objects if o["id"] not in refuted_ids]
    for oid, okd in verif.items():
        if okd and oid in by_id and "retake_confirmed" not in by_id[oid]["flags"]:
            by_id[oid]["flags"].append("retake_confirmed")
    print(f"[sp4] refined bounds on {n_refined} objects; refuted+dropped: "
          f"{refuted_ids or 'none'}", flush=True)

    # ---------------- children: dedup, attach ----------------
    id_map = {oid: oid for oid in objs_by_id}   # ids stable (in-place)
    children = []
    for L in sorted(children_raw, key=lambda x: -x["score"]):
        lo, hi = np.array(L["lo"]), np.array(L["hi"])
        if any(o["label"] == L["label"] and overlaps(o, lo, hi, 0.2, 0.5)
               for o in objects):
            continue      # already known at room scale
        if any(c["label"] == L["label"] and iou3d(
                np.array(c["aabb_min"]), np.array(c["aabb_max"]),
                lo, hi) > 0.3 for c in children):
            continue      # duplicate sibling
        pid = id_map.get(L["parent"], L["parent"])
        children.append({
            "id": f"{pid}_c{sum(1 for c in children if c['parent'] == pid):02d}",
            "label": L["label"], "score": round(L["score"], 3),
            "aabb_min": [round(float(v), 3) for v in lo],
            "aabb_max": [round(float(v), 3) for v in hi],
            "center": [round(float(v), 3) for v in (lo + hi) / 2],
            "size": [round(float(v), 3) for v in hi - lo],
            "views": [L["view"]], "n_detections": 1, "n_whole":
                0 if L["trunc"] else 1,
            "parent": pid, "flags": ["sub_object"]})
    print(f"[sp4] {len(children)} children attached "
          f"({len(children_raw) - len(children)} deduped)", flush=True)

    out = {"scene": sc,
           "source": "pano_recenter.py SP4 (recenter 2.0: completion + "
                     "verification + enrichment children)",
           "frame": man["frame"], "refuted": refuted_ids,
           "n_objects": len(objects) + len(children),
           "objects": objects + children}
    outf = sd / f"scene_manifest_pano2{sfx}_rc.json"
    outf.write_text(json.dumps(out, indent=2))
    print(f"[sp4] wrote {outf}", flush=True)
    print_gap_stats("sp4 before", man["objects"], floor_y)
    print_gap_stats("sp4 after (parents only)", objects, floor_y)
    from collections import Counter
    print("[sp4] children:", dict(Counter(
        c["label"] for c in children).most_common()), flush=True)


if __name__ == "__main__":
    main()
