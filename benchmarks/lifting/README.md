# Lifting benchmark scaffold

This directory contains the versioned, model-independent plumbing for the
lifting-paper benchmark. Heavy renders, splats, predictions, and checkpoints
belong under the machine-local `out/` root and are never committed.

Status on 2026-08-21: **the corrected five-scene Pipeline Lifter benchmark is
complete**. The former
fixed-proposal SliceVote experiment is quarantined as a legacy ablation: it
started from Splat Analyzer proposals and masks and is not the pipeline lifter.

## Hypersim benchmark

The public-data benchmark uses five Hypersim train scenes spanning a
living room, kitchen, bedroom, dining room, and office. Each scene uses 50
evenly spaced source frames, exact metric cameras, five reserved reconstruction
checks, and seven canonical object categories. Every splat-consuming
configuration uses the same highest-quality available 15,000-step
reconstruction in `reconstruction_recipe.v1.json`. Reconstruction quality is
common input preparation, not part of the lifting method.

The pipeline lifter uses a fixed five-pose compute budget from the same prepared
Hypersim trajectories supplied to Zoo3D. It renders a 20-view angular sweep at
each base (100 views per scene), runs its own
GroundingDINO and SAM discovery, lifts the masks with exact camera sidecars,
spatially fuses the lifted observations, and then runs SliceVote. The exact pose
indices are in `base_views.v1.json`; no novel base positions and no Splat
Analyzer proposals, masks, or viewpoints enter this method.

The old experiment across 87 visible ground-truth objects and the same 123
fixed proposals reported
scene-macro mAP25 is 0.124 for Splat Analyzer's rectangular lift, 0.054 for the
global SAM mask-pixel lift, and **0.180 for active slice-vote lifting**. Active
lifting also raises mean recall25 from 0.131 (rectangular) and 0.066 (global SAM)
to 0.255. Its paired mAP25 gain over the stronger rectangular baseline was 0.056
with a scene-bootstrap 95% interval of [0.008, 0.133]. It improves four scenes
and ties the no-proposal scene against that baseline. These are development
results, not held-out estimates, and are retained only as a historical
fixed-proposal ablation. They must not be reported as the pipeline lifter.

The corrected cross-system benchmark uses the same five scenes, 87 visible ground
truth objects, seven-category normalization, and common evaluator, but lets each
system keep its own proposal and aggregation pipeline. Zoo3D reaches scene-macro
mAP25 0.194, recall25 0.249, and mAP50 0.151 from 50 target-category predictions.
Pipeline Lifter reaches 0.401, 0.495, and 0.237 from 183 predictions; Boxer
reaches 0.019, 0.057, and 0.000 from 49 predictions. All five Pipeline Lifter
prediction files were frozen before ground truth was opened. This is a native
same-scene system comparison, not a fixed-proposal causal ablation.

The offline visual summary, including the aggregate and per-scene
ours-versus-Zoo3D win/tie/loss tables, is in
[`reports/zoo3d_comparison.html`](reports/zoo3d_comparison.html).

The interactive five-scene comparison, with the full Gaussian splat, our
boxes, Zoo3D, Boxer, ground truth, and all 90 proposal-camera directions, is in
[`reports/scene3d/`](reports/scene3d/README.md).

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
8. `prepare_pipeline_lifter_scene.py`, `slicevote.py`, and
   `adapt_pipeline_lifter.py`: run native multibase discovery, mask lift/fusion,
   SliceVote, and freeze predictions without reading ground truth.
9. `prepare_slicevote_scene.py` and `adapt_slicevote.py`: legacy
   Splat-Analyzer-fixed-proposal ablation only; never the pipeline lifter.
10. `summarize_lifting_results.py`: recompute scene-macro and pooled metrics,
   input hashes, and paired scene-bootstrap intervals from saved predictions.

External systems are evaluated as a separate cross-system reference because
they generate and aggregate their own proposals. `export_scannet_sequence.py`
and `adapt_boxer.py` preserve Boxer's native posed-RGB-D contract.
`prepare_zoo3d_scene.py` writes Zoo3D's 640x480 posed-image layout while
preserving the benchmark metric world frame, and `adapt_zoo3d.py` converts its
point masks to benchmark AABBs. The fixed-proposal table is a historical
component ablation and is kept separate from the corrected native
pipeline-lifter result.

Heavy source data, splats, model outputs, and metrics remain under the ignored
machine-local `out/` root. The committed receipts record the frozen inputs,
settings, and predictions.

## Protocol rules

Keep the corrected native method, historical ablation, and external protocols
distinct:

- `fixed_proposal`: every lift receives the same proposal identity, label, score,
  and initial global observations; legacy ablation only.
- `pipeline_lifter_native`: five measured source-trajectory bases, 20 angular
  views per base, native detector/masks/lift/fusion, then SliceVote.
- `native_external`: each released system keeps its intended proposal and
  aggregation path; inputs and resource use are reported rather than treated as
  matched.

Do not use object-level benchmark ground truth to tune discovery, lifting,
fusion, or refinement. Existing generated scenes have no object-level metric
ground truth and may be used for plumbing, timing, and qualitative checks.

## Unified object record

Predictions and ground truth use one JSON object per line:

```json
{"scene_id":"dev_000","object_id":"chair_0","label":"chair",
 "aabb_min":[-0.5,0.0,-0.5],"aabb_max":[0.5,1.0,0.5],"score":0.9}
```

The corrected method and matching rules are in `protocol.v1.json`.
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
Boxer's released offline fusion (`iou=0.3`, `min_detections=4`, `conf=0.55`)
emitted no boxes on these 50-frame Hypersim trajectories. The reported external
row changes only `min_detections` to one while preserving the released IoU and
confidence thresholds. This avoids comparing against a trivial empty output and
matches the one-observation support available to the other lifting paths.

Export a prepared scene for Zoo3D's posed-image release path:

```powershell
python benchmarks/lifting/prepare_zoo3d_scene.py `
  --scannet-dir <prepared-scene>/scannet `
  --initial-points <prepared-scene>/initial_points.npz `
  --zoo-data-root <zoo-output>/data/scannet --scene-id <scene>
```

The exporter resizes RGB-D frames from 512x384 to Zoo3D's 640x480 input and
writes the equivalent 1280x960 calibration expected by its internal half-scale.
It supplies the prepared 200,000-point metric reconstruction as the released
posed-image pipeline's reconstructed point-cloud input. Camera poses and points
remain in the benchmark world frame.

After Zoo3D semantic inference, convert its point-mask NPZ:

```powershell
python benchmarks/lifting/adapt_zoo3d.py `
  --input <prediction.npz> --points <scene.bin> `
  --constants <Zoo3D_0>/evaluation/constants.py `
  --scene-id <scene> --output <predictions.jsonl>
```

The adapter evaluates only the seven benchmark categories and applies a frozen
semantic normalization for direct ScanNet200 synonyms such as `couch` to
`sofa`, `tv` to `television`, and table/chair/cabinet subtypes to their parent
categories. Non-target Zoo3D classes are discarded before common evaluation.
The `patches/zoo3d_*.patch` files record four release-environment fixes: the
modern PyTorch scalar-type API, Python 3.12 HoRNet evaluation scope, removal
of an unused `mmdet3d` import, and memory-only batching of independent SAM2
frames. None changes model weights, thresholds, geometry,
or predictions.

The original experiment design remains in
`CS-8903-OVM/paper/overleaf/LIFTING_RESULTS_PLAN.md`.
