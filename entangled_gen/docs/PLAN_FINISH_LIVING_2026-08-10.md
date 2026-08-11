# PLAN — FINISH THE LIVING SCENE (session 2026-08-10, real date)

Goal: run living_marble end to end through compose/shopping, with user
checkpoints between stages. Per the 08-23 handoff, the graph is ready;
the only open gate is the chair split.

Scene: `out/living_marble` (out root = CS-8903-OVM/week7/entangled_gen/out)
Code: scene-pipeline/entangled_gen

## Checkpoints (user reviews at each; nothing past a checkpoint runs
## until the user passes it)

- [ ] **CP1 — Chair-split ruling (USER GATE, no model calls).**
      Page: `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\living_marble\graph\same_product_sheets\index.html`
      Question: obj_021+obj_028 vs obj_041+obj_068 — one chair product or two?
      If WRONG → parked fix: prompt bar ("same kind in one room is one
      product unless they LOOK different; size is never a reason to
      split") → one re-judge (that pool only) → materialize → re-review.
      If RIGHT → J9 closed, move on.
- [ ] **CP2 — supported_by.** Run `compose/supported_by.py` on living.
      Review: the support edges (what sits on what).
- [ ] **CP3 — shopping + pick.** Run `compose/shopping.py` then
      `compose/pick.py`. Review: shortlists/picks per object.
- [ ] **CP4 — fit/place.** fit_check → snap/declip chain. Review:
      placed-scene preview.
- [ ] **CP5 — loop/final.** Full-scene render for user judgment.

Expectation (handoff): small wiring issues are LIKELY — the compose
chain has not executed since the graph restructure (R-S2-65). Fix at
source, scene-agnostically, log in REVIEW_LOG.

## Standing rules in force
- User judges all visuals; Claude never concludes from images.
- Pipeline map is the authority; deviations need explicit approval.
- "vote" not "carve" (old DATA files still say carve — translate).
- Subagents get easy fully-specified tasks; orchestrator keeps runs,
  wipes, judgment calls.
- Commit checkpoint owed (~5 sessions uncommitted) — ask user when.

## Progress log
- (start) Plan written. Waiting on CP1 ruling.
- Preflight audit (subagent): compose chain has real wiring gaps — see
  the summary in chat / R-S2-72 session notes. Fix batch NOT yet
  approved: fingerprint guard, supported_by/snap half-migrations,
  propose_edits + three judged-readers, stale supported_by.json.
- Box-view orientation fix APPLIED (user go): fit_size_to_member
  extracted in materialize_layers.py, shared by the J9 box view;
  sheets regenerated from cache (0 model calls, verdicts identical).
- R-S2-72: retired shot systems archived after a repo-wide consumer
  audit (user order). 514 files → archive_2026-08-10_retired_shots/;
  viewer parallax_voted layer removed; pool_retake/ kept (double-booked
  live). Details in REVIEW_LOG R-S2-72 + ARCHIVE_NOTE.md.
- STILL OPEN: CP1 chair ruling; fix-batch go; anchor-name fix
  ("interpenetrates obj_039" → "desk") decision.
