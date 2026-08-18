import unittest

import numpy as np

from benchmarks.lifting.prepare_slicevote_scene import estimate_shell


class PrepareSliceVoteSceneTests(unittest.TestCase):
    def test_estimate_shell_encloses_camera_path_and_finds_horizontal_planes(self):
        rng = np.random.default_rng(3)
        interior = rng.uniform(
            [-4.0, -2.8, -5.0], [5.0, -0.2, 3.0], size=(4_000, 3)
        )
        ceiling = np.column_stack(
            (
                rng.uniform(-4, 5, 2_000),
                rng.normal(-3.0, 0.01, 2_000),
                rng.uniform(-5, 3, 2_000),
            )
        )
        floor = np.column_stack(
            (
                rng.uniform(-4, 5, 2_000),
                rng.normal(0.0, 0.01, 2_000),
                rng.uniform(-5, 3, 2_000),
            )
        )
        points = np.vstack((interior, ceiling, floor))
        cameras = np.array([[-2.0, -1.4, -3.0], [1.0, -1.0, 0.0]])
        shell = estimate_shell(points, cameras)
        self.assertLess(shell["ceiling_y_raw"], cameras[:, 1].min())
        self.assertGreater(shell["floor_y_raw"], cameras[:, 1].max())
        self.assertLess(abs(shell["ceiling_y_raw"] + 3.0), 0.08)
        self.assertLess(abs(shell["floor_y_raw"]), 0.08)


if __name__ == "__main__":
    unittest.main()
