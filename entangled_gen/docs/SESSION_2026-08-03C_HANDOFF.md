# SESSION 2026-08-03C HANDOFF — ROTATION EXPERIMENTS RUN; resume by REVIEWING THEM

Continues SESSION_2026-08-03B_HANDOFF.md. Short session, one job:
build and run experiment B (the rotation-question head-to-head) that
08-03B queued. Ran past midnight into 08-04. Everything is
UNCOMMITTED, on top of the ~18 already-unpushed commits (push is the
user's).

## NEXT SESSION — FIRST THING (user, verbatim intent)

**REVIEW THE ROTATION EXPERIMENTS.** Both A and B are run and waiting
on the user's eyeballs. Nothing in PH2 moves until the verdicts land —
the whole fit-loop design (round shape, verdict menu, where the
rotation check sits) is downstream of which question format wins.

Everything is in ONE folder:
`D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\compose\review_shots\`

- `rotcheck_cam{A,B}_<id>.png` — **experiment A**, 8 strips. Which
  camera lets a model tell rotations apart?
- `rotq_sheet_cam{A,B}_<id>.png` — **experiment B**, 8 sheets. Four
  tiles each: `as placed | arm1 | arm2 | arm3`, all four rendered from
  the SAME camera so the answer is judged and not the view.
- `rotq\` — raw replies, verbatim prompts, `rotq_record.json`,
  `rotq_timing.md`.

Items throughout: obj_109 chair, obj_008 bed, obj_022 bookshelf,
obj_025 side table.

**Offered, not built** (user deferred to next session): an
`index.html` in that folder putting all 16 on one scrolling page with
each arm's angle and stated reason beside its picture. User asked to
plan first if we build it.

## What happened this session

1. **Built `entangled_gen/experiments/fitloop_rotq_test.py`** — the
   only new repo file. Imports the 08-03B rotcam module for scene
   load / shell / spin / render, adds: room-context view with the
   target's projected bbox outlined (projection verified numerically —
   8/8 corners in front of camera, boxes inside frame, sizes ordered
   sensibly), the three arms, the review sheets, and a per-call timing
   record. All image output goes to the DATA folder, not the repo.
2. **Ran it in both cameras** (4 items × 2 cams × 3 arms = 24
   conditions, 32 model calls, serial). 24/24 answered.
3. **Diagnosed the runtime** when the user asked why calls were slow —
   see PLAN_FIT_LOOP.md for the numbers. Short version: it is the
   agentic loop, not the image size, and my first explanation ("a
   3096 px strip is a lot of image to read") was wrong.

## Results — the record is PLAN_FIT_LOOP.md "Experiment B result"

Headlines, so a resumed session does not have to re-derive them:

- **Timing:** arm1 direct 24.0 s/condition · arm3 propose-verify
  41.4 s (1.7×) · arm2 8-tile 69.1 s (2.9×). Wall 1098 s, rendering
  21.8 s of it. The 08-03B assumption that costs are comparable is
  true on call count and wrong by ~3× on wall clock.
- **Why:** trivial call 3.2 s · +one 384 px view 7.0 s · +the 3156 px
  strip 9.4 s → stimulus ≤6 s. arm1 = 3 turns/1.2k out tokens; arm2 =
  25 turns/16.1k out tokens. The model re-reads the strip tile by
  tile. arm2 also swung 126 s → 261 s on identical prompts — **the
  variance is the finding.**
- **Answers:** arm1 said **0° in 8/8** (never proposed a rotation);
  arm3 said 0° in 7/8 (its one non-zero was a +180 flip on the chair
  in camB); arm2 was the only arm to propose rotations, and
  **contradicted itself across cameras on half the items** (bed 0 vs
  +90, side table +90 vs −135).
- **Same image read oppositely:** obj_109 camB — arm1 "seat opens
  toward the desk, plausible" vs arm3's verify "seat turned away from
  the desk." And arm2 justified −135° on the side table with the same
  sentence arm1 used to justify 0°.

Claude did NOT score correctness — standing rule, the user judges all
visuals ([[verification-workflow]]).

## Ops gotchas earned this session

1. **`claude -p` can only read images inside its cwd tree.** Arm2's
   first run came back "I need permission to read that image file" in
   9.6 s and scored a non-answer, because the strip lived one
   directory up from the call's cwd. Stimuli are now copied in. Any
   future stage pointing a judge at an image outside its working
   directory will hit this.
2. **`--output-format json` is the way to see cost.** It reports
   `num_turns`, `duration_api_ms`, and token usage — that is what
   turned "why is this slow" from speculation into a measurement.
3. Python buffers stdout when redirected to a log, so the background
   run showed no progress until it finished. Use `python -u` next time.

## State

- Repo: one new untracked file (`experiments/fitloop_rotq_test.py`).
  Nothing else in scene-pipeline touched. No pipeline stage was run —
  this was an isolated experiment, per [[pipeline-viewer-authority]].
- Data: new files under `review_shots/` and `review_shots/rotq/` only.
- `fitted_preview.glb` (08-03 17:43, naive #1-candidate placement) is
  what every render in both experiments is built on.
