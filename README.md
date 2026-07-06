# scene-pipeline

Text → generated 3D scene (Gaussian splat) → extracted scene manifest →
LLM/agent-driven composition. Research pipeline (CS 8903, Summer 2026),
modularized by stage; each module is a subfolder.

## Modules

| module | stage |
|--------|-------|
| `entangled_gen/` | generated-splat leg: generate (swappable methods under `gen/`) → render views → segment → depth-lift → `scene_manifest.json` → envelope → LLM composition package + live placement viewer |
| `real_scan/` | real-scan leg (ex week5/splat_to_placement): candidate triage, SOG/InteriorGS decoding, clean/render/plan tooling, agent starter pack |
| `proposer/` | scene-proposer stage (seed: week5 proposer experiments; real scene → composition proposal for a Holodeck/GLTS-style composer) |

(Planned next: composition/verification module; modules are incomplete by
design — this repo is the single home for the pipeline as it grows.)

Stages talk only through per-scene files — the contracts (and how to swap in an
alternative method for any stage) are in `entangled_gen/PIPELINE.md`.

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
