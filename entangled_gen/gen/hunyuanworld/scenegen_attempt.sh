#!/bin/bash
# scenegen_attempt.sh — attended-window bedroom scenegen attempt (2026-07-06
# night, user approved "after playroom pano, try bedroom to splat").
# Zero-argument by design (see start_night.sh header for why). Runs its own
# resource sampler. Expected failure mode: cgroup OOM-kill during the double
# FluxFill load (2× bf16 ≈ 68 GB virtual vs 20+24 GB available) — that is a
# CLEAN death and a legit 1.4 data point, not a machine crash. Machine
# safety = the WSL 20 GB cap (Windows keeps ~11 GB) + the deadman watchdog.
set -o pipefail
GEN=/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/entangled_gen/gen/hunyuanworld
OUT=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out
LOG="$OUT/logs/overnight_hw1.log"
log(){ echo "[$(date +%F' '%T)] $*" | tee -a "$LOG"; }

# refuse to start while any other GPU python is alive (serial GPU rule)
if pgrep -f demo_panogen >/dev/null; then
  log "scenegen_attempt: pano still running — refusing to start"; exit 1
fi

(
  while true; do
    echo "$(date +%T) $(free -m | awk '/Mem:/{print "ram_used_mb="$3}') $(free -m | awk '/Swap:/{print "swap_used_mb="$3}') $(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits 2>/dev/null | head -1 | sed 's/^/vram_mb=/')"
    sleep 20
  done >> "$OUT/logs/scenegen_resources.log" 2>&1
) &
SAMPLER=$!
trap 'kill $SAMPLER 2>/dev/null' EXIT

log "stage 3 (attended window): bedroom scenegen attempt"
bash "$GEN/run_scenegen.sh" bedroom_hw1 >> "$LOG" 2>&1
RC=$?
if ls "$OUT/bedroom_hw1/scenegen"/mesh_layer*.ply >/dev/null 2>&1; then
  log "stage 3 rc=$RC — MESHES EXIST, proceeding to splat conversion"
  source /root/miniconda3/etc/profile.d/conda.sh
  conda activate HunyuanWorld
  python "$GEN/mesh_to_splat.py" bedroom_hw1 >> "$LOG" 2>&1
  log "mesh_to_splat rc=$? ($([ -f "$OUT/bedroom_hw1/gen_raw.ply" ] && echo gen_raw.ply-exists || echo NO-PLY))"
else
  log "stage 3 rc=$RC — NO MESHES (see scenegen.log; OOM-kill shows as rc=137)"
fi
