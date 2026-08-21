"""Build the interactive 3D lifting diagnostic report.

The report intentionally packages only derived visualization data. It does not
modify benchmark outputs. Example:

    python benchmarks/lifting/build_scene3d_report.py \
      --benchmark-root ../CS-8903-OVM/week7/entangled_gen/out/lifting_benchmark/hypersim
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np


SCENES = {
    "ai_051_002": "Living room",
    "ai_002_006": "Kitchen",
    "ai_006_008": "Bedroom",
    "ai_037_007": "Dining room",
    "ai_003_009": "Office",
}


def read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()]


def iou_3d(a: dict, b: dict) -> float:
    alo = np.asarray(a["aabb_min"], dtype=float)
    ahi = np.asarray(a["aabb_max"], dtype=float)
    blo = np.asarray(b["aabb_min"], dtype=float)
    bhi = np.asarray(b["aabb_max"], dtype=float)
    inter = np.maximum(0.0, np.minimum(ahi, bhi) - np.maximum(alo, blo))
    inter_volume = float(np.prod(inter))
    union = float(np.prod(ahi - alo) + np.prod(bhi - blo) - inter_volume)
    return inter_volume / union if union > 0 else 0.0


def annotate_matches(objects: list[dict], ground_truth: list[dict]) -> list[dict]:
    out = []
    for obj in objects:
        peers = [gt for gt in ground_truth if gt.get("label") == obj.get("label")]
        best = max(((iou_3d(obj, gt), gt) for gt in peers),
                   key=lambda pair: pair[0], default=(0.0, None))
        keep = {key: obj.get(key) for key in
                ("object_id", "label", "score", "aabb_min", "aabb_max")}
        keep["best_iou"] = best[0]
        keep["best_gt"] = best[1].get("object_id") if best[1] else None
        out.append(keep)
    return out


def camera_records(transforms: dict) -> list[dict]:
    records = []
    for index, frame in enumerate(transforms.get("frames", [])):
        matrix = frame["transform_matrix"]
        # These benchmark transforms use the third rotation column as the
        # rendered camera's +z viewing direction.
        records.append({
            "index": index,
            "position_idx": frame.get("position_idx"),
            "position": [matrix[row][3] for row in range(3)],
            "forward": [matrix[row][2] for row in range(3)],
            "up": [matrix[row][1] for row in range(3)],
        })
    return records


def source_review_camera(transforms: dict) -> dict | None:
    """Return the first known-valid prepared camera in raw splat coordinates."""
    frames = transforms.get("frames", [])
    if not frames:
        return None
    frame = frames[0]
    matrix = frame["transform_matrix"]
    # Prepared Hypersim transforms are camera-to-world in OpenGL convention:
    # column 2 points backward, so the rendered viewing direction is -column 2.
    return {
        "source_frame": frame.get("file_path", "images/frame_0000.png"),
        "camera_convention": transforms.get("camera_convention", "c2w_opengl"),
        "position": [matrix[row][3] for row in range(3)],
        "forward": [-matrix[row][2] for row in range(3)],
        "up": [matrix[row][1] for row in range(3)],
        "fov_y_deg": float(np.degrees(
            2 * np.arctan(transforms["h"] / (2 * transforms["fl_y"])))),
    }


def build_scene(root: Path, out_dir: Path, scene_id: str, title: str,
                max_points: int) -> dict:
    prepared = root / "prepared" / scene_id
    analyzer = root / "predictions" / f"{scene_id}_splat_analyzer_medium_min1"
    gt = read_jsonl(prepared / "ground_truth.visible.jsonl")
    proposals = read_jsonl(analyzer / "predictions.jsonl")
    active = read_jsonl(root / "external" / "comparison" / "active" /
                        scene_id / "predictions.jsonl")
    zoo = read_jsonl(root / "external" / "comparison" / "zoo3d" /
                     scene_id / "predictions.jsonl")
    boxer = read_jsonl(root / "external" / "comparison" / "boxer" /
                       scene_id / "predictions.jsonl")
    transforms = json.loads((analyzer / "transforms.json").read_text(encoding="utf-8"))
    prepared_transforms = json.loads(
        (prepared / "transforms.json").read_text(encoding="utf-8"))
    splat = (root / "training" / f"{scene_id}_gsplat5000" / "ply" /
             "point_cloud_4999.ply")
    if not splat.exists():
        raise FileNotFoundError(f"trained Gaussian splat not found: {splat}")

    points_file = prepared / "initial_points.npz"
    with np.load(points_file) as data:
        points = data["points"]
        colors = data["colors"]
    if len(points) > max_points:
        selection = np.random.default_rng(0).choice(len(points), max_points,
                                                    replace=False)
        points = points[selection]
        colors = colors[selection]
    points = np.asarray(points, dtype="<f4")
    colors = np.asarray(colors, dtype=np.uint8)
    payload = out_dir / f"{scene_id}.bin"
    with payload.open("wb") as stream:
        points.tofile(stream)
        colors.tofile(stream)

    gt_keep = [{key: obj.get(key) for key in
                ("object_id", "label", "aabb_min", "aabb_max")} for obj in gt]
    record = {
        "scene_id": scene_id,
        "title": title,
        "coordinate_frame": "Hypersim metric; physical up is raw -Y",
        "display_rotation_deg": [0, 0, 180],
        "point_count": len(points),
        "point_file": payload.name,
        "splat_file": f"{scene_id}.ply",
        "splat_bytes": splat.stat().st_size,
        "bounds": {
            "min": points.min(axis=0).tolist(),
            "max": points.max(axis=0).tolist(),
            "p01": np.percentile(points, 1, axis=0).tolist(),
            "p99": np.percentile(points, 99, axis=0).tolist(),
        },
        "scene_center": transforms.get("scene_center"),
        "scene_radius": transforms.get("scene_radius"),
        "camera_fov_y_deg": float(np.degrees(
            2 * np.arctan(transforms["h"] / (2 * transforms["fl_y"])))),
        "base_camera_positions": transforms.get("camera_positions", []),
        "look_targets": transforms.get("look_targets", []),
        "cameras": camera_records(transforms),
        "source_review_camera": source_review_camera(prepared_transforms),
        "layers": {
            "ground_truth": gt_keep,
            "raw_proposals": annotate_matches(proposals, gt),
            "active": annotate_matches(active, gt),
            "zoo3d": annotate_matches(zoo, gt),
            "boxer": annotate_matches(boxer, gt),
        },
    }
    (out_dir / f"{scene_id}.json").write_text(
        json.dumps(record, indent=2), encoding="utf-8")
    return {
        "id": scene_id,
        "title": title,
        "data": f"data/{scene_id}.json",
        "counts": {key: len(value) for key, value in record["layers"].items()},
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--benchmark-root", type=Path, required=True)
    parser.add_argument("--max-points", type=int, default=120_000)
    parser.add_argument("--output", type=Path,
                        default=Path(__file__).parent / "reports" / "scene3d" / "data")
    args = parser.parse_args()
    root = args.benchmark_root.resolve()
    out_dir = args.output.resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    scenes = [build_scene(root, out_dir, scene_id, title, args.max_points)
              for scene_id, title in SCENES.items()]
    (out_dir / "manifest.json").write_text(
        json.dumps({"scenes": scenes}, indent=2), encoding="utf-8")
    for scene in scenes:
        print(f"{scene['title']}: {scene['counts']}")


if __name__ == "__main__":
    main()
