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

## STATE ENTERING THIS PLAN (updated R-S2-35, 08-07 late)

- Carve run 6 = current geometry: scene_manifest_slicevote_preview.json
  (45 objects; 27 carved_pano / 3 carved / 8 kept_wall / 7
  kept_ceiling; the 4 R-S2-35 fixes in — half-space shell filter,
  slice shell clamp, winning-blob pano filter, plan-fill v2 record).
- scene_graph.json `carve` block re-applied post-run-6: status + tiers
  + typed doubts per node (26 nodes with doubts); docket = AUTO doubts
  only (the 08-07 user_routed channel was a Rule-1 violation, removed;
  obj_011 now admits via large_empty_notch BY RULE).
- Same-product grouping dry-run current: 6 groups (chairs×6, pillows×9,
  lights×4+×3, magazines×3+×2). Verdicts never run.
- Resolved layer = identity canon; its boxes pre-carve (stale); ON
  edges declared poisoned 08-09 (rebuild post-carve).

## PHASE A — J8 SPLIT-CELL JUDGE (graph/judge_multiplicity.py)

**STATUS 08-07 late (R-S2-35): DESIGN v2 SETTLED** (user directive
"commit and design j8 correctly"; sub-decisions adopted on the stated
leans, read-back at Gate A0). Docket = run 6, 5 cases, obj_011 ON BY
RULE via large_empty_notch (the R-S2-34 fill-fraction candidate is
SUPERSEDED — plan-fill v2 k-sweep was an honest negative, the notch
metric is the adopted form; census 1.52 m² vs 0.18 next). Old run-4
sheets superseded; sheets rebuild in the v2 form below.

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
- **Outcome taxonomy (5):**
  - ONE_OBJECT — box ruling required: ship_pano (vote box absorbed a
    neighbor) | ship_vote (pano cut was occlusion-shaved) | either
    (boxes agree within tolerance).
  - ONE_OBJECT_NONRECT — single object, non-box footprint (the L as
    ONE sectional). CODE cuts the rectangles [sub-decision (a),
    ADOPTED]: mechanical decomposition of the occupied footprint
    (NOTCH_K occupancy) into >= 2 axis-aligned rectangles; per-part
    boxes carry the elected heights. The judge only classifies —
    part-naming needs pixel precision judges don't have; mechanical
    cuts are reproducible and Rule-1-safe.
  - MULTIPLE_COPIES — count-k of the same product in one box (Probe-A
    vocabulary; the "6 matching chairs" family). Ships count + the
    per-copy footprint from the same mechanical decomposition.
  - MULTIPLE_DISTINCT — ownership itemization per part:
    this_node | existing:<id> | missing_instance (missing_instance is
    a work order for the loop-back, not an edit).
  - UNCLEAR — shipping default stands; the doubt stays open on the
    record as a work order.
  - Tiebreak [sub-decision (b), ADOPTED]: when parts read as the same
    product, PREFER MULTIPLE_COPIES over MULTIPLE_DISTINCT — copies
    is the cheaper claim (one asset, k placements), and J9 exists to
    verify sameness; DISTINCT requires a visible identity difference,
    else it is unfalsifiable.
- **Trigger-aware case openings:** the prompt opens with the doubt
  that admitted the case and asks ITS question — notch case: "this
  empty rectangle sits inside the footprint; is it a missing limb of
  one non-rect object, another object's territory, or nothing?" /
  pano_vs_cluster case: "the founding-mask share is under half the
  elected mass; one occluded object or a shared cluster?" / culled
  case: "a disconnected elected blob was discarded; was it part of
  this object?". Same evidence, matched question.
- **Stimuli v2 (one-look rule; cone-map tile OUT — user ruling):**
  the object's real card renders + top view with boxes PROJECTED on
  them — orange vote box, cyan pano box, red dashed notch rectangle
  (rect_m from the doubt payload) when present. REQUIRES the shared
  camera helper: lift the card-camera math out of carve_slicevote.py
  (MatCamLite/make_cam + the card view construction) into a module
  both the carve and the sheet builder import, so overlays cannot
  drift from the renders they annotate.
- **Verdict schema (sidecar graph/multiplicity.json):** per case:
  {node, outcome, box_ruling?, count?, parts?[{footprint_rect_m,
  owner}], confidence, reason, stimuli_hash}. Judge-chain claude.exe
  pattern (judge_same_product's env-scrub + parse), content-keyed
  cache (prompt+stimuli hash). Verdicts REFERENCE nodes, never edit
  them (materialize is the editor).
- **Docket (run 6, auto):** obj_011 sofa (large_empty_notch) ·
  obj_019 pillow, obj_021 chair, obj_029 magazine (pano_vs_cluster) ·
  obj_032 magazine (culled_clusters).
- **USER GATE A0 (design read-back):** this section + notch_review
  page. GATE A1: the v2 sheets (stimulus per case — tool-up = format
  wrong). GATE A2: verdicts + reasons per case.
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

- Carved boxes re-enter at 4g2: geometric edge facts re-derived
  mechanically; the SAME judge chain runs down (J0 triage on the new
  nesting candidates; J1 only on genuinely new pairs; J4 names / J6
  appearance+existence are pure cache hits — crop stimuli unchanged by
  the carve); then the two NEW benches (J8 split, J9 same-product);
  then materialize. Second pass, not a cycle (carve needed resolved
  identity to exist). Support is NOT graph business (user: compose
  derives it, Phase D).
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

## ORDER + WHY

A → A2 → B2 → B → C → D → E.
A before B2/B (J8 splits change the node set; pair facts and grouping
must see it). A2 is independent (crop-based attribute) — may run
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
