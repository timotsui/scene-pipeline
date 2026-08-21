# SESSION 2026-08-21 HANDOFF — corrected Pipeline Lifter benchmark complete

## Final state

The corrected five-scene Pipeline Lifter run completed successfully. All native
predictions were sealed before scoring, Hypersim ground-truth boxes were not
pipeline inputs, and the shared evaluator was then run over Pipeline Lifter,
Zoo3D, and Boxer.

This supersedes the pre-bake-off execution state in
`SESSION_2026-08-20_PIPELINE_LIFTER_RESPLAT_SAFETY_HANDOFF.md`. That file remains
historical evidence of the safety boundary; do not treat its "not started"
status as current.

## Method boundary

- Ours is **Pipeline Lifter**, not Splat Analyzer.
- It uses its own Grounding DINO + SAM discovery, exact-camera mask lifting,
  spatial fusion, and SliceVote refinement.
- It consumes no Splat Analyzer proposal, mask, identity, or viewpoint.
- Every base position is an exact Hypersim/Zoo3D source-pose index from
  `benchmarks/lifting/base_views.v1.json`; no room position is invented. The
  five-pose budget is an efficiency subset of the same 50-pose input trajectory,
  not a separate camera-selection method.
- Each scene uses five base poses and a 20-view angular sweep per base.
- The seven frozen labels are chair, table, sofa, bookshelf, cabinet, lamp, and
  television.

## Reconstruction

The kitchen-only 5k/15k quality check established that the available splat
could be improved. The best available 15k reconstruction is common input
preparation, not a Pipeline Lifter component or lifting hyperparameter. The
identical recipe in `benchmarks/lifting/reconstruction_recipe.v1.json` was used
for all splat-consuming configurations, with no downstream lifting signal.
All five reconstructions passed the held-out gate. Mean PSNR ranged from
20.525 dB (bedroom) to 26.209 dB (office).

## Frozen outputs

Run receipt:

`D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\pipeline_lifter_five_scene_run.v1.json`

Per-scene predictions are under:

`...\out\hypersim_{scene}_pipeline_lifter_v1_gsplat15000\benchmark\predictions.jsonl`

| Scene | Valid exact-camera views / 100 | Frozen predictions |
|---|---:|---:|
| `ai_051_002` living | 81 | 52 |
| `ai_002_006` kitchen | 48 | 20 |
| `ai_006_008` bedroom | 55 | 47 |
| `ai_037_007` dining | 59 | 43 |
| `ai_003_009` office | 47 | 21 |
| **Total** | **290 / 500** | **183** |

## Corrected results

Headline metrics are scene-macro over the five benchmark scenes.

| Method | Predictions | mAP25 | mR25 | mAP50 |
|---|---:|---:|---:|---:|
| Pipeline Lifter | 183 | 0.401 | 0.495 | 0.237 |
| Zoo3D | 50 | 0.194 | 0.249 | 0.151 |
| Boxer | 49 | 0.019 | 0.057 | 0.000 |

Pipeline Lifter minus Zoo3D is +0.207 AP25 (paired scene-bootstrap 95% CI
[0.043, 0.372]), +0.246 recall25 ([0.064, 0.415]), and +0.086 AP50
([-0.012, 0.186]). The strict-IoU interval crosses zero. Pipeline Lifter emits
many more candidates and has 148 pooled false discoveries at IoU 0.25 versus
37 for Zoo3D, so proposal precision remains a major limitation. Kitchen is the
clear failure scene (AP25 0.014); dining is no longer empty (AP25 0.592).

The authoritative result artifact is:

`D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\paper\overleaf\lifting-paper\results\pipeline_lifter_corrected_v1.json`

## Paper

`lifting_paper.tex` in the Overleaf repository now presents the corrected
end-to-end method, common source-pose/reconstruction inputs, headline and
per-scene results, paired intervals, and false-discovery limitation. The invalid
Splat-Analyzer-fixed-proposal text remains only
inside balanced `\iffalse ... \fi` audit blocks and is not compiled.

## Reproduction

The serial entry point is `benchmarks/lifting/run_pipeline_lifter_benchmark.py`.
It writes prediction-freeze receipts and a five-scene run receipt. Evaluation is
performed with `benchmarks/lifting/summarize_lifting_results.py`, using explicit
`--method` directories and paired `--compare` entries. Do not tune camera,
detector, fusion, SliceVote, reconstruction, or label settings using these five
ground-truth results. The historical `development` name in the pre-run protocol
receipt identifies the original split record; it does not make source-pose
subsampling or reconstruction quality part of the lifting method.
