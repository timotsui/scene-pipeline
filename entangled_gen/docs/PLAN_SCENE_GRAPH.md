# PLAN — semantic scene graph (deliberate extraction from splat scenes)

Canonical plan + progress doc for this effort, per the production-session
workflow (see PLAN_GAUSSIAN_CUT_AND_SPLAT_ANALYZER.md for the sibling effort;
same rules govern: progress log updated on every state change, resume
protocol at bottom, checkpoints are hard stops unless autonomous mode is
explicitly authorized).

- Created: 2026-07-22
- Current state: 🔴 WAITING ON USER — Checkpoint G1 graph correctness
  review (`out\bedroom_marble\graph_review.html` + viewer "graph nodes"
  layer). Steps 1–4 all DONE; Step 5 (consumer wiring + VLM adjacency)
  gated on G1.
- Scene: bedroom_marble first (the fully-instrumented scene)

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
| G1 | graph correctness review | **🔴 WAITING ON USER** | open `graph_review.html` + launch_viewer.bat → :8321 → "graph nodes" | 2026-07-22 |
| 5 | consumer wiring + adjacency (v2) | gated on G1 | — | |

## 5. Resume protocol

Same as the sibling plan: read this doc fully → verify claimed artifacts on
disk → continue from first non-done row → never skip an unpassed checkpoint
→ orchestrator + subagents, doc updated on every state change.
