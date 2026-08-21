# SESSION 2026-08-20 HANDOFF — pipeline-lifter viewpoints approved; resplat bake-off staged but NOT STARTED

## STOP/RECOVERY STATE

The user deliberately stopped execution before the resplat bake-off because a
larger gsplat run might destabilize the machine. **Nothing in the bake-off has
started. Do not start training automatically when reading this handoff.** Wait
until the user explicitly returns and says to begin.

The earlier Dining pipeline-lifter render was also interrupted. Its partial
artifacts were preserved. No detector, SAM, lifting, fusion, SliceVote, or
benchmark evaluation ran from that partial scene.

The base-view review server that had been listening on `127.0.0.1:8765` was
stopped during wrap-up. Its HTML and selections remain on disk.

The current task is paused at a clean decision boundary:

1. user-approved base viewpoints are frozen on disk;
2. the invalid earlier lifting benchmark has been diagnosed;
3. a corrected pipeline-lifter scene preparer exists but is unfinished beyond
   pano/crop preparation;
4. existing 5k splats have been audited;
5. a safety-staged resplat bake-off is designed below but has not run.

## TERMINOLOGY AND SCIENTIFIC BOUNDARY

- Our method is the **pipeline lifter**.
- Splat Analyzer is an external baseline. It is not our pipeline.
- The corrected pipeline lifter must perform its own Grounding DINO + SAM
  discovery, mask lift/fusion, and SliceVote.
- It must not consume Splat Analyzer proposals, masks, or chosen viewpoints.
- Base locations must be exact source trajectory poses used by Zoo3D/Hypersim,
  not invented or sampled novel camera positions.
- Multiple reviewed base locations are allowed because the pipeline lifter
  performs its angular sweep at each base.

## WHY THE PREVIOUS LIFTING TEST IS INVALID

The existing benchmark bootstrap in
`benchmarks/lifting/prepare_slicevote_scene.py` starts from fixed Splat Analyzer
proposals/SAM masks. That is not the pipeline lifter described by the user, and
its results must not be presented as ours. The earlier test also used poor
novel viewpoints. Existing metrics and manuscript claims produced from that
test must remain quarantined until the corrected pipeline has been run.

## FROZEN USER-APPROVED BASE VIEWS

Authoritative receipt:
`benchmarks/lifting/base_views.v1.json`

At runtime, load the complete `transform_matrix` from the prepared scene's
`transforms.json` at each approved Zoo input index. Never transcribe rounded
coordinates.

| Scene | Room | Approved Zoo/Hypersim indices |
|---|---|---|
| `ai_051_002` | Living | `4, 45, 34, 43, 8` |
| `ai_002_006` | Kitchen | `6, 21, 17, 19, 0` |
| `ai_006_008` | Bedroom | `23, 0, 21, 11, 3` |
| `ai_037_007` | Dining | `26, 29, 33, 43, 30` |
| `ai_003_009` | Office | `13, 3, 29, 5, 35` |

The user specifically replaced Kitchen index 13 with index 19 and then
approved all five scenes. The interactive review page is:
`benchmarks/lifting/reports/base_view_review/index.html`.

The manifest includes a SHA-256 for every source `transforms.json`; the
preparer validates the hash before using a pose. It also explicitly forbids
novel base positions and a Splat Analyzer bootstrap.

## CORRECTED PIPELINE-LIFTER CODE ON DISK

All of this work is currently uncommitted and shares a dirty worktree with
other user changes. Preserve unrelated changes.

- `benchmarks/lifting/prepare_pipeline_lifter_scene.py` — loads approved exact
  poses, prepares a clean pipeline scene, renders one pano per base, and crops
  the normal 20-view sweep per base. It accepts no baseline proposals/masks.
- `entangled_gen/pano_stitch.py` — added exact `--eye-raw` support.
- `entangled_gen/crop_pano.py` — added prefixed multi-base outputs and exact
  camera-transform sidecars.
- `entangled_gen/pano_lift.py` — accepts exact transform sidecars.
- Detector, lift/fusion, and voting orchestration are not yet wired into the
  new preparer. Do not mistake pano preparation for a finished benchmark.

## PARTIAL DINING RENDER

Preserved output:
`D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\hypersim_ai_037_007_pipeline_lifter_v1`

State at interruption:

