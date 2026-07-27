# PLAN — COMPOSE + LOOP stage (STEP 3)

**Started:** 2026-07-26 (session G) · **Status: PLANNING — support-attribution design awaiting user go-ahead**
**Authority:** `pipeline_map.html` STEP 3 section (drawn 07-26F) — **now stale at the top
of 3.1: the map's "S1 anchor set (viewer filter) → S2 screening" opening needs a redraw**
(see below). Map edits are user-gated; redraw proposed, not done.
**Method (user 07-26G): prove step by step.** Only the CURRENT step is designed here.
Later modules exist only as direction; each is designed after the previous step passes
its user gate. No module runs before its design row is user-approved.
**Resume protocol:** read this file top to bottom, then the newest `SESSION_2026-07-26*`
handoff.

## Overall direction (updated 07-26G with the user)

The semantic sub-stage FIRST produces a **clean, semantically viable scene graph**,
then decides what to shop for. Discussion rulings (user, this session):

- The touch-based anchor rule is **crude**: false anchors (obj_061 book grazing the
  wall from a shelf = geometric fluke) AND misses (obj_013 picture on a shelf).
  "Anchor" must stop being a stored classification.
- Core reframe: per object ask **"what is actually holding this up?"** —
  **support attribution**. The module CONVERTS geometric contact edges
  (ON / IN / IN_WALL / ATTACHED) into ranked **`SUPPORTED_BY` options** (support
  stories). Contacts are demoted to evidence, never deleted.
- **Stories are plural** where evidence is ambiguous (obj_013: rests-on-shelf vs
  mounted-on-wall — a leaning picture legitimately has TWO supporters). Ambiguity is
  a legitimate output; it stays in the graph until something downstream forces a
  choice or the user rules.
- Objects with NO plausible support story = strongest flag that the box is broken or
  the object isn't real → feeds box cleaning / existence disputes.
- Sequence after this step (direction only, not designed): box cleaning + identity
  resolution on what the stories flag → screening (compose-or-skip) → shopping →
  physical sub-stage → judge. Screening's earlier draft design is parked at the
  bottom of this doc.

## Layout decisions (standing)

| what | decision | note |
|---|---|---|
| code home | `entangled_gen/compose/` (new folder, sibling of `graph/`) | old `composition/` stays untouched donor |
| per-scene output | `out/<scene>/compose/` via new `paths.compose_dir()` | first file: `support_stories.json` |
| LLM channel | `claude.exe -p --model sonnet`, same pattern as `graph/judge_names.py` (`call_claude` + evidence-hash cache) | model swappable by flag (automated-pipeline rule) |

## CURRENT STEP · SUPPORTED_BY (design settled with user 07-26G, awaiting go)

**Module:** `compose/supported_by.py` — candidate relations in, one superseding
`supported_by` field out. **User's formulation:** per object, list the existing
ON / IN / IN_WALL / ATTACHED / NEAR edges plus computed "contact"/"near" candidates;
the LLM reasons whether each even makes sense and returns THE `supported_by` field,
which SUPERSEDES those relational edges. Multiple entries allowed when several
options are semantically viable; one is fine too.

