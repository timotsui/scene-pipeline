# PLAN — CARVE DOWNSTREAM: judges → materialize → compose (the wiring road)

**Written 2026-08-07** (session after the four-run night). Continues the
R-S2-30 directive ("keep running the carved output along the pipeline")
and the END-STATE CONTRACT on the map's carve card: the handoff stays
ONE canonical graph; carved boxes + new-judge verdicts materialize into
it; the preview manifest retires; THEN the runner is wired and the
carve's outgoing edge is drawn solid.

**Map rule (user 08-07): every phase that lands gets DRAWN on
pipeline_map.html as part of landing — no invisible stages.** Nodes
appear when implemented (dashed if preview, solid at canon), same as
the carve node's own history. Step-3 shift-down script pattern from
the 08-07 main-lane move (dry-run the threshold crossing first).

Protocol: pipeline_map.html is the authority; every checkpoint = USER
GATE with review stimuli (module contract first); verdicts land in
REVIEW_LOG.md; Claude does not conclude from images. Rule #1: no
scene-specific tuning; fixes at the source.

## STATE ENTERING THIS PLAN (updated 2026-08-08, J8 v2.4 canonization)

- Carve run 10 = BOX CANON (user-passed R-S2-35..39):
  scene_manifest_slicevote_preview.json — 46 objects; {carved_pano 28,
  carved 2, kept_wall 7, kept 2, kept_ceiling 7}. Runs 6–10 rules in:
  half-space shell filter, winning-blob pano filter, plan-fill v2,
  large_empty_notch doubt, PROTRUSION wall exemption, SHELL CLIP,
  never-silent kept path, perp-cam re-box for flat objects (slice
  shell clamp tried + reverted, R-S2-38). Details:
  docs/CARVE_SLICEVOTE.md runs-6–10 update.
- scene_graph.json `carve` block re-applied post-run-10 (46 nodes, 28
  with doubts); docket = AUTO doubts only, 7 cases (the 08-07
  user_routed channel was a Rule-1 violation, removed; obj_011 admits
  via large_empty_notch BY RULE).
- **Phase B2 loop-back: RUN** (R-S2-36..39) — additive carved_edges
  layer + J0/J1 on it; **Phase A J8: CANONICAL VERDICTS RUN**, now on
  the v2.4 10-case docket (status lines in each phase below).
- Same-product grouping dry-run current: 6 groups (chairs×6, pillows×9,
  lights×4+×3, magazines×3+×2). Verdicts never run.
- Resolved layer = identity canon; its boxes pre-carve (stale); the
  poisoned ON edges are superseded by the rebuilt carved_edges layer.
