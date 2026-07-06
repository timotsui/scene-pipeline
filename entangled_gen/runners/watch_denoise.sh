#!/bin/bash
# watch_denoise.sh — exit when denoise passes 0% (freeze point cleared) or run ends
LOG=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out/run.log
MEM=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out/mem.log
for i in $(seq 1 540); do
  NEW=$(tail -c 200000 "$LOG" | tr '\r' '\n')
  if echo "$NEW" | grep -qE '=== STATUS rc='; then
    echo 'RUN ENDED:'
    echo "$NEW" | grep -vE '^\s*$' | tail -25
    exit 0
  fi
  if echo "$NEW" | grep -qE 'Predicting DataLoader 0: +[1-9][0-9]?%'; then
    echo 'PASSED FREEZE POINT — denoise progressing:'
    echo "$NEW" | grep -E 'Predicting DataLoader 0:' | tail -3
    echo '--- recent VRAM ---'
    tail -5 "$MEM"
    exit 0
  fi
  sleep 1
done
echo 'TIMEOUT after 9 min — still at:'
tail -c 3000 "$LOG" | tr '\r' '\n' | grep -vE '^\s*$' | tail -6
tail -5 "$MEM"
