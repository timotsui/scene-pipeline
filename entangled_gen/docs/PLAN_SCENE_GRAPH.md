# PLAN — semantic scene graph (deliberate extraction from splat scenes)

Canonical plan + progress doc for this effort, per the production-session
workflow (see PLAN_GAUSSIAN_CUT_AND_SPLAT_ANALYZER.md for the sibling effort;
same rules govern: progress log updated on every state change, resume
protocol at bottom, checkpoints are hard stops unless autonomous mode is
explicitly authorized).

- Created: 2026-07-22
- Current state: 🔴 CHECKPOINT R1 — record review WAITING ON USER
  (2026-07-26 late; REVIEW_LOG R10, rebuilt per the §0a.0 amendment). The
  design is settled (**record, then judge** — §0a; §0a.0: NO pre-merges,
  dedup stage retired) AND pass 1 is BUILT: record builder (f30 → 108
  nodes) + edges (incl. 14 SAME_CANDIDATE) + the viewer "graph record"
  layer (progress rows R-0..R-2 below). Judge passes gated on R1. G1 (analyzer-seeded graph
  review) is MOOT — v1 archived as scene_graph_v1.json / graph/crops_v1;
  its Steps 1–4 remain DONE as machinery/lessons (edge thresholds,
  appearance batching + cache, review-page builder).
- Scene: bedroom_marble first (the fully-instrumented scene)

## 0a. SETTLED 2026-07-26 (pm) — what the scene graph IS: record, then judge

The record-vs-judge question resolved: **both, in that order** — two passes
over one file, `scene_graph.json`.

### 0a.0 AMENDMENT 2026-07-26 (late, user: "record both objects and
### indicate their relationship faithfully") — NO pre-merges at all

The earlier carve-out (geometry-only dedup doing confident IoU ≥ 0.6
merges BEFORE the record) is REVOKED after the user saw obj_057 absorbed
into obj_007 on the record card. Since even a confident merge is a
commitment about object identity, it belongs to the judge:

- **The dedup stage is RETIRED entirely** (`manifest_dedup.py` kept
  runnable, banner in its docstring; nothing consumes it). The record
  builds from the f30 manifest directly — every f30 object = one node,
  duplicates included (bedroom_marble: 102 detection nodes).
- **`build_edges.py` computes the duplicate-suspect pairs itself** as
  SAME_CANDIDATE edges with a `zone` field: "confident" (IoU ≥ 0.60) or
  "gray" (IoU .40–.60 + containment ≥ .90). Bedroom_marble: 14 edges =
  10 confident + 4 gray (lamp↔ceiling-light is confident, both nodes
  present, relationship stated with its numbers).
- **The judge's same-vs-part pass resolves EVERY pair, confident zone
  included** — a confident-zone verdict of "same" produces the merge as a
  VERDICT (reversible, cached); the record is never edited.
- Consequence: node-level naming questions now mostly ARISE at judge time
  (post-merge, over the union multiset) rather than at record time.

### 0a.1 Pass 1 — the RECORD (deterministic, zero LLM)

Writes down everything extraction already knows; commits to nothing.
Byte-reproducible. Contents:

- **Scene-level:** frame conventions (up axis, units — the mirror-bug
  lesson), source lineage (manifest version, pano bundle, **prompt.txt** —
  the generation prompt is evidence), envelope summary (floor/ceiling
  heights, wall planes).
- **Nodes** = f30 manifest objects VERBATIM (§0a.0: no dedup stage,
  duplicates included) + envelope architecture (floor/ceiling/walls).
  Windows/doors/curtains are ordinary object nodes — typing settled later
  by geometry + the judge.
- **Labels, plural:** each node keeps the FULL label multiset from all
  member detections with scores; primary label kept but
  `label_provisional: true`. No winner picked.
- **Geometry:** observed box AND amodal-completed box, each tagged with its
  method; yaw null (honest gap).
- **Evidence as pointers:** member detection ids, per-view 2D boxes, mask
  refs, source tiles; per-node crops are CUT here (deterministic) so the
  record is reviewable by eye and pass 2 reads them.
