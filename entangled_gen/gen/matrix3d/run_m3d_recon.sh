#!/bin/bash
# run_m3d_recon.sh <scene> — Matrix-3D stage 3: pano video -> 3DGS splat
# (optimization recon via Pano_GS_Opt; PanoLRM path skipped). Consumes the
# run_m3d_video.sh output dir <repo>/output/<scene>/ (pano_video.mp4 +
# condition/ + generated/). Chain inside panoramic_video_to_3DScene.py:
#   geom optim -> mv extraction -> StableSR (4-step turbo SR) -> Pano_GS_Opt
#   train.py (3000 iters, densify 500-1501) -> generated_3dgs_opt.ply
# Copies the ply to OUT/<base>_m3d/gen_raw.ply for the eval kit.
# GPU-heavy: launch only with the clock lock applied + deadman armed
# (same guard pair as the video stage — see tools/launch_m3d_video_guarded.ps1).
# All markers (OK/NO_*) are tee'd into $OUT/logs so the Windows-side monitor
# sees them (the video-stage lesson: start-script stdout goes to /root only).
set -o pipefail
SCENE="${1:?scene, e.g. bedroom_hw1}"

source /root/miniconda3/etc/profile.d/conda.sh
set +u; conda activate matrix3d
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$LD_LIBRARY_PATH"
export CUDA_HOME="$CONDA_PREFIX"
# conda cuda-toolkit headers/libs live under targets/ — needed by torch JIT
export CPATH="$CONDA_PREFIX/targets/x86_64-linux/include:$CPATH"
export LIBRARY_PATH="$CONDA_PREFIX/targets/x86_64-linux/lib:$CONDA_PREFIX/lib:$LIBRARY_PATH"

REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/Matrix-3D
OUT=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out
RUN="$REPO/output/$SCENE"
LOG="$OUT/logs/m3d_recon_${SCENE}.log"
[ -f "$RUN/pano_video.mp4" ] || { echo "NO_VIDEO $RUN/pano_video.mp4" | tee -a "$LOG"; exit 1; }

cd "$REPO" || exit 1

# resource sampler — never run a runtime-risky stage without a memory trace
(
  while true; do
    echo "$(date +%T) $(free -m | awk '/Mem:/{print "ram_used_mb="$3}') $(free -m | awk '/Swap:/{print "swap_used_mb="$3}') $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | sed 's/^/vram_mb=/')"
    sleep 20
  done >> "$OUT/logs/m3d_recon_${SCENE}_resources.log" 2>&1
) &
SAMPLER=$!
trap 'kill $SAMPLER 2>/dev/null' EXIT

echo ">>> m3d recon: $SCENE (resolution 720, GS 3000 iters) started $(date '+%F %T')" | tee -a "$LOG"
python code/panoramic_video_to_3DScene.py \
  --inout_dir "output/$SCENE" \
  --resolution 720 \
  2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}

if [ -f "$RUN/generated_3dgs_opt.ply" ]; then
  DEST="$OUT/${SCENE%%_*}_m3d"    # bedroom_hw1 -> bedroom_m3d
  mkdir -p "$DEST"
  cp "$RUN/generated_3dgs_opt.ply" "$DEST/gen_raw.ply"
  echo "OK splat -> $DEST/gen_raw.ply ($(date '+%F %T'))" | tee -a "$LOG"
  exit 0
fi
echo "NO_SPLAT_PRODUCED (rc=$RC) $(date '+%F %T')" | tee -a "$LOG"
exit 1
