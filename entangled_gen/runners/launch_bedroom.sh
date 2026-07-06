#!/bin/bash
# Furniture-validation run (2026-07-04): does the generator produce floor-standing
# furniture with sane geometry, and how bad are its occlusion shadows?
# Same wrapper pattern as launch_playroom.sh.
cd /mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/runners || exit 1
exec ./launch_detached.sh "a bedroom with a bed, a nightstand and a wardrobe" /mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out/bedroom/gen_raw.ply 0
