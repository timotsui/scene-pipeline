#!/bin/bash
# run_m3d_video.sh <scene> [angle] [movement_mode]
#
# Matrix-3D stage 2 on OUR pano: OUT/<scene>/panorama.png -> panoramic video
# at <repo>/output/<scene>/pano_video.mp4. 5B model + vram management
# (~12 GB VRAM claim) — RUNTIME-RISKY on the 12 GB card: run guarded
# (deadman armed), expect overnight-class duration (1 h on an A800).
#
# 2026-07-06 12:56 incident: this froze the whole box mid-VAE-encode (swap=
# 40 GB thrash, no deadman armed; hard reset). There is NO lighter config:
# the 5B path is fixed 704x1408 (--resolution is ignored), and non-5B swaps
# in Wan2.1-I2V-14B — bigger, plus a ~30 GB download. Retry = same command,
# swap capped back at 24 GB (clean OOM-kill beats a frozen machine), deadman
# armed via tools/deadman.ps1, resource sampler below for a memory trace.
#
# Their own-pano contract (README): run dir with pano_img.jpg + prompt.txt.
set -o pipefail
SCENE="${1:?scene, e.g. bedroom_hw1}"; ANGLE="${2:-0}"; MOVE="${3:-straight}"

source /root/miniconda3/etc/profile.d/conda.sh
set +u; conda activate matrix3d
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$LD_LIBRARY_PATH"
export CUDA_HOME="$CONDA_PREFIX"
# conda cuda-toolkit headers/libs live under targets/ — needed by torch JIT
# (nvdiffrast plugin build: fatal error cuda_runtime.h without these)
export CPATH="$CONDA_PREFIX/targets/x86_64-linux/include:$CPATH"
export LIBRARY_PATH="$CONDA_PREFIX/targets/x86_64-linux/lib:$CONDA_PREFIX/lib:$LIBRARY_PATH"

REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/Matrix-3D
OUT=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out
PANO="$OUT/$SCENE/panorama.png"
[ -f "$PANO" ] || { echo "NO_PANO $PANO"; exit 1; }

RUN="$REPO/output/$SCENE"
mkdir -p "$RUN"
# their loader wants jpg + a prompt file
python - "$PANO" "$RUN/pano_img.jpg" <<'PY'
import sys
from PIL import Image
Image.open(sys.argv[1]).convert("RGB").save(sys.argv[2], quality=95)
PY
case "$SCENE" in
  bedroom*)  echo "a bedroom with a bed, a nightstand and a wardrobe" > "$RUN/prompt.txt" ;;
  playroom*) echo "a cozy playroom with a rug and shelves" > "$RUN/prompt.txt" ;;
  *)         echo "an indoor scene" > "$RUN/prompt.txt" ;;
esac

cd "$REPO" || exit 1

# resource sampler (same shape as scenegen_attempt.sh) — the 12:56 freeze
# left no memory trace; never run this stage blind again
(
  while true; do
    echo "$(date +%T) $(free -m | awk '/Mem:/{print "ram_used_mb="$3}') $(free -m | awk '/Swap:/{print "swap_used_mb="$3}') $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | sed 's/^/vram_mb=/')"
    sleep 20
  done >> "$OUT/logs/m3d_video_${SCENE}_resources.log" 2>&1
) &
SAMPLER=$!
trap 'kill $SAMPLER 2>/dev/null' EXIT

echo ">>> m3d video: $SCENE (5B, vram_mgmt, angle=$ANGLE, $MOVE) -> $RUN"
VISIBLE_GPU_NUM=1 torchrun --nproc_per_node 1 code/panoramic_image_to_video.py \
  --inout_dir "$RUN" \
  --resolution 720 \
  --use_5b_model \
  --enable_vram_management \
  --seed 0 \
  --angle "$ANGLE" \
  --movement_range 0.6 \
  --movement_mode "$MOVE" \
  2>&1 | tee "$OUT/logs/m3d_video_${SCENE}.log"
RC=${PIPESTATUS[0]}

[ -f "$RUN/pano_video.mp4" ] && { echo "OK video -> $RUN/pano_video.mp4"; exit 0; }
echo "NO_VIDEO_PRODUCED (rc=$RC) — see $OUT/logs/m3d_video_${SCENE}.log"
exit 1
