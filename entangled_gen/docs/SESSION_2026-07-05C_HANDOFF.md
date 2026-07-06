# Session handoff — 2026-07-05 (C, coordinate-saga RESOLUTION session)

> Supersedes SESSION_2026-07-05B_HANDOFF.md (kept for history). Read this first.

## THE RESOLUTION (user-verified, method: cube8 debug splat)

**Upright world = RAW ply coords rotated 180° about Z** — (x,y,z) → (−x,−y,+z), det=+1,
a true rotation, NOT a mirror. The old `st_mirror_x` x-mirror calibration was wrong.

Verification chain (each link either code-read or the USER's eyes — no image judgment
by Claude anywhere):
1. Our viewer draws raw ply numbers verbatim (code: prep_scene.py takes x,y,z as-is;
   index.html copies the buffer verbatim; Three.js +y-up).
2. `debug_cube_ply.py` → `out/_debug/cube8.ply`: 8 corner balls of a 2 m cube,
   color = coordinate (R⇔x+, G⇔y+, B⇔z+, 2000 jittered gaussians per corner).
   USER compared SuperSplat vs our viewer with it and keyed SuperSplat's rotation
   boxes: **un-rotating z by 180 reproduces our raw view exactly** → SuperSplat
   (and by extension the PlayCanvas family incl. splat-transform) applies rot180Z
   on import.
3. USER confirmed the 4 gpu yaw webps are upright and sweep anticlockwise
   yaw000→270 = positive rotation about +y (right-hand rule) — chirality check:
   a hidden mirror would have read clockwise.
4. 4-hypothesis correlation screen (`debug_frame_hypotheses.py`, numbers only):
   rot180 wins all 4 bedroom_s1 views (0.91–0.96; mirX NEGATIVE on yaw180) and
   8/10 realplayroom views (mean 0.186 vs 0.093) → same convention for the week5
   real scan.

## ARCHITECTURE DECISION (user's call): RAW frame everywhere

Storage frame = raw ply frame, full stop. Upright is only ever an explicit
display/compute transform. Consequences: physical up in raw = **−y**, so
`floor_y > ceiling_y` numerically in manifests; "on the floor" =
`center_y = floor_y − h/2`.

New manifest `frame` contract (see bedroom_s1's manifest for a live example):
```
space: "raw"                  up: [0,-1,0]  (physical up, raw coords)
floor_y / ceiling_y           physical floor/ceiling y in RAW coords (floor > ceiling)
extent_p1 / extent_p99        raw-frame room extent
raw_to_render: [-1,-1,1]      elementwise, self-inverse; render = webp/SuperSplat space
frame_hypothesis: "rot180"    frame_calib_corr: {identity, mirX, mirY, rot180}
calib_views: 4
```

## Code changed this session

- `lift_views.py` REPAIRED + fixed: `detect_st_mirror` (2 hyp, 1 view) →
  `detect_frame` (4 hypotheses, mean over ALL detection views — single-view
  calibration was fooled by the vertically-uniform yaw000 close-up). Lifts in
  render space (masks/cams live there), transforms boxes back to raw via
  `sign_box`; writes the new frame block; plan-view band + floor percentiles
  are up-sign aware.
- `viewer/index.html`: worldGroup wrapping all content + SuperSplat-style
  display-rot degree boxes (x/y/z), **default z=180 (user-verified upright)**,
  `?rot=` override; world-space axis triad at origin (red=+x, green=+y, blue=+z,
  same code as cube8 colors); ceiling-clip made up-sign aware; manifest boxes
  now per-object palette colors MATCHING manifest_overlay_*.png (same palette,
  same index), edges depthTest:false so points can't swallow them; 3D labels
  show the object name only; start pose = (0,0.15,−0.6) looking at origin,
  orbit pivot at origin. All picking/placing converts rays to raw frame
  (`rawRay`) — coords stay raw everywhere.
- NEW `debug_frame_hypotheses.py` (4-hyp correlation table, any scene) and
  `debug_cube_ply.py` (the cube; regenerate with different SIZE/PTS if needed).
  cube8 is prepped as a viewer scene (`viewer/data/cube8.bin`).
- `paths.py` docstring updated (frame contract pointer).

## Current state per artifact

- **bedroom_s1: CORRECT & USER-APPROVED** — manifest (15 objects, calib rot180
  0.940), overlays, viewer boxes checked by eye in the viewer. Note: all 15
  objects are single-view; the label-based merge joined nothing (obj_008
  dresser ≈ obj_011 nightstand are plausibly one object). Open quality topic,
  not a frame bug.
- **STALE (old x-mirror frame, must re-lift):** manifests of bedroom, bedroomdim,
  ctrlroom, kitchen, livingroom, livingspatial, playroom + realplayroom
  (realplayroom needs `--views-dir ../../week5/splat_to_placement/package/views`).
  `scene_ready.py` will NOT auto-re-lift (its trigger is only the missing
  extent_p1 field) — run `lift_views.py --scene X` explicitly.
- **STALE (all scenes incl. bedroom_s1):** envelope.npz / envelope_heatmap /
  viewer `*_clearance.json` (envelope.py still assumes up=+y AND reads raw ply
  without the frame transform — its floor logic currently finds the ceiling);
  agent packages/GUIDE (contract formula `center_y = floor_y + h/2` assumes
  up=+y; GUIDE must state up=−y in raw); report.html.
- **STALE CODE (will misbehave with new manifests, don't run until fixed):**
  `render_proposal.py` (st_mirror block + `floor_y + h/2` check),
  `suggest_spots.py` (`floor_y + dev + H/2`), `envelope.py` (above),
  `agent_package.py` (GUIDE text/formulas). `splat_place.py` takes explicit CLI
  coords — document that they're raw-frame.
- Viewer server was left running on :8321 (default scene cube8).

## Next steps (in order, each gated on the user)

1. Fix `envelope.py` for up=−y (cleanest: rotate points to upright internally
   via frame.raw_to_render, compute, then map the grid back to raw x/z —
   remember rot180 negates x, so grid x0 flips too). Regenerate bedroom_s1
   envelope; user checks the clearance overlay in the viewer.
2. Fix `agent_package.py` (GUIDE frame section + contract formulas, explicit
   up=−y) and `render_proposal.py` (drop st_mirror, up-sign floor check);
   `suggest_spots.py` same. Regenerate bedroom_s1 package.
3. Re-lift the other 8 manifests; user spot-checks a couple in the viewer;
   regenerate their envelopes/packages/report.
4. Then back to the original agenda (composition experiments, scene proposer).

## Process rules (unchanged, follow strictly)
- Make a plan and tell the user BEFORE doing anything; wait for go-ahead.
  Design forks inside an agreed step still require asking.
- Claude NEVER judges images/spatial quality — user's eyes only. Claude
  prepares artifacts + numbers + code citations.
- One assumption at a time; minimal work per question.
