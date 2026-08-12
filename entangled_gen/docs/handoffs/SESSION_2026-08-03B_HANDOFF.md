# SESSION 2026-08-03B HANDOFF — SHOPPING CLOSED (k=3 canon), fit loop design opened; resume at the rotation experiments

Continues SESSION_2026-08-03_HANDOFF.md. Everything this session is
UNCOMMITTED (on top of the ~18 already-unpushed commits — push is the
user's). Working rule reaffirmed hard this session: **plan + explicit
approval before EVERY edit/run — one go-ahead is not blanket.**

## NEXT SESSION — FIRST THING (user, end of session):

**PLAN_FIT_LOOP.md "NEXT SESSION" section** — (A) user camera verdict
on the rendered rotation strips (review_shots/rotcheck_cam{A,B}_*.png,
4 items × 8 free yaws), then (B) the rotation-question head-to-head:
direct-angle vs 8-tile multiple-choice vs propose-verify hybrid, user
eyeballs = GT. Machinery: entangled_gen/experiments/fitloop_rotcam_test.py.

## What happened this session (detail in PLAN_SHOPPING.md rows 7–7d + PLAN_FIT_LOOP.md)

1. **SHOPPING STAGE CLOSED — k=3 CANON.** Chain of user rulings:
   - **Native size only** (no rescale ever): fit score = worst-axis
     |native/box − 1|, symmetric (too big NOT assumed worse), yaw-only
     rotation, ≤15% = strict "fits" mark NOT a cutoff (boxes loose).
     shopping.py rewritten accordingly; ~⅓ of items honestly have 0
     in-tolerance candidates (AC, ceiling light, curtain, ALL
     pictures, yoga mat) = future re-shop channel input.
   - **Style judge run** (pick.py, 8 calls / 217 s / 31 items): ranks
     top-8 fit candidates by look & feel — mood sheet (4 level pano
     crops) + graph testimony + thumbnails. STYLE ORDER IS SEPARATE
     from fit (no blend; combine policy open).
   - **IMAGE judge = canon** (user, after the barn-door case: catalog
     descriptions are honest but gestalt-blind). TEXT+MOOD experiment
     archived with numbers in PLAN_SHOPPING row 7a (2.5× faster;
     mood paragraph fixed the invented-item blind spot; not adopted).
   - **Sheets v2**: dark gaps WITHIN rows (mega-panel lesson applied
     to candidate tiles) + per-item row_<id>.png; PROMPT_VERSION 1→2
     invalidates the style cache BY DESIGN — current picks.json is
     from v1 sheets (user: "live with this").
   - **final_candidates = style top-3 per box** — THE shopping output
     (user: "k=3 candidates for each object box"); patched into the
     existing picks.json (31/31) + produced by pick.py going forward.
   - **ORIENTATION SPLIT OUT of shopping** (user: separate step).
     Prototype that joined it resolved 4/4 face_conflicts — code
     deleted per no-stale-floaters, finding in PLAN_SHOPPING row 8.
2. **MAP CANON ×2** (pipeline_map.html): S4 = SHOPPING + STYLE PICK
   · k=3; then STAGE REDRAW (user: "fit loop should be physical"):
   3.1 ends at S4, picks.json = the semantic→physical HANDOFF BATON,
   fit loop = PH2 in 3.2 (collide → PH3, surgery → PH4).
3. **FIT LOOP DESIGN OPENED** (PLAN_FIT_LOOP.md): contract drafted;
   rulings: rotation check FIRST (before candidate evaluation), FREE
   spin (not cardinal); camera A/B strips rendered for user verdict.
4. **Dev previews** (not pipeline): fitted_preview.glb currently =
   image-judge style #1 at native size. It cycled fit#1 → image-style
   → text-style → back to image-style this session via scratchpad
   swap scripts (shopping.json always restored byte-for-byte).

## Viewer state

- **:8322 shopping viewer** (composition/review_server.py --shopping):
  per item — fit strip (dev % badges, FITS = ≤15% at native size),
  style strip (blue bar = the kept k=3), "what the judge saw" row
  image, text-judge experiment card; top links = mood sheet / sheets /
  prompts. Live-reads picks.json + pick_sheets per request.
- **:8330 scene viewer**: process DIED at session end — relaunch with
  `python viewer/serve.py --scene bedroom_marble --port 8330` (from
  entangled_gen/). The fitted-preview layer it serves =
  image-style #1 picks at native size (fitted_preview.glb on disk).

## Files touched (all uncommitted)

- entangled_gen/compose/shopping.py — native_fit (no-rescale ruling)
- entangled_gen/compose/pick.py — style judge + final_candidates k=3
- composition/review_server.py — style/text/fit strips, picksheet
  routes, k=3 blue bar
- scene-pipeline/pipeline_map.html — S4 canon + stage redraw
- docs/PLAN_SHOPPING.md (rows 7–7d, 8) · docs/PLAN_FIT_LOOP.md (new)
- entangled_gen/experiments/fitloop_rotcam_test.py (promoted)
- out/.../compose: shopping.json (re-run), picks.json (+finals),
  pick_sheets/ (v2 sheets + rows + text results copy), review_shots/
  rotcheck_*.png, fitted_preview.* (dev state)
- Session scratchpad (temp, may vanish): style_preview.py /
  style_preview_text.py / text_style_experiment.py /
  text_mood_experiment.py + results jsons (findings preserved in
  PLAN_SHOPPING 7a; text_mood_results.json copied to pick_sheets/)
