"""Convert one downloaded Hypersim subset into a metric 3DGS benchmark.

Outputs include tone-mapped training images, exact cameras, metric point depth,
a COLMAP model initialized from Hypersim world-position images, visible-object
ground truth, a Boxer-compatible RGB-D sequence, and projected-box overlays.
The benchmark frame is rotated so physical up is -Y, matching the PLY frame
expected by Splat Analyzer.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import shutil
import struct
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

try:
    from .select_hypersim_scenes import (
        DEFAULT_TARGET_LABELS,
        instance_semantic_labels,
        pinhole_projection_error,
    )
except ImportError:
    from select_hypersim_scenes import (  # type: ignore
        DEFAULT_TARGET_LABELS,
        instance_semantic_labels,
        pinhole_projection_error,
    )


HYPERSIM_TO_SPLAT = np.array(
    [[1.0, 0.0, 0.0], [0.0, 0.0, -1.0], [0.0, 1.0, 0.0]],
    dtype=np.float64,
)
OPENGL_TO_OPENCV = np.diag([1.0, -1.0, -1.0])
BOX_EDGES = (
    (0, 1),
    (0, 2),
    (0, 4),
    (1, 3),
    (1, 5),
    (2, 3),
    (2, 6),
    (3, 7),
    (4, 5),
    (4, 6),
    (5, 7),
    (6, 7),
)


def _hdf5(path: Path) -> np.ndarray:
    try:
        import h5py
    except ImportError as error:
        raise SystemExit(
            "h5py is required; use the hypersim_bench Conda environment"
        ) from error
    with h5py.File(path, "r") as handle:
        return np.asarray(handle["dataset"])


def projection_to_intrinsics(row: dict[str, str], width: int, height: int):
    error = pinhole_projection_error(row)
    if error > 1e-5:
        raise ValueError(
            f"scene uses a non-pinhole tilt-shift projection (error {error:.6g})"
        )
    fx = 0.5 * (width - 1) * float(row["M_proj_00"])
    fy = 0.5 * (height - 1) * float(row["M_proj_11"])
    cx = 0.5 * (width - 1) * (1.0 - float(row["M_proj_02"]))
    cy = 0.5 * (height - 1) * (1.0 + float(row["M_proj_12"]))
    return fx, fy, cx, cy


def rotation_matrix_to_qvec(rotation: np.ndarray) -> np.ndarray:
    """COLMAP world-to-camera rotation matrix to [qw, qx, qy, qz]."""
    r = np.asarray(rotation, dtype=np.float64)
    if r.shape != (3, 3):
        raise ValueError(f"rotation must be 3x3, got {r.shape}")
    trace = float(np.trace(r))
    if trace > 0:
        scale = 2.0 * math.sqrt(trace + 1.0)
        qvec = np.array(
            [
                0.25 * scale,
                (r[2, 1] - r[1, 2]) / scale,
                (r[0, 2] - r[2, 0]) / scale,
                (r[1, 0] - r[0, 1]) / scale,
            ]
        )
    else:
        axis = int(np.argmax(np.diag(r)))
        if axis == 0:
            scale = 2.0 * math.sqrt(1.0 + r[0, 0] - r[1, 1] - r[2, 2])
            qvec = np.array(
                [
                    (r[2, 1] - r[1, 2]) / scale,
                    0.25 * scale,
                    (r[0, 1] + r[1, 0]) / scale,
                    (r[0, 2] + r[2, 0]) / scale,
                ]
            )
        elif axis == 1:
            scale = 2.0 * math.sqrt(1.0 + r[1, 1] - r[0, 0] - r[2, 2])
            qvec = np.array(
                [
                    (r[0, 2] - r[2, 0]) / scale,
                    (r[0, 1] + r[1, 0]) / scale,
                    0.25 * scale,
                    (r[1, 2] + r[2, 1]) / scale,
                ]
            )
        else:
            scale = 2.0 * math.sqrt(1.0 + r[2, 2] - r[0, 0] - r[1, 1])
            qvec = np.array(
                [
                    (r[1, 0] - r[0, 1]) / scale,
                    (r[0, 2] + r[2, 0]) / scale,
                    (r[1, 2] + r[2, 1]) / scale,
                    0.25 * scale,
                ]
            )
    qvec /= np.linalg.norm(qvec)
    if qvec[0] < 0:
        qvec *= -1
    return qvec


def _tone_map(rgb: np.ndarray, valid: np.ndarray) -> np.ndarray:
    rgb = np.asarray(rgb, dtype=np.float32)
    good = valid & np.isfinite(rgb).all(axis=2)
    brightness = 0.3 * rgb[..., 0] + 0.59 * rgb[..., 1] + 0.11 * rgb[..., 2]
    if np.count_nonzero(good) == 0:
        scale = 1.0
    else:
        current = float(np.percentile(brightness[good], 90))
        scale = 0.0 if current < 1e-4 else 0.8 ** 2.2 / current
    mapped = np.power(np.maximum(scale * np.nan_to_num(rgb), 0.0), 1.0 / 2.2)
    return np.rint(np.clip(mapped, 0.0, 1.0) * 255.0).astype(np.uint8)


def _read_parameter_csv(path: Path) -> dict[str, str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return {
            row["parameter_name"].strip(): row["parameter_value"].strip()
            for row in csv.DictReader(handle)
        }


def _camera_parameters(repo: Path, scene: str) -> dict[str, str]:
    path = repo / "contrib" / "mikeroberts3000" / "metadata_camera_parameters.csv"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        for row in csv.DictReader(handle):
            if row["scene_name"].strip() == scene:
                return row
    raise KeyError(f"no camera parameters for {scene}")


def _semantic_names(repo: Path) -> dict[int, str]:
    path = (
        repo
        / "code"
        / "cpp"
        / "tools"
        / "scene_annotation_tool"
        / "semantic_label_descs.csv"
    )
    with path.open(encoding="utf-8-sig", newline="") as handle:
        result = {}
        for row in csv.DictReader(handle):
            clean = {key.strip(): value.strip() for key, value in row.items()}
            result[int(clean["semantic_id"])] = clean["semantic_name"]
        return result


def _box_corners(center: np.ndarray, rotation: np.ndarray, extents: np.ndarray):
    signs = np.array(
        [[x, y, z] for x in (-0.5, 0.5) for y in (-0.5, 0.5) for z in (-0.5, 0.5)]
    )
    return center + (signs * extents) @ rotation.T


def _write_colmap_model(
    sparse_dir: Path,
    width: int,
    height: int,
    intrinsics: tuple[float, float, float, float],
    frames: list[dict],
    points: np.ndarray,
    colors: np.ndarray,
) -> None:
    sparse_dir.mkdir(parents=True, exist_ok=True)
    fx, fy, cx, cy = intrinsics
    with (sparse_dir / "cameras.bin").open("wb") as handle:
        handle.write(struct.pack("<Q", 1))
        handle.write(struct.pack("<iiQQ", 1, 1, width, height))  # PINHOLE = 1
        handle.write(struct.pack("<dddd", fx, fy, cx, cy))

    with (sparse_dir / "images.bin").open("wb") as handle:
        handle.write(struct.pack("<Q", len(frames)))
        for image_id, frame in enumerate(frames, 1):
            c2w = np.asarray(frame["c2w_opencv"], dtype=np.float64)
            rotation = c2w[:3, :3].T
            translation = -rotation @ c2w[:3, 3]
            qvec = rotation_matrix_to_qvec(rotation)
            handle.write(struct.pack("<i", image_id))
            handle.write(struct.pack("<ddddddd", *qvec, *translation))
            handle.write(struct.pack("<i", 1))
            handle.write(frame["image_name"].encode("utf-8") + b"\x00")
            handle.write(struct.pack("<Q", 0))

    with (sparse_dir / "points3D.bin").open("wb") as handle:
        handle.write(struct.pack("<Q", len(points)))
        for point_id, (point, color) in enumerate(zip(points, colors), 1):
            handle.write(
                struct.pack(
                    "<QdddBBBdQ",
                    point_id,
                    *point.astype(float),
                    *color.astype(int),
                    0.0,
                    0,
                )
            )


def _project(corners: np.ndarray, c2w: np.ndarray, intrinsics):
    fx, fy, cx, cy = intrinsics
    rotation = c2w[:3, :3]
    cam = (corners - c2w[:3, 3]) @ rotation
    z = cam[:, 2]
    uv = np.column_stack((fx * cam[:, 0] / z + cx, fy * cam[:, 1] / z + cy))
    return uv, z


def _jsonl(path: Path, records: list[dict]) -> None:
    path.write_text(
        "".join(json.dumps(record, separators=(",", ":")) + "\n" for record in records),
        encoding="utf-8",
    )


def prepare(args) -> dict:
    plan_path = args.source_root / f"{args.scene}.{args.camera}.subset-plan.json"
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    frame_ids = [int(frame) for frame in plan["frame_ids"]]
    scene_dir = args.source_root / args.scene
    detail = scene_dir / "_detail"
    images_source = scene_dir / "images"
    args.output.mkdir(parents=True, exist_ok=True)
    images_out = args.output / "images"
    depth_out = args.output / "depth"
    overlay_out = args.output / "overlays"
    scannet = args.output / "scannet"
    for directory in (
        images_out,
        depth_out,
        overlay_out,
        scannet / "frames" / "color",
        scannet / "frames" / "depth",
        scannet / "frames" / "pose",
        scannet / "frames" / "intrinsic",
    ):
        directory.mkdir(parents=True, exist_ok=True)

    scene_parameters = _read_parameter_csv(detail / "metadata_scene.csv")
    meters_per_asset_unit = float(scene_parameters["meters_per_asset_unit"])
    camera_row = _camera_parameters(args.official_repo, args.scene)
    source_width = int(float(camera_row["settings_output_img_width"]))
    source_height = int(float(camera_row["settings_output_img_height"]))
    width = source_width // args.downscale
    height = source_height // args.downscale
    intrinsics = projection_to_intrinsics(camera_row, width, height)
    fx, fy, cx, cy = intrinsics

    camera_dir = detail / args.camera
    camera_indices = _hdf5(camera_dir / "camera_keyframe_frame_indices.hdf5").reshape(-1)
    camera_positions = _hdf5(camera_dir / "camera_keyframe_positions.hdf5")
    camera_orientations = _hdf5(camera_dir / "camera_keyframe_orientations.hdf5")
    camera_lookup = {int(frame): index for index, frame in enumerate(camera_indices)}

    annotations = args.official_repo / "evermotion_dataset" / "scenes" / args.scene / "_detail" / "mesh"
    object_semantic = _hdf5(annotations / "mesh_objects_si.hdf5")
    object_instance = _hdf5(annotations / "mesh_objects_sii.hdf5")
    labels_by_instance, annotation_conflicts = instance_semantic_labels(
        object_semantic, object_instance
    )
    semantic_names = _semantic_names(args.official_repo)

    mesh = detail / "mesh"
    box_extents = _hdf5(
        mesh / "metadata_semantic_instance_bounding_box_object_aligned_2d_extents.hdf5"
    )
    box_orientations = _hdf5(
        mesh / "metadata_semantic_instance_bounding_box_object_aligned_2d_orientations.hdf5"
    )
    box_positions = _hdf5(
        mesh / "metadata_semantic_instance_bounding_box_object_aligned_2d_positions.hdf5"
    )

    boxes = {}
    for instance_id, semantic_id in labels_by_instance.items():
        if instance_id >= len(box_extents):
            continue
        center = np.asarray(box_positions[instance_id], dtype=np.float64)
        rotation = np.asarray(box_orientations[instance_id], dtype=np.float64)
        extents = np.asarray(box_extents[instance_id], dtype=np.float64)
        if not (np.isfinite(center).all() and np.isfinite(rotation).all() and np.isfinite(extents).all()):
            continue
        if np.any(extents <= 0):
            continue
        corners_h = _box_corners(center, rotation, extents) * meters_per_asset_unit
        corners_s = corners_h @ HYPERSIM_TO_SPLAT.T
        boxes[instance_id] = {
            "scene_id": args.scene,
            "object_id": f"sii_{instance_id:03d}",
            "label": semantic_names.get(semantic_id, f"semantic_{semantic_id}"),
            "aabb_min": corners_s.min(axis=0).tolist(),
            "aabb_max": corners_s.max(axis=0).tolist(),
            "native_obb_center_hypersim_asset": center.tolist(),
            "native_obb_extents_hypersim_asset": extents.tolist(),
            "native_obb_orientation_hypersim": rotation.tolist(),
            "_corners": corners_s,
        }

    visibility = defaultdict(lambda: {"pixels": 0, "frames": [], "max_pixels": 0})
    point_chunks, color_chunks, frames = [], [], []
    frame_images = {}
    geometry_dir = images_source / f"scene_{args.camera}_geometry_hdf5"
    color_dir = images_source / f"scene_{args.camera}_final_hdf5"
    for output_index, frame_id in enumerate(frame_ids):
        row = camera_lookup[frame_id]
        position_h = _hdf5(geometry_dir / f"frame.{frame_id:04d}.position.hdf5").astype(np.float32)
        semantic_instance = _hdf5(
            geometry_dir / f"frame.{frame_id:04d}.semantic_instance.hdf5"
        ).astype(np.int32)
        rgb_hdr = _hdf5(color_dir / f"frame.{frame_id:04d}.color.hdf5").astype(np.float32)
        valid = np.isfinite(position_h).all(axis=2)
        rgb = _tone_map(rgb_hdr, valid)

        image_name = f"frame_{frame_id:04d}.png"
        image = Image.fromarray(rgb).resize((width, height), Image.Resampling.LANCZOS)
        image.save(images_out / image_name)
        shutil.copy2(images_out / image_name, scannet / "frames" / "color" / f"{output_index}.png")
        frame_images[frame_id] = image.copy()

        c2w_gl = np.eye(4, dtype=np.float64)
        c2w_gl[:3, :3] = HYPERSIM_TO_SPLAT @ camera_orientations[row]
        c2w_gl[:3, 3] = (
            HYPERSIM_TO_SPLAT @ camera_positions[row] * meters_per_asset_unit
        )
        c2w_cv = c2w_gl.copy()
        c2w_cv[:3, :3] = c2w_gl[:3, :3] @ OPENGL_TO_OPENCV

        position_s = (position_h * meters_per_asset_unit) @ HYPERSIM_TO_SPLAT.T
        camera_points = (position_s - c2w_cv[:3, 3]) @ c2w_cv[:3, :3]
        depth = np.where(valid, camera_points[..., 2], 0.0).astype(np.float32)
        depth[(depth < 0) | ~np.isfinite(depth)] = 0.0
        depth_small = np.asarray(
            Image.fromarray(depth, mode="F").resize((width, height), Image.Resampling.NEAREST),
            dtype=np.float32,
        )
        np.save(depth_out / f"frame_{frame_id:04d}.npy", depth_small, allow_pickle=False)
        depth_mm = np.zeros_like(depth_small, dtype=np.uint16)
        good_depth = depth_small > 0
        depth_mm[good_depth] = np.clip(
            np.rint(depth_small[good_depth] * 1000.0), 1, np.iinfo(np.uint16).max
        ).astype(np.uint16)
        Image.fromarray(depth_mm).save(scannet / "frames" / "depth" / f"{output_index}.png")
        np.savetxt(scannet / "frames" / "pose" / f"{output_index}.txt", c2w_cv, fmt="%.10f")

        values, counts = np.unique(semantic_instance[semantic_instance >= 0], return_counts=True)
        for instance_id, count in zip(values, counts):
            entry = visibility[int(instance_id)]
            entry["pixels"] += int(count)
            entry["frames"].append(frame_id)
            entry["max_pixels"] = max(entry["max_pixels"], int(count))

        sampled_points = position_s[:: args.point_stride, :: args.point_stride]
        sampled_colors = rgb[:: args.point_stride, :: args.point_stride]
        sampled_valid = np.isfinite(sampled_points).all(axis=2)
        point_chunks.append(sampled_points[sampled_valid])
        color_chunks.append(sampled_colors[sampled_valid])
        frames.append(
            {
                "source_frame": frame_id,
                "output_frame": output_index,
                "image_name": image_name,
                "file_path": f"images/{image_name}",
                "depth_path": f"depth/frame_{frame_id:04d}.npy",
                "transform_matrix": c2w_gl.tolist(),
                "c2w_opencv": c2w_cv.tolist(),
            }
        )

    points = np.concatenate(point_chunks, axis=0)
    colors = np.concatenate(color_chunks, axis=0)
    voxel_keys = np.floor(points / args.point_voxel_m).astype(np.int64)
    _, unique_indices = np.unique(voxel_keys, axis=0, return_index=True)
    points, colors = points[unique_indices], colors[unique_indices]
    if len(points) > args.max_initial_points:
        rng = np.random.default_rng(0)
        chosen = np.sort(rng.choice(len(points), args.max_initial_points, replace=False))
        points, colors = points[chosen], colors[chosen]

    _write_colmap_model(
        args.output / "sparse" / "0", width, height, intrinsics, frames, points, colors
    )
    np.savez_compressed(
        args.output / "initial_points.npz",
        points=points.astype(np.float32),
        colors=colors.astype(np.uint8),
    )

    K4 = np.eye(4, dtype=np.float64)
    K4[0, 0], K4[1, 1], K4[0, 2], K4[1, 2] = fx, fy, cx, cy
    for name in ("intrinsic_color.txt", "intrinsic_depth.txt"):
        np.savetxt(scannet / "frames" / "intrinsic" / name, K4, fmt="%.10f")

    target_labels = set(args.labels)
    all_targets, visible_targets = [], []
    visibility_receipt = {}
    for instance_id, box in sorted(boxes.items()):
        if box["label"] not in target_labels:
            continue
        record = {key: value for key, value in box.items() if not key.startswith("_")}
        all_targets.append(record)
        seen = visibility.get(instance_id, {"pixels": 0, "frames": [], "max_pixels": 0})
        visibility_receipt[record["object_id"]] = dict(seen)
        if seen["pixels"] >= args.min_visible_pixels and len(seen["frames"]) >= args.min_visible_frames:
            visible_targets.append(record)
    _jsonl(args.output / "ground_truth.all-targets.jsonl", all_targets)
    _jsonl(args.output / "ground_truth.visible.jsonl", visible_targets)
    (args.output / "visibility.json").write_text(
        json.dumps(visibility_receipt, indent=2) + "\n", encoding="utf-8"
    )

    overlay_frames = {frame_ids[0], frame_ids[len(frame_ids) // 2], frame_ids[-1]}
    palette = {
        label: color
        for label, color in zip(
            sorted(target_labels),
            ("#ff3355", "#00c9ff", "#ffb000", "#65d46e", "#c46dff", "#00d6a3", "#ff6ec7", "#f4e04d"),
        )
    }
    for frame in frames:
        frame_id = frame["source_frame"]
        if frame_id not in overlay_frames:
            continue
        image = frame_images[frame_id].copy()
        draw = ImageDraw.Draw(image)
        c2w = np.asarray(frame["c2w_opencv"])
        mask_source = _hdf5(
            geometry_dir / f"frame.{frame_id:04d}.semantic_instance.hdf5"
        ).astype(np.int32)
        visible_ids = set(np.unique(mask_source[mask_source >= 0]).tolist())
        for instance_id in visible_ids:
            box = boxes.get(instance_id)
            if box is None or box["label"] not in target_labels:
                continue
            uv, z = _project(box["_corners"], c2w, intrinsics)
            if np.count_nonzero(z > 0.05) < 4:
                continue
            color = palette[box["label"]]
            for left, right in BOX_EDGES:
                if z[left] > 0.05 and z[right] > 0.05:
                    draw.line((*uv[left], *uv[right]), fill=color, width=2)
            anchor = np.nanmin(uv[z > 0.05], axis=0)
            draw.text(tuple(anchor), box["label"], fill=color, stroke_width=2, stroke_fill="black")
        image.save(overlay_out / f"frame_{frame_id:04d}.boxes.png")

    transforms = {
        "camera_model": "OPENCV",
        "fl_x": fx,
        "fl_y": fy,
        "cx": cx,
        "cy": cy,
        "w": width,
        "h": height,
        "camera_convention": "c2w_opengl",
        "coordinate_frame": "Hypersim metric rotated to physical-up=-Y",
        "frames": [
            {key: frame[key] for key in ("file_path", "depth_path", "transform_matrix")}
            for frame in frames
        ],
    }
    (args.output / "transforms.json").write_text(
        json.dumps(transforms, indent=2) + "\n", encoding="utf-8"
    )

    boxer_manifest = {
        "format": "boxer_scannet_interop_v0",
        "source_transforms": str((args.output / "transforms.json").resolve()),
        "camera_convention": "c2w_opencv",
        "depth_unit": "uint16 millimetres",
        "coordinate_frame": "Hypersim metric rotated to physical-up=-Y",
        "boxer_world_offset_source": np.asarray(frames[0]["c2w_opencv"])[:3, 3].tolist(),
        "width": width,
        "height": height,
        "frames": [
            {
                "output_frame": frame["output_frame"],
                "source_frame": frame["source_frame"],
                "source_rgb": frame["file_path"],
                "source_metric_depth": frame["depth_path"],
            }
            for frame in frames
        ],
    }
    (scannet / "export_manifest.json").write_text(
        json.dumps(boxer_manifest, indent=2) + "\n", encoding="utf-8"
    )

    manifest = {
        "format": "hypersim-lifting-benchmark-v0",
        "status": "development-smoke-not-paper-frozen",
        "scene_id": args.scene,
        "camera": args.camera,
        "source_subset_plan": str(plan_path.resolve()),
        "frame_ids": frame_ids,
        "image_size": [width, height],
        "intrinsics": {"fx": fx, "fy": fy, "cx": cx, "cy": cy},
        "meters_per_asset_unit": meters_per_asset_unit,
        "hypersim_to_splat_rotation": HYPERSIM_TO_SPLAT.tolist(),
        "physical_up_splat": [0.0, -1.0, 0.0],
        "initial_points": len(points),
        "target_labels": sorted(target_labels),
        "all_target_boxes": len(all_targets),
        "visible_target_boxes": len(visible_targets),
        "visible_label_counts": dict(Counter(box["label"] for box in visible_targets)),
        "visibility_gate": {
            "minimum_total_pixels": args.min_visible_pixels,
            "minimum_frames": args.min_visible_frames,
        },
        "annotation_conflicts": annotation_conflicts,
        "artifacts": {
            "ground_truth": "ground_truth.visible.jsonl",
            "transforms": "transforms.json",
            "colmap_sparse": "sparse/0",
            "initial_points": "initial_points.npz",
            "boxer_sequence": "scannet",
            "overlays": "overlays",
        },
    }
    (args.output / "benchmark_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--official-repo", required=True, type=Path)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--camera", default="cam_00")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--downscale", type=int, default=2)
    parser.add_argument("--point-stride", type=int, default=8)
    parser.add_argument("--point-voxel-m", type=float, default=0.02)
    parser.add_argument("--max-initial-points", type=int, default=200_000)
    parser.add_argument("--min-visible-pixels", type=int, default=500)
    parser.add_argument("--min-visible-frames", type=int, default=2)
    parser.add_argument("--labels", nargs="+", default=list(DEFAULT_TARGET_LABELS))
    args = parser.parse_args()
    if args.downscale <= 0 or args.point_stride <= 0:
        parser.error("--downscale and --point-stride must be positive")
    manifest = prepare(args)
    print(
        f"prepared {manifest['scene_id']}: {len(manifest['frame_ids'])} frames, "
        f"{manifest['initial_points']} initial points, "
        f"{manifest['visible_target_boxes']} visible target boxes"
    )


if __name__ == "__main__":
    main()
