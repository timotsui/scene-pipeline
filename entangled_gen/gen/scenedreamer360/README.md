# gen method: SceneDreamer360

Stage-1 (generate) implementation: prompt → PanFusion panorama → 30 perspective
crops → per-crop ZoeDepth + greedy scalar-scale merge → 13M-pt cloud → 150
training renders → 3DGS (densify off) → `gen_raw.ply` (3M gaussians).

The external repo clone (~17 GB, incl. weights) is NOT in git — it lives in the
local data area (`CS-8903-OVM/week7/entangled_gen/repos/SceneDreamer360`) and
runs under WSL on the RTX 4080.

These scripts are the launch/queue harness from the 2026-07-03..05 runs. They
contain ABSOLUTE paths from that setup — treat them as working templates for
the next batch, not push-button tools:

- `run_scenedreamer360.sh` — single scene generation
- `overnight_queue*.sh` — multi-scene WSL queue (logs to OUT/logs/queue.log)
- `post_queue*.ps1` — Windows watcher: after "queue done", runs stages 2–4
  (render → segment → lift) per scene on the freed GPU
- `launch_*.sh`, `launch_detached.sh`, `watch_denoise.sh`,
  `compile_rasterizers.sh` — setup/one-off helpers

Known method quirks (documented 2026-07-05): pano enhance step bypassed; poles
beyond ±55° elevation never directly sampled; per-crop monocular depth with
scalar-only alignment is the inherited LucidDreamer machinery (geometry warp is
the METHOD's fault); horizontal ring sweeps opposite to the tilted rings
(upstream sin sign flip, harmless). Untested alternative for the depth part:
pano-native depth models (Panoformer/EGFormer, sitting in repos/FastScene).
