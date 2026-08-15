import unittest

from benchmarks.lifting.evaluate import evaluate, iou3d


def box(object_id, lo, hi, score=1.0, label="chair"):
    return {
        "scene_id": "synthetic",
        "object_id": object_id,
        "label": label,
        "aabb_min": lo,
        "aabb_max": hi,
        "score": score,
    }


class EvaluateTests(unittest.TestCase):
    def setUp(self):
        self.gt = [box("gt", [0, 0, 0], [1, 1, 1])]

    def test_iou_known_shift(self):
        shifted = box("pred", [0.5, 0, 0], [1.5, 1, 1])
        self.assertAlmostEqual(iou3d(self.gt[0], shifted), 1 / 3)

    def test_perfect_prediction(self):
        result = evaluate(self.gt, [box("pred", [0, 0, 0], [1, 1, 1])])
        self.assertEqual(result["iou25"]["map"], 1.0)
        self.assertEqual(result["iou50"]["map"], 1.0)
        self.assertEqual(result["paired"]["median_center_error_m"], 0.0)

    def test_shift_passes_25_not_50(self):
        result = evaluate(self.gt, [box("pred", [0.5, 0, 0], [1.5, 1, 1])])
        self.assertEqual(result["iou25"]["map"], 1.0)
        self.assertEqual(result["iou50"]["map"], 0.0)

    def test_duplicate_is_counted(self):
        predictions = [
            box("best", [0, 0, 0], [1, 1, 1], score=0.9),
            box("duplicate", [0, 0, 0], [1, 1, 1], score=0.8),
        ]
        result = evaluate(self.gt, predictions)
        self.assertEqual(result["iou25"]["duplicates"], 1)
        self.assertEqual(result["iou25"]["false_discoveries"], 1)

    def test_empty_predictions(self):
        result = evaluate(self.gt, [])
        self.assertEqual(result["iou25"]["map"], 0.0)
        self.assertEqual(result["iou25"]["mean_recall"], 0.0)
        self.assertEqual(result["paired"]["assigned_pairs"], 0)

    def test_prediction_for_absent_class_is_false_discovery(self):
        result = evaluate(
            self.gt, [box("wrong-label", [0, 0, 0], [1, 1, 1], label="table")]
        )
        self.assertEqual(result["iou25"]["false_discoveries"], 1)
        self.assertEqual(result["iou25"]["predictions_without_gt_class"], {"table": 1})


if __name__ == "__main__":
    unittest.main()
