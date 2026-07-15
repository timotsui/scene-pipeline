# gen method: HunyuanWorld 1.0 Lite  (backend tag: hw1)

Stage-1 (generate) implementation: prompt → FLUX.1-dev + PanoDiT-Text LoRA →
960×1920 equirect panorama → (scenegen stage) semantic layering (ZIM) +
layer depth → layered 3D mesh world → sampled-point ply for the lift.

Eval-plan context: Experiment 1 of GEN_BACKEND_EVAL_PLAN.md (docs/). Timeboxed:
FP8 Lite is stated ~17 GB VRAM vs our 12 GB 4080 Laptop; pano stage is the
must-have (it feeds Experiment 2 / SPAG4d), full scenegen is the bonus.

## Isolation (mirrors gen/scenedreamer360)

- External repo clone is NOT in git — lives in the local data area:
  `CS-8903-OVM/week7/entangled_gen/repos/HunyuanWorld-1.0` (shallow clone,
  2026-07-05), runs under WSL Ubuntu-24.04.
- Own conda env `HunyuanWorld` (python 3.10, torch 2.5.0+cu124) at
  /root/miniconda3 — fully separate from `panfusion` (SceneDreamer360).
- HF weights go to the default WSL cache `/root/.cache/huggingface` (WSL vhdx
  on C:, ext4 = fast loads). Per-repo subfolders keep backends separable.
- Scene outputs: `out/<scene>_hw1/` via paths.py (free-form scene names, no
  code change). Pano stage writes `panorama.png` into the scene dir — exactly
  paths.panorama().

## Weights (per stage)

| Weight | Size | Gated? | Needed for |
|---|---|---|---|
| tencent/HunyuanWorld-1 (PanoDiT/PanoInpaint subfolders) | ~1.5 GB | no | all stages |
| black-forest-labs/FLUX.1-dev | ~24 GB | YES — accept license on HF | pano stage (1.2) |
| black-forest-labs/FLUX.1-Fill-dev | ~24 GB | YES — accept license on HF | scenegen layer inpaint (1.3) + image-conditioning (1.5) |

Gated repos need `huggingface-cli login` with the USER's token after accepting
both licenses at huggingface.co (model pages → "Agree and access").

## VRAM strategy (12 GB)

demo_panogen.py stock already does `enable_model_cpu_offload()` +
`enable_vae_tiling()`. Plan: run with `--fp8_gemm --fp8_attention` (12B Flux
transformer → ~12 GB) and hope model-level offload squeezes under; if OOM, the
one-line fallback is patching `enable_model_cpu_offload` →
`enable_sequential_cpu_offload` (leaf-level streaming, <4 GB, much slower —
fine for eval). Patches to the repo clone get documented here like
scenedreamer360's were.

## Scripts (working templates, absolute paths from this setup)

- `setup_env.sh` — the install steps actually run (clone, conda env,
  weight downloads); scenegen extras (Real-ESRGAN, ZIM, draco) staged but NOT
  installed yet — demo_panogen.py doesn't import them (verified), they're
  scenegen-only. Install when 1.3 starts.
- `download_weights.sh` — public HunyuanWorld weights + the gated FLUX pulls
  (run after HF login).
- `run_panogen.sh <prompt> <scene> [seed]` — pano stage only (step 1.2);
  writes OUT/<scene>/panorama.png. Baseline prompts use seed 0.
- scenegen run script: TO BE WRITTEN at step 1.3 (after pano approved).

## Status

- 2026-07-05: clone done; conda env building; FLUX gated-license step waiting
  on user. Nothing generated yet.
- 2026-07-05 late: env verified (4 fixes, see setup_env.sh); HunyuanWorld-1 +
  FLUX.1-dev weights pulled; overnight queue armed (overnight_hw1.sh: panos →
  scenegen lookahead; prepare_scenegen.sh concurrent). Machine guards:
  .wslconfig swap 16 GB, resource sampler, Windows deadman watchdog.
