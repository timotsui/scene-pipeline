# SESSION 2026-08-04B HANDOFF — THE MECHANICAL FIT LOOP, BUILT AND RUN TO DRY

Continues SESSION_2026-08-04_HANDOFF.md (rotation check closed as
PH2a). One evening+night session; outcome: **the fit loop's entire
mechanical core exists, is canon (PLAN_FIT_LOOP.md rules 1–14), and
ran bedroom_marble to a dry state: 0 out-of-bounds, residual clips =
rug-class + ≤1.3 L contact grazes.** Every step deterministic, ~1 min
per full cycle, zero judge calls inside the loop.

## THE LOOP (canonical order)

    compose/fit_preview.py    place: style/walk pick -> snapped box,
                              PCA cardinal snap, facing, wall flush,
                              dual attachment, rotation apply (uid +
                              basis-carry gated)
    compose/fit_declip.py     jiggle: plane-constrained bounce-apart,
                              static shell, hug/tucked/attachment
                              locks; applies IN PLACE to the glb
    compose/fit_check.py      verify: vertex-exact bounds + 2 cm
                              voxel clips, report-only
    compose/fit_walk.py       walk over-margin picks down the style
                              top-3; choices consumed by fit_preview
    compose/fit_feedback.py   dry-list walk-back (rule 9): rejects
                              consumed by shopping.py on re-run

Repeat preview→declip→check→walk until walk reports 0 new. Ran to dry
in 2 passes tonight.

## NEXT SESSION — FIRST THINGS

1. **CLOSING ROTATION CHECK (rule 10, USER runs/authorizes):** one
   rotation_check pass on the FINAL walked asset set, then
   fit_preview→fit_declip to apply. Verdicts are deltas (record
   carries measured_uid + measured_applied_deg; 0 = keep).
2. **Visual judge round** vs the refcam photos (the C7-style verdict
   pass; typed menu; refcam-pair stimulus is the proven format).
3. Parked policies: obj_058 walk-past-the-style-3 (its 3 style picks
   are all dry while better-fitting candidates exist deeper);
   flat-item (rug) pairs stay exempt — judge-blessable.
4. **Map edits queued** (pipeline_map.html = authority, user's
   diagram rules): 4 new loop nodes + PH2a repositioned OUTSIDE the
   loop; get approval on the drawing before wiring.
5. Refactor candidate (ratified direction): ONE box-derived
   attachment SET per item replacing mount/dual-attachment/hug-lock
   trio (see PLAN_FIT_LOOP.md tail).

## WHAT LANDED (full detail = PLAN_FIT_LOOP.md canon 1–14)

- **Preview places the real baton:** picks.json style #1 (was
  silently shopping size-fit #1 — the "viewer lag" mystery), walk
  choices override, snapped boxes as targets, wall flush, PCA
  cardinal snap (4 crooked-in-file assets straightened, obj_032's
  +142% oversize was a −31° baked rotation, an EXACT fit once
  straight), dual attachment (doors = wall+floor, bottom-aligned,
  y-locked; box-derived, no categories).
- **Rotation bookkeeping made compounding-safe:** rotation_check
  stamps measured_uid + measured_applied_deg; fit_preview composes
  basis + fresh HIGH delta. Bed read 0° after its 180 was applied =
  the judge confirming the fix.
- **Walk-back (wardrobe autopsy):** every library wardrobe failed its
  clamped 0.33 m swap envelope (best 71% off; wall shelf 994%!) —
  both invented swaps rejected at DRY 0.65 (measured gap), observed
  picture obj_017 + bookshelf obj_023 restored (shop at 6%/11%).
  Re-pick changed 12 assets; old rotation verdicts correctly inert.
- **Walk:** 5 items stepped to fitting candidates; the measured
  5.63 m-furniture-on-4.34 m-wall overflow resolved; 73 L
  desk×bookshelf collision vanished.
- **Jiggle locks (both user-spotted live in the viewer):** wall-
  adjacency HUG 0.30 (slide-along free, corners pinned, shell
  push-back bypasses) + tucked exemption (observed facing TOWARD the
  wall = desk chair, jiggles free).
- Experiments kept: small-yaw rejected (metric-gaming diagonals),
  cardinal-only confirmed (19/20 already best-cardinal);
  experiments/fit_rotate_test.py, fit_cardinal_test.py,
  rotate_view_item.py (--no-tint), axis_view_item.py (the
  axis-aligned top-down overlay that cracked obj_032).

## STATE

- Repo: ALL UNCOMMITTED (commit/push = user's). New: compose/
  fit_check.py, fit_declip.py, fit_walk.py, fit_feedback.py + the 4
  experiment scripts. Modified: compose/fit_preview.py (heavy),
  compose/rotation_check.py (measurement basis), compose/shopping.py
  (feedback consumer), viewer/index.html ('fit check' view, fit
  boxes AT snapped positions), viewer/serve.py (/fit_check.json).
- Data (out/bedroom_marble/compose/): fitted_preview.glb/.json =
  the dry scene (declip applied in place — re-running fit_preview
  drops jiggle moves until fit_declip re-runs); fit_check.json,
  fit_declip.json, fit_walk.json, fit_feedback.json,
  rotation_check.json (measured on PRE-walk assets; mostly inert),
  fit_rotate_test/ + fit_cardinal_test.json + obj_032 sheets.
- FLAGGED CONSTANTS to re-measure on scene #2: DRY 0.65, HUG 0.30,
  MARGIN 0.15/GAIN 0.02, FLAT 0.06, dual-attach floor tol 0.10.
- Viewer ops: servers MUST be launched via WMI Win32_Process.Create
  ([[windows-detached-server-gotcha]]) — tool-shell launches die
  with the shell's job object. Last PID 42104 on :8321.
