# PLAN — repo cleanup: module isolation + contracts (2026-07-23)

Goal: every module and sub-module isolated, clean file in/out contracts,
functions callable standalone. Baseline: 3-agent audit 2026-07-23 (composition /
entangled_gen / repo-wide). Checkpoint commit before any cleanup: `225d4c5`.

## Audit verdict (baseline)

Repo-wide there are exactly TWO cross-module code imports:
1. `composition/comp_paths.py:8-9` → `entangled_gen/paths.py` — the sanctioned
   single-chokepoint seam (~20 composition files route through it).
2. `entangled_gen/cut/integration_demo.py:44-46` → `composition/place2` — the
   reverse edge (architecture-level cycle). PARKED, user decision pending.

`real_scan/` and `proposer/` cross zero boundaries. No tracked binaries
(156 tracked files, all code/docs/small JSON). proposer/ contains no code.

## User decisions (2026-07-23)

- Dead code: DELETE (render_views.py, render_test2.py, adapter.py, 2 logs).
- Refactor depth: FULL Tier 1 + guards (behavior identical).
- Git order: checkpoint first (done, `225d4c5`), cleanup as separate commits.
- Circular dep: user asked "why" — explanation given; resolution PARKED.
- Also requested: interactive pipeline-architecture HTML; kill stale docs.

## Work items

| # | item | status |
|---|------|--------|
| 1 | Checkpoint commit | DONE `225d4c5` |
| 2 | This plan doc | DONE |
| 3 | Delete dead code: `entangled_gen/render_views.py`, `render_test2.py`, `adapter.py`; `composition/jiggle_run.log`, `recreate_run.log` | pending |
| 4 | Path fixes: `comp_paths.py` OBJATHOR+BRIDGE_DIR → local_paths.json mechanism; `bridge.py:20` CLAUDE_EXE → config; `gen/hunyuanworld/mesh_to_splat.py:29` + `gen/matrix3d/download_weights.py:13` stale week7 paths → paths.py; `analyzer/build_comparison.py:141` abs bat path → derived | pending |
| 5 | Coupling + guards: `make_crops` out of review_server → shared `crops.py`; `retrieve.py` explicit refresh API (loop.py:168 stops mutating catalog rows); `pick.py` warns when `clip` missing; `retrieve2.py` warns when measure cache absent; `__main__` guards: seg_views, viewer/serve, spag_convert, download_weights, test_roundtrip | pending |
| 6 | Docs: PIPELINE.md += analyzer/ + graph/ stage tables + pano contracts + numbering reconciliation; root README refresh (new lanes, local_paths claim fix, real_scan = frozen optional); real_scan README dup fragment; PROPOSER.md dangling week5 paths; .gitignore gaps (`outputs/`, `views/`, `*.log` repo-wide) | pending |
| 7 | Interactive pipeline HTML artifact (modules → sub-modules → contracts) | pending |
| 8 | Circular dep resolution | PARKED (user) |

## Stale-docs kill policy

- KILL only if verified superseded AND not a dated record:
  `viewer/OFFLINE_VIEWER_FIX_PLAN.md` (candidate — verify vendoring complete first).
- KEEP: `docs/SESSION_*_HANDOFF.md` (dated history, the resume system),
  `PLAN_GAUSSIAN_CUT_AND_SPLAT_ANALYZER.md` (governs R1–R6 resume),
  `PLAN_SCENE_GRAPH.md` (ACTIVE), `docs/REVIEW_LOG.md` (verdicts pending),
  `GEN_BACKEND_EVAL_PLAN.md` (eval queue active).
- FIX-IN-PLACE (stale content, living doc): root README, real_scan README,
  proposer/PROPOSER.md.

## Explicitly NOT touched

- v0 composition files (`recreate.py`, `propose.py`, `place.py` v0 entrypoints,
  `jiggle.py`, `compose_scene.py`) — kept frozen for `--compare`; their
  duplicate constants (`WALL_LABELS` divergence, `_sub_boxes` copy) documented
  here as known debt, not unified.
- `real_scan/` code — frozen module; known quirks left as-is
  (`03_render.py` ABANDONED-marked, `02_clean.py:129` `or True` no-op guard).
- `graph/build_graph.py` importing parent `envelope` — intra-module, allowed.
- Module-level `r3 = paths.load_r3()` in 6 files — mild import-time work, allowed.

## REVIEW_LOG

| id | What | Why | Look for | provisional verdict |
|----|------|-----|----------|--------------------|
| RC1 | dead-code deletes | user-approved | nothing imports them (audit-confirmed) | — |
| RC2 | comp_paths → local_paths.json | portability; README claim becomes true | chain still runs: retrieve2/pick/place2 find objathor + bridge dirs | — |
| RC3 | make_crops move | server module was a compute dep | review_server + relevance both still work | — |
| RC4 | retrieve refresh API | kill hidden global mutation | loop.py add-op still refreshes sizes | — |
| RC5 | main guards | scripts ran at import | CLIs behave identically | — |
| RC6 | docs refresh | contracts current | PIPELINE.md matches code reality | — |
| RC7 | pipeline HTML | user-requested architecture view | user judges the diagram | — |

## Resume protocol

Read this file top-to-bottom; `git log` since `225d4c5` shows what landed.
Continue at the first non-DONE work item. Parked item 8 needs a user decision.
