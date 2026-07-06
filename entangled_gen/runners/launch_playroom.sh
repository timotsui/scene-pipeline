#!/bin/bash
# One-argument wrapper so the run can be launched from Windows via a detached
# hidden wsl.exe (Start-Process mangles multi-word arguments, and a setsid
# launch from a transient `wsl -- bash -c` dies with the WSL session).
cd /mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/runners || exit 1
exec ./launch_detached.sh "a cozy playroom with a rug and shelves" /mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out/playroom/gen_raw.ply 0
