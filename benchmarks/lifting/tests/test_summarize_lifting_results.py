import unittest

from benchmarks.lifting.summarize_lifting_results import _bootstrap_delta, _macro


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


if __name__ == "__main__":
    unittest.main()
