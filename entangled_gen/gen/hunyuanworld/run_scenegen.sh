#!/bin/bash
# run_scenegen.sh <scene>
#
# HunyuanWorld 1.0 Lite stage 2: panorama -> layered 3D mesh world.
# Reads OUT/<scene>/panorama.png, writes OUT/<scene>/scenegen/mesh_layer*.ply
# (open3d triangle meshes; draco export off). classes=indoor for our scenes.
#
# FG labels drive the semantic layering (fg1 = big furniture, fg2 = second
# pass on the remainder). First-guess values below — a design knob to revisit
# with the user, not ground truth.
#
# KNOWN RISK on 12 GB / 24 GB WSL RAM: LayerDecomposition loads TWO
# FluxFill pipelines (fg + sky) with LoRA fuse each — the load spike may
# OOM-kill python even with fp8 + offload. That outcome is contained (cgroup)
# and is exactly the 1.3/1.4 data point we need; log tells the story.
set -o pipefail
SCENE="${1:?scene name, e.g. bedroom_hw1}"

source /root/miniconda3/etc/profile.d/conda.sh
set +u; conda activate HunyuanWorld
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$LD_LIBRARY_PATH"

REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/HunyuanWorld-1.0
OUT=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out
PANO="$OUT/$SCENE/panorama.png"
SG_DIR="$OUT/$SCENE/scenegen"
[ -f "$PANO" ] || { echo "NO_PANORAMA $PANO"; exit 1; }
mkdir -p "$SG_DIR"

case "$SCENE" in
  bedroom*)  FG1="bed wardrobe nightstand"; FG2="lamp chair rug" ;;
  playroom*) FG1="shelf sofa rug";          FG2="toy lamp table" ;;
  *)         FG1="furniture";               FG2="decor" ;;
esac

cd "$REPO" || exit 1
echo ">>> hw1 scenegen: $SCENE (fg1: $FG1 | fg2: $FG2)"
CUDA_VISIBLE_DEVICES=0 python3 demo_scenegen.py \
  --image_path "$PANO" \
  --labels_fg1 $FG1 \
  --labels_fg2 $FG2 \
  --classes indoor \
  --seed 0 \
  --output_path "$SG_DIR" \
  --fp8_gemm --fp8_attention \
  2>&1 | tee "$SG_DIR/scenegen.log"
RC=${PIPESTATUS[0]}

if ls "$SG_DIR"/mesh_layer*.ply >/dev/null 2>&1; then
  echo "OK meshes: $(ls "$SG_DIR"/mesh_layer*.ply | tr '\n' ' ')"; exit 0
fi
echo "NO_MESH_PRODUCED (rc=$RC) — see $SG_DIR/scenegen.log"
exit 1
