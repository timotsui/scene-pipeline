# SESSION 2026-08-21 HANDOFF — corrected Pipeline Lifter benchmark complete

## Final state

The corrected five-scene Pipeline Lifter run completed successfully. All native
predictions were frozen before Hypersim ground truth was opened, and the shared
evaluator was then run once over Pipeline Lifter, Zoo3D, and Boxer.

This supersedes the pre-bake-off execution state in
`SESSION_2026-08-20_PIPELINE_LIFTER_RESPLAT_SAFETY_HANDOFF.md`. That file remains
historical evidence of the safety boundary; do not treat its "not started"
status as current.

## Method boundary

- Ours is **Pipeline Lifter**, not Splat Analyzer.
- It uses its own Grounding DINO + SAM discovery, exact-camera mask lifting,
  spatial fusion, and SliceVote refinement.
- It consumes no Splat Analyzer proposal, mask, identity, or viewpoint.
- Every base position is an exact, user-reviewed Hypersim/Zoo3D source-pose
  index from `benchmarks/lifting/base_views.v1.json`; no room position is
  invented.
- Each scene uses five base poses and a 20-view angular sweep per base.
- The seven frozen labels are chair, table, sofa, bookshelf, cabinet, lamp, and
  television.

## Reconstruction

The kitchen-only 5k/15k bake-off selected 15k from reconstruction PSNR and user
visual review, with no downstream lifting signal. The identical frozen recipe
in `benchmarks/lifting/reconstruction_recipe.v1.json` was used for all scenes.
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

Headline metrics are scene-macro over five development scenes, not held-out
population estimates.

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
end-to-end method, the frozen-camera/reconstruction boundary, headline and
per-scene results, paired intervals, false-discovery limitation, and held-out
claim boundary. The invalid Splat-Analyzer-fixed-proposal text remains only
inside balanced `\iffalse ... \fi` audit blocks and is not compiled.

## Reproduction

The serial entry point is `benchmarks/lifting/run_pipeline_lifter_benchmark.py`.
It writes prediction-freeze receipts and a five-scene run receipt. Evaluation is
performed with `benchmarks/lifting/summarize_lifting_results.py`, using explicit
`--method` directories and paired `--compare` entries. Do not tune camera,
detector, fusion, SliceVote, reconstruction, or label settings using these five
ground-truth results; future evaluation should use new held-out scenes with the
protocol frozen.
