# entangled_gen — swappable text→splat front-end for OVM

> **Layout note (2026-07-05):** `out/` was reorganized into one folder per scene
> (`out/<scene>/gen_raw.ply`, `views/`, `seg/`, `package/`, `scene_manifest.json`, …).
> All scripts resolve paths via `paths.py`; see `out/README.md` for the map.
> Older path mentions below (e.g. `out/gen_playroom_raw.ply`) are historical.

Isolated module that produces an **entangled** scene (a single fused 3D Gaussian
splat of a room, no addressable object handles) from a **text prompt**, to serve
as the *generated* input source for the extraction→placement pipeline in
`week5/splat_to_placement/`.

This is the "generator = swappable front-end adapter" from the OVM direction memo:
nothing downstream knows *which* generator produced the splat. The only contract
is the adapter output (see `adapter.py`).

## Why these two candidates (2026-07 search)

The 2025–26 text→3D-scene landscape is dominated by **compositional** generators
(WorldGen, GALA3D, SceneWeaver, SPATIALGEN) that already emit object handles /
layout structure. Those are the *wrong camp* for us — they sit on the
output/backend side of our axis and are better treated as related work.

We want a **fused room from text with no handles** = the **panorama→3DGS**
sub-family. The two most on-thesis, code-available picks:

| Candidate | Pipeline | Output | Weights | Integration |
|-----------|----------|--------|---------|-------------|
| **SceneDreamer360** (arXiv 2408.13711) | PanFusion panorama → 3-stage enhance → point-cloud-fusion 3DGS | real 3DGS `.ply` | PanFusion ckpt on **OneDrive** (ok) + enhancer on **Baidu** (`w2vr`) | one conda env, one command — **preferred first target** |
| **FastScene** (IJCAI 2024) | Diffusion360 panorama → PNVI/CVS inpaint → OpenMVG MVP → vanilla 3DGS | real 3DGS `.ply` | **all Baidu** (`7777`) | glue 3 repos + OpenMVG, no single env — higher friction |

Both bounded-room, text-driven, emit a gaussian `.ply` that drops into
`splat_to_placement`. SceneDreamer360 is the more cohesive run.

## Adapter contract (stable interface)

`adapter.generate(prompt: str, out_ply: Path, backend: str) -> Path`

Produces a 3DGS `.ply` at `out_ply`, **canonicalized** to the convention
`splat_to_placement` expects (see the coord-convention note below). Downstream
code imports only this; swapping backend = changing one arg.

## Coord-convention note (OPEN — same calibration gotcha as week5)

