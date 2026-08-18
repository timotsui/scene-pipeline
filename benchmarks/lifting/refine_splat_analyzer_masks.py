"""Replace Splat Analyzer's rectangular depth lift with SAM mask-pixel lift.

The detector observations and Splat Analyzer clusters are held fixed.  For
each recorded 2D box, SAM supplies a modal mask, the analyzer's renderer-aligned
depth map supplies metric depth, and the recorded camera unprojects the masked
pixels.  Per-view boxes are fused per axis with edge trust and robust bounds.

This is the paper's global mask-lift ablation, not the active plan/tunnel stage.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import torch
from PIL import Image
from transformers import SamModel, SamProcessor


EDGE_TOL_PX = 3.0
DEPTH_GAP_M = 0.40
CLUSTER_FRAC = 0.25
MIN_MASK_PX = 150
MAX_LIFT_PX = 30_000
BOUND_QUANTILE = 0.05
MAD_BOUND_M = 0.40
MAD_BOUND_K = 3.0


def _unproject(mask: np.ndarray, depth: np.ndarray, c2w: np.ndarray, K: np.ndarray):
    valid = mask & np.isfinite(depth) & (depth > 0.2)
    if int(valid.sum()) < MIN_MASK_PX:
        return None
    vs, us = np.nonzero(valid)
    ds = depth[vs, us]

    # Masks can include background through chair legs or at silhouette rims.
    # Split on empty depth intervals and retain the nearest sufficiently large
    # cluster, matching the implemented global lifter.
    order = np.argsort(ds)
    sorted_depth = ds[order]
    cuts = np.nonzero(np.diff(sorted_depth) > DEPTH_GAP_M)[0]
    bounds = [0, *(cuts + 1), len(sorted_depth)]
    need = max(MIN_MASK_PX, int(CLUSTER_FRAC * len(sorted_depth)))
    chosen = max(range(len(bounds) - 1), key=lambda i: bounds[i + 1] - bounds[i])
    for index in range(len(bounds) - 1):
        if bounds[index + 1] - bounds[index] >= need:
            chosen = index
            break
    selected = order[bounds[chosen] : bounds[chosen + 1]]
    us, vs, ds = us[selected], vs[selected], ds[selected]
    if len(ds) < MIN_MASK_PX:
        return None
    if len(ds) > MAX_LIFT_PX:
        selected = np.random.default_rng(0).choice(len(ds), MAX_LIFT_PX, replace=False)
        us, vs, ds = us[selected], vs[selected], ds[selected]

    x = (us.astype(np.float32) - K[0, 2]) / K[0, 0] * ds
    y = (vs.astype(np.float32) - K[1, 2]) / K[1, 1] * ds
    points_camera = np.stack([x, y, ds], axis=1)
    points_world = points_camera @ c2w[:3, :3].T + c2w[:3, 3]
    return np.percentile(points_world, 2, axis=0), np.percentile(points_world, 98, axis=0)


def _edge_trust(box, c2w, width, height):
    trust = [True] * 6
    right = c2w[:3, 0]
    up = -c2w[:3, 1]
    outward = []
    if box[0] <= EDGE_TOL_PX:
        outward.append(-right)
    if box[2] >= width - EDGE_TOL_PX:
        outward.append(right)
    if box[1] <= EDGE_TOL_PX:
        outward.append(up)
    if box[3] >= height - EDGE_TOL_PX:
        outward.append(-up)
    for vector in outward:
        axis = int(np.argmax(np.abs(vector)))
        trust[2 * axis + (1 if vector[axis] > 0 else 0)] = False
    return trust


def _mad_keep(values):
    if len(values) < 4:
        return values
    median = float(np.median(values))
    mad = float(np.median(np.abs(np.asarray(values) - median)))
    threshold = max(MAD_BOUND_M, MAD_BOUND_K * mad)
    kept = [value for value in values if abs(value - median) <= threshold]
    return kept or values


def _fuse(members):
    lower, upper = np.empty(3), np.empty(3)
    weak = []
    for axis in range(3):
        lows = [member["lo"][axis] for member in members if member["trust"][2 * axis]]
        highs = [member["hi"][axis] for member in members if member["trust"][2 * axis + 1]]
        if not lows:
            lows = [member["lo"][axis] for member in members]
            weak.append(2 * axis)
        if not highs:
            highs = [member["hi"][axis] for member in members]
            weak.append(2 * axis + 1)
        lows, highs = _mad_keep(lows), _mad_keep(highs)
        lower[axis] = np.percentile(lows, 100 * BOUND_QUANTILE)
        upper[axis] = np.percentile(highs, 100 * (1 - BOUND_QUANTILE))
    return lower, upper, weak


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--job", required=True, type=Path)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--mask-cache",
        type=Path,
        help="optional directory for the ordered founding masks and metadata",
    )
    parser.add_argument("--model", default="facebook/sam-vit-base")
    args = parser.parse_args()

    interactions = json.loads((args.job / "interactions.json").read_text())
    transforms = json.loads((args.job / "transforms.json").read_text())
    frames = {index: frame for index, frame in enumerate(transforms["frames"])}
    width, height = int(transforms["w"]), int(transforms["h"])
    K = np.array(
        [
            [transforms["fl_x"], 0.0, transforms["cx"]],
            [0.0, transforms["fl_y"], transforms["cy"]],
            [0.0, 0.0, 1.0],
        ],
        dtype=np.float32,
    )

    by_frame = {}
    for object_index, obj in enumerate(interactions["objects"]):
        for evidence in obj.get("frames", []):
            frame_index = int(evidence["frame_idx"])
            by_frame.setdefault(frame_index, []).append((object_index, evidence))

    device = "cuda" if torch.cuda.is_available() else "cpu"
    processor = SamProcessor.from_pretrained(args.model)
    model = SamModel.from_pretrained(args.model).to(device).eval()
    members = {index: [] for index in range(len(interactions["objects"]))}
    cached_frames = []
    if args.mask_cache:
        args.mask_cache.mkdir(parents=True, exist_ok=True)
    started = time.time()
    for progress, frame_index in enumerate(sorted(by_frame), start=1):
        frame = frames[frame_index]
        image = Image.open(args.job / frame["file_path"]).convert("RGB")
        entries = by_frame[frame_index]
        boxes = [[list(evidence["box"]) for _, evidence in entries]]
        inputs = processor(image, input_boxes=boxes, return_tensors="pt").to(device)
        with torch.no_grad():
            outputs = model(**inputs, multimask_output=False)
        masks = processor.image_processor.post_process_masks(
            outputs.pred_masks.cpu(),
            inputs["original_sizes"].cpu(),
            inputs["reshaped_input_sizes"].cpu(),
        )[0].squeeze(1).numpy().astype(bool)
        if masks.ndim == 2:
            masks = masks[None, ...]
        cache_rows = []
        if args.mask_cache:
            np.save(args.mask_cache / f"frame_{frame_index:04d}_masks.npy", masks)
        depth = np.load(args.job / "frames" / f"depth_{frame_index:04d}.npy")
        c2w = np.asarray(frame["transform_matrix"], dtype=np.float32)
        for (object_index, evidence), mask in zip(entries, masks):
            cache_row = {
                "object_index": object_index,
                "label": interactions["objects"][object_index]["label"],
                "box": [float(value) for value in evidence["box"]],
                "score": float(evidence["score"]),
            }
            lifted = _unproject(mask, depth, c2w, K)
            if lifted is None:
                cache_rows.append(cache_row)
                continue
            lower, upper = lifted
            member = {
                "lo": lower.tolist(),
                "hi": upper.tolist(),
                "trust": _edge_trust(evidence["box"], c2w, width, height),
                "frame_idx": frame_index,
                "score": float(evidence["score"]),
                "mask_pixels": int(mask.sum()),
            }
            members[object_index].append(member)
            cache_row.update(member)
            cache_rows.append(cache_row)
        if args.mask_cache:
            cached_frames.append(
                {
                    "frame_idx": frame_index,
                    "view": f"frame_{frame_index:04d}",
                    "file_path": frame["file_path"],
                    "mask_file": f"frame_{frame_index:04d}_masks.npy",
                    "entries": cache_rows,
                }
            )
        print(f"mask-lifted frame {progress}/{len(by_frame)}", flush=True)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    records, fallbacks = [], 0
    for index, obj in enumerate(interactions["objects"]):
        evidence = members[index]
        if evidence:
            lower, upper, weak = _fuse(evidence)
            source = "sam_mask_pixel_lift"
        else:
            center = np.array([obj["position"][axis] for axis in "xyz"], dtype=np.float64)
            extent_key = "scale" if "scale" in obj else "size"
            extent = np.array([obj[extent_key][axis] for axis in "xyz"], dtype=np.float64)
            lower, upper = center - extent / 2.0, center + extent / 2.0
            weak, source = list(range(6)), "splat_analyzer_fallback"
            fallbacks += 1
        records.append(
            {
                "scene_id": args.scene_id,
                "object_id": f"mask_lift_{index:04d}",
                "label": obj["label"],
                "aabb_min": [float(value) for value in lower],
                "aabb_max": [float(value) for value in upper],
                "score": float(max((entry.get("score", 0.0) for entry in obj.get("frames", [])), default=0.0)),
                "native_id": index,
                "native_metadata": {
                    "source": source,
                    "lifted_views": len(evidence),
                    "weak_bounds": weak,
                },
            }
        )
    with args.output.open("w", encoding="utf-8") as handle:
        for record in records:
            handle.write(json.dumps(record) + "\n")
    receipt = {
        "format": "splat-analyzer-sam-mask-lift-v0",
        "status": "development-smoke-not-paper-frozen",
        "scene_id": args.scene_id,
        "model": args.model,
        "input_objects": len(interactions["objects"]),
        "input_2d_observations": sum(len(values) for values in by_frame.values()),
        "processed_frames": len(by_frame),
        "mask_lifted_objects": len(records) - fallbacks,
        "fallback_objects": fallbacks,
        "elapsed_seconds": time.time() - started,
        "output": str(args.output.resolve()),
    }
    (args.output.parent / "mask_lift_receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    if args.mask_cache:
        cache_index = {
            "format": "splat-analyzer-sam-founding-masks-v1",
            "scene_id": args.scene_id,
            "source_job": str(args.job.resolve()),
            "width": width,
            "height": height,
            "frames": cached_frames,
        }
        (args.mask_cache / "index.json").write_text(
            json.dumps(cache_index, indent=2) + "\n", encoding="utf-8"
        )
    print(
        f"wrote {len(records)} objects ({fallbacks} fallbacks) in "
        f"{receipt['elapsed_seconds']:.1f} s"
    )


if __name__ == "__main__":
    main()
