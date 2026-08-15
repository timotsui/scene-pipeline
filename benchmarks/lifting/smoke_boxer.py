"""Load Boxer's released CUDA checkpoints without downloading sample data."""

from __future__ import annotations

import argparse
import gc
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, required=True)
    args = parser.parse_args()
    repo = args.repo.resolve()
    sys.path.insert(0, str(repo))

    import torch
    from boxernet.boxernet import BoxerNet

    if not torch.cuda.is_available():
        raise SystemExit("CUDA is not available")
    checkpoint = repo / "ckpts" / "boxernet_hw960in2x6d768-c88128f8.ckpt"
    model = BoxerNet.load_from_checkpoint(str(checkpoint), device="cuda")
    print(
        {
            "component": "BoxerNet",
            "parameters": sum(parameter.numel() for parameter in model.parameters()),
            "input_hw": model.hw,
            "gpu": torch.cuda.get_device_name(0),
            "allocated_gb": round(torch.cuda.memory_allocated() / 2**30, 3),
        }
    )
    del model
    gc.collect()
    torch.cuda.empty_cache()

    from owl.owl_wrapper import OwlWrapper

    detector = OwlWrapper(
        "cuda",
        text_prompts=["chair", "table"],
        precision="bfloat16",
        warmup=False,
    )
    print(
        {
            "component": "OWLv2",
            "prompts": detector.text_prompts,
            "allocated_gb": round(torch.cuda.memory_allocated() / 2**30, 3),
        }
    )
    del detector
    gc.collect()
    torch.cuda.empty_cache()
    print("Boxer checkpoint smoke test passed")


if __name__ == "__main__":
    main()
