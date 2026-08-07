# Slice-vote carve + uniform-instances judge (2026-08-06 cone session)

⚠ **STATUS: UNTESTED PROMOTION.** Everything here was designed and judged
by the user on 8 living-room objects (sofas obj_011/obj_063 + all 6
chairs) in one evening of ~10 preview experiments. **No bedroom
regression has run. Nothing is wired into the canonical runner. Nothing
is on the pipeline map** — that promotion is user-gated (map is the
authority; see pipeline_map.html rules). Consumers (S1/support,
shopping) are NOT wired.

## Where this came from (the experiment ladder, all on living, 1 evening)

1. **Cone maps** (scratchpad `cone_map.py`): visualized each pool-retake
   camera's mask-cone claims over the object's original points. Findings:
   the chair's coalition split into two perfect factions (wrong-instance
   camera groups agree 0.98 internally, 0.00 across — the old
   most-agreeing-pair rule picked the right chair by a hair), and
   "dropped views" are mechanically just <30%-of-core outliers, with no
   correctness knowledge anywhere.
2. **Visual-hull voting over neutral splat points** (any-2-of-N):
   EXPLODED (obj_063 → 5×6 m) — two cones always cross somewhere over
   open geometry; ≥2-of-N without pre-restriction confirms junk.
3. **Isolation** (user design): candidates = original∪top masks, then the
   candidates rendered ALONE and re-detected. Big win (chair obj_068
   finally chair-sized) — isolation makes the detector's job easy. But
   the original member masks carry junk (user found a member mask that
   segmented FLOOR, labeled sofa — nothing in the pipeline ever re-checks
   a mask against its label).
4. **Top-column** (user design): slice = plan-view detection box extruded
   vertically; original masks OUT of the candidate loop. CPU plan renders
   defeated the detector (6/8 failed) — with proper WSL renders, 7/8
   top detections succeed. Slab fallbacks (prior footprint) proved that
   loose slices hand the hard problem back to the voters.
5. Slice comparison at real render quality settled it (user): **top-box
   prism = PRIMARY, original-box wedge = FALLBACK**, both TRUE
   floor-to-ceiling prisms (not perspective cones), margins CAPPED
   (min(30%, 0.35 m)/side — 30% of a sofa box is a monster margin).
   Tilt-smear fix: cast the box only across the object's height band
   (ceiling-to-floor casting smears the tilted top beam ~0.7 m sideways
   — found by the user on obj_041/obj_020).
6. **6-voter election at gate 3** (user): 4 cardinals on the isolated
   renders + the top view's mask + the original standpoint (union of
   member masks = ONE voter; same-eye crops must not corroborate each
   other). Gate 3 killed the degenerate-ballot blowup (obj_063's
   claim-everything camera outvoted) AND obj_028's unstable-detection
   regression, while keeping the sofas' recovery.

## The promoted stage: `carve_slicevote.py`

Slice (prism/wedge, capped margins, height-band footprint) → subset .ply
→ 4 near-cardinal WSL renders → GDINO+SAM per render → 6-voter election,
gate `--gate` (default 3) → anchored cluster (culled clusters recorded as
multiplicity evidence) → **arm assignment** (below). Outputs:
`scene_manifest_slicevote_preview.json` (+ `pool_retake/
slicevote_report.json`, the viewer cone-map layer files, `cone_map.html`).

**Arm assignment (⚠ untested-est of all):** L-sectional problem — an
axis-aligned box around an L bounds the whole L, and sibling nodes
(obj_011/obj_063 are the two arms) each wrap the same cluster. Rule: each
node keeps the vote survivors **its own original masks vouch for**
(user's option 2); falls back to the cluster box when sp0 coverage is
thin (junk-mask guard); flags when the arm box is <50% of the cluster
volume (multiplicity-judge territory). The semantic authority for "two
arms, one sectional" remains the queued multiplicity judge
(PART_OF_STRUCTURE) — arm assignment is geometric triage, not identity.

## The uniform-instances judge: `compose/uniform_instances.py`

USER IDEA: repeated instances (the chairs around one table) measure at
varying sizes because splat+segmentation are messy per instance; sameness
is a SEMANTIC call, so give it to a judge. Deterministic candidate
groups (same name, plan-proximity clusters, geometric shared-anchor
detection — no hardcoded class lists, Rule #1) → one LLM verdict per
group ("same product? pick ONE canonical size") → 
`compose/uniform_instances.json`. Dry-run VERIFIED on living (finds the
6-chair group, 9 pillows, 2 ceiling-light runs, 2 magazine clusters);
**LLM verdicts NEVER run**. Consumer wiring (shopping retrieves ONE
asset per group at the canonical size) NOT done.

## Placement rulings (user, 2026-08-06 late)

- The uniform-instances ("same product") judge is **its own pass in the
  graph judge chain** — NOT folded into the multiplicity judge (user
  ruling; two different questions: "one object or several?" vs "same
  product across objects?"). The deterministic grouping half of
  `compose/uniform_instances.py` becomes that pass's candidate
  generator; the compose module dissolves once wired; shopping only
  consumes the graph verdict (SAME_PRODUCT group + canonical size).
- The carve's doubt flags (arm-vs-cluster ratio, culled clusters) are
  RECORDED, never decided on: they enter the graph record via the
  description-making pass so node cards carry the doubt, and the judge
  passes consume them as typed open questions — the standard
  record-then-judge flow.

## Open items before this becomes canon

1. Bedroom regression (the standing set: book/desk/plant/sofa-arms/
   chair/pillow + the 150-box no-growth check).
2. User gates the living result object-by-object (R-S2-26 in REVIEW_LOG).
3. Pipeline-map promotion (user-gated; repair stage between J7 and S1)
   + canonical runner wiring.
4. Degenerate-ballot rule (a mask claiming ~100% of the slice = abstain)
   — discussed, NOT implemented; gate-3 currently contains the damage.
5. Multiplicity judge (PART_OF_STRUCTURE) for flagged arm cases; its
   typed evidence NOW EXISTS: `graph/record_carve_doubts.py` →
   `graph/carve_doubts.json` (arm_vs_cluster / culled_clusters /
   slice_fallback; 6 living nodes emitted, mechanics-verified).
6. Same-product judge: NOW ITS OWN GRAPH-CHAIN PASS
   (`graph/judge_same_product.py`, judge-chain claude.exe pattern,
   carve doubts ride as context; grouping dry-run verified — the
   6-chair group found; VERDICTS NEVER RUN). Then: user-review verdicts,
   wire shopping (one asset per SAME_PRODUCT group at canonical size).
   `compose/uniform_instances.py` = superseded first draft, do not wire.
7. Per-view detection instability on marginally-different renders
   (obj_028's card1: 2,281 → 26,308 claims from a slightly different
   slice render) — the old parked item, now measured.