- **Geometric edges** (still record — threshold arithmetic, numeric
  evidence on every edge): ON, IN, ATTACHED/IN_WALL, INTERPENETRATES.
- **Open questions recorded as open:** duplicate-suspect pairs (computed
  from box geometry in build_edges.py, §0a.0) become **SAME_CANDIDATE
  edges** carrying IoU / containment / zone (confident|gray) / height
  difference.

NOT in the record (reversal of v1): downstream state — retrieval picks,
placement, cut status. Those are *consumers* of the graph, not evidence.

### 0a.2 CHECKPOINT — record review (user gate, BEFORE any VLM spend)

Eyeball nodes, geometric edges, the candidate queue, crops. Same
What/Why/Look-for discipline as every other gate.

### 0a.3 Pass 2 — the JUDGE (VLM via claude.exe, batched, cached)

Verdicts are new fields REFERENCING the record, never overwriting it.
Order matters:

1. **Same-vs-part** — visits ONLY the SAME_CANDIDATE queue; one cached call
   per edge (both nodes' crops + label multisets + the edge's geometric
   facts). Verdicts: SAME OBJECT → merge nodes (evidence of both retained,
   affected geometric edges re-derived) · PART OF → edge becomes PART_OF ·
   DISTINCT → edge dropped. This REPLACES semantic dedup entirely.
2. **Naming** — after merges, every node with a disputed multiset gets its
   canonical name from crops + cheap facts (height, size, ATTACHED edges).
   The lamp/ceiling-light fix.
3. **Appearance** — v1 describe_nodes machinery + cache carried over
   (§3a batching fixes apply).

Degradation (automated-pipeline rule): LLM unavailable ⇒ provisional names
stand, SAME_CANDIDATE stays unresolved — never a guessed merge.

### 0a.4 The contract

After the judge + the G-gate review, **the judged graph (record + verdicts)
replaces the manifest as the downstream contract** — the 2→3 package and C1
read `scene_graph.json`; the manifest becomes one more evidence input
behind it. Two canonical files would drift; there is one.

### 0a.5 Why this shape (recorded rationale)

- Record-first gives a review checkpoint before any LLM spend.
- The geometric edges recorded in pass 1 are exactly the cheap facts the
  judge was spec'd to use.
- A bad verdict is a one-pass cached rerun, not archaeology — provenance
  on every verdict ("merge: geometry IoU 0.75" / "name: VLM, cache key X").