- scene setup/receipt, shell, frame data, and 5k `gen_raw.ply` are present;
- `rig_base0` through `rig_base3` have all six cube faces and a stitched pano;
- `rig_base4` has all six cube faces, but `pano_selfrender.png` and its metadata
  are missing because stitching was interrupted;
- combined crops were not produced;
- no discovery, masks, lift, fusion, vote, or evaluation ran.

If the bake-off selects a new splat recipe, do not continue this 5k-based
partial output as the benchmark. Preserve it as diagnostic evidence and create
a fresh pipeline-lifter output from the frozen replacement PLY.

## WHY A RESPLAT BAKE-OFF IS WARRANTED

The current splats use the official gsplat v1.5.3 simple trainer with exact
metric cameras, 100,000 initial points, 50 images, held-out frame index modulo
10, no normalization, SH degree 3, no antialiasing, no appearance optimization,
and no depth loss.

Critical mismatch: training stops at 5,000 steps, while the default strategy's
`refine_stop_iter` is 15,000. The current runs end after only the first third of
the configured densification/refinement window.

Current held-out PSNR:

| Scene | Mean | Median | Min | Max | Training time |
|---|---:|---:|---:|---:|---:|
| Living | 23.50 | 24.10 | 20.35 | 25.83 | 1.9 min |
| Kitchen | 20.97 | 21.46 | 18.12 | 23.11 | 1.6 min |
| Bedroom | 20.96 | 19.98 | 18.10 | 25.70 | 2.3 min |
| Dining | 25.83 | 25.87 | 23.93 | 27.02 | 1.6 min |
| Office | 25.01 | 25.53 | 15.45 | 31.29 | 1.5 min |

Read-only visual inspection found large texture/geometry smearing in Kitchen,
floaters and boundary corruption in Bedroom, and severe wall/ceiling corruption
in Office. Dining is the stronger control but remains soft around thin and
reflective structures. Passing the old mean >=18/min >=15 smoke gate proves
basic usability, not that these are good lifting substrates.

## SAFETY-STAGED BAKE-OFF — DO NOT LAUNCH AS A BATCH

The original idea was Kitchen and Dining at 15k and 30k. For machine safety,
the actual work order must be serial with a hard review point after every
training job.

### Stage 0 — preflight only

1. Confirm the user has explicitly said to start.
2. Confirm no render/training process is already using the GPU.
3. Run `nvidia-smi` and record free VRAM, GPU temperature, utilization, and the
   process list.
4. Record free space on `D:` and WSL. Require at least 100 GiB free on `D:`.
5. Do not run detector/SAM/pipeline jobs concurrently.
6. Do not overwrite or delete any `gsplat5000` directory.

### Stage 1 — Kitchen 15k only

Train only `ai_002_006_gsplat15000`, then stop. Do not queue Dining or 30k in
the same shell command. A successful job must end with both:

- `training_receipt.json`
- `ply/point_cloud_14999.ply`

Then run held-out verification into a separate
`verification/ai_002_006_gsplat15000` directory. Inspect all five comparisons,
not just their mean.

Afterward, check machine health, output size, Gaussian count, peak/ending VRAM,
and whether the receipt exists. Report to the user before Stage 2.

### Stage 2 — Dining 15k control

Run only after Kitchen 15k completes safely and the user accepts continuing.
Use the same recipe and separate output name
`ai_037_007_gsplat15000`. Verify all five held-out frames. Stop and report.

### Stage 3 — 30k is conditional

Do not automatically run 30k. The default densification window already ends at
15k; 30k tests whether additional optimization after densification matters. Run
Kitchen 30k only if 15k is safe and improves the weak case while leaving a
clear unresolved trend. Run Dining 30k only if Kitchen 30k adds a material
benefit and remains safe.

The 200k-initial-point and depth-supervised candidates are separate future
ablations. They are deliberately excluded from this bake-off so that training
duration is the only changed variable.

## EXACT COMMAND TEMPLATE FOR THE NEXT SESSION

Run under WSL Ubuntu using the existing isolated Splat Analyzer environment.
These commands are recorded for reproducibility, but they were **not executed
in this session**.

