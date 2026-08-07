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

## STATE ENTERING THIS PLAN (all user-passed)

- Carve run 4 = current geometry: scene_manifest_slicevote_preview.json
  (45 objects; 28 arm / 2 carved / 8 kept_wall / 7 kept_ceiling).
- scene_graph.json `carve` block (R-S2-31): status + tiers + typed
  doubts per node (28 nodes), obj_011 user-routed to multiplicity.
- Same-product grouping dry-run current: 6 groups (chairs×6, pillows×9,
  lights×4+×3, magazines×3+×2). Verdicts never run.
- Resolved layer = identity canon; its boxes pre-carve (stale); ON
  edges declared poisoned 08-09 (rebuild post-carve).

## PHASE A — SPLIT-CELL JUDGE (built: graph/judge_multiplicity.py)

**STATUS 08-07 late:** BUILT review-first (8-case sheets + prompts,
zero verdicts). Docket rules final: ownership gap (arm<50%) +
discarded candidate (culled>0) + shape gap (plan_fill<0.65, rule 3,
R-S2-34). Run 5 launched with all three; after it the docket
regenerates WITH obj_011 (by rule). PENDING USER SIGN-OFF: the
5-outcome ask taxonomy + sheet redesign (cone map out, boxes projected
onto real renders) — full proposal in R-S2-34 / the 08-12 handoff.

- **Contract:** GETS the carve block's multiplicity docket — AUTO
  DOUBTS ONLY (arm_vs_cluster ×6, culled_clusters ×2; Rule #1 — the
  user_routed channel built 08-07 was a violation, removed same day;
  obj_011's L-question = honest miss on the eval ledger, rule-design
  candidate below) — plus visual stimuli. DECIDES per case: ONE_OBJECT |
  MULTIPLE (named parts, PART_OF_STRUCTURE grouping, per-part boxes
  from the carve's arm/cluster geometry) | UNCLEAR (ships open as a
  work order). A mistake looks like: splitting a real single object,
  or blessing one box around two real instances.
- **Stimuli (one-look rule):** plan-view tile (clip-top render) with
  the arm box vs vote-cluster box drawn + the cone-map card strip for
  that object. Judge sees the SAME evidence the user judged in
  R-S2-26..30.
- **Pattern:** judge-chain claude.exe calls (judge_same_product's
  env-scrub + parse), content-keyed cache, sidecar
  graph/multiplicity.json. Verdicts REFERENCE nodes, never edit them
  (materialize is the editor).
- **Docket (living, auto):** obj_019/obj_024 pillows, obj_021/obj_068
  chairs, obj_029 magazine, obj_042 tv stand (arm_vs_cluster);
  obj_034 glass door, obj_032 magazine (culled). 8 cases.
- **EVAL FINDING (recorded, not fixed — Rule #1):** the doubt rules
  miss obj_011's L-question (arm ratio above the 0.5 gate because its
  own masks are broad). Scene-agnostic rule CANDIDATE for a user gate,
  designed from the failure mode not the instance: vote-dot
  FILL-FRACTION of the vote-box AABB (an L fills ~half its bounding
  box; computable for every node from data already in the report, no
  labels). Decide at a gate; verify what else it fires on before
  adopting.
- **USER GATE A:** case sheets (stimulus + verdict + reason per case).
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
