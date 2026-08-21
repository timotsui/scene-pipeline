"""Run the corrected five-scene pipeline-lifter benchmark serially.

This runner validates the frozen reconstruction gates, then invokes
``prepare_pipeline_lifter_scene.py`` for each scene. It never opens ground
truth; evaluation is a separate post-freeze command.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path


SCENES = ["ai_051_002", "ai_002_006", "ai_006_008", "ai_037_007", "ai_003_009"]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepared-root", required=True, type=Path)
    parser.add_argument("--training-root", required=True, type=Path)
    parser.add_argument("--verification-root", required=True, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--scenes", nargs="+", default=SCENES)
    parser.add_argument("--through", default="vote",
                        choices=("setup", "render", "crops", "detect", "lift", "vote"))
    parser.add_argument("--seg-pace", type=float, default=2.0)
    args = parser.parse_args()

    here = Path(__file__).resolve().parent
    run_rows = []
    for scene_id in args.scenes:
        metrics_path = (args.verification_root / f"{scene_id}_gsplat15000"
                        / "reconstruction_metrics.json")
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        if (len(metrics.get("held_out_frames", [])) != 5
                or metrics["mean_psnr_db"] < 18.0
                or metrics["min_psnr_db"] < 15.0):
            raise ValueError(f"{scene_id} failed frozen reconstruction gate: {metrics}")
        ply = (args.training_root / f"{scene_id}_gsplat15000" / "ply"
               / "point_cloud_14999.ply")
        if not ply.is_file() or ply.stat().st_size <= 0:
            raise FileNotFoundError(ply)
        output_scene = args.output_root / f"hypersim_{scene_id}_pipeline_lifter_v1_gsplat15000"
        command = [
            sys.executable, str(here / "prepare_pipeline_lifter_scene.py"),
            "--scene-id", scene_id,
            "--prepared-scene", str(args.prepared_root / scene_id),
            "--ply", str(ply), "--output-scene", str(output_scene),
            "--through", args.through, "--seg-pace", str(args.seg_pace),
            "--run-id", f"plv1-{scene_id}-15k",
        ]
        print("[pipeline-lifter-benchmark]", " ".join(command), flush=True)
        subprocess.run(command, check=True)
        run_rows.append({
            "scene_id": scene_id,
            "output_scene": str(output_scene.resolve()),
            "reconstruction_metrics": str(metrics_path.resolve()),
            "prediction_freeze": (
                str((output_scene / "benchmark" / "prediction_freeze.json").resolve())
                if args.through == "vote" else None
            ),
        })

    receipt = {
        "format": "pipeline-lifter-five-scene-run-v1",
        "ground_truth_read": False,
        "through": args.through,
        "scenes": run_rows,
    }
    receipt_path = args.output_root / "pipeline_lifter_five_scene_run.v1.json"
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(f"completed {len(run_rows)} scenes; receipt {receipt_path}")


if __name__ == "__main__":
    main()
