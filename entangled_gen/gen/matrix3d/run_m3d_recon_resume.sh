#!/bin/bash
# run_m3d_recon_resume.sh <scene> — resume the m3d recon after the StableSR
# import crash (2026-07-07 04:10: env protobuf too old for tensorboard's
# runtime_version, pulled in via pytorch_lightning; geom optim + mv
# extraction had already SUCCEEDED — 108 frames in mv_rgb_ori).
#
# DEVIATION (noted for the comparison report): StableSR is BYPASSED —
# mv_rgb_ori is copied to mv_rgb unsharpened and Pano_GS_Opt trains on the
# original frames. SR is cosmetic (4-step sharpening of training targets);
# cameras/depths/geometry are untouched. Fixing protobuf in the matrix3d env
# unattended was judged riskier than skipping SR (11-failure-mode env).
# GS train command copied verbatim from panoramic_video_to_3DScene.py.
set -o pipefail
SCENE="${1:?scene, e.g. bedroom_hw1}"

source /root/miniconda3/etc/profile.d/conda.sh
set +u; conda activate matrix3d
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$LD_LIBRARY_PATH"
export CUDA_HOME="$CONDA_PREFIX"
export CPATH="$CONDA_PREFIX/targets/x86_64-linux/include:$CPATH"
export LIBRARY_PATH="$CONDA_PREFIX/targets/x86_64-linux/lib:$CONDA_PREFIX/lib:$LIBRARY_PATH"

REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/Matrix-3D
OUT=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out
RUN="$REPO/output/$SCENE"
DATA="$RUN/geom_optim/data"
GSOUT="$RUN/geom_optim/output"
LOG="$OUT/logs/m3d_recon_resume_${SCENE}.log"
[ -d "$DATA/mv_rgb_ori" ] || { echo "NO_MV_FRAMES $DATA/mv_rgb_ori" | tee -a "$LOG"; exit 1; }

# SR bypass: train on the original frames
rm -rf "$DATA/mv_rgb"
cp -r "$DATA/mv_rgb_ori" "$DATA/mv_rgb"

(
  while true; do
    echo "$(date +%T) $(free -m | awk '/Mem:/{print "ram_used_mb="$3}') $(free -m | awk '/Swap:/{print "swap_used_mb="$3}') $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | sed 's/^/vram_mb=/')"
    sleep 20
  done >> "$OUT/logs/m3d_recon_${SCENE}_resources.log" 2>&1
) &
SAMPLER=$!
trap 'kill $SAMPLER 2>/dev/null' EXIT

echo ">>> m3d recon RESUME (SR bypassed): $SCENE GS 3000 iters started $(date '+%F %T')" | tee -a "$LOG"
cd "$REPO/code/Pano_GS_Opt" || exit 1
python train.py -s "$DATA" -m "$GSOUT" -r 1 --use_decoupled_appearance \
  --save_iterations 3000 6000 9000 12000 15000 --test_iterations 3000 \
  --sh_degree 0 --densify_from_iter 500 --densify_until_iter 1501 \
  --iterations 3000 --eval --img_sample_interval 1 --num_views_per_view 3 \
  --num_of_point_cloud 3000000 --device cuda:0 \
  --distortion_from_iter 6500 --depth_normal_from_iter 6500 \
  2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}

GS_PLY="$GSOUT/point_cloud/iteration_3000/point_cloud.ply"
if [ -f "$GS_PLY" ]; then
  cp "$GS_PLY" "$RUN/generated_3dgs_opt.ply"
  DEST="$OUT/${SCENE%%_*}_m3d"
  mkdir -p "$DEST"
  cp "$GS_PLY" "$DEST/gen_raw.ply"
  echo "OK splat -> $DEST/gen_raw.ply ($(date '+%F %T'))" | tee -a "$LOG"
  exit 0
fi
echo "NO_SPLAT_PRODUCED (rc=$RC) $(date '+%F %T')" | tee -a "$LOG"
exit 1
