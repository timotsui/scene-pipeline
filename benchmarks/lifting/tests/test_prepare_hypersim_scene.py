import unittest

import numpy as np

from benchmarks.lifting.prepare_hypersim_scene import (
    projection_to_intrinsics,
    rotation_matrix_to_qvec,
)


class PrepareHypersimSceneTests(unittest.TestCase):
    def test_projection_to_intrinsics(self):
        row = {f"M_proj_{i}{j}": "0" for i in range(4) for j in range(4)}
        row.update(
            {
                "M_proj_00": "2",
                "M_proj_11": "2",
                "M_proj_02": "0",
                "M_proj_12": "0",
                "M_proj_32": "-1",
            }
        )
        self.assertEqual(projection_to_intrinsics(row, 101, 81), (100, 80, 50, 40))

    def test_identity_rotation_quaternion(self):
        qvec = rotation_matrix_to_qvec(np.eye(3))
        np.testing.assert_allclose(qvec, [1, 0, 0, 0], atol=1e-7)

    def test_quaternion_round_trip_rotation(self):
        rotation = np.array([[0, -1, 0], [1, 0, 0], [0, 0, 1]], dtype=float)
        qw, qx, qy, qz = rotation_matrix_to_qvec(rotation)
        recovered = np.array(
            [
                [1 - 2 * (qy * qy + qz * qz), 2 * (qx * qy - qw * qz), 2 * (qx * qz + qw * qy)],
                [2 * (qx * qy + qw * qz), 1 - 2 * (qx * qx + qz * qz), 2 * (qy * qz - qw * qx)],
                [2 * (qx * qz - qw * qy), 2 * (qy * qz + qw * qx), 1 - 2 * (qx * qx + qy * qy)],
            ]
        )
        np.testing.assert_allclose(recovered, rotation, atol=1e-7)


if __name__ == "__main__":
    unittest.main()
