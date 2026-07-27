# SESSION 2026-07-26D HANDOFF — the judge chain ran end-to-end

## ⭐ FINAL STATE (2026-07-27, session close) — GRAPH STAGE COMPLETE, HANDED OFF

- **bedroom_marble `scene_graph.json` SHIPPED, produced end-to-end by the
  drawn pipeline** (clean-method rerun, R14: record → J1∥J5 → J2 → J3 →
  J4 once → J6 once → ship; 5 calls). G2 PASSED by user handoff decision.
- **The settled design (§0a.8):** J1–J5 as specified · J4 once, flags =
  queue · J6 = TERMINAL (appearance + J4-flag resolution in one pass,
  judge_cases.py folded into describe_nodes.py) · unsettled ships to
  placement. NO loops anywhere.
- **Viewer :8321 — record and judged are TWO SEPARATE LAYERS** (user
  ruling 07-27, final form): "graph record" (stage-3 suffix scraped,
  record-pure — no verdicts) and a new **"judged graph" checkbox**: one
  box per merged cluster with its canonical name sprited above, state
  colors (blue shipping / green ✓ confirmed real / red ✗ not-real),
  arch slabs, judged edges incl. PART_OF with case verdicts inline,
  full judged click-card (members, verdicts, appearance, open flags as
  placement work orders, member crops), same-spot cycling. Both layers
  can be on at once to see 102 record boxes collapse into 92 clusters.
- **COMMITS (local, PUSH PENDING — blocked by permission gate, user
  runs `git push`):** `b6e63a8` (judge chain complete + docs + map) and
  `73ef33f` (judged layer separation).
- **USER RULES minted this session:** gates + review artifacts are
  dev-time only, never pipeline stages · pipeline_map.html is the
  AUTHORITY — deviations need warning + approval (memory
  pipeline-viewer-authority) · isolated LLM calls run in parallel ·
  effort follows downstream error cost (memory
  judge-loop-effort-allocation).
- **NEXT SESSION: the COMPOSE + LOOP stage** — rework C1–C7 against
  `graph["judged"]` (skip existence-rejected/disputed; retrieval shops
  with the appearance fields; placement consumes the work orders:
  obj_035/obj_096 deep boxes, obj_083, the 5 suspect boxes from edge
  reinterpretations). Read this block + PIPELINE.md "Scene-graph stages"
  + PLAN_SCENE_GRAPH.md §0a.8 first.

Read `docs/PLAN_SCENE_GRAPH.md` (state header + §0a.7 + progress log) and
`PIPELINE.md` ("Scene-graph stages" section, new) first. This session sat
on top of 07-26C (record built, R10/R11 gates open).

## What happened (user-directed, in order)

1. **R10 + R11 PASSED** ("all the graph nodes seems good"). The user
   diagnosed the 3 NEAR floaters from the viewer — recorded as GROUND
   TRUTH in REVIEW_LOG R10 (plant → floor w/ occluded base · monitor →
   desk via undetected arm · picture → wall).
2. **Judge sub-steps planned** (§0a.7): J0 truncation evidence → J1 pair
   judge ∥ J5 floater judge → J2 merge view → J3 naming → **J4 COHERENCE
   (new, user: "does it make sense", text-only)** → J6 appearance.
   USER RULINGS captured: gates are dev-time scaffolding only (zero gates
   in production — [[automated-pipeline-rule]] updated); floater-type
   problems are JUDGE work, not record heuristics.
3. **J0+J1+J5 built and run.** J1: 14/14 pairs (11 SAME — door↔window ×3
   all doors, mat 3-clique; 3 PART_OF; 0 DISTINCT). J5 v1: 2/3 — the
   plant miss traced to MY prompt gloss ("negative = box overlaps it").
4. **USER RULING → the fixed-schema rework:** "code interprets the
   numbers, the model interprets the pixels"; prompts = fixed versioned
   templates a deterministic script fills (pipeline must run unattended
   over hundreds of scenes). judge_near v2: deterministic menu classifier
   (plausible ≤0.25 m / floating / ruled-out ≥0.25 m-below), SAME-verdict
   menu dedupe, PROMPT_VERSION salted into BOTH judges' caches,
   `--selftest` zero-LLM regression. **v2 rerun: 3/3 ground truth.**
5. **R12 approved (all verdicts) → J2/J3/J4 built and run:**
   - J2 `build_judged.py` (zero LLM): 102 → 92 clusters; edge case found
     + fixed (mat triple's ON edges all internal after merge → post-merge
     support re-derivation with record thresholds; mat → ON floor,
     −0.017 m). Self-checks PASS.
   - J3 `judge_names.py`: 9/9 (office chair · door ×3 · CEILING LIGHT =
     the R9 fix · bookshelf ×2 · side table · yoga mat), 2 calls.
   - J4 `judge_coherence.py`: 259-line room digest, ONE call, 15 flags —
     caught the motivating obj_138 AND unnoticed twin obj_139
     (pictures-inside-doors) → 6 existence-disputed total (all ≤2 views);
     7 reexamine_with_crops = the escalation queue; 2 rename candidates.
