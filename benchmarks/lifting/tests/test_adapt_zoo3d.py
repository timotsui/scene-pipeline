import unittest

import numpy as np

from benchmarks.lifting.adapt_zoo3d import convert_arrays


class Zoo3DAdapterTests(unittest.TestCase):
    def test_point_mask_box_and_label_normalization(self):
        points = np.asarray([[0, 1, 2], [2, 4, 8], [9, 9, 9]], dtype=float)
        masks = np.asarray([[1, 0], [1, 0], [0, 1]], dtype=bool)
        records = convert_arrays(
            points,
            masks,
            np.asarray([7, 8]),
            np.asarray([0.75, 0.9]),
            {7: "couch", 8: "wall"},
            "scene",
        )
        self.assertEqual(len(records), 1)
        self.assertEqual(records[0]["label"], "sofa")
        self.assertEqual(records[0]["aabb_min"], [0.0, 1.0, 2.0])
        self.assertEqual(records[0]["aabb_max"], [2.0, 4.0, 8.0])
        self.assertEqual(records[0]["native_metadata"]["mask_point_count"], 2)

    def test_shape_mismatch_is_rejected(self):
        with self.assertRaises(ValueError):
            convert_arrays(
                np.zeros((3, 3)),
                np.zeros((4, 1)),
                np.zeros(1),
                np.zeros(1),
                {0: "chair"},
                "scene",
            )


if __name__ == "__main__":
    unittest.main()
