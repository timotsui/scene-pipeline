# Gen-backend evaluation plan (2026-07-05)

> Living document. Update the Status column as we go; sessions are expected to
> end mid-plan. Read SESSION_2026-07-05C_HANDOFF.md for the frame-resolution
> context this builds on.

## Decision & goal

**SceneDreamer360 is dropped as the primary backend.** Its weak results are
method-level (single panorama + estimated depth → hard quality ceiling), not a
setup problem. We evaluate 5 replacement backends, one by one, 1–2 scenes each.

**Evaluation criterion — the composition field, not splat prettiness:**
does the generated world give useful *object regions + relative depth +
approximate poses + support relationships + free space*? A messy splat with a
strong composition wins over a beautiful flythrough with inconsistent object
positions.

## Ground rules

- USER evaluates all visuals (viewer, overlays, panos). Claude prepares
  artifacts + numbers only, never concludes from images.
- Plan-first: each ▶ step is proposed to the user before execution; each
  ⛔ CHECKPOINT blocks until the user has looked and said continue.
- Hardware: RTX 4080 Laptop, 12 GB VRAM, WSL Ubuntu-24.04. Disk-check before
  every weight download (Flux / Matrix-3D weights are tens of GB).
- Evaluation stops at manifest + viewer boxes. Envelopes / agent packages /
  report are still blocked on the stale up=−y code (see handoff §STALE CODE) —
  fixing those is a separate task, not part of this plan.

## Common scaffolding (once, before experiment 1)

| # | Step | Status |
|---|------|--------|
| S1 | Fix the two eval prompts (reuse bedroom + playroom prompts from the 2026-07-04 gen queue so results compare against the SceneDreamer360 baselines) | DONE 07-05: bedroom = "a bedroom with a bed, a nightstand and a wardrobe", playroom = "a cozy playroom with a rug and shelves", seed 0 |
| S2 | Scene naming: `out/<scene>_<backend>/` — backends: `hw1`, `spag`, `m3d`, `hw2`, `marble`; via paths.py, nothing downstream changes | DONE 07-05: paths.py scene names are free-form — zero code change needed |
| S3 | Eval kit checklist doc (below) confirmed by user | DONE 07-05: user go-ahead with the 1.1 plan |

**Eval kit per scene (identical for every backend):**
1. Backend output → adapter → `gen_raw.ply` (mesh backends: sample to colored
   point ply).
2. `render_views.py` → RGB views  →  ⛔ user glances: is the scene itself worth
   lifting? (reject here = cheapest rejection point)
3. `seg_views.py` + `lift_views.py` (auto 4-hypothesis frame calibration) →
   manifest + overlay PNGs.
4. Viewer scene with manifest boxes.
5. ⛔ CHECKPOINT: user judges composition field in viewer + overlays.

## Experiment 1 — HunyuanWorld 1.0 Lite  [Status: panos DONE (pending user eyes); scenegen NOT VIABLE LOCALLY → decision 1.4 open]

Text/image → panorama (Flux) → semantic layering → layered 3D mesh world.
Known risk: FP8 Lite is stated ~17 GB VRAM vs our 12 GB; staged execution +
CPU offload may still work. **Timebox: one working session** for install +
first pano.

