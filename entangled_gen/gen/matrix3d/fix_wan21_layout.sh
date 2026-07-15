#!/bin/bash
# fix_wan21_layout.sh — DiffSynth's wan_video_new.py redirects the T5 +
# tokenizer (google/*) lookups to model id Wan-AI/Wan2.1-T2V-1.3B even for
# the 5B pipeline (redirect map at wan_video_new.py:296-304). The files are
# byte-identical to the ones in our Wan2.2-TI2V-5B snapshot — hardlink them
# into the expected folder instead of re-downloading 10.6 GB at 1 MB/s from
# modelscope.
set -o pipefail
CK=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/Matrix-3D/checkpoints/Wan-AI
SRC="$CK/Wan2.2-TI2V-5B"
DST="$CK/Wan2.1-T2V-1.3B"

rm -rf "$DST/._____temp"
mkdir -p "$DST/google"

[ -f "$DST/models_t5_umt5-xxl-enc-bf16.pth" ] || \
  ln "$SRC/models_t5_umt5-xxl-enc-bf16.pth" "$DST/models_t5_umt5-xxl-enc-bf16.pth" || \
  cp "$SRC/models_t5_umt5-xxl-enc-bf16.pth" "$DST/models_t5_umt5-xxl-enc-bf16.pth"

# tokenizer files (small)
cp -rn "$SRC/google/." "$DST/google/"

ls -la "$DST" "$DST/google" | head -12
echo WAN21_LAYOUT_OK
