# SESSION 2026-08-03 HANDOFF — facing closed (v6), freshness redesigned, fit-set view; resume at shopping + test fit

Continues SESSION_2026-08-02C_HANDOFF.md (shopping v1 + fit preview
built there). Commits this session: 336af9a → 417a6b4 (facing v2–v6,
freshness fingerprints, fit-set view + arrows). ~17 unpushed commits
total — push is the user's.

## TOMORROW — FIRST THING (user ruling, end of 08-03):

**STYLE-AWARE PICKING.** Today the pick = candidate #1 by SIZE FIT
alone (aspect + scale + upright + tiling); look & feel plays no part
— "look and feel is just as important." Rework the candidate CHOICE
so the first placement ONE-SHOTS as well as possible, before leaning
on the fit loop to churn: style/looks joins the ranking (catalog
descriptions + thumbnails + the room photos as the mood reference —
the sandbox ruling's one remaining job), and orientation
reachability should join too (kills the 4 face_conflicts at the
source). Then the fit loop verifies a good first guess instead of
repairing a blind one.

Then:
1. User reviews the test fit:
   `out/bedroom_marble/compose/review_shots/fit2_judge_*.png` +
   the viewer (:8330, "fitted preview" + "fit set" view). Review
   split: wrong SIZE = scoring bug (report); wrong LOOK = the
   style-picking work above.
2. FIT LOOP design (whole-room rounds, typed per-item verdicts,
   re-shop channel). Inherits: candidates per box · decided fronts +
   face_conflict records · scale policy · USER RULING: the
   ORIENTATION LAST PASS lives here — no more per-category facing
   rules (the pillow rule was the line).

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
