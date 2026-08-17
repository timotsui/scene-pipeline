"""Rank small Hypersim development scenes for the lifting benchmark.

The official Hypersim repository includes per-scene semantic annotations but
not the rendered images.  This script uses those lightweight annotations to
find scenes with several common, movable indoor objects before any multi-GB
image download is started.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np


DEFAULT_TARGET_LABELS = (
    "chair",
    "table",
    "sofa",
    "bed",
    "bookshelf",
    "cabinet",
    "lamp",
    "television",
)


def instance_semantic_labels(
    object_semantic_ids: np.ndarray,
    object_instance_ids: np.ndarray,
) -> tuple[dict[int, int], dict[int, list[int]]]:
    """Return one semantic label per instance and report inconsistent IDs."""
    semantic = np.asarray(object_semantic_ids, dtype=np.int64).reshape(-1)
    instance = np.asarray(object_instance_ids, dtype=np.int64).reshape(-1)
    if semantic.shape != instance.shape:
        raise ValueError(
            f"semantic and instance arrays differ: {semantic.shape} vs {instance.shape}"
        )

    labels_by_instance: dict[int, Counter[int]] = defaultdict(Counter)
    for semantic_id, instance_id in zip(semantic, instance):
        if semantic_id > 0 and instance_id >= 0:
            labels_by_instance[int(instance_id)][int(semantic_id)] += 1

    labels: dict[int, int] = {}
    conflicts: dict[int, list[int]] = {}
    for instance_id, candidates in labels_by_instance.items():
        winner = candidates.most_common(1)[0][0]
        labels[instance_id] = winner
        if len(candidates) > 1:
            conflicts[instance_id] = sorted(candidates)
    return labels, conflicts


def instance_label_counts(
    object_semantic_ids: np.ndarray,
    object_instance_ids: np.ndarray,
) -> tuple[Counter[int], dict[int, list[int]]]:
    """Count instances per semantic class."""
    labels, conflicts = instance_semantic_labels(
        object_semantic_ids, object_instance_ids
    )
    return Counter(labels.values()), conflicts


def _read_hdf5(path: Path) -> np.ndarray:
    try:
        import h5py
    except ImportError as error:
        raise SystemExit(
            "h5py is required. Use the isolated hypersim_bench environment "
            "documented in benchmarks/lifting/README.md."
        ) from error
    with h5py.File(path, "r") as handle:
        if "dataset" not in handle:
            raise ValueError(f"{path} has no 'dataset' array")
        return np.asarray(handle["dataset"])


def _semantic_names(path: Path) -> dict[int, str]:
    result = {}
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            clean = {key.strip(): value.strip() for key, value in row.items()}
            result[int(clean["semantic_id"])] = clean["semantic_name"]
    return result


def _public_scene_metadata(analysis_dir: Path) -> dict[str, dict]:
    split_path = analysis_dir / "metadata_images_split_scene_v1.csv"
    result: dict[str, dict] = {}
    camera_frames: dict[tuple[str, str], int] = Counter()
    with split_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["included_in_public_release"].strip().lower() != "true":
                continue
            scene = row["scene_name"].strip()
            camera = row["camera_name"].strip()
            partition = row["split_partition_name"].strip()
            camera_frames[(scene, camera)] += 1
            entry = result.setdefault(
                scene,
                {"split": partition, "public_frames": 0, "cameras": {}},
            )
            if entry["split"] != partition:
                raise ValueError(f"scene {scene} appears in multiple splits")
            entry["public_frames"] += 1
    for (scene, camera), count in camera_frames.items():
        result[scene]["cameras"][camera] = count

    trajectories_path = analysis_dir / "metadata_camera_trajectories.csv"
    with trajectories_path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            animation = row["Animation"].strip()
            if "_cam_" not in animation:
                continue
            scene, camera_suffix = animation.rsplit("_cam_", 1)
            if scene not in result:
                continue
            entry = result[scene]
            entry["scene_type"] = row["Scene type"].strip()
            entry["notes"] = row["Notes"].strip()
            camera = f"cam_{camera_suffix}"
            if camera in entry["cameras"]:
                entry["cameras"][camera] = int(entry["cameras"][camera])
    return result


def pinhole_projection_error(row: dict[str, str]) -> float:
    """Distance from Hypersim's projection matrix to a pinhole form.

    A shifted principal point is still a normal pinhole camera, so M02 and
    M12 are intentionally allowed. Non-zero values in the entries below
    indicate the tilt-shift projection that ordinary 3DGS renderers cannot
    reproduce exactly.
    """
    expected_zero = ("01", "03", "10", "13", "20", "21", "30", "31", "33")
    residuals = [float(row[f"M_proj_{suffix}"]) for suffix in expected_zero]
    residuals.append(float(row["M_proj_32"]) + 1.0)
    return float(np.linalg.norm(residuals))


def _camera_parameters(hypersim_repo: Path) -> dict[str, dict[str, str]]:
    path = (
        hypersim_repo
        / "contrib"
        / "mikeroberts3000"
        / "metadata_camera_parameters.csv"
    )
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {row["scene_name"].strip(): row for row in csv.DictReader(handle)}


def rank_scenes(
    hypersim_repo: Path,
    partition: str,
    target_labels: tuple[str, ...],
    max_pinhole_error: float,
) -> list[dict]:
    dataset = hypersim_repo / "evermotion_dataset"
    metadata = _public_scene_metadata(dataset / "analysis")
    label_names = _semantic_names(
        hypersim_repo
        / "code"
        / "cpp"
        / "tools"
        / "scene_annotation_tool"
        / "semantic_label_descs.csv"
    )
    camera_parameters = _camera_parameters(hypersim_repo)

    ranked = []
    for scene_dir in sorted((dataset / "scenes").glob("ai_*")):
        scene = scene_dir.name
        scene_meta = metadata.get(scene)
        if scene_meta is None or scene_meta["split"] != partition:
            continue
        projection_error = pinhole_projection_error(camera_parameters[scene])
        if projection_error > max_pinhole_error:
            continue
        mesh_dir = scene_dir / "_detail" / "mesh"
        semantic_path = mesh_dir / "mesh_objects_si.hdf5"
        instance_path = mesh_dir / "mesh_objects_sii.hdf5"
        if not semantic_path.exists() or not instance_path.exists():
            continue
        semantic_counts, conflicts = instance_label_counts(
            _read_hdf5(semantic_path), _read_hdf5(instance_path)
        )
        named_counts = {
            label_names.get(label_id, f"semantic_{label_id}"): count
            for label_id, count in semantic_counts.items()
        }
        target_counts = {
            label: int(named_counts.get(label, 0)) for label in target_labels
        }
        diversity = sum(count > 0 for count in target_counts.values())
        useful_instances = sum(min(count, 4) for count in target_counts.values())
        best_camera, best_camera_frames = max(
            scene_meta["cameras"].items(), key=lambda item: item[1]
        )
        # Diversity matters more than a room containing many copies of one item.
        score = 10 * diversity + useful_instances + min(best_camera_frames, 100) / 100
        ranked.append(
            {
                "scene_id": scene,
                "split": partition,
                "scene_type": scene_meta.get("scene_type", ""),
                "notes": scene_meta.get("notes", ""),
                "recommended_camera": best_camera,
                "recommended_camera_public_frames": best_camera_frames,
                "public_frames": scene_meta["public_frames"],
                "pinhole_projection_error": projection_error,
                "target_instance_counts": target_counts,
                "target_diversity": diversity,
                "score": round(score, 2),
                "annotation_conflicts": len(conflicts),
            }
        )
    return sorted(ranked, key=lambda item: (-item["score"], item["scene_id"]))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hypersim-repo", required=True, type=Path)
    parser.add_argument("--split", default="train", choices=("train", "val", "test"))
    parser.add_argument("--top", default=20, type=int)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--labels", nargs="+", default=list(DEFAULT_TARGET_LABELS))
    parser.add_argument(
        "--max-pinhole-error",
        type=float,
        default=1e-5,
        help="reject non-pinhole tilt-shift scenes (default: %(default)g)",
    )
    args = parser.parse_args()

    ranked = rank_scenes(
        args.hypersim_repo,
        args.split,
        tuple(args.labels),
        args.max_pinhole_error,
    )
    selected = ranked[: args.top]
    text = json.dumps(selected, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
        print(f"wrote {len(selected)} candidates to {args.output}")
    else:
        print(text, end="")


if __name__ == "__main__":
    main()
