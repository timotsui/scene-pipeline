"""Build the legacy fixed-proposal SliceVote ablation scene bundle.

The benchmark starts from fixed Splat Analyzer proposals and SAM founding
masks.  This adapter changes no proposal geometry: it only writes the camera,
mask, graph, and shell files expected by ``entangled_gen/slicevote.py``.
It is not the pipeline lifter and must never be reported as that method.
The room shell is estimated from the reconstruction points and camera path;
ground-truth object boxes are never read.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
from pathlib import Path

import numpy as np


def _read_jsonl(path: Path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if source.resolve() == target.resolve():
            return
        target.unlink()
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def _outer_peak(values: np.ndarray, threshold: float, below: bool) -> float:
    """Return the densest 4-cm surface band on one side of a camera path."""
    lo, hi = np.percentile(values, [0.1, 99.9])
    bins = max(40, int(np.ceil((hi - lo) / 0.04)))
    counts, edges = np.histogram(values, bins=bins, range=(lo, hi))
    centers = (edges[:-1] + edges[1:]) / 2.0
    valid = centers < threshold if below else centers > threshold
    if not valid.any():
        return float(lo if below else hi)
    candidates = np.nonzero(valid)[0]
    return float(centers[candidates[np.argmax(counts[candidates])]])


def estimate_shell(points: np.ndarray, cameras: np.ndarray) -> dict:
    """Estimate a conservative, axis-aligned shell without object labels."""
    xlo, xhi = np.percentile(points[:, 0], [0.5, 99.5])
    zlo, zhi = np.percentile(points[:, 2], [0.5, 99.5])
    ceiling = _outer_peak(points[:, 1], float(cameras[:, 1].min() - 0.35), True)
    floor = _outer_peak(points[:, 1], float(cameras[:, 1].max() + 0.35), False)
    if not ceiling < cameras[:, 1].min() < cameras[:, 1].max() < floor:
        raise ValueError("estimated floor/ceiling do not enclose the camera path")
    return {
        "format": "benchmark-axis-aligned-shell-v1",
        "method": "reconstruction point quantiles and dominant horizontal planes",
        "frame": {"space": "raw", "up": [0.0, -1.0, 0.0], "raw_to_render": [1.0, 1.0, 1.0]},
        "ceiling_y_raw": float(ceiling),
        "floor_y_raw": float(floor),
        "walls": [
            {"id": "XLO", "axis": "x", "plane_upright_m": float(xlo)},
            {"id": "XHI", "axis": "x", "plane_upright_m": float(xhi)},
            {"id": "ZLO", "axis": "z", "plane_upright_m": float(zlo)},
            {"id": "ZHI", "axis": "z", "plane_upright_m": float(zhi)},
        ],
    }


def prepare(
    *,
    scene_id: str,
    source_job: Path,
    proposals_path: Path,
    mask_cache: Path,
    prepared_scene: Path,
    ply: Path,
    output_scene: Path,
) -> dict:
    transforms = json.loads((source_job / "transforms.json").read_text(encoding="utf-8"))
    cache = json.loads((mask_cache / "index.json").read_text(encoding="utf-8"))
    proposals = _read_jsonl(proposals_path)
    if cache["scene_id"] != scene_id:
        raise ValueError(f"mask cache scene {cache['scene_id']!r} != {scene_id!r}")

    output_scene.mkdir(parents=True, exist_ok=True)
    rig = output_scene / "rig_sp0"
    seg = rig / "seg_batched20"
    crops = rig / "crops"
    seg.mkdir(parents=True, exist_ok=True)
    crops.mkdir(parents=True, exist_ok=True)
    _link_or_copy(ply, output_scene / "gen_raw.ply")

    frame_by_index = {index: frame for index, frame in enumerate(transforms["frames"])}
    pool = []
    member_indices = {index: [] for index in range(len(proposals))}
    detections = {}
    for cached in cache["frames"]:
        frame_index = int(cached["frame_idx"])
        view = cached["view"]
        frame = frame_by_index[frame_index]
        rows = cached["entries"]
        detections[view] = []
        _link_or_copy(mask_cache / cached["mask_file"], seg / f"{view}_masks.npy")
        sidecar = {
            "format": "exact-c2w-opencv-v1",
            "transform_matrix": frame["transform_matrix"],
            "fl_x": transforms["fl_x"],
            "fl_y": transforms["fl_y"],
            "cx": transforms["cx"],
            "cy": transforms["cy"],
            "w": transforms["w"],
            "h": transforms["h"],
        }
        (crops / f"{view}.json").write_text(json.dumps(sidecar, indent=2) + "\n", encoding="utf-8")
        for row in rows:
            object_index = int(row["object_index"])
            proposal = proposals[object_index]
            box = {
                key: float(value)
                for key, value in zip(("xmin", "ymin", "xmax", "ymax"), row["box"])
            }
            detections[view].append({"label": row["label"], "score": float(row["score"]), "box": box})
            pool_row = {
                "label": row["label"],
                "score": float(row["score"]),
                "view": view,
                "box": box,
                "lo": row.get("lo", proposal["aabb_min"]),
                "hi": row.get("hi", proposal["aabb_max"]),
                "trust": row.get("trust", [True] * 6),
                "trunc": False,
            }
            member_indices[object_index].append(len(pool))
            pool.append(pool_row)

    (seg / "detections.json").write_text(json.dumps(detections, indent=2) + "\n", encoding="utf-8")
    (rig / "lift_poolc.json").write_text(json.dumps({"pool": pool}, indent=2) + "\n", encoding="utf-8")

    nodes, manifest_objects, mapping = [], [], []
    for index, proposal in enumerate(proposals):
        node_id = f"obj_{index:03d}"
        lo = np.asarray(proposal["aabb_min"], dtype=float)
        hi = np.asarray(proposal["aabb_max"], dtype=float)
        center = ((lo + hi) / 2.0).tolist()
        size = (hi - lo).tolist()
        geometry = {"aabb_min": lo.tolist(), "aabb_max": hi.tolist(), "center": center, "size": size}
        nodes.append({"id": node_id, "name": proposal["label"], "geometry": geometry, "members": [node_id], "from": "fixed_global_proposal"})
        manifest_objects.append(
            {
                "id": node_id,
                "label": proposal["label"],
                "score": float(proposal["score"]),
                **geometry,
                "views": [],
                "n_detections": len(member_indices[index]),
                "n_whole": len(member_indices[index]),
                "members": member_indices[index],
                "flags": ["fixed_global_proposal"],
            }
        )
        mapping.append(
            {
                "id": node_id,
                "native_id": proposal.get("native_id", index),
                "object_id": proposal["object_id"],
                "label": proposal["label"],
                "score": float(proposal["score"]),
            }
        )

    (output_scene / "scene_graph.json").write_text(
        json.dumps({"resolved": {"nodes": nodes}}, indent=2) + "\n", encoding="utf-8"
    )
    (output_scene / "scene_manifest_pano2c_rc_f30.json").write_text(
        json.dumps({"scene": scene_id, "frame": {"space": "raw", "up": [0.0, -1.0, 0.0]}, "objects": manifest_objects}, indent=2) + "\n",
        encoding="utf-8",
    )

    # The analyzer's synthetic view ring may deliberately place cameras
    # outside the room.  Shell estimation must use the real capture path,
    # which is stored with the prepared benchmark scene.
    capture_transforms = json.loads(
        (prepared_scene / "transforms.json").read_text(encoding="utf-8")
    )
    camera_positions = np.asarray(
        [
            np.asarray(frame["transform_matrix"])[:3, 3]
            for frame in capture_transforms["frames"]
        ]
    )
    (rig / "pano_selfrender_meta.json").write_text(
        json.dumps({"eye_raw": camera_positions.mean(axis=0).tolist(), "note": "mean benchmark camera position; exact founding cameras are in crop sidecars"}, indent=2) + "\n",
        encoding="utf-8",
    )
    point_data = np.load(prepared_scene / "initial_points.npz")
    points = point_data["points"] if "points" in point_data else point_data[point_data.files[0]]
    shell = estimate_shell(points[:, :3], camera_positions)
    (output_scene / "room_shell.json").write_text(json.dumps(shell, indent=2) + "\n", encoding="utf-8")

    receipt = {
        "format": "hypersim-slicevote-compat-v1",
        "scene_id": scene_id,
        "source_job": str(source_job.resolve()),
        "source_proposals": str(proposals_path.resolve()),
        "source_masks": str(mask_cache.resolve()),
        "objects": len(proposals),
        "founding_observations": len(pool),
        "mapping": mapping,
        "shell": shell,
    }
    (output_scene / "benchmark_compat_manifest.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--source-job", required=True, type=Path)
    parser.add_argument("--proposals", dest="proposals_path", required=True, type=Path)
    parser.add_argument("--mask-cache", required=True, type=Path)
    parser.add_argument("--prepared-scene", required=True, type=Path)
    parser.add_argument("--ply", required=True, type=Path)
    parser.add_argument("--output-scene", required=True, type=Path)
    args = parser.parse_args()
    receipt = prepare(**vars(args))
    print(f"prepared {receipt['objects']} objects and {receipt['founding_observations']} founding observations in {args.output_scene}")


if __name__ == "__main__":
    main()
