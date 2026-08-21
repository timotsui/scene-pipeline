"""SP3 — lift the self-pano rig detections to a manifest (PLAN_SELF_PANO_RIG).

Chain: rig_sp0/crops sidecars (PANO frame: cam at origin, +y up) -> exact
RAW cameras via the recorded mirror mapping (pano_selfrender_meta.json:
d_raw = (x_p, -y_p, z_p), eye known by construction) -> mini-G1 verify every
crop camera (house rule) -> z-buffer mask lift (lift_sweep machinery) ->
robust per-axis merge (q=0.05) -> static vote gate (votes>=2 & peak>=0.40).

Outputs: rig_sp0/lift_pool.json + scene_manifest_pano2.json (robust) +
scene_manifest_pano2_gated.json (+vote gate). Floor-gap stats printed —
the pedestal test: min gap must be ~0 (exact camera, no registration).

Run:  python pano_lift.py --scene bedroom_marble
"""
import argparse, json
from pathlib import Path
import numpy as np

import paths
from lift_sweep import lift_frame, merge_per_axis, print_gap_stats
from analyzer.cams_from_transforms import MatCam, build_cam
from sweep_recenter import corr_check

r3 = paths.load_r3()
MIRROR = np.array([1.0, -1.0, 1.0])
CORR_MIN = 0.25
MERGE_Q = 0.05
# gate = confidence-only (user decision 2026-07-26: single-view objects must
# NOT be killed for being single-view — audit showed 12 fine-confidence
# casualties incl. a real computer monitor; votes stay recorded per object
# for the future retake-verifier, they just don't gate)
GATE_VOTES, GATE_PEAK = 1, 0.40


