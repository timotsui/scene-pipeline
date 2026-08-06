# PLAN — SCENE #2: living_marble (the generality run)

**Session start: 2026-08-05 ~23:00** (note: SESSION_*_HANDOFF names run
ahead of real dates; the "08-07" handoff was written 08-05 22:37).
Continues SESSION_2026-08-07_HANDOFF.md ("NEXT SESSION — SCENE #2").

## THE POINT

First full run of the canonical chain on a scene it was NOT built on.
Scene #1 = bedroom_marble (everything tuned there). Scene #2 tests
generality: same realistic style, different room + furniture vocabulary.
Fix-at-the-source rules apply: any failure here gets fixed
scene-agnostically, never with a living-room special case.

## THE SCENE

- **World `484c93f0-9abb-47e6-8ab4-087e5bd0c96c`** — "contemporary
  living room, realistic style, modern elegance" (user-picked from the
  7-thumbnail shortlist, 2026-08-05).
- Bundle (verified complete on disk):
  `CS-8903-OVM\week8\marble-harvest\worlds\484c93f0-9abb-47e6-8ab4-087e5bd0c96c\`
  — splats.spz 28.9 MB · collider.glb 3.6 MB · pano_rgb_0..3.png ·
  prompt.txt. No browser harvest needed (pre-downloaded in the catalogue
  sweep; catalogue = week8\marble-harvest\catalog\).
- Scene name: **living_marble** (bedroom_marble convention).
- out root (local_paths.json): `CS-8903-OVM\week7\entangled_gen\out\living_marble\`

## PROTOCOL

- pipeline_map.html is the authority; stage commands are read from it at
  execution time. Any deviation = warn + explicit approval first.
- Every checkpoint = USER GATE: I stop, hand over review stimuli
  (module contract first: what it got / what it decided / what a mistake
  looks like), user verdicts land in REVIEW_LOG.md. I do NOT conclude
  from images.
- This doc is updated at every state change. Resume protocol: read this
  doc top to bottom, then the newest REVIEW_LOG entries.

## CHECKPOINTS

| CP | Stage (pipeline_map order) | Gate stimulus | Status |
|----|---------------------------|---------------|--------|
| 0 | Setup: spz→ply (splat-transform, same as bedroom), bundle_path.txt, prep_scene.py → viewer dropdown | scene in viewer :8321 — first one-look (ALSO covers the pending decluttered-HUD eyeball) | ✅ USER PASS 08-06 (R-S2-0/2) |
| 1 | Pano self-render (funnel stage 1, recentered) | pano strip | ✅ USER PASS 08-06 (R-S2-2) |
| 2 | Crop rig (funnel stage 2, f30) | crop contact sheet | ✅ ran · ⏸ AT GATE (R-S2-3) |
| 3 | Vocab (from prompt.txt) | vocab list | ✅ ran, 2 source fixes · ⏸ AT GATE (R-S2-3) |
| 4 | Detect | detection overlays | ✅ ran (crash → capped re-run, 20/20) · ⏸ AT GATE (R-S2-4) |
| 5 | Lift | boxes projected into RGB views (NOT plan views) | ✅ ran (18/20 cams, 75 obj) · ⏸ AT GATE (R-S2-5) |
| 6 | Merge / recenter | merged manifest overlay | ✅ ran (65 obj → f30 66) · ⏸ AT GATE (R-S2-6/7) |
| 7 | Room shell | room_shell_audit.png + collider deltas | ✅ ran (extent-clip fix; 4 walls 5–20mm) · ⏸ AT GATE (R-S2-11, W3 open-boundary ruling) |
| 8 | Graph record + judge passes | graph_review.html | ✅ ran (100→51, all self-checks PASS) · ⏸ AT GATE (R-S2-12) |
| 9 | S1–S4 shopping | shortlist/pick pages | ✅ ran (33 anchors, 0 NO_MATCH) · ⏸ AT GATE (R-S2-13/14) |
| 10 | PH1 snap | fitted preview | ✅ ran (sofa refit 8/9 views) · ⏸ AT GATE (R-S2-13) |
| 11 | PH2 fit loop + PH2a | loop report | ✅ DRY r4; rotation recorded, 0 applied · ⏸ AT GATE (R-S2-15) |
| 12 | Sub rounds (sub_round_all.py) | sub-round fleet review | ✅ ran (12 subs — THIN, see R-S2-16) · ⏸ AT GATE |
| 13 | build_subs_preview.py — full fleet | subs preview 15-point check | ✅ ran · ⏸ AT GATE (R-S2-16) |

## WATCH LIST (from the 08-07 handoff, all still live)

1. **Room YAW** — boards/intervals/jiggle are world-axis-aligned; the
   pipeline only does 4 discrete flips, no continuous yaw estimate.
   bedroom was ~5.5° yawed and survived; check cp2 board rects EARLY.
2. **Y_BLOCK_MIN 0.10** — tuned on ONE bed.
3. Anchor-loop five: DRY 0.65 · HUG 0.30 · MARGIN 0.15 · FLAT 0.06 ·
   dual-attach 0.10.
4. cp2 board constants: UP_DOT 0.65 · GAP 0.035 · MIN_AREA 0.02 ·
   MIN_SPAN 0.12 · PLANK_MAX 0.06 · UNDERSIDE_AREA_FRAC 0.3.
5. Multiplicity: blunt rowable gate (book/books) is the interim stand-in;
   anchor-tier tiling is PRE-GATE (rug-style tiles may be legit).
6. **SCENE PROPERTY (noted at CP0): short ceiling.** living_marble is
   ~2.2 m floor-to-ceiling (splat extents AND collider agree) on a
   4.6 × 7.8 m footprint — vertically compressed vs the bedroom's 2.8 m.
   Watch at CP7 (shell) and S1–S4 (real-world-sized assets in a short
   room); also why the default 1.6 m viewer eye feels high here (user
   noticed 2026-08-05; rig origin sits at 1.09 m = exact mid-height).

Any of these firing wrong on living_marble = fix at the source,
scene-agnostic, with a bedroom_marble regression check.

## CP1 BOOTSTRAP FINDINGS (2026-08-06 ~00:30)

1. **pano_stitch.py fresh-scene bug confirmed** (reads the retired
   scene_manifest_sweep.json for floor/up; crashes on any new scene).
   Fix plan approved by user: collider bootstrap → frame_bootstrap.json
   → 3-line pano_stitch fallback.
2. **collider_register.py ran on living and flagged ITSELF suspect**
   (dist_p50 0.109 > 5cm; picked a det=-1 mirror at coarse IoU 0.174 vs
   bedroom's clean 0.511). Probes show the ALIGNMENT is fine and the
   SCORING is what breaks on this scene type:
   - plane-lock under IDENTITY: floor y=-1.069 delta 0.0 cm; x-walls
     -1.829/+1.843 delta 0.0 cm both. Identity is the true T (±icp).
   - **scene property: OPEN-PLAN + PARTIAL COLLIDER.** Splat has no
     z-walls (ends of the 7.8 m space are open); the collider covers
     only ~60% of the footprint (23 m² floor vs 36 m²) and CAPS its
     open ends with artificial planes at z=-2.49/+3.78. Global
     voxel-IoU/coverage metrics are meaningless here (coverage 0.22
     with perfect alignment). ⚠ CP7: shell must not read cap planes
     as walls. ⚠ collider_registration.json on disk = the suspect
     mirror T — DO NOT CONSUME until re-registered (plane-lock fix).
   - **y-symmetry trap:** camera at mid-height (room -1.09..+1.11) →
     floor and ceiling ridges mirror onto each other; plane evidence
     alone CANNOT decide up-sign or rule out mirrors on this room.
     The bundle pano (always upright by Marble convention) is the
     scene-agnostic tie-breaker. User eyeball already confirms up=+y
     for living (blind-test target for the bootstrap method).
3. CP0 mirror check (window side vs pano_rgb_0) is now LOAD-BEARING —
   geometry cannot exclude an x-mirror on this near-symmetric room.

## BOOTSTRAP BUILT + VALIDATED (2026-08-06 ~01:30)

- **User ruling reshaped the design**: "splat+collider matching IS the
  product" — bootstrap TRUSTS the bundle and VERIFIES (identity
  plane-lock), searches nothing. Old-vintage scenes fail the verify
  loudly and keep the search path (bedroom untouched).
- **frame_bootstrap.py** (new stage): (1) collider floor plane, (2)
  identity plane-lock vs splat ridges, (3) handedness + up via coarse
  CPU equirect correlated against the bundle pano over the 4 sign
  classes × yaw shifts. Living: floor/x-walls lock 0–2 cm (z caps =
  noise-mass, tolerated as open ends); pano picks -x+y+z at 0.824
  (margin +0.27) → up=+y CONFIRMED, NO MIRROR — the CP0 mirror eyeball
  is no longer load-bearing. Writes frame_bootstrap.json + identity
  collider_registration.json + collider_registered.glb (REPLACED the
  suspect mirror from the earlier search run; user had spotted that
  mirrored mesh in the viewer live).
- **Blind control PASSED**: same pano method on bedroom (from its eye
  height −1.571; old pano = foreign camera, origin-render was mud)
  rediscovers +x-y+z at 0.53 — the established A2 convention.
- **pano_stitch.py**: frame source = legacy sweep manifest (bedroom
  bit-identical, signs [1,-1,1]) → frame_bootstrap.json (fresh scenes,
  signs from pano check, mirror-x for y-up vintage); mapping + meta
  sign-aware. Cube-face cameras untouched (renderer+stitcher share the
  same up convention — consistent pair, geometry-safe on any vintage).
- Note: pano_stitch's legacy mechanical verify (crop vs direct SP1
  render) only fires when sp_*.png exist — living has none; the CP1
  user gate is the visual check for fresh scenes.

## RESET (2026-08-06, user-ordered after trust break at CP1 gate)

User saw: mesh upside-down in viewer + our pano front/back-rotated vs
Marble's. Diagnosis, verified not theorized:
- Mesh file on disk was CORRECT (GLB vertex bounds byte-identical to the
  shipped bundle mesh). The upside-down view = the browser session still
  holding the EARLIER genuinely-mirrored mesh (bad registration output,
  overwritten mid-session; viewer fetched the mesh once per page load).
  FIX: collider fetch now cache-busted (index.html); frame_bootstrap
  writes the registered mesh as a BYTE-COPY of the bundle file, no
  trimesh round-trip.
- Pano front/back = 180° yaw start-direction choice, the documented
  sign-class equivalence (sx,sy,sz)~(-sx,sy,-sz); downstream never
  compares against Marble's pano. Cosmetic.
Executed: killed ALL derived living artifacts (rig_sp0, gen_raw,
registered mesh+json, bootstrap json, viewer bin) and rebuilt from the
raw bundle: convert → bundle_path → byte-copy mesh → prep_scene →
frame_bootstrap (same numbers reproduced: floor -1.069, -x+y+z 0.824).
CP1 pano NOT re-rendered — awaiting user's viewer one-look first.

## RAW BUNDLE VIEW (2026-08-06, user-ordered)

User: "put in the raw mesh and splat straight from marble download."
Built viewer/raw.html + serve.py routes /raw, /bundle_splats.spz,
/bundle_collider.glb — streams the bundle files THEMSELVES (spz decoded
natively by the vendored lib; glb as shipped; no conversion, no copy on
disk, no display rotation, no pipeline code in the path). Ground-truth
page for any scene with a bundle_path.txt. Server restarted (pid 44376);
routes verified (spz 30,336,296 B, glb 3,782,364 B = exact bundle sizes).

## FRAME SAGA RESOLUTION + RULE-1 COMPLIANCE (2026-08-06 ~03:00)

**THE ACTUAL TRUTH (supersedes the 'vintage mismatch' and 'identity
verify' sections above — kept as the evidence trail):**
- Marble bundles are internally CONSISTENT (user's claim, correct):
  living's spz storage == collider frame (verified by direct spz byte
  decode). The bundle frame is y-down.
- **splat-transform's spz→ply conversion applies rot180-about-x
  (y,z negated) — ALWAYS.** The pipeline frame (gen_raw.ply, all
  stages) = rot180x(bundle). All tonight's confusion was this one
  constant, hidden by the room's y-symmetry (camera at mid-height).
- Every user report was correct: raw view upside-down = faithful
  bundle y-down; main-viewer mesh upside-down = byte-copied (unrotated)
  collider REALLY was 180° off the ply (NOT stale cache — that
  explanation was wrong); 'product matches on its own' = true.
- Bedroom nuance: its old-vintage collider genuinely differs from its
  spz by ~0.95 scale + shift (not just the converter constant), so its
  SEARCHED registration stays grandfathered. New-vintage bundles that
  violate the contract fail intake's self-check loudly.
- CP0-era 'up=+y, floor −1.07' bootstrap values were correct FOR THE
  PLY FRAME (color-fingerprint vs Marble pano: floor/ceiling matched to
  ±0.01); the pano check and CP1 pano were right all along.

**RULE-1 COMPLIANCE (user re-invoked the prime directive):** all probing
machinery deleted from the pipeline. frame_bootstrap.py rewritten as the
SCENE INTAKE module: trust bundle + converter constant, zero estimation
(convert if needed → collider × rot180x → floor/ceiling from rotated
collider bounds → constant pano signs), one loud self-check (collider
bounds ⊂ splat bounds ±0.5 m). Hand-made artifacts DELETED and
reproduced blind by the module: floor −1.077, ceiling +1.105, eye
+0.523, pano re-stitched by the module chain. Scene #3 intake = write
bundle_path.txt, run frame_bootstrap.py, done.

## FINAL FRAME DESIGN — BUNDLE FRAME PIPELINE-WIDE (2026-08-06, user-directed)

Supersedes the earlier "canonical = converter output" intake. The full
causal story (user-driven forensics): the 07-07 manual bedroom download
was a DEPRECATED Marble encode (same world re-downloaded in the harvest
sweep = different bytes: fracBits 10→12, origin floor→eye, orientation
flipped — Marble re-exported platform-wide ~mid-July; all 318 harvest
worlds are one uniform encode, header-sweep verified). Within every
bundle, spz==collider (one frame, y-down). The pipeline's tuned frame
(old bedroom ply) equals that bundle frame class.

DESIGN (user: "do the same as bedroom" / "trust the downloads"):
- intake (frame_bootstrap.py): `splat-transform <spz> -r 180,0,0
  gen_raw.ply` — the -r UNDOES the converter's hidden rot180-about-x, so
  the ply == bundle frame exactly. Collider = byte-copy (T identity).
  floor/ceiling from collider bounds (floor_y > ceiling_y, y-down).
  Verified on living: ply floor slab +1.07 warm/wood (R-B +0.229 vs pano
  floor sig +0.227), ceiling -1.07 bright (+0.129 vs +0.121).
- pano_stitch: single A2 convention again (sign-class branch deleted);
  frame source = sweep manifest else frame_bootstrap.json (same schema).
- viewer: rz=180 default for ALL scenes again (special case deleted);
  serve.py /meta.json feeds pre-manifest floor/ceiling from
  frame_bootstrap.json. Raw page + collider cache-buster kept.
- Regenerated blind: intake → prep_scene → pano (eye -0.523). Axes layer
  now reads like bedroom's (+y down) BY DESIGN.
- Queued: bedroom_harvest regression (d113b1c8 = same world, current
  encode; old bedroom_marble = grandfathered reference archive).
  ⏸ USER CHECK pending: viewer + pano composite (cp1_pano_gate_v2.jpg).

## RUN TO NORMALIZATION (2026-08-06 morning, user: "run untill we can
do the size normalization" — stages run back-to-back, review artifacts
batched for the user)

- CP2 crop rig: 20 crops ✓ (crop_pano.py, pure CPU).
- CP3 vocab: TWO SOURCE FIXES first —
  1. find_pano glob missed harvest naming (pano_rgb_0.png vs the old
     "<title>_pano.png") → VLM observation leg silently empty on every
     harvest scene. Glob broadened (both vintages).
  2. Flowery prompts leak abstractions ("elegance","warmth","sense")
     through the noun funnel → new CONCRETENESS PASS (one haiku call,
     doctrine-compliant: LLM judgment not curated list; degrades
     conservatively; drops recorded in vocab.json diff).
  Result: 20 concrete terms (10 prompt + 15 pano; door ✓ = future
  normalization anchor; figurine/vase/basket = pano improvisations).
- P3 seg_batched (GPU) launched in background (task brqcu0qsc).
- NEXT after P3: pano_lift → pano_recenter → manifest_filter, then the
  SIZE NORMALIZATION design lands with real lifted object sizes.

## CRASH + RECOVERY (2026-08-06 01:18 → 01:5x)

- Machine HARD-POWERED-OFF at ~01:18:50 during seg view 20/20 — the known
  power-delivery fault ([[laptop-gpu-crash]]): kernel-power 41, bugcheck 0,
  no button, no WHEA, power vanished mid-inference 96 s into the burst.
  --pace 2 was on → pacing reduces but does NOT prevent.
- Damage audit: 19/20 views' masks intact (valid NPY/PNG headers, no NTFS
  zero-fill) BUT detections.json was end-of-run-write only → all 19 views'
  label/box records died with the process.
- FIX APPLIED + VERIFIED: `nvidia-smi -lgc 0,1500` (admin; `-pl` OEM-locked).
  Full 20-view seg re-run under the lock: peak 93.8 W / 1500 MHz / 65°C
  (vs ~190 W spikes), clean. ⚠ Lock resets on reboot — re-apply before GPU
  stages. Seg stage now COMPLETE (20/20 + full detections.json).
- SOURCE FIX (user-approved): seg_batched.py now rewrites detections.json
  after every view (crash loses ≤ the in-flight view). Scene-agnostic.
- Crash-surviving work committed: 2080c98 (vocab fixes + plan doc).

## ⭐ STATE CHECKPOINT — N1 NORMALIZATION DONE, CLEAN HANDOFF (2026-08-06 ~14:30)

USER-ORDERED clean state ("as if you just finished normalization"):
- **Scene state on disk = normalized (s=0.699, ×1.431) and coherent:**
  ply + collider + frame block (scale_applied guard set) + pano (eye
  −0.059 = true 1.6 m) + crops + seg + manifests (f30: 64 obj, floor
  1.556) + lift pool + diffs + scene_scale.json evidence. Originals =
  `*_prescale.*`. Audit verified floor/pool/graph-frame agreement.
- **Archived (MOVED, not deleted)** →
  `archive_2026-08-06_pre_normalization/`: `compose_prescale_era/`
  (the whole pre-norm compose run incl. fitted/subs previews) and
  `postN1_partial_chain/` (shell + envelope + scene_graph.json with
  20 partial J1 verdicts from the killed P1-re-entry run).
- **KEPT: all judge caches** (graph/*_cache.json) — the redo of
  J0/J1 verdicts re-hits them where stimuli match.
- **PROTOCOL RULING (user):** N1 = STATE TRANSFORM — multiply the
  meter-bearing state, never re-run P1–P5 (map card + PIPELINE.md N1
  updated; the P1-re-entry experiment is archived evidence).
- **RESUME POINT: room shell** → envelope → G1 … (the drawn order).
- Still queued: scene_scale.py apply-extension (manifest/pool/eye
  multiplies for scene #3+; living got its meters via the archived
  re-entry path) + measure-from-graph[resolved] refinement.

## PROGRESS LOG

- 2026-08-05 23:0x — plan written; scene picked (484c93f0); bundle
  verified complete; CP0 starting.
- 2026-08-05 23:10 — CP0 done: gen_raw.ply converted (splat-transform
  v2.6.0, 2M gaussians, 106.8 MB, SH0, no transform flags — same
  no-flag conversion family as bedroom); bundle_path.txt written;
  prep_scene → viewer/data/living_marble.bin (1,036,905 pts, 15.6 MB);
  server :8321 alive (route-table server picks new scenes up live).
  ⏸ CP0 GATE handed to user.
- 2026-08-05 23:3x — CP0 USER REPORT: scene upside-down in viewer; grid
  ABOVE camera start (bedroom: below). DIAGNOSED, no code touched:
  1. **The two Marble exports genuinely differ in raw frame.** bedroom
     raw = y-down (COLMAP-style; calib picked rot180, corr 0.649;
     collider disagreed with splat by y-flip + ~1.67 m). living raw =
     already upright — its splat bounds match its collider bounds
     EXACTLY (p1/p99 [-1.87,-1.09,-3.78]/[+2.89,+1.11,+3.21] vs mesh
     [-1.85,-1.10,-3.97]/[+2.73,+1.08,+3.79]): Marble now exports the
     splat in the collider's y-up frame. Different exporter vintage
     confirmed by spz headers: bedroom fractionalBits=10 antialiased=1,
     living fractionalBits=12 antialiased=0.
  2. **What the user saw is the VIEWER's display default, not the
     data**: index.html display-rot defaults z=180 (hardcoded "upright",
     verified 07-05 on bedroom-era scenes) + no manifest yet → floorY
     falls back to -1.6 → grid drawn at -1.6 flips to +1.6 above the
     camera. Data on disk is fine; coords stay RAW.
  3. **The pipeline's flip is per-scene BY DESIGN**: lift_views.py
     detect_frame() scores identity/mirX/mirY/rot180 against actual GPU
     webps and writes frame.raw_to_render into the manifest; downstream
     reads it. Should pick identity for living at CP5.
  CAVEATS for the gate: a 180° eyeball cannot distinguish identity from
  mirX (mirror) — the CP0 one-look must check handedness against the
  bundle pano/thumbnail. RISK queued for CP1: pre-lift camera rigs
  (self-render/crop rig) may assume the bedroom up-sign — read that
  stage's code before running it.
- 2026-08-05 23:5x — VIEWER FLIP FIX (user-approved, display layer only):
  serve.py /meta.json now passes frame.raw_to_render through;
  index.html display-rot default = manifest's calibrated frame (rz=180
  iff raw y-sign < 0), pre-manifest scenes render RAW AS-IS (rz=0) with
  floor/ceiling fallback from the prep-meta extents (grid, startup pose,
  ceiling clip all land on the real room at CP0). The hardcoded z=180
  was bedroom-vintage. URL ?rot still wins; manual rot boxes unchanged.
  Server restarted via WMI (pid 17516). Verified: bedroom meta r2r
  [-1,-1,1] → rz=180 (regression-identical); living meta pre-manifest →
  rz=0, floor -1.087 / ceil +1.110 from extents. ⏸ CP0 GATE re-handed:
  upright check + MIRROR check vs pano_rgb_0 + HUD declutter eyeball.
- 2026-08-06 01:18 — MACHINE CRASH during seg view 20/20 (see CRASH +
  RECOVERY section). Session died with it.
- 2026-08-06 02:xx — recovery session: clock lock applied+verified,
  seg re-run complete (20/20), seg_batched per-view persistence fix
  (2b88ee2), then user "go": P4 lift (18/20 cams, 171 dets → 75 obj)
  → P5 recenter (10 refuted-with-photo, 14 refined, 1 child → 65 obj;
  9/38 shot-cams FAILED, clustered ceiling-light/up-aimed — short-
  ceiling suspect, flagged R-S2-6) → P6 filter (66 kept / 0 dropped)
  → pano_track_diffs deltas. Whole chain peaked 84.8 W / 1500 MHz.
  Viewer relaunched via CIM Win32_Process (pid 26280; gotcha: rc 8 =
  bad CurrentDirectory — viewer lives under entangled_gen\viewer).
  ⏸ REVIEW BATCH R-S2-3..7 handed to user. NEXT: size-normalization
  design with real lifted sizes (needs user), then graph record.
- 2026-08-06 02:0x–03:0x — OVERNIGHT AUTONOMOUS RUN (user authorized
  "run it to the end", asleep): threshold deviation corrected (canonical
  0.20/topk40), TV hand-tune reverted → generic LLM synonym pass
  (vocab_build), full redo P3→P6, then shell → G1/G2 → J0–J7 →
  S1/S2/PH1 all clean (details + provisional verdicts in REVIEW_LOG
  R-S2-8..13; per-module times in stage_timings.csv). THREE source
  fixes committed 22d855d (recenter stale-shot fingerprint gate,
  paths.frame_block fallback + full intake frame block, room_shell
  extent clip — bedroom regression bit-identical). Compose chain
  S3→shopping→pick→PH2 loop→rotation→sub rounds running via
  scratchpad\overnight_chain.ps1 → out\living_marble\overnight_run.log.
  ⚠ OPEN for user: W3 open-boundary ruling (R-S2-11), TV-refuted
  finding (R-S2-9), size-normalization design (untouched, needs user).
