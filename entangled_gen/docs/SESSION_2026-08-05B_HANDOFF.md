# SESSION 2026-08-05B HANDOFF — CLOSING ROTATION PASS + MAP TRUED UP

Continues SESSION_2026-08-05_HANDOFF.md (top-down annex) and
SESSION_2026-08-04B_HANDOFF.md (the mechanical loop). One evening
session; outcome: **the closing rotation check ran and applied through
the wall-legality constraint (born mid-session from the sideways-door
incident), the pipeline map now matches reality (fit-loop nodes drawn,
PH2a = stage terminus, PH3/PH4/JUDGE retired), and the review page
grew the multiple choice + top views.** Scene: 0 OOB, 9 residual
grazes.

## NEXT SESSION — FIRST THINGS (user, end of session)

1. **SUB ROUNDS** (user: "tomorrow we start adding in the sub
   objects, shouldn't be too hard"): the 64 deferred subs, grouped per
   anchor in shopping.json, onto their FITTED anchors' real mesh
   surfaces (books on actual shelf boards — the reason they were
   deferred). Anchors are converged and rotation-checked; this is the
   step the anchors-first ruling was waiting for.
2. **FRONT/BACK CONSTRAINT** (user-approved in principle, NOT wired —
   PLAN_FIT_LOOP "QUEUED NEXT" block has the settled design):
   pure-wall-attachment items (['wall'] — pictures/AC/curtain, vs
   doors' wall+floor) get the back side banned; the facing ladder owns
   their pose; rotation_check skips/locks their calls (a non-zero
   judge opinion = library-front audit flag, never an applied spin);
   fit_preview ignores their deltas. ⚠ WILL REVERT obj_035's applied
   180 — user should eyeball that picture (top view on the review
   page) before/when wiring.
3. Parked: obj_058 walk-past-the-style-3 policy; the 5 riding
   rotation flags (bed −90 med is NEW vs 0 last run — fragility, the
   gate held it out); box-check MISS crops (accepted wart: MISS =
   position disagreement, crop clips when the box is offset).

## WHAT LANDED

- **Closing rotation check (rule 10) RUN on the dry walked scene**,
  twice: first with 4-candidate menus → 8 non-zero, 2 HIGH applied →
  ⚠ turned door obj_128 + picture obj_017 SIDEWAYS (the menu offered
  wall items poses perpendicular to their wall; the judge, correctly
  matching hinge/handle sides in pixels, expressed the answer as an
  illegal pose at HIGH). Pre-walk record kept as
  rotation_check_prewalk.json. Timing run 1: wave 481 s at 8 jobs,
  ~$9.29, 13-call ≥10-turn tail (evidence-limited, matches canon).
- **WALL-LEGALITY MENU canon** (user: "take out the strictly illegal
  options"; PLAN_FIT_LOOP CANON 2026-08-05): rotation_check
  legal_spins() — wall-attached items only see in-wall candidates
  (wall normal = the observed box's own thin axis; a sideways
  placement gets exactly {90,270}, the menu that can fix it;
  near-square ratio <1.15 indeterminate → keep 4; floor items keep 4
  contrast anchors — DISTINCT from the annexed footprint-prune).
  fit_preview gate extension: constrained-menu verdicts apply at ANY
  confidence (every option legal; worst case = wrong legal flip).
  Re-run (wave 376 s) self-corrected both items (obj_017 −90 on 90 =
  net 0, original flush; obj_128 +90 on 90 = net 180, in-wall hinge
  flipped) + caught obj_035 picture 180 HIGH on the [0,180] menu;
  obj_127's stale +90 flag dissolved to 0 HIGH; wall calls dropped to
  4 turns / 11–35 s (one look).
- **Applied in scene**: obj_000 chair 180 · obj_035 picture 180 ·
  obj_128 door 180. Declip + check after: 0 OOB, 9 clips (rug-class +
  grazes; 3 STUCK basket pairs ≤0.54 L).
- **Map trued up** (pipeline_map.html, each step user-approved): PH2
  placeholder → 4 drawn loop nodes (PH2·1 PLACE / ·2 JIGGLE / ·3
  CHECK / ·4 WALK, cards fitp/fitd/fitc/fitw written from canon);
  PH2a moved BELOW the loop = STAGE TERMINUS (output =
  fitted_preview + rotation_check deltas); **PH3 COLLIDE + PH4
  SURGERY + JUDGE RETIRED** (collide absorbed by fit_check every
  cycle; surgery's jobs → PH1 refit + walk/walk-back; judge =
  C7-era outer loop, remaining judging = dev-time review, never
  drawn) — reasons recorded as SVG comments, donor code stays on
  disk. Intro card rewritten; script block node-checked.
- **Review page = choice edition** (build_rotq_viewer.py): per object
  verdict + verbatim reason + the actual multiple choice (2 or 4
  candidates, pick outlined green) + TOP-DOWN pair (splat ceiling-
  clipped | as placed, same overhead camera — USER-view aid only;
  top-down as judge stimulus stays annexed) + sheet + refcam gate
  pair. Page: out/bedroom_marble/compose/review_shots/index.html.

## STATE

- ALL UNCOMMITTED (commit/push = user's). Modified this session:
  compose/rotation_check.py (legal_spins + attach map),
  compose/fit_preview.py (gate extension),
  experiments/build_rotq_viewer.py (choice + top views),
  pipeline_map.html (major), docs/PLAN_FIT_LOOP.md (canon + queued +
  08-05 update annotations), this file.
- Data (out/bedroom_marble/compose/): fitted_preview.glb/.json =
  legality-corrected scene (00:2x); rotation_check.json = constrained
  run (00:24) + rotation_check_prewalk.json + the superseded _2cam/
  _roomframed/_4cand records; refcam pairs + topdown_check
  re-rendered at current poses; review_shots/index.html rebuilt;
  *_legalfix.png / *_before_after.png composites in refcam/.
- Viewer: :8321 alive (PID 42104, WMI-launched —
  [[windows-detached-server-gotcha]]). Order reminder: re-running
  fit_preview drops jiggle moves until fit_declip re-runs.
