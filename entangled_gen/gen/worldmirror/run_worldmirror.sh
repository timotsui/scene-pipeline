#!/bin/bash
# run_worldmirror.sh <scene_in> <scene_out> — WorldMirror 2.0 feed-forward
# recon on perspective crops of OUR pano (Exp 4 local leg).
#   scene_in  = source pano scene, e.g. bedroom_hw1 (needs OUT/<scene_in>/crops/)
#   scene_out = eval scene name, e.g. bedroom_hw2
# Produces gaussians.ply -> OUT/<scene_out>/gen_raw.ply.
# Known caveat (plan doc 4.1): crops are a zero-baseline rotation-only rig —
# depth comes from the model's monocular priors, not parallax.
# GPU run: clock lock + deadman required (same guard pair as m3d).
set -o pipefail
SIN="${1:?source scene, e.g. bedroom_hw1}"
SOUT="${2:?output scene, e.g. bedroom_hw2}"
# Footprint knobs (2026-07-07 deadman trip: 14 views @952 pegged VRAM 11.8/12
# and the driver spilled to WDDM shared sysmem, draining WINDOWS RAM — no
# clean CUDA OOM. Shrink tokens instead: crops subdir + target_size.)
CROPS_SUB="${WM_CROPS_SUB:-crops8}"
TARGET="${WM_TARGET:-700}"

source /root/miniconda3/etc/profile.d/conda.sh
set +u; conda activate worldmirror
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$LD_LIBRARY_PATH"

REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/HY-World-2.0
OUT=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out
CROPS="$OUT/$SIN/$CROPS_SUB"
DEST="$OUT/$SOUT"
LOG="$OUT/logs/worldmirror_${SOUT}.log"
[ -d "$CROPS" ] || { echo "NO_CROPS $CROPS (run make_crops.py first)" | tee -a "$LOG"; exit 1; }
mkdir -p "$DEST"

cd "$REPO" || exit 1

(
  while true; do
    echo "$(date +%T) $(free -m | awk '/Mem:/{print "ram_used_mb="$3}') $(free -m | awk '/Swap:/{print "swap_used_mb="$3}') $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | sed 's/^/vram_mb=/')"
    sleep 20
  done >> "$OUT/logs/worldmirror_${SOUT}_resources.log" 2>&1
) &
SAMPLER=$!
trap 'kill $SAMPLER 2>/dev/null' EXIT

echo ">>> worldmirror: $SIN/$CROPS_SUB (target $TARGET) -> $SOUT started $(date '+%F %T')" | tee -a "$LOG"
python -m hyworld2.worldrecon.pipeline \
  --input_path "$CROPS" \
  --strict_output_path "$DEST/worldmirror_out" \
  --target_size "$TARGET" \
  --no_sky_mask \
  2>&1 | tee -a "$LOG"
RC=${PIPESTATUS[0]}

PLY="$DEST/worldmirror_out/gaussians.ply"
if [ -f "$PLY" ]; then
  cp "$PLY" "$DEST/gen_raw.ply"
  echo "OK splat -> $DEST/gen_raw.ply ($(date '+%F %T'))" | tee -a "$LOG"
  exit 0
fi
echo "NO_SPLAT_PRODUCED (rc=$RC) $(date '+%F %T')" | tee -a "$LOG"
exit 1
