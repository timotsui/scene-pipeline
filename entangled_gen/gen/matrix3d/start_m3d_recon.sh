#!/bin/bash
# start_m3d_recon.sh — zero-argument entry point for the guarded m3d recon
# stage (same pattern as start_m3d_video.sh: launched by ONE hidden
# persistent wsl.exe, no quoting games, absolute paths, foreground so the
# VM stays alive). Scene hardcoded per the one-scene-per-pipeline policy.
GEN=/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/entangled_gen/gen/matrix3d
bash "$GEN/run_m3d_recon.sh" bedroom_hw1 > /root/m3d_recon_launcher.log 2>&1
