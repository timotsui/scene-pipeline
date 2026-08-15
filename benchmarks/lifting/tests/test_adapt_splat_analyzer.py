import unittest

from benchmarks.lifting.adapt_splat_analyzer import convert


class SplatAnalyzerAdapterTests(unittest.TestCase):
    def test_current_scale_and_frames_schema(self):
        payload = {
            "objects": [
                {
                    "label": "Chair",
                    "position": {"x": 1, "y": 2, "z": 3},
                    "scale": {"x": 2, "y": 4, "z": 6},
                    "frames": [
                        {"frame_idx": 2, "score": 0.4},
                        {"frame_idx": 5, "score": 0.7},
                    ],
                }
            ]
        }
        record = convert(payload, "scene")[0]
        self.assertEqual(record["label"], "chair")
        self.assertEqual(record["aabb_min"], [0.0, 0.0, 0.0])
        self.assertEqual(record["aabb_max"], [2.0, 4.0, 6.0])
        self.assertEqual(record["score"], 0.7)
        self.assertEqual(record["native_metadata"]["votes"], 2)

    def test_legacy_size_schema(self):
        payload = {
            "objects": [
                {
                    "label": "lamp",
                    "position": {"x": 0, "y": 0, "z": 0},
                    "size": {"x": 1, "y": 1, "z": 1},
                    "peak_score": 0.8,
                }
            ]
        }
        record = convert(payload, "scene")[0]
        self.assertEqual(record["aabb_min"], [-0.5, -0.5, -0.5])
        self.assertEqual(record["score"], 0.8)


if __name__ == "__main__":
    unittest.main()
