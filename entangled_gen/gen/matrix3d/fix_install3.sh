#!/bin/bash
# fix_install3.sh — final resume: after fix2's --override-channels toolkit
# install removed python from the env (conda solver casualty; python 3.10 +
# pip reinstalled manually, site-packages survived). Verify the pieces, then
# build the remaining CUDA extensions.
set -o pipefail
exec > >(tee /root/m3d_fix3.log) 2>&1   # self-log: hidden launches have no pipe
source /root/miniconda3/etc/profile.d/conda.sh
conda activate matrix3d
REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/Matrix-3D
export PIP_CONSTRAINT=/root/m3d_constraints.txt
export CUDA_HOME="$CONDA_PREFIX"
export TORCH_CUDA_ARCH_LIST="8.9"

nvcc --version | grep 'release 12.6' || { echo NVCC_MISSING; exit 1; }
python -c "import torch, diffsynth; print('torch', torch.__version__, 'cuda_build', torch.version.cuda)" || exit 1

pip install "git+https://github.com/facebookresearch/pytorch3d.git@v0.7.7" --no-build-isolation || exit 1
cd "$REPO/submodules/nvdiffrast" && pip install . --no-build-isolation || exit 1
cd "$REPO/submodules/simple-knn" && pip install . --no-build-isolation || exit 1
pip install "git+https://github.com/rmurai0610/diff-gaussian-rasterization-w-pose.git" --no-build-isolation || exit 1
[ -d "$REPO/submodules/ODGS" ] || git clone --depth 1 https://github.com/esw0116/ODGS.git "$REPO/submodules/ODGS"
cd "$REPO/submodules/ODGS" && pip install submodules/odgs-gaussian-rasterization --no-build-isolation || exit 1

python - <<'PY'
import torch; print("torch", torch.__version__, "cuda", torch.cuda.is_available())
import diffsynth; print("diffsynth OK")
import pytorch3d; print("pytorch3d OK")
import nvdiffrast; print("nvdiffrast OK")
PY
echo M3D_FIX3_OK
