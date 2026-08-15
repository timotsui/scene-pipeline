import unittest

import numpy as np

from benchmarks.lifting.adapt_boxer import convert_rows


def row(**updates):
    value = {
        "time_ns": "4",
        "tx_world_object": "1",
        "ty_world_object": "2",
        "tz_world_object": "3",
        "qw_world_object": "1",
        "qx_world_object": "0",
        "qy_world_object": "0",
        "qz_world_object": "0",
        "scale_x": "2",
        "scale_y": "4",
        "scale_z": "6",
        "name": "Chair",
        "instance": "7",
        "sem_id": "10",
        "prob": "0.8",
    }
    value.update(updates)
    return value


class BoxerAdapterTests(unittest.TestCase):
    def test_identity_obb_and_world_offset(self):
        result = convert_rows([row()], "scene", [10, 20, 30])[0]
        self.assertEqual(result["label"], "chair")
        np.testing.assert_allclose(result["aabb_min"], [10, 20, 30])
        np.testing.assert_allclose(result["aabb_max"], [12, 24, 36])

    def test_rotation_expands_in_world_axes(self):
        # 90 degrees about z swaps the x/y full dimensions.
        q = 2**-0.5
        result = convert_rows(
            [row(qw_world_object=str(q), qz_world_object=str(q))], "scene", [0, 0, 0]
        )[0]
        np.testing.assert_allclose(result["aabb_min"], [-1, 1, 0], atol=1e-7)
        np.testing.assert_allclose(result["aabb_max"], [3, 3, 6], atol=1e-7)


if __name__ == "__main__":
    unittest.main()
