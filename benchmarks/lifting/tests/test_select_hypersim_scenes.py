import unittest

import numpy as np

from benchmarks.lifting.select_hypersim_scenes import (
    instance_label_counts,
    instance_semantic_labels,
    pinhole_projection_error,
)


class SelectHypersimScenesTests(unittest.TestCase):
    def test_counts_one_label_per_instance(self):
        semantic = np.array([5, 5, 7, 7, 7, -1])
        instance = np.array([0, 0, 1, 2, 2, -1])

        counts, conflicts = instance_label_counts(semantic, instance)

        self.assertEqual(counts, {5: 1, 7: 2})
        self.assertEqual(conflicts, {})

    def test_uses_majority_label_and_reports_conflict(self):
        semantic = np.array([5, 5, 7])
        instance = np.array([3, 3, 3])

        counts, conflicts = instance_label_counts(semantic, instance)

        self.assertEqual(counts, {5: 1})
        self.assertEqual(conflicts, {3: [5, 7]})

    def test_returns_instance_to_semantic_map(self):
        labels, conflicts = instance_semantic_labels(
            np.array([5, 5, 7]), np.array([2, 2, 4])
        )
        self.assertEqual(labels, {2: 5, 4: 7})
        self.assertEqual(conflicts, {})

    def test_rejects_mismatched_arrays(self):
        with self.assertRaisesRegex(ValueError, "differ"):
            instance_label_counts(np.array([1]), np.array([1, 2]))

    def test_standard_pinhole_has_zero_projection_error(self):
        row = {f"M_proj_{i}{j}": "0" for i in range(4) for j in range(4)}
        row["M_proj_32"] = "-1"
        row["M_proj_02"] = "0.1"  # allowed principal-point offset
        row["M_proj_12"] = "-0.2"
        self.assertEqual(pinhole_projection_error(row), 0.0)

    def test_tilt_shift_has_nonzero_projection_error(self):
        row = {f"M_proj_{i}{j}": "0" for i in range(4) for j in range(4)}
        row["M_proj_32"] = "-0.99"
        row["M_proj_31"] = "0.1"
        self.assertGreater(pinhole_projection_error(row), 0.1)


if __name__ == "__main__":
    unittest.main()
