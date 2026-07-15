#!/bin/bash
# prepare_scenegen.sh — fetch everything demo_scenegen.py needs (step 1.3
# prep). Idempotent; touches .scenegen_ready on success so overnight_hw1.sh
# knows stage 3 may run.
set -o pipefail
source /root/miniconda3/etc/profile.d/conda.sh
conda activate HunyuanWorld
HF=/root/miniconda3/envs/HunyuanWorld/bin/huggingface-cli
GEN=/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/entangled_gen/gen/hunyuanworld
REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/HunyuanWorld-1.0

# 1) gated FLUX.1-Fill-dev (~24 GB) — license accepted by user 2026-07-05
$HF download black-forest-labs/FLUX.1-Fill-dev || exit 1

# 2) ZIM onnx weights -> the cwd-relative path layer_decomposer expects
#    (self.zim_checkpoint = "./ZIM/zim_vit_l_2092", cwd = repo root)
mkdir -p "$REPO/ZIM"
$HF download naver-iv/zim-anything-vitl \
  zim_vit_l_2092/encoder.onnx zim_vit_l_2092/decoder.onnx \
  --local-dir "$REPO/ZIM" || exit 1

# 3) onnxruntime-gpu for ZIM (device cuda:0); numpy 1.24.1 already satisfies
pip show onnxruntime-gpu >/dev/null 2>&1 || pip install onnxruntime-gpu || exit 1

# 4) prefetch the public auto-download models so runtime needs no network
$HF download IDEA-Research/grounding-dino-tiny || exit 1
$HF download Ruicheng/moge-vitl || exit 1
# (RealESRGAN_x2plus.pth still auto-downloads on first use via basicsr URL)

touch "$GEN/.scenegen_ready"
echo SCENEGEN_PREP_OK
