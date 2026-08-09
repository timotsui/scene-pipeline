# Slice-vote carve + uniform-instances judge (2026-08-06 cone session)

✅ **STATUS (2026-08-07 late): RUN 10 = BOX CANON** — user-passed
R-S2-35..39 (see the runs 6–10 update at the bottom for today's rules:
half-space electorate filter, winning-blob pano filter, plan-fill v2,
large_empty_notch doubt, PROTRUSION exemption, SHELL CLIP, never-silent
kept, perp-cam re-box; slice clamp tried + reverted). Statuses
{carved_pano 28, carved 2, kept_wall 7, kept 2, kept_ceiling 7} = 46
objects on living_marble. Still NOT wired into the canonical runner;
consumers (S1/support, shopping) NOT wired; next = materialize (Phase C,
PLAN_CARVE_DOWNSTREAM). The paragraphs below are the founding history
("untested promotion" era) — kept verbatim.

➡ **CURRENT STATE (2026-08-08): RUN 17** (`r20260808-203800`,
canon-eligible, 46 objects, statuses {carved_pano 28, kept_wall 7,
kept_ceiling 7, kept 2, kept_outlier 2}) — the mechanism above is
unchanged; what changed is HOW THE TOP-VIEW DETECTION IS CHOSEN
(ranking + framing check + re-shoot ladder). See the 2026-08-08 update
at the bottom of this file.

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
   the PANO MASKS carry junk (pano masks = a node's founding masks from
   the original pano-funnel views, i.e. the rig_sp0 f30 crops — the
   graph's identity evidence, as opposed to the carve's fresh
   identity-blind card detections; the user found a pano mask that
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
   pano masks = ONE voter; same-eye crops must not corroborate each
   other). Gate 3 killed the degenerate-ballot blowup (obj_063's
   claim-everything camera outvoted) AND obj_028's unstable-detection
   regression, while keeping the sofas' recovery.

## The promoted stage: `carve_slicevote.py`

