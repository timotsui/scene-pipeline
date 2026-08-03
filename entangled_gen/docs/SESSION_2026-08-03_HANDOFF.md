# SESSION 2026-08-03 HANDOFF — facing closed (v6), freshness redesigned, fit-set view; resume at shopping + test fit

Continues SESSION_2026-08-02C_HANDOFF.md (shopping v1 + fit preview
built there). Commits this session: 336af9a → 417a6b4 (facing v2–v6,
freshness fingerprints, fit-set view + arrows). ~17 unpushed commits
total — push is the user's.

## TOMORROW (user's words): "back to shopping and test fit"

1. User reviews the CURRENT test fit:
   `out/bedroom_marble/compose/review_shots/fit2_judge_*.png`
   (side-by-side real vs shopped, regenerated from the final v6 GLB)
   + the viewer (:8330, "fitted preview" checkbox + "fit set" view).
   Remaining known sins = fit-loop checklist: ugly picks, uniform-
   scale under-fills, collisions, 4 declared face_conflicts.
2. Then design the FIT LOOP (whole-room rounds, typed per-item
   verdicts, re-shop channel — sketch in compose-loop memory +
   PLAN_SHOPPING.md). It inherits: candidates per box (shopping.json)
   · decided fronts + face_conflict records (fitted_preview.json) ·
   scale policy + style tiebreak still open · USER RULING: the
   ORIENTATION LAST PASS lives here — no more per-category facing
   rules (the pillow rule was the line; it stays, but the pattern
   does not grow).

## What landed today (details in PLAN_SHOPPING.md + commit messages)

- **FACING, v2–v6, closed:** evidence ladder in fit_preview
  (wall-mount thin-axis → pillow evidence → wall-hug 0.30 edge gap →
  observed witness (line-of-sight converted, recomputed every run) →
  heuristic); subs inherit host front (subs_front); proposals inherit
  through their declared hosts (no new plumbing). Witness v8 facing
  question in describe_nodes (leftmost crop, camera-relative). v5
  fixed the backwards-shelf bug (yaw gate vetoed 180°). v6 = pillow
  marks the bed head (user GT: head north; bed lies SIDE-against the
  wall). Scoreboard: 26/30 verified correct (achieved-vs-decided dot
  check, front_check.py pattern), 4 DECLARED face_conflict records
  (obj_002 AC, obj_109 chair, obj_053 rug sideways perms; obj_031 mat
  front-up) — fit-loop inputs, orientation must join candidate
  scoring.
- **FRESHNESS REDESIGN (user: mtime gate "bad for active
  debugging"):** compose layers stamp graph_fingerprint (geometry /
  testimony slice hashes, paths.graph_fingerprint); serve.py FP_NEED
  compares per consumed slice; STALE = served WITH data + badge
  (viewer "⚠ stale" + amber hint), never hidden. edit_proposals sits
  stale-badged on purpose (stochastic loop — never re-run just to
  stamp).
- **Viewer:** "fit set (to place)" default view (only the objects
  being fitted; adds blue / swap-ins green; swapped-out hidden) +
  front arrows on everything incl. proposals (bright = decided,
  whisker = raw witness) + fitted_preview.json route.
- **Chain re-ran on the v8 graph:** 4/4 blind GT held; obj_096
  demoted anchor→sub; 31 anchors / 64 subs.

## Ops notes

- User's client has NO side panel: SendUserFile attachments never
  arrive. Review artifacts go to
  `out/<scene>/compose/review_shots/` (30 files there now) — give
  the folder path.
- Viewers running: :8330 scene viewer, :8322 shopping candidates.
- Scale-calibration watch-list in PLAN_SHOPPING.md (wall-hug 0.30 =
  re-test on scene #2).
