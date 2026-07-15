#!/bin/bash
# setup_env.sh — Matrix-3D env install (WSL, conda env 'matrix3d'). Idempotent.
# Their install.sh builds CUDA extensions (gaussian rasterizers etc.) — if it
# fails on missing nvcc, install cuda-toolkit into the env and rerun.
set -o pipefail
source /root/miniconda3/etc/profile.d/conda.sh
REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/Matrix-3D

conda env list | grep -q '^matrix3d ' || conda create -y -n matrix3d python=3.10
conda activate matrix3d

cd "$REPO" || exit 1
# shallow clone was non-recursive; their install.sh needs the submodules
git submodule update --init --recursive --depth 1

pip show torch 2>/dev/null | grep -q '2.7.0' || \
  pip install torch==2.7.0 torchvision==0.22.0 --index-url https://download.pytorch.org/whl/cu124

chmod +x install.sh
./install.sh

python -c "import torch; print('torch', torch.__version__, 'cuda', torch.cuda.is_available())" \
  && echo M3D_SETUP_OK
