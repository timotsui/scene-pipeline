# 2026-07-14 handoff — surrogate bridge, GLTS comparison, composition v0

## Where this session ended

The full chain ran E2E but the recreate output quality is BAD (user verdict on
the composite views). NEXT SESSION: break down and rework **stage by stage,
starting with RETRIEVAL and PLACEMENT** — v0 treated them as one shot; they
need to be developed and judged per-object, not per-scene.

## What exists and works (plumbing verified)

- **Claude agent surrogate** for all LLM/VLM calls (subscription, sonnet):
  - TreeSearchGen: `utils/get_claude_agent.py` + `utils/backend.py`
    (`MODEL_BACKEND=claude`), launcher `run_test_claude.sh`
    (PROJECT_ROOT/BENCHMARK_INSTRUCTIONS env-overridable).
  - composition module: `scene-pipeline/composition/bridge.py` (same wrapper,
    Windows-native). Gotcha both share: a stale INVALID Windows User-level
    ANTHROPIC_API_KEY must be stripped from the env or claude.exe fails.
- **GLTS baseline complete** on the shared prompt (Cozy Sunlit Study Bedroom =
  bedroom_marble's Marble prompt): `TreeSearchGen/output_glts_bedroom/0/`
  (layout pngs, top/side renders, 16_scene.glb). 156 calls, ~87 min, 0 failures.
- **Frame fixes (07-05 stale-code list closed):** envelope.py (upright-internal
  compute, grid mapped back to raw), agent_package.py (up=−y GUIDE, elevation
  filter, `mount: floor|wall` contract), render_proposal.py (raw→render box
  projection replaces st_mirror; up-sign floor check). All user-verified on
  bedroom_marble.
- **composition module** (`scene-pipeline/composition/`): compose_scene.py
  orchestrator (`--mode recreate|augment --until propose|retrieve|place|loop`),
  recreate.py / retrieve.py / assets_thor.py / place.py / jiggle.py.
  Checkpoint gates at retrieval + placement; jiggle loop never run (user
  skipped). pyrender installed --no-deps (torch untouched).
- **Comparison package:** `out/glts_comparison_2026-07-14/COMPARISON.html`
  (stats: ours 19 calls/~2.5 min vs GLTS 156/~87 min; paired renders; both glbs).

## Method definition (user, this session — the important part)

Ours = **RECREATE**: the lifted manifest IS the layout ("pick object after
layout"). Every box gets retrieve-&-replace from the asset library, matching
description AND dimensions; when nothing fits a box whole, compose multiple
assets (two shelves end-to-end, several small pictures for one big one — the
tiling in recreate.py worked: shelf ×2). The LLM-propose flow (augment mode)
is a LATER enrichment pass; the GUIDE/manifest does most of the work.

## Known v0 failures to attack next session

1. **Retrieval scoring:** token overlap lets descriptions hijack categories
   (rug → "footstool with a red rug on it" ×2). Ideas: category-weighted or
   CLIP scoring; top-N alternates per box with a VISUAL pick (render variants,
   VLM/user chooses) — user prefers this over positional jiggling.
2. **Label noise from lift:** "poter" → chocolate box. Sanity-check labels
   against view crops (seg 2D boxes exist) before retrieval.
3. **Placement/compositing:** no occlusion (meshes pasted over splat), no
   lighting match, uniform height-only scaling, no orientation canonicalization
   (yRotOffset/pose_z_rot_angle in annotations unused → objects can face wrong
   way), axis-aligned only.
4. Wall objects centered at box center (fine), floor snap threshold 0.25 m
   (untested edge cases), rug-like flat objects need a flat-asset class.

## Rerun commands

- GLTS leg: `wsl -d Ubuntu-24.04`, repo TreeSearchGen,
  `PROJECT_ROOT=... BENCHMARK_INSTRUCTIONS=... bash run_test_claude.sh 13`
- Ours: `python composition/compose_scene.py --scene bedroom_marble --mode
  recreate --until place` (Windows python; --until place = stop before loop)
- Viewer: `python entangled_gen/viewer/serve.py --scene bedroom_marble --port 8321`

## Not committed

All of today's scene-pipeline changes + the TreeSearchGen bridge files are
uncommitted (scene-pipeline commits as Timotsui / timotsuihc@gmail.com).