| # | Step | Gate |
|---|------|------|
| 1.1 | Disk check; clone + conda env in WSL; download quantized weights | ▶ plan shown first |
| 1.2 | Text→panorama stage alone, bedroom prompt | ⛔ user views pano |
| 1.3 | Full pipeline (layering + mesh) on the approved pano; watch VRAM | — |
| 1.4 | If OOM despite offload → **decision point**: (a) rent 4090 now, or (b) park, continue to Exp 2, batch one cloud rental later covering Exp 1 + Exp 4 (Claude's lean: b) | ⛔ user decides |
| 1.5 | Mesh → sampled-point ply adapter; run eval kit (both scenes; also try image-conditioning on one) | ⛔ eval-kit checkpoints |
| 1.6 | Export per-layer FG meshes — keep as potential lift-accuracy oracle | — |

## Experiment 2 — strong panorama → SPAG4d  [Status: TODO]

github.com/cedarconnor/SPAG4d (verified real, active 2026-06). Equirect pano →
3DGS ply in seconds, 2–12 GB depending on depth backend. Philosophy: generate/
select the best pano FIRST (reject bad compositions cheaply), lift only the
keeper. May overlap Exp 1's downloads.

| # | Step | Gate |
|---|------|------|
| 2.1 | Pano source: HW1.0 pano stage if Exp 1 reached 1.2, else a strong text→pano generator; produce 2–3 candidate panos per prompt | ⛔ user picks/rejects panos |
| 2.2 | Install SPAG4d; lift chosen panos (indoor-appropriate depth backend; note which backends we used) | ▶ plan shown first |
| 2.3 | Eval kit on both scenes | ⛔ eval-kit checkpoints |

## Experiment 3 — Matrix-3D (5B, low-VRAM, optimization recon)  [Status: COMPLETE 07-07 06:24 — bedroom_m3d splat + eval kit (SR bypassed, see log); pending user eyes]

SkyworkAI/Matrix-3D, MIT. Text/image → pano video (camera MOVES → real
parallax) → 3DGS. Config: 5B video model low-VRAM (~12 GB) + optimization-based
reconstruction (~10 GB); **skip PanoLRM**. Slow — video gen ~1 h on an A800,
so overnight-queue territory locally.

| # | Step | Gate |
|---|------|------|
| 3.1 | Disk check; install; VRAM smoke test of the 5B low-mem path | ▶ plan shown first |
| 3.2 | Overnight: video gen for bedroom prompt (or selected pano as input) | — |
| 3.3 | Optimization recon → ply; eval kit scene 1 | ⛔ eval-kit checkpoints |
| 3.4 | If worth it, queue scene 2 overnight | ⛔ user decides |

## Experiment 4 — HY World 2.0, own panorama  [Status: LOCAL LEG COMPLETE 07-07 ~11:00 — bedroom_hw2 via WorldMirror 2.0 (~5 GB weights, 61 s); 17B WorldStereo stage still rental; pending user eyes]

Tencent-Hunyuan/HY-World-2.0 (Apr 2026). **Skip the 80B pano stage** — feed our
best pano from Exp 1/2 into WorldStereo 2 (17B) → WorldMirror 2 → 3DGS.
17B ⇒ not local; hosted demo first, else the batched cloud rental from 1.4.

| # | Step | Gate |
|---|------|------|
| 4.1 | Recon: does Tencent's hosted demo accept own panos + export ply? | ▶ findings to user |
| 4.2 | Hosted route OR cloud rental (batched with Exp 1 if it OOM'd) | ⛔ user approves any rental/spend |
| 4.3 | Eval kit on both scenes | ⛔ eval-kit checkpoints |

## Experiment 5 — World Labs Marble (quality ceiling)  [Status: TODO]

Hosted, no install. Same two prompts; download splats; eval kit. Serves as the
"what good composition looks like" target + sanity check for the whole
decomposition idea. Account/credits = user's call.

| # | Step | Gate |
|---|------|------|
| 5.1 | User generates (or hands Claude access to generate) the two scenes; download plys | ⛔ user drives the hosted UI |
| 5.2 | Eval kit on both scenes | ⛔ eval-kit checkpoints |

## Final comparison  [Status: TODO]

Side-by-side per prompt: views grid + manifest stats (object count, box
plausibility) + user's composition-field verdicts → pick the pipeline's
default backend; losers documented as related-work data points.

## ACTIVE DAY PLAN 2026-07-06 (user-approved ~09:00; resume here if session dies)

1. [x] SPAG4d install DONE 07-06 + FIRST SPLAT + FULL EVAL KIT:
   `out/bedroom_spag/gen_raw.ply` (900K gaussians, 3.9 s, DAP metric depth
   0.5-2.9 m, stride 1) → 4 yaw renders → seg → lift: manifest 4 objects
   (bed/wardrobe/2 doors, metric-plausible sizes), calib rot180 0.942 (same
   convention as scenedreamer360), overlays + plan written, viewer scene
   prepped (viewer/data/bedroom_spag.bin), server on :8321.
   FIXES (in gen/spag4d/): repo CLI broken at HEAD (sharp_refine kwarg) →
   our spag_convert.py calls core API directly; DAP submodule blocked by
   stale GSFix3D gitlink → direct clone into spag4d/dap_arch/DAP.
   yaw270 skipped by lift (missing masks) — quality topic, user's eyes.
   ⛔ USER: judge pano + boxes: http://localhost:8321/?scene=bedroom_spag
2. [x] Exp 4.1 recon DONE 07-06: no public hosted demo found — the "demo" is
   a LOCAL gradio app (`python -m hyworld2.worldrecon.gradio_app`). Pipeline
   stages run independently. WorldMirror 2.0 (open weights, tencent/
   HY-World-2.0 on HF) takes PERSPECTIVE images/video + optional priors, NOT
   equirect panos; exports gaussians.ply + points.ply + COLMAP. WorldStereo
   2.0 (17B pano-native stage) = rental territory as planned. VIABLE OWN-PANO
   ADAPTATION: our pano → perspective crops (Perspective class in HW1 repo)
   → WorldMirror 2.0 → gaussians.ply. VRAM unstated (fsdp/bf16 flags hint
   big) — check HF weight size before attempting. USER DECIDES 4.2 route.
3. [x] Matrix-3D (Exp 3) INSTALL COMPLETE 07-06 (M3D_FIX3_OK: diffsynth +
   pytorch3d + nvdiffrast + simple_knn + both rasterizers). Our 12 GB
   config: OWN PANO input (their README supports it) → 5B video low-vram
   ~12 GB → optimization recon ~10 GB; text2pano + PanoLRM skipped.
   Wan2.2-TI2V-5B base (32 GB) downloaded. Install took 11 documented
   failure modes — see gen/matrix3d/fix_install*.sh + .wslconfig
   vmIdleTimeout note. run_m3d_video.sh written (own-pano prep + 5B flags).
   REMAINING: (a) [x] Skywork access granted 07-06, all weights down
   (M3D_WEIGHTS_OK); (b) [~] bedroom video RUN IN PROGRESS (take 5!) —
   runtime fixes, all in gen/matrix3d/: fix_utils3d.sh (vendored MoGe needs
   pre-rename utils3d — actually resolved by sys.path.insert(0) patch in
   vendored infer_panorama.py so its BUNDLED utils3d wins), opencv 5→4.11
   (EXR write removed in 5.x), CPATH/LIBRARY_PATH for conda cuda-toolkit
   targets/ headers (nvdiffrast JIT), fix_wan21_layout.sh (DiffSynth
   redirects T5/tokenizer to Wan2.1-T2V-1.3B id — hardlinked from the 2.2
   snapshot, dodging a 3 h modelscope re-download). Now denoising: VRAM
   6.2 GB, RAM 15+12 swap, guards armed; (c) recon script still to write.
4. [ ] After (1): `bash gen/spag4d/run_spag.sh <bedroom_hw1 pano> bedroom_spag`
   → gen_raw.ply (seconds, 2–12 GB VRAM, deadman armed) → eval kit stages
   render_views → seg_views → lift_views → viewer prep. User judges pano +
   boxes whenever ready (⛔ gates 2.1/2.3 still theirs).
Parked: Marble (user: skip), HW1 scenegen (decision 1.4 pending), playroom
lifts (one scene per pipeline until cross-backend comparison).

## Status log

- 2026-07-05: Plan created. Nothing executed yet.
- 2026-07-05 (later): S1–S3 done. Exp 1 step 1.1 executing: repo cloned to
  `repos/HunyuanWorld-1.0` (shallow); conda env `HunyuanWorld` building;
  harness at `gen/hunyuanworld/` (README + setup_env + download_weights +
  run_panogen, scenedreamer360-style isolation). Findings: demo_panogen.py
  stock has model-CPU-offload + VAE tiling; fp8 flags ≈ 12 GB transformer —
  sequential-offload patch is the OOM fallback. BLOCKER for 1.2: FLUX.1-dev
  (and later FLUX.1-Fill-dev) are gated — user must accept licenses + provide
  HF token. Scenegen extras (Real-ESRGAN/ZIM/draco) deferred to 1.3.
- 2026-07-05 (later still): 1.1 COMPLETE except gated weights. Env
  `HunyuanWorld` verified (torch 2.5.0, cuda True, hy3dworld imports OK) after
  4 repo-env fixes, all documented in gen/hunyuanworld/setup_env.sh: av repin,
  flash-attn dropped (never imported), basicsr→basicsr-fixed, realesrgan +
  zim-anything added --no-deps (hy3dworld.__init__ eagerly imports the whole
  scenegen chain — pano-only still needs them importable).
  tencent/HunyuanWorld-1 weights (1.1 GB) downloaded. WAITING ON USER:
  FLUX.1-dev license + HF token, then download_weights.sh → step 1.2.
- 2026-07-06 ~00:30 OVERNIGHT QUEUE ARMED (user asleep, pre-authorized
  depth-first-with-lookahead): HF login done (FLUX licenses accepted);
  FLUX.1-dev ~46/55 GB. Machine-safety hardening: .wslconfig swap 8→16 GB
  (LoRA-fuse RAM spike), resource sampler → out/logs/, Windows-side deadman
  watchdog (auto `wsl --shutdown` if Windows RAM <1.2 GB or WSL unresponsive
  ~2 min). Detached WSL jobs: (a) overnight_hw1.sh — finish FLUX → bedroom
  pano → playroom pano → scenegen lookahead on bedroom (fp8, classes=indoor,
  fg labels = first-guess in run_scenegen.sh); (b) prepare_scenegen.sh —
  Fill-dev + ZIM onnx + DINO-tiny + MoGe + onnxruntime-gpu. Logs:
  out/logs/overnight_hw1.log + *_resources.log, /root/prep_scenegen.log.
  SPAG4d (exp 2): cloned + harness written (gen/spag4d/), env install
  DEFERRED — permission classifier wants the user present for executing a
  new external repo. PANOS = PENDING USER EYES regardless of how far the
  pipeline ran ahead; scenegen mesh (if any) too.
- 2026-07-06 ~01:05: PREVENTION RE-WEIGHT (user: crash = machine stays off
  until physical button). Panos switched to SAFE MODE (sequential offload,
  bf16, no fp8; <1 GB VRAM; HW1_SEQ_OFFLOAD patch in repo demo_panogen.py);
  scenegen CUT from unattended hours. INCIDENT: deadman fired at Windows-
  free-RAM 946 MB during pano #1 → wsl --shutdown (machine saved, by
  design). Fix: .wslconfig memory 24→20 GB, swap 16→24 GB; relaunched.
  SCOPE CHANGE (user): one scene PER PIPELINE (bedroom first everywhere),
  second scenes only after cross-backend comparison — playroom_hw1 cut from
  tonight. Full details: SESSION_2026-07-06_OVERNIGHT_HANDOFF.md.
- 2026-07-06 ~01:40: BOTH PANOS DONE (bedroom 00:56, playroom ~01:25; safe
  mode ≈25 min each; PENDING USER EYES). User (awake, ~01:15) approved
  attended scenegen attempt on bedroom. Attempt #1: loaded BOTH Fill pipes
  (fp8 applied, seg started!) then OOM-killed mid-processing at rss 19.5 GB
  + swap 23.4/24 full ≈ 43 GB total — fits load, not processing. Guards
  held (clean cgroup kill, machine fine). Retry #2 with swap 24→40 GB
  (60 GB virtual) — running. mesh_to_splat.py adapter written + round-trip
  VERIFIED against rendertools load_splat (auto-runs after meshes).
- 2026-07-06 ~01:45: NIGHT CLOSED. Scenegen retry #2 triggered the deadman
  AGAIN (Windows free RAM 920 MB — the 40 GB swap thrash bloats Windows'
  own cache even with WSL capped at 20 GB). wsl --shutdown; machine safe;
  Windows recovered to 25 GB free. VERDICT (2 attempts, 2 clean saves):
  HunyuanWorld scenegen is NOT viable on this machine — 12 GB VRAM was
  never the binding constraint, 31 GB system RAM is. Decision 1.4 now has
  hard evidence; lean (b) park + batch one cloud rental with Exp 4 (17B).
  MORNING AGENDA: (1) user views bedroom_hw1 + playroom_hw1 panos;
  (2) user present → SPAG4d env install (15 min) + lift BOTH panos to
  splats (2-12 GB, well within local limits) → Exp 2 eval kit; (3) user
  calls decision 1.4. WSL left STOPPED deliberately.
- 2026-07-06 12:56 INCIDENT: m3d video (5B, vram_mgmt, 704x1408) on
  bedroom_hw1 HARD-FROZE the whole box mid-VAE-encode of the Wan diffusion
  stage; hard reset 14:25. No deadman was armed (it lived in the night
  session and died with it) and swap was still 40 GB from scenegen retry
  #2 — the exact thrash mode the 01:45 incident flagged. No memory trace
  (run had no resource sampler). Data point WITH the caveat: the freeze may
  be the 40 GB-swap config, not m3d itself — one guarded retry is justified
  before ruling local m3d video out. NO LIGHTER CONFIG EXISTS: 5B path is
  fixed 704x1408 (--resolution ignored); non-5B swaps in Wan2.1-I2V-14B
  (bigger + ~30 GB download). Prep done, LAUNCH PENDING USER GO:
  .wslconfig swap 40→24 GB (overrun = clean OOM-kill, not freeze); deadman
  saved as a FILE (tools/deadman.ps1: RAM<1.2 GB, WSL-unresponsive ~2 min,
  NEW sustained-swap>20 GB trip; probe doubles as VM keepalive); resource
  sampler added to run_m3d_video.sh; one-command guarded launcher
  tools/launch_m3d_video_guarded.ps1 (preflights swap=24, arms deadman,
  one hidden persistent wsl.exe → gen/matrix3d/start_m3d_video.sh).
- 2026-07-06 ~16:57 INCIDENT 2 (guarded retry): instant power-OFF at the
  start of the sustained VAE/denoise phase — deadman read "ok" 20 s before
  death (RAM/swap all below trips). ROOT CAUSE: EC power trip — the
  `nvidia-smi -lgc 300,1500` clock lock had reset at the 14:25 hard reboot
  and nothing re-applied it. FIX: launcher now applies the lock as
  preflight 0 (elevated required; fails loud without the "GPU clocks set
  to" confirmation). Lesson: deadman = RAM guard, clock lock = power
  guard; every run needs BOTH.
- 2026-07-06 23:13 **3.2 SUCCESS on retry 2** (launched 22:42 with both
  guards): 50/50 denoise steps (~22 min sustained GPU at 1500 MHz — the
  exact load that killed the box twice) + VAE decode 6/6 → pano_video.mp4
  + pano_video_cam.json in repos/Matrix-3D/output/bedroom_hw1/. Peak:
  VRAM 11.9/12 GB, RAM at 20 GB cap, swap ~13 GB. Machine never blinked.
  Video PENDING USER EYES. Ops note: the run's "OK video" marker lands in
  /root/m3d_video_launcher.log (WSL side), not out/logs — check the mp4 on
  disk. Windows gotcha: `tail -F` on a log a PowerShell process appends to
  BLOCKS the writer (orphaned tail.exe held deadman.log 22:42→23:15;
  watchdog ran fine, logging silently failed) — poll with brief opens.
  NEXT: 3.3 write + run the optimization-recon script (video → 3DGS ply,
  ~10 GB VRAM) → eval kit.
- 2026-07-07 OVERNIGHT (user asleep, pre-authorized "splat from each
  pipeline"): (a) m3d recon crashed 04:10 in StableSR — matrix3d env
  protobuf too old for tensorboard's runtime_version (via pytorch_lightning);
  geom optim + 108-frame mv extraction had SUCCEEDED. Resumed 04:12 with
  run_m3d_recon_resume.sh (StableSR BYPASSED, GS trains on original frames)
  → 06:24 bedroom_m3d/gen_raw.ply (11.2 M gaussians, 771 MB; GS 3000 iters
  took 2 h 11). Scene NOT metric (~24 units across). Eval kit done, calib
  rot180 0.646, 12 objects. (b) ~09:35 WSL VM wedged (HCS_E_CONNECTION_
  TIMEOUT; deadman probes falsely "ok" — probe checks exit, not output;
  FIX NEEDED in deadman.ps1). wsl --shutdown cleared. (c) WorldMirror 2.0
  local leg: weights only 5 GB (vs 169 GB pano stage); worldmirror conda
  env (torch 2.7.1+cu126, prebuilt gsplat 1.5.3; requirements_git.txt =
  training-only, SKIPPED); repo patch: flash_attn made optional in
  worldrecon attention.py (SDPA fallback). 14 crops @952 pegged VRAM
  11.8/12 → driver spilled to Windows sysmem → deadman TRIP 10:53 (by
  design, machine fine). Retry 8 crops @ target 700 fit in 5.7 GB VRAM,
  61 s total → bedroom_hw2/gen_raw.ply (3.1 M gaussians, 202 MB). NOTE:
  pipeline ends in an interactive REPL — harvest gaussians.ply from
  strict_output_path, don't wait for the script marker. Eval kit done,
  8 objects, calib rot180. (d) ALL FOUR bedroom splats + eval kits ready:
  out/BACKEND_COMPARISON_2026-07-07.html (views/overlays/plans/timings
  side by side). USER: judge composition fields → pick default backend.
