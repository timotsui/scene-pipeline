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

## STATE ENTERING THIS PLAN (updated R-S2-39, 08-07 late)

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
  layer + J0/J1 on it; **Phase A J8: CANONICAL VERDICTS RUN** on the
  7-case docket (status lines in each phase below).
- Same-product grouping dry-run current: 6 groups (chairs×6, pillows×9,
  lights×4+×3, magazines×3+×2). Verdicts never run.
- Resolved layer = identity canon; its boxes pre-carve (stale); the
  poisoned ON edges are superseded by the rebuilt carved_edges layer.
- **NEXT: Phase C materialize design**, carrying the queued opens:
  mechanical ownership assignment for J8 splits (run-8→9 drift);
  eyeballs — obj_042 TV-stand extent (run 9) + curtain re-box under
  the dist-clamped camera (run 10); J8 confidence clustering .62–.83
  (watch for anchoring).

## PHASE A — J8 SPLIT-CELL JUDGE (graph/judge_multiplicity.py)

**STATUS 08-07 late (R-S2-36..39): v2.1 BUILT + CANONICAL VERDICTS
RUN** on the 7-case docket, inside the Phase-B2 loop-back pass as the
order ruling required (facts read from the rebuilt carved_edges; the
earlier 3 verdict runs were design trials of the machinery only).
Verdicts (run-9 fresh; run 10 = 7/7 cache hits, stimuli unchanged):
obj_011 SPLIT/one_structure .62 (THE L RESOLVED — one sectional,
PART_OF_STRUCTURE, mechanical rectangle cut at materialize) · obj_024
SPLIT/distinct 4 owners .65 · obj_019 ONE_BOX/ship_pano .70 · obj_029
ship_pano .62 · obj_032 either .74 · obj_042 ship_pano .83 · obj_068
ship_vote .62 (the shaved chair: vote box bounds the full chair).
**KNOWN OPEN — OWNERSHIP DRIFT:** obj_011's SPLIT part owners flipped
between runs 8 and 9 (existing:obj_063/this_node →
this_node/this_node) while geometry barely moved. DESIGN NOTE QUEUED
(for Phase C): mechanical ownership assignment — code assigns split
parts by overlap with existing nodes' boxes, the judge rules identity
only. Companion note: confidences cluster .62–.83 (low spread — watch
for anchoring). Design history: v2.1 revised v2 same day on the
obj_063 STIMULUS GAP — J8's private top-6 overlap list dropped
obj_063 (the other sofa, ~96% overlap with obj_011's vote box, lost
the top-6 to six pillows), so the judge ruled the sofa case without
the decisive fact; rule adopted: J8 READS relational facts from the
graph's own 4g2 edges and never computes private overlaps. obj_011 is
ON BY RULE via large_empty_notch (plan-fill v2 k-sweep was an honest
negative; census 1.52 m² vs 0.18 next).

