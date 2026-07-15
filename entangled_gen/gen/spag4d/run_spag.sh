#!/bin/bash
# run_spag.sh <pano_path_wsl> <scene> [extra spag4d convert args]
#
# One pano -> 3DGS ply at OUT/<scene>/gen_raw.ply (the paths.ply() location).
# Copies the source pano into the scene dir for provenance. Defaults: DAP
# depth, stride 2 (~350K splats); pass --stride 1 for max density or
# --depth-model da360 to compare depth backends.
set -o pipefail
PANO="${1:?pano path (wsl)}"; SCENE="${2:?scene name, e.g. bedroom_spag}"; shift 2

source /root/miniconda3/etc/profile.d/conda.sh
set +u; conda activate spag4d
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$LD_LIBRARY_PATH"

REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/SPAG4d
OUT=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out
SCENE_DIR="$OUT/$SCENE"
mkdir -p "$SCENE_DIR"
[ -f "$PANO" ] || { echo "NO_PANO $PANO"; exit 1; }
cp -n "$PANO" "$SCENE_DIR/panorama.png" 2>/dev/null

# bypass the repo CLI (broken at HEAD: passes sharp_refine kwargs core
# doesn't accept) — call the core API via our spag_convert.py instead
GEN=/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/entangled_gen/gen/spag4d
cd "$SCENE_DIR" || exit 1
echo ">>> spag4d convert: $PANO -> $SCENE_DIR/gen_raw.ply ($*)"
python "$GEN/spag_convert.py" "$PANO" "$SCENE_DIR/gen_raw.ply" "$@" \
  2>&1 | tee "$SCENE_DIR/spag.log"
RC=${PIPESTATUS[0]}

if [ -f "$SCENE_DIR/gen_raw.ply" ]; then
  echo "OK ply -> $SCENE_DIR/gen_raw.ply ($(du -h "$SCENE_DIR/gen_raw.ply" | cut -f1))"; exit 0
fi
echo "NO_PLY_PRODUCED (rc=$RC) — see $SCENE_DIR/spag.log"
exit 1
