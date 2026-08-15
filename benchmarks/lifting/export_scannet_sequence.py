"""Export an analyzer render job as the ScanNet-style sequence Boxer reads.

This is an interoperability exporter, not a ScanNet dataset converter. It
copies RGB frames, converts metric float depth to uint16 millimetres, and
writes OpenCV camera-to-world poses. The source job must first pass the G1
camera-convention check in ``entangled_gen/analyzer/cams_from_transforms.py``.
"""

from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

import numpy as np
from PIL import Image


SUPPORTED_CONVENTIONS = {
    "c2w_opencv",
    "c2w_opengl",
    "w2c_opencv",
    "w2c_opengl",
}


def _as_c2w(matrix: list[list[float]], convention: str) -> np.ndarray:
    """Return an OpenCV c2w matrix (x right, y down, z forward)."""
    if convention not in SUPPORTED_CONVENTIONS:
        raise ValueError(f"unsupported camera convention: {convention}")

    result = np.asarray(matrix, dtype=np.float64)
    if result.shape != (4, 4):
        raise ValueError(f"expected a 4x4 transform, got {result.shape}")
    if convention.startswith("w2c_"):
        result = np.linalg.inv(result)
    if convention.endswith("opengl"):
        # OpenGL camera axes are x-right, y-up, z-backward. Flipping y and z
        # gives the OpenCV axes consumed by Boxer's ScanNet loader.
        result = result @ np.diag([1.0, -1.0, -1.0, 1.0])
    return result


def _frame_indices(total: int, maximum: int | None) -> list[int]:
    if total <= 0:
        raise ValueError("transforms.json has no frames")
    if maximum is None or maximum >= total:
        return list(range(total))
    if maximum <= 0:
        raise ValueError("--max-frames must be positive")
    # Cover the trajectory instead of using only its first adjacent views.
    return np.linspace(0, total - 1, maximum).round().astype(int).tolist()


def _metric_depth_path(job_dir: Path, frame: dict) -> Path:
    visual_path = job_dir / frame["depth_path"]
    index = Path(frame["file_path"]).stem.rsplit("_", 1)[-1]
    candidates = [
        visual_path.with_suffix(".npy"),
        job_dir / "frames" / f"depth_{index}.npy",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    raise FileNotFoundError(
        f"metric depth not found for {frame['file_path']}; checked {candidates}"
    )


def export_sequence(
    transforms_path: Path, output_dir: Path, maximum: int | None
) -> dict:
    job_dir = transforms_path.resolve().parent
    transforms = json.loads(transforms_path.read_text(encoding="utf-8"))
    convention_path = job_dir / "g1_convention.json"
    if not convention_path.exists():
        raise FileNotFoundError(
            f"{convention_path} is required; run the G1 camera-convention check first"
        )
    convention = json.loads(convention_path.read_text(encoding="utf-8"))["winner"]

    color_dir = output_dir / "frames" / "color"
    depth_dir = output_dir / "frames" / "depth"
    pose_dir = output_dir / "frames" / "pose"
    intrinsic_dir = output_dir / "frames" / "intrinsic"
    for directory in (color_dir, depth_dir, pose_dir, intrinsic_dir):
        directory.mkdir(parents=True, exist_ok=True)

    K = np.eye(4, dtype=np.float64)
    K[0, 0] = float(transforms["fl_x"])
    K[1, 1] = float(transforms.get("fl_y", transforms["fl_x"]))
    K[0, 2] = float(transforms["cx"])
    K[1, 2] = float(transforms["cy"])
    np.savetxt(intrinsic_dir / "intrinsic_color.txt", K, fmt="%.10f")
    np.savetxt(intrinsic_dir / "intrinsic_depth.txt", K, fmt="%.10f")

    selected = _frame_indices(len(transforms["frames"]), maximum)
    manifest_frames = []
    for output_index, source_index in enumerate(selected):
        frame = transforms["frames"][source_index]
        rgb_source = job_dir / frame["file_path"]
        if not rgb_source.exists():
            raise FileNotFoundError(rgb_source)
        shutil.copy2(rgb_source, color_dir / f"{output_index}.png")

        depth_m = np.load(_metric_depth_path(job_dir, frame), allow_pickle=False)
        if depth_m.shape != (int(transforms["h"]), int(transforms["w"])):
            raise ValueError(f"unexpected depth shape {depth_m.shape} for {rgb_source}")
        valid = np.isfinite(depth_m) & (depth_m > 0)
        depth_mm = np.zeros(depth_m.shape, dtype=np.uint16)
        depth_mm[valid] = np.clip(
            np.rint(depth_m[valid] * 1000.0), 1, np.iinfo(np.uint16).max
        ).astype(np.uint16)
        Image.fromarray(depth_mm).save(depth_dir / f"{output_index}.png")

        pose = _as_c2w(frame["transform_matrix"], convention)
        np.savetxt(pose_dir / f"{output_index}.txt", pose, fmt="%.10f")
        manifest_frames.append(
            {
                "output_frame": output_index,
                "source_frame": source_index,
                "source_rgb": frame["file_path"],
                "source_metric_depth": str(
                    _metric_depth_path(job_dir, frame).relative_to(job_dir)
                ),
            }
        )

    manifest = {
        "format": "boxer_scannet_interop_v0",
        "source_transforms": str(transforms_path.resolve()),
        "camera_convention": convention,
        "depth_unit": "uint16 millimetres",
        "coordinate_frame": "source world; Boxer subtracts the first camera translation while loading",
        "boxer_world_offset_source": _as_c2w(
            transforms["frames"][selected[0]]["transform_matrix"], convention
        )[:3, 3].tolist(),
        "width": int(transforms["w"]),
        "height": int(transforms["h"]),
        "frames": manifest_frames,
    }
    (output_dir / "export_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transforms", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--max-frames", type=int)
    args = parser.parse_args()
    manifest = export_sequence(args.transforms, args.output, args.max_frames)
    print(
        f"exported {len(manifest['frames'])} frames to {args.output} "
        f"({manifest['camera_convention']})"
    )


if __name__ == "__main__":
    main()
