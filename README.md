# scene-pipeline

Text → generated 3D scene (Gaussian splat) → extracted scene manifest →
LLM/agent-driven composition. Research pipeline (CS 8903, Summer 2026),
modularized by stage; each module is a subfolder.

## Modules

| module | stage |
|--------|-------|
| `entangled_gen/` | generated-splat leg: render views → segment → depth-lift → `scene_manifest.json` → envelope → LLM composition package + live placement viewer |

(Planned next modules: scene proposer, composition/verification.)

## Data

Heavy data (splats, renders, caches — ~15 GB) is **not** in this repo. Each
module reads machine-local roots from a gitignored `local_paths.json`
(copy `local_paths.json.example` and fill in your paths).

## Coordinate frame (hard-won, user-verified 2026-07-05)

Raw 3DGS plys from the generator are stored "upside-down": the upright world is
the raw coordinates **rotated 180° about Z** (−x, −y, +z; a rotation, not a
mirror — SuperSplat/splat-transform apply it silently on import). This repo's
convention: **all stored coordinates are RAW frame** (physical up = −y,
`floor_y > ceiling_y`); upright is display/compute-only via
`frame.raw_to_render`. See `entangled_gen/docs/SESSION_2026-07-05C_HANDOFF.md`.
