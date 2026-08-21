"""Build the data payload for the interactive lift-only pipeline walkthrough.

The HTML intentionally renders evidence rather than assigning visual quality.
It reads the machine-local benchmark artifacts and emits a compact, browser-safe
summary; large PNGs and PLYs remain in the benchmark output and are streamed by
``serve_scene3d.py``.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


REPO = Path(__file__).resolve().parents[2]
OUTPUT = REPO / "benchmarks" / "lifting" / "reports" / "pipeline_walkthrough" / "data.json"
GENERATED = OUTPUT.parent / "generated"
SCENES = [
    ("ai_051_002", "Living room"),
    ("ai_002_006", "Kitchen"),
    ("ai_006_008", "Bedroom"),
    ("ai_037_007", "Dining room"),
    ("ai_003_009", "Office"),
]


def read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def compact_boxes(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    result = []
    for record in records:
        if "aabb_min" not in record or "aabb_max" not in record:
            continue
        item = {
            "id": record.get("object_id", ""),
            "label": record.get("label", "unknown"),
            "min": record["aabb_min"],
            "max": record["aabb_max"],
        }
        if record.get("score") is not None:
            item["score"] = record["score"]
        result.append(item)
    return result


def metric_slice(metrics: dict[str, Any]) -> dict[str, Any]:
    return {
        "gt": metrics.get("ground_truth_objects", 0),
        "predicted": metrics.get("predicted_objects", 0),
        "map25": metrics.get("iou25", {}).get("map"),
        "recall25": metrics.get("iou25", {}).get("mean_recall"),
        "map50": metrics.get("iou50", {}).get("map"),
        "falseDiscoveries25": metrics.get("iou25", {}).get("false_discoveries"),
        "duplicates25": metrics.get("iou25", {}).get("duplicates"),
        "medianIou": metrics.get("paired", {}).get("median_iou"),
        "medianCenterErrorM": metrics.get("paired", {}).get("median_center_error_m"),
        "perClass25": metrics.get("iou25", {}).get("per_class", {}),
    }


def artifact(relative: str) -> str:
    return f"/benchmark-artifacts/{relative.replace('\\\\', '/')}"


def active_artifact(scene_id: str, relative: str) -> str:
    return f"/active-artifacts/{scene_id}/{relative.replace(chr(92), '/')}"


def generated_artifact(relative: str) -> str:
    return (
        "/benchmarks/lifting/reports/pipeline_walkthrough/generated/"
        f"{relative.replace(chr(92), '/')}"
    )


def compact_matrix(matrix: Any) -> list[list[float]]:
    return [[round(float(value), 6) for value in row] for row in matrix]


def build_sam_evidence(
    root: Path,
    scene_id: str,
    analyzer_name: str,
) -> tuple[list[dict[str, Any]], Path | None]:
    candidates = [
        root / "predictions" / analyzer_name / "founding_masks",
        root / "predictions" / f"{scene_id}_sam_global" / "founding_masks",
    ]
    cache = next((path for path in candidates if (path / "index.json").is_file()), None)
    if cache is None:
        return [], None
    index = read_json(cache / "index.json")
    frames = []
    for frame in index.get("frames", []):
        frame_index = int(frame["frame_idx"])
        masks = np.load(cache / frame["mask_file"])
        if masks.ndim == 2:
            masks = masks[None, ...]
        entries = frame.get("entries", [])
        if len(entries) != len(masks):
            raise ValueError(
                f"{scene_id} frame {frame_index}: {len(entries)} SAM entries but "
                f"{len(masks)} saved masks"
            )
        observations = []
        for mask_index, (entry, mask) in enumerate(zip(entries, masks)):
            relative = f"sam/{scene_id}/frame_{frame_index:04d}_mask_{mask_index:03d}.png"
            output = GENERATED / relative
            output.parent.mkdir(parents=True, exist_ok=True)
            Image.fromarray(np.asarray(mask, dtype=np.uint8) * 255, mode="L").save(output)
            observations.append(
                {
                    "maskIndex": mask_index,
                    "object": int(entry["object_index"]),
                    "label": entry.get("label", "unknown"),
                    "box": [float(value) for value in entry.get("box", [])],
                    "score": entry.get("score"),
                    "maskPixels": int(np.asarray(mask, dtype=bool).sum()),
                    "lifted": "lo" in entry and "hi" in entry,
                    "lo": entry.get("lo"),
                    "hi": entry.get("hi"),
                    "trust": entry.get("trust"),
                    "mask": generated_artifact(relative),
                }
            )
        frames.append(
            {
                "frame": f"{frame_index:04d}",
                "source": artifact(
                    f"predictions/{analyzer_name}/frames/frame_{frame_index:04d}.png"
                ),
                "depth": artifact(
                    f"predictions/{analyzer_name}/frames/depth_{frame_index:04d}.png"
                ),
                "observations": observations,
            }
        )
    return frames, cache / "index.json"


def compact_slice_rule(rule: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "need_votes", "flag", "pano_flag", "outlier", "tiers",
        "culled_clusters", "shell_ineligible_dots", "plan_fill", "plan_fill2",
        "slice", "top_frame", "top_shots",
    )
    return {key: rule.get(key) for key in keys if key in rule}


def build_active_evidence(root: Path, scene_id: str) -> dict[str, Any]:
    active_root = root.parents[1] / f"hypersim_{scene_id}_active"
    report_path = active_root / "vote" / "slicevote_report.json"
    if not report_path.is_file():
        return {"ran": False, "objects": [], "visualFiles": 0}
    report = read_json(report_path)
    slices = active_root / "vote" / "slices"
    objects = []
    for result in report.get("results", []):
        object_id = result.get("id", "")
        names = sorted(
            {
                *[path.name for path in slices.glob(f"{object_id}_*.png")],
                *[path.name for path in slices.glob(f"vote_{object_id}_*.png")],
            }
        )
        assets = [
            {
                "name": asset_name,
                "url": active_artifact(scene_id, f"vote/slices/{asset_name}"),
                "kind": (
                    "detector overlay" if asset_name.endswith("_det.png")
                    else "vote render" if asset_name.startswith("vote_")
                    else "plan/top render"
                ),
            }
            for asset_name in names
        ]
        conemap = active_root / "vote" / f"conemap_{object_id}.png"
        row = active_root / "vote" / "rows" / f"{object_id}.html"
        objects.append(
            {
                "id": object_id,
                "name": result.get("name", "unknown"),
                "nviewsVote": result.get("nviews_vote"),
                "boxes": result.get("boxes", {}),
                "rule": compact_slice_rule(result.get("rule", {})),
                "assets": assets,
                "conemap": (
                    active_artifact(scene_id, f"vote/{conemap.name}")
                    if conemap.is_file() else None
                ),
                "row": (
                    active_artifact(scene_id, f"vote/rows/{object_id}.html")
                    if row.is_file() else None
                ),
            }
        )
    return {
        "ran": True,
        "status": report.get("status"),
        "runId": report.get("run_id"),
        "gate": report.get("gate"),
        "byStatus": report.get("by_status", {}),
        "objects": objects,
        "visualFiles": sum(
            len(item["assets"]) + bool(item["conemap"]) for item in objects
        ),
        "report": active_artifact(scene_id, "vote/slicevote_report.json"),
        "preview": active_artifact(scene_id, "scene_manifest_slicevote_preview.json"),
        "compatibility": active_artifact(scene_id, "benchmark_compat_manifest.json"),
    }


def build_external_evidence(root: Path, scene_id: str) -> dict[str, Any]:
    zoo_base = root / "external" / "zoo3d"
    zoo_inputs = zoo_base / "data" / "scannet" / "rec_posed_images" / scene_id
    zoo_masks = (
        zoo_base / "logs" / "output" / "scannet_posed_images" / scene_id / "mask"
    )
    zoo_frames = []
    for index in range(50):
        stem = f"{index:05d}"
        input_path = zoo_inputs / f"{stem}.jpg"
        mask_path = zoo_masks / f"{stem}.png"
        if input_path.is_file() and mask_path.is_file():
            zoo_frames.append(
                {
                    "frame": index,
                    "input": artifact(input_path.relative_to(root).as_posix()),
                    "mask": artifact(mask_path.relative_to(root).as_posix()),
                }
            )

    boxer_csv = root / "external" / "boxer" / scene_id / "scannet" / "owl_2dbbs.csv"
    detections: dict[int, list[dict[str, Any]]] = {index: [] for index in range(50)}
    if boxer_csv.is_file():
        with boxer_csv.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                index = int(row["frame_id"])
                detections.setdefault(index, []).append(
                    {
                        "label": row["name"],
                        "score": float(row["prob"]),
                        "box": [float(row[key]) for key in ("x1", "y1", "x2", "y2")],
                    }
                )
    boxer_frames = [
        {
            "frame": index,
            "input": artifact(f"prepared/{scene_id}/scannet/frames/color/{index}.png"),
            "depth": artifact(f"prepared/{scene_id}/scannet/frames/depth/{index}.png"),
            "detections": detections.get(index, []),
            "coordinateSize": [960, 960],
        }
        for index in range(50)
    ]
    return {
        "zoo3dFrames": zoo_frames,
        "boxerFrames": boxer_frames,
        "boxer2dCsv": (
            artifact(boxer_csv.relative_to(root).as_posix())
            if boxer_csv.is_file() else None
        ),
        "zoo3dPredictions": artifact(
            f"external/comparison/zoo3d/{scene_id}/predictions.jsonl"
        ),
        "boxerPredictions": artifact(
            f"external/comparison/boxer/{scene_id}/predictions.jsonl"
        ),
    }


def build_scene(root: Path, scene_id: str, name: str, summaries: dict[str, Any]) -> dict[str, Any]:
    prepared = root / "prepared" / scene_id
    analyzer_name = f"{scene_id}_splat_analyzer_medium_min1"
    analyzer = root / "predictions" / analyzer_name
    global_dir = root / "predictions" / f"{scene_id}_sam_global"
    training = root / "training" / f"{scene_id}_gsplat5000"
    verification = root / "verification" / f"{scene_id}_gsplat5000"
    manifest = read_json(prepared / "benchmark_manifest.json")
    train_receipt = read_json(training / "training_receipt.json")
    reconstruction = read_json(verification / "reconstruction_metrics.json")
    interactions = read_json(analyzer / "interactions.json")
    analyzer_transforms = read_json(analyzer / "transforms.json")
    mask_receipt_path = global_dir / "mask_lift_receipt.json"
    if not mask_receipt_path.is_file():
        mask_receipt_path = analyzer / "mask_lift_receipt.json"
    mask_receipt = read_json(mask_receipt_path)
    sam_frames, sam_index_path = build_sam_evidence(root, scene_id, analyzer_name)
    active_evidence = build_active_evidence(root, scene_id)
    external_evidence = build_external_evidence(root, scene_id)

    source_frames = []
    overlay_ids = {0, 51, 99}
    for scan_index, frame_id in enumerate(manifest.get("frame_ids", [])):
        overlay_path = prepared / "overlays" / f"frame_{frame_id:04d}.boxes.png"
        source_frames.append(
            {
                "frame": f"{frame_id:04d}",
                "scanIndex": scan_index,
                "rgb": artifact(f"prepared/{scene_id}/images/frame_{frame_id:04d}.png"),
                "depth": artifact(
                    f"prepared/{scene_id}/scannet/frames/depth/{scan_index}.png"
                ),
                "overlay": (
                    artifact(f"prepared/{scene_id}/overlays/{overlay_path.name}")
                    if frame_id in overlay_ids and overlay_path.is_file() else None
                ),
            }
        )

    analyzer_frames = sorted(
        path.stem.removeprefix("frame_")
        for path in (analyzer / "frames").glob("frame_*.png")
    )
    analyzer_frame_records = []
    transform_frames = analyzer_transforms.get("frames", [])
    for index, frame in enumerate(transform_frames):
        stem = f"{index:04d}"
        analyzer_frame_records.append(
            {
                "frame": stem,
                "positionIndex": frame.get("position_idx"),
                "matrix": compact_matrix(frame.get("transform_matrix", [])),
                "rgb": artifact(f"predictions/{analyzer_name}/frames/frame_{stem}.png"),
                "depth": artifact(f"predictions/{analyzer_name}/frames/depth_{stem}.png"),
                "depthRaw": artifact(f"predictions/{analyzer_name}/frames/depth_{stem}.npy"),
            }
        )
    detected_frames = sorted(
        (str(key).zfill(4) for key in interactions.get("frame_annotations", {})),
        key=int,
    )
    annotations: dict[str, list[dict[str, Any]]] = {}
    for key, entries in interactions.get("frame_annotations", {}).items():
        annotations[str(key).zfill(4)] = [
            {
                "label": entry.get("label", "unknown"),
                "score": entry.get("score"),
                "box": entry.get("box", []),
                "object": entry.get("object_idx"),
            }
            for entry in entries
        ]

    prediction_paths = {
        "groundTruth": prepared / "ground_truth.visible.jsonl",
        "native": analyzer / "predictions.jsonl",
        "global": global_dir / "predictions.jsonl",
        "active": root / "predictions" / f"{scene_id}_slicevote_full" / "predictions.jsonl",
        "boxer": root / "external" / "comparison" / "boxer" / scene_id / "predictions.jsonl",
        "zoo3d": root / "external" / "comparison" / "zoo3d" / scene_id / "predictions.jsonl",
    }
    boxes = {key: compact_boxes(read_jsonl(path)) for key, path in prediction_paths.items()}

    methods = summaries.get("development", {}).get("per_scene", {})
    external_methods = summaries.get("external", {}).get("per_scene", {})
    metrics: dict[str, Any] = {}
    for method in ("native", "global", "active"):
        metrics[method] = metric_slice(methods.get(method, {}).get(scene_id, {}))
    for method in ("boxer", "zoo3d"):
        metrics[method] = metric_slice(external_methods.get(method, {}).get(scene_id, {}))

    held_out = []
    for record in reconstruction.get("held_out_frames", []):
        frame = record.get("frame", "")
        held_out.append({
            "frame": frame,
            "psnrDb": record.get("psnr_db"),
            "comparison": artifact(f"verification/{scene_id}_gsplat5000/{frame}.comparison.png"),
            "render": artifact(f"verification/{scene_id}_gsplat5000/{frame}.render.png"),
        })

    counts = {
        key: len(value)
        for key, value in boxes.items()
    }
    label_counts = {
        key: dict(sorted(Counter(box["label"] for box in value).items()))
        for key, value in boxes.items()
    }
    slice_metrics_path = root / "predictions" / f"{scene_id}_slicevote_full" / "metrics.json"
    return {
        "id": scene_id,
        "name": name,
        "status": manifest.get("status", "unknown"),
        "manifest": {
            "camera": manifest.get("camera"),
            "frames": len(manifest.get("frame_ids", [])),
            "frameIds": manifest.get("frame_ids", []),
            "imageSize": manifest.get("image_size", []),
            "initialPoints": manifest.get("initial_points"),
            "allTargetBoxes": manifest.get("all_target_boxes"),
            "visibleTargetBoxes": manifest.get("visible_target_boxes"),
            "targetLabels": manifest.get("target_labels", []),
            "visibilityGate": manifest.get("visibility_gate", {}),
            "sourceFrames": source_frames,
        },
        "training": {
            "steps": train_receipt.get("steps"),
            "seconds": train_receipt.get("elapsed_seconds"),
            "plyBytes": train_receipt.get("output_ply_bytes"),
            "commit": train_receipt.get("gsplat_commit"),
            "meanPsnrDb": reconstruction.get("mean_psnr_db"),
            "heldOutRule": reconstruction.get("held_out_rule"),
            "heldOut": held_out,
        },
        "analyzer": {
            "directory": analyzer_name,
            "frames": analyzer_frames,
            "frameRecords": analyzer_frame_records,
            "detectedFrames": detected_frames,
            "annotations": annotations,
            "objects": len(interactions.get("objects", [])),
            "rawDetectionsSaved": False,
            "rawDetectionNote": (
                "interactions.json preserves only post-cluster survivors; no raw "
                "per-frame OWLv2 output or rejected-score log was saved"
            ),
            "intrinsics": {
                key: analyzer_transforms.get(key)
                for key in ("fl_x", "fl_y", "cx", "cy", "w", "h")
            },
            "sceneCenter": analyzer_transforms.get("scene_center"),
            "sceneRadius": analyzer_transforms.get("scene_radius"),
            "cameraPositions": analyzer_transforms.get("camera_positions", []),
            "lookTargets": analyzer_transforms.get("look_targets", []),
        },
        "sam": {
            "ran": bool(mask_receipt),
            "model": mask_receipt.get("model"),
            "inputObjects": mask_receipt.get("input_objects", 0),
            "observations": mask_receipt.get("input_2d_observations", 0),
            "processedFrames": mask_receipt.get("processed_frames", 0),
            "maskLifted": mask_receipt.get("mask_lifted_objects", 0),
            "fallback": mask_receipt.get("fallback_objects", 0),
            "seconds": mask_receipt.get("elapsed_seconds"),
            "frames": sam_frames,
            "savedMasks": sum(len(frame["observations"]) for frame in sam_frames),
        },
        "activeEvidence": active_evidence,
        "externalEvidence": external_evidence,
        "diagnostic": (
            {
                "status": "UNRESOLVED ZERO",
                "boundary": (
                    "reconstruction passed and 90 RGB/depth views exist; final "
                    "analyzer output contains zero objects and zero annotations"
                ),
                "known": [
                    "mean held-out reconstruction PSNR is 25.83 dB",
                    "all five standpoints and all 90 sweep poses were saved",
                    "SAM, SliceVote, and evaluation receive an empty proposal set",
                    "Zoo3D and Boxer produce nonempty outputs on the same scene",
                ],
                "missing": [
                    "raw pre-threshold OWLv2 scores",
                    "raw post-threshold detections before clustering",
                    "rejection/filter log",
                    "same-camera analyzer render versus verification-render check",
                ],
                "next": (
                    "user judges the 90 sweep RGB/depth pairs; then compare frozen "
                    "OWLv2 on source RGB, a verified-camera splat render, and sweep frames"
                ),
            }
            if scene_id == "ai_037_007" else None
        ),
        "counts": counts,
        "labelCounts": label_counts,
        "boxes": boxes,
        "metrics": metrics,
        "artifacts": {
            "source": artifact(f"prepared/{scene_id}/images/frame_0000.png"),
            "sourceMid": artifact(f"prepared/{scene_id}/images/frame_0051.png"),
            "sourceLast": artifact(f"prepared/{scene_id}/images/frame_0099.png"),
            "groundTruthOverlay": artifact(f"prepared/{scene_id}/overlays/frame_0000.boxes.png"),
            "manifest": artifact(f"prepared/{scene_id}/benchmark_manifest.json"),
            "trainingReceipt": artifact(f"training/{scene_id}_gsplat5000/training_receipt.json"),
            "reconstructionReceipt": artifact(f"verification/{scene_id}_gsplat5000/reconstruction_metrics.json"),
            "interactions": artifact(f"predictions/{analyzer_name}/interactions.json"),
            "analyzerTransforms": artifact(f"predictions/{analyzer_name}/transforms.json"),
            "nativePredictions": artifact(f"predictions/{analyzer_name}/predictions.jsonl"),
            "maskReceipt": artifact(mask_receipt_path.relative_to(root).as_posix()) if mask_receipt_path.is_file() else None,
            "samMaskIndex": (
                artifact(sam_index_path.relative_to(root).as_posix())
                if sam_index_path else None
            ),
            "globalPredictions": (
                artifact((global_dir / "predictions.jsonl").relative_to(root).as_posix())
                if (global_dir / "predictions.jsonl").is_file() else None
            ),
            "sliceMetrics": artifact(slice_metrics_path.relative_to(root).as_posix()) if slice_metrics_path.is_file() else None,
            "activePredictions": (
                artifact(prediction_paths["active"].relative_to(root).as_posix())
                if prediction_paths["active"].is_file() else None
            ),
            "boxer2dCsv": external_evidence["boxer2dCsv"],
            "boxerPredictions": external_evidence["boxerPredictions"],
            "zoo3dPredictions": external_evidence["zoo3dPredictions"],
        },
    }


def build(root: Path) -> dict[str, Any]:
    development = read_json(root / "development_summary_5scene.json")
    external = read_json(root / "external" / "comparison" / "summary.json")
    summaries = {"development": development, "external": external}
    return {
        "format": "lifting-pipeline-debugger-v2",
        "scope": "development-smoke-not-paper-frozen",
        "pipelineMap": "/pipeline_map.html",
        "viewer3d": "/benchmarks/lifting/reports/scene3d/",
        "scenes": [build_scene(root, scene_id, name, summaries) for scene_id, name in SCENES],
        "aggregate": {
            "development": development.get("methods", {}),
            "comparisons": development.get("comparisons", {}),
            "external": external.get("methods", {}),
        },
        "stages": [
            {"id": "input", "number": "01", "map": [], "name": "Benchmark input", "kind": "adapter", "ran": "5/5", "input": "Official Hypersim RGB, metric depth, cameras, and instance boxes", "operation": "Select 50 evenly spaced views; transform cameras and visible GT into one metric raw-splat frame", "output": "50 RGB-D camera records, initialized points, visible GT, and three saved GT overlays", "missing": "Only three prepared frames have pre-rendered GT overlay PNGs; all 50 RGB and depth frames are available"},
            {"id": "train", "number": "02", "map": [], "name": "Train 3D Gaussian", "kind": "prerequisite", "ran": "5/5", "input": "45 prepared RGB views, exact cameras, and initialized points", "operation": "Optimize gsplat v1.5.3 for 5,000 steps without normalizing world space", "output": "Full Gaussian PLY plus a training receipt", "missing": "The trainer did not save a per-step visual timeline"},
            {"id": "verify", "number": "03", "map": [], "name": "Hold-out verification", "kind": "prerequisite", "ran": "5/5", "input": "Trained PLY and five reserved source cameras", "operation": "Render the PLY at cameras excluded from optimization and calculate PSNR", "output": "Five render PNGs, five GT/render comparison PNGs, and reconstruction metrics", "missing": "PSNR does not explain discovery behavior at analyzer-generated cameras"},
            {"id": "sweep", "number": "04", "map": ["asp", "asw"], "name": "Standpoints + sweep", "kind": "pipeline", "ran": "5/5", "input": "Full trained PLY", "operation": "Density-sample five standpoints; render 6 azimuths × 3 elevations at 130° FOV from each", "output": "90 RGB PNGs, 90 depth PNGs, 90 raw depth arrays, poses, intrinsics, positions, and look targets", "missing": "No saved score stating whether each sampled standpoint is inside useful room space"},
            {"id": "detect", "number": "05", "map": ["adet"], "name": "OWLv2 detect + vote", "kind": "pipeline", "ran": "5/5", "input": "90 analyzer RGB renders and the frozen seven-label vocabulary", "operation": "Run OWLv2 at threshold 0.12; lift box centers through depth; cluster per label with one-vote support", "output": "Post-cluster objects plus supporting 2D boxes in interactions.json", "missing": "Raw OWLv2 scores, pre-cluster detections, and rejection logs were not saved"},
            {"id": "native", "number": "06", "map": ["a1"], "name": "Rectangular lift", "kind": "pipeline", "ran": "5/5", "input": "Post-cluster analyzer objects and their supporting 2D rectangles", "operation": "Use center-patch depth for position; derive width/height from pixels and fabricate depth extent as (width+height)/2", "output": "Axis-aligned native proposal boxes in benchmark JSONL", "missing": "This output contains no dense object mask or volumetric support"},
            {"id": "mask", "number": "07", "map": ["segb", "plift"], "name": "SAM mask lift", "kind": "adaptation", "ran": "4/5", "input": "The same saved analyzer boxes, paired RGB/depth, and camera matrices", "operation": "Prompt SAM with each box; unproject valid mask pixels; depth-cluster and robustly fuse bounds", "output": "Every saved binary SAM mask, per-view lift metadata, global 3D boxes, and receipt", "missing": "Dining has no masks because discovery supplied no boxes to prompt SAM"},
            {"id": "vote", "number": "08", "map": ["vote"], "name": "Active SliceVote", "kind": "pipeline", "ran": "4/5", "input": "Global SAM proposal boxes, founding masks, full PLY, shell, and camera sidecars", "operation": "Render fitted plan and object-centered tunnel/cardinal views; detect, cast mask-cone votes, apply gates and fallbacks", "output": "All saved plan/tunnel/vote/detection PNGs, per-object conemaps, report, and shipping boxes", "missing": "Dining has no active evidence because it has no proposal identities"},
            {"id": "evaluate", "number": "09", "map": [], "name": "Evaluate", "kind": "harness", "ran": "5/5", "input": "Visible Hypersim GT and each method's benchmark-schema boxes", "operation": "Exact-label 3D IoU matching; scene-macro AP/recall; paired diagnostics and bootstrap summary", "output": "Per-scene metrics, per-class values, pooled metrics, and input hashes", "missing": "Metrics reveal where output differs from GT but do not diagnose upstream rendering or detection"},
            {"id": "external", "number": "10", "map": [], "name": "External baselines", "kind": "adapter", "ran": "5/5", "input": "Boxer: 50 posed RGB-D frames. Zoo3D: posed frames plus 200k metric points", "operation": "Run each released proposal path; adapt native 3D output to the common AABB evaluator", "output": "50 Zoo3D input/mask pairs, all Boxer 2D boxes, both 3D prediction sets, and common metrics", "missing": "These are cross-system references, not fixed-proposal causal ablations"},
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=OUTPUT)
    args = parser.parse_args()
    root = args.benchmark_root.resolve()
    if not root.is_dir():
        parser.error(f"benchmark root does not exist: {root}")
    payload = build(root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote {args.output} ({args.output.stat().st_size:,} bytes)")


if __name__ == "__main__":
    main()
