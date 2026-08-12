# SESSION 2026-08-05 — TOP-DOWN ROTATION EXPERIMENT (annexed) + VIEWER CEILING CLIP

Short session, one experiment, one verdict. Continues
SESSION_2026-08-04_HANDOFF.md. Full measurement write-up lives in
**PLAN_FIT_LOOP.md → "ANNEXED 2026-08-05"**; this file is the session
record only.

## What we did

1. **Viewer: per-gaussian ceiling clip for the hi-fi splat.** Previously
   "clip ceiling" was dots-only (the lib has no clipping API). Now
   `viewer/index.html` string-patches the vendored splat vertex shader in
   `onBeforeCompile` (uniforms + a discard using the lib's own off-screen
   `gl_Position` idiom), cutting at the SAME plane as the dots
   (`ceilY`, 0.25 m margin). Self-heals each frame because
   `SplatMesh.build()` makes a new material on a non-update build; fails
   loud in the toolbar if the shader anchors ever stop matching.
   User-confirmed working. Unrelated to the experiment below — keep it.

2. **Top-down rotation stimulus, full scene, then ANNEXED.** Same
   4-candidate choice as canon, only the camera changed: judge from above,
   with the splat rendered overhead + ceiling clipped as the "real" side.
   31/31 answered, $7.08. Agreement with canon 15/31 overall but **1/10 on
   the objects where canon says a real rotation is needed**. User verdict:
   annex — and the stated reason is FRAGILITY, not the score (identical
   pixels, opposite HIGH-confidence answers across two models, with the
   same `why` text either way). Not resolved whether 1/10 measures the
   viewpoint or the model; re-running the 10 on a stronger model was
   offered and declined.

## Findings that SURVIVE the annex (both in PLAN_FIT_LOOP.md)

- **splat-transform works in the RENDER frame** — applies diag(-1,-1,1)
  on load, so camera/`--look-at`/`--up`/`-B` all take render coords.
  Zero-error fit over 4 clip-box observations. Every prior trusted use in
  this repo was a HORIZONTAL camera, where the error is invisible; it cost
  most of this session to find. Also: shot.py's argparse rejects flag
  values starting with `-` (use `--k=v`).
- **The room is yawed ~5.5°** vs the world axes (splat wall points -5.50°,
  collider normals +5.75°, independent). Root cause: `detect_frame` only
  scores four DISCRETE hypotheses; nothing estimates a continuous yaw.
  **USER RULING: accepted, not corrected** — the rotation module prefers
  cardinal directions. Not a defect, do not re-open.

## Yesterday's handoff may be a STALE RECORD on one point

SESSION_2026-08-04_HANDOFF.md says "fitted_preview: UNTOUCHED by
everything today" and "Nothing has been applied to fitted_preview".
That is probably just stale — written before the last steps of the
session. On disk, `fitted_preview.json` (21:16) carries
`rotcheck_applied_deg: 180.0` for obj_008 and postdates
`rotation_check.json` (21:14), whose bed verdict is **0.0 = keep the
correction**. Trust the files, not that line. It sent this session down a
wrong path once (a superseded `rotation_check_4cand.json` was mistaken for
canon). Yesterday's doc was left unedited.

## State

- Repo: still all UNCOMMITTED (push/commit = user's). New this session:
  `experiments/topdown_choice_test.py` (`--flip-bed` reproduces the blind
  benchmark condition), `experiments/topdown_align_check.py`,
  `experiments/build_topdown_viewer.py`. Modified: `viewer/index.html`,
  `docs/PLAN_FIT_LOOP.md`.
- Data: `compose/topdown_check.json`, `compose/topdown_check/<oid>_td/`
  (per-call folders + stimulus-keyed replies), `compose/topdown_test/`
  (first single-object build + the whole-room alignment images),
  `compose/review_shots/topdown.html` (review page).
- Canon UNTOUCHED: `rotation_check.json`, `fitted_preview.*`,
  `review_shots/index.html`.
- Housekeeping if this code is reused: `shot.py` leaves `reference.json`
  and `shots.csv` inside each call folder — harmless but it breaks the
  clean-folder rule.

## Next

Unchanged from yesterday: **FIT LOOP (PH2) proper**, with the three parked
gates (apply gate; library front semantics + bed asset flip; placement
discrepancies the refcam box check exposed).
