# scene-pipeline

Text → generated 3D scene (Gaussian splat) → extracted scene manifest →
asset-based recreation → VLM refinement loop. Research pipeline (CS 8903,
Summer 2026), modularized by stage; each module is a subfolder.

## The end-to-end chain (complete as of 2026-07-15; side lanes 07-21/22)

```
text prompt
  → world generation (Marble; harvest bundle = pano + splat + collider + prompt)
  → splat renders (yaw views, camera sidecars)                 entangled_gen/
  → detect + segment (GroundingDINO + SAM) → depth-lift
  → scene_manifest.json  (+ amodal box extension, stage 4.5)
  → recreate chain C1–C6 (shortlist → measure → CLIP → pick → place)
                                                               composition/
  → C7 loop: VLM propose→verify {add, nudge}, deterministic
    mesh-collision gating, edits.jsonl trace
  → composed_state2.json + composed_scene2.glb

side lanes (entangled_gen/, 2026-07-21/22):
  cut/       GaussianCut object removal → background.ply (ghost fix)
  analyzer/  external splat_analyzer detections vs our manifest
  graph/     semantic scene graph over all extractions (ACTIVE)
```

Every arrow is a per-scene file contract with a working implementation
(reference scene: bedroom_marble). Where the shape is done but quality is
open: verify-judge sensitivity, facing initialization, the asset-catalog
ceiling, and the deferred loop ops (swap / remove / flip_facing).

Stage docs, in reading order:

1. `entangled_gen/PIPELINE.md` — gen → views → seg → lift contracts (+ pano,
   cut, analyzer, graph lanes), the frame convention, what the sources can
   and cannot know.
2. `composition/README.md` — recreate chain C1–C6 + the "C7 loop contract".
3. `entangled_gen/docs/PLAN_*.md` — active plan+progress docs
   (`REVIEW_LOG.md` = pending user verdicts); `PLAN_REPO_CLEANUP.md` (root)
   = the 2026-07-23 isolation cleanup.
4. `entangled_gen/docs/SESSION_*_HANDOFF.md` — session-by-session findings,
   newest first.

## Modules

| module | stage |
|--------|-------|
| `entangled_gen/` | generated-splat leg: generate (swappable methods under `gen/`) → render views → segment → depth-lift → `scene_manifest.json` → envelope → LLM composition package + live placement viewer. Sub-lanes: `cut/` (object removal), `analyzer/` (detection comparison), `graph/` (scene graph) |
| `composition/` | recreate the lifted scene from library assets (objathor): C1–C6 chain + C7 VLM refinement loop + `collide.py` mesh-collision check + review/asset viewers |
| `real_scan/` | FROZEN, optional side module (not needed for the main chain): real-scan leg (ex week5/splat_to_placement) — candidate triage, SOG/InteriorGS decoding, clean/render/plan tooling, agent starter pack. Kept for a possible works-on-real-captures generality experiment |
| `proposer/` | seed module, docs+data only (no code): describe a real scene → composition proposal protocol for a Holodeck/GLTS-style composer |

**Isolation rule:** stages talk ONLY through per-scene files — the contracts
(and how to swap in an alternative method for any stage) are in
`entangled_gen/PIPELINE.md` and `composition/README.md`. Exactly one
sanctioned cross-module code seam exists: `composition/comp_paths.py` imports
`entangled_gen/paths.py` (every composition file routes through it).

## Data

Heavy data (splats, renders, caches — ~15 GB) is **not** in this repo.
Machine-local roots live in a gitignored `entangled_gen/local_paths.json`
(copy `local_paths.json.example` and fill in): the per-scene `out/` root, the
week5 data checkout, the objathor asset dump, and the claude.exe bridge
settings. `entangled_gen` reads it via `paths.py`; `composition` reads the
same file via `comp_paths.py`. `real_scan`/`proposer` carry no wired data
paths (frozen/seed).

## Coordinate frame (hard-won, user-verified 2026-07-05)

Raw 3DGS plys from the generator are stored "upside-down": the upright world is
the raw coordinates **rotated 180° about Z** (−x, −y, +z; a rotation, not a
mirror — SuperSplat/splat-transform apply it silently on import). This repo's
convention: **all stored coordinates are RAW frame** (physical up = −y,
`floor_y > ceiling_y`); upright is display/compute-only via
`frame.raw_to_render`. See `entangled_gen/docs/SESSION_2026-07-05C_HANDOFF.md`.
