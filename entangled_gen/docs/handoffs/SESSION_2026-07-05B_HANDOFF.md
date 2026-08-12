# Session handoff — 2026-07-05 evening (verification session)

> Start here next session. Companion: `OVERNIGHT_2026-07-05.md` (previous session),
> `out/README.md` (new layout map).

## ⚠️ THE HEADLINE: x-mirror fix is likely INCOMPLETE — true transform is probably a 180° ROTATION

**User's decisive observation (end of session):**
- `gen_raw.ply` dragged into SuperSplat web UI → **right-side-up, landmarks match generator pano**.
- Same ply in our viewer (:8321, draws raw coords) → **upside-down, chirality CORRECT** (not a mirror).

Upside-down + not-mirrored + left-right preserved = **180° rotation (−x, −y, +z), det=+1**.
Interpretation: gen PLYs are in the standard 3DGS **Y-DOWN** convention (COLMAP heritage);
SuperSplat silently corrects it; our tools don't.

**Supporting numeric evidence (was wrongly dismissed mid-session):** world-space correlation
of point renders vs actual webps, bedroom, 4 views (yaw000/090/180/270):
- x-mirror only (current lift model): 0.87 / 0.54 / **−0.06** / 0.27
- x-mirror + v-flip (= the 180° rotation): **0.92 / 0.94 / 0.86 / 0.89 — wins all 4 views**

**Why the current calibration got fooled:** `detect_st_mirror()` in `lift_views.py` tests only
2 hypotheses (as-is, x-mirror) and calibrates on the FIRST view = yaw000 = the door-panel
close-up, which is vertically quasi-uniform, so the missing y-flip barely hurt its score (0.90).

**If confirmed, this invalidates (all currently suspect):**
- vertical structure of ALL 9 manifests (objects may be glued to the wrong end; floor_y may be the ceiling)
- envelope "floor" maps (may literally have mapped the CEILING) → floor-coverage/warp metrics suspect
- parts of the desk-placement post-mortem in OVERNIGHT doc §5
- NOTE: overlay verification CANNOT catch this class of bug (round-trips through the same camera).
  The "height sanity table" also cannot (a global y-flip flips objects AND floor/ceiling percentiles together).

**Agreed next-session plan (in order, all numeric until step 3):**
1. Read `viewer/index.html` draw code — confirm it displays raw Y unflipped (formally pins the file as Y-down).
2. 4-hypothesis world-space correlation (identity, mirX, mirY, rot180Z) on a vertically
   ASYMMETRIC view (yaw180, not yaw000), for bedroom_s1 AND realplayroom (real scan may have a
   different convention — its 2-hypothesis calibration was near-tied: 0.11 vs 0.08).
3. Fix `detect_st_mirror` → 4 hypotheses + better calibration view; re-lift all 9 scenes
   (`scene_ready` chain), regenerate packages + envelopes; **user re-verifies overlays by eye**.
4. Re-examine envelope/floor logic and the placement post-mortem under the corrected frame.

## Process rules established this session (user directives — follow strictly)
- **Announce what you're about to do BEFORE doing it.** No unrequested script runs.
- **Claude must NEVER judge images or spatial quality on its own.** ALL spatial and image
  understanding (alignment, geometry quality, handedness, up-direction, "does the box fit")
  goes through the user. Claude prepares artifacts + numbers + code citations only.
- Verify assumptions one at a time; no stacking conclusions on unverified assumptions.
- Minimal work to answer the current question; don't gold-plate.

## What was done this session

1. **Recovered post-cutoff state:** x-mirror fix had landed pre-cutoff; all 9 manifests re-lifted
   (16:18–16:21), packages + report regenerated. Overlays spot-checked.
2. **out/ reorganized — one folder per scene** (`out/<scene>/gen_raw.ply, views/, seg/, package/,
   scene_manifest.json, envelope.*, panorama.png, pano_frames/, live_placement.json`).
   All scripts route through new `paths.py` (single source of truth; no playroom special case).
   Shared: `report.html`, `logs/`, `cache/`, `archive/`, `viewer_caps/`, `_debug/`. Smoke-tested
   (make_report, render_proposal bedroom). Docs got layout-note banners only (full doc cleanup deferred).
3. **week5 isolation:** `rendertools/` = local copies of week5 `shot.py` + `03_render.py`;
   everything repointed (paths.SHOT / paths.load_r3()); week5 now touched only for the read-only
   realplayroom data ply. Edit rendertools freely; week5 frozen.
4. **Full pipeline walkthrough documented with the user** (bedroom_s1 as the example scene —
   only scene with surviving gen intermediates).

## Findings log (this session)

- **User-verified:** 4-tile `panorama.png` landmark order MATCHES `generator_pano.jpg` (bedroom_s1).
- **Gen pipeline anatomy (code-verified):** prompt → PanFusion pano (only creative step; enhance
  bypassed) → 30 perspective crops (fullscan: 3 rings × 10 headings, translation=0, ~50° FOV,
  poles beyond ±55° elevation never directly sampled) → per-crop ZoeDepth + greedy merge
  (view 0 anchors world; later views: overlap check → ONE scalar scale fit → append new pixels
  only) → 13.0M-pt cloud → 150 training renders of the cloud → 3DGS (densify off) → ply.
- **Ring-direction quirk (code-verified, harmless):** fullscan horizontal ring sweeps opposite
  direction vs both tilted rings (sin sign flip, trajectory.py:502 vs 513) — user SAW this in the
  crops first. Diagnostic of upstream convention sloppiness.
- **Geometry quality is the METHOD's fault, not ours:** per-crop monocular depth + scalar-only
  alignment is inherited LucidDreamer machinery; SceneDreamer360 only swapped SD-inpainted views
  for pano crops (content consistency ✓, depth consistency unchanged). Pano-native depth models
  (Panoformer/EGFormer, sitting in repos/FastScene) are the untested alternative.
- **gen_raw.ply = exactly 3,000,000 gaussians** (header-verified; deliberate cap from 13M points).
- **1440.mp4 (generator's own splat flythrough) is 8 bytes = empty**; their video writer failed.
  Not worth debugging — SuperSplat/our viewer cover it. (Consequence: we had never seen the splat
  through the generator's own renderer — which delayed catching the rotation issue.)
- **Cache pickles ARE per-scene gen intermediates** for all 8 scenes:
  `out/cache/traindata_<md5(prompt|seed)[:10]>.pkl` = {camera_angle_x, W, H, pcd_points(3×13M),
  pcd_colors, 150 frames(PIL image + transform_matrix)}. Mapping: eefb=playroom, 35f3=bedroom,
  1319=livingroom, fea7=kitchen, 6385=ctrlroom, 2fe1=bedroomdim, b943=livingspatial, eaee=bedroom_s1.
  Extracted previews: `out/bedroom_s1/gen_intermediates/` (pcd top-down/elevation + 4 train frames).
- **panorama.png is currently the 4-tile version** (4×75° views = 300°, so 4×15° blind wedges,
  literal discontinuities at tile seams — expected, not a bug). 12-frame 30°-step sets exist in
  `out/<scene>/pano_frames/` for 5 scenes (overlapping, no wedges) — can re-tile without GPU.

## Where each key artifact lives (quick ref)
- Scene assets: `out/<scene>/…` (see out/README.md table)
- Gen intermediates (bedroom_s1 only): repo predict dir + `out/bedroom_s1/gen_intermediates/`
- Mirror-bug debug panels: `out/_debug/`
- Correlation numbers quoted above: produced by scratchpad script (session-local, gone);
  regenerate via the 4-hypothesis test in next-session plan step 2.