Slice (prism/wedge, capped margins, height-band footprint) → subset .ply
→ 4 near-cardinal WSL renders → GDINO+SAM per render → 6-voter election,
gate `--gate` (default 3) → anchored cluster (culled clusters recorded as
multiplicity evidence) → **pano-mask filter** (formerly "arm
assignment"; below). Outputs:
`scene_manifest_slicevote_preview.json` (+ `pool_retake/
slicevote_report.json`, the viewer cone-map layer files, `cone_map.html`).

**Pano-mask filter — formerly "arm assignment" (⚠ untested-est of
all):** L-sectional problem — an axis-aligned box around an L bounds the
whole L, and sibling nodes (obj_011/obj_063 are the two arms of the
sectional) each wrap the same cluster. Rule: each node keeps the vote
survivors **its own pano masks vouch for** (user's option 2); falls back
to the cluster box when sp0 coverage is thin (junk-mask guard); flags
when the **pano-filtered box** is <50% of the cluster volume
(multiplicity-judge territory). The semantic authority for "two arms,
one sectional" remains the queued multiplicity judge
(PART_OF_STRUCTURE) — the pano-mask filter is geometric triage, not
identity.

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
- The carve's doubt flags (pano-vs-cluster ratio, culled clusters) are
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
5. Multiplicity judge (PART_OF_STRUCTURE) for flagged pano_vs_cluster
   cases; its typed evidence NOW EXISTS: `graph/record_carve_doubts.py`
   → `graph/carve_doubts.json` (pano_vs_cluster / culled_clusters /
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

---

# UPDATE 2026-08-07 (the four-run night, R-S2-26..30): USER-PASSED DESIGN

The "untested promotion" above is now HISTORY — the stage was hardened
over four whole-scene living runs in one night, each folding in user
rulings from reviewing the previous, and USER-PASSED (R-S2-29 "i think
this is good", R-S2-30 "awesome"). Bedroom regression WAIVED by user
08-06. Still NOT wired into the canonical runner; viewer serves the
preview as the "slicevote" box-source layer (cyan). NOTHING COMMITTED.

## Design deltas over the original promotion (all user-ruled)

1. **VIEW TUNNEL cards** (run 2): cards render the FULL scene minus a
   carved hole — gaussians in the camera cone, nearer than the slice,
   not slice members. Replaced black isolation: on black the detector
   inflates the object to the whole blob (and run 1's ceiling lights
   exploded ×288–×5027). Card re-detect is gated to the slice's screen
   footprint so backdrop same-class objects can't be picked.
2. **Geometric exemptions** (runs 2-3): kept_ceiling (top ≤0.35 m from
   shell ceiling + bottom in upper half of room) and kept_wall (≤0.20 m
   from a shell wall plane + ≤0.30 m thin along its normal). Flat
   objects have no side silhouette; wall-flush ones have no plan
   footprint so the top detection can't even start ("anything can be a
   picture" — obj_002 ×369). Resolved box ships verbatim, status
   recorded. Living: 7 ceiling + 8 wall (incl. 2 to sanity-check:
   obj_017_c00 magazine, obj_022 plant).
3. **Outlier guard** (run 3): shipping box > 8× original volume →
   original ships (kept_outlier), vote box recorded as doubt. Fired 0
   times on living once exemptions existed — pure backstop now.
4. **Detection escalation ladder** (run 4): object-height context cards
   → (≥3 of 4 unproductive) eye-height context cards as EXTRA voters →
   (election empty) isolation retry on black → (still empty) original
   box. Eye-height rationale: Marble splats are biased toward eye-height
   capture. Proven immediately: obj_004 book 0/4 → 4/4 detections,
   final box 0.40×0.08×0.47 m. rule.tiers records the path per object.

## Final living numbers (run 4)

45 objects: 28 carved_pano / 2 carved / 8 kept_wall / 7 kept_ceiling,
zero kept-by-failure. (The run-4/5 data on disk predates the rename and
spells that status `carved_arm`; readers accept both.) (Count is 45 vs
the earlier 44: exemptions catch an object that previously died silently
at the <100-dot skip.)

## Where things stand / next

- R-S2-30 lists carried opens: thin boxes (obj_010/020/041), the two
  surprise wall exemptions, sofa L → multiplicity judge (unbuilt),
  same-product verdicts (never run).
- NEXT (user 08-07): run the carved output ALONG THE PIPELINE — doubts
  into the record via the description pass, the two judge passes, then
  S1/compose consuming scene_manifest_slicevote_preview.json, then
  runner wiring + map promotion (draw the node solid).
- Ops gotchas: PYTHONUTF8=1 when redirecting stdout (cp1252 vs ≥);
  transient votectx plys are big (~250 MB × 4/object) but self-delete;
  a full living run ≈ 15-20 min under the 1500 MHz clock lock.

---

# UPDATE 2026-08-07 late (runs 6–10, R-S2-35..39): RUN 10 = BOX CANON

Six more whole-scene runs in one day, each folding in user rulings from
reviewing the previous; run 10 user-passed as the canonical carve state.
Statuses {carved_pano 28, carved 2, kept_wall 7, kept 2, kept_ceiling 7}
= 46 objects.

## Rules landed (all user-passed; pointers into REVIEW_LOG)

- **HALF-SPACE shell electorate filter** (R-S2-35): dots at-or-behind a
  shell plane (minus eps) are structure — one-sided test, votes zeroed
  at tally, renders untouched. Fixed the obj_014 bookshelf wall-leak.
- **WINNING-BLOB pano filter** (R-S2-35): the founding-mask share is
  compared against the winning blob only (culled-blob dots out).
- **PLAN-FILL v2 recording** (R-S2-35): winning-blob dots,
  footprint-clipped cells, per-cell dot-count histogram. The k-sweep
  was an honest negative — no fill threshold isolates the L.
- **large_empty_notch doubt** (R-S2-35): largest contiguous empty
  rectangle in the object's own plan footprint ≥ 0.50 m² fires a
  multiplicity doubt. Blind census: sofa 1.52 m² | gap 8.4× | desk
  0.18. The L is on the docket BY RULE.
- **PROTRUSION wall exemption** (R-S2-37, replaces flush+thin): box
  touches a wall plane AND protrudes ≤ 0.20 m into the room; depth
  beyond the wall irrelevant. Un-exempted the old surprise exempts
  (obj_022 plant, obj_017_c00 magazine).
- **SHELL CLIP** (R-S2-37): every SHIPPING box is intersected with the
  shell interior; a fully-outside opening ships as a 0.02 m panel flush
  at its wall (the glass door). vote/pano/original stay recorded
  unclipped as evidence.
- **NEVER-SILENT kept path** (R-S2-37): the <100-dot slice skip ships
  the original box as status `kept` with reason + dot count — recovered
  obj_005_c00 + obj_017_c00, both previously silently dropped.
- **PERP-CAM RE-BOX** (R-S2-39): kept_wall/kept_ceiling flat objects
  get ONE face-on view-tunnel render → prior-gated detect → SAM claim →
  1–99 pct re-box of the two in-plane axes only (normal axis untouched;
  guards keep + record, never silent). 13/14 re-boxed; the glass door
  panel corrected 0.53 m along its wall.
- **SLICE SHELL CLAMP tried + REVERTED same day** (R-S2-38, tombstone
  in code): the clamp made wall dots occluders and deleted them from
  every wall-adjacent card. Order ruling: segment WITH wall context →
  disenfranchise at tally (half-space filter) → clip at shipping
  (shell clip).

## The run 6→10 arc

- **Run 6** (R-S2-35): half-space filter + clamp + winning-blob +
  plan-fill v2 — obj_014 wall-leak fixed; notch rule adopted after.
- **Runs 7–8** (R-S2-37): protrusion + shell clip + never-silent —
  glass door ships as a wall panel; 46 objects (two recovered nodes).
- **Run 9** (R-S2-38): clamp reverted; regression held (half-space
  filter alone carries the wall-leak fix); TV stand re-entered the
  docket full-width.
- **Run 10** (R-S2-39): perp-cam re-box for flat objects — CANON.

Downstream on run 10: loop-back B2 RUN (additive carved_edges layer,
J0/J1 on it) + J8 v2.1 canonical verdicts on the 7-case docket — see
PLAN_CARVE_DOWNSTREAM.md for status and the queued opens.

---

# UPDATE 2026-08-08 (run 17, commit 99070ab): THE TOP-VIEW DETECTION IS CHOSEN, NOT ACCEPTED

Everything downstream rests on ONE plan-view box: the top detection
becomes the slice, and the election can never reach outside its own
slice. So a wrong or truncated top box is not a small error — it is a
ceiling on every box the stage can ship. Three fixes landed today, all
traced from real renders, all scene-agnostic (Rule #1). **No threshold
was retuned**: the 30% admission gate keeps its value and its meaning,
and no extra model calls are spent — the detector already returned the
right answer in most of these cases and we were discarding it.

## 1. DETECTION CHOICE IS A RANKING, not "highest confidence wins"

GroundingDINO returns SEVERAL boxes per pass. `gdino_best` used to keep
the highest-scoring one that cleared the admission gate
(`DET_PRIOR_MIN = 0.30` on in-prior/detection). Admission is not
selection, and on obj_020 (chair) the highest score was the WRONG
CHAIR:

| score | detection box            | in-prior/det | covers-prior | touches border |
|-------|--------------------------|--------------|--------------|----------------|
| 0.430 | [515,   2, 768, 344]     | 0.365        | 0.139        | YES (2 edges)  |
| 0.413 | [125, 154, 518, 478]     | 0.984        | 0.549        | no             |
| 0.384 | [127,   3, 766, 481]     | 0.640        | 0.857        | YES            |

Row 0 — the NEIGHBOURING chair, 36% of it inside the prior, covering
13.9% of the prior, running off two frame edges — beat the correct
chair (row 1: 98% inside the prior, clear of every border) by 0.017 of
confidence. The right answer was already in the list.

**The rule now:** admitted candidates are ranked by ONE combined score

```
combo = detector score × prior match × DET_EDGE_PENALTY (0.7 if the box touches a border)
```

where **prior match = the harmonic mean (F1) of in-prior/detection and
covers-prior**. The mean is SYMMETRIC on purpose: a box that merely
SWALLOWS the prior cannot win on containment alone, and a box sitting
in one corner of the prior cannot win on coverage alone. The edge
penalty carries the stage's own evidence doctrine — a box within
`DET_EDGE_PX = 4` px of an image border is CUT BY THE FRAME, so its
extent is not a measurement; it is discounted, not vetoed.
`DET_PRIOR_MIN` stays ADMISSION ONLY: it decides who may be considered,
never who wins, and it is **not a knob to retune when a pick looks
wrong** — the ranking is what picks.

**Why match alone is not enough — obj_034, the glass door.** A
match-only rule (drop the confidence factor) preferred a 0.224-confidence
sprawl over the 0.619 detection:

| score | prior match | combo | outcome under match-only |
|-------|-------------|-------|--------------------------|
| 0.619 | 0.610       | 0.378 | lost                     |
| 0.224 | 0.810       | 0.181 | won — WRONG              |

The door's prior IS the drifted box that the re-box exists to correct,
so "covers the prior well" was rewarding a detection for filling a box
already known to be wrong. Keeping the detector's own score in the
product is what stops the prior from voting for itself. Verified before
landing: the combined score reproduces the OLD choice on all 22
recorded top-view cases where the old choice was right, AND fixes
obj_034.

## 2. FRAMING CHECK — before detecting, make the object fit the frame

The admission gate is a fraction of the PRIOR, so it is meaningless
when the prior fills the picture. obj_068's original box projected to
essentially the whole 768 px frame; an 8%-coverage detection passed and
won.

**The rule:** project the object's ORIGINAL box into the candidate plan
camera FIRST. If the frame CUTS it, or it fills more than
`FRAME_MAX_FILL = 0.80` of either axis, that camera cannot frame the
object — build a camera along the SAME view direction with the SAME aim
and the SAME fov, pulled back until the box occupies
`FRAME_TARGET_FILL = 0.60` of both axes, re-render as
`<id>_topfit.png` (params-sidecar gated like every other render;
ceiling-clipped exactly as `ctop` when the eye lands above the
ceiling), and detect on THAT image.

## 3. RE-SHOOT LADDER — after detecting, don't trust a truncated box

The same problem one step later: the chosen detection itself can run
off the border, and a box within `TOP_EDGE_PX = 4` px of an edge is cut
by the frame, not by the object. This used to be answered by PATCHING
the footprint out to the projected prior — a patch is a guess.

**The rule (same answer as §2): take another shot, pulled back, and
look again.** Up to `TOP_FIT_RETRIES = 2` re-shoots along the same view
direction / aim / fov, each standing off far enough that the
DETECTION's screen extent would land near `FRAME_TARGET_FILL`, rendered
as `<id>_topfitN.png` and re-detected under the same prior gate. The
ladder stops at the first detection clear of every border. ONLY if the
object is still cut off after the ladder does the footprint fall back
to keeping the projected ORIGINAL box's extent on the truncated sides
(rays through off-image pixels are still valid rays); a detection still
touching all four borders is discarded outright.

## What gets recorded (per object, in the rule record + report)

- `top_frame` — the framing check: view, `reframed`, `fit_before`
  (why it failed), fill before/after, standoff distance, and the
  re-framed camera's eye/fov when one was built.
- `top_shots` — EVERY plan shot including the re-shoots: shot index,
  view, render filename, distance, detection box + score, fill,
  `truncated_sides`, `prior_frac`, and the `action` taken
  ("clear of every border", "no detection", …).
- `top_choice` — the FULL RANKED SHORTLIST with each candidate's score,
  match, combo and border contact, plus which index was chosen and why.
- `top_choice_overruled_score` — true whenever the pick was NOT the
  highest-scoring admitted box.

A reviewer can therefore watch the whole decision — what the camera
saw, what was offered, what was chosen and what it beat — without
re-running anything.

## Scene effect (run 17 = `r20260808-203800`, 46 objects, canon-eligible)

- **7 objects had their detection overruled** (obj_011, obj_020,
  obj_024, obj_026, obj_037, obj_046, obj_068).
- **13 needed re-framing** (obj_004, 011, 013, 016, 024, 026, 037, 039,
  046, 048, 063, 068, 069).
- **2 needed a re-shoot** (obj_048, obj_063).
- **~20 boxes moved more than 2 cm.**
- obj_020 chair: 0.32 → 0.47 m wide (the original box was 0.47).
- obj_068: 0.09 → 0.25 × 0.68 × 0.28 m, chair-sized at last — and it
  now raises the multi-node flag, so the chair duplicate is caught
  again downstream (J0 nominated it, J1 ruled SAME).
- obj_034 glass door: back to 0.02 × 3.06 × 2.94 m.
- Statuses: {carved_pano 28, kept_wall 7, kept_ceiling 7, kept 2,
  **kept_outlier 2**} = 46.

## The two outlier-guard trips (RECORDED AS DOUBTS, not fixed)

The 8× guard fired twice — both ship their ORIGINAL box with the
oversized vote box recorded as a doubt, per the standing rule:

1. **obj_019 pillow — exactly 8×.** Its pano-mask filter also reports
   "sp0 coverage too thin", so there is no founding-mask box to pull it
   back; it sits inside the overlapping pillow pile, which is precisely
   where a slice election over-claims.
2. **obj_029 magazine — 40×.** Its top view finds NO detection at all,
   so the slice falls back to the full-height wedge and the bookshelf
   behind it wins the election.

Neither is a threshold question — both are honest carried opens
(they belong to the multiplicity/eyeball docket, not to a knob).

## Viewer rule (from the same session)

The carve layer's HUD label is now composed LIVE from the manifest's
own provenance (run id, `canon_eligible`, object count). A hard-coded
"run 10" caption had been on screen while the file already held run 16
boxes. **Never hand-write a run number in a label** — if a caption
states a run, it reads it from the artifact it is drawing.
