# Lifting benchmark scaffold

This directory contains the versioned, model-independent plumbing for the
lifting-paper benchmark. Heavy renders, splats, predictions, and checkpoints
belong under the machine-local `out/` root and are never committed.

Status on 2026-08-17: **five-scene development benchmark complete; method
configuration frozen before held-out evaluation**.

## Hypersim development benchmark (2026-08-17)

The public-data development study uses five Hypersim train scenes spanning a
living room, kitchen, bedroom, dining room, and office. Each scene uses 50
evenly spaced source frames, exact metric cameras, five reserved reconstruction
checks, and seven canonical object categories. The frozen selection and method
settings are in `hypersim_split.v1.json`; four rejected kitchen candidates and
their predeclared reconstruction-gate failures remain in that file.

Across 87 visible ground-truth objects and the same 123 fixed proposals,
scene-macro mAP25 is 0.124 for Splat Analyzer's rectangular lift, 0.054 for the
global SAM mask-pixel lift, and **0.180 for active slice-vote lifting**. Active
lifting also raises mean recall25 from 0.131 (rectangular) and 0.066 (global SAM)
to 0.255. Its paired mAP25 gain over the stronger rectangular baseline is 0.056
with a scene-bootstrap 95% interval of [0.008, 0.133]. It improves four scenes
and ties the no-proposal scene against that baseline. These are development
results, not held-out estimates.

The reusable stages are:

1. `select_hypersim_scenes.py`: rank official scenes and reject non-pinhole
   cameras.
2. `download_hypersim_subset.py`: use Hypersim's official range downloader for
   an aligned, evenly spaced modality subset.
3. `prepare_hypersim_scene.py`: write exact metric cameras, visible ground
   truth, initialized points, COLMAP files, a Boxer sequence, and box overlays.
4. `train_hypersim_splat.py`: run gsplat v1.5.3's official trainer headlessly
   while preserving the metric scene frame.
5. `verify_hypersim_splat.py`: render reserved cameras with Splat Analyzer's
   PLY loader/renderer and write PSNR plus visual comparisons.
6. `adapt_splat_analyzer.py` and `evaluate.py`: convert and score the native
   rectangular lift.
7. `refine_splat_analyzer_masks.py`: hold detections and clusters fixed while
   replacing only their geometry with SAM mask-pixel depth lifting.
8. `prepare_slicevote_scene.py`, `slicevote.py`, and `adapt_slicevote.py`: hold
   proposal identities, labels, and scores fixed while applying active plan and
   tunnel re-observation, then restore the common benchmark schema.
9. `summarize_lifting_results.py`: recompute scene-macro and pooled metrics,
   input hashes, and paired scene-bootstrap intervals from saved predictions.

Heavy source data, splats, model outputs, and metrics remain under the ignored
machine-local `out/` root. The committed split records which settings are frozen
and which held-out work remains.

## Recommended execution order

1. Generate two development scenes from known assets and export exact AABBs.
2. Validate frame, units, and box projection visually.
3. Convert every method's native output to `schema.v0.json` JSONL records.
4. Run `evaluate.py` on synthetic fixtures, then on the two development scenes.
5. Only after adapters agree, freeze the full dev/test manifests and protocol.

Keep two method protocols:

- `native`: each method uses its intended view policy; record resource use.
- `matched_budget`: common initial views and a common render/detector-call cap.

Do not tune on held-out scenes. Existing generated scenes have no object-level
metric ground truth and may be used only for plumbing, timing, and qualitative
checks.

## Unified object record

Predictions and ground truth use one JSON object per line:

```json
{"scene_id":"dev_000","object_id":"chair_0","label":"chair",
 "aabb_min":[-0.5,0.0,-0.5],"aabb_max":[0.5,1.0,0.5],"score":0.9}
```

The required coordinate frame and matching rules are in `protocol.v0.json`.
Native outputs must be preserved next to converted outputs.

## Commands

Convert a Splat Analyzer result:

```powershell
python benchmarks/lifting/adapt_splat_analyzer.py `
  --input <interactions.json> --scene-id <scene> --output <predictions.jsonl>
```

Evaluate predictions:

```powershell
python benchmarks/lifting/evaluate.py `
  --ground-truth <objects.jsonl> --predictions <predictions.jsonl> `
  --output <metrics.json>
```

Run the local evaluator tests (requires NumPy and SciPy):

```powershell
python -m unittest discover -s benchmarks/lifting/tests -v
```

Validate Boxer's released checkpoints without sample data (inside its WSL
environment):

```bash
python /mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/benchmarks/lifting/smoke_boxer.py \
  --repo /root/lifting_bench/boxer
```

Export a mechanically verified analyzer render job for Boxer's ScanNet loader:

```powershell
python entangled_gen/analyzer/cams_from_transforms.py `
  --scene <scene> --job <analyzer-job>
python benchmarks/lifting/export_scannet_sequence.py `
  --transforms <job>/transforms.json --output <sceneNNNN_NN> --max-frames 5
```

The export refuses to run without the G1 convention result, converts the
metric `.npy` depth to uint16 millimetres, and records source-frame provenance
in `export_manifest.json`. Use a `sceneNNNN_NN` output basename so Boxer's CLI
selects its pinhole RGB-D loader.

Run a deliberately small Boxer inference from its isolated WSL checkout:

```bash
cd /root/lifting_bench/boxer
.venv/bin/python run_boxer.py \
  --input <sceneNNNN_NN> --max_n 5 --labels='chair,table,sofa' \
  --skip_viz --force_precision bfloat16 --output_dir <output-root>
```

Ubuntu's `python3.12-dev` package is required because Triton compiles a small
CUDA helper during first use. Install `ffmpeg` if visualization is enabled;
Boxer uses it to assemble the final MP4. Omit `--fuse` for plumbing checks;
enable and record it as a distinct native-method setting for actual Boxer
evaluation.

Convert Boxer's OBB CSV back to the source scene frame and benchmark AABBs:

```powershell
python benchmarks/lifting/adapt_boxer.py `
  --input <boxer_3dbbs.csv> --export-manifest <export_manifest.json> `
  --scene-id <scene> --output <predictions.jsonl>
```

The adapter restores the camera-translation offset applied by Boxer's loader
and encloses each quaternion-oriented native box with a world-frame AABB.
Keep the native OBB CSV: the AABB conversion is for the common evaluator only.

## Baseline order

1. Splat Analyzer: already runnable in WSL; use it to validate the adapter.
2. Boxer: official checkpoint and headless smoke inference.
3. Zoo3D_0: prepare after Boxer; its CropFormer, Detectron2, SAM2, OpenCLIP,
   point-cloud, and ScanNet-style contracts make it the highest-risk adapter.

The full experiment design remains in
`CS-8903-OVM/paper/overleaf/LIFTING_RESULTS_PLAN.md`.
