"""HYBRID: analyzer detection + OUR lift (the 3h2 hybrid, first real test).

Keeps the analyzer's OWLv2 detections AND its object clustering exactly as
they are (interactions.json: 103 objects, each with per-frame 2D evidence
boxes) and replaces ONLY the geometry: instead of their center-pixel depth +
fabricated (w+h)/2 z-extent, every evidence box gets a SAM mask -> per-pixel
splat z-buffer depth -> 3D points -> per-detection box with edge trust, and
each object's members fuse per-axis (robust quantile). Object identity is
1:1 with theirs, so any viewer difference is purely the lift swap.

Run:  python analyzer/hybrid_lift.py --scene bedroom_marble
Out:  scene_manifest_analyzer_hybrid.json (RAW frame, same ids order)
"""
import argparse, json, sys, time
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths
from lift_views import depth_zbuffer, unproject_px, aabb_of
from lift_sweep import edge_trust, group_box, merge_per_axis, print_gap_stats
from analyzer.cams_from_transforms import cams_for_job

r3 = paths.load_r3()

MIN_MASK_PX = 150        # their frames are 512px; evidence boxes can be small
MAX_LIFT_PX = 30000
MERGE_Q = 0.05
PACE = 1.5               # GPU pacing between frames (laptop crash mitigation)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--job", default="")
    ap.add_argument("--merge", choices=["theirs", "ours"], default="theirs",
                    help="'theirs' keeps the analyzer clusters 1:1; 'ours' "
                         "flattens all evidence detections and re-merges "
                         "with our label+overlap 3D merge (their radius "
                         "clustering shreds e.g. ONE bed into 8 clusters)")
    a = ap.parse_args()
    sc = a.scene
    sd = paths.scene_dir(sc)

    cams, jd, tj, conv = cams_for_job(sc, a.job)
    inter = json.loads((jd / "interactions.json").read_text())
    objs = inter["objects"]
    by_frame = {}
    for oi, o in enumerate(objs):
        for fr in o["frames"]:
            by_frame.setdefault(fr["frame_idx"], []).append(
                (oi, fr["box"], fr["score"]))
    print(f"[hybrid] {len(objs)} analyzer objects, "
          f"{sum(len(v) for v in by_frame.values())} evidence boxes over "
          f"{len(by_frame)} frames (cams {conv})", flush=True)

    poolf = sd / "analyzer" / "hybrid_pool.json"
    if poolf.exists():
        pj = json.loads(poolf.read_text())
        pool, floor_y = pj["pool"], pj["floor_y"]
        print(f"[hybrid] reusing lifted pool ({len(pool)} members)", flush=True)
    else:
        print("[hybrid] loading splat ...", flush=True)
        xyz, rgb, _al, _r = r3.load_splat(str(paths.ply(sc)), opacity_min=0.3)

        import torch
        from transformers import SamModel, SamProcessor
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        sam = SamModel.from_pretrained("facebook/sam-vit-base").to(dev)
        sam_proc = SamProcessor.from_pretrained("facebook/sam-vit-base")

        pool = []
        n_frames = 0
        for fi in sorted(by_frame):
            cam = cams[fi]
            imgf = jd / "frames" / f"frame_{fi:04d}.png"
            if not imgf.exists():
                continue
            img = Image.open(imgf).convert("RGB")
            entries = by_frame[fi]
            boxes = [[list(b) for _, b, _ in entries]]
            sinp = sam_proc(img, input_boxes=boxes,
                            return_tensors="pt").to(dev)
            with torch.no_grad():
                souts = sam(**sinp, multimask_output=False)
            masks = sam_proc.image_processor.post_process_masks(
                souts.pred_masks.cpu(), sinp["original_sizes"].cpu(),
                sinp["reshaped_input_sizes"].cpu())[0]
            masks = masks.squeeze(1).numpy().astype(bool)
            depth = depth_zbuffer(xyz, cam, near=0.2)
            for (oi, b, score), mask in zip(entries, masks):
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
                    sel = np.random.default_rng(0).choice(
                        len(ds), MAX_LIFT_PX, replace=False)
                    us, vs, ds = us[sel], vs[sel], ds[sel]
                pts = unproject_px(cam, us.astype(np.float32),
                                   vs.astype(np.float32), ds)
                lo, hi = aabb_of(pts)
                trust, trunc = edge_trust(
                    {"xmin": b[0], "ymin": b[1],
                     "xmax": b[2], "ymax": b[3]}, cam)
                pool.append({"analyzer_idx": oi, "label": objs[oi]["label"],
                             "lo": lo.tolist(), "hi": hi.tolist(),
                             "trust": trust, "trunc": trunc,
                             "score": score, "view": f"frame_{fi:04d}"})
            n_frames += 1
            if n_frames % 25 == 0:
                print(f"[hybrid] {n_frames}/{len(by_frame)} frames",
                      flush=True)
            time.sleep(PACE)
        floor_y = float(np.percentile(xyz[:, 1], 99))
        poolf.write_text(json.dumps({"floor_y": round(floor_y, 3),
                                     "pool": pool}))
        print(f"[hybrid] saved pool ({len(pool)} members)", flush=True)

    if a.merge == "ours":
        # discard their radius clustering (it shreds one bed into 8
        # clusters); our label + 3D-overlap merge over the lifted boxes
        out_objs = merge_per_axis(pool, q=MERGE_Q)
        n_dropped = 0
    else:
        members = {}
        for m in pool:
            members.setdefault(m["analyzer_idx"], []).append(m)
        out_objs = []
        n_dropped = sum(1 for oi in range(len(objs)) if oi not in members)
        for oi, o in enumerate(objs):
            mems = members.get(oi, [])
            if not mems:
                continue
            lo, hi, weak = group_box(mems, q=MERGE_Q)
            flags = [f"lower_bound_{w}" for w in weak]
            out_objs.append({
                "id": f"obj_{len(out_objs):03d}",
                "analyzer_idx": oi, "label": o["label"],
                "score": round(max(m["score"] for m in mems), 3),
                "aabb_min": [round(float(v), 3) for v in lo],
                "aabb_max": [round(float(v), 3) for v in hi],
                "center": [round(float(v), 3) for v in (lo + hi) / 2],
                "size": [round(float(v), 3) for v in hi - lo],
                "views": sorted({m["view"] for m in mems}),
                "n_detections": len(mems),
                "n_whole": sum(1 for m in mems if not m["trunc"]),
                "flags": flags})
    man = {"scene": sc,
           "source": "analyzer/hybrid_lift.py — analyzer OWLv2 detection, "
                     "OUR SAM+z-buffer lift, merge=" + a.merge,
           "frame": {"space": "raw", "up": [0.0, -1.0, 0.0],
                     "floor_y": round(floor_y, 3),
                     "camera_convention": conv},
           "n_objects": len(out_objs), "objects": out_objs}
    outf = sd / ("scene_manifest_analyzer_hybrid_ours.json"
                 if a.merge == "ours"
                 else "scene_manifest_analyzer_hybrid.json")
    outf.write_text(json.dumps(man, indent=2))
    print(f"[hybrid] wrote {outf} ({len(out_objs)} objects; {n_dropped} "
          f"dropped with no liftable evidence)", flush=True)
    print_gap_stats("hybrid", out_objs, floor_y)

    # geometry delta vs their own lift (bridged boxes)
    bridged = json.loads((sd / "analyzer" / "bridged_boxes.json").read_text())
    bmap = {i: o for i, o in enumerate(bridged.get("objects", []))}
    dys, vol_ratio = [], []
    for o in out_objs:
        b = bmap.get(o.get("analyzer_idx"))
        if not b:
            continue
        dys.append(o["center"][1] - b["center"][1])
        vb = max(np.prod(b["size"]), 1e-9)
        vol_ratio.append(np.prod(o["size"]) / vb)
    if dys:
        print(f"[hybrid] vs their lift: center dy median {np.median(dys):+.3f} "
              f"m; volume ratio median {np.median(vol_ratio):.2f}x "
              f"(q25 {np.percentile(vol_ratio, 25):.2f} "
              f"q75 {np.percentile(vol_ratio, 75):.2f})", flush=True)


if __name__ == "__main__":
    main()
