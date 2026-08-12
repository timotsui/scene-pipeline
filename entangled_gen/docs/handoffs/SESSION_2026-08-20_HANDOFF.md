# SESSION 2026-08-20 HANDOFF — obj_018 SOLVED TO ROOT CAUSE; THE FIX IS UNDESIGNED

(Real date 2026-08-09, second session that day. Evidence: REVIEW_LOG
R-S2-59. The scene graph was NOT touched — still exactly as
J8/materialize left it.)

## WHAT THIS SESSION SETTLED (R-S2-59)

**The obj_018 question is answered: it was a SCORING loss, proven.**
Run 17's candidate list was never cached, so the detector was re-run
on the CACHED run-17 perp render (params hash efe4f131f913,
byte-identical, deterministic model = the exact same race). Two
candidates:

    #0 light+strip grab   score 0.287, CLIPPED 2 sides, match 0.602 -> combo 0.121  WINNER
    #1 small round light  score 0.534 (detector's TOP answer), clean, match 0.045 -> combo 0.024  lost

The combo's match term rewards covering the PRIOR — and obj_018's
prior is the oversized box the re-box exists to correct. Wrong-big
prior => wrong-big detections win. obj_018 is the direct casualty of
the obj_034 fix (truncation veto softened to a x0.7 discount). The old
ladder would have picked #1, and run 14 proves the rest of the chain
then goes right on its own (guard rejects the 3x shrink,
`rebox_rejected_smaller` keeps it on the ballot, J8 ships it).

**One-shot framing settled with the user:** "remember yesterday's good
answer" is a dev crutch, NOT a fix — in production there is one run.
The one-shot-valid layers are: **scoring** (fix the picker), **ballot**
(never hand a judge one name — a truncated rebox must record its
alternatives), **retry** (another shot when the only detection is weak
and clipped). None of the three is designed yet.

**Evidence on the cone map:** cone_map.html -> obj_018's card, the
red-bordered "DETECTION CANDIDATES — REPLAY 2026-08-09" panel: both
boxes drawn, score table, link to the JSON. Labelled a REPLAY (the
cone map is otherwise a run-17 artifact).

    out/living_marble/cone_map.html
    out/living_marble/pool_retake/slices/vote_obj_018_perp_candidates.json
    out/living_marble/pool_retake/slices/vote_obj_018_perp_cands.png

**Code landed (user: "lets cache those too"):** slicevote.py now
records the full candidate race as `det_choice` in the perp re-box
doubt rec AND the card re-detect info (top-view already recorded; its
"recorded ONLY here" comment corrected). Syntax-checked. A race can
never need re-running again.

## OPEN, IN THE ORDER I'D TAKE THEM

1. **Design the obj_018 fixes** — now unblocked by the root cause:
   scoring (what should the match term do when the prior is
   untrustworthy? the obj_034 comment in gdino_best is the constraint
   in the other direction — don't just re-add the veto), ballot
   (`rebox_truncated` records alternatives: the raw un-filled
   measurement + runner-up candidates), retry. Scene-agnostic, no
   per-node tuning (automated-pipeline rule).
2. **The J9 gate — FIFTH session open, blocks compose:**
   out/living_marble/graph/same_product_sheets/index.html
   (ceiling-light trim split + chair split, on-disk chair reason =
   BACKREST SHAPE).
3. **Judge packaging** (designed in conversation, not built): which
   views each judge is SHOWN; strip per node, fixed card order + plan,
   count stated in words.
4. **Culled-camera audit renders** — re-render awaits an explicit go.
5. Carried: split-piece fixes (verdict fan-out guard; per-piece
   descriptions); declip rotation oscillation; support_clip.py
   retirement candidate.

## WHAT IS ON DISK

Committed: NOTHING (this session or last). Uncommitted in
scene-pipeline: graph/view_cams.py + graph/node_views.py (prev
session), slicevote.py (det_choice caching, this session),
PIPELINE.md, docs/REVIEW_LOG.md (R-S2-57..59), pipeline_map.html,
both handoffs.

Data edits (out/living_marble/): cone_map.html obj_018 panel + the two
replay artifacts above (regenerable via scratchpad
replay_obj018_perp_det.py).

## GOTCHAS THAT DECIDED THINGS THIS SESSION

- **The render cache saves photos, not decisions.** Params-hash reuse
  meant run 14 and run 17 detected on the byte-same image — which is
  what made the replay legitimate, and also what proved the selection
  rule (changed between the runs) was the only moving part.
- **A deterministic detector + a cached input = a replayable race.**
  Cheap provenance recovery, but only because the png survived;
  det_choice caching removes the need entirely.
- **The combo's match term inverts when the prior is wrong** — it was
  verified on 22 top-view choices where the prior was roughly right;
  nothing in the formula knows which case it is in.
