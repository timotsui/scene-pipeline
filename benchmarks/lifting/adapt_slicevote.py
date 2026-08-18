"""Convert a slice-vote preview manifest to benchmark prediction JSONL."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def convert(preview: dict, compatibility: dict, scene_id: str) -> list[dict]:
    source = {row["id"]: row for row in compatibility["mapping"]}
    records = []
    for obj in preview.get("objects", []):
        if obj["id"] not in source:
            raise ValueError(f"preview id {obj['id']!r} is absent from compatibility mapping")
        original = source[obj["id"]]
        status = (obj.get("flags") or ["unknown"])[0]
        records.append(
            {
                "scene_id": scene_id,
                "object_id": f"slicevote_{obj['id']}",
                "native_id": original["native_id"],
                "label": original["label"],
                "aabb_min": [float(value) for value in obj["aabb_min"]],
                "aabb_max": [float(value) for value in obj["aabb_max"]],
                "score": float(original["score"]),
                "native_metadata": {
                    "source": "active_slice_vote",
                    "status": status,
                    "flags": obj.get("flags", []),
                    "run_id": (obj.get("prov") or {}).get("run_id"),
                },
            }
        )
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--compatibility", required=True, type=Path)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    preview = json.loads(args.input.read_text(encoding="utf-8"))
    compatibility = json.loads(args.compatibility.read_text(encoding="utf-8"))
    records = convert(preview, compatibility, args.scene_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    print(f"wrote {len(records)} predictions to {args.output}")


if __name__ == "__main__":
    main()
