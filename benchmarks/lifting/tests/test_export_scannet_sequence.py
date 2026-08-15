import unittest

import numpy as np

from benchmarks.lifting.export_scannet_sequence import _as_c2w, _frame_indices


class ExportScanNetTests(unittest.TestCase):
    def test_opencv_c2w_is_unchanged(self):
        matrix = np.eye(4)
        matrix[:3, 3] = [1, 2, 3]
        np.testing.assert_allclose(_as_c2w(matrix.tolist(), "c2w_opencv"), matrix)

    def test_opengl_axes_are_converted(self):
        expected = np.diag([1.0, -1.0, -1.0, 1.0])
        np.testing.assert_allclose(_as_c2w(np.eye(4).tolist(), "c2w_opengl"), expected)

    def test_frame_selection_covers_trajectory(self):
        self.assertEqual(_frame_indices(90, 5), [0, 22, 44, 67, 89])


if __name__ == "__main__":
    unittest.main()
