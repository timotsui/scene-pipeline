import unittest

from benchmarks.lifting.adapt_slicevote import convert


class SliceVoteAdapterTests(unittest.TestCase):
    def test_convert_restores_fixed_proposal_label_and_score(self):
        compatibility = {
            "mapping": [
                {
                    "id": "obj_000",
                    "native_id": 7,
                    "object_id": "mask_lift_0007",
                    "label": "chair",
                    "score": 0.42,
                }
            ]
        }
        preview = {
            "objects": [
                {
                    "id": "obj_000",
                    "label": "chair (voted 3v/6)",
                    "aabb_min": [0, 1, 2],
                    "aabb_max": [3, 4, 5],
                    "score": 1.0,
                    "flags": ["voted"],
                    "prov": {"run_id": "r1"},
                }
            ]
        }
        [record] = convert(preview, compatibility, "scene")
        self.assertEqual(record["label"], "chair")
        self.assertEqual(record["score"], 0.42)
        self.assertEqual(record["native_id"], 7)
        self.assertEqual(record["native_metadata"]["status"], "voted")


if __name__ == "__main__":
    unittest.main()
