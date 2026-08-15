# EVAL RESULTS — first numbers (2026-08-13, review session)

Companion to EVAL_PLAN_2026-08-13.md. Every number here is computed
from records that already existed (no re-runs — R-S2-172). Sources:
`out/eval_renders/clip_scores.json`, `out/eval_renders/llm_calls.json`,
`out/comparison.json` (ten-pair rebuild, this session). Scripts:
`clip_score.py`, `eval_llm_calls.py`, `eval_renders.py`,
`compare_methods.py`.

Baseline identity correction (2026-08-14): the saved GLTS runs use the 2026
progress-reward-guided MCTS solver, not the 2025 DFS solver. They run through
step 15, including style-aware asset retrieval, and intentionally stop before
the optional Paint3D texture-generation stage. The paper cites and describes
that exact configuration.

## 1. CLIP score (the baselines' own metric)

OpenCLIP ViT-L/14 (LAION-2B), cosine × 100 vs "a top-down view of a
[scene type]" — GLTS §6.1 recipe. Renders: our frozen product-shot
spec (pyrender, walls from measured floor, room-volume clip, black
void), IDENTICAL for both sides. ⚠ Comparable WITHIN this table only —
never to the papers' printed numbers (theirs are lit Blender/Cycles).

| scene | ours·ortho | ours·persp | glts·ortho | glts·persp |
|---|---|---|---|---|
| natural_living | 31.29 | 33.11 | 29.04 | 25.69 |
| blue_living | 33.83 | 34.70 | 28.77 | 30.85 |
| living_marble† | 32.40 | 34.28 | 34.54 | 28.45 |
| sunlit_office | 33.42 | 35.33 | 26.35 | 31.05 |
| panel_bedroom | 26.77 | 32.08 | 36.27 | 32.65 |
| arch_bedroom | 28.96 | 30.07 | 34.31 | 32.46 |
| plaster_bedroom | 27.30 | 29.31 | 27.57 | 31.70 |
| bedroom_marble† | 32.05 | 32.56 | 27.64 | 29.50 |
| fresh04 | 32.60 | 33.88 | 30.97 | 32.12 |
| fresh06 | 31.42 | 30.17 | 33.01 | 32.52 |
| **MEAN** | **31.00** | **32.55** | **30.85** | **30.70** |

READING: parity-or-better on the invention-friendly plausibility
metric — best column is ours·persp (+1.85 over GLTS's best).
Perspective HELPS ours (+1.55) and hurts GLTS (−0.15): depth cues
flatter dense textured rooms. Per-scene pattern is coherent: ours wins
all living rooms + the office; GLTS wins mostly bedrooms — exactly
where the realization funnel leaves our rooms sparser than GLTS's
fully-furnished inventions. † = older-pair fallback renders
(bedroom_marble bbox walls; living_marble pre-normalization GLB).

## 2. Cost — wall clock + LLM calls

| scene | ours s | ours calls* | glts s | glts calls |
|---|---|---|---|---|
| natural_living | 2271 | 726 | 6346 | 172 |
| sunlit_office | 1327 | 831 | 9020 | 234 |
| blue_living | 3235 | 484 | 7247 | 184 |
| panel_bedroom | 2712 | 286 | 7378 | 196 |
| arch_bedroom | 3804 | 565 | 7952 | 179 |
| plaster_bedroom | 3034 | 616 | 5657 | 147 |
| bedroom_marble | — | 706† | 3755 | 172 |
| living_marble | — | 1528† | 3222 | 138 |
| fresh04 | 740 | 1227† | 11157 | 280 |
| fresh06 | 3389 | 1070† | 11549 | 279 |

- Ours is 2–7× FASTER wall-clock while making ~3–4× MORE model calls:
  small calls at concurrency 8 vs GLTS's serial tree search through the
  same Claude Sonnet backend used by our judges. Time is context, not a race — the two systems do different
  work (we reconstruct + verify; they invent).
- ours s = the latest run_scene record; COVERAGE VARIES (some records
  are partial re-runs; `A_cost.ours.seconds_covers` in comparison.json
  says per scene what is included). No record for the two pre-harness
  scenes. Neither side's number includes crop/seg/lift (no GLTS
  counterpart).
- *ours calls = receipts recount (eval_llm_calls.py): verdict-carrying
  records + cache entries; LOWER BOUND (vocab ~6, bearings, sub-round
  checkpoints, retries uncounted). † caches persist across re-runs, so
  the four older scenes' counts span multiple eras — quote the six
  night scenes as per-build numbers; GLTS side is its own log recount.

## 3. Grounding — room area (ASYMMETRIC: only ours can be scored)

