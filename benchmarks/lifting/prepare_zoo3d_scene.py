"""Export a prepared lifting scene to Zoo3D's posed-image layout.

Zoo3D's ScanNet posed-image loader reads 640x480 RGB-D frames but rescales a
1280x960 calibration internally.  This exporter therefore resizes the prepared
frames to 640x480 and writes the mathematically equivalent 1280x960 intrinsic.
Camera poses and reconstruction points remain in the benchmark's metric world
frame.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image


ZOO_IMAGE_SIZE = (640, 480)
ZOO_INTRINSIC_SIZE = (1280, 960)


def _numeric_files(directory: Path, suffix: str) -> list[Path]:
    files = [path for path in directory.glob(f"*{suffix}") if path.stem.isdigit()]
    return sorted(files, key=lambda path: int(path.stem))


def _scaled_intrinsic(
    intrinsic: np.ndarray,
    source_size: tuple[int, int],
    calibration_size: tuple[int, int] = ZOO_INTRINSIC_SIZE,
) -> np.ndarray:
    if intrinsic.shape != (4, 4):
        raise ValueError(f"expected a 4x4 intrinsic, got {intrinsic.shape}")
    source_width, source_height = source_size
    target_width, target_height = calibration_size
    result = intrinsic.astype(np.float64, copy=True)
    result[0, :] *= target_width / source_width
    result[1, :] *= target_height / source_height
    result[2:, :] = intrinsic[2:, :]
    return result


def export_scene(
    scannet_dir: Path,
    initial_points_path: Path,
    zoo_data_root: Path,
    scene_id: str,
) -> dict:
    frames_dir = scannet_dir / "frames"
    color_paths = _numeric_files(frames_dir / "color", ".png")
    if not color_paths:
        raise FileNotFoundError(f"no color frames in {frames_dir / 'color'}")

    frame_ids = [int(path.stem) for path in color_paths]
    expected = list(range(len(frame_ids)))
    if frame_ids != expected:
        raise ValueError(f"Zoo3D export requires contiguous frame ids; got {frame_ids}")

    scene_dir = zoo_data_root / "rec_posed_images" / scene_id
    scene_dir.mkdir(parents=True, exist_ok=True)
    with Image.open(color_paths[0]) as first_image:
        source_size = first_image.size

    source_intrinsic = np.loadtxt(
        frames_dir / "intrinsic" / "intrinsic_color.txt", dtype=np.float64
    )
    zoo_intrinsic = _scaled_intrinsic(source_intrinsic, source_size)
    np.savetxt(scene_dir / "intrinsic.txt", zoo_intrinsic, fmt="%.10f")

    for frame_id, color_path in enumerate(color_paths):
        depth_path = frames_dir / "depth" / f"{frame_id}.png"
        pose_path = frames_dir / "pose" / f"{frame_id}.txt"
        if not depth_path.exists() or not pose_path.exists():
            raise FileNotFoundError(f"missing depth or pose for frame {frame_id}")

        with Image.open(color_path) as image:
            image.convert("RGB").resize(
                ZOO_IMAGE_SIZE, Image.Resampling.BILINEAR
            ).save(scene_dir / f"{frame_id:05d}.jpg", quality=95)
        with Image.open(depth_path) as depth:
            if depth.mode not in ("I;16", "I"):
                raise ValueError(f"expected uint16 depth at {depth_path}, got {depth.mode}")
            depth.resize(ZOO_IMAGE_SIZE, Image.Resampling.NEAREST).save(
                scene_dir / f"{frame_id:05d}.png"
            )
        shutil.copy2(pose_path, scene_dir / f"{frame_id:05d}.txt")

    initial = np.load(initial_points_path, allow_pickle=False)
    points = np.asarray(initial["points"], dtype=np.float32)
    colors = np.asarray(initial["colors"], dtype=np.float32)
    if points.ndim != 2 or points.shape[1] != 3 or colors.shape != points.shape:
        raise ValueError(
            f"expected matching Nx3 points/colors, got {points.shape}/{colors.shape}"
        )
    if not np.isfinite(points).all() or not np.isfinite(colors).all():
        raise ValueError("initial point cloud contains non-finite values")
    point_dir = zoo_data_root / "points_dust3r_posed"
    point_dir.mkdir(parents=True, exist_ok=True)
    point_path = point_dir / f"{scene_id}.bin"
    np.concatenate([points, colors], axis=1).astype(np.float32).tofile(point_path)

    manifest = {
        "format": "zoo3d-posed-images-interop-v0",
        "scene_id": scene_id,
        "source_scannet_dir": str(scannet_dir.resolve()),
        "source_initial_points": str(initial_points_path.resolve()),
        "coordinate_frame": "unchanged benchmark metric world frame",
        "depth_unit": "uint16 millimetres",
        "source_image_size": list(source_size),
        "zoo_image_size": list(ZOO_IMAGE_SIZE),
        "zoo_intrinsic_calibration_size": list(ZOO_INTRINSIC_SIZE),
        "frame_ids": frame_ids,
        "point_count": int(len(points)),
    }
    (scene_dir / "interop_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scannet-dir", required=True, type=Path)
    parser.add_argument("--initial-points", required=True, type=Path)
    parser.add_argument("--zoo-data-root", required=True, type=Path)
    parser.add_argument("--scene-id", required=True)
    args = parser.parse_args()
    manifest = export_scene(
        args.scannet_dir, args.initial_points, args.zoo_data_root, args.scene_id
    )
    print(
        f"exported {len(manifest['frame_ids'])} frames and "
        f"{manifest['point_count']} points for {args.scene_id}"
    )


if __name__ == "__main__":
    main()
