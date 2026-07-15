#!/bin/bash
# start_m3d_video.sh — zero-argument entry point for the guarded m3d video
# retry (same pattern as hunyuanworld/start_night.sh: launched by ONE hidden
# persistent wsl.exe, no quoting games, absolute paths). Runs in the
# foreground so the wsl.exe session — and with it the VM — stays alive for
# the whole run. Scene hardcoded per the one-scene-per-pipeline policy.
GEN=/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/entangled_gen/gen/matrix3d
bash "$GEN/run_m3d_video.sh" bedroom_hw1 > /root/m3d_video_launcher.log 2>&1
