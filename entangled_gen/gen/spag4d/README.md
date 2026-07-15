# gen method: SPAG4d  (backend tag: spag)

Stage-1 (generate) implementation for Experiment 2 of GEN_BACKEND_EVAL_PLAN.md:
equirect panorama → 360° depth (DAP metric / DA360 disparity) → spherical
depth-to-Gaussian projection → 3DGS ply, in seconds. Philosophy: the pano is
selected FIRST (user gate), only the keeper gets lifted.

## Isolation (mirrors gen/scenedreamer360 + gen/hunyuanworld)

- Repo clone NOT in git: `CS-8903-OVM/week7/entangled_gen/repos/SPAG4d`
  (shallow, 2026-07-05). Upstream is Windows-portable-first but documents a
  pip route; we use a dedicated WSL conda env `spag4d` (python 3.11) to stay
  consistent with the other backends. Nothing system-wide.
- Model weights cache: `~/.cache/spag4d/` (WSL) — DAP ~1.5 GB, DA360 ~1.3 GB.
- Depth backends: DAP (metric, default) and DA360. The optional PaGeR backend
  is CC BY-NC and outdoor-oriented — skipped. SHARP refine / ArtiFixer3D
  refine — skipped (out of eval scope).
- Panos in: `out/<scene>_hw1/panorama.png` (HW1 pano stage) or any 2:1
  equirect. Splats out: `out/<scene>_spag/gen_raw.ply` via paths.py naming.

## Scripts

- `setup_env.sh` — conda env + pip deps + arch submodule clones + weight
  download (idempotent).
- `run_spag.sh <pano_path> <scene> [--depth-model da360] [--stride N]` — one
  conversion → OUT/<scene>/gen_raw.ply. Stride 1 = ~1.3M splats (max), 2 =
  default. Try DAP first (metric depth suits indoor scale checks).

## Status

- 2026-07-05: cloned only; env/weights not yet installed (queued behind the
  HW1 overnight GPU work — network shared, GPU serial).