- "Bridge the detection" (user's stated next step) and the record builder
  are the SAME piece of work.

### 0a.6 Build order

1. ~~`manifest_dedup.py` geometry-only rework~~ — built, then RETIRED by
   §0a.0 (no dedup stage; record reads f30 directly).
2. Record builder (`graph/build_graph.py` rework, f30 input) +
   `graph/build_edges.py` (+ SAME_CANDIDATE computed from geometry).
3. **CHECKPOINT R1 — record review (user).**
4. Judge passes: same-vs-part → naming → appearance.
5. **CHECKPOINT G2 — judged-graph review (user)**, then consumer wiring
   (package + C1 read the graph).

## 0. NEW DECISION 2026-07-26 (pm) — the graph inherits ALL semantic judgment

From the R9 dedup review (lamp+ceiling-light merged node surfaced as
"lamp" via highest-detector-score naming — rejected): the user chose
**"all semantics to graph"**. Concretely, when the graph is rebuilt on the
pano track it gains two passes:

- **Naming pass** — every node with multiple labels (`alt_labels` from the
  geometry-only dedup, or an appearance-pass label dispute) gets its
  canonical name picked by the VLM using the node's crops + cheap
  scene-agnostic geometric facts (height above floor, size, ON/ATTACHED
  edges). Batched, cached, degrades to detector-score order offline.
- **Same-vs-part pass** — consumes the `deferred_semantic` pair queue the
  reworked geometry-only dedup will emit (IoU .40–.60 + containment ≥ .90),
  judging with crops + IN/INTERPENETRATES edge evidence; merge nodes or
  keep as part-of edges.

Upstream contract change this implies: `manifest_dedup.py` goes
geometry-only (confident IoU ≥ 0.6 merges, labels all kept, primary label
provisional) — spec in PLAN_SELF_PANO_RIG.md's top UPDATE block. The
redefinition discussion this waited on is RESOLVED — §0a above is the
settled design; both passes described here land inside it (pass-2 judge).

## 1. Purpose (plain language)

Today the pipeline extracts five disconnected things from a splat scene
(manifest boxes, analyzer boxes, envelope, per-object Gaussians, per-view
masks) and downstream stages re-derive semantics ad hoc. This effort creates
ONE queryable representation: `out\<scene>\scene_graph.json` — nodes =
objects with all metadata + provenance, edges = typed relations. Downstream
(retrieval, placement, refinement loop) reads the graph instead of
re-deriving. Also a paper contribution: graph-structured scene semantics
aligns with the Graph2Plan lineage in the OVM paper strategy.

## 2. User decisions already made (2026-07-22 — do not re-litigate)

- **Node seed = analyzer boxes (103), not manifest, not union.** Manifest
  metadata (cut status, picks, amodal) attaches to nodes VIA the existing
  match_report mapping (e.g. ana_101 ← obj_004 lamp). NOTE: this front-runs
  part of the Checkpoint-4 adoption verdict; user accepts, R3 review will
  police hallucinated nodes; per-node confidence fields make weak nodes
  filterable.
- **Edges v1 = geometric only:** ON (support), ATTACHED/IN-WALL
  (architecture attachment), INTERPENETRATES (box overlap), IN
  (containment — "things might be inside other things, allow that").
  **Adjacency (NEXT-TO) deferred to a separate VLM step (v2)** — build the
  baseline graph geometrically first.
- **Appearance extraction included in v1**: VLM describes each node's crops
  → color / material / style / short description fields.
- Standing rules apply: no manual work (text-to-CAD), user judges visuals,
  numbered steps + descriptive names, review artifacts with What/Why/
  Look-for.

## 3. Flow

```
Step 1 — node-assembly ⟂ Step 2 — geometric-edges (after 1) → Step 3 — appearance-pass
   → Step 4 — graph-review build → CHECKPOINT G1 — graph correctness review (user)
   → (gated on G1) Step 5 — consumer wiring + VLM adjacency pass (v2)
```

### Step 1 — node-assembly (`graph/build_graph.py`)
- **In:** `analyzer\bridged_boxes.json` (103), `analyzer\match_report.json`,
  `scene_manifest.json` (metadata donor), `envelope.npz`, cut outputs
  (obj_004_v2), retrieval picks, collide export if present.
- **Out:** `out\<scene>\scene_graph.json` — nodes only, edges empty. Node
  schema: identity (id ana_XXX, label, canonical category, synonyms),
  geometry (box, position, size, yaw: null — honest gap), gaussians (fg PLY
  ref + count when cut), views (evidence frames, best crop refs, mask refs),
  provenance (detector, votes, peak score, standpoints, matched manifest id
  + distance), state (pick uid, placement, cut status), confidence tier
  (votes/score-derived: confirmed / candidate / weak). Architecture nodes:
  floor/ceiling/walls from envelope; window/door/curtain/AC typed
  `architecture`, movables typed `object`.
- Idempotent; schema documented in the module docstring (= the contract).

### Step 2 — geometric-edges (`graph/build_edges.py`)
- **In:** scene_graph.json (nodes) + envelope.
- **Out:** same file, edges filled: `ON` (bottom-face contact within
  tolerance, supported-by resolution to the topmost supporter), `IN`
  (containment: overlap fraction of the smaller box), `ATTACHED`/`IN_WALL`
  (architecture nodes near/inside wall planes), `INTERPENETRATES` (box
  overlap volume > threshold, value recorded). Every edge carries its
  numeric evidence (contact gap, overlap fraction) — auditable, not vibes.
- NEXT-TO deliberately absent (v2, VLM).

### Step 3 — appearance-pass (`graph/describe_nodes.py`)
- **In:** nodes + their best evidence crops (from analyzer job_high frames,
  box-projected, top-K by view area).
- **Out:** per-node `appearance` block: dominant colors, material guess,
  style words, one-sentence description. VLM route: claude.exe bridge
  (subscription, same pattern as the TreeSearchGen backend swap) — NO new
  API keys; batched; results cached per node (idempotent reruns skip
  described nodes).
- This is the genuinely NEW extraction of v1.

### Step 4 — graph-review build (`graph/graph_review.py`)
- **Out:** `out\<scene>\graph_review.html` — self-contained (vendored JS
  only, offline rule), interactive: node-link view grouped by type/tier,
  click node → metadata card + its crops; edge list with numeric evidence;
  plus a 3D tie-in layer in the placement viewer (click node ↔ highlight
  box) via additive serve.py route.
- **CHECKPOINT G1 — graph correctness review (user):** What = the review
  page + viewer layer; Why = the graph becomes the substrate every stage
  reads — wrong edges poison placement, hallucinated nodes poison
  retrieval; Look for = spot-check ON edges (is everything really on what
  the graph says), IN edges plausibility, architecture typing, appearance
  descriptions vs crops, and the weak-tier node list (real vs hallucinated).

### Step 5 — consumer wiring + adjacency (v2, gated on G1)
Retrieval reads node appearance; placement reads ON/ATTACHED constraints;
VLM adjacency pass adds NEXT-TO; batch-cut integration links every cut
object's Gaussians into its node.

## 3a. Deferred optimization — appearance-pass runtime (documented 2026-07-22, USER DECISION: fix later)

Measured on bedroom_marble: 16 claude.exe calls + 1 retry for 103 nodes ≈
25–30 min (~100 s/invocation). Time budget per invocation: ~70–80% = the
CLI agentic image-read loop (`claude -p` Reads each of the 6–8 crops as a
SEPARATE sequential model turn → one batch call ≈ 9 round trips), ~10–15% =
claude.exe cold boot per call, remainder = inference. Model thinking is NOT
the bottleneck; loop structure is.

Planned fixes (apply before the next multi-scene run; results are cached so
bedroom_marble never re-pays):
1. **Contact-sheet batching**: composite each batch's crops into one
   numbered grid image → 1 Read per call (~3x).
2. **Concurrent batches**: 3–4 claude.exe processes in parallel (~3x,
   stacks with fix 1 → est. 2–4 min/scene).
3. Optional scope cut: describe confirmed+candidate tiers only (weak tier
   is mostly duplicate clusters).
4. Rejected for now: direct API route (1 round trip/batch, fastest) —
   violates the subscription-bridge billing choice.

## 4. Progress log

| # | Step | Status | Artifacts / notes | Updated |
|---|---|---|---|---|
| 1 | node-assembly | **DONE** | `scene_graph.json`: 109 nodes (103 analyzer + 6 envelope arch); tiers confirmed 25 / candidate 70 / weak 14 (weak = votes<8); enrichment: 19 manifest, 19 picks, 19 poses, 1 gaussian-cut (ana_101=lamp). Inconsistencies logged (match accounting 19+17+67; loop-adds add_000/001 have no node; collisions.json is render-frame — noted, not used; ana_060/061 window centers outside envelope) | 2026-07-22 |
| 2 | geometric-edges | **DONE** | 320 edges: ON 35, IN 108 (books-in-shelves works: 21), IN_WALL 12, ATTACHED 7, INTERPENETRATES 158 (duplicate clusters self-expose; all z_fabricated-flagged). Frame self-check PASS (rug/bed ON floor, 0 ceiling edges). Documented threshold deviation: floor band ±0.15 m + straddle (spec 3–8 cm false-floated confirmed floor-standers); object-ON band asymmetric [−0.15,+0.08]. Floating: 20 flagged honestly (7 wall art; wall-mounted shelf ana_054; dup clusters) | 2026-07-22 |
| 3 | appearance-pass | **DONE** | 102/103 detection nodes described (fail = ana_062 rug, weak tier: malformed twice → appearance null + vlm_failed, honest); coverage confirmed 19/19, candidate 70/70, weak 13/14; 11 label_disputes (label_agreement:false — dup-cluster beds ana_076/077/079, blur ana_012/093, misreads ana_039 painting→curtain, ana_083 pillow→throw blanket); appearance_meta + cache (16 calls + 1 retry, sonnet via claude.exe, API-key gotcha WAS live → stripped from child env); 309 crops; crop selection deviation documented in describe_nodes.py docstring (score ≥ 0.5×peak filter before top-K-by-area — pure area picked junk boxes, caught by smoke test); runtime → §3a (USER: fix later, results cached). Sample: ana_101 = "Thin copper-toned metal desk lamp arm angled up against a white curtained window" (is_label true) | 2026-07-22 |
| 4 | graph-review build | **DONE** | `graph/graph_review.py` → `out\bedroom_marble\graph_review.html` (430 KB self-contained: G1 banner, stats, XZ minimap w/ per-type edge overlays, 109 node cards w/ 309 crops, 5 sortable edge tables (320 edges), sanity panel; rerun byte-identical). Viewer (additive, user scope-extension "whole graph visible"): serve.py `/scene_graph.json` + `/graph_crops/<file>` routes; index.html "graph nodes" layer = tier-colored boxes (per-tier toggles ✓25/70/14) + per-type edge lines (dim = z_fabricated) + click card (appearance + crops + edges) + dispute/undescribed/floating markers. curl-verified on :8329 (routes 200, traversal 404, old routes intact) | 2026-07-22 |
| G1 | graph correctness review | **MOOT** (07-26) | superseded by the record-then-judge rebuild (§0a); v1 machinery/lessons retained | 2026-07-26 |
| 5 | consumer wiring + adjacency (v2) | superseded | folded into §0a.6 step 5 | 2026-07-26 |
| R-0 | dedup geometry-only rework (§0a.6 step 1) | **SUPERSEDED same evening** | geometry-only rework was built and run (102 → 93), then the user amendment (§0a.0) RETIRED the dedup stage entirely — no pre-merges; `manifest_dedup.py` banner'd, `_dd`/`_dd_llm` files remain on disk unused | 2026-07-26 |
| R-1 | record builder (§0a.6 step 2) | **DONE (rebuilt per §0a.0)** | `graph/build_graph.py` = RECORD builder reading f30 directly (v1 archived: `scene_graph_v1.json`, `graph/crops_v1`): **108 nodes (102 det + 6 envelope)**, nothing pre-merged, full label multisets, evidence pointers + 465 referenced member crops from rig views, prompt.txt in lineage, amodal/yaw = null, downstream state OUT. `graph/build_edges.py`: label-blind IN_WALL/ATTACHED (curtain rule dropped), **SAME_CANDIDATE computed from geometry (14 = 10 confident + 4 gray)**, z_fabricated retired; edges ON 41 / IN 105 / IN_WALL 29 / ATTACHED 3 / INTERP 31; frame self-check PASS (bed+rug ON floor, nothing on ceiling) | 2026-07-26 |
| R-2 | record review artifact | **DONE** | viewer "graph record" layer (main HUD row; v1 toggle retired): nodes colored by open-question status (green single-label / amber naming / pink same-candidate), SAME_CANDIDATE lines on by default, click card = the RECORD card (label multiset w/ scores, dedup lineage + absorbed boxes, open questions, member crops, edge list) | 2026-07-26 |
| R-3 | room shell + no-floater invariant | **DONE** | measured wall/ceiling/floor planes in the record (PLAN_ROOM_SHELL.md, R11); USER RULE 07-26: "no standing floaters" — every detection node must hold ≥1 structural edge (ON/IN/IN_WALL/ATTACHED); the 3 isolated nodes get an explicit **NEAR** fallback edge (status unresolved, caveated, with deduped alternatives incl. the floor/support runners-up) — judge resolves; invariant enforced in the self-check (PASS) | 2026-07-26 |
| **R1** | **CHECKPOINT — record review (user)** | **🔴 WAITING ON USER** | REVIEW_LOG **R10** (+ R11 shell): viewer :8321 → "graph record"; also re-opens the dedup adoption verdict (R9) | 2026-07-26 |
| J | judge passes (§0a.6 step 4: same-vs-part → naming → appearance) | gated on R1 | — | |

## 5. Resume protocol

Same as the sibling plan: read this doc fully → verify claimed artifacts on
disk → continue from first non-done row → never skip an unpassed checkpoint
→ orchestrator + subagents, doc updated on every state change.
