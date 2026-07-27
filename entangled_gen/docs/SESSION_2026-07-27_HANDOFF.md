# Session 2026-07-27 (overnight, autonomous) — semantic sub-stage built end-to-end · PH1 v0 · context crops

⭐ **FINAL STATE (read this block first)**

The COMPOSE+LOOP semantic sub-stage went from one module to a working
chain tonight: **supported_by (S1) → consistency (S2) both BUILT + RUN**
on bedroom_marble, the viewer's canonical scene-graph row now IS the
supported_by graph, the appearance pass was re-grounded on **context
crops** (the obj_001 root-cause fix), **PH1 snap analyzer v0** ran and
independently re-derived the suspect-box list from pure geometry, and an
**isolated propose_edits module** awaits its first full run. Everything
is proposals-only; the graph and its boxes remain verbatim.
**`PLAN_COMPOSE_LOOP.md` is the canonical doc** (progress table + REVIEW_LOG
R1–R4). Map redrawn to match (user pre-approved).

## Open gates for the user (in review order)

1. **R1 · supported_by verdicts** — viewer :8321 (server running, hard-refresh).
   31 anchors vs 44 crude, 13 demotions, 5 multi-option (doors ×2,
   pictures ×2, book). v5 = prompt with most-plausible framing +
   directional metrics + descriptions-as-testimony.
2. **R2 · consistency verdicts** — `compose/consistency.json`: 11 DROP +
   17 KEEP proposals; obj_080 repeatedly fingered as an OVERSIZED box
   swallowing books (duplicate-shelf suspicion, 2nd independent angle).
3. **R3 · obj_001 plant** — open `graph/crops_ctx/obj_001_m*.png`: even the
   context crops describe "resting on a wooden shelf" (0.55). Your eyes
   rule: shelf (→ crude ON-floor edge + box wrong) or floor (→ description
   wrong, box truncated).
4. **R4 · PH1 snap flags** — 7 LARGE corrections = exactly the known
   suspect boxes (plant 0.94 m, picture obj_096 0.32, curtain 0.25,
   monitor 0.22, bookshelves 0.21/0.15, obj_013 0.10). Zero false alarms.
5. **propose_edits first full run** — `python compose/propose_edits.py
   --scene bedroom_marble` (module is isolated; tonight only `--no-llm`
   sanity ran, and against the PRE-v5 layer — the delete-candidate pool
   shifts with v5 since obj_083 is no longer none_plausible).

## Built tonight (chronological)

1. `compose/supported_by.py` — v3→v5 across the night: always-offer-floor
   (bookshelf lesson), directional overlap metrics (footprint %, edge
   slivers, side-by-side vs stacked — obj_001 lesson), beneath window
   0.12→0.30 m (`--beneath-tol`; occlusion), most-plausible framing,
   descriptions = pixel testimony weighed WITH numbers. v2 (bundled
   nonsense job) RETRACTED same session — template isn't hashed, never
   reuse a version number.
2. `compose/consistency.py` — first consumer of supported_by; USER RULING:
   edges NOT fully superseded (containment/attachment/adjacency =
   arrangement facts); code explains ~85% of edges, one batched LLM call
   for leftovers; all proposals.
3. Viewer :8321 — "supported_by graph (canonical)" main row; anchor tint
   from top option; green support arrows dim-at-rest, anchor-focus
   highlights ONLY anchor→shell; contact edges → archive toggle; click
   card shows options + reasons; `/supported_by.json` route (serve.py).
4. `graph/describe_nodes.py` v3 — CONTEXT CROPS (`graph/crops_ctx/`,
   pad 35/35/**75-below**, red outline; `--appearance-only`, `--no-ctx`).
   Appearance re-described 89/89. obj_083's description flipped from
   "greenery through window" to "backlit plant silhouette" → its verdict
   became rests_on floor 0.55 (occlusion-truncation reasoning, 93.6 cm).
   obj_030 self-resolved to "group of books". obj_001 unchanged (R3).
5. `compose/propose_edits.py` — ISOLATED add/delete proposer (user:
   test/review tomorrow). Deterministic doubt aggregation + LLM
   confirm/deny (deletes) + conservative room-inventory adds with
   DECLARED support. Sanity: 3 candidates (obj_080, obj_083, obj_093).
6. `compose/snap.py` — PH1 v0 ANALYZER (user architecture: semantic loop ·
   deterministic physical · physics feeds BACK = loop in loop). Also USER
   RULING: collision = PER SELECTED MODEL (mesh), never boxes → PH2 waits
   for shopping.
7. `docs/S4_SHOPPING_DESIGN_NOTES.md` — subagent-mined reference: old-chain
   contracts, worked/failed record, reuse verdicts (fit() + pick-policy =
   crown jewels; _mount/MIN_CONF/bridge = drop), 17 open questions.
8. Map: 3.1 lane = S1 supported_by → S2 consistency → S3 screening (LATER)
   → S4 shopping (LATER); propose-edits node + PH1 v0 + loop-in-loop
   feedback arrow all drawn; cards updated; JS syntax-checked.

## Numbers (bedroom_marble, final tonight)

- supported_by v5: 89/89 resolved · 31 anchors (crude 44) · 13 demoted ·
  0 added · 5 multi-option · 0 none_plausible
- consistency on v5: 84 CONFIRMED_SUPPORT · 4 SUPPORT_ALT · 10 TRANSITIVE ·
  26 KEPT_GEOMETRIC · 2 KEPT_STRUCTURAL · 3 KEPT_ARRANGEMENT · 17 KEEP ·
  11 DROP · 0 audit flags
- snap v0: 16 floor / 13 wall-flush / 2 ceiling / 12 on-object /
  13 internal-surface / 32 inside-container / 1 embedded · 7 LARGE flags

## Next session (after the gates)

- Rule on R1–R4 + run/review propose_edits (its output feeds the same
  cleaning conversation as the snap flags).
- Then the cleaning step design: box surgery work orders (snap deltas =
  the quantified queue), duplicate resolution (obj_080/obj_093), identity
  holdouts (obj_001).
- Screening (S3) unparks after cleaning; S4 design starts from
  `S4_SHOPPING_DESIGN_NOTES.md` open questions.

## File inventory (this session)

- NEW: `compose/supported_by.py` · `compose/consistency.py` ·
  `compose/snap.py` · `compose/propose_edits.py` ·
  `docs/PLAN_COMPOSE_LOOP.md` · `docs/S4_SHOPPING_DESIGN_NOTES.md` · this
  handoff
- MODIFIED: `paths.py` (compose_dir) · `viewer/serve.py` ·
  `viewer/index.html` · `graph/describe_nodes.py` (v3 context crops) ·
  `../pipeline_map.html`
- Data (out/bedroom_marble/compose/): supported_by.json (+cache) ·
  consistency.json (+cache) · snap.json · edit_proposals.json (STALE:
  pre-v5 sanity output) · graph/crops_ctx/ (89×2 context crops)
- Commits: 423aebb (mid-session) + the end-of-session commit.
