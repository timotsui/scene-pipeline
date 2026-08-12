# Session 2026-07-26E — J6 v2 evidence pack · J7 materialize · THE STAGE CONTRACT

⭐ **FINAL STATE (read this block first)**

The scene-graph stage is DONE and its handoff contract is SET (user
ruling this session): **`graph["resolved"]` in
`OUT/<scene>/scene_graph.json` is the canonical handoff — verdicts
materialized, box geometry VERBATIM from the judged layer, NO box
surgery.** Record + pre-edit judged are archived IN PLACE as immutable
audit layers (nothing moved on disk). The next session starts the
COMPOSE + LOOP stage against `graph["resolved"]`.

bedroom_marble resolved layer: **89 nodes** (3 removed: obj_091
not-real toy, obj_138/139 → part of door frame) · **157 edges** (4
judge-rewritten, 6 dropped) · 0 unresolved · work orders riding along:
suspect boxes obj_014 curtain / obj_109 chair / obj_023 shelf + the
open deep-box flags (obj_035/obj_096, obj_083).

## What happened this session

### 1. J6 v2 evidence pack (the obj_138 door-frame fix)
Diagnosis: the resolve judge saw only tight detector crops — a
truncated door-frame corner (box_2d cut at x=0, `truncated: true`) read
as "picture frame, REAL". The identity question is unanswerable at
crop zoom.

Fix (judge_cases.py PROMPT_VERSION 1→2 + describe_nodes.py phase A):
- every existence/rename case gets a zoomed-out **CONTEXT TILE** —
  source rig frame (lineage.crop_source), detection outlined in red,
  box + generous margin (`jc.context_tile`)
- a **"CUT OFF at the image edge"** fact line when members are
  truncated (`jc.trunc_note`)
- new existence verdict **PART_OF_STRUCTURE** → `existence:
  "structure"` (skipped by appearance, absorbed downstream; host
  recorded in the verdict)
- shared assembly `jc.build_exist_job()` so harnesses run the exact
  pipeline code path

Read-only retry (`graph/retry_cases_context.py`; sheet in
`OUT/bedroom_marble/graph/case_sheets_v2/`): obj_138 + obj_139 flipped
REAL picture frame → **PART_OF_STRUCTURE door frame**; obj_059 revived
as a small wall print; obj_091 stayed NOT_REAL. User: "these are
better" → applied via `--apply` (backup:
`graph/scene_graph_pre_ctxretry.json`).

### 2. J7 · materialize_verdicts.py → graph["resolved"]
User directive: "let the judge's comment affect the boxes." New stage
(drawn in pipeline_map.html as J7 + 4g4):
- removals: rejected / structure / disputed out of the shipping set
  (listed with provenance)
- REINTERPRET free-text → ONE batched cached call → closed vocab
  ON/IN/ATTACHED/NEAR/NONE. bedroom_marble: lamp~curtain +
  basket~chair IN→NEAR, stacked frames ON→NEAR, book PART_OF→ON,
  AC~bookshelf deleted (coincidental heights)
- honest degradation: LLM fail ⇒ `unresolved_reinterpret`, old type
  kept

### 3. Shrink experiment — built, TRACED, REVERTED (the big lesson)
Letter-menu design: code enumerates every valid single-face cut
(fully clears the partner, ≤75% loss) with floor-aware plain-language
descriptions; one batched call picks a letter or KEEP. Run: curtain
TRIM −40%, chair KEEP (leg space), shelf KEEP (support contact).

The user-led step-by-step trace then showed the curtain cut was
**wrong-axis**: the model called x "room-facing" but x was the
along-wall WIDTH; it was primed by the template's own curtain example;
the prompt carried no wall orientation; and the truly-correct z-depth
slim was inexpressible because the lamp's own box (which J4 had
already hypothesized was mis-sized) spans the curtain's whole depth.

**USER CONTRACT RULING: no shrink at the graph stage.** Trim reverted
(rebuild from cache, zero calls). Machinery kept behind `--shrink` as
placement-stage donor code. Lessons recorded (map J7 card) for that
future version: BAD_MENU verdict distinct from KEEP · partner-box cuts
on the same menu · shell wall-orientation in cut descriptions · no
pattern-matchable concrete examples in templates.

### 4. Canonicalization + cosmetics
- Viewer (:8321): main row = **"scene graph (canonical)"**, opens in
  RESOLVED view (untick for the judged audit view); "graph record
  (audit)" moved to the archive section; judged layer gained the
  structure state (purple) + judged→resolved edge counts; shrink UI
  auto-hides when no trims exist
- pipeline_map.html: J7 node + 4g4 "RESOLVED = CANONICAL · STAGE ENDS
  HERE" box, handoff rewired; compose section shifted 60 px down
  (overlap fix); **GaussianCut removed from the flow graph** (user:
  out of scope — decision on record in the Parked-ideas card; cut/
  code + outputs + WSL env stay on disk); flow now OPENS with a
  **"0 · TEXT PROMPT"** node → WORLD generate (user: the map should
  start where a scene starts)
- PIPELINE.md: J6 row updated, J7 row added, downstream-contract
  paragraph rewritten to the resolved-layer contract

## Batching / cost notes (user asked)
Judges are ONE batched call per queue type — not per-case parallel
agents (J6 runs its three queue types ×3 concurrent). Latency is
claude.exe session overhead (boot + tool-read of the contact sheet),
not iteration. J7 adds at most 2 batched calls per scene, both cached.

## Next session — COMPOSE + LOOP (the last part)
1. Wire the handoff: agent_package.py / C1 read `graph["resolved"]`
   (skip nothing — removals already applied) + rig crops (both rewires
   were already pending in the map).
2. Retrieval shops with the appearance fields on judged clusters
   (dereference by node id).
3. Placement consumes the work orders: suspect boxes + open flags —
   box surgery lives THERE, starting from the shrink experiment's
   lessons (`materialize_verdicts.py --shrink` is the donor code).

## File inventory (this session)
- `entangled_gen/graph/judge_cases.py` — v2 template + context/trunc
  helpers + build_exist_job (PROMPT_VERSION 2)
- `entangled_gen/graph/describe_nodes.py` — phase A wiring, structure
  write-back, phase-B skip
- `entangled_gen/graph/retry_cases_context.py` — NEW: read-only retry
  harness + `--apply`
- `entangled_gen/graph/materialize_verdicts.py` — NEW: J7 (shrink
  retired behind `--shrink`)
- `entangled_gen/viewer/index.html` — canonical/resolved/structure/
  trim UI
- `pipeline_map.html` — J7 + 4g4, contract text, layout shift, cut
  removal
- `entangled_gen/PIPELINE.md` — stage table + contract
- Data (not in repo): `OUT/bedroom_marble/scene_graph.json` (resolved
  layer), `graph/case_sheets_v2/`, `graph/resolve_cache.json`,
  `graph/scene_graph_pre_ctxretry.json` (backup)
