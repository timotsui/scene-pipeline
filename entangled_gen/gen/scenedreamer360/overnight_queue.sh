#!/bin/bash
# overnight_queue.sh (2026-07-04) — wait for the in-flight generation run to
# finish, then run the remaining prompt queue SEQUENTIALLY (one GPU run at a
# time, per the 1-at-a-time rule). Progress -> out/queue.log.
#
# Queue: bedroom (already running when this starts) -> living room -> kitchen.
OUT=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out
RUNNERS=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/runners

log(){ mkdir -p "$OUT/logs"; echo "$(date '+%m-%d %H:%M:%S') $*" >> "$OUT/logs/queue.log"; }

wait_for_idle(){
  sleep 30
  while pgrep -f run_scenedreamer360.sh >/dev/null 2>&1; do sleep 60; done
}

archive(){  # archive <tag>
  mkdir -p "$OUT/logs"
  mv "$OUT/run.log" "$OUT/logs/run.$1.log" 2>/dev/null
  mv "$OUT/mem.log" "$OUT/logs/mem.$1.log" 2>/dev/null
}

log "queue start — waiting for bedroom run to finish"
wait_for_idle
log "bedroom finished ($(ls -la "$OUT/bedroom/gen_raw.ply" 2>/dev/null | awk '{print $5}' ) bytes)"
archive 9.bedroom

log "launching living room"
"$RUNNERS/launch_detached.sh" "a living room with a sofa, a coffee table and a television" "$OUT/livingroom/gen_raw.ply" 0
log "living room rc=$? ($(ls -la "$OUT/livingroom/gen_raw.ply" 2>/dev/null | awk '{print $5}') bytes)"
archive 10.livingroom

log "launching kitchen"
"$RUNNERS/launch_detached.sh" "a kitchen with a dining table and chairs" "$OUT/kitchen/gen_raw.ply" 0
log "kitchen rc=$? ($(ls -la "$OUT/kitchen/gen_raw.ply" 2>/dev/null | awk '{print $5}') bytes)"
archive 11.kitchen

log "queue done"