```bash
PY=/root/miniconda3/envs/splatanalyzer/bin/python
PIPELINE=/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline
ROOT=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out/lifting_benchmark/hypersim
GSPLAT=/mnt/d/T/Documents/GeorgiaTech/Summer2026/Research/code/reference/gsplat
ANALYZER=/root/splat_analyzer

"$PY" "$PIPELINE/benchmarks/lifting/train_hypersim_splat.py" \
  --gsplat-repo "$GSPLAT" \
  --data "$ROOT/prepared/ai_002_006" \
  --result "$ROOT/training/ai_002_006_gsplat15000" \
  --steps 15000 \
  --max-initial-points 100000 \
  --test-every 10

"$PY" "$PIPELINE/benchmarks/lifting/verify_hypersim_splat.py" \
  --splat-analyzer-repo "$ANALYZER" \
  --data "$ROOT/prepared/ai_002_006" \
  --ply "$ROOT/training/ai_002_006_gsplat15000/ply/point_cloud_14999.ply" \
  --output "$ROOT/verification/ai_002_006_gsplat15000" \
  --test-every 10
```

For Dining, change both occurrences of `ai_002_006` to `ai_037_007`. For 30k,
use a new `gsplat30000` directory, `--steps 30000`, and
`point_cloud_29999.ply`. Never reuse a candidate output directory after an
interrupted run; preserve it and use a clearly suffixed retry directory.

Pinned/current environment facts from the 5k receipts:

- Python environment: `/root/miniconda3/envs/splatanalyzer`
- PyTorch `2.4.1+cu124`; CUDA `12.4`; gsplat `1.5.3`
- gsplat reference commit: `937e29912570c372bed6747a5c9bf85fed877bae`
- Splat Analyzer runnable copy: `/root/splat_analyzer`

## CRASH/OOM RECOVERY RULES

- Training writes the final receipt only after the PLY export succeeds. If
  `training_receipt.json` is absent, treat that candidate as incomplete even if
  checkpoints or partial files exist.
- A CUDA OOM or system interruption must not trigger an automatic retry.
- Do not delete partial output during recovery. Record its last modified time,
  size, last log line, and whether the expected final PLY/receipt exists.
- Recheck GPU processes and free disk after any failure.
- Retry only after user approval, serially, into a new suffixed directory.
- Do not lower image resolution, point count, or silently change strategy to
  make a failed run pass; that would invalidate the duration-only comparison.

## COMPARISON AND ADOPTION GATE

The existing verifier computes PSNR and writes five reference/render pairs. It
does **not** currently compute SSIM, LPIPS, or depth metrics. Do not claim those
metrics unless a separate evaluator is implemented and run.

The selection must use reconstruction-only evidence, never downstream lifting
labels or benchmark results. This prevents choosing a splat that happens to
favor our method.

Proposed 15k adoption gate:

1. Kitchen mean held-out PSNR improves by about 1 dB or more;
2. Kitchen's worst held-out view does not materially regress;
3. visible smearing, floaters, boundaries, and thin structures improve;
4. Dining does not show a meaningful regression in its strong control views;
5. machine resource use and output size remain operationally safe.

Choose 30k over 15k only if it adds a visible reconstruction benefit and a
nontrivial metric gain; otherwise freeze 15k as the smaller recipe. Once a
recipe is frozen, resplat all five scenes identically before restarting the
pipeline-lifter benchmark. Every method compared must consume the same frozen
scene reconstruction.

## CURRENT REPOSITORY STATE

No commit was made. Relevant new/modified files include:

- `benchmarks/lifting/base_views.v1.json` (new)
- `benchmarks/lifting/prepare_pipeline_lifter_scene.py` (new)
- `benchmarks/lifting/reports/base_view_review/` (new)
- `benchmarks/lifting/reports/pipeline_walkthrough/` (new/dirty)
- `entangled_gen/pano_stitch.py` (modified)
- `entangled_gen/crop_pano.py` (modified)
- `entangled_gen/pano_lift.py` (modified)
- lifting 3D viewer/report files (modified)

There are other unrelated user changes in the dirty worktree. Do not reset,
checkout, clean, or bulk-delete anything.

## NEXT SESSION — EXACT ORDER

1. Read this handoff completely.
2. Confirm with the user whether to begin Stage 0/Stage 1.
3. Perform the safety preflight and report anything surprising.
4. Run Kitchen 15k alone.
5. Verify and visually inspect all five held-out frames.
6. Stop and report machine health, artifact completeness, metrics, and visual
   result before asking whether to continue to Dining 15k.
7. Do not resume the pipeline-lifter render until a splat recipe has been
   selected and frozen.
