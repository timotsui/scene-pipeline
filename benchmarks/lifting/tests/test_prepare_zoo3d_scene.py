import unittest

import numpy as np

from benchmarks.lifting.prepare_zoo3d_scene import _scaled_intrinsic


class Zoo3DExporterTests(unittest.TestCase):
    def test_intrinsic_matches_zoo_internal_half_scale(self):
        intrinsic = np.eye(4)
        intrinsic[0, 0] = 400
        intrinsic[1, 1] = 410
        intrinsic[0, 2] = 256
        intrinsic[1, 2] = 192
        exported = _scaled_intrinsic(intrinsic, (512, 384))
        # Zoo3D halves the exported 1280x960 calibration for 640x480 images.
        np.testing.assert_allclose(exported[0, :3] * 0.5, [500, 0, 320])
        np.testing.assert_allclose(exported[1, :3] * 0.5, [0, 512.5, 240])


if __name__ == "__main__":
    unittest.main()
