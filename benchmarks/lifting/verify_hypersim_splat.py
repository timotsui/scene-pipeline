"""Render held-out Hypersim cameras and measure a trained Gaussian splat.

This is a reconstruction gate, not a lifting score.  It uses the same PLY
loader and gsplat renderer as Splat Analyzer, then compares each held-out
render with the prepared benchmark image using PSNR.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

import numpy as np
import torch
from PIL import Image, ImageDraw


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(2**20), b""):
            digest.update(block)
    return digest.hexdigest()


def _psnr(reference: np.ndarray, rendered: np.ndarray) -> float:
    delta = reference.astype(np.float32) / 255.0 - rendered.astype(np.float32) / 255.0
    mse = float(np.mean(delta * delta))
    return float("inf") if mse == 0.0 else float(-10.0 * np.log10(mse))


def _comparison(reference: np.ndarray, rendered: np.ndarray, caption: str) -> Image.Image:
    height, width = reference.shape[:2]
    canvas = Image.new("RGB", (width * 2, height + 28), "white")
    canvas.paste(Image.fromarray(reference), (0, 28))
    canvas.paste(Image.fromarray(rendered), (width, 28))
    draw = ImageDraw.Draw(canvas)
    draw.text((8, 7), f"reference | {caption}", fill="black")
    return canvas


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--splat-analyzer-repo", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--ply", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--test-every", type=int, default=10)
    args = parser.parse_args()

    sys.path.insert(0, str(args.splat_analyzer_repo))
    from render_cameras import _load_ply_arrays
    from renderers.gsplat_backend import GsplatRenderer

    transforms = json.loads((args.data / "transforms.json").read_text())
    width, height = int(transforms["w"]), int(transforms["h"])
    K = torch.tensor(
        [
            [transforms["fl_x"], 0.0, transforms["cx"]],
            [0.0, transforms["fl_y"], transforms["cy"]],
            [0.0, 0.0, 1.0],
        ],
        dtype=torch.float32,
        device="cuda",
    )

    # Prepared transforms use the common OpenGL camera convention.  gsplat's
    # view matrix uses OpenCV axes, matching the training adapter.
    flip = np.diag([1.0, -1.0, -1.0, 1.0])
    selected = list(range(0, len(transforms["frames"]), args.test_every))
    c2ws = []
    references = []
    names = []
    for index in selected:
        frame = transforms["frames"][index]
        c2w = np.asarray(frame["transform_matrix"], dtype=np.float32) @ flip
        c2ws.append(c2w)
        references.append(np.asarray(Image.open(args.data / frame["file_path"]).convert("RGB")))
        names.append(Path(frame["file_path"]).stem)

    w2cs = torch.from_numpy(np.linalg.inv(np.stack(c2ws)).astype(np.float32)).cuda()
    renderer = GsplatRenderer()
    gaussians = renderer.prepare(_load_ply_arrays(str(args.ply)))
    rendered = renderer.render_rgb(gaussians, w2cs, K, width, height)

    args.output.mkdir(parents=True, exist_ok=True)
    frames = []
    for name, reference, prediction in zip(names, references, rendered):
        score = _psnr(reference, prediction)
        Image.fromarray(prediction).save(args.output / f"{name}.render.png")
        _comparison(reference, prediction, f"render; PSNR {score:.2f} dB").save(
            args.output / f"{name}.comparison.png"
        )
        frames.append({"frame": name, "psnr_db": score})

    scores = np.asarray([frame["psnr_db"] for frame in frames], dtype=np.float64)
    receipt = {
        "format": "hypersim-splat-reconstruction-check-v0",
        "status": "development-smoke-not-paper-frozen",
        "data": str(args.data.resolve()),
        "ply": str(args.ply.resolve()),
        "ply_sha256": _sha256(args.ply),
        "held_out_rule": f"prepared frame index modulo {args.test_every} equals zero",
        "held_out_frames": frames,
        "mean_psnr_db": float(scores.mean()),
        "median_psnr_db": float(np.median(scores)),
        "min_psnr_db": float(scores.min()),
        "max_psnr_db": float(scores.max()),
    }
    output_path = args.output / "reconstruction_metrics.json"
    output_path.write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    print(
        f"verified {len(frames)} held-out cameras: mean PSNR "
        f"{receipt['mean_psnr_db']:.2f} dB ({receipt['min_psnr_db']:.2f}--"
        f"{receipt['max_psnr_db']:.2f})"
    )


if __name__ == "__main__":
    main()
