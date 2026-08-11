# The prompt for the next session

Paste the block below into a fresh session. Kept in the repo so it is not
lost in chat scrollback, and so it can be edited as items get done.

---

```
Continue the scene-pipeline automation work. Repo:
D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen

READ FIRST, in this order — do not skip, and do not work from summaries:
1. docs/SESSION_2026-08-25B_HANDOFF.md — §0 (the real state), then §6b
   (your first task), then §5 (the ordered work), then §7 (open questions)
2. docs/PARKED.md — what NOT to work on
3. graph/stages.py — the chain IS this file

THE GOAL: a pipeline that runs top to bottom, unattended, over 100 fresh
Marble bundles, as designed.

THE HONEST STATE: from a raw bundle, NOTHING runs unattended yet. The middle
third (vote → grouped → composed) is wired, gated, timed and resumable.
Everything before it — intake, the pano funnel, and the whole
record→judged→resolved half — is ~20 hand-run commands no script contains.
Do not repeat the claim that the pipeline runs 100 scenes.

═══ TWO WAYS THIS SESSION WILL GO WRONG IF YOU LET IT ═══

1. YOU WILL WANT TO START WIRING STAGES IMMEDIATELY. Do not. Item 2 below
   (what `--phase core` IS) BLOCKS items 3-5, because until it is settled you
   cannot tell which of two lanes a stage belongs to. The user has already
   ruled the map correct, so the answer is available — but you must apply it
   deliberately and delete the dead lane, not wire around it. Wiring first
   and deciding after is how the repo ended up with two intake lanes.

2. YOU WILL SEE A PASSING RUN ON autotest_bedroom AND BELIEVE THE CHAIN
   WORKS. It does not mean that. That scene is a CLONE carrying hand-fixes
   that steer the result — snap_rulings.json pins marked USER_RULING that
   OUTRANK the model, fit_walk.json overriding the picks,
   rotation_check.json, fit_feedback.json, a prior fitted_preview.json. None
   is declared in stages.py. A fresh scene has none of them and gets a
   different answer with NO crash and NO warning. See handoff §4b. Any claim
   of the form "the pipeline works" must be backed by a scene that has never
   run before, or it is not evidence.

═══ FIRST TASK — handoff §6b ═══

The user ruled: "the pipeline viewer is generally correct. Items marked
Stale should not be in the core pipeline." Apply it:
  - drop the `voted_edges` row from stages.CHAIN (the file stays on disk)
  - give graph/triage_pairs.py and graph/judge_pairs.py an `--edges-from
    voted` mode reading the voted LAYER's own edges (they offer only
    record|voted_edges today), then point j0_retriage/j1_repairs at it
  - same for judge_multiplicity, which hard-exits without the block
  - retire the graph['vote'] block across its four readers
    (judge_multiplicity:2097, judge_same_product:1038,
    materialize_layers:274/324, scene_gate:332) but KEEP vote_doubts.json —
    five modules read it and materialize already prefers it
  - keep the `doubts` STAGE; only the graph block is retired
The map's own wording matters: J0/J1 STILL RUN, just on the voted layer's
edges. The loop-back survives; the half-layer does not.

═══ THEN, handoff §5f in order ═══

  1. Fix four bundle globs — crop_pano.py:79, seg_pano_overlay.py:41,
     lift_pano.py:250 and :91 want *_pano.png / *_collider.glb; harvest
     gives pano_rgb_0.png / collider.glb. 0 of 318 worlds match. Copy
     vocab_build.find_pano. Minutes.
  2. `run_scene --phase core` is the WRONG LANE and the user has ruled the
     map correct — replace it with the funnel the map draws
     (frame_bootstrap → pano_stitch → crop_pano → vocab_build →
     pano_bearings → seg_batched → pano_lift → pano_recenter →
     manifest_filter → scene_scale → room_shell → envelope → build_graph).
     SETTLE THIS BEFORE 3-5.
  3. Add that funnel to stages.py as a tuple, and make slicevote.py:1038-1042
     derive its filenames instead of hardcoding pano2c_rc_f30 / lift_poolc /
     seg_batched20 (compose/supported_by.py:604 shows the regex pattern).
  4. Add the record/judge half as a tuple — ruled order in
     PIPELINE.md:303-312. Three orderings there are unenforced and silently
     wrong if reversed (J1→J5, J3→J4, J0→J1): make them refusals.
  5. Give bundle_path.txt a producer (a --bundle flag or a one-line
     new_scene.py). It is the only thing a human must type.

═══ FOUR TRAPS THAT HAVE ALREADY CAUSED REAL BUGS ═══

- TRUST THE PRIMARY RECORD, NEVER A SUMMARY. Two summary docs caused two code
  defects in one day. Authority: pipeline_map.html → the owning PLAN_*.md →
  REVIEW_LOG run records → module docstrings → summaries.
- CLONED TEST SCENES LIE (see failure mode 2 above).
- FLAGS ARE INVERTED. Writing is the default; --dry-run opts out. --apply,
  --render, --recut, --reshoot still parse and DO NOTHING — an old command
  line from a handoff now does MORE than its author expected.
- A GREEN GATE IS NOT DESIGN CONFORMANCE. The gate proves a stage did what it
  promised, not that the sequence matches the design, and not that the
  pipeline starts where a real scene starts. Three of the worst findings of
  the last session were invisible to it and surfaced only by auditing against
  the primary records.

═══ HARD RULES ═══

- NEVER mutate out/living_marble — live scene, open J9 gate.
- PARKED, do not touch: the ctop/top-view problem, anything J9-specific.
- Do not decide handoff §7's open questions (support_clip, sub rounds,
  re-shop scope, grouped-rebuild, the 34-of-318 collider shortfall, the paper
  metric). Ask.
- 17 commits are unpushed. Do not push without asking.
- Machine: the GPUClockLock task holds the GPU at 1500 MHz, so long GPU runs
  are safe; tools/watch_gpu.ps1 logs it.
- Report honestly. If a stage is skipped, say so. If a number comes from a
  cloned scene, say so.

Working scenes: autotest_bedroom (82 objects, the best test scene),
autotest_living, autotest_living2, autotest_broken (deliberate failure
fixture). Commit as Timotsui / timotsuihc@gmail.com.
```
