#!/bin/bash
# overnight_queue2.sh (2026-07-05 ~04:00) — spatial-prompting experiment.
# Does dimension/spatial-relation language in the prompt improve the generator's
# spatial correctness? Four sequential runs (1-at-a-time rule):
#   1. ctrlroom     — empty-box control (minimal content, tests base geometry)
#   2. bedroomdim   — bedroom w/ explicit dimensions + layout
#   3. livingspatial— living room w/ explicit spatial relations
#   4. bedroom_s1   — LAST NIGHT'S bedroom prompt verbatim, seed 1 (variance probe)
# Progress -> out/queue2.log. Logs archived as run12..15.
OUT=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out
RUNNERS=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/runners

log(){ mkdir -p "$OUT/logs"; echo "$(date '+%m-%d %H:%M:%S') $*" >> "$OUT/logs/queue2.log"; }

wait_for_idle(){
  sleep 15
  while pgrep -f run_scenedreamer360.sh >/dev/null 2>&1; do sleep 60; done
}

archive(){
  mkdir -p "$OUT/logs"
  mv "$OUT/run.log" "$OUT/logs/run.$1.log" 2>/dev/null
  mv "$OUT/mem.log" "$OUT/logs/mem.$1.log" 2>/dev/null
}

run_one(){  # run_one <tag> <archive-prefix> <seed> <prompt>
  local tag="$1" arch="$2" seed="$3" prompt="$4"
  log "launching $tag (seed $seed): $prompt"
  "$RUNNERS/launch_detached.sh" "$prompt" "$OUT/$tag/gen_raw.ply" "$seed"
  log "$tag rc=$? ($(ls -la "$OUT/$tag/gen_raw.ply" 2>/dev/null | awk '{print $5}') bytes)"
  archive "$arch"
}

log "queue2 start — spatial-prompting experiment"
wait_for_idle

run_one ctrlroom 12.ctrlroom 0 \
  "an empty rectangular room with white walls, a flat ceiling and a wooden floor, one wooden chair in the middle"

run_one bedroomdim 13.bedroomdim 0 \
  "a rectangular bedroom 4 meters wide and 5 meters long with a flat 2.7 meter ceiling, a double bed against the far wall, a nightstand on each side, a wardrobe on the right wall, clear floor in the middle"

run_one livingspatial 14.livingspatial 0 \
  "a rectangular living room with a flat ceiling, a grey sofa against the left wall facing a television on the opposite wall, a low coffee table in the center on a rug"

run_one bedroom_s1 15.bedroom_s1 1 \
  "a bedroom with a bed, a nightstand and a wardrobe"

log "queue2 done"