- **J8 v2.4 = CANON (user ruling 2026-08-08, "they all make sense.
  this is the one we use")** — the comparison ask, per-node candidate
  boxes, NO_GOOD_BOX, carve-exempt routing and dependency-ordered
  judging all landed and the living_marble verdicts are USER-ACCEPTED.
  Details in Phase A below.
- **Phase C materialize: BUILT + RUN ONCE** (R-S2-43) as an UNTESTED
  TRIAL — additive `graph["carved"]`, status UNTESTED-TRIAL, not
  promoted to canon.
- **NEXT: J9 GATES** — sheets + verdicts user review, and the J9
  INSTABILITY first (two runs 20 min apart gave disjoint sets; J9 has
  no verdict cache, so every run re-decides) — **then PHASE C
  promotion**: close the six materialize gaps listed in R-S2-43
  before the carved layer becomes the handoff. Carried opens:
  post_judge_conflicts (Phase A); eyeballs — obj_042 TV-stand extent
  + curtain re-box under the dist-clamped camera; J8 confidence
  spread (watch for anchoring).

## PHASE A — J8 MULTIPLICITY JUDGE, v2.4 (graph/judge_multiplicity.py)

**STATUS 08-08: v2.4 IS CANON — VERDICTS USER-ACCEPTED for
living_marble** (user ruling: "they all make sense. this is the one we
use"). The bench ran inside the Phase-B2 loop-back pass as the order
ruling requires (facts read from the rebuilt carved_edges), on a
10-case docket sorted into 3 dependency levels.

**What v2.4 is, in one line:** J8 no longer diagnoses what went wrong
with a box — it COMPARES the boxes a node actually has and picks the
better one, in an order that guarantees each case sees its
neighbours' settled geometry.

- **THE ASK IS A COMPARISON, NOT A DIAGNOSIS (v2.3).** For ONE_BOX the
  judge is shown this node's candidate boxes and picks THE BETTER ONE,
  on two ORDERED criteria:
  1. **COMPLETE** — does it contain the whole object? A box that cuts
     through the object, or floats above the surface the object
     plainly rests on, is worse.
  2. **TIGHT ENOUGH** — is it mostly the object, rather than empty
     space or another object's territory?
  **Perfection is NOT required — error tolerance is explicit in the
  prompt: a box only has to be REASONABLE.** The old v2.1 conditions
  ("ship_pano when the vote box absorbed a neighbour / ship_vote when
  the pano cut was occlusion-shaved") are **DEMOTED TO HINTS** printed
  beside each candidate, never the test. They described the usual
  failure modes, and the judge was answering the question of which
  failure mode applied instead of the question of which box is the
  object.
- **CANDIDATE BOXES ARE PER-NODE (v2.2, user ruling — "allow it to
  ship the boxes it is able to evaluate").** Each case carries its OWN
  candidate list, built from the boxes that node actually HAS, each
  with a stable key, its dimensions and a provenance sentence:
  - carved node — `vote` (boxes.vote2, the elected cluster) |
    `pano` (boxes.pano, the founding-mask share)
  - carve-EXEMPT node — `current` (the shipping box = the ORIGINAL
    pre-carve box after the shell clip; it never voted) |
    `rebox_candidate` (the face-on re-box the carve's guard REJECTED;
    shipping it ADOPTS that smaller measured box)
  - `either` is offered ONLY when two candidates agree within
    AGREE_TOL = 5 cm on every face.
  This REPLACED the fixed ship_pano/ship_vote/either enum, which was a
  carved node's vocabulary. obj_018 is the case that proved it: the
  judge had correctly seen that the box over-reaches into ceiling
  architecture and that the rejected magenta candidate is the actual
  fixture, and had no legal way to say so — it was forced to answer
  UNCLEAR.
- **NEW OUTCOME — NO_GOOD_BOX (v2.3, the obj_021 ruling).** Outcomes
  are ONE_BOX | SPLIT | NO_GOOD_BOX | UNCLEAR. NO_GOOD_BOX means the
  evidence DOES settle it and the answer is "none of these boxes is
  usable" — every candidate is grossly wrong. It is DISTINCT from
  UNCLEAR (= the evidence does not settle the question). It carries a
  `reason`, has no `ship`, and materialize KEEPS the node's current
  shipping geometry while recording rule `j8_no_good_box` + an open
  question. **Unused on living_marble (0 cases) — the outcome exists,
  the materialize path is unexercised on real data.**
- **CARVE-EXEMPT NODES CAN NOW BE JUDGED (the obj_018 gap).**
  wall/ceiling nodes skip the carve, so they produced no doubts and
  could never reach the docket. Two new doubt kinds route them in:
  `rebox_rejected_smaller` (the face-on detection is >3× smaller than
  the box, so the guard threw the re-box away) and `rebox_truncated`
  (>= 2 of 4 in-plane sides ran off the frame and kept their priors).
  Their stimulus is the carve's FACE-ON (perp) render — camera READ
  from its params sidecar, never recomputed — **PLUS a BOX-CONTENT
  PANEL:** an isolated render of only the gaussians inside the node's
  OWN box, grown a margin in-plane and opened along the plane normal
  so a fixture that hangs down is not sliced off. The panel exists
  because a face-on render of the SCENE cannot settle "one fixture or
  two" when the ceiling architecture around the fixture is in the
  picture too. Their legend no longer uses the vote/pano vocabulary
  they never had. Census on living: exactly obj_018 and obj_038.
- **DEPENDENCY-ORDERED JUDGING (v2.4, user ruling 08-08 — the
  compute-cheap alternative to a fixed-point loop).** A verdict is
  placed against its NEIGHBOURS' boxes, and another case's verdict can
  MOVE one of those boxes.
  - **ONE SETTLED GEOMETRY MAP** is what every case reads. It starts
    as the carve's shipping boxes (preview manifest, VERBATIM) and
    each ONE_BOX verdict REPLACES its own node's entry with the box it
    NAMED, resolved from the carve's own records exactly as
    materialize resolves it. SPLIT / UNCLEAR / NO_GOOD_BOX never move
    an entry. It ships in the sidecar as `settled_boxes`.
  - **LEVELS** come from geometry only: where one docket box sits
    >= DEP_FRAC = 50% inside another, the SMALLER is judged FIRST
    (inner before outer). A level's cases are independent and still
    run concurrently; levels run in sequence. Sheets are built LAZILY
    inside the per-case work, so a case sees the map as it stands at
    that moment (a moved neighbour changes the prompt, so the cache
    key misses — correct behaviour, not a bug). **Same number of model
    calls, just sequenced.**
  - **THE REAL BUG IT FIXED:** J8 grew obj_063 to x=0.636 (ship=vote)
    while J8s had already cut obj_011 at x=0.335 BECAUSE that was
    obj_063's edge — the two ended up overlapping by 0.30 m. Under the
    settled map the same S-line resolves to 0.636 and the overlap is
    exactly 0.000 m. **split_cuts reads the same settled map** (Phase
    A3).
  - **POST-PASS CONSISTENCY CHECK** (pure arithmetic, no model calls)
    re-measures every docket pair afterwards and records any pair
    whose overlap fraction GREW, under `post_judge_conflicts`. See the
    open below.
- **`--only` MERGES INSTEAD OF CLOBBERING (08-08).** A partial re-run
  repairs one case and keeps every other verdict verbatim in the same
  documents — the same merge-on-write rule the carve adopted. Related:
  a call timeout is a failed ATTEMPT (retry, then UNCLEAR), never an
  exception that kills the whole docket; timeout 240 -> 600 s.

**RESULT on living_marble (USER-ACCEPTED 08-08):** 10 cases, 3 levels.
**4 boxes changed** — obj_018 ceiling light 1.25×0.03×0.52 ->
0.17×0.05×0.16 (ship=rebox_candidate) · obj_021 chair -> its vote box ·
obj_019 pillow -> vote · obj_063 sofa -> vote. **5 kept** (obj_013 /
obj_024 / obj_032 / obj_042 pano; obj_038 current). **1 SPLIT** —
obj_011 one_structure: the back run is obj_063's, the chaise is this
node's. Materialize applied all of it; the additive check passes.

**⚠ OPEN — post_judge_conflicts (RECORDED, NOT ACTED ON):** 5 pairs
whose overlap GREW after judging — obj_024/obj_063 0 -> 32%,
obj_013/obj_019 60 -> 71%, and three more. These are SECOND-ORDER
dependencies the level order cannot see: a box that grows can collide
with a node that was never in its containment chain. No box was
changed and no case was re-opened. A fix is a design decision, not a
threshold tweak (candidates: a second settle pass, or admitting the
grown pairs as a fresh docket).

Design history worth keeping: v2.1 revised v2 on the obj_063 STIMULUS
GAP — J8's private top-6 overlap list dropped obj_063 (the other sofa,
~85% of its volume inside obj_011's box, lost the top-6 to six
pillows), so the judge ruled the sofa case without the decisive fact;
rule adopted, J8 READS relational facts from the graph's own 4g2 edges
and never computes private overlaps. obj_011 is ON BY RULE via
large_empty_notch (plan-fill v2 k-sweep was an honest negative; census
1.52 m² vs 0.18 next). The v2.1 OWNERSHIP-DRIFT open (obj_011's part
owners flipped between runs 8 and 9) is superseded: under v2.4 the
split's ownership is settled geometrically by J8s against the settled
map, and the current verdict is USER-ACCEPTED. (Cross-run stability
has not been re-measured since — if it matters, it is a check to run,
not a claim to carry.)

- **Contract:** GETS one docket case = node + its ADMITTING doubts
  (pano_vs_cluster / culled_clusters / low_plan_fill /
  large_empty_notch / rebox_rejected_smaller / rebox_truncated; AUTO
  doubts only, Rule #1) + that node's OWN candidate boxes and stimuli.
  DECIDES: (1) the outcome, (2) on ONE_BOX, WHICH CANDIDATE BOX IS THE
  OBJECT (undecidable from geometry — user insight 08-07: "exactly
  what the judge will be solving"), (3) on SPLIT, the identity
  annotation + part owners. NEVER edits nodes; verdicts land in the
  sidecar and materialize applies them. A mistake looks like:
  splitting a real single object, blessing one box around two real
  instances, or picking the shaved / over-reaching box over the true
  extent.
- **SPLIT keeps its v2.1 shape:** the footprint must become >= 2
  sub-boxes. IDENTITY is an ANNOTATION: one_structure (the L as ONE
  sectional) | copies(k) (same product, k placements — Probe-A
  vocabulary) | distinct (different objects). Sub-box OWNERS per part:
  this_node | existing:<id> | missing_instance (a work order for the
  loop-back, not an edit). WHERE the box is actually cut is
  **PHASE A3**. Tiebreak [ADOPTED]: when parts read as the same
  product, PREFER copies(k) over distinct — copies is the cheaper
  claim (one asset, k placements) and J9 exists to verify sameness;
  distinct requires a visible identity difference, else it is
  unfalsifiable.
- **UNCLEAR** — shipping default stands; the doubt stays open on the
  record as a work order.
- **Facts from the graph's own edges (REQUIRED, the obj_063 rule):**
  every relational fact in the docket line (which nodes overlap /
  contact / nest with this box) is READ from the loop-back-rebuilt
  4g2 edges — J8 computes NO private overlap lists. Same-class facts
  are NEVER truncated; unrelated-class facts cap at FACT_CAP = 8 by
  relevance.
- **Trigger-aware case openings:** the prompt opens with the doubt
  that admitted the case and asks ITS question — notch case: "this
  empty rectangle sits inside the footprint; is it a missing limb of
  one non-rect object, another object's territory, or nothing?" /
  pano_vs_cluster case: "the founding-mask share is under half the
  elected mass; one occluded object or a shared cluster?" / culled
  case: "a disconnected elected blob was discarded; was it part of
  this object?" / exempt cases: "this box is much larger than what the
  face-on view found in it — one fixture or several?". Same evidence,
  matched question.
- **Stimuli for a CARVED case (one-look rule; cone-map tile OUT):**
  the object's real card renders + the plan view it was detected on,
  with the carve's 3D boxes PROJECTED on them by carve_cams — the SAME
  camera module the renderer used, so an overlay cannot drift from the
  render it annotates. ORANGE = vote · CYAN = pano · GREEN wireframe +
  id = a same-class neighbour's SETTLED box · RED DASHED (plan only) =
  the large_empty_notch rectangle · MAGENTA = the rejected face-on
  re-box. The plan camera is drawn ONLY when its eye validates against
  the eye the carve recorded — no guessed projections.
- **Verdict schema (sidecar graph/multiplicity.json):** per case:
  {node, outcome (ONE_BOX|SPLIT|NO_GOOD_BOX|UNCLEAR), ship? (ONE_BOX
  only — a key from THIS case's candidate list), identity? + count?
  (SPLIT only), parts?[{name, owner}], confidence, reason,
  stimuli_hash}. Document-level: `settled_boxes`, `judge_order`
  (levels + the containment edges that produced them), `settle_log`
  (per case: changed / was / now / why / level), `post_judge_conflicts`.
  Judge-chain claude.exe pattern (env-scrub + parse, cwd passed),
  content-keyed cache. Verdicts REFERENCE nodes, never edit them
  (materialize is the editor).
- **Docket (v2.4, auto):** obj_011 sofa (large_empty_notch) · obj_013 /
  obj_019 pillows, obj_032 magazine, obj_042 tv stand
  (pano_vs_cluster) · obj_021 chair, obj_024 pillow (low_plan_fill) ·
  obj_063 sofa (culled_clusters) · obj_018 ceiling light
  (rebox_rejected_smaller) · obj_038 window (rebox_truncated).
- **USER GATE A0 (design read-back):** this section + notch_review
  page. GATE A1: the sheets (`--sheets-only` builds every stimulus +
  verbatim prompt with ZERO model calls — tool-up = format wrong).
  GATE A2: CANONICAL verdicts — **PASSED 08-08 (v2.4, all 10).**
- **Map:** "J8 · multiplicity" node drawn in the main lane under the
  carve node; still DASHED, because materialize is a trial.

## PHASE A3 — SPLIT CUTS (fixed 3-round chain)
(build: graph/split_cuts.py — J8s. **USER RULING 08-07: NO RECURSION
MACHINERY.** A plain loop over a flat worklist, at most 3 rounds, then it
stops. This section SUPERSEDES the earlier lettered-candidate-options
phrasing of Phase A sub-decision (a) and any "recursive split-cut judge"
wording elsewhere in this plan.)

**STATUS 08-08 ~00:30 (R-S2-42): DESIGN CANON (user-passed R-S2-42)**
— the settling point. Representation objective: discard what existing
boxes take care of; keep only unrepresented content. Residue
criterion: <= 25% uncovered occupied cells, 0.10 m margin.
Independent-support eligibility: cover must be the `a` of an ON edge
to a target other than the case node; riders + unsupported objects
drawn gray dashed, never cover. One-cut-per-call chain (k=3 cap, early
termination). CONVERGENCE: the L resolved in ONE cut / zero doubts —
representation achieved as the union of one new piece + obj_063's +
obj_006's existing boxes. CLOSED open: other-class cover refinement
(subsumed by eligibility). NEW open: the 4g2 pillow-ON gap — the carve
turns resting relations into IN edges; support re-derivation needed
pre-compose.

**08-08 — SPLIT CUTS CONSUME J8's SETTLED MAP.** The case's region
box, the same-class neighbour boxes it draws, the S-lines it measures
and the eligible cover it tests a discard against ALL come from
graph/multiplicity.json `settled_boxes` (the carve's shipping boxes
with every J8 ONE_BOX verdict's named box applied), with the preview
manifest as the per-id FALLBACK — see `settled_carved()`. Living: 46
settled entries, 4 MOVED by a verdict (obj_018, obj_019, obj_021,
obj_063). This is the second half of the v2.4 dependency ruling and it
fixed a real defect: the cut had landed on obj_063's PRE-verdict edge
x=0.335 while J8 then grew obj_063 to x=0.636 — 0.30 m of overlap
between the piece and the very neighbour it was cut against. Reading
the settled map, the same S-line resolves to 0.636 and the overlap is
exactly 0.000 m. Re-run result: obj_011 = one cut at S1 (x=0.636
verbatim), the low-x side discarded at residue 0% against legitimate
cover only (obj_063's box for z<1.824, obj_006's coffee table for the
mid-z strip, bare notch floor for the rest — the pillows resting there
are gray-dashed, never cover), the +x side kept as this_node and
confirmed finished by a second no_cut call. ONE final piece, ZERO
doubts, ZERO guard trips.

- **Contract:** GETS one SPLIT outcome from graph/multiplicity.json plus
  the node's SETTLED box (see above; preview manifest as fallback).
  DECIDES, one region at a time, WHERE the box is cut and WHO owns
  each piece.
  NEVER edits the graph, the carve or multiplicity.json — verdicts are a
  SIDECAR and materialize (Phase C) is the editor. A mistake looks like:
  cutting one physical object in half, leaving two objects inside one
  piece, or landing a cut a few cm off a real boundary that the S-lines
  had measured exactly.
- **ONE JUDGE CALL = ONE REGION = ONE DECISION.** Either
  `{"no_cut", action: keep|discard}` (a one-thing region: keep with an
  owner, or discard with a note) or ONE cut line plus, for EACH of the
  two sides, an INDEPENDENT per-side verdict (user ruling 08-07 late):
  `{action: "keep", owner: this_node | existing:<id>, more_cut:
  true|false}` (+ optional exclusions) or `{action: "discard", note?}`.
  Nothing bigger is ever asked in one breath.
- **KEEP/DISCARD per side (user ruling 08-07 late).** A DISCARDED side
  is DROPPED from this case entirely — empty floor, junk, or the
  territory of an object that already has its own node (e.g. the
  coffee-table region): recorded in the rounds list with its note, no
  owner, never a more_cut, never a final piece. Keeping BOTH sides is
  legal and normal. The old `not_this_object` owner is RETIRED —
  nobody's-territory content is a discard now. The chain continues ONLY
  where a kept side has more_cut=true and ends the moment nothing is
  flagged. PROMPT BIAS, stated explicitly: DECIDE NOW —
  discard-and-finish or keep-and-finish whenever this one cut settles
  the side; flag more_cut ONLY when the kept side visibly contains
  multiple separable things that THIS cut could not separate.
- **REPRESENTATION CHECK on discards (user-adopted 08-07; replaces the
  same-class union-cover >= 0.60 rule AND the mostly-empty exemption
  with ONE rule):** a side may be discarded iff its UNREPRESENTED-
  CONTENT RESIDUE is small — residue = (occupied plan cells, >= 2 dots
  from the carve's own plan_cells grid, covered by NO ELIGIBLE existing
  box) / max(1, occupied cells) <= 0.25. ELIGIBLE = SETTLED boxes
  (08-08; preview manifest per-id fallback) overlapping the side, ANY
  class, plan footprints
  grown 0.10 m on all sides — EXCLUDING RIDERS (the `a` of an ON edge
  whose `b` is the case node in carved_edges: resting objects never
  represent the region beneath them). Cover must be independently
  supported — an ON edge to something other than the case node; the
  carved-edge layer's missing pillow ON edges is a recorded 4g2 open.
  Mostly-empty sides pass automatically (few
  occupied cells => tiny residue — no separate rule). On failure the
  discard is DOWNGRADED to keep {this_node, more_cut: false} with doubt
  "discard_unverified — NN% of the side's content is unrepresented";
  the residue + eligible box ids + excluded box ids with reasons
  (rider | no_independent_support) are recorded on EVERY discard,
  standing or not.
- **The judge answers in GRID VOCABULARY ONLY** — a lattice line name
  (letters = constant-x, numbers = constant-z), a measured special line
  name (S1..), or "between X and Y". It NEVER states a coordinate.
- **Stimulus per region** (promoted verbatim from the two user-passed
  08-07 scratchpad prototypes — promote, don't reinvent): the
  BOX-CONTENT top render — ONLY the gaussians inside this region's box,
  camera straight above and OUTSIDE the room, fov 50 — with
  (a) projected boxes: the region box (orange), same-class neighbours'
  carved boxes (green), overlapping other-class carved boxes (red),
  RIDER boxes thin dashed gray labeled "resting — not cover",
  drawn by the SAME camera that made the render (carve_cams.make_cam,
  the anti-drift module); (b) a DYNAMIC named lattice — pitch chosen
  from {0.1, 0.2, 0.25, 0.5, 1.0} so the longer plan extent carries <= 9
  lines, chess chips at BOTH ends + the world coordinate; (c) MAGENTA
  S-LINES at measured boundaries inside the region (same-class neighbour
  box edges + notch-rect edges from the carve doubts, deduped at
  0.15 m), named S1.. with a LEGEND STRIP appended below the render;
  (d) the object's existing J8 card renders as side context.
- **Snapping is CODE's job, never the judge's:** an S-line pick takes its
  measured coordinate verbatim; a lattice pick takes that line's value,
  then snaps to the nearest measured boundary within 0.25 m if one
  exists on the same axis; "between X and Y" takes an S-line lying
  between them when there is one, else the midpoint (recorded as
  midpoint_fallback). Every cut carries its provenance.
- **THE CHAIN (no recursion):** a flat worklist, at most 3 ROUNDS.
  Round 1 — the case box gets one judged cut. Rounds 2 and 3 — every
  KEPT piece flagged more_cut gets one judged cut, with a FRESH
  sub-render and a re-derived grid + S-lines for that piece. The chain
  ends the moment nothing is flagged more_cut; after round 3 the loop
  STOPS UNCONDITIONALLY regardless.
- **GUARDS:** a piece with either plan extent < 0.25 m is auto-done and
  is NEVER judged; at most 8 pieces per case (the chain stops early and
  the remaining more_cut pieces are recorded); any piece still wanting a
  cut when the chain stops ships UNCUT with doubt "split_incomplete"; an
  unparsable model reply twice ships that region uncut; a cut line
  outside the region or outside the region's vocabulary ships it uncut.
- **Record:** rounds are a FLAT LIST — [{round, region_box, stimulus,
  verdict, snapped_cut, pieces}] — no tree structures. Plus a flat final
  pieces list [{box, owner, provenance}] of KEPT pieces only: discarded
  sides live in the rounds list (with their notes) and never appear in
  final pieces.
- **Docket:** SPLIT-outcome cases from graph/multiplicity.json. A
  SPLIT/distinct case whose parts ALL map to existing nodes whose carved
  boxes cover the region needs NO cuts: record
  {"resolution": "covered_by_existing", owners} MECHANICALLY, zero model
  calls. Only cases needing real geometry (one_structure, copies, or any
  missing_instance part) enter the chain.
- **Outputs:** graph/split_cuts.json (per case: the rounds list + flat
  final pieces) and graph/split_sheets/<case>/ (stimulus pngs + verbatim
  prompt txts + a small index.html). Content-keyed verdict cache (region
  box + prompt + stimulus bytes) like the sibling judges; claude.exe
  through the same judge-chain pattern (env-scrub, retry x2,
  malformed -> ship-uncut fallback).
- **CLI:** `python graph/split_cuts.py --scene <s> [--only ids]
  [--sheets-only] [--rounds 3] [--model sonnet]`.
- **USER GATE A3:** the per-case sheet (stimulus + the rounds list +
  final pieces). Watch item: piece owners that disagree with J8's
  identity annotation are the ownership-drift open (Phase A, ledger
  item 4) becoming visible as geometry.
- **Map:** dashed "J8s · split cuts" node in the J-lane under J8; solid
  when materialize consumes the cuts.

## PHASE A2 — ROW-COUNT ATTRIBUTE JUDGE (wire: multiplicity probe A)
(user 08-07: "something that would tell shopping if it should look for
multiple of the same to fill the box")

- Wire experiments/multiplicity_probe.py PROBE A (crop -> single-or-row;
  12/12 correct + stable x3 on bedroom, ruled wire-ready 08-05) as a
  graph-stage judged attribute: per node, single_vs_row (+ rough count)
  from its crop. Consumer: shopping's native_fit k ceiling — REPLACES
  the hardcoded ROWABLE_CATS book/books list (a label-list blemish;
  LLM judgment is the doctrine-legal form). Probe B stays parked
  (over-scoped, ruled 08-05).
- **USER GATE A2:** attribute sheet (crop + verdict per node).
- **Map:** draw as a J-lane node when it lands.

## PHASE B2 — THE LOOP-BACK: carved state re-enters the graph chain
(user ARCHITECTURE RULING 08-07, superseding the "incremental pair
facts" framing: "after slice vote the scene goes all the way back up to
geometric edges and down the judges again — just with two more judges
at the end")

**STATUS 08-07 late (R-S2-36..39): IMPLEMENTED + RUN.**
graph/rederive_carved_edges.py (derive_edges() extracted from
build_edges.py, regression = field-identical re-derivation) writes the
ADDITIVE graph["carved_edges"] layer — 46 resolved nodes × carved
boxes verbatim from the preview manifest; 84 edges, self-check PASS.
Gate-B2 diff delivered (pairs appeared/dissolved per run). J0/J1 run
ON the layer via --edges-from carved_edges: chair-merge obj_020 ↔
obj_041 SAME .75 (merge pending materialize) · window-vs-curtain
obj_038 ↔ obj_053 DISTINCT .68 — both on the record. Re-run per carve
run (runs 8/9/10), J4/J6 pure cache hits throughout.

- Carved boxes re-enter at 4g2: geometric edge facts re-derived
  mechanically; the SAME judge chain runs down (J0 triage on the new
  nesting candidates; J1 only on genuinely new pairs; J4 names / J6
  appearance+existence are pure cache hits — crop stimuli unchanged by
  the carve); then the two NEW benches (J8 split, J9 same-product);
  then materialize. Second pass, not a cycle (carve needed resolved
  identity to exist). Support is NOT graph business (user: compose
  derives it, Phase D).
- **ORDER EXPLICIT (user-adopted 08-07 late): B2 runs BEFORE the
  J8/J9 canonical verdicts.** The chain is 4g2 re-derive → J0/J1
  (J4/J6 cached) → THEN J8/J9 at the end — because J8 must READ
  its relational facts from the rebuilt 4g2 edges (the obj_063
  stimulus-gap lesson, Phase A). The 08-07 J8 verdict runs (obj_011 /
  obj_019 / obj_024) were DESIGN TRIALS of the machinery, not
  canonical verdicts; canon runs inside this pass.
- Drawn on the map: dashed loop-back edge carve -> 4g2 (legend:
  dashed = loop-back).
- **USER GATE B2:** edge/triage diff (pairs appeared/dissolved) + any
  new J1 verdicts.

## PHASE B — SAME-PRODUCT VERDICTS (run: graph/judge_same_product.py)

**STATUS 08-08: RUN (6/6), GATES OPEN — and ⚠ UNSTABLE.** Two runs 20
minutes apart on near-identical data returned DISJOINT sets (pillows
{obj_024, obj_037} -> {obj_015, obj_016, obj_026}; lights group 3
flipped false -> true). J9 has NO verdict cache, so every run
re-decides from scratch. This is an OPEN, and it blocks trusting the
12 same-product annotations materialize wrote. Candidate fixes (design
decision, user-gated): a content-keyed verdict cache like J8's, a
repeat-vote consensus, or PAIRWISE comparisons instead of asking one
call to pick a subset out of 9. Set-member id normalization was fixed
at source (some groups returned bare ints).

- **Contract:** GETS the 6 deterministic groups + carved sizes + carve
  doubts as context. DECIDES per group: same product? which members
  excluded? ONE canonical size. A mistake looks like: unifying
  different products (magazine ≠ book on the same shelf) or letting
  one bad carve set the group's size.
- **OPEN DECISION (user) before running:** current draft is TEXT-ONLY
  (names + sizes + doubts). Add crop evidence (member contact sheet
  per group, one image per call) or run text-only first and see?
  "Same product" is substantially a visual claim — recommend crops.
- **Watch item:** chair group's shared-anchor came up None (design
  expected the table via the 2× footprint rule) — check before trusting
  anchor context in prompts.
- **Sequencing:** after Phase A (multiplicity may split/absorb members
  — same-product should rule on the post-multiplicity node set).
- **PASS PLACEMENT RULED (user 08-07): second pass ONLY, never the
  first flow-through.** Rationale: the verdict binds identity to SIZE
  (canonical size = shopping's input) and sizes are only trustworthy
  post-carve; membership is only final post-J8; one call per group
  makes a split visual/size run pointless. General rule: geometry-bound
  judges (J8/J9/pair-fact rerun) = second pass; pixel-only judges
  (names, existence, appearance, Probe A count) = first pass, cached
  through the second.
- **USER GATE B:** group sheets + verdicts. Shopping consumption is
  NOT this phase (wire at S4 when compose runs).
- **Map:** draw "J9 · same-product" beside J8 when verdicts run.

## PHASE C — MATERIALIZE v2 (build: graph/materialize_carve.py)

**STATUS 08-08: BUILT + RUN ONCE, status UNTESTED-TRIAL.** The
additive `graph["carved"]` block exists and the viewer serves it
(amber layer). On living_marble, after the v2.4 J8 pass: **45 boxes
out of 46 resolved · 4 box swaps · 1 split piece · 1 merged away · 12
same-product annotations · 1 conflict** (J1 merged obj_029 <-> obj_036
which J9 ruled NOT the same product — recorded, merge wins, J9's false
has no effect) + 9 open questions on 8 nodes. Additivity verified
twice, idempotent, backup written. **NOT promoted to canon** — the box
canon is still the slice-vote carve layer.

**⚠ THE GAPS (from R-S2-43, all still open):** (1) the L loses its
one_structure linkage — obj_063 and obj_011#1 ship as two unrelated
sofas, so shopping would buy two; (2) obj_063 carries no
machine-readable pointer that it represents the discarded back run
(the ownership lives in a discard note's free text); (3) piece ids
contain "#", which will break path-shaped consumers; (4) edges are NOT
re-derived, so carved_edges still references nodes the carved set no
longer has; (5) 3 of 6 materialize rules never fired on real data
(ship_vote swap, existing:<id> piece drop, covered_by_existing) —
synthetic-only, treat as unproven, and `j8_no_good_box` joins them
(0 cases on living); (6) J9 canonical sizes diverge sharply from
carved boxes (pillow 0.376 vs shipping 0.56) — shopping needs an
explicit precedence rule.

- **Contract:** GETS resolved layer + carve block + preview manifest +
  multiplicity/same-product verdicts. WRITES the new additive layer =
  THE canonical handoff (working name graph["carved"] — LAYER NAME =
  USER DECISION): carved boxes folded in; node set edited per
  multiplicity verdicts (splits get part nodes with carve arm/cluster
  geometry); same-product groups recorded (canonical size rides the
  group, per-node boxes stay honest); contact-edge facts RE-DERIVED
  mechanically from carved geometry (the 08-09 poisoned-edge ruling);
  poisoned resolved edges + preview manifest RETIRED to audit status.
  Targeted appearance pass (describe_nodes --appearance-only) for
  nodes multiplicity created — nothing else re-judged.
- A mistake looks like: any silent geometry edit (boxes must be
  VERBATIM carve outputs), or an old-layer mutation (record-then-judge:
  layers are append-only).
- **USER GATE C:** the carved layer in the viewer as the new "scene
  model" default + a diff sheet (node set changes, edge rebuild counts).
- **Map:** draw "4g5 · CARVED = CANONICAL handoff" node; carve card's
  END-STATE CONTRACT marked delivered; preview-manifest mentions
  flipped to audit.

## PHASE D — S1/COMPOSE ON CARVED GEOMETRY

- Point S1 supported_by at the carved layer; run the compose chain in
  true meters on honest boxes for the first time. The chairs' shaved
  bottoms are the user's predicted snap/supported-by test case.
- **USER GATE D:** standard compose review surfaces.
- **Map:** step-3 cards get their input line updated (carved layer, not
  resolved).

## PHASE E — RUNNER WIRING + PROMOTION

- run_scene.py stage order: … → graph judges → carve → J8/J9 →
  materialize → compose. Understand the 44→45 count delta before
  wiring (R-S2-30 note). Wipe-rules for slice/vote render caches
  respected by the runner.
- **Map:** carve's outgoing edge drawn SOLID; "wiring pending" labels
  removed. This is the promotion gate the whole plan walks toward.
- Commit/push checkpoints remain the user's call throughout.

## DESIGN CANDIDATES ON THE LEDGER (recorded, NOT scheduled — each is a
user-gated design decision; born from the parked obj_009/obj_081
finding, R-S2-33)

1. **Instance-context facts for existence cases:** the docket line
   gains mechanical facts — "overlaps no surviving same-class node /
   nearest same-class at X m / N same-class instances in scene" —
   position + product regularity as evidence (position discriminates
   duplicate vs new instance; appearance alone cannot). Judge still
   rules; no label lists.
2. **Verdict-dependency check at materialize (pure code):** a
   kill-reason that references a node which was itself removed reopens
   the case as UNCLEAR (the obj_009/obj_081 co-accused circularity).
3. **Vote-dot fill-fraction doubt** (from the obj_011 L-miss, earlier
   entry above).
4. ~~**Mechanical ownership assignment for J8 splits**~~ (from the
   run-8→9 ownership drift, R-S2-38) — **SUPERSEDED 08-08.** Under
   v2.4 the split's ownership is settled geometrically by J8s against
   J8's settled map, and the current verdict is USER-ACCEPTED. Kept on
   the ledger only as history.
5. **J8 confidence spread** — narrow band across canonical verdicts;
   watch for anchoring; no fix scheduled.
6. **A second settle pass for post_judge_conflicts** (from the 5
   grown-overlap pairs, 08-08): after the level pass, re-open the
   pairs whose overlap GREW as a fresh docket, or run one more settle
   round. Currently recorded only. This is a DESIGN decision — not a
   threshold tweak.

## THE REMAINING OPENS (08-08, after the J8 v2.4 canonization)

Everything else in this plan has run at least once. What is actually
outstanding:

1. **post_judge_conflicts** — 5 pairs whose overlap grew after judging
   (Phase A). Second-order dependencies the level order cannot see.
   RECORDED, not acted on.
2. **The J9 instability** — no verdict cache, disjoint sets across
   runs 20 minutes apart (Phase B). Blocks trusting the 12
   same-product annotations.
3. **The materialize gaps** — the six items listed in Phase C, plus
   the two never-fired paths (`j8_no_good_box`, ship_vote swap).
   These gate Phase C's promotion from UNTESTED-TRIAL to the
   canonical handoff.

Then Phase D (compose on carved geometry) and Phase E (runner wiring +
the solid edge on the map).

## ORDER + WHY

A → A3 → A2 → B2 → B → C → D → E.
A3 follows A directly: it consumes A's SPLIT verdicts and produces the
geometry those verdicts only asserted, so it must land before C
(materialize folds the cuts in).
A here = the DESIGN/BUILD work (sheets + trials); J8's CANONICAL
verdicts execute inside B2's pass, at its end (order ruling in Phase
B2 — J8 reads the rebuilt 4g2 edges first). WITHIN A, v2.4 adds an
internal order: the docket's own dependency LEVELS, and A3 reads the
settled map A leaves behind. A2 is independent (crop-based attribute) — may run
alongside A. B2 before B (merges change group membership). A+A2+B2+B
before C (materialize folds all verdicts in one pass, once). C before
D (compose must read the canonical layer, not the preview side-file).
E last (wire only what proved out downstream — the standing promotion
rule).

The three multiplicity flavors (nomenclature guard): J8 = one box,
several DIFFERENT objects (split). Probe A = one box, several COPIES
(fill with k). J9 = several boxes, SAME product (buy once).

## OPEN DECISIONS — ALL RULED (user 2026-08-07, "i agree with your
recommendation")

1. Phase B evidence: WITH CROPS — member contact sheet per group, one
   image per call.
2. Phase C layer name: graph["carved"] (fourth additive layer).
3. Canonical size: GROUP ATTRIBUTE for shopping; per-node boxes stay
   verbatim carve outputs, never overwritten by the group size.
