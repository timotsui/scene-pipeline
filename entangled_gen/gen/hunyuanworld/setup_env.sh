#!/bin/bash
# setup_env.sh — HunyuanWorld 1.0 Lite install log (WSL Ubuntu-24.04, as root).
# Documents the steps actually run 2026-07-05; re-runnable but written as a
# template like the scenedreamer360 scripts, not a push-button installer.
set -o pipefail

REPOS=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos
CONDA=/root/miniconda3/bin/conda

# 1) shallow clone into the local data area (NOT in git) — done 2026-07-05
cd "$REPOS" || exit 1
[ -d HunyuanWorld-1.0 ] || git clone --depth 1 https://github.com/Tencent-Hunyuan/HunyuanWorld-1.0.git

# 2) dedicated conda env 'HunyuanWorld' (python 3.10, torch 2.5.0+cu124),
#    fully separate from panfusion — done 2026-07-05 (~10 GB into the WSL vhdx)
#    NOTE the yaml's pip stage FAILS as shipped: av==14.3.0 is yanked from
#    PyPI. Fix applied: docker/extract_pip.sh dumps the pip: section to
#    docker/pip_requirements.txt, two repins:
#      av ==14.3.0 -> ==14.2.0   (14.3.0 yanked from PyPI; 14.4.0 has no
#                                 cp310 wheel, sdist wants ffmpeg-7 headers)
#      flash-attn COMMENTED OUT  (source-build needs torch at metadata time +
#                                 nvcc; grep shows NO repo code imports
#                                 flash_attn — install a prebuilt wheel from
#                                 Dao-AILab releases later IF runtime asks)
#    installed
#    manually (log: /root/hw1_pip.log in WSL — NOT /tmp, Ubuntu wipes /tmp
#    on every WSL restart).
cd HunyuanWorld-1.0 || exit 1
$CONDA env list | grep -q '^HunyuanWorld ' || $CONDA env create -f docker/HunyuanWorld.yaml
# then: bash docker/extract_pip.sh && conda activate HunyuanWorld && \
#   pip install -r docker/pip_requirements.txt   (after the av bump)

# 3) post-install fixes actually needed to import hy3dworld (its __init__
#    eagerly imports the WHOLE scenegen chain, pano-only doesn't dodge these):
#      pip uninstall -y basicsr && pip install basicsr-fixed
#        (stock basicsr breaks on torchvision>=0.17 functional_tensor removal;
#         basicsr-fixed is upstream's own documented choice)
#      pip install realesrgan --no-deps
#        (--no-deps is LOAD-BEARING: realesrgan declares basicsr as a dep and
#         would drag the broken one back over basicsr-fixed)
#      pip install zim-anything --no-deps
#        (import-only for pano; runtime deps (onnxruntime) + the zim_vit_l_2092
#         onnx weights are a 1.3/scenegen task)
#    Verify with: bash check_env.sh  (torch 2.5.0 cuda True, imports OK 07-05)

# 4) weights — see download_weights.sh (gated FLUX repos need the user's HF
#    login + accepted licenses first). tencent/HunyuanWorld-1 (1.1 GB) pulled
#    2026-07-05 into /root/.cache/huggingface.

# ---------------------------------------------------------------------------
# STAGED, NOT INSTALLED (scenegen stage only — demo_panogen.py doesn't import
# any of these; install when eval-plan step 1.3 starts):
#
# source /root/miniconda3/etc/profile.d/conda.sh && conda activate HunyuanWorld
# cd "$REPOS"
# git clone https://github.com/xinntao/Real-ESRGAN.git   # pano superres in scenegen
# cd Real-ESRGAN && pip install basicsr-fixed facexlib gfpgan && \
#   pip install -r requirements.txt && python setup.py develop
# cd "$REPOS"
# git clone https://github.com/naver-ai/ZIM.git           # FG-layer matting
# cd ZIM && pip install -e . && mkdir -p zim_vit_l_2092 && cd zim_vit_l_2092 && \
#   wget https://huggingface.co/naver-iv/zim-anything-vitl/resolve/main/zim_vit_l_2092/encoder.onnx && \
#   wget https://huggingface.co/naver-iv/zim-anything-vitl/resolve/main/zim_vit_l_2092/decoder.onnx
# draco (compressed mesh export) skipped entirely unless ply export needs it.
# ---------------------------------------------------------------------------
echo "setup steps listed above — see README.md for status"