These repos emit **standard 3DGS** ply. `splat_to_placement` was calibrated on
PlayCanvas/SuperSplat exports (Y-up) and InteriorGS (Z-up), and week5 already hit
the `splat-transform` Y-up vs 3DGS Y-down transform issue. So the adapter MUST
run the same calibration (`splat-transform <ply> --summary`, then map to the
pipeline's frame) before handing off. Do NOT assume the axis convention matches —
this is a TODO in `adapter.py`, verified per-backend on the first real output.

## Environment (WSL Ubuntu-24.04)

- GPU passthrough works (RTX 4080 Laptop, 12 GB). VRAM is tight but OK at inference.
- miniconda at `/root/miniconda3` (conda 26.3.2). Had to `conda tos accept` the
  default channels first (new conda ToS gate) — done.
- The `panfusion` env pins **torch 2.0.1 / CUDA 11.7** (xformers 0.0.22, py3.9).
- **CUDA arch gotcha:** the 4080 is Ada (sm_89), but **CUDA 11.7 nvcc only goes to
  sm_87**. So compile the rasterizers with `TORCH_CUDA_ARCH_LIST="8.6+PTX"` (sm_86
  cubin + PTX that JIT-upgrades to sm_89 at runtime), OR install nvcc 11.8 which
  supports sm_89 directly. Also need a host compiler gcc <= 11 (WSL has gcc 13.3,
  too new for 11.7), so pull `gxx_linux-64=11` into the env.

## How to run (once env + weights are ready)

`python adapter.py "a cozy playroom with a rug and shelves" out/room.ply --backend scenedreamer360`

which shells into `runners/run_scenedreamer360.sh` (sets `config.json`, runs
`run.py`, copies `gsplat.ply` out). See that script's NOTES for the repo's rough
edges (commented `cli.run()`, enhancement bypassed, `../logs` path inconsistency)
to resolve on the first real run.

## Repo patches applied (all in `repos/SceneDreamer360`, see `git diff`)

The repo was in a rough research state with hardcoded/gated/broken deps. Fixes:

| File | Patch | Why |
|------|-------|-----|
| `main.py` | commented `from Enhance_img import ...` + its instantiation | enhancement is bypassed downstream; import pulls Baidu model path + basicsr |
| `main.py` | `../logs` -> `logs` in `result_dir` | logger writes to `logs/...`; read path was wrong |
| `PanoGenerator.py` | `stabilityai/stable-diffusion-2-base` -> `PeggyWang/stable-diffusion-2-base` | stabilityai repo is now **gated**; mirror is public, identical vae/text-enc/tokenizer/scheduler, has safetensors |
| `luciddreamer.py` | `runwayml/stable-diffusion-inpainting` -> `stable-diffusion-v1-5/stable-diffusion-inpainting`, drop `revision='fp16'` | runwayml org removed from HF (404) |
| `luciddreamer.py` | ZoeDepth path from `__file__` instead of `/root/autodl-tmp/...` | authors' hardcoded AutoDL path |
| `main.py` | VRAM cap = (free-at-launch − 2 GiB), `set_per_process_memory_fraction` | turn driver-level VRAM exhaustion (machine freeze) into clean CUDA OOM; fraction-of-total caps can't fire because Windows/DWM holds ~1 GB of the card |
| `PanFusion.py` | CFG pair runs sequentially (2 half-batches), not one doubled batch | halves peak activation VRAM at ~2x denoise time; halves are independent batch elements |
| `PanFusion.py` | `init_noise` output cast to module dtype | fp32 noise (e2p warp) fed to fp16 UNets under `precision=16-true` |
| `PanoGenerator.py` | `add_lora` uses `LoRAXFormersAttnProcessor` (was `LoRAAttnProcessor`) | **the machine-freeze root cause**: LoRA setup silently replaced the xformers attn processors → vanilla O(n²) attention → multi-GB single-burst alloc at first denoise step (pano 8192 tokens + 20 views in one batch); no cap can catch it before WDDM hard-freezes. Same `to_*_lora` attrs, ckpt loads unchanged |
| `PanoGenerator.py` | `decode_latent` upcasts VAE to fp32 for decode (restores dtype after) + NaN probes on latents/pixels | **the all-black-output cause** (run 5, 16:23): SD2's VAE overflows in fp16 → NaN → black frames; `precision=16-true` had cast it to fp16. Probes distinguish UNet-side vs VAE-side blowups in run.log |
| `main.py` | `[timing] <stage> wall=… elapsed=…` markers at each stage boundary | per-stage generation times in run.log (predict / multiview / LD load / LD create / render). NB: current numbers are at locked 1500 MHz clocks |
| `PanFusion.py` + `PanoGenerator.py` + runner | **04f: `bf16-true`, not `16-true`** (runner flag); `on_predict_start` derives half dtype from trainer precision; `init_noise` + `WarpAttn` masks/coords pinned fp32 (torch 2.0.1 has no bf16 `grid_sampler_2d_cuda`); `tensor_to_image` casts fp32 before `.numpy()` (numpy has no bf16) | **the REAL black-output cause** (run 6b, 18:0x 2026-07-04): SD2's UNet overflows to NaN in fp16 — latents were NaN BEFORE the VAE, so the 04d fp32-decode fix (kept, still correct defensively) was aimed at the wrong stage. bf16 = fp16 memory + fp32 exponent range. Run 6e: first non-black pano |
| `run_scenedreamer360.sh` | **04e: `rm -rf` the predict output dir pre-run** | `inference_and_save` early-returns if `<outdir>/prompt.txt` exists → every run after run 5 silently REUSED run 5's stale black pano and skipped denoising entirely (tell: `Predicting DataLoader 0: ... 42 it/s` = instant). The runbook's "next run overwrites them" assumption was wrong |

Runner-side (not repo): `run_scenedreamer360.sh` predicts with `--trainer.precision=16-true`
(~3.4 GB weight saving); `launch_detached.sh` samples RAM/VRAM at 1 s.

**⚠️ Before any GPU run: NVIDIA Control Panel → Manage 3D Settings → Global →
"CUDA - Sysmem Fallback Policy" → "Prefer No Sysmem Fallback".** Driver-level
seatbelt (applies to WSL too): overruns become clean OOMs instead of WDDM
sysmem-paging machine freezes. Set manually once per driver install — three hard
freezes on 2026-07-04 (02:17, 02:39, 15:28) before this was in place.

**⚠️ ALSO cap GPU power before any run (crash #4, 2026-07-04 15:43):** with the
xformers fix in place the run finally did real denoise compute — and ~25 s of
sustained full GPU load spontaneously hard-reset the machine (Kernel-Power 41,
BugcheckCode 0, no WHEA, auto-reboot in ~14 s = EC/power-delivery trip, NOT a
memory freeze; VRAM was only ~6.0/12.3 GB). Dynamic boost runs the card at
~159 W (default 150, max 175). Before relaunch, from an **admin** Windows
shell: `nvidia-smi -lgc 300,1500` (lock clocks; applies to WSL CUDA) and try
`nvidia-smi -pl 100` (may be unsupported on laptop). Slower denoise beats a
fifth power cycle. Undo with `nvidia-smi -rgc`.

Extra env deps installed into `panfusion` (torch-safe, `--no-deps` where needed):
open3d+dash+scikit-learn+addict+pyquaternion+pandas, plyfile, timm==0.6.7, peft,
realesrgan, diffusers==0.26.0, imageio, opencv, gradio.

**PanFusion checkpoint (`last.ckpt`, 9.2 GB):** the OneDrive share IS fetchable
headless via the guest-cookie + `download.aspx?share=<id>` flow (see
`runners/` download logic) — no manual step needed after all. The Baidu enhancer
is NOT needed (bypassed).

## Status

- [x] Both repos cloned; module scaffold + adapter + runner
- [x] WSL miniconda + `panfusion` env (torch 2.0.1+cu117)
- [x] Compiled `depth-diff-gaussian-rasterization-min` + `simple-knn` (gcc-11, sm_86+PTX)
- [x] All pipeline modules import; all model sources resolved to public/working repos
- [x] PanFusion `last.ckpt` downloaded + stripped (8.26 GB)
- [x] All 3 crash classes solved (VRAM burst → 04c xformers fix; EC power trip →
      1500 MHz clock lock; fp16-VAE black frames → 04d fp32 decode)
- [x] Run 5 (2026-07-04 16:23): machine survived end of denoise + 32 min of pipeline —
      killed manually (black output, pre-04d)
- [x] Black-output ROOT CAUSE found + fixed (runs 6a–6e, 2026-07-04 17:42–18:06):
      04e stale-guard skip (runs weren't denoising at all) + 04f SD2-UNet fp16 NaN →
      bf16-true. Run 6e: **first real pano** (74 KB cozy playroom, correct geometry)
- [x] Two 3DGS-stage OOMs fixed: run 6e died at Scene init (13M-pt cloud + 6.7 GB of
      dead inpaint models → 04g: free models + subsample to 3M + **traindata pickle
      cache**); run 7 died mid-training (densification growth → 04h:
      `ENTANGLED_DENSIFY_UNTIL=0`; dense depth-projected init doesn't need it)
- [x] **FIRST END-TO-END `.ply` — run 8, 2026-07-04 20:21, rc=0.**
      `out/gen_playroom_raw.ply` (744 MB, 3M gaussians, standard 3DGS attrs).
      Cache resume made run 8 launch→train in 4.5 min. Training (2990 iters,
      no densify) ≈ 5.5 min @1500 MHz. Known cosmetic wart: `render_video`
      dies in `imageio.mimwrite` (1440 frames @60fps held in RAM ≈ 24 GB) —
      the runner correctly returns rc=0 anyway since gsplat.ply exists.
- [x] **QUALITY GATE PASSED (2026-07-04):** 4 GPU views (week5 `shot.py --ply`, i.e.
      splat-transform) are photorealistic — shelves/toys, window w/ trees, rug.
      Output renamed `gen_playroom_raw.ply` (vs week5's REAL playroom.ply).
      NB: week5's numpy `03_render.py` RGB is misleading (disc approx → speckle);
      splat-transform for RGB, numpy renderer for depth/unproject only.
      Known artifacts: black no-gaussian disocclusion holes; slight depth-warp wall
      curvature. Scene already Y-up, floor y≈−1.6, ceil y≈+1.45, ~metric scale.
- [x] **DEPTH-LIFT + MANIFEST (2026-07-05 ~00:00):** `lift_views.py` — vectorized
      point z-buffer depth at the shot.py sidecar cameras + median/IQR mask trim +
      label/IoU3D cross-view merge → `out/scene_manifest_playroom.json` (19 objects,
      geometrically sane) + ID-annotated box overlays in the photoreal views
      (`out/seg/manifest_overlay_*.png` — the verification artifact; plan views are
      not useful for judging).
- [x] **COMPOSITION PACKAGE + FULL-LOOP DEMO (2026-07-05):** `agent_package.py` →
      `out/package_<scene>/` (GUIDE.md: frame + object table + ASCII floor-occupancy
      grid + OUTPUT CONTRACT; geometry in JSON, images for grounding only) and
      `render_proposal.py` (numeric constraint check + proposal renders). Playroom
      demo: LLM composed 4 placements from the package alone — ALL CONSTRAINTS PASS.
- [ ] Overnight 2026-07-05 (~2:30 AM): post_queue.ps1 extracts bedroom/livingroom/
      kitchen; then repeat package+compose on bedroom  ← IN FLIGHT
- [ ] Coord calibration (`_canonicalize` in adapter.py) — fold into step 2 above
- [ ] Coord calibration (`_canonicalize` in adapter.py) once we have a real `.ply`

Fallback (revised 2026-07-04 re-survey): **LayerPano3D (SIGGRAPH 2025, 3DTopia) is now
the #1 fallback**, demoting FastScene. It's the quality leader of the pano→3DGS family
(layered-depth decomposition handles occlusions; maintained repo; torch 2.4) — but
FLUX-based pano generation (12B) is painful on 12 GB (CPU offload + VAE tiling exist),
and the multi-stage layer/inpaint pipeline is a new infra project. DreamScene360
(ECCV 2024) checked and rejected: lateral move (same era/limitations, scattered
weights, optional GPT-4V dep). FastScene demoted to #2 (all-Baidu weights, 3-repo
glue). Decision point unchanged: switch only if SceneDreamer360 fails *structurally*
(unusable splat quality / broken geometry), not on infra bugs.

## Runbook — next run (written 2026-07-04, after run 5)

**1. Pre-flight (every session):**
- Clock lock (CRITICAL — resets on every reboot; unlocked full load hard-kills the
  machine, see crash #4): re-apply from an elevated shell: `nvidia-smi -lgc 300,1500`
  (undo: `-rgc`. From Claude: `Start-Process cmd '/c nvidia-smi -lgc 300,1500 > %TEMP%\out.txt' -Verb RunAs -Wait`
  + user clicks UAC, then read the file). NB (learned 2026-07-04): `clocks.max.gr`
  always reports the hardware max (3105) regardless of the lock — the ONLY
  confirmation is the command's own `GPU clocks set to ...` output. When in doubt
  just re-apply; it's idempotent.
- NVCP "CUDA - Sysmem Fallback Policy = Prefer No Sysmem Fallback": persists per driver
  install; re-check only after driver updates.
- OEM 330 W adapter plugged in; GPU otherwise idle (`nvidia-smi` VRAM < ~500 MB).

**2. Launch (from Windows/PowerShell — do NOT use `wsl -- bash -c` + setsid, it dies
with the session):**
```powershell
Start-Process -FilePath wsl.exe -ArgumentList '-d','Ubuntu-24.04','--','bash',
  '/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/runners/launch_playroom.sh' `
  -WindowStyle Hidden
```
(`launch_playroom.sh` hardcodes prompt/out-ply/seed; edit it for a different prompt.)
Logs: `out/run.log` (stages, `[timing]` markers) + `out/mem.log` (1 s RAM/VRAM samples).

**3. Expected timeline (at locked 1500 MHz; from runs 4–5):**
| t | stage | signal in run.log |
|---|-------|-------------------|
| 0–2 min | ckpt load (18 GB RAM spike — normal) | `Loaded model weights` |
| ~2–4 min | PanFusion denoise (the old killer stage; 1:44) | `Predicting DataLoader 0: 100%` then `[timing] panfusion_predict_done` |
| **~4 min** | **CHECK: open `logs/4142dlo4/predict/e9zR4mvMWw7_test/pano.jpg` — must be a real room, NOT black.** If black: kill run, read the `[entangled_gen] WARNING: NaN...` probe lines (UNet-side vs VAE-side) | `prompt:...` |
| ~5 min | 30-view projection | `[timing] multiview_projection_done` |
| +45 s (first run only) | ZoeDepth download (1.34 GB) | tqdm download bar |
| 20–40+ min | QUIET CPU phase (14-core burst → ~1.6-core serial Python). Normal — GIL-bound research code. Not stalled unless CPU ≈ 0 AND log frozen | (silence) |
| ? (untested) | LucidDreamer inpaint + 3DGS opt (GPU bursts return) | `[timing] luciddreamer_*` |
| end | export + copy | `OK copied ... gen_playroom_raw.ply` + `=== STATUS rc=0 ===` |

**4. Success = `out/gen_playroom_raw.ply` exists + rc=0.** Then: view it (week5 render
tools), run coord calibration (`splat-transform <ply> --summary`, Y-up gotcha), wire
`_canonicalize`, feed to `splat_to_placement`. If quality is good, later runs can step
clocks up (`-lgc 300,2000`, then higher) to find the safe ceiling.

**5. Stale state note (RESOLVED by 04e):** the predict dir is now `rm -rf`'d by the
runner before every run — `inference_and_save` early-returns (silently skipping ALL
denoising) if `prompt.txt` survives from a previous run, which is what made runs 6a
and earlier "reuse" run 5's black pano. Every file in the predict dir is now
guaranteed fresh per run.
