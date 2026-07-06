# entangled_gen — generated-splat leg

Prompt → generated 3D scene (Gaussian splat) → extracted, verifiable scene
representation → LLM/agent composition. Stage-by-stage file contracts (and how
to swap any stage's method): **`PIPELINE.md`** — read that first.

## Quick start

1. `cp local_paths.json.example local_paths.json` and fill in the data roots
   (`out` = the ~15 GB scene-data home; `week5` = real-scan data for
   realplayroom).
2. CPU stages for a scene that already has views+seg:
   `python scene_ready.py --scene bedroom_s1` (lift → package → viewer prep →
   envelope, by mtime; use `lift_views.py --scene X` to force a re-lift).
3. Live viewer: `python viewer/serve.py --scene bedroom_s1 --port 8321` →
   http://localhost:8321 — point cloud + manifest boxes + placement editing.
   Display-rot boxes in the HUD (default z=180 = upright, user-verified);
   coordinates shown are always RAW frame.
4. Generation (GPU/WSL): see `gen/scenedreamer360/README.md`.

## Coordinate frame (resolved 2026-07-05 — don't relearn this the hard way)

Raw gen plys are "upside-down": upright world = raw **rotated 180° about Z**
(−x,−y,+z; det=+1, not a mirror). SuperSplat/splat-transform correct it
silently on import; numpy/Three.js tools see raw. Convention: **stored
coordinates are always RAW frame** (up = `frame.up` = −y ⇒ `floor_y >
ceiling_y`); upright is display/compute-only via `frame.raw_to_render`.
`lift_views.detect_frame` self-calibrates per scene (4 sign hypotheses × all
views vs the webps). New splat source? Verify once with `debug_cube_ply.py`
(color=coordinate cube) + your eyes, and `debug_frame_hypotheses.py` for the
numeric screen.

## Current status (2026-07-05 checkpoint)

- CORRECT & user-approved: bedroom_s1 manifest + overlays (calib rot180 0.940).
- STALE data (old wrong frame, re-lift/regen pending): other 8 manifests incl.
  realplayroom; all envelopes; all agent packages; report.
- STALE code (up=+y assumptions, fix before running): `envelope.py`,
  `agent_package.py`, `render_proposal.py`, `suggest_spots.py`.
- Segmentation outputs are 2D and valid everywhere.

Session history and the original long-form module doc: `docs/`.
