#!/bin/bash
# launch_detached.sh <prompt> <out_ply> <seed>
#
# Detached wrapper around run_scenedreamer360.sh: appends to out/run.log,
# runs a RAM/VRAM sampler to out/mem.log, and writes a final STATUS line.
# Launch with:  setsid nohup ./launch_detached.sh ... >/dev/null 2>&1 &
# so the run survives the launching session (2026-07-04: host froze mid-run;
# also protects against the driving app crashing).
PROMPT="${1:?prompt}"; OUT_PLY="${2:?out ply}"; SEED="${3:-0}"
HERE="$(cd "$(dirname "$0")" && pwd)"
OUT="$HERE/../out"
mkdir -p "$OUT" "$(dirname "$OUT_PLY")"

echo "=== launch $(date) ===" >> "$OUT/run.log"
echo "prompt: $PROMPT" >> "$OUT/run.log"

(
  while true; do
    ram=$(free -m | awk '/^Mem:/{printf "used=%sM avail=%sM", $3, $7}')
    swap=$(free -m | awk '/^Swap:/{printf "%sM", $3}')
    vram=$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null)
    echo "$(date +%H:%M:%S)  RAM $ram  swap=$swap  VRAM=${vram}M" >> "$OUT/mem.log"
    # 1s sampling: the 15:28 freeze allocated from 7 GB to the 12 GB wall faster
    # than the old 5s interval could record
    sleep 1
  done
) &
MEMPID=$!

"$HERE/run_scenedreamer360.sh" "$PROMPT" "$OUT_PLY" "$SEED" >> "$OUT/run.log" 2>&1
RC=$?

kill "$MEMPID" 2>/dev/null
echo "=== STATUS rc=$RC $(date) ===" >> "$OUT/run.log"
exit $RC