- **Contract:** GETS one docket case = node + its ADMITTING doubts
  (pano_vs_cluster / culled_clusters / low_plan_fill /
  large_empty_notch; AUTO doubts only, Rule #1) + v2 stimuli. DECIDES
  two things per case: (1) the multiplicity outcome, (2) WHICH
  GEOMETRY SHIPS (the pano-vs-vote ambiguity is undecidable from
  geometry — user insight 08-07: "exactly what the judge will be
  solving"). NEVER edits nodes; verdicts land in the sidecar and
  materialize applies them. A mistake looks like: splitting a real
  single object, blessing one box around two real instances, or
  picking the occlusion-shaved box over the true extent.
- **Ask v2.1 (representation first — outcome = ONE_BOX | SPLIT |
  UNCLEAR):** the judge answers the REPRESENTATION question first;
  identity rides as an annotation, not a top-level outcome.
  - ONE_BOX — one box represents this node. Box ruling required
    (carried from v2): ship_pano (vote box absorbed a neighbor) |
    ship_vote (pano cut was occlusion-shaved) | either (boxes agree
    within tolerance).
  - SPLIT — the footprint must become >= 2 sub-boxes. IDENTITY is an
    ANNOTATION on the split: one_structure (the L as ONE sectional) |
    copies(k) (same product, k placements — Probe-A vocabulary) |
    distinct (different objects). Sub-box OWNERS per part:
    this_node | existing:<id> | missing_instance (missing_instance is
    a work order for the loop-back, not an edit). CODE cuts the
    rectangles mechanically [sub-decision (a), ADOPTED — carried]:
    NOTCH_K-occupancy decomposition into axis-aligned rectangles;
    per-part boxes carry the elected heights. The judge only
    classifies — part-naming needs pixel precision judges don't have;
    mechanical cuts are reproducible and Rule-1-safe.
  - UNCLEAR — shipping default stands; the doubt stays open on the
    record as a work order.
  - Tiebreak [sub-decision (b), ADOPTED — now inside the identity
    annotation]: when parts read as the same product, PREFER
    copies(k) over distinct — copies is the cheaper claim (one asset,
    k placements), and J9 exists to verify sameness; distinct
    requires a visible identity difference, else it is unfalsifiable.
- **Facts from the graph's own edges (REQUIRED, the obj_063 rule):**
  every relational fact in the docket line (which nodes overlap /
  contact / nest with this box) is READ from the loop-back-rebuilt
  4g2 edges — J8 computes NO private overlap lists. The retired
  private top-6 list is the cautionary tale above.
- **Neighbor wireframes (REQUIRED, v2.1):** same-class neighbor boxes
  get DRAWN on the judge's panels (green wireframe) so the
  is-the-rest-another-object evidence is visible, not just numeric.
- **Trigger-aware case openings:** the prompt opens with the doubt
  that admitted the case and asks ITS question — notch case: "this
  empty rectangle sits inside the footprint; is it a missing limb of
  one non-rect object, another object's territory, or nothing?" /
  pano_vs_cluster case: "the founding-mask share is under half the
  elected mass; one occluded object or a shared cluster?" / culled
  case: "a disconnected elected blob was discarded; was it part of
  this object?". Same evidence, matched question.
- **Stimuli v2.1 (one-look rule; cone-map tile OUT — user ruling):**
  the object's real card renders + top view with boxes PROJECTED on
  them — orange vote box, cyan pano box, red dashed notch rectangle
  (rect_m from the doubt payload) when present, green wireframe for
  same-class neighbor boxes (the v2.1 addition). REQUIRES the shared
  camera helper: lift the card-camera math out of carve_slicevote.py
  (MatCamLite/make_cam + the card view construction) into a module
  both the carve and the sheet builder import, so overlays cannot
  drift from the renders they annotate.
- **Verdict schema (sidecar graph/multiplicity.json):** per case:
  {node, outcome (ONE_BOX|SPLIT|UNCLEAR), box_ruling? (ONE_BOX only),
  identity? + count? (SPLIT only), parts?[{footprint_rect_m, owner}],
  confidence, reason, stimuli_hash}. Judge-chain claude.exe
  pattern (judge_same_product's env-scrub + parse), content-keyed
  cache (prompt+stimuli hash). Verdicts REFERENCE nodes, never edit
  them (materialize is the editor).
- **Docket (run 9/10, auto):** obj_011 sofa (large_empty_notch) ·
  obj_019 pillow, obj_029 magazine (pano_vs_cluster) · obj_032
  magazine (culled_clusters) · obj_024 pillow, obj_042 tv stand,
  obj_068 chair (joined run 9 with wall context restored; obj_021
  dropped).
- **USER GATE A0 (design read-back):** this section + notch_review
  page. GATE A1: the v2.1 sheets (stimulus per case — tool-up =
  format wrong; neighbor wireframes present). GATE A2: CANONICAL
  verdicts — RAN inside the Phase-B2 loop-back pass on rebuilt-edge
  facts, USER-PASSED with today's arc (R-S2-36..39).
- **Map:** draw "J8 · multiplicity" node into the main lane under the
  carve node when it lands.

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
  (J4/J6 cached) → THEN J8/J9 at the end — because J8 v2.1 must READ
  its relational facts from the rebuilt 4g2 edges (the obj_063
  stimulus-gap lesson, Phase A). Today's J8 verdict runs (obj_011 /
  obj_019 / obj_024) were DESIGN TRIALS of the machinery, not
  canonical verdicts; canon waits for this pass.
- Drawn on the map: dashed loop-back edge carve -> 4g2 (legend:
  dashed = loop-back).
- **USER GATE B2:** edge/triage diff (pairs appeared/dissolved) + any
  new J1 verdicts.

## PHASE B — SAME-PRODUCT VERDICTS (run: graph/judge_same_product.py)

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
4. **Mechanical ownership assignment for J8 splits** (from the
   run-8→9 ownership drift, R-S2-38): code assigns split-part owners
   by overlap with existing nodes' boxes; the judge rules identity
   only. Design at Phase C.
5. **J8 confidence clustering** (.62–.83 narrow band across all
   canonical verdicts) — watch for anchoring; no fix scheduled.

## ORDER + WHY

A → A2 → B2 → B → C → D → E.
A here = the DESIGN/BUILD work (v2.1 sheets + trials); J8's CANONICAL
verdicts execute inside B2's pass, at its end (order ruling in Phase
B2 — J8 reads the rebuilt 4g2 edges first). A2 is independent (crop-based attribute) — may run
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
