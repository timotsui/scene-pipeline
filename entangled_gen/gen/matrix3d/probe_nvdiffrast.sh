#!/bin/bash
# probe_nvdiffrast.sh — reproduce the nvdiffrast JIT plugin build with full stderr.
source /root/miniconda3/etc/profile.d/conda.sh
conda activate matrix3d
export CUDA_HOME="$CONDA_PREFIX"
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$LD_LIBRARY_PATH"
# conda cuda-toolkit keeps headers/libs under targets/ — torch JIT looks in
# $CUDA_HOME/include, so expose them via the compiler search-path env vars
export CPATH="$CONDA_PREFIX/targets/x86_64-linux/include:$CPATH"
export LIBRARY_PATH="$CONDA_PREFIX/targets/x86_64-linux/lib:$CONDA_PREFIX/lib:$LIBRARY_PATH"
cd /root
python - <<'PY'
import torch
import nvdiffrast.torch as dr
ctx = dr.RasterizeCudaContext()
print("NVDIFFRAST_JIT_OK")
PY