def crop_cam_raw(side, eye, scale=1.0):
    """Pano-frame crop sidecar -> RAW-frame MatCam. The pano frame is a
    MIRROR of raw, so the returned R is improper (det -1) — intentional:
    it maps the MIRRORED crop image's pixels to their true RAW rays, which
    is all project/unproject algebra needs."""
    fwd_p = np.array([float(t) for t in side["look"].split(",")])
    res = int(side["res"].split("x")[0])
    c = r3.Cam([0, 0, 0], fwd_p, [0, 1, 0], float(side["fov"]), res, res)
    R_raw = c.R * MIRROR[None, :]        # each row's y component negated
    return MatCam(R_raw, np.array(eye), c.f * scale, c.cx * scale,
                  c.cy * scale, int(res * scale), int(res * scale))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--seg-dir", default="",
                    help="detections dir under rig_sp0 (default seg; pass "
                         "seg_batched for the batched-vocab run)")
    ap.add_argument("--suffix", default="",
                    help="manifest name suffix (e.g. 'b' -> "
                         "scene_manifest_pano2b*.json)")
    ap.add_argument("--rig", default="rig_sp0",
                    help="rig dir (multi-standpoint: rig_sp1, ...)")
    ap.add_argument("--min-score", type=float, default=0.35,
                    help="lift admission floor (match the detect box-thr)")
    ap.add_argument("--gate-peak", type=float, default=GATE_PEAK,
                    help="confidence gate (user 2026-07-26: 0.20)")
    a = ap.parse_args()
    sc = a.scene
    sd = paths.scene_dir(sc)
    rig = sd / a.rig
    seg = rig / (a.seg_dir or "seg")
    meta = json.loads((rig / "pano_selfrender_meta.json").read_text())
    eye = meta["eye_raw"]
    print(f"[sp3] eye {eye} (defined, not estimated)", flush=True)

    dets_all = json.loads((seg / "detections.json").read_text())
    vocab = json.loads((sd / "vocab.json").read_text(encoding="utf-8"))\
        .get("canonical")

    print("[sp3] loading splat ...", flush=True)
    xyz, rgb, _a, _r = r3.load_splat(str(paths.ply(sc)), opacity_min=0.3)

    # mini-G1 every crop camera, then lift
    pool = []
    n_ok = 0
    camera_validation = []
    for view in sorted(dets_all):
        side = json.loads((rig / "crops" / f"{view}.json").read_text())
        if "transform_matrix" in side:
            cam0 = build_cam(side, side, "c2w_opencv")
            scale = 192 / side["w"]
            cam_s = MatCam(cam0.R, cam0.pos, cam0.f * scale,
                           cam0.cx * scale, cam0.cy * scale, 192, 192)
        else:
            cam_s = crop_cam_raw(side, eye, scale=192 / 960)
        corr = corr_check(xyz, rgb, cam_s, rig / "crops" / f"{view}.webp")
        ok = corr >= CORR_MIN
        n_ok += ok
        camera_validation.append({"view": view, "correlation": round(float(corr), 6),
                                  "accepted": bool(ok)})
        print(f"[sp3] {view}: cam corr {corr:+.3f} {'ok' if ok else 'FAIL'}",
              flush=True)
        if not ok:
            continue
        maskf = seg / f"{view}_masks.npy"
        if not maskf.exists() or not dets_all[view]:
            continue
        cam = (build_cam(side, side, "c2w_opencv")
               if "transform_matrix" in side else crop_cam_raw(side, eye))
        pool.extend(lift_frame(xyz, cam, dets_all[view], np.load(maskf),
                               view=view, vocab=vocab, keep_pts=False,
                               min_score=a.min_score))
    n_tr = sum(1 for L in pool if L["trunc"])
    print(f"[sp3] cams verified {n_ok}/{len(dets_all)}; lifted {len(pool)} "
          f"detections ({n_tr} edge-truncated)", flush=True)
    (rig / f"lift_camera_validation{a.suffix}.json").write_text(
        json.dumps({"threshold": CORR_MIN, "accepted": n_ok,
                    "total": len(dets_all), "views": camera_validation},
                   indent=2) + "\n", encoding="utf-8")

    floor_y = float(np.percentile(xyz[:, 1], 99))    # raw up = -y
    pj = [{k: (v.tolist() if isinstance(v, np.ndarray) else v)
           for k, v in L.items()} for L in pool]
    (rig / f"lift_pool{a.suffix}.json").write_text(json.dumps(
        {"scene": sc, "floor_y": round(floor_y, 3), "pool": pj}))

    objects = merge_per_axis(pool, q=MERGE_Q)
    n_bases = len(meta.get("base_views", [])) or 1
    frame = {"space": "raw", "up": [0.0, -1.0, 0.0],
             "floor_y": round(floor_y, 3),
             "note": f"pipeline-lifter rig lane: {len(dets_all)} views "
                     f"from {n_bases} approved base position(s), exact "
                     "defined cameras, z-buffer mask lift, per-axis robust "
                     "merge q=0.05"}
    man = {"scene": sc,
           "source": "pano_lift.py SP3 (pipeline-lifter approved multibase rig)",
           "frame": frame, "n_objects": len(objects), "objects": objects}
    outf = sd / f"scene_manifest_pano2{a.suffix}.json"
    outf.write_text(json.dumps(man, indent=2))
    print(f"[sp3] wrote {outf}", flush=True)
    print_gap_stats("sp3 robust", objects, floor_y)

    kept = [o for o in objects
            if o["n_detections"] >= GATE_VOTES and o["score"] >= a.gate_peak]
    man2 = dict(man, source=man["source"] + f" + vote gate (votes>="
                f"{GATE_VOTES} & peak>={a.gate_peak})",
                n_objects=len(kept), objects=kept)
    outf2 = sd / f"scene_manifest_pano2{a.suffix}_gated.json"
    outf2.write_text(json.dumps(man2, indent=2))
    print(f"[sp3] wrote {outf2} (gate kept {len(kept)}/{len(objects)})",
          flush=True)
    print_gap_stats("sp3 gated", kept, floor_y)
    from collections import Counter
    print("[sp3] gated labels:",
          dict(Counter(o["label"] for o in kept).most_common()), flush=True)


if __name__ == "__main__":
    main()
