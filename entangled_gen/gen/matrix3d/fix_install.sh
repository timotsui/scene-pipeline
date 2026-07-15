#!/bin/bash
# fix_install.sh — repair pass after upstream install.sh (see README).
# Upstream problems: (a) CUDA ext builds need nvcc, absent in a pip-torch
# env; (b) DiffSynth/pytorch3d builds need torch visible at build time
# (--no-build-isolation); (c) unpinned installs stomped torch 2.7.0 -> 2.12.
# Fix: conda cuda-toolkit 12.4, PIP_CONSTRAINT pin, targeted rebuilds.
set -o pipefail
source /root/miniconda3/etc/profile.d/conda.sh
conda activate matrix3d
REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/Matrix-3D
GEN=/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/entangled_gen/gen/matrix3d

# 0) torch pin (no +local tags — they confuse the resolver vs CLI specs)
cat > /root/m3d_constraints.txt <<EOF
torch==2.7.0
torchvision==0.22.0
EOF
# torch 2.7.0 has no cu124 wheels; its default PyPI wheel IS the cu126 build
# (upstream's bare `pip install torch==2.7.0` = exactly this). Plain PyPI —
# the pytorch.org cu126 index CDN (download-r2) throws SSL handshake failures
# from this WSL box.

# 1) restore the stomped torch — constraint-free, forced, no-deps: some
# stomp-installed package (xfuser et al) declares torch>=2.12 so clean
# resolution is impossible; upstream's own env runs this combo regardless.
env -u PIP_CONSTRAINT pip install --force-reinstall --no-deps \
  torch==2.7.0 torchvision==0.22.0 || exit 1
# pin applies to everything AFTER the restore
export PIP_CONSTRAINT=/root/m3d_constraints.txt

# 2) nvcc for the CUDA extension builds (12.6 to match the cu126 torch)
conda install -y -c nvidia/label/cuda-12.6.3 cuda-toolkit || exit 1
export CUDA_HOME="$CONDA_PREFIX"
nvcc --version | tail -1

# 3) DiffSynth-Studio (WanVideoPipelineNew lives here — required for video gen)
cd "$REPO/code/DiffSynth-Studio" && pip install -e . --no-build-isolation || exit 1

# 4) pytorch3d v0.7.7 (long CUDA compile)
export TORCH_CUDA_ARCH_LIST="8.9"   # Ada (RTX 4080 Laptop) only — big speedup
pip install "git+https://github.com/facebookresearch/pytorch3d.git@v0.7.7" --no-build-isolation || exit 1

# 5) CUDA submodules for the recon stage
cd "$REPO/submodules/nvdiffrast" && pip install . --no-build-isolation || exit 1
cd "$REPO/submodules/simple-knn" && pip install . --no-build-isolation || exit 1
pip install "git+https://github.com/rmurai0610/diff-gaussian-rasterization-w-pose.git" --no-build-isolation || exit 1
[ -d "$REPO/submodules/ODGS" ] || git clone --depth 1 https://github.com/esw0116/ODGS.git "$REPO/submodules/ODGS"
cd "$REPO/submodules/ODGS" && pip install submodules/odgs-gaussian-rasterization --no-build-isolation || exit 1

# 6) smoke: the imports our two stages actually need
python - <<'PY'
import torch; print("torch", torch.__version__, "cuda", torch.cuda.is_available())
import diffsynth; print("diffsynth OK")
import pytorch3d; print("pytorch3d OK")
import nvdiffrast; print("nvdiffrast OK")
PY
echo M3D_FIX_OK
