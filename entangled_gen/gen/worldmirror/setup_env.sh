#!/bin/bash
# setup_env.sh — conda env `worldmirror` for HY-World-2.0 WorldMirror 2.0
# inference (Exp 4 local leg, bedroom_hw2).
#
# Dependency findings (2026-07-07, from import scan of hyworld2/worldrecon):
# - requirements_git.txt (pytorch3d/fused-ssim/spz/MoGe/nerfview) is for the
#   worldgen TRAINING tree — worldrecon never imports any of it. SKIPPED.
# - Load-time third-party imports: torch/torchvision, gsplat (model imports
#   GaussianSplatRenderer unconditionally), onnxruntime + pycolmap
#   (inference_utils, imported even when unused), cv2, einops, omegaconf,
#   plyfile, safetensors, scipy, matplotlib, trimesh, huggingface_hub, tqdm,
#   numpy 1.26.4. gradio only in gradio_app.py (skipped).
# - torch 2.7.1 from PLAIN PyPI = cu126 build (same lesson as matrix3d).
# - gsplat: try the prebuilt pt27cu126 wheel index first; source build needs
#   nvcc (would need conda cuda-toolkit like matrix3d) — avoid if wheel works.
# DO NOT run while another heavy job owns the WSL RAM cap.
set -e
source /root/miniconda3/etc/profile.d/conda.sh

conda create -y -n worldmirror python=3.10
conda activate worldmirror

pip install torch==2.7.1 torchvision==0.22.1
pip install numpy==1.26.4 opencv-python einops omegaconf plyfile safetensors \
    scipy matplotlib trimesh "huggingface_hub" tqdm imageio[ffmpeg] \
    onnxruntime pycolmap==3.10.0
# gsplat prebuilt wheel for torch 2.7 + cu126
pip install gsplat --index-url https://docs.gsplat.studio/whl/pt27cu126 \
  || pip install gsplat  # fallback: source build (needs nvcc on PATH)

python - <<'PY'
import torch, gsplat, onnxruntime, pycolmap, cv2, trimesh
print("worldmirror env OK: torch", torch.__version__, "cuda", torch.cuda.is_available(),
      "gsplat", gsplat.__version__)
PY
echo "WORLDMIRROR_ENV_OK"