| scene | real m² | GLTS guess m² | error |
|---|---|---|---|
| natural_living | 30.9 | 31.5 | +2% |
| sunlit_office | 89.1 | 57.0 | −36% |
| blue_living | 23.0 | 23.5 | +2% |
| panel_bedroom | 40.8 | 24.8 | −39% |
| arch_bedroom | 30.9 | 22.0 | −29% |
| plaster_bedroom | 34.9 | 15.0 | −57% |
| bedroom_marble | 22.2 | 18.7 | −16% |
| living_marble | 49.7 | 30.0 | −40% |
| fresh04 | 20.9 | 31.5 | +51% |
| fresh06 | 19.7 | 26.6 | +35% |

GLTS's guessed rooms are off by up to −57% / +51%; ours measures. The
worst miss is the two-room scene (plaster) — what a paragraph cannot
tell you.

## 4. Object counts (measured vs invented)

ours 15–82 evidence-backed objects per scene vs GLTS 6–11 invented
(deficit −5 to −73 per scene; full per-scene rows in comparison.json
D_grounding.object_count_error). Retention: GLTS loses part of its own
retrieval per scene (e.g. fresh06: 13 retrieved → 11 placed, 2 lost);
per-scene lists in each comparison.html row.

## 5. Realization funnel (eval_funnel.py -> realization_funnel.json)

The denominator is the newest complete, non-stale scene-graph layer, after
duplicate resolution and overlap cleanup. Raw detections are never counted.
Every graph ID has exactly one outcome: placed under its own ID, covered by a
validated replacement, or not placed. Those outcomes sum to the graph count;
unmeasured additions are separate.

| scene | graph | as requested | replaced | missing | filled | extra |
|---|---:|---:|---:|---:|---:|---:|
| natural_living | 53 | 35 | 7 | 11 | 42 (79%) | 0 |
| sunlit_office | 60 | 48 | 8 | 4 | 56 (93%) | 0 |
| blue_living | 25 | 22 | 0 | 3 | 22 (88%) | 0 |
| panel_bedroom | 15 | 14 | 1 | 0 | 15 (100%) | 0 |
| arch_bedroom | 26 | 19 | 2 | 5 | 21 (81%) | 0 |
| plaster_bedroom | 18 | 13 | 4 | 1 | 17 (94%) | 0 |
| bedroom_marble† | 82 | 30 | 0 | 52 | 30 (37%) | 1 |
| living_marble | — no compatible final compose receipts | | | | | |
| fresh04 | 56 | 33 | 5 | 18 | 38 (68%) | 0 |
| fresh06 | 33 | 26 | 2 | 5 | 28 (85%) | 0 |

The old script was not a true funnel. It compared different stage populations
and then added `merge_subs.json.n_added` to `fitted_preview.json.placed` even
though merged subs were already present in `placed`. The new audit fixes that
double count and preserves graph identity through the final record.

READING: grouped-graph runs place 59–93% of objects as requested and fill
68–100% of measured slots after validated replacements. Swap-ins cover 0–8
slots per scene. Missing slots do not have one cause: the detailed
JSON distinguishes unavailable asset matches, small objects that were placed
in a sub-pass but never merged into the final scene, support-surface failures,
replacement handoff failures, and missing final receipts. † bedroom_marble is
an older run whose newest complete graph layer is `resolved`, before the
current grouped-graph and sub-merge path.

Across the six current runs, 151/197 slots (77%) are direct placements,
22/197 (11%) are fallback replacements, and 24/197 (12%) are missing; total
coverage is 173/197 (88%). Of the 24 missing slots, 13 are library/size-bar
failures, eight were successfully placed in the small-object pass but skipped
because the merger only scanned `obj_*` hosts rather than replacement `swap_*`
hosts, and three are other support/receipt/replacement-handoff failures. The
merger is fixed for future runs; the evaluated outputs remain frozen as built.
Replacement improves coverage, but is not counted as faithful realization of
the requested object.

## 5b. Size match — the library gap, quantified (eval_size_match.py)

| scene | chosen fits (15% canon) | NO fitting option | native dev | out-of-box med/max mm |
|---|---|---|---|---|
| natural_living | 11% | 64% | 42% | 124 / 938 |
| sunlit_office | 18% | 67% | 32% | 143 / 845 |
| blue_living | 7% | 67% | 35% | 280 / 2208 |
| panel_bedroom | 27% | 73% | 33% | 93 / 963 |
| arch_bedroom | 7% | 71% | 75% | 157 / 1039 |
| plaster_bedroom | 13% | 80% | 52% | 383 / 4470 |
| bedroom_marble† | 23% | 61% | 24% | 71 / 587 |
| fresh04 | 18% | 68% | 108% | — |
| fresh06 | 28% | 56% | 64% | 402 / 2246 |

