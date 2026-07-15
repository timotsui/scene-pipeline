#!/bin/bash
# follow_playroom.sh — chained follower for the 2026-07-06 night (user's
# standing order ~01:10: "if all the bedrooms are done and I'm not back,
# continue to playroom"). Waits for overnight_hw1.sh to exit AND the bedroom
# pano to exist, then runs the playroom pano in SAFE mode. Nothing else —
# scenegen stays attended-only.
set -o pipefail
GEN=/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/entangled_gen/gen/hunyuanworld
OUT=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out
LOG="$OUT/logs/overnight_hw1.log"
log(){ echo "[$(date +%F' '%T)] $*" | tee -a "$LOG"; }

# wait for the main runner to exit (poll; it logs 'queue end' but process
# death is the robust signal)
while pgrep -f "bash $GEN/overnight_hw1.sh" >/dev/null 2>&1; do sleep 60; done

if [ ! -f "$OUT/bedroom_hw1/panorama.png" ]; then
  log "follower: bedroom pano MISSING after runner exit — not continuing (see panogen.log)"
  exit 1
fi

if [ -f "$OUT/playroom_hw1/panorama.png" ]; then
  log "follower: playroom pano already exists, nothing to do"
  exit 0
fi

log "follower: bedroom done, user standing order -> playroom pano (safe mode)"
bash "$GEN/run_panogen.sh" "a cozy playroom with a rug and shelves" playroom_hw1 0 safe >> "$LOG" 2>&1
log "follower: playroom rc=$? ($([ -f "$OUT/playroom_hw1/panorama.png" ] && echo pano-exists || echo NO-PANO))"