6. **Escalation TEXT experiment** (user: "will the LLM guess the basket
   is under the chair?"): one text call with FULL coordinates resolved
   the user-verified case exactly, correct mechanism. Other 6 answers
   plausible, ungraded. Scratchpad script; promote if adopted.
7. **R13 user verdict: "good enough for me for now"** + DIRECTION: next
   effort = the **PLACEMENT stage — key the judged graph and let the LLM
   resolve flags AND affect boxes/placements** (escalation resolution
   lives THERE, not a graph v2).
8. **Formalization:** PIPELINE.md gained the "Scene-graph stages" contract
   table; pipeline_map.html reworked — 4g3 = JUDGED GRAPH node, plus a
   new right-hand judge lane with ALL SIX judges as individual nodes
   (J1/J5 → J2 → J3 → J4 → J6) with cards; canonical-Δ and analyzer-bridge
   edges rerouted to clear the lane; header prose updated (incl. the
   placement decision). JS validated (node parse + all card keys).
9. **Map polish round (user feedback "no user gates in the end; review
   pages are for us; 2.4 too crowded"):** the 2.4 band expanded by 280 px
   (everything below shifted programmatically; viewBox 1800 → 2080);
   judge lane respaced to a uniform 72 px pitch; main chain gaps 40–50 px.
   ALL "USER GATE" badges removed from drawn pipeline stages — the graph
   review page + splat viewer are now a dashed, labeled **DEV BENCH — for
   us while building · NOT pipeline stages** group hanging off the judged
   graph ("inspection only"); C4 review viewer + cut4 rebadged DEV BENCH /
   DEV CHECK; g2's gate line replaced with "self-check exits 1"; the
   downstream handoff edge now departs the JUDGED GRAPH directly (label:
   "skip disputed"). Validated: node --check on the inline JS, SVG parses
   as XML, zero empty marker-ends (a shift-regex bite that was caught and
   repaired).
10. **Map round 3 (user: "remove the dev review page + judging bench
   entirely; arrows only horizontal or downward"):** the graph review
   page (4g4) and splat viewer nodes are GONE from the map (cards
   removed too; the tools still exist on disk — they're just not drawn;
   a-bridge card notes its only reader was the undrawn dev viewer, hence
   no outgoing arrow). DATA-FLOW GEOMETRY RULE (add to the diagram
   rules): arrowheads only point right or down — 4g2 RECORD and J1 sit
   on the same row (horizontal feed), the judge lane descends at 72 px
   pitch, and 4g3 JUDGED GRAPH sits at the J6 row receiving the lane's
   output horizontally; the record flows straight down the middle column
   into it. Audited programmatically: zero upward arrowheads; remaining
   leftward finals = same-level handoffs, right-edge entry stubs, and
   the dashed compose loop-backs (inherently cyclic).
11. **Map round 4:** 2.3 LIFT opened up (+40 above P6, +60 below; P5→P6
   gap 12→52 px, P6→divider 3→63 px; viewBox 2180) and ALL rotated edge
   labels converted to horizontal (user: no sideways text) — labels now
   sit at the top of long vertical runs or beside arrow tips; the
   redundant "verdicts · additive · cached" label deleted (the 4g3 node
   says it). Diagram rules memory updated: arrows right/down only, no
   rotate(-90), ~40 px min node spacing, ≥60 px above dividers.

12. **The closure loop — run, then REVOKED (read §0a.8 first).** After J6,
   the user asked to resolve the coherence flags with crops. A
   coherence↔case-closing loop was built (`graph/judge_cases.py`) and
   iterated on bedroom_marble: 5 whole-room scans (flags 15→10→5→13→4),
   ~20+ calls. RESULTS STAND: 6 ghosts/dupes rejected, obj_138/139
   pictures + obj_083 box confirmed REAL, ~17 book-row/etc. renames, 11
   edge adjudications; obj_023 + 4 low-conf box flags ship open. USER
   STOPPED IT MID-FLIGHT and revoked the design ("too exhaustive at the
   wrong place"; "the loop is not the right place"): **J1–J5 unchanged,
   J4 once, J6 = appearance + J4-flag resolution in ONE terminal pass,
   ship the rest.** judge_cases.py banner'd as donor code — FOLD ITS
   QUEUES INTO describe_nodes.py before the next scene runs (the one
   real TODO this leaves). Memory: judge-loop-effort-allocation.md.
   PIPELINE.md + map (J4/J6 nodes+cards) resynced to the settled design.

## Where things stand

- `out/bedroom_marble/scene_graph.json`: record (untouched) + verdicts on
  edges + `graph["judged"]` (92 clusters, names, flags, disputed set).
  Caches: judge_pairs / judge_near / judge_names / judge_coherence .json.
- NOTE: judge_pairs' new PROMPT_VERSION salt invalidates its 14 old cache
  entries — next pairs run re-judges (~6 min); the graph holds the
  reviewed v1 verdicts.
- Uncommitted in scene-pipeline: all of today (judge modules, build_edges
  J0, docs, map). Commit as Timotsui.

## Next session

1. **PLACEMENT stage design** (user's declared next step): consume
   `graph["judged"]` (skip disputed), resolve the 7-flag escalation queue
   (text-first with full coordinates — experiment says it works — vision
   last), let the LLM affect boxes/placements. The old C1–C7 composition
   chain is the substrate to rework against the graph contract.
2. ~~J6 appearance rework~~ — DONE same session (round 5): v2 =
   judged-cluster input + CONTACT SHEETS (§3a landed: batch of 8 → one
   grid PNG per call, ×3 concurrent) + `--sheets-only` review-first mode
   (user approved the 11 sheets before spend). RUN: 86/86 described,
   11 calls, 0 failures. 3 label disagreements CROSS-CORROBORATE the
   other judges: obj_027 "picture"=books (coherence + text experiment
   agree), obj_062 "lamp"=white box (coherence rename flag), obj_075
   "basket"=book-like (new — coherence food next round). Still parked:
   viewer judged layer (merges/disputed in 3D).
3. Unjudged R13 items the user may still want to eyeball: the 6 disputed
   nodes and the 6 ungraded escalation answers.
