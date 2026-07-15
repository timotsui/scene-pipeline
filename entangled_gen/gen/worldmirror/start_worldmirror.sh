#!/bin/bash
# start_worldmirror.sh — zero-arg entry (one hidden persistent wsl.exe,
# foreground, scenes hardcoded per one-scene-per-pipeline).
GEN=/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/entangled_gen/gen/worldmirror
bash "$GEN/run_worldmirror.sh" bedroom_hw1 bedroom_hw2 > /root/worldmirror_launcher.log 2>&1
