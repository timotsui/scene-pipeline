"""Convert Boxer's native OBB CSV to lifting-benchmark-v0 AABBs."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np


def _rotation_from_wxyz(values: list[float]) -> np.ndarray:
    q = np.asarray(values, dtype=np.float64)
    norm = np.linalg.norm(q)
    if not np.isfinite(norm) or norm <= 0:
        raise ValueError(f"invalid quaternion: {values}")
    w, x, y, z = q / norm
    return np.asarray(
        [
            [1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)],
            [2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)],
            [2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)],
        ],
        dtype=np.float64,
    )


def convert_rows(rows: list[dict[str, str]], scene_id: str, world_offset) -> list[dict]:
    offset = np.asarray(world_offset, dtype=np.float64)
    if offset.shape != (3,) or not np.isfinite(offset).all():
        raise ValueError("world offset must contain three finite values")

    records = []
    for index, row in enumerate(rows):
        center = (
            np.asarray(
                [
                    row["tx_world_object"],
                    row["ty_world_object"],
                    row["tz_world_object"],
                ],
                dtype=np.float64,
            )
            + offset
        )
        dimensions = np.asarray(
            [row["scale_x"], row["scale_y"], row["scale_z"]], dtype=np.float64
        )
        if np.any(dimensions <= 0) or not np.isfinite(dimensions).all():
            raise ValueError(
                f"row {index}: invalid full dimensions {dimensions.tolist()}"
            )
        rotation = _rotation_from_wxyz(
            [
                float(row["qw_world_object"]),
                float(row["qx_world_object"]),
                float(row["qy_world_object"]),
                float(row["qz_world_object"]),
            ]
        )
        # The axis-aligned half extent of an OBB is |R| times its local half extent.
        half_extent = np.abs(rotation) @ (dimensions / 2.0)
        time_ns = str(row["time_ns"])
        records.append(
            {
                "scene_id": scene_id,
                "object_id": f"boxer_{time_ns}_{index}",
                "label": row["name"].strip().lower(),
                "aabb_min": (center - half_extent).tolist(),
                "aabb_max": (center + half_extent).tolist(),
                "score": float(row["prob"]),
                "native_id": f"frame={time_ns};instance={row['instance']}",
                "native_metadata": {
                    "method": "boxer",
                    "time_ns": int(time_ns),
                    "instance": int(float(row["instance"])),
                    "sem_id": int(float(row["sem_id"])),
                    "obb_center_recentered": (center - offset).tolist(),
                    "obb_dimensions": dimensions.tolist(),
                    "quaternion_wxyz": [
                        float(row["qw_world_object"]),
                        float(row["qx_world_object"]),
                        float(row["qy_world_object"]),
                        float(row["qz_world_object"]),
                    ],
                },
            }
        )
    return records


def convert_file(csv_path: Path, manifest_path: Path, scene_id: str) -> list[dict]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("format") != "boxer_scannet_interop_v0":
        raise ValueError(f"unsupported export manifest: {manifest.get('format')}")
    with csv_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    return convert_rows(rows, scene_id, manifest["boxer_world_offset_source"])


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="Boxer 3D-box CSV")
    parser.add_argument("--export-manifest", required=True, type=Path)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    records = convert_file(args.input, args.export_manifest, args.scene_id)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )
    print(f"wrote {len(records)} Boxer predictions to {args.output}")


if __name__ == "__main__":
    main()
