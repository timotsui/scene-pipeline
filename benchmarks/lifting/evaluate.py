"""Small, deterministic evaluator for the lifting benchmark v0 schema."""

from __future__ import annotations

import argparse
import json
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.optimize import linear_sum_assignment


def load_jsonl(path):
    records = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            record = json.loads(line)
            validate_record(record, path, line_no)
            records.append(record)
    return records


def validate_record(record, path="<memory>", line_no=0):
    required = ("scene_id", "object_id", "label", "aabb_min", "aabb_max")
    missing = [key for key in required if key not in record]
    if missing:
        raise ValueError(f"{path}:{line_no}: missing {missing}")
    lo = np.asarray(record["aabb_min"], dtype=float)
    hi = np.asarray(record["aabb_max"], dtype=float)
    if lo.shape != (3,) or hi.shape != (3,):
        raise ValueError(f"{path}:{line_no}: boxes must have three axes")
    if not np.isfinite(lo).all() or not np.isfinite(hi).all():
        raise ValueError(f"{path}:{line_no}: non-finite box")
    if np.any(hi <= lo):
        raise ValueError(f"{path}:{line_no}: non-positive box extent")


def iou3d(left, right):
    a0, a1 = np.asarray(left["aabb_min"]), np.asarray(left["aabb_max"])
    b0, b1 = np.asarray(right["aabb_min"]), np.asarray(right["aabb_max"])
    overlap = np.maximum(0.0, np.minimum(a1, b1) - np.maximum(a0, b0))
    inter = float(np.prod(overlap))
    va = float(np.prod(a1 - a0))
    vb = float(np.prod(b1 - b0))
    union = va + vb - inter
    return inter / union if union > 0 else 0.0


def _groups(records):
    grouped = defaultdict(list)
    for record in records:
        grouped[(str(record["scene_id"]), str(record["label"]))].append(record)
    return grouped


def hungarian_pairs(ground_truth, predictions):
    gt_groups, pred_groups = _groups(ground_truth), _groups(predictions)
    pairs = []
    for key in sorted(set(gt_groups) | set(pred_groups)):
        gt, pred = gt_groups[key], pred_groups[key]
        if not gt or not pred:
            continue
        matrix = np.asarray([[iou3d(g, p) for p in pred] for g in gt])
        rows, cols = linear_sum_assignment(-matrix)
        for row, col in zip(rows, cols):
            pairs.append((gt[row], pred[col], float(matrix[row, col])))
    return pairs


def _ap_for_label(gt, pred, threshold):
    gt_by_scene = defaultdict(list)
    for item in gt:
        gt_by_scene[item["scene_id"]].append(item)
    used = {scene: set() for scene in gt_by_scene}
    ranked = sorted(pred, key=lambda item: float(item.get("score", 1.0)), reverse=True)
    tp, fp, duplicate = [], [], 0
    for item in ranked:
        candidates = gt_by_scene.get(item["scene_id"], [])
        overlaps = [iou3d(target, item) for target in candidates]
        best = int(np.argmax(overlaps)) if overlaps else -1
        best_iou = overlaps[best] if best >= 0 else 0.0
        if best_iou >= threshold and best not in used.get(item["scene_id"], set()):
            used[item["scene_id"]].add(best)
            tp.append(1.0)
            fp.append(0.0)
        else:
            if best_iou >= threshold and best in used.get(item["scene_id"], set()):
                duplicate += 1
            tp.append(0.0)
            fp.append(1.0)
    if not gt:
        return None
    if not ranked:
        return {"ap": 0.0, "recall": 0.0, "false_discoveries": 0, "duplicates": 0}
    tp_cum, fp_cum = np.cumsum(tp), np.cumsum(fp)
    recall = tp_cum / len(gt)
    precision = tp_cum / np.maximum(tp_cum + fp_cum, 1e-12)
    mrec = np.concatenate(([0.0], recall, [1.0]))
    mpre = np.concatenate(([0.0], precision, [0.0]))
    for index in range(len(mpre) - 2, -1, -1):
        mpre[index] = max(mpre[index], mpre[index + 1])
    changes = np.where(mrec[1:] != mrec[:-1])[0] + 1
    ap = float(np.sum((mrec[changes] - mrec[changes - 1]) * mpre[changes]))
    return {
        "ap": ap,
        "recall": float(recall[-1]),
        "false_discoveries": int(fp_cum[-1]),
        "duplicates": duplicate,
    }


def detection_metrics(ground_truth, predictions, threshold):
    labels = sorted({item["label"] for item in ground_truth})
    by_gt, by_pred = defaultdict(list), defaultdict(list)
    for item in ground_truth:
        by_gt[item["label"]].append(item)
    for item in predictions:
        by_pred[item["label"]].append(item)
    per_class = {
        label: _ap_for_label(by_gt[label], by_pred[label], threshold)
        for label in labels
    }
    unexpected = {
        label: len(items)
        for label, items in sorted(by_pred.items())
        if label not in by_gt
    }
    return {
        "map": float(np.mean([value["ap"] for value in per_class.values()]))
        if per_class
        else 0.0,
        "mean_recall": float(np.mean([value["recall"] for value in per_class.values()]))
        if per_class
        else 0.0,
        "false_discoveries": (
            sum(value["false_discoveries"] for value in per_class.values())
            + sum(unexpected.values())
        ),
        "duplicates": sum(value["duplicates"] for value in per_class.values()),
        "predictions_without_gt_class": unexpected,
        "per_class": per_class,
    }


def _median(values):
    return float(np.median(values)) if values else None


def paired_metrics(pairs):
    ious, center_errors, normalized_errors, extent_errors = [], [], [], []
    for gt, pred, iou in pairs:
        g0, g1 = np.asarray(gt["aabb_min"]), np.asarray(gt["aabb_max"])
        p0, p1 = np.asarray(pred["aabb_min"]), np.asarray(pred["aabb_max"])
        gs, ps = g1 - g0, p1 - p0
        center_error = float(np.linalg.norm((p0 + p1) / 2 - (g0 + g1) / 2))
        diagonal = float(np.linalg.norm(gs))
        ious.append(iou)
        center_errors.append(center_error)
        normalized_errors.append(center_error / diagonal if diagonal else math.inf)
        extent_errors.extend((np.abs(ps - gs) / gs).tolist())
    return {
        "assigned_pairs": len(pairs),
        "median_iou": _median(ious),
        "median_center_error_m": _median(center_errors),
        "median_normalized_center_error": _median(normalized_errors),
        "median_axis_extent_relative_error": _median(extent_errors),
    }


def evaluate(ground_truth, predictions):
    for record in ground_truth:
        validate_record(record)
    for record in predictions:
        validate_record(record)
    return {
        "schema_version": "lifting-benchmark-v0",
        "ground_truth_objects": len(ground_truth),
        "predicted_objects": len(predictions),
        "iou25": detection_metrics(ground_truth, predictions, 0.25),
        "iou50": detection_metrics(ground_truth, predictions, 0.50),
        "paired": paired_metrics(hungarian_pairs(ground_truth, predictions)),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--predictions", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = evaluate(load_jsonl(args.ground_truth), load_jsonl(args.predictions))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
