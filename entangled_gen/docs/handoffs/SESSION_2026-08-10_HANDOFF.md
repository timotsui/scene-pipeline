# SESSION 2026-08-10 HANDOFF — THE CONE-MAP SESSION (slice-vote carve)

(Real date 2026-08-06 late night; names run ahead. Continues
SESSION_2026-08-09_HANDOFF.md — this session ANSWERED its open k-rule
question by redesign. REVIEW_LOG R-S2-26 carries the evidence trail.
docs/CARVE_SLICEVOTE.md is the design doc. ALL NEW WORK UNCOMMITTED.)

## WHAT HAPPENED (one line each)

1. Cone maps built (which camera claims which dots): exposed the old
   coalition as knowledge-free geometry — the chair's cameras split into
   two perfect wrong-instance factions decided by a hair.
2. USER FOUND a floor-segmenting member mask wearing a "sofa" label —
   masks are never re-checked against their labels, ever.
3. Experiment ladder (~10 rounds, all user-driven, 8 objects): neutral
   visual-hull voting exploded → isolation (render candidates ALONE,
   re-detect) won → top-box column candidates → true full-height prisms
   with CAPPED margins (min(30%, 0.35 m)) → height-band footprint fix
   (tilted-beam smear, user-traced on obj_041/obj_020) → 6-voter
   election (4 cardinals + top mask + original-masks-union-as-one-voter)
   → USER GATE = 3 VOTES (killed the degenerate ballot AND the unstable
   detection regression).
4. L-problem named by user (a box around an L bounds the whole L) →
   per-node ARM ASSIGNMENT designed (own-mask survivors); uniformity
   idea born (chairs at one table = same product, judge picks ONE size
   → shopping).
5. PROMOTED TO REPO, ALL ⚠ UNTESTED: `carve_slicevote.py` (the stage;
   mechanics-verified on the 8, statuses {'carved_arm': 8}) +
   `compose/uniform_instances.py` (grouping dry-run verified — finds
   the 6-chair group; LLM verdicts NEVER run; shopping NOT wired).
6. Viewer: cone-map layer (TEMPORARY, remove when ruled) — vote-colored
   dots, per-camera cone dropdown, object isolation dropdown, legend,
   4 boxes (gray original / red all-agree / orange gate / cyan arm);
   set A/B layers retired (user); /conemap.json route added.

## STATE / FILES

- Evidence pages (out/living_marble/): cone_map.html (slice → voters →
  claims → boxes per object), slice_compare.html (prism vs wedge cuts,
  real renders). Viewer :8321 "cone map (8 obj)" checkbox.
- Preview outputs: scene_manifest_slicevote_preview.json,
  pool_retake/slicevote_report.json (+ conemap.json, slices/*.ply,
  vote_*.png).
- Gate-3 numbers + arm results: REVIEW_LOG R-S2-26. Notables: obj_011
  vote box 2.97×0.86×3.21 still wraps the L (arm didn't split it — its
  own masks are broad; multiplicity judge remains the authority);
  chairs' arm boxes tighten a lot (obj_068 0.58×0.70×0.60) with 6/8
  <50%-volume flags firing.
- UNCOMMITTED: carve_slicevote.py, graph/record_carve_doubts.py,
  graph/judge_same_product.py, compose/uniform_instances.py
  (superseded draft), docs/CARVE_SLICEVOTE.md, REVIEW_LOG R-S2-26,
  this handoff, viewer serve.py (+/conemap.json route, set A/B
  retired) + index.html (cone-map layer). Scratchpad experiment
  scripts are session-local (cone_map.py, isolated_vote*.py,
  slice_compare.py) — the repo scripts are the canonical ports.

## QUEUE (in order)

1. USER GATE on R-S2-26 (the 8 objects, esp. shaved chair heights
   0.49/0.58 at gate 3 and the arm boxes vs their flags).
2. Bedroom regression: carve_slicevote.py --scene bedroom_marble, the
   standing set (book/desk/plant/sofa-arms/chair/pillow) + no-growth on
   known-good boxes. THEN living full-46 blind.
3. Pipeline-map promotion (user-gated): repair stage between J7 and S1;
   canonical runner wiring; retire pool_retake preview layer.
4. Degenerate-ballot rule (mask claiming ~100% of slice = abstain) —
   discussed, not implemented.
5. Multiplicity judge (PART_OF_STRUCTURE): its typed evidence now
   exists — graph/record_carve_doubts.py wrote graph/carve_doubts.json
   (6 living nodes; arm_vs_cluster / culled_clusters / slice_fallback).
   The judge itself is still unbuilt.
6. Same-product judge = OWN graph-chain pass (user ruling; NOT inside
   multiplicity): graph/judge_same_product.py — grouping dry-run
   verified (finds the 6-chair group), VERDICTS NEVER RUN; then
   user-review + wire shopping. compose/uniform_instances.py =
   superseded first draft. Record-proper integration of doubts (the
   description-making pass) rides the gated map promotion.
7. Commit + push (user's call — nothing committed this session).

## GOTCHAS (carried + new)

GPU clock lock resets on reboot. Retake/slice render caches are
camera+slice dependent — ANY geometry edit ⇒ wipe slices/vote_*.png
(same-name reuse is stale-cache poison; carve_slicevote wipes only det
overlays, so delete renders manually after slice-geometry edits).
Detection is render-sensitive: byte-identical renders → identical
detections; marginally different renders can flip a detection wholesale
(obj_028 card1, 2,281 → 26,308 claims). HF seg runs need
HF_HUB_OFFLINE=1. The viewer server was restarted twice tonight (WMI
detached, pid changes) — /conemap.json requires the new serve.py.
