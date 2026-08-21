import importlib.util
from pathlib import Path
import unittest


MODULE = Path(__file__).parents[1] / "adapt_pipeline_lifter.py"
SPEC = importlib.util.spec_from_file_location("adapt_pipeline_lifter", MODULE)
ADAPTER = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(ADAPTER)


class PipelineLifterAdapterTests(unittest.TestCase):
    def test_convert_uses_native_manifest_label_and_score(self):
        preview = {
            "objects": [{
                "id": "obj_004", "label": "decorated vote label",
                "aabb_min": [1, 2, 3], "aabb_max": [4, 5, 6],
                "flags": ["voted"], "prov": {"run_id": "run-a"},
            }]
        }
        founding = {
            "objects": [{
                "id": "obj_004", "label": "chair", "score": 0.42,
                "views": ["base0_pano_000"], "n_detections": 3,
            }]
        }
        got = ADAPTER.convert(preview, founding, "ai_test")[0]
        self.assertEqual(got["label"], "chair")
        self.assertEqual(got["score"], 0.42)
        self.assertEqual(got["native_id"], "obj_004")
        self.assertEqual(got["native_metadata"]["run_id"], "run-a")

    def test_convert_rejects_non_native_identity(self):
        with self.assertRaises(ValueError):
            ADAPTER.convert(
                {"objects": [{"id": "foreign", "aabb_min": [0] * 3,
                              "aabb_max": [1] * 3}]},
                {"objects": []},
                "ai_test",
            )


if __name__ == "__main__":
    unittest.main()
