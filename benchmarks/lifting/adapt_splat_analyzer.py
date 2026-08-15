"""Convert Splat Analyzer interactions.json to benchmark JSONL.

The adapter does no frame conversion: Splat Analyzer returns coordinates in
the input splat frame. Its `position` is treated as AABB center and `size` as
full extents, matching the tool's output contract. Preserve interactions.json
as the native artifact because its boxes include method-specific heuristics.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def _xyz(value, field):
    try:
        out = [float(value[k]) for k in ("x", "y", "z")]
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"invalid {field}: {value!r}") from exc
    if any(not (v == v and abs(v) != float("inf")) for v in out):
        raise ValueError(f"non-finite {field}: {value!r}")
    return out


def convert(payload, scene_id):
    records = []
    for index, obj in enumerate(payload.get("objects") or []):
        center = _xyz(obj.get("position"), "position")
        # Current Splat Analyzer calls full extents `scale`; older examples and
        # bridge code may call the same quantity `size`.
        size = _xyz(obj.get("scale", obj.get("size")), "scale/size")
        if any(v <= 0 for v in size):
            raise ValueError(f"object {index} has non-positive size: {size}")
        half = [v / 2.0 for v in size]
        frames = obj.get("frames") or []
        frame_scores = [float(frame["score"]) for frame in frames if "score" in frame]
        score = obj.get("peak_score", obj.get("score", max(frame_scores, default=1.0)))
        record = {
            "scene_id": scene_id,
            "object_id": f"splat_analyzer_{index:04d}",
            "native_id": obj.get("id", index),
            "label": str(obj["label"]).strip().lower(),
            "aabb_min": [center[i] - half[i] for i in range(3)],
            "aabb_max": [center[i] + half[i] for i in range(3)],
            "score": float(score),
            "native_metadata": {
                "votes": int(obj.get("votes", len(frames))),
                "peak_score": float(score),
                "supporting_frame_indices": [
                    int(frame["frame_idx"]) for frame in frames if "frame_idx" in frame
                ],
            },
        }
        records.append(record)
    return records


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    payload = json.loads(args.input.read_text(encoding="utf-8"))
    records = convert(payload, args.scene_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(json.dumps(record, sort_keys=True) + "\n")
    print(f"wrote {len(records)} predictions to {args.output}")


if __name__ == "__main__":
    main()
