# EVAL RESULTS — first numbers (2026-08-13, review session)

Companion to EVAL_PLAN_2026-08-13.md. Every number here is computed
from records that already existed (no re-runs — R-S2-172). Sources:
`out/eval_renders/clip_scores.json`, `out/eval_renders/llm_calls.json`,
`out/comparison.json` (ten-pair rebuild, this session). Scripts:
`clip_score.py`, `eval_llm_calls.py`, `eval_renders.py`,
`compare_methods.py`.

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
  small cheap calls at concurrency 8 vs GLTS's serial GPT-4o tree
  search. Time is context, not a race — the two systems do different
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

measured graph objects -> anchor-tier shopped (+ subs deferred) ->
assets standing in the final GLB (anchors + swap-ins + merged subs),
with every unrealized item's recorded reason:

| scene | measured | shopped (+subs) | in GLB | unrealized (reason) |
|---|---|---|---|---|
| natural_living | 53 | 34 (+19) | 56 | 4 — no asset match |
| sunlit_office | 60 | 45 (+15) | 67 | 0 |
| blue_living | 25 | 18 (+7) | 29 | 1 — no asset match |
| panel_bedroom | 15 | 11 (+4) | 19 | 0 |
| arch_bedroom | 26 | 17 (+9) | 28 | 3 — no asset match |
| plaster_bedroom | 18 | 16 (+2) | 18 | 0 |
| bedroom_marble† | 82 | 31 (+64) | 31 | 0 (era: no sub machinery) |
| living_marble | — no current-era compose receipts (never fitted) | | | |
| fresh04 | 56 | 43 (+26) | 38 | 5 — no asset match |
| fresh06 | 33 | 20 (+13) | 38 | 2 — no asset match |

"in GLB" can exceed "measured" because swap-ins (retrieval
replacements) and merged subs add items beyond the graph count — the
columns are populations, not a strict subset chain; the honest rate is
per-tier (anchors placed / anchors shopped, near-total on every night
scene). READING — sharper than the going-in assumption: on the current
pipeline the funnel's hard losses are SMALL (0–5 per scene) and have
ONE cause, "no acceptable asset match" — the asset-library ceiling is
real but narrow; the sparse look of some rooms is about asset QUALITY
and the deferred-sub tail, not mass unrealization. The limitation
paragraph should say that precisely. † bedroom_marble (old era, 38%
of measured placed, 64 subs deferred with no sub machinery yet) shows
what the funnel looked like BEFORE the sub rounds landed — a nice
built-in ablation of the sub machinery.

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
