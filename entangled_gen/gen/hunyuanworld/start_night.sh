#!/bin/bash
# start_night.sh — single entry point for the 2026-07-06 night jobs.
# Launched by ONE hidden persistent wsl.exe on the Windows side (survives the
# Claude session; killed only by wsl --shutdown / reboot). No quoting games:
# zero arguments, absolute paths. `wait` keeps this process (and the WSL
# session) alive for the whole night.
GEN=/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/entangled_gen/gen/hunyuanworld
bash "$GEN/overnight_hw1.sh"    > /root/overnight_hw1_launcher.log 2>&1 &
bash "$GEN/prepare_scenegen.sh" > /root/prep_scenegen.log          2>&1 &
bash "$GEN/follow_playroom.sh"  > /root/follow_playroom.log        2>&1 &
wait
