# Session 2026-08-01B handoff — propose-edits v2, PART_OF retired, J0 triage, graph re-run ×2

Read me first next session. Everything below is UNCOMMITTED in
scene-pipeline. The user reviews this session's results before anything
else moves.

## What exists now that didn't this morning

1. **propose_edits v2** (`compose/propose_edits.py`, prompt v2): the R5
   'duplicat' regex and the dead existence-disputed detector are GONE.
   The audit judge receives raw verbatim consistency wordings (candidates'
   verdicts + all dropped-edge reasons scene-wide), is told duplication is
   not a delete reason, and reports `duplicate_suspicions` →
   `reopen_petitions` in `edit_proposals.json`. First run: plant KEEP 0.6
   (flipped from v1's DELETE 0.75), 4 adds, 0 petitions (correct on the
   v6 wordings). **R5b was opened for this — but see STALE below.**
2. **Pair-judge v2 — PART_OF retired** (user ruling: "if it is not a
   separately shoppable object, it must not stay a node"). Menu is
   SAME/DISTINCT; fragments are SAME (merge), contents DISTINCT.
   `build_judged.py` hard-aborts on a stale PART_OF verdict.
3. **Nesting record facts** (`build_edges.py`): every detection pair with
   containment ≥ 0.90 recorded on the smaller node — 108 facts / 62 nodes
   on bedroom_marble. Deterministic, always produced.
4. **J0 · pair triage** (`graph/triage_pairs.py`, NEW): text-only docket
   clerk between the edge builder and the pair judge. Nesting facts in,
   one batched cheap call, NOMINATE/SKIP per pair (asymmetric: nominate
   on doubt). Nominations = additive SAME_CANDIDATE edges, zone
   "semantic", cached. First run: 94 candidates → 6 nominate / 88 skip
   (all books/toys correctly skipped).
5. **Viewer** (`viewer/index.html`): search now indexes the resolved main
   layer; card partner ids are hover-highlight + click-transfer links.
6. **Map** (`pipeline_map.html`): step 3 linearized (S1→S2→PH1 snap→S3
   propose edits→S4 screening→S5 shopping, no loop arrows, caption notes
   re-entry); J0 triage box in the judge lane; all stat boxes/cards at
   the final numbers below.

## The graph stage was re-run to resolved TWICE

Backup of the pre-change graph: `out/bedroom_marble/scene_graph.json.bak-0801-prepartof`.

Run 1 (v2 menu, geometric nominations): 14 pairs → 13 SAME / 1 DISTINCT
(books-in-shelf DISTINCT first try). 102 → 90 clusters → 85 shipping.

Run 2 (after J0 triage added 6 semantic nominations): 20 pairs → 18 SAME
/ 2 DISTINCT. **Final: 102 detections → 86 clusters → 82 shipping / 4
removed.** The shelf corner is DONE: obj_043 bookshelf = {043,080,093,
140}; obj_023 bookshelf = {023,047,088}; every book has exactly one IN
edge to its bookshelf; zero loose "shelf" nodes.

## USER REVIEW ITEMS (R6 — the gate for all of this, in PLAN_COMPOSE_LOOP.md)

Verdict flips the user must eyeball (viewer :8321, hard refresh):
- **obj_083 plant → REJECTED (removed)** by the terminal pass ("spurious
  detection from clutter near the window"). This ENDS the plant saga in
  the opposite direction from propose-edits v2's KEEP and the R3-era
  leaning. User's eyes on ctx crops required (record layer still has it).
- **obj_059 flip**: rejected (run 1) → confirmed "small glass decorative"
  (run 2). Same crops, different runs — verdict instability to note.
- **obj_062 renamed lamp → "air conditioner"** by the rename pass;
  coherence hypothesized ceiling fan / linear light. A SECOND AC on the
  ceiling is suspicious — eyeball.
- The big merges themselves: obj_043 4-member and obj_023 3-member
  clusters — check the merged crops read as one unit each.

## STALE / PENDING

- **All compose files are stale** (supported_by, consistency, snap,
  edit_proposals — built against the old 89-node resolved; they
  reference merged-away ids). Viewer review modes for them are
  misleading until re-run. Re-running them = next session's first move
  after R6 passes (~4 LLM calls).
- R5b (propose-edits v2 output) is therefore also stale — re-open after
  the compose re-run instead of judging the old file.
- NOT BUILT: screening's non-visual dedup + "parts aren't shoppable"
  rule (design settled in conversation; propose-edits petitions and
  loop-judge observations should file into the J0 docket).
- NOT COMMITTED: everything since 07-31. Commit after user review.

## Known wart

`judge_pairs.py` expects `center_height_diff_m` in SAME_CANDIDATE
evidence; triage edges now include it (bug found+fixed this session —
first triage run wrote 6 edges without it, patched in place).
