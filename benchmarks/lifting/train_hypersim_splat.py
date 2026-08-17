"""Train a metric Hypersim splat with gsplat's official v1.5.3 trainer.

The official example imports viewer, metric, and fused-CUDA packages even when
they are unused in headless training.  This launcher supplies small headless
adapters for those optional pieces, while retaining the official optimizer,
rasterizer, densification strategy, checkpointing, and PLY export.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import subprocess
import sys
import time
import types
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F


def _install_headless_modules(gsplat_repo: Path, data_dir: Path, max_points: int):
    examples = gsplat_repo / "examples"
    sys.path.insert(0, str(examples))

    class PreparedParser:
        def __init__(self, data_dir: str, factor=1, normalize=False, test_every=10):
            if factor != 1 or normalize:
                raise ValueError("prepared benchmark must remain metric at factor=1")
            root = Path(data_dir)
            transforms = json.loads((root / "transforms.json").read_text())
            self.image_names = [Path(frame["file_path"]).name for frame in transforms["frames"]]
            self.image_paths = [str(root / frame["file_path"]) for frame in transforms["frames"]]
            flip = np.diag([1.0, -1.0, -1.0])
            cameras = []
            for frame in transforms["frames"]:
                c2w = np.asarray(frame["transform_matrix"], dtype=np.float64)
                c2w[:3, :3] = c2w[:3, :3] @ flip
                cameras.append(c2w)
            self.camtoworlds = np.stack(cameras)
            self.camera_ids = [1] * len(cameras)
            K = np.array(
                [
                    [transforms["fl_x"], 0.0, transforms["cx"]],
                    [0.0, transforms["fl_y"], transforms["cy"]],
                    [0.0, 0.0, 1.0],
                ],
                dtype=np.float64,
            )
            self.Ks_dict = {1: K}
            self.params_dict = {1: np.empty(0, dtype=np.float32)}
            self.imsize_dict = {1: (int(transforms["w"]), int(transforms["h"]))}
            self.mask_dict = {1: None}
            initial = np.load(root / "initial_points.npz", allow_pickle=False)
            points = initial["points"].astype(np.float32)
            colors = initial["colors"].astype(np.uint8)
            if len(points) > max_points:
                rng = np.random.default_rng(0)
                selected = np.sort(rng.choice(len(points), max_points, replace=False))
                points, colors = points[selected], colors[selected]
            self.points = points
            self.points_rgb = colors
            self.points_err = np.zeros(len(points), dtype=np.float32)
            self.point_indices = {}
            self.transform = np.eye(4)
            self.bounds = np.array([0.01, 1.0])
            self.extconf = {"spiral_radius_scale": 1.0, "no_factor_suffix": False}
            self.test_every = int(test_every)
            center = self.camtoworlds[:, :3, 3].mean(axis=0)
            self.scene_scale = float(
                np.linalg.norm(self.camtoworlds[:, :3, 3] - center, axis=1).max()
            )
            print(
                f"[prepared-parser] {len(cameras)} cameras, {len(points)} metric points, "
                f"scene scale {self.scene_scale:.3f} m"
            )

    class PreparedDataset:
        def __init__(self, parser, split="train", patch_size=None, load_depths=False):
            if load_depths:
                raise ValueError("depth-loss mode is not used in the smoke benchmark")
            self.parser = parser
            self.patch_size = patch_size
            indices = np.arange(len(parser.image_names))
            if split == "train":
                self.indices = indices[indices % parser.test_every != 0]
            else:
                self.indices = indices[indices % parser.test_every == 0]

        def __len__(self):
            return len(self.indices)

        def __getitem__(self, item):
            index = int(self.indices[item])
            image = np.array(__import__("PIL.Image", fromlist=["Image"]).open(
                self.parser.image_paths[index]
            ).convert("RGB"))
            K = self.parser.Ks_dict[1].copy()
            if self.patch_size is not None:
                height, width = image.shape[:2]
                x = np.random.randint(0, max(width - self.patch_size, 1))
                y = np.random.randint(0, max(height - self.patch_size, 1))
                image = image[y : y + self.patch_size, x : x + self.patch_size]
                K[0, 2] -= x
                K[1, 2] -= y
            return {
                "K": torch.from_numpy(K).float(),
                "camtoworld": torch.from_numpy(self.parser.camtoworlds[index]).float(),
                "image": torch.from_numpy(image).float(),
                "image_id": item,
            }

    datasets_package = types.ModuleType("datasets")
    datasets_package.__path__ = [str(examples / "datasets")]
    sys.modules["datasets"] = datasets_package
    colmap_module = types.ModuleType("datasets.colmap")
    colmap_module.Parser = PreparedParser
    colmap_module.Dataset = PreparedDataset
    sys.modules["datasets.colmap"] = colmap_module

    fused_module = types.ModuleType("fused_ssim")

    def fused_ssim(left, right, padding="valid"):
        pad = 0 if padding == "valid" else 5
        mu_left = F.avg_pool2d(left, 11, stride=1, padding=pad)
        mu_right = F.avg_pool2d(right, 11, stride=1, padding=pad)
        var_left = F.avg_pool2d(left * left, 11, stride=1, padding=pad) - mu_left**2
        var_right = F.avg_pool2d(right * right, 11, stride=1, padding=pad) - mu_right**2
        covariance = F.avg_pool2d(left * right, 11, stride=1, padding=pad) - mu_left * mu_right
        c1, c2 = 0.01**2, 0.03**2
        score = ((2 * mu_left * mu_right + c1) * (2 * covariance + c2)) / (
            (mu_left**2 + mu_right**2 + c1) * (var_left + var_right + c2)
        )
        return score.mean()

    fused_module.fused_ssim = fused_ssim
    sys.modules["fused_ssim"] = fused_module

    utils_module = types.ModuleType("utils")

    def knn(points, K=4):
        from scipy.spatial import cKDTree

        distances, _ = cKDTree(points.detach().cpu().numpy()).query(
            points.detach().cpu().numpy(), k=K, workers=-1
        )
        return torch.from_numpy(distances).to(points)

    def rgb_to_sh(rgb):
        return (rgb - 0.5) / 0.28209479177387814

    def set_random_seed(seed):
        random.seed(seed)
        np.random.seed(seed)
        torch.manual_seed(seed)

    class UnusedModule(torch.nn.Module):
        def __init__(self, *args, **kwargs):
            super().__init__()

    utils_module.knn = knn
    utils_module.rgb_to_sh = rgb_to_sh
    utils_module.set_random_seed = set_random_seed
    utils_module.CameraOptModule = UnusedModule
    utils_module.AppearanceOptModule = UnusedModule
    sys.modules["utils"] = utils_module

    class DummyMetric:
        def __init__(self, *args, **kwargs):
            pass

        def to(self, *args, **kwargs):
            return self

        def __call__(self, *args, **kwargs):
            return torch.tensor(float("nan"))

    torchmetrics = types.ModuleType("torchmetrics")
    torchmetrics.__path__ = []
    metrics_image = types.ModuleType("torchmetrics.image")
    metrics_image.PeakSignalNoiseRatio = DummyMetric
    metrics_image.StructuralSimilarityIndexMeasure = DummyMetric
    metrics_lpips = types.ModuleType("torchmetrics.image.lpip")
    metrics_lpips.LearnedPerceptualImagePatchSimilarity = DummyMetric
    sys.modules.update(
        {
            "torchmetrics": torchmetrics,
            "torchmetrics.image": metrics_image,
            "torchmetrics.image.lpip": metrics_lpips,
        }
    )

    class DummyWriter:
        def __init__(self, *args, **kwargs):
            pass

        def add_scalar(self, *args, **kwargs):
            pass

        def add_image(self, *args, **kwargs):
            pass

        def flush(self):
            pass

    tensorboard_module = types.ModuleType("torch.utils.tensorboard")
    tensorboard_module.SummaryWriter = DummyWriter
    sys.modules["torch.utils.tensorboard"] = tensorboard_module

    sys.modules["tyro"] = types.ModuleType("tyro")
    sys.modules["viser"] = types.ModuleType("viser")
    viewer_module = types.ModuleType("gsplat_viewer")
    viewer_module.GsplatViewer = object
    viewer_module.GsplatRenderTabState = object
    sys.modules["gsplat_viewer"] = viewer_module
    nerfview_module = types.ModuleType("nerfview")
    nerfview_module.CameraState = object
    nerfview_module.RenderTabState = object
    nerfview_module.apply_float_colormap = lambda image, *args, **kwargs: image
    sys.modules["nerfview"] = nerfview_module


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(2**20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gsplat-repo", required=True, type=Path)
    parser.add_argument("--data", required=True, type=Path)
    parser.add_argument("--result", required=True, type=Path)
    parser.add_argument("--steps", type=int, default=5000)
    parser.add_argument("--max-initial-points", type=int, default=100_000)
    parser.add_argument("--test-every", type=int, default=10)
    args = parser.parse_args()

    _install_headless_modules(args.gsplat_repo, args.data, args.max_initial_points)
    import simple_trainer
    from gsplat.strategy import DefaultStrategy

    args.result.mkdir(parents=True, exist_ok=True)
    cfg = simple_trainer.Config(
        disable_viewer=True,
        data_dir=str(args.data),
        data_factor=1,
        result_dir=str(args.result),
        test_every=args.test_every,
        normalize_world_space=False,
        max_steps=args.steps,
        eval_steps=[],
        save_steps=[args.steps],
        save_ply=True,
        ply_steps=[args.steps],
        tb_every=0,
        packed=False,
        strategy=DefaultStrategy(verbose=True),
    )
    started = time.time()
    runner = simple_trainer.Runner(0, 0, 1, cfg)
    runner.train()
    elapsed = time.time() - started
    ply = args.result / "ply" / f"point_cloud_{args.steps - 1}.ply"
    if not ply.exists():
        raise FileNotFoundError(f"official trainer did not export {ply}")
    try:
        commit = subprocess.check_output(
            ["git", "-C", str(args.gsplat_repo), "rev-parse", "HEAD"], text=True
        ).strip()
    except Exception:
        commit = "unknown"
    receipt = {
        "format": "hypersim-gsplat-training-v0",
        "status": "development-smoke-not-paper-frozen",
        "data": str(args.data.resolve()),
        "benchmark_manifest_sha256": _sha256(args.data / "benchmark_manifest.json"),
        "gsplat_repo": str(args.gsplat_repo.resolve()),
        "gsplat_commit": commit,
        "torch": torch.__version__,
        "cuda": torch.version.cuda,
        "steps": args.steps,
        "max_initial_points": args.max_initial_points,
        "test_every": args.test_every,
        "normalize_world_space": False,
        "physical_up": [0.0, -1.0, 0.0],
        "elapsed_seconds": elapsed,
        "output_ply": str(ply.resolve()),
        "output_ply_sha256": _sha256(ply),
        "output_ply_bytes": ply.stat().st_size,
    }
    (args.result / "training_receipt.json").write_text(
        json.dumps(receipt, indent=2) + "\n", encoding="utf-8"
    )
    print(
        f"trained {ply.name} in {elapsed / 60:.1f} min; "
        f"{ply.stat().st_size / 2**20:.1f} MiB"
    )


if __name__ == "__main__":
    main()
