"""Freeze native pipeline-lifter SliceVote output as benchmark JSONL.

Labels and confidence scores come from the pipeline lifter's own founding
manifest.  No baseline compatibility mapping or ground truth is accepted.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def convert(preview: dict, founding: dict, scene_id: str) -> list[dict]:
    source = {row["id"]: row for row in founding.get("objects", [])}
    records = []
    for obj in preview.get("objects", []):
        native = source.get(obj["id"])
        if native is None:
            raise ValueError(
                f"SliceVote id {obj['id']!r} is absent from the native "
                "pipeline-lifter manifest"
            )
        status = (obj.get("flags") or ["unknown"])[0]
        records.append(
            {
                "scene_id": scene_id,
                "object_id": f"pipeline_lifter_{obj['id']}",
                "native_id": obj["id"],
                "label": native["label"],
                "aabb_min": [float(value) for value in obj["aabb_min"]],
                "aabb_max": [float(value) for value in obj["aabb_max"]],
                "score": float(native["score"]),
                "native_metadata": {
                    "source": "pipeline_lifter_multibase_slicevote",
                    "status": status,
                    "flags": obj.get("flags", []),
                    "founding_views": native.get("views", []),
                    "founding_detections": native.get("n_detections", 0),
                    "run_id": (obj.get("prov") or {}).get("run_id"),
                },
            }
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--founding-manifest", required=True, type=Path)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--receipt", required=True, type=Path)
    args = parser.parse_args()

    preview = json.loads(args.input.read_text(encoding="utf-8"))
    founding = json.loads(args.founding_manifest.read_text(encoding="utf-8"))
    if preview.get("run_kind") != "full" or not preview.get("canon_eligible"):
        raise ValueError("refusing to freeze a partial or mixed-provenance SliceVote run")
    records = convert(preview, founding, args.scene_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")

    receipt = {
        "format": "pipeline-lifter-prediction-freeze-v1",
        "scene_id": args.scene_id,
        "ground_truth_read": False,
        "prediction_count": len(records),
        "slicevote_run_id": preview.get("run_id"),
        "slicevote_params_hash": preview.get("params_hash"),
        "slicevote_source_sha": preview.get("source_sha"),
        "inputs": {
            "slicevote_preview": {"path": str(args.input.resolve()),
                                  "sha256": _sha256(args.input)},
            "founding_manifest": {"path": str(args.founding_manifest.resolve()),
                                  "sha256": _sha256(args.founding_manifest)},
        },
        "predictions": {"path": str(args.output.resolve()),
                        "sha256": _sha256(args.output)},
    }
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.receipt.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"froze {len(records)} native predictions in {args.output}")


if __name__ == "__main__":
    main()
