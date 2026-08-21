import unittest

from benchmarks.lifting.summarize_lifting_results import (
    _bootstrap_delta,
    _macro,
    summarize,
)


def metrics(map25, recall25, map50):
    return {
        "iou25": {"map": map25, "mean_recall": recall25},
        "iou50": {"map": map50},
        "paired": {
            "median_iou": 0.2,
            "median_center_error_m": 1.0,
            "median_normalized_center_error": 0.5,
            "median_axis_extent_relative_error": 0.3,
        },
    }


class SummarizeLiftingResultsTests(unittest.TestCase):
    def test_macro_uses_scenes_as_equal_units(self):
        result = _macro({"a": metrics(0.2, 0.4, 0.1), "b": metrics(0.6, 0.8, 0.3)})
        self.assertAlmostEqual(result["map25"]["mean"], 0.4)
        self.assertAlmostEqual(result["recall25"]["median"], 0.6)

    def test_bootstrap_reports_paired_scene_direction(self):
        active = {"a": metrics(0.4, 0.5, 0.2), "b": metrics(0.3, 0.4, 0.1)}
        global_ = {"a": metrics(0.2, 0.2, 0.1), "b": metrics(0.3, 0.1, 0.0)}
        result = _bootstrap_delta(active, global_, "map25", seed=3, samples=100)
        self.assertAlmostEqual(result["left_minus_right_mean"], 0.1)
        self.assertEqual(result["scenes_improved"], 1)
        self.assertEqual(result["scenes_tied"], 1)
        self.assertEqual(result["scenes_worse"], 0)

    def test_summary_accepts_explicit_cross_system_comparison(self):
        from pathlib import Path
        from tempfile import TemporaryDirectory
        import json

        record = {
            "scene_id": "scene",
            "object_id": "chair_1",
            "label": "chair",
            "aabb_min": [0.0, 0.0, 0.0],
            "aabb_max": [1.0, 1.0, 1.0],
            "score": 1.0,
        }
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            prepared = root / "prepared" / "scene"
            prepared.mkdir(parents=True)
            (prepared / "ground_truth.visible.jsonl").write_text(
                json.dumps(record) + "\n", encoding="utf-8"
            )
            for method in ("ours", "zoo"):
                output = root / "predictions" / method / "scene"
                output.mkdir(parents=True)
                (output / "predictions.jsonl").write_text(
                    json.dumps(record) + "\n", encoding="utf-8"
                )

            result = summarize(
                root / "prepared",
                root / "predictions",
                ["scene"],
                {"ours": "ours/{scene}", "zoo": "zoo/{scene}"},
                comparison_pairs=[("ours", "zoo")],
                bootstrap_samples=10,
            )

        self.assertEqual(result["methods"]["ours"]["prediction_count"], 1)
        comparison = result["comparisons"]["ours_minus_zoo"]["map25"]
        self.assertEqual(comparison["scenes_tied"], 1)


if __name__ == "__main__":
    unittest.main()
