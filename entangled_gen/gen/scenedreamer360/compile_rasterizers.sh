#!/bin/bash
# compile_rasterizers.sh — build the two CUDA extensions for SceneDreamer360's
# 3DGS stage into the panfusion env. Handles the Ada(sm_89) + gcc-13 issues:
#   - torch 2.0.1 is CUDA 11.7; 11.7 nvcc maxes at sm_87, so target 8.6+PTX
#     (sm_86 cubin JIT-upgrades to sm_89 on the 4080 at runtime).
#   - 11.7 needs host gcc <= 11; WSL gcc is 13.3, so use a conda gcc-11.
# NOTE: no `set -u` — conda's gxx activation hooks reference unbound vars.
set -o pipefail
LOG=/root/sd360_compile.log
exec > >(tee "$LOG") 2>&1
source /root/miniconda3/etc/profile.d/conda.sh
set +u
conda activate panfusion

echo "=== [1] host gcc-11 + nvcc 11.7 into env $(date) ==="
conda install -y -c conda-forge gxx_linux-64=11 gcc_linux-64=11
conda install -y -c "nvidia/label/cuda-11.7.1" cuda-nvcc cuda-cudart-dev cuda-libraries-dev

export CUDA_HOME="$CONDA_PREFIX"
export CC="$CONDA_PREFIX/bin/x86_64-conda-linux-gnu-gcc"
export CXX="$CONDA_PREFIX/bin/x86_64-conda-linux-gnu-g++"
export TORCH_CUDA_ARCH_LIST="8.6+PTX"
echo "nvcc: $(which nvcc)"; nvcc --version | tail -2
echo "CC=$CC"

REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/SceneDreamer360
SUB="$REPO/PanoSpaceDreamer/submodules"

echo "=== [2] depth-diff-gaussian-rasterization-min ==="
cd "$SUB/depth-diff-gaussian-rasterization-min" && pip install . ; echo "RASTERIZER_EXIT=$?"

echo "=== [3] simple-knn ==="
cd "$SUB/simple-knn" && pip install . ; echo "SIMPLEKNN_EXIT=$?"

echo "=== [4] verify imports ==="
python - <<'PY'
import torch
print("torch", torch.__version__, "cuda", torch.version.cuda, "avail", torch.cuda.is_available())
for m in ("diff_gaussian_rasterization", "simple_knn._C"):
    try:
        __import__(m); print("import OK:", m)
    except Exception as e:
        print("import FAIL:", m, "->", repr(e)[:200])
PY
echo "=== COMPILE_STAGE_DONE ==="
