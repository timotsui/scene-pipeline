#!/bin/bash
# fix_install2.sh — resume after fix_install.sh got torch/DiffSynth right but
# conda pulled cuda-toolkit 13.3 (label channel alone doesn't pin!) and
# pytorch3d refused the 13.3-vs-12.6 mismatch. Force 12.6.3 with
# --override-channels, then finish the CUDA builds.
set -o pipefail
source /root/miniconda3/etc/profile.d/conda.sh
conda activate matrix3d
REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/Matrix-3D
export PIP_CONSTRAINT=/root/m3d_constraints.txt

# force-downgrade the toolkit to exactly 12.6.3
conda install -y --override-channels -c nvidia/label/cuda-12.6.3 -c conda-forge cuda-toolkit=12.6.3 || exit 1
export CUDA_HOME="$CONDA_PREFIX"
nvcc --version | grep release || exit 1

export TORCH_CUDA_ARCH_LIST="8.9"
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
echo M3D_FIX2_OK
