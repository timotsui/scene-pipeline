#!/bin/bash
# overnight_hw1.sh — 2026-07-05 overnight queue (user asleep, pre-authorized).
#
# Depth-first Experiment 1 with lookahead past the pano user-gates: generate
# both panos, then attempt full scenegen on bedroom. Every stage is resumable
# (skips if its artifact exists) and logs to OUT/logs on /mnt/d so evidence
# survives WSL/machine death. A resource sampler runs alongside.
#
# Machine-safety context: WSL capped at memory=24GB swap=16GB (.wslconfig);
# worst case is the cgroup OOM-killer taking python down, not the box.
set -o pipefail
GEN=/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/entangled_gen/gen/hunyuanworld
OUT=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out
LOG="$OUT/logs/overnight_hw1.log"
mkdir -p "$OUT/logs"
log(){ echo "[$(date +%F' '%T)] $*" | tee -a "$LOG"; }

# --- resource sampler: RAM + VRAM every 30 s, post-mortem evidence ---------
(
  while true; do
    echo "$(date +%T) $(free -m | awk '/Mem:/{print "ram_used_mb="$3}') $(free -m | awk '/Swap:/{print "swap_used_mb="$3}') $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | sed 's/^/vram_mb=/')"
    sleep 30
  done >> "$OUT/logs/overnight_hw1_resources.log" 2>&1
) &
SAMPLER=$!
trap 'kill $SAMPLER 2>/dev/null' EXIT

log "=== overnight queue start ==="

# --- stage 0: wait for FLUX.1-dev download to be complete ------------------
# hf download exits 0 only when every file is present; re-invoking is a cheap
# no-op if already done, so just run it (resumes if the background pull died).
log "stage 0: ensure FLUX.1-dev complete"
/root/miniconda3/envs/HunyuanWorld/bin/huggingface-cli download black-forest-labs/FLUX.1-dev >> "$LOG" 2>&1
log "stage 0 rc=$? (0 = weights complete)"

# --- stage 1+2: panos, bedroom then playroom (VRAM moment of truth) --------
if [ ! -f "$OUT/bedroom_hw1/panorama.png" ]; then
  log "stage 1: bedroom pano"
  bash "$GEN/run_panogen.sh" "a bedroom with a bed, a nightstand and a wardrobe" bedroom_hw1 0 >> "$LOG" 2>&1
  log "stage 1 rc=$?"
else log "stage 1: bedroom pano exists, skip"; fi

if [ ! -f "$OUT/bedroom_hw1/panorama.png" ]; then
  log "ABORT: bedroom pano failed — leaving GPU work here (likely OOM; see
       panogen.log; sequential-offload patch is the next move, made manually
       so it stays a documented decision, not an overnight surprise)"
  exit 1
fi

# stage 2 (playroom pano) CUT per user 07-06 ~00:55: ONE scene, ONE pipeline
# tonight. Run tomorrow: bash run_panogen.sh "a cozy playroom with a rug and
# shelves" playroom_hw1 0
log "stage 2: playroom pano intentionally SKIPPED (user: one scene tonight)"

# --- stage 3: scenegen — CUT from the unattended queue (2026-07-06) --------
# The double FluxFill load is the highest crash-risk event and the machine
# cannot be power-cycled remotely. Run tomorrow ATTENDED via run_scenegen.sh
# (weights are prefetched by prepare_scenegen.sh regardless — network only).
log "stage 3: scenegen intentionally SKIPPED (unattended run; crash prevention)"

log "=== overnight queue end ==="