1. **Candidate listing — deterministic code, no LLM.** Per object (all 89):
   - existing resolved edges touching it (ON / IN / IN_WALL / ATTACHED / NEAR);
   - *gravity candidate:* whatever lies directly beneath the bottom face (floor or
     another object's top) within tolerance;
   - *near scan:* walls/objects within a tolerance wider than touch (box error >
     contact tolerance — the obj_013 lesson), so crude-miss cases get candidates too.
   **Every candidate carries its metrics (user):** near → distance (m); contact /
   overlap → gap or penetration depth, overlap volume %, contact area and which face;
   gravity → vertical clearance beneath the bottom face. Computed from the boxes +
   shell planes in code — the LLM interprets numbers it is given, never invents them.
2. **ONE batched LLM call.** Input per object: name + size + candidate list as plain
   sentences WITH metrics ("book obj_061: ON shelf obj_023 (bottom face rests on top,
   gap 0.4 cm, 78 % of base supported); IN_WALL arch_wall_z_low (graze, penetration
   0.2 cm, contact on thin back face)").
   Output per object: `supported_by: [ {supporter, how (rests_on / mounted_on /
   leans_on / hangs_from / embedded_in), confidence, reason} ]` — 1..n options,
   ambiguity legitimate; explicit `none_plausible` allowed (→ box/existence flag).
   TEXT-ONLY v1 (no crops): the candidate relations + names carry the signal; crops
   are the held-back upgrade lever if the review sheet shows guessing.
3. **Conservative degrade:** LLM unavailable → candidates written with
   `supported_by: null`, every object `NEEDS_REVIEW`, nothing auto-resolved.
4. **Output `out/<scene>/compose/supported_by.json`** — a layer BESIDE the graph
   (resolved layer + boxes untouched; superseded edges remain as evidence). Cached
   per object by evidence hash. `anchor` becomes a derived reading: an option's
   supporter is an `arch_*` node → anchor under that option.
5. **Viewer (user ask): show it in the scene graph.** Scene-graph row of :8321 learns
   the supported_by layer when the file exists: support arrows object → supporter
   (styled apart from raw edges), multi-option objects visually marked, anchor-focus
   tinting re-derived from top supported_by option instead of the crude touch rule.
   Raw edges remain drawable (they're evidence, and the old view must stay
   comparable — this IS the delta review).
6. **Crude-match check first:** before diverging, reproduce the viewer's crude count
   in code (44 = 16/26/2) to prove we read the same edges the viewer does.

**Scope cuts:** no graph rewrite, no box edits (later step), no crops in v1, no
separate review sheet — THE VIEWER is the review gate (user judges visuals there).

**Map impact (user-gated, proposed):** 3.1 opening becomes
"S1 SUPPORT ATTRIBUTION (contacts → SUPPORTED_BY stories) → S2 clean/box+identity →
S3 screening → S4 shopping"; the viewer anchor filter card becomes a reference/preview
of the crude rule. Redraw only after the user approves this design.

## CURRENT STEP 2 · CONSISTENCY (designed 07-26G, user: "self consistency pass")

**Module:** `compose/consistency.py` — DOWNSTREAM of supported_by (its first
consumer). Reads `scene_graph.json` resolved + `compose/supported_by.json`;
writes `compose/consistency.json`. Nothing removed — verdicts are proposals.

1. **Part A — supported_by self-audit (pure code):** support cycles via
   top-option chains; supporter flagged none_plausible (dependents inherit
   doubt); supporter NEEDS_REVIEW/missing.
2. **Part B — every resolved edge classified (code first):**
   - matches an endpoint's supported_by option → `CONFIRMED_SUPPORT` (top) /
     `SUPPORT_ALT` (alternate — evidence for a live option)
   - target is in the object's support CHAIN (book IN shelf inside bookshelf)
     → `TRANSITIVE`
   - `NEAR` → `KEPT_ARRANGEMENT` · `INTERPENETRATES` → `KEPT_GEOMETRIC`
     (box-surgery food) · `PART_OF` → `KEPT_STRUCTURAL`
   - leftover support-type edges nobody's verdict explains → **one batched
     LLM call**: `KEEP` (real arrangement fact: containment/attachment/flush)
     vs `DROP` (artifact: graze, in-two-shelves loser) + reason; conservative
     degrade → `NEEDS_REVIEW`.
3. Cache per edge (evidence hash). Output: audit flags + per-edge verdicts +
   drop-proposal list + counts. Review: console summary + JSON first; viewer
   marking only if the result earns it (effort rule).

## STEP · CONTEXT CROPS (07-27, user: "make the crops more correct")

Root cause of the obj_001 wrong description: `build_graph.py` cuts crops at
CROP_PAD 0.10 — a tight box that excludes what the object stands on, so the
appearance VLM invented support ("sitting on a shelf"). Fix in
`graph/describe_nodes.py` (appearance v3): **context crops** in
`graph/crops_ctx/` — source view padded 35% sides/top and **75% below**
(support lives there), object outlined in red (the `judge_cases.context_tile`
pattern + its obj_138 lesson). New flags: `--appearance-only` (skip phase A
flag resolution) and `--no-ctx` (old behavior). Tight evidence crops are
untouched — the settled naming/pairs judges keep their caches.

## ISOLATED MODULE · PROPOSE EDITS (07-27, built for tomorrow's review)

`compose/propose_edits.py` → `compose/edit_proposals.json`. **Nothing
consumes it** (map: dashed arrows; intended landing = the JUDGE loop's
add/delete channel). DELETE candidates aggregated deterministically from
every existing doubt signal (none_plausible, consistency duplicate DROPs,
all-support-edges-dropped + weak confidence, unresolved existence disputes)
then one batched LLM confirm/deny; ADD proposals from one batched LLM call
over the room inventory + dimensions, conservative (0–6), **every add
declares its support** (floor / wall / ceiling / on:<id>) per the stage rule.
Degrade: `--no-llm` → candidates unconfirmed, adds empty. TOMORROW: full run
+ user review of both lists.

## PH1 v0 · SNAP ANALYZER (07-27, built + run)

**User architecture direction (07-27, recorded):** the semantic stage is a
LOOP; the physical stage is DETERMINISTIC; physical results feed BACK into
the semantic loop — **a loop within a loop**. And: **collision is checked
PER SELECTED MODEL (mesh), never box-vs-box** — so PH2 waits for shopping.

`compose/snap.py` → `compose/snap.json`, zero LLM, runs on the graph's own
boxes as proxy geometry (no cast list needed). Per object: the correction
making its TOP supported_by option physically exact — floor/ceiling contact,
wall flush (horizontal only; mounting height = observed truth), parent-top
contact with supporters snapped BEFORE dependents (chain-depth ordering).
`INTERNAL_SURFACE` rule: a bottom deep inside the supporter's span (books on
bookshelf boards) is NOT snapped to the supporter's top — interior boards
aren't in the box model, the observed height IS the shelf.

