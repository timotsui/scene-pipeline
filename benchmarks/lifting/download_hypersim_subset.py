"""Plan or download one small, frame-aligned Hypersim scene subset.

This wraps the official range-request downloader instead of saving a complete
1--20 GB scene archive.  A single archive index is opened and the same evenly
spaced frame IDs are used for every requested image modality.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import shutil
import zipfile
from pathlib import Path

import numpy as np


FRAME_RE = re.compile(r"/frame\.(\d{4})\.")
FRAME_ROLES = {
    "preview": "final_preview/frame.{frame:04d}.color.jpg",
    "color": "final_hdf5/frame.{frame:04d}.color.hdf5",
    "position": "geometry_hdf5/frame.{frame:04d}.position.hdf5",
    "semantic_instance": (
        "geometry_hdf5/frame.{frame:04d}.semantic_instance.hdf5"
    ),
}


def _load_official_downloader(repo: Path):
    path = repo / "contrib" / "99991" / "download.py"
    if not path.exists():
        raise FileNotFoundError(f"official Hypersim downloader not found: {path}")
    spec = importlib.util.spec_from_file_location("hypersim_official_download", path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _evenly_spaced(values: list[int], maximum: int | None) -> list[int]:
    if not values:
        raise ValueError("no frame IDs are common to all requested modalities")
    if maximum is None or maximum >= len(values):
        return values
    if maximum <= 0:
        raise ValueError("--max-frames must be positive")
    indices = np.linspace(0, len(values) - 1, maximum).round().astype(int)
    return [values[index] for index in indices]


def _detail_suffixes(camera: str) -> tuple[str, ...]:
    return (
        "/_detail/metadata_scene.csv",
        "/_detail/metadata_cameras.csv",
        f"/_detail/{camera}/camera_keyframe_frame_indices.hdf5",
        f"/_detail/{camera}/camera_keyframe_orientations.hdf5",
        f"/_detail/{camera}/camera_keyframe_positions.hdf5",
        f"/_detail/{camera}/metadata_camera.csv",
        (
            "/_detail/mesh/"
            "metadata_semantic_instance_bounding_box_object_aligned_2d_"
            "extents.hdf5"
        ),
        (
            "/_detail/mesh/"
            "metadata_semantic_instance_bounding_box_object_aligned_2d_"
            "orientations.hdf5"
        ),
        (
            "/_detail/mesh/"
            "metadata_semantic_instance_bounding_box_object_aligned_2d_"
            "positions.hdf5"
        ),
    )


def select_entries(
    entries: list[zipfile.ZipInfo],
    camera: str,
    roles: tuple[str, ...],
    maximum: int | None,
) -> tuple[list[zipfile.ZipInfo], list[int]]:
    by_name = {entry.filename.replace("\\", "/"): entry for entry in entries}
    scene_prefixes = {name.split("/", 1)[0] for name in by_name if "/" in name}
    if len(scene_prefixes) != 1:
        raise ValueError(f"expected one scene in archive, found {scene_prefixes}")
    scene = next(iter(scene_prefixes))

    frame_roles = [role for role in roles if role in FRAME_ROLES]
    available_by_role: dict[str, set[int]] = {}
    for role in frame_roles:
        marker = f"/images/scene_{camera}_{FRAME_ROLES[role].split('/')[0]}/"
        frames = set()
        for name in by_name:
            if marker not in name:
                continue
            match = FRAME_RE.search(name)
            if match and name.endswith(FRAME_ROLES[role].split("{frame:04d}")[1]):
                frames.add(int(match.group(1)))
        available_by_role[role] = frames

    frame_ids: list[int] = []
    if frame_roles:
        common = set.intersection(*(available_by_role[role] for role in frame_roles))
        frame_ids = _evenly_spaced(sorted(common), maximum)

    selected_names = set()
    if "detail" in roles:
        for suffix in _detail_suffixes(camera):
            name = scene + suffix
            if name not in by_name:
                raise FileNotFoundError(f"required Hypersim metadata missing: {name}")
            selected_names.add(name)
    for role in frame_roles:
        for frame in frame_ids:
            name = f"{scene}/images/scene_{camera}_{FRAME_ROLES[role].format(frame=frame)}"
            if name not in by_name:
                raise FileNotFoundError(f"required aligned frame missing: {name}")
            selected_names.add(name)

    return [by_name[name] for name in sorted(selected_names)], frame_ids


def _safe_destination(root: Path, archive_name: str) -> Path:
    root = root.resolve()
    destination = (root / archive_name).resolve()
    if root != destination and root not in destination.parents:
        raise ValueError(f"archive path escapes output root: {archive_name}")
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-repo", required=True, type=Path)
    parser.add_argument("--scene", required=True)
    parser.add_argument("--camera", default="cam_00")
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--roles",
        nargs="+",
        choices=("detail", *FRAME_ROLES),
        default=("detail", "color", "position", "semantic_instance"),
    )
    parser.add_argument("--max-frames", type=int, default=50)
    parser.add_argument("--download", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()

    official = _load_official_downloader(args.official_repo)
    urls = [url for url in official.URLS if f"/{args.scene}.zip" in url]
    if len(urls) != 1:
        raise ValueError(f"expected one official URL for {args.scene}, found {urls}")

    session = official.requests.session()
    remote = official.WebFile(urls[0], session)
    with zipfile.ZipFile(remote) as archive:
        selected, frame_ids = select_entries(
            archive.infolist(), args.camera, tuple(args.roles), args.max_frames
        )
        plan = {
            "format": "hypersim-subset-plan-v0",
            "source_url": urls[0],
            "scene_id": args.scene,
            "camera": args.camera,
            "roles": list(args.roles),
            "frame_ids": frame_ids,
            "archive_bytes": remote.size,
            "selected_compressed_bytes": sum(item.compress_size for item in selected),
            "selected_uncompressed_bytes": sum(item.file_size for item in selected),
            "files": [item.filename for item in selected],
        }
        args.output.mkdir(parents=True, exist_ok=True)
        plan_path = args.output / f"{args.scene}.{args.camera}.subset-plan.json"
        plan_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
        print(
            f"planned {len(selected)} files / {len(frame_ids)} aligned frames; "
            f"{plan['selected_compressed_bytes'] / 2**30:.2f} GiB compressed"
        )
        if not args.download:
            print(f"plan only; wrote {plan_path}")
            return

        for index, item in enumerate(selected, 1):
            destination = _safe_destination(args.output, item.filename)
            if (
                destination.exists()
                and destination.stat().st_size == item.file_size
                and not args.overwrite
            ):
                print(f"[{index}/{len(selected)}] keep {item.filename}")
                continue
            destination.parent.mkdir(parents=True, exist_ok=True)
            print(f"[{index}/{len(selected)}] download {item.filename}", flush=True)
            with archive.open(item) as source, destination.open("wb") as target:
                shutil.copyfileobj(source, target, length=2**20)
            if destination.stat().st_size != item.file_size:
                raise IOError(f"size mismatch after extracting {item.filename}")
    print(f"downloaded Hypersim subset to {args.output}")


if __name__ == "__main__":
    main()
