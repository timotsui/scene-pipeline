"""Aggregate a multi-scene Hypersim lifting benchmark reproducibly.

The scene is the sampling unit.  The output contains both scene-macro metrics
and a pooled evaluator result.  Missing derived-method predictions are treated
as empty only when the fixed proposal method also emitted no predictions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

try:
    from benchmarks.lifting.evaluate import evaluate, load_jsonl
except ModuleNotFoundError:  # Support ``python benchmarks/lifting/<script>.py``.
    from evaluate import evaluate, load_jsonl


FIELDS = {
    "map25": ("iou25", "map"),
    "recall25": ("iou25", "mean_recall"),
    "map50": ("iou50", "map"),
    "median_iou": ("paired", "median_iou"),
    "median_center_error_m": ("paired", "median_center_error_m"),
    "median_normalized_center_error": (
        "paired",
        "median_normalized_center_error",
    ),
    "median_axis_extent_relative_error": (
        "paired",
        "median_axis_extent_relative_error",
    ),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _metric(metrics: dict, field: str):
    left, right = FIELDS[field]
    return metrics[left][right]


def _macro(per_scene: dict[str, dict]) -> dict:
    summary = {}
    for field in FIELDS:
        values = [
            _metric(metrics, field)
            for metrics in per_scene.values()
            if _metric(metrics, field) is not None
        ]
        summary[field] = {
            "mean": float(np.mean(values)) if values else None,
            "median": float(np.median(values)) if values else None,
            "scenes": len(values),
        }
    return summary


def _bootstrap_delta(
    left: dict[str, dict],
    right: dict[str, dict],
    field: str,
    *,
    seed: int,
    samples: int,
) -> dict:
    scenes = sorted(set(left) & set(right))
    deltas = np.asarray(
        [_metric(left[scene], field) - _metric(right[scene], field) for scene in scenes],
        dtype=float,
    )
    rng = np.random.default_rng(seed)
    indices = rng.integers(0, len(deltas), size=(samples, len(deltas)))
    draws = deltas[indices].mean(axis=1)
    return {
        "left_minus_right_mean": float(deltas.mean()),
        "bootstrap_95ci": [
            float(np.quantile(draws, 0.025)),
            float(np.quantile(draws, 0.975)),
        ],
        "scenes_improved": int(np.sum(deltas > 1e-12)),
        "scenes_tied": int(np.sum(np.abs(deltas) <= 1e-12)),
        "scenes_worse": int(np.sum(deltas < -1e-12)),
        "scene_deltas": {scene: float(delta) for scene, delta in zip(scenes, deltas)},
    }


def summarize(
    prepared_root: Path,
    predictions_root: Path,
    scenes: list[str],
    methods: dict[str, str],
    *,
    seed: int = 17,
    bootstrap_samples: int = 10_000,
) -> dict:
    ground_truth, native_counts, provenance = {}, {}, []
    for scene in scenes:
        gt_path = prepared_root / scene / "ground_truth.visible.jsonl"
        ground_truth[scene] = load_jsonl(gt_path)
        provenance.append(
            {
                "path": f"prepared/{scene}/ground_truth.visible.jsonl",
                "sha256": _sha256(gt_path),
            }
        )

    loaded_predictions: dict[str, dict[str, list]] = {}
    per_scene: dict[str, dict[str, dict]] = {}
    for method, pattern in methods.items():
        loaded_predictions[method], per_scene[method] = {}, {}
        for scene in scenes:
            prediction_path = predictions_root / pattern.format(scene=scene) / "predictions.jsonl"
            if prediction_path.exists():
                predictions = load_jsonl(prediction_path)
                provenance.append(
                    {
                        "path": f"predictions/{pattern.format(scene=scene)}/predictions.jsonl",
                        "sha256": _sha256(prediction_path),
                    }
                )
            else:
                if method == "native":
                    raise FileNotFoundError(prediction_path)
                if native_counts.get(scene) != 0:
                    raise FileNotFoundError(prediction_path)
                predictions = []
            loaded_predictions[method][scene] = predictions
            per_scene[method][scene] = evaluate(ground_truth[scene], predictions)
            if method == "native":
                native_counts[scene] = len(predictions)

    methods_summary = {}
    for method in methods:
        pooled_gt = [record for scene in scenes for record in ground_truth[scene]]
        pooled_predictions = [
            record
            for scene in scenes
            for record in loaded_predictions[method][scene]
        ]
        methods_summary[method] = {
            "scene_macro": _macro(per_scene[method]),
            "pooled": evaluate(pooled_gt, pooled_predictions),
        }

    comparisons = {}
    if "active" in methods:
        for baseline in ("global", "native"):
            if baseline not in methods:
                continue
            comparisons[f"active_minus_{baseline}"] = {
                field: _bootstrap_delta(
                    per_scene["active"],
                    per_scene[baseline],
                    field,
                    seed=seed,
                    samples=bootstrap_samples,
                )
                for field in ("map25", "recall25", "map50")
            }

    return {
        "format": "lifting-hypersim-summary-v1",
        "sampling_unit": "scene",
        "scenes": scenes,
        "method_paths": methods,
        "bootstrap": {"seed": seed, "samples": bootstrap_samples},
        "methods": methods_summary,
        "per_scene": per_scene,
        "comparisons": comparisons,
        "input_provenance": provenance,
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--prepared-root", type=Path, required=True)
    parser.add_argument("--predictions-root", type=Path, required=True)
    parser.add_argument("--scenes", nargs="+", required=True)
    parser.add_argument(
        "--method",
        action="append",
        required=True,
        help="NAME=directory-pattern, where {scene} expands to the scene id",
    )
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--bootstrap-samples", type=int, default=10_000)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    methods = {}
    for value in args.method:
        name, separator, pattern = value.partition("=")
        if not separator or not name or "{scene}" not in pattern:
            parser.error("--method must be NAME=pattern-containing-{scene}")
        methods[name] = pattern
    result = summarize(
        args.prepared_root,
        args.predictions_root,
        args.scenes,
        methods,
        seed=args.seed,
        bootstrap_samples=args.bootstrap_samples,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result["methods"], indent=2))


if __name__ == "__main__":
    main()
