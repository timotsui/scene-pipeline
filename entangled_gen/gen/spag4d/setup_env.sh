#!/bin/bash
# setup_env.sh — SPAG4d install (WSL Ubuntu-24.04, dedicated conda env
# 'spag4d'). Idempotent. Torch installed separately per upstream (cu121 pip
# wheels run fine on the WSL cu12 driver).
set -o pipefail
source /root/miniconda3/etc/profile.d/conda.sh
REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/SPAG4d

conda env list | grep -q '^spag4d ' || conda create -y -n spag4d python=3.11
conda activate spag4d

pip show torch >/dev/null 2>&1 || \
  pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

cd "$REPO" || exit 1
pip install -r requirements.txt
pip install -e . --no-deps 2>/dev/null || true   # package may be src-layout only

# depth-arch clones (upstream install.bat does these on Windows)
[ -d spag4d/dap_arch/DAP ] || git submodule update --init --recursive
[ -d spag4d/da360_arch/DA360 ] || \
  git clone --depth 1 https://github.com/Insta360-Research-Team/DA360 spag4d/da360_arch/DA360

# weights (~2.8 GB into ~/.cache/spag4d)
python -m spag4d download-models || exit 1

python -m spag4d --help >/dev/null && echo SPAG4D_SETUP_OK