**bedroom_marble v0 result:** dispositions 16 floor / 13 wall-flush /
2 ceiling / 12 on-object / 13 internal-surface / 32 inside-container /
1 embedded. **7 LARGE corrections (>10 cm) = exactly the known suspect
family, zero false alarms:** obj_083 plant 0.94 m (occlusion-truncated box,
matches the v5 verdict's own reasoning) · obj_096 picture 0.32 · obj_014
curtain 0.25 · obj_005 monitor 0.22 (stand neck) · obj_088 bookshelf 0.21 ·
obj_043 bookshelf 0.15 · obj_013 picture 0.10. The physics pass
independently re-derived the suspect-box work-order list from geometry +
verdicts alone — the loop-in-loop feedback channel demonstrated on real
data. Map: dashed return arrow PH1 → S1.

## Progress

| # | item | status | ruled by |
|---|---|---|---|
| 0 | this plan doc | REWRITTEN 07-26G: support attribution = current step | — |
| 1 | support-attribution design (above) | **APPROVED 07-26G** (deterministic-first + metrics→LLM confirmed) | user |
| 2 | map redraw of 3.1 opening | proposed, user-gated | user |
| 3 | `paths.compose_dir()` + `compose/` folder | DONE 07-26G | — |
| 4 | `compose/supported_by.py` build (code pass + crude-match check first) | DONE 07-26G — crude port matches viewer exactly (44 = 16/26/2) | — |
| 5 | LLM pass on bedroom_marble + viewer integration (:8321 scene-graph row) | DONE 07-26G — 89/89 resolved, see R1 | — |
| 5b | viewer promotion (user 07-26G): main row = "supported_by graph (canonical)", raw contact edges → archive toggle "graph contact edges (superseded)"; per-node evidence edges still drawn on click + arrows dim-at-rest / anchor-focus highlights only anchor→shell arrows | DONE 07-26G | user |
| 5c | bundled "nonsense relations" second job (prompt v2) | **RETRACTED same session (user)** — edge cleaning is DOWNSTREAM: needs the resolved supported_by of BOTH endpoints (cross-object coherence, e.g. book-in-two-shelves) and much of it becomes near-deterministic once verdicts exist; module stays single-question. Prompt jumped v1→v3 (v2 = the retracted bundle; template isn't hashed, so reusing "2" could silently serve aborted-v2 cache). [cN] candidate numbering kept in the layer for downstream reference | user |
| 6 | USER GATE: supported_by rulings in the viewer (R1, v3 numbers) | **OPEN — awaiting user** | user |
| 6b | `compose/consistency.py` design + build + run (STEP 2, downstream of supported_by) | DONE 07-26G — 157 edges: 132 explained by code, 25 LLM leftovers → 8 KEEP / 17 DROP proposals; 0 audit flags; see R2 | — |
| 6c | USER GATE: consistency verdicts (R2 — 17 drop proposals + 8 keeps) | **OPEN — awaiting user** | user |
| 6d | tuning: `BENEATH_TOL` 0.12→0.30 (+`--beneath-tol` flag; user: occluded detections truncate boxes past 12 cm) | DONE 07-26G — 33 objects re-judged; anchors/demotions UNCHANGED; 29 top-option shifts: mass rests_on→inside for bookshelf contents, some supporters coarsened (shelf board→whole bookshelf), wall-mount confidences dropped (AC 0.8→0.6, pictures →0.5/0.45); trade-off on record: wider window = occlusion-robust but more distractor candidates. consistency.json now STALE (built on tol-0.12 layer) | user |
| 6e | prompt v5 (most-plausible framing + directional metrics: footprint %, edge slivers, side-by-side vs stacked) — the obj_001 lesson chain | DONE 07-26G/27 | — |
| 6f | CONTEXT CROPS: describe_nodes v3 (`crops_ctx/`, pad 35/35/75 + red outline, `--appearance-only`) + appearance re-run 89/89 | DONE 07-27 — obj_001 description STILL says "resting on a wooden shelf" under context crops → now honest pixel testimony, not a cropping artifact; gate evidence = `graph/crops_ctx/obj_001_m*.png` (user judges) | user |
| 6g | supported_by v5 re-run on refreshed (context-crop) descriptions | DONE 07-27 — 89/89; **31 anchors** (kept 31 / demoted 13 / added 0); multi-option 22→**5** (only the genuinely contested: doors ×2, pictures ×2, book); none_plausible → **0**: obj_083 FLIPPED to rests_on floor 0.55 (new description: "leafy plant as green silhouette against bright window, washed out by backlight" — context crop sees a real plant; verdict applies occlusion-truncation reasoning to the 93.6 cm gap); obj_030 identity self-resolved ("group of books… on a wooden shelf" — the yoga-mat text was reason-bleed); obj_001 shelf story persists at 0.55 (user's crops_ctx ruling pending, R3) | user |
| 6g2 | consistency re-run on the v5 layer | DONE 07-27 — 157 edges: 84 CONFIRMED / 4 ALT / 10 TRANSITIVE / 31 kept facts / **17 KEEP + 11 DROP** (LLM), 0 audit flags. Drop list sharpened: obj_080 repeatedly fingered as an OVERSIZED box swallowing books at wildly different heights (the duplicate-shelf suspicion, second independent angle); obj_095 caught claiming IN_WALL with an 8.4 cm gap FROM the wall | user |
| 6h2 | PH1 `compose/snap.py` v0 built + run (see PH1 section + R4) | DONE 07-27 — 7 LARGE corrections = the known suspect family exactly, zero false alarms | user |
| 6h3 | S4 shopping design notes mined from old C1–C5 (subagent research) | DONE 07-27 → `docs/S4_SHOPPING_DESIGN_NOTES.md` (module contracts, worked/failed record, reuse verdicts, 17 open questions) | — |
| 6h | `compose/propose_edits.py` — ISOLATED add/delete proposer + map placement (dashed, unwired) | BUILT 07-27, `--no-llm` sanity only; **FULL RUN + REVIEW = TOMORROW** | user |
| 6i | pipeline map redrawn: 3.1 = S1 supported_by → S2 consistency → S3 screening → S4 shopping; cards updated; propose-edits node dashed; J6 card v3 note | DONE 07-27 (user pre-approved "update the pipeline viewer") | — |
| 7 | next step chosen + designed AFTER gate 6 — direction (user rulings 07-26G, superseding each other in order): (a) edge cleaning is downstream of supported_by [5c]; (b) briefly scoped down to "no edge pass at all — supersede + archive"; (c) FINAL: **supported_by does NOT fully supersede the edges** — containment (book IN bookshelf) / attachment / adjacency (table flush with table) are ARRANGEMENT facts composition will consume. Next step = **edge–support consistency module**: each contact edge checked against BOTH endpoints' resolved supported_by + sibling edges → confirmed (support's own evidence) / kept arrangement fact / impossible (drop-proposal: in-two-shelves, in-wall-while-on-shelf); deterministic core, LLM for leftovers, verdicts as proposals. Plus supported_by self-audit (cycles, flagged supporters) + box/identity cleaning (obj_030, obj_083, deep pictures). Viewer stance: click-card edges stay (meaningful relations); only the global spaghetti is archived | user |

## REVIEW_LOG

Format per production workflow: What / Why / Look for → provisional verdict → user verdict.

### R1 · supported_by v1 on bedroom_marble (07-26G) — GATE OPEN

**What:** `compose/supported_by.py` full run (sonnet, prompt v1, 3 batches, 89/89
resolved, ~4.8 candidate lines/object) + the :8321 scene-graph row now shows the
layer: anchor tint follows the TOP supported_by option; green arrows = options
(bright top, faint alternates); click card lists options with reasons; the
supported_by header segment shows the delta vs crude.

**Why:** replace the crude touch-anchor rule with semantic support attribution
(user design: deterministic metrics in, one superseding supported_by field out).

**Numbers (v3 final run):** anchors 30 vs crude 44 — **15 demoted** (obj_001
plant, obj_009 basket, obj_010 desk lamp, obj_011 basket, obj_023 shelf,
obj_038/047/060/061/068/076 books, obj_080 shelf, obj_083 plant, obj_093 shelf,
obj_095), **1 ADDED: obj_030** (crude miss → floor anchor — but see look-fors),
13 multi-option, 1 none-plausible (obj_083 plant: "outdoor greenery seen through
a window, not a physical object in the room" — bad detection, feeds cleaning).
v1 iteration recorded: the 15 cm floor cutoff hid the floor from the two
truncated-box bookshelves (obj_043/obj_088) → the model flagged exactly that →
floor candidate now ALWAYS offered with its measured clearance; both resolved
rests_on floor (crude had them as WALL anchors — tier corrected).
Run-to-run notes: obj_009 basket flipped top option between runs
(floor ↔ inside-side-table, both retained — genuine ambiguity behaving as
designed); obj_030 is NAMED "book" but its verdict reason describes a yoga mat
unrolled on the floor (obj_031 the yoga mat sits next to it) — either an
identity problem or reason-bleed between adjacent batch items; identity food
for the cleaning step.

**Look for in the viewer:** (1) the demoted list — every one should read as a
"fluke contact" you agree with (obj_061 book was the user's own example);
(2) multi-option objects (basket obj_009 floor-vs-inside-table, books on stacked
shelves, lamp obj_062 mounted-vs-hangs) — are the alternates real ambiguity?;
(3) low-confidence tops: curtain obj_014 hangs_from wall 0.55, doors mounted_on
0.55–0.85, plant obj_083 rests_on desk **0.35** (its doubt survives in the
confidence + reason citing "greenery through window"); (4) whether any anchor
tint now looks WRONG against the splat.

**Provisional verdict:** PASS — the three v0 none-plausible flags were all
information (2 = my tolerance bug, fixed; 1 = the known suspect plant), the
demotions match the known fluke family, and no crude-miss surfaced as a new
anchor. **User verdict: pending (gate 6).**

### R2 · consistency pass on bedroom_marble (07-26G) — GATE OPEN

**What:** `compose/consistency.py` (first consumer of supported_by). Part A
self-audit: **0 flags** (no support cycles; nothing rests on the disputed
plant). Part B: all 157 resolved edges classified — code explained 132
(81 CONFIRMED_SUPPORT · 14 SUPPORT_ALT · 6 TRANSITIVE · 26 KEPT_GEOMETRIC ·
2 KEPT_STRUCTURAL · 3 KEPT_ARRANGEMENT); 25 leftovers → one sonnet batch →
**8 KEEP / 17 DROP proposals**. Graph untouched; verdicts in
`compose/consistency.json`.

**Why:** user ruling — supported_by does NOT fully supersede the edges;
containment/attachment/adjacency are arrangement facts composition consumes,
so every edge needs a consistency verdict.

**Look for:** (1) the 17 DROPs — the 8 shelf-riding wall grazes
(books/pillow/basket), picture-IN-book + toy-IN-book grazes, curtain-ON-desk
drape, two fake book-stacks (4+ cm air gaps), door-ON-floor (4.2 cm above;
verdict = mounted in wall), plant's moot edge, and **obj_093 IN obj_080
flagged as probable duplicate shelf detection** (SAME_CANDIDATE food);
(2) the 8 KEEPs — the model split wall contact semantically: floor-standing
furniture flush against a wall = genuine arrangement fact (desk, bookshelves
×3, shelves ×2), books genuinely inside shelves, basket tucked under desk;
(3) obj_030 "book" IN bookshelf kept — its identity oddity (R1) still open.

**Provisional verdict:** PASS — every drop reads as a true artifact, the
keep/drop split on wall contact is a real semantic distinction applied
consistently, and the duplicate-shelf find is new information the dedup-free
graph design predicted would surface at judge time. **User verdict: pending
(gate 6c).**

### R3 · the obj_001 evidence chain + context crops (07-26G → 07-27)

**The chain, as it actually unfolded:** (1) crude rule: plant obj_001 = floor
anchor (ON-floor edge). (2) supported_by v3/v4: rests_on bookshelf — the
metrics line hid overlap DIRECTION. (3) v4 directional metrics added (6 cm
sliver, side-by-side) — verdict STILL bookshelf, reason cites the appearance
description "sitting on a shelf". (4) User checked the crops: **too tight,
never show the plant's bottom** — the description was invented support.
(5) Fix: context crops (35/35/**75-below** pad + red outline) + appearance
v3 re-run (89/89) + supported_by v5 downgrade of description support-claims
→ **the new description from context crops STILL says "resting on a wooden
shelf."** The claim survived better evidence — it is now honest pixel
testimony, and the remaining question is box-vs-pixels, not cropping.

**Look for (user, tomorrow):** open `graph/crops_ctx/obj_001_m*.png` — does
the wider view actually show the floor / the shelf? If shelf: the crude
ON-floor edge + box position are wrong (box-surgery order). If floor still
not visible: crop padding needs another notch (or this object needs a
purpose-cut view).

**Provisional verdict:** the crops fix is WORKING as designed (descriptions
now grounded in visible context; support claims no longer croppping
artifacts) — obj_001 itself stays UNRESOLVED, correctly, until your eyes
rule. **User verdict: pending.**

### R4 · PH1 snap analyzer v0 (07-27) — GATE OPEN

**What:** `compose/snap.py` — deterministic corrections making each top
supported_by option physically exact, on the graph's own boxes (details in
the PH1 section above). **Why:** the user's loop-in-loop direction — the
physical stage is deterministic and its outputs are semantic-loop evidence.

**Look for:** (1) the 7 LARGE corrections — every one should read as a
suspect box you already believe (they are the known work-order list,
re-derived independently); (2) the `INTERNAL_SURFACE` rule (13 objects) —
books/objects on bookshelf inner boards left at observed height rather than
teleported to the shelf's top: is that the right v0 behavior?; (3) obj_083's
0.94 m floor snap — if the plant is real (R3 ruling), this is the box
surgery order; if not, it's a delete and the snap is moot — the two gates
resolve together.

**Provisional verdict:** PASS — zero false alarms in the flag list, frame
math verified against hand-computed values (obj_043 0.154, obj_088 0.206).
**User verdict: pending.**

---

## PARKED — screening draft (earlier this session, now a later step)

Compose-or-skip per anchor (`COMPOSE` / `SKIP_ARCH` / `HOLD`), one batched call,
`anchor_cast.json` + review sheet. To be redesigned on top of support stories when
reached — its anchor input will come from story readings, not touch edges. Open
discussion points recorded 07-26G: what SKIP means for the composed scene's judge
comparison; HOLD's blast radius on dependents.
