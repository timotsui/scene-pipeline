#!/bin/bash
# run_panogen.sh  <prompt>  <scene>  [seed]
#
# HunyuanWorld 1.0 Lite stage 1: text -> equirect panorama (FLUX.1-dev +
# PanoDiT-Text LoRA, 960x1920, 50 steps). Writes OUT/<scene>/panorama.png —
# the paths.panorama() location — plus a run log next to it.
#
# Eval-plan step 1.2: run bedroom first, USER views the pano before anything
# else. Baseline prompts use seed 0 (SceneDreamer360 parity).
#
# VRAM (12 GB) — two modes:
#   MODE=safe (default): HW1_SEQ_OFFLOAD=1 sequential offload, bf16, no fp8
#     flags. Peak VRAM <1 GB — far from the driver-hang zone. Slower. This is
#     the UNATTENDED mode (machine cannot be power-cycled remotely).
#   MODE=fast (4th arg "fast"): stock model-offload + --fp8_gemm
#     --fp8_attention (Lite config) — ~12 GB peak, at the edge. Only run
#     attended.
set -o pipefail
PROMPT="${1:?prompt}"; SCENE="${2:?scene name, e.g. bedroom_hw1}"; SEED="${3:-0}"
MODE="${4:-safe}"

source /root/miniconda3/etc/profile.d/conda.sh
set +u; conda activate HunyuanWorld
# WSL: CUDA driver stub lives off the loader path (same fix as scenedreamer360)
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$LD_LIBRARY_PATH"

REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/HunyuanWorld-1.0
OUT=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out
SCENE_DIR="$OUT/$SCENE"
mkdir -p "$SCENE_DIR"

cd "$REPO" || exit 1
if [ "$MODE" = "fast" ]; then
  EXTRA_FLAGS="--fp8_gemm --fp8_attention"; export HW1_SEQ_OFFLOAD=0
else
  EXTRA_FLAGS=""; export HW1_SEQ_OFFLOAD=1
fi
echo ">>> hw1 panogen [$MODE]: '$PROMPT' seed=$SEED -> $SCENE_DIR"
python3 demo_panogen.py \
  --prompt "$PROMPT" \
  --seed "$SEED" \
  --output_path "$SCENE_DIR" \
  $EXTRA_FLAGS \
  2>&1 | tee "$SCENE_DIR/panogen.log"
RC=${PIPESTATUS[0]}

if [ -f "$SCENE_DIR/panorama.png" ]; then
  echo "OK panorama -> $SCENE_DIR/panorama.png"; exit 0
fi
echo "NO_PANO_PRODUCED (rc=$RC) — see $SCENE_DIR/panogen.log"
exit 1