For 56–80% of placements NOT ONE candidate in the retrieval shortlist
natively fit the measured box within the fit canon's own 15% — the
best wrong-size asset was placed. This establishes a library limit under the
pipeline's own fit rule. The boxes are measured but coarse, so it does not prove
that every size mismatch is external to the pipeline. A better library can
improve no-fit cases without changing the graph; the handoff losses above need
pipeline changes.
(Across the six current runs, 128 direct placements have comparable main-pass
pick receipts: 18/128, or 14%, use a candidate within the 15% size tolerance;
88/128, or 69%, had no fitting candidate in the shortlist.) Direct placement
means that the measured graph ID survived; it does not establish an appearance
match. Color, material, shape, and style fidelity are not scored here and
remain dependent on what the asset catalogue and selector provide.
(size_match.json; "native dev" = |native size − box| / box, sorted
dims, orientation-free; out_of_box_mm is the fit's own protrusion
record — absent from fresh04's older-era records.)

## 6. NOT gathered (rulings)

- Physics counts — DEPRIORITIZED (user: we employ a physics solver
  precisely to make this number near-zero; it differentiates nothing).
  If ever mentioned: settled-mesh only, one line, never the box rows.
- Optional, parked for spare time: VLM pairwise preference;
  image-to-image fidelity vs the captured splat.

## STANDING CAVEATS (quote with the numbers)

- Rotation receipts before the R-S2-170 fix are plausibility-mode
  (every scene here except sunlit_office onward).
- CLIP: our renderer both sides; within-table comparisons only.
- Ours call count is a lower bound; older scenes' spans multiple eras.
- living_marble ours side = pre-normalization archive (never fitted in
  the current era — user accepted 08-13).

## 7. August 15 paper-audit update

The first-number interpretation above has now been reviewed against the final paper artifacts. The raw scores remain unchanged; the following statements are the locked reading.

### CLIP prompt sensitivity

The fixed primary metric remains room type only: ours minus GLTS is `+0.15` orthographic (`+0.5%`) and `+1.85` perspective (`+6.0%`). The later shared-prompt experiments are exploratory diagnostics, not replacement metrics:

| shared prompt family | ortho delta | perspective delta |
|---|---:|---:|
| 3D rendering + room type | +2.46 (+7.9%) | +1.89 (+5.6%) |
| + one source style | +3.02 (+10.2%) | +1.40 (+4.3%) |
| + one source mood | +2.12 (+7.2%) | +1.20 (+3.7%) |

The exact prompt protocol and experiment history are preserved in `CS-8903-OVM/week7/entangled_gen/out/eval_renders/CLIP_PROMPT_EXPLORATION_2026-08-15.md`. Every prompt is applied identically to both methods. The result shows prompt sensitivity and a positive margin under these three selected shared conditions; it does not establish full-prompt fidelity.

### Qualitative loss diagnoses

- `plaster_bedroom` entered the automatic pipeline with approximately +39 degrees of uncorrected plan yaw. The evaluated render is raw pipeline output and remains included unchanged in every mean, win count, and pooled comparison. Axis-aligned box inflation and non-canonical framing are suspected contributors to the loss, not confirmed causation. Connecting the existing yaw correction is a small future implementation fix; rerunning downstream artifacts was outside the evaluation budget.
- `arch_bedroom` contains several visibly incorrect lifted boxes, especially around the arched alcove. Lifting quality is a suspected contributor to its loss. This supports the modular limitation story: improved lifting can replace the current stage and improve retrieval, scale, and placement without changing the graph or composer.
- No failed or weak scene was excluded, hand-corrected, or score-adjusted for the paper.

### Scope and interpretation

- Both methods are shown using the same camera and rendering setup for comparison.
- Neither evaluated method uses Paint3D; both are scored with selected assets as delivered.
- Exact preservation of the selected asset is a capability distinct from visual fidelity to the observed splat object. The former can preserve a sourceable SKU, collision data, rig, metadata, and behavior; the latter remains bounded by lifting and catalogue quality.
- The current room shell selects for a flat floor/ceiling and vertical walls. It still preserves non-cardinal walls, cut corners, L-shapes, and connected spaces, which is more expressive in plan than GLTS's rectangular emoji grid. Sloped vertical architecture is future work.
- The 2–7x wall-clock result remains a supporting efficiency win scoped to the six pairs with complete timing records.
- No human study was run; do not translate CLIP into a claim of superior human preference, realism, or style.
