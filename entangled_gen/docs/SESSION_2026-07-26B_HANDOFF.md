# SESSION 2026-07-26B HANDOFF — R9 pass: dedup re-scoped, semantics → graph

Read `docs/PLAN_SELF_PANO_RIG.md` (top UPDATE block) and
`docs/PLAN_SCENE_GRAPH.md` (§0 + current-state line) first — they carry
the full state. This was the afternoon review session on top of the
morning's filter+dedup work (SESSION_2026-07-26_HANDOFF.md).

## What happened (all user-directed)

1. **R9 viewer pass started.** First finding: merged node `obj_007`
   "lamp" (alt_label "ceiling light"). Diagnosis (verified in code +
   data): the merge is RIGHT — obj_007+obj_057 overlap at IoU 0.75
   (lamp box 100% inside the ceiling-light box, both at ~2.7 m = ceiling
   height in the −y-up frame), confident-zone geometry, no LLM involved.
   The NAME is wrong: `merge_group()` picks primary label = highest
   detector score ("lamp" 0.622 beat "ceiling light" 0.4), and detector
   score measures box↔label confidence, not name quality — generic labels
   systematically outscore specific ones.
2. **USER: score-based naming rejected** ("i dont think that is a great
   idea"). Discussion → AskUserQuestion → **DECISION: "all semantics to
   graph"** — dedup keeps only confident pure-geometry merges; canonical
   naming AND the gray-zone same-vs-part judgment both become scene-graph
   passes (VLM with crops + cheap geometric facts; details in
   PLAN_SCENE_GRAPH.md §0).
3. **Rework PAUSED before implementation.** User: "first we need to talk
   about what is scene graph." The open framing question: is the graph a
   passive index over extraction outputs, or the stage where the pipeline
   COMMITS to object identity (names, merges, relations)? Also live: the
   graph's analyzer-seeded node set is deprecated by the pano track, so a
   rebuild is coming regardless; G1 review likely moot.
4. **Wrap-up executed** (this session's close): PLAN_SELF_PANO_RIG.md
   UPDATE block, REVIEW_LOG R9 verdict lines (adoption DEFERRED, naming
   bug recorded), PLAN_SCENE_GRAPH.md §0 + state, pipeline_map.html
   (P6 post-process node + decision card + graph-card notes), memory.
5. **Map cleanup (user-directed, same close):** analyzer side column
   demoted to REFERENCE-ONLY — steps kept and band-aligned with the
   canonical lane (correspondence stated on each card) but dimmed
   (opacity .5, full on hover/click), dashed, "reference only" lane
   title. Envelope→a-bridge arrow REMOVED (established: report-only
   frame-mismatch check, not a dependency — a-bridge card explains);
   a-bridge output labeled record-only; hybrid experiment moved from
   the middle into the side column; "LATER multiview vote" node removed
   from the flow (lives on the Parked-ideas card, SPEC_3H2_FUSE §7).
   Established fact: NOTHING in the pipeline consumes bridged_boxes.json
   except the cyan viewer layer + graph v1 (until rewire).

## Resume protocol (next session)

0. **User's stated direction at session close (2026-07-26, verbatim
   intent):** "the natural next step is to bridge the detection, and
   semantically dedup + scene graph." Reading: connect the pano-track
   detection output into the scene graph (our own detection→graph bridge,
   analogous to what a-bridge did for the analyzer), and do the semantic
   dedup (naming + same-vs-part) AS PART of the scene graph stage — i.e.
   start the graph rebuild on the pano track with the semantics passes.
   Confirm this reading with the user before building.
1. **The "what is the scene graph" discussion is still the gate.**
   The user wants to talk through what the graph IS (record-vs-judge, node
   identity, what seeds nodes) before/while starting the above.
2. After that discussion, the queued implementation (spec already agreed,
   in PLAN_SELF_PANO_RIG.md top block):
   - `manifest_dedup.py` → geometry-only (strip LLM path; emit
     `deferred_semantic`; `label_provisional: true`; docstring contract).
   - Rerun on bedroom_marble (~95 objects expected; door+window gray
     merges revert; lamp merge stays). R9 re-review against that.
   - Graph rebuild on the pano track + naming / same-vs-part passes per
     PLAN_SCENE_GRAPH.md §0.
3. Still open besides that: R8 canonical-layer verdict; floor snap +
   room-envelope clamp (post-processing queue); the parked ideas board on
   pipeline_map.html.

## Untouched this session

No pipeline code was edited (user rule: plan first — the dedup rework spec
is written but NOT implemented). Manifests on disk unchanged:
`scene_manifest_pano2c_rc.json` (108) → `_f30` (102, ADOPTED) →
`_f30_dd` (92, review deferred). `dedup_llm_cache.json` still present —
retires with the rework.
