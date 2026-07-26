# SESSION 2026-07-26C HANDOFF — record built · shell measured · viewer reworked

Read `docs/PLAN_SCENE_GRAPH.md` (state + §0a + §0a.0) and
`docs/PLAN_ROOM_SHELL.md` first — they carry the full state. This was the
evening/late session on top of 07-26B (which ended at "what IS the scene
graph" as the open gate).

## What happened (all user-directed, in order)

1. **The graph-definition discussion RESOLVED**: record THEN judge
   (§0a) — pass 1 records deterministically and commits to nothing; pass
   2 (VLM, cached) writes verdicts that reference the record. The judged
   graph replaces the manifest as the downstream contract; downstream
   state (picks/placement) is OUT of the graph; windows/doors are
   ordinary nodes.
2. **Viewer cleanup** (user-directed, several rounds): current/archive
   registry grouping; pano funnel staged 1→2→3; fuse + gate-kills + both
   dedup layers + Δ-recenter layer REMOVED from the HUD (files stay);
   detect stages folded into their own collapsed section; "graph record
   (stage 3)" = the main layer.
3. **Pass 1 BUILT**, then **AMENDED same evening (§0a.0)**: user saw
   obj_057 absorbed into obj_007 and ruled "record both objects and
   indicate their relationship faithfully" → NO pre-merges at all, the
   dedup stage RETIRED (manifest_dedup.py banner'd; _dd/_dd_llm files
   unused). Record = f30 verbatim (102 det nodes); build_edges computes
   SAME_CANDIDATE pairs from geometry (14 = 10 confident zone IoU≥.6 +
   4 gray); MERGING IS A JUDGE VERDICT.
4. **Record card + click UX**: record card per node (multiset, crops,
   edges); smallest-first + same-spot cycling; edge palette disjoint
   from box palette; ALL edge types drawn faint (0.30), selection raises
   the node's edges to full and dims the rest to 0.12 (never hides).
5. **Room shell effort** (PLAN_ROOM_SHELL.md, W0→W3 in one session):
   W0 audit → placeholders off 0.02–0.4 m, splat↔collider agree on
   visible surfaces, room NOT a 4-plane box. User rulings: vertical-
   prism walls GO; collider cross-check IN; "clean and workable"; N-
   segment schema. W1 room_shell.py: 4 measured walls (collider Δ
   5–36 mm) + parallel surfaces (curtain plane etc.) + span-vs-observed
   extents (coverage 27–45% = occlusion metric). envelope.py REWIRED to
   the shell (legacy-manifest read = fallback; floor warp tightened to
   ±0.03 m). W2: shell → record arch nodes + IN_WALL on-wall footprints
   (32). W3: gray clickable slabs (faint persistent fill), arch sorts
   LAST in click-cycling.
6. **No-floater invariant** (user rule): every detection node ≥1
   structural edge; 3 isolated nodes got caveated NEAR fallback edges
   (status unresolved, deduped alternatives incl. floor/support
   runners-up); enforced in the self-check (PASS).
7. **Pipeline map** updated throughout: decision card (record-then-judge
   + amendment), P6 = score filter only, 4w room-shell node + rewired
   arrows, graph chain redrawn (record → R-gate → judge → gate), judge's
   three queues (SAME_CANDIDATE · naming · NEAR).

## Where things stand

- Record on bedroom_marble: 108 nodes (102 det + 6 measured arch),
  edges ON 41 · IN 105 · IN_WALL 32 · ATTACHED 3 · INTERP 31 ·
  SAME_CANDIDATE 14 · NEAR 3; self-checks PASS; 465 evidence crops;
  prompt.txt in lineage.
- Commits: 74205ce (record-then-judge) + dd3f845 (viewer) PUSHED; the
  shell + amendment + invariant wave committed at session close (see
  git log) — push pending unless already done.

## Resume protocol (next session)

1. **Gates open, user judges in the viewer** (:8321, "graph record"):
   REVIEW_LOG **R10** (record correctness: 14 pink pairs, crops, ON
   edges; re-opens the R9 dedup-adoption question as "pair quality") and
   **R11** (shell: gray slabs on collider walls, not curtain faces;
   IN_WALL neighbors sane).
2. After R10/R11 → **the judge passes** (PLAN_SCENE_GRAPH.md §0a.3):
   same-vs-part over the 14 SAME_CANDIDATE edges → merges as verdicts →
   naming over post-merge multisets → appearance (v1 machinery + §3a
   batching fixes) → NEAR resolution. claude.exe bridge, batched,
   cached, conservative degradation.
3. Then CHECKPOINT G2 (judged graph) → consumer wiring (agent package +
   C1 read scene_graph.json).
4. Parked nearby: openings as first-class nodes (coverage gaps ∩
   IN_WALL footprints); non-box shell fitter (schema ready); floor snap
   + room-envelope clamp (old post-processing queue).

## Untouched

Detection chain (P1–P5) untouched; composition C1–C7 untouched; no VLM
calls were made this session (the record is pure geometry).
