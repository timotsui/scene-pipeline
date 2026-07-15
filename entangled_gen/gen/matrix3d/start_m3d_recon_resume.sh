#!/bin/bash
# start_m3d_recon_resume.sh — zero-arg entry for the SR-bypass recon resume
# (one hidden persistent wsl.exe, foreground, scene hardcoded).
GEN=/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/entangled_gen/gen/matrix3d
bash "$GEN/run_m3d_recon_resume.sh" bedroom_hw1 > /root/m3d_recon_resume_launcher.log 2>&1
