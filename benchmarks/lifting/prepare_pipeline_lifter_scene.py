"""Prepare approved Hypersim base sweeps for the pipeline lifter.

This is the end-to-end global-discovery entry point.  Base positions are
loaded by index from ``base_views.v1.json`` and the exact prepared
``transforms.json``; it accepts no Splat Analyzer jobs, proposals, masks, or
novel camera coordinates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ENTANGLED = REPO / "entangled_gen"
sys.path.insert(0, str(ENTANGLED))

import paths  # noqa: E402
from prepare_slicevote_scene import estimate_shell  # noqa: E402


CANONICAL_LABELS = [
    "chair", "table", "sofa", "bookshelf", "cabinet", "lamp", "television"
]
SYNONYMS = {
    "office chair": "chair", "armchair": "chair", "folded chair": "chair",
    "coffee table": "table", "end table": "table", "dining table": "table",
    "couch": "sofa", "shelf": "bookshelf", "bookcase": "bookshelf",
    "kitchen cabinet": "cabinet", "file cabinet": "cabinet",
    "bathroom cabinet": "cabinet", "cabinetry": "cabinet",
    "floor lamp": "lamp", "desk lamp": "lamp", "standing lamp": "lamp",
    "tv": "television",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_vocab(scene_dir: Path, scene_id: str) -> Path:
    terms = CANONICAL_LABELS + list(SYNONYMS)
    vocab = {
        "scene": scene_dir.name,
        "format": "pipeline-lifter-frozen-benchmark-vocabulary-v1",
        "dataset_scene_id": scene_id,
        "canonical": {label: ["frozen_hypersim_target"] for label in CANONICAL_LABELS},
        "synonyms": SYNONYMS,
        "queries": {
            "gdino": ". ".join(terms) + ".",
            "owlv2": ", ".join(terms),
        },
        "meta": {
            "source": "hypersim_split.v1.json frozen public target labels",
            "ground_truth_instances_read": False,
        },
    }
    path = scene_dir / "vocab.json"
    path.write_text(json.dumps(vocab, indent=2) + "\n", encoding="utf-8")
    return path


def _write_native_graph(scene_dir: Path, manifest_path: Path) -> Path:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    nodes = []
    for obj in manifest["objects"]:
        geometry = {
            key: obj[key] for key in ("aabb_min", "aabb_max", "center", "size")
        }
        nodes.append({
            "id": obj["id"], "name": obj["label"], "geometry": geometry,
            "members": [obj["id"]], "from": "pipeline_lifter_native_fusion",
        })
    graph_path = scene_dir / "scene_graph.json"
    graph_path.write_text(
        json.dumps({
            "source": "pipeline lifter native filtered manifest",
            "founding_manifest": manifest_path.name,
            "resolved": {"nodes": nodes},
        }, indent=2) + "\n",
        encoding="utf-8",
    )
    return graph_path


def _link_or_copy(source: Path, target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        if hashlib.sha256(target.read_bytes()).digest() != hashlib.sha256(source.read_bytes()).digest():
            raise ValueError(f"refusing to overwrite different file: {target}")
        return
    try:
        os.link(source, target)
    except OSError:
        shutil.copy2(source, target)


def _run(argv: list[str]) -> None:
    print("[pipeline-lifter]", " ".join(argv), flush=True)
    subprocess.run(argv, cwd=ENTANGLED, check=True)


def prepare(args: argparse.Namespace) -> dict:
    approved = json.loads(args.approved_views.read_text(encoding="utf-8"))
    if not approved.get("approved"):
        raise ValueError("base-view manifest is not approved")
    spec = approved["scenes"][args.scene_id]
    transforms_path = args.prepared_scene / "transforms.json"
    transforms_bytes = transforms_path.read_bytes()
    actual_hash = hashlib.sha256(transforms_bytes).hexdigest()
    if actual_hash != spec["transforms_sha256"]:
        raise ValueError(f"prepared transforms hash changed: {actual_hash}")
    transforms = json.loads(transforms_bytes)
    indices = [int(i) for i in spec["zoo_input_indices"]]
    frames = transforms["frames"]
    selected = []
    for rank, index in enumerate(indices):
        frame = frames[index]
        matrix = np.asarray(frame["transform_matrix"], dtype=float)
        selected.append({
            "rank": rank,
            "zoo_input_index": index,
            "source_image": Path(frame["file_path"]).name,
            "position_raw": matrix[:3, 3].tolist(),
            "transform_matrix": matrix.tolist(),
        })
    if [row["source_image"] for row in selected] != spec["source_images"]:
        raise ValueError("approved source-image receipt no longer matches transforms")

    expected = paths.scene_dir(args.output_scene.name).resolve()
    if args.output_scene.resolve() != expected:
        raise ValueError(f"output must be the configured pipeline scene directory {expected}")
    args.output_scene.mkdir(parents=True, exist_ok=True)
    _link_or_copy(args.ply, args.output_scene / "gen_raw.ply")

    all_positions = np.asarray([
        np.asarray(frame["transform_matrix"], dtype=float)[:3, 3]
        for frame in frames
    ])
    point_data = np.load(args.prepared_scene / "initial_points.npz")
    points = point_data["points"] if "points" in point_data else point_data[point_data.files[0]]
    shell = estimate_shell(points[:, :3], all_positions)
    (args.output_scene / "room_shell.json").write_text(
        json.dumps(shell, indent=2) + "\n", encoding="utf-8"
    )
    frame_bootstrap = {
        "format": "hypersim-approved-camera-frame-v1",
        "floor_y": shell["floor_y_raw"],
        "ceiling_y": shell["ceiling_y_raw"],
        "up": [0.0, -1.0, 0.0],
        "pano_to_raw_signs": [1.0, -1.0, 1.0],
        "source": "prepared Hypersim metric frame",
    }
    (args.output_scene / "frame_bootstrap.json").write_text(
        json.dumps(frame_bootstrap, indent=2) + "\n", encoding="utf-8"
    )
    receipt = {
        "format": "pipeline-lifter-approved-multibase-v1",
        "scene_id": args.scene_id,
        "pipeline_scene": args.output_scene.name,
        "approved_views": str(args.approved_views.resolve()),
        "prepared_transforms": str(transforms_path.resolve()),
        "prepared_transforms_sha256": actual_hash,
        "base_views": selected,
        "views_per_base": 20,
        "global_views_total": 20 * len(selected),
        "proposal_source": "pipeline lifter GroundingDINO + SAM mask lift and fusion",
        "forbidden_bootstrap": "Splat Analyzer",
    }
    (args.output_scene / "pipeline_lifter_input_manifest.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    if args.through == "setup":
        return receipt

    for row in selected:
        eye = ",".join(f"{v:.12g}" for v in row["position_raw"])
        rig = f"rig_base{row['rank']}"
        _run([sys.executable, "pano_stitch.py", "--scene", args.output_scene.name,
              "--rig", rig, f"--eye-raw={eye}"])
    if args.through == "render":
        return receipt

    combined = args.output_scene / "rig_sp0" / "crops"
    combined.mkdir(parents=True, exist_ok=True)
    for row in selected:
        eye = ",".join(f"{v:.12g}" for v in row["position_raw"])
        rig = args.output_scene / f"rig_base{row['rank']}"
        meta = json.loads((rig / "pano_selfrender_meta.json").read_text(encoding="utf-8"))
        signs = ",".join(str(v) for v in meta["pano_to_raw_signs"])
        _run([sys.executable, "crop_pano.py", "--scene", args.output_scene.name,
              "--pano", str(rig / "pano_selfrender.png"),
              "--out-dir", str(combined),
              "--name-prefix", f"base{row['rank']}_", f"--eye-raw={eye}",
              "--pano-to-raw-signs", signs])
    rig_meta = {
        "format": "pipeline-lifter-multibase-rig-v1",
        "eye_raw": selected[0]["position_raw"],
        "eye_source": "first approved Zoo3D/Hypersim base; exact per-view cameras are in crop sidecars",
        "base_views": selected,
        "views_per_base": 20,
    }
    rig0 = args.output_scene / "rig_sp0"
    (rig0 / "pano_selfrender_meta.json").write_text(
        json.dumps(rig_meta, indent=2) + "\n", encoding="utf-8"
    )
    vocab_path = _write_vocab(args.output_scene, args.scene_id)
    receipt["vocabulary"] = {
        "path": str(vocab_path.resolve()), "sha256": _sha256(vocab_path),
        "canonical_labels": CANONICAL_LABELS,
    }
    (args.output_scene / "pipeline_lifter_input_manifest.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    if args.through == "crops":
        return receipt

    seg_dir = rig0 / "seg_batched20"
    _run([
        sys.executable, "seg_batched.py", "--scene", args.output_scene.name,
        "--views-dir", str(combined), "--glob", "*.webp",
        "--out-dir", str(seg_dir), "--box-thr", "0.20", "--topk", "40",
        "--pace", str(args.seg_pace), "--resume",
    ])
    if args.through == "detect":
        return receipt

    _run([
        sys.executable, "pano_lift.py", "--scene", args.output_scene.name,
        "--seg-dir", "seg_batched20", "--suffix", "c",
        "--min-score", "0.20", "--gate-peak", "0.20",
    ])
    _run([
        sys.executable, "manifest_filter.py", "--scene", args.output_scene.name,
        "--manifest", "scene_manifest_pano2c.json", "--thr", "0.30",
    ])
    founding = args.output_scene / "scene_manifest_pano2c_f30.json"
    graph_path = _write_native_graph(args.output_scene, founding)
    receipt["native_discovery"] = {
        "detections": str((seg_dir / "detections.json").resolve()),
        "lift_pool": str((rig0 / "lift_poolc.json").resolve()),
        "founding_manifest": str(founding.resolve()),
        "scene_graph": str(graph_path.resolve()),
        "score_threshold": 0.30,
    }
    (args.output_scene / "pipeline_lifter_input_manifest.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    if args.through == "lift":
        return receipt

    run_id = args.run_id or f"plv1-{args.scene_id}-15k"
    _run([
        sys.executable, "slicevote.py", "--scene", args.output_scene.name,
        "--gate", "3", "--res", "768", "--run-id", run_id,
        "--graph", graph_path.name, "--manifest", founding.name,
        "--pool", "rig_sp0/lift_poolc.json",
        "--seg-dir", "rig_sp0/seg_batched20",
        "--crops-dir", "rig_sp0/crops",
    ])
    benchmark_dir = args.output_scene / "benchmark"
    _run([
        sys.executable, str(HERE / "adapt_pipeline_lifter.py"),
        "--input", str(args.output_scene / "scene_manifest_slicevote_preview.json"),
        "--founding-manifest", str(founding), "--scene-id", args.scene_id,
        "--output", str(benchmark_dir / "predictions.jsonl"),
        "--receipt", str(benchmark_dir / "prediction_freeze.json"),
    ])
    return receipt


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scene-id", required=True)
    parser.add_argument("--prepared-scene", required=True, type=Path)
    parser.add_argument("--ply", required=True, type=Path)
    parser.add_argument("--output-scene", required=True, type=Path)
    parser.add_argument("--approved-views", type=Path,
                        default=HERE / "base_views.v1.json")
    parser.add_argument("--through",
                        choices=("setup", "render", "crops", "detect", "lift", "vote"),
                        default="crops")
    parser.add_argument("--seg-pace", type=float, default=2.0)
    parser.add_argument("--run-id", default="")
    args = parser.parse_args()
    receipt = prepare(args)
    print(f"prepared {len(receipt['base_views'])} approved bases / "
          f"{receipt['global_views_total']} views in {args.output_scene}")


if __name__ == "__main__":
    main()
