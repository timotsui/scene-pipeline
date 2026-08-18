"""Convert Zoo3D point-mask predictions to lifting-benchmark-v0 AABBs."""

from __future__ import annotations

import argparse
import json
import runpy
from pathlib import Path

import numpy as np


CANONICAL_LABELS = {
    "chair": "chair",
    "office chair": "chair",
    "armchair": "chair",
    "folded chair": "chair",
    "table": "table",
    "coffee table": "table",
    "end table": "table",
    "dining table": "table",
    "couch": "sofa",
    "bookshelf": "bookshelf",
    "shelf": "bookshelf",
    "cabinet": "cabinet",
    "kitchen cabinet": "cabinet",
    "file cabinet": "cabinet",
    "bathroom cabinet": "cabinet",
    "lamp": "lamp",
    "tv": "television",
}


def convert_arrays(
    points: np.ndarray,
    masks: np.ndarray,
    class_ids: np.ndarray,
    scores: np.ndarray,
    label_by_id: dict[int, str],
    scene_id: str,
) -> list[dict]:
    points = np.asarray(points, dtype=np.float64)
    masks = np.asarray(masks)
    class_ids = np.asarray(class_ids).reshape(-1)
    scores = np.asarray(scores, dtype=np.float64).reshape(-1)
    if points.ndim != 2 or points.shape[1] != 3:
        raise ValueError(f"expected Nx3 points, got {points.shape}")
    if masks.ndim != 2 or masks.shape[0] != points.shape[0]:
        raise ValueError(f"mask shape {masks.shape} does not match {points.shape}")
    if masks.shape[1] != len(class_ids) or len(class_ids) != len(scores):
        raise ValueError("mask, class, and score counts differ")

    records = []
    for index, (class_id, score) in enumerate(zip(class_ids, scores)):
        native_label = label_by_id.get(int(class_id))
        canonical = CANONICAL_LABELS.get(native_label or "")
        if canonical is None:
            continue
        selected = points[np.asarray(masks[:, index]).astype(bool)]
        selected = selected[np.isfinite(selected).all(axis=1)]
        if not len(selected):
            continue
        lower, upper = selected.min(axis=0), selected.max(axis=0)
        if np.any(upper <= lower):
            continue
        records.append(
            {
                "scene_id": scene_id,
                "object_id": f"zoo3d_{index}",
                "label": canonical,
                "aabb_min": lower.tolist(),
                "aabb_max": upper.tolist(),
                "score": float(score),
                "native_id": str(index),
                "native_metadata": {
                    "method": "Zoo3D_0",
                    "class_id": int(class_id),
                    "class_label": native_label,
                    "mask_point_count": int(len(selected)),
                },
            }
        )
    return records


def convert_file(
    prediction_path: Path,
    point_path: Path,
    constants_path: Path,
    scene_id: str,
) -> list[dict]:
    prediction = np.load(prediction_path, allow_pickle=False)
    point_rows = np.fromfile(point_path, dtype=np.float32).reshape((-1, 6))
    constants = runpy.run_path(str(constants_path))
    label_by_id = {
        int(class_id): label
        for class_id, label in zip(
            constants["SCANNET200_IDS"], constants["SCANNET200_LABELS"]
        )
    }
    return convert_arrays(
        point_rows[:, :3],
        prediction["pred_masks"],
        prediction["pred_classes"],
        prediction["pred_score"],
        label_by_id,
        scene_id,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--points", required=True, type=Path)
    parser.add_argument("--constants", required=True, type=Path)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    records = convert_file(args.input, args.points, args.constants, args.scene_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )
    print(f"wrote {len(records)} Zoo3D predictions to {args.output}")


if __name__ == "__main__":
    main()
