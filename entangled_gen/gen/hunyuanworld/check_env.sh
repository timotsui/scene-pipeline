#!/bin/bash
# check_env.sh — smoke-test the HunyuanWorld conda env (imports + CUDA).
source /root/miniconda3/etc/profile.d/conda.sh
conda activate HunyuanWorld
cd /mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/HunyuanWorld-1.0 || exit 1
python - <<'PY'
import torch, numpy, diffusers, transformers
print("torch", torch.__version__, "| cuda", torch.cuda.is_available(),
      "| numpy", numpy.__version__, "| diffusers", diffusers.__version__)
import hy3dworld
from hy3dworld import Text2PanoramaPipelines
print("hy3dworld + Text2PanoramaPipelines import OK")
PY
