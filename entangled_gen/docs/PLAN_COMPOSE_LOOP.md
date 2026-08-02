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

**DEPENDENT-PLACEMENT CONTRACT (user ruling 08-01, follows the R4
pass):** snap's meaning SPLITS BY CLASS. Anchors: corrections are real
suspect-box evidence (unchanged). Dependents (sub-objects): corrections
are ADVISORY ONLY — a dependent's exact position is a function of its
parent's REAL geometry (shelf levels), which doesn't exist in the box
model; the binding output is the RELATIONSHIP, not the position. The
durable evidence is RELATIVE placement (height fraction of the parent's
span, footprint offset) — derivable any time from the verbatim boxes,
so NO CODE NOW. At mesh time (S4): children re-resolve against the
shopped parent's real interior, observed relative height selects the
level, in support-chain order. (Generalizes INTERNAL_SURFACE: observed
height IS the shelf — until a real shelf exists.)

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
| 6 | USER GATE: supported_by rulings in the viewer (R1) | **PASSED 07-31 (provisional, "good for now, expecting changes as we loop")** on the v6 layer — this row was stale ("OPEN") until 08-01 evening; re-affirmed via R7 on the post-R6 re-run | user |
| 6b | `compose/consistency.py` design + build + run (STEP 2, downstream of supported_by) | DONE 07-26G — 157 edges: 132 explained by code, 25 LLM leftovers → 8 KEEP / 17 DROP proposals; 0 audit flags; see R2 | — |
| 6c | USER GATE: consistency verdicts (R2 — v6 sheet: 13 drops + 8 keeps) | **PASSED 08-01 (provisional, "for now")** — reviewed in the viewer's new consistency box-color mode | user |
| 6d | tuning: `BENEATH_TOL` 0.12→0.30 (+`--beneath-tol` flag; user: occluded detections truncate boxes past 12 cm) | DONE 07-26G — 33 objects re-judged; anchors/demotions UNCHANGED; 29 top-option shifts: mass rests_on→inside for bookshelf contents, some supporters coarsened (shelf board→whole bookshelf), wall-mount confidences dropped (AC 0.8→0.6, pictures →0.5/0.45); trade-off on record: wider window = occlusion-robust but more distractor candidates. consistency.json now STALE (built on tol-0.12 layer) | user |
| 6e | prompt v5 (most-plausible framing + directional metrics: footprint %, edge slivers, side-by-side vs stacked) — the obj_001 lesson chain | DONE 07-26G/27 | — |
| 6f | CONTEXT CROPS: describe_nodes v3 (`crops_ctx/`, pad 35/35/75 + red outline, `--appearance-only`) + appearance re-run 89/89 | DONE 07-27 — obj_001 description STILL says "resting on a wooden shelf" under context crops → now honest pixel testimony, not a cropping artifact; gate evidence = `graph/crops_ctx/obj_001_m*.png` (user judges) | user |
| 6g | supported_by v5 re-run on refreshed (context-crop) descriptions | DONE 07-27 — 89/89; **31 anchors** (kept 31 / demoted 13 / added 0); multi-option 22→**5** (only the genuinely contested: doors ×2, pictures ×2, book); none_plausible → **0**: obj_083 FLIPPED to rests_on floor 0.55 (new description: "leafy plant as green silhouette against bright window, washed out by backlight" — context crop sees a real plant; verdict applies occlusion-truncation reasoning to the 93.6 cm gap); obj_030 identity self-resolved ("group of books… on a wooden shelf" — the yoga-mat text was reason-bleed); obj_001 shelf story persists at 0.55 (user's crops_ctx ruling pending, R3) | user |
| 6g2 | consistency re-run on the v5 layer | DONE 07-27 — 157 edges: 84 CONFIRMED / 4 ALT / 10 TRANSITIVE / 31 kept facts / **17 KEEP + 11 DROP** (LLM), 0 audit flags. Drop list sharpened: obj_080 repeatedly fingered as an OVERSIZED box swallowing books at wildly different heights (the duplicate-shelf suspicion, second independent angle); obj_095 caught claiming IN_WALL with an 8.4 cm gap FROM the wall | user |
| 6h2 | PH1 `compose/snap.py` v0 built + run (see PH1 section + R4) | DONE 07-27 — 7 LARGE corrections = the known suspect family exactly, zero false alarms | user |
| 6h3 | S4 shopping design notes mined from old C1–C5 (subagent research) | DONE 07-27 → `docs/S4_SHOPPING_DESIGN_NOTES.md` (module contracts, worked/failed record, reuse verdicts, 17 open questions) | — |
| 6h | `compose/propose_edits.py` — ISOLATED add/delete proposer + map placement (dashed, unwired) | **FULL RUN 08-01** on the v6 layer: 4 delete candidates → 3 DELETE / 1 KEEP · 5 ADDs; viewer edits review mode built; see R5 — superseded by 6h3 | user |
| 6h3 | propose_edits **v2 rework** (user design 08-01): regex + disputed detectors REMOVED (books/shelf never accused; resolved['removed'] already covers disputed); RAW verbatim consistency wordings piped to the audit judge; judge reports duplicate_suspicions → `reopen_petitions` (referrals to the J1 pair judge; unwired). Module now IN LANE as S3 (map linearized, loop arrows omitted) | **RUN 08-01**: 1 candidate → plant KEEP 0.6 (flipped) · 4 ADDs (blanket gone — variance) · 0 petitions (correct: v6 wordings have no object-dup phrasing); see R5b — **GATE OPEN** | user |
| 6h4 | **PART_OF RETIRED + graph stage re-run to resolved** (user ruling 08-01: pair-judge menu = SAME/DISTINCT; fragments are SAME — "not separately shoppable → not a node"; contents DISTINCT). build_edges also now records per-node `nesting` facts (containment ≥ .90; 108 entries / 62 nodes). Full replay: G2 → J1 v2 (14 live calls: 13 SAME / 1 DISTINCT — books-in-shelf finally DISTINCT first-try) → J5 (3/3 cache) → J2 (102 → **90 clusters**: shelf sections 080→043, 088→047 merged) → J3 (2 new names, both "bookshelf") → J4 re-run (13 flags; NEW: obj_023 disputed as duplicate shelf, obj_054 basket disputed) → J6 (obj_023 → **structure "part of bookshelf"**, obj_054 basket REAL, 3 edge REJECTs incl. picture-on-picture) → J7: **85 shipping / 5 removed**. Backup: scene_graph.json.bak-0801-prepartof | **DONE 08-01** — compose files (supported_by/consistency/snap/edit_proposals) now STALE vs the new resolved; re-run pending. obj_093/obj_140 still un-nominated (semantic nomination not built) | — |
| 6l | viewer STALE GATE (user 08-01 evening: "take out the stale stuff"): serve.py freshness-gates the 4 compose routes (file older than scene_graph.json → `{stale:true}` stub + re-run hint; un-stales automatically on re-run); index.html treats stale layers as not-built (review modes hidden) + dim "⚠ stale, hidden: …" note in the row | DONE 08-01 — verified: all 4 layers stubbed stale against the 18:30 graph | user |
| 6m | compose chain re-run on the new resolved layer (82 clusters): supported_by → consistency → snap, sequential, defaults (v6 prompts, beneath-tol 0.30, caches live) | DONE 08-01 evening (49/82 cache hits + 33 judged; exit clean) — supported_by 82/82, **30 anchors / 9 demoted / 16 multi-option / 0 none_plausible** · consistency 77 confirmed / 11 alt / **11 DROP + 4 KEEP**, 0 audit flags · snap **18 LARGE**. See R7 | user |
| 6n | viewer HUD cleared to latest-and-greatest (user 08-01 evening): main toggle RENAMED "supported_by graph (canonical)" → **"scene model (resolved · canonical)"** (row header "scene model:"); REMOVED from HUD+code: composed (C6 glb), collisions overlay, analyzer cams, ALL box-source layers (serve registry emptied, entries commented for one-line re-enable); pass-2 existence colors neutralized in resolved view (confirmed = ship blue; green obj_027/obj_054 was settled history reading as current review); axes triad behind default-off "axes" toggle. KEPT collapsed audit: graph record (obj_083 ctx crops live there) + contact edges. Files + serve routes untouched | DONE 08-01 — both files syntax-checked, server restarted, registry serves [] | user |
| 6o | scene-model sub-row consolidated (user 08-01 evening: "a lot of sub check boxes… clean them"): the 5 checkboxes (anchor focus / supported_by arrows / review mode / consistency / snap [/ edits]) → ONE "view" dropdown (anchor tiers · support review · consistency · snap · edits-when-fresh · plain), legend + tooltip follow the picked mode; arrows auto-show in anchors+support, ghosts in snap, ADD labels in edits; default = support review (the open gate) | DONE 08-01 — syntax-checked, served | user |
| 6q | view dropdown TRIMMED post-verdicts (user 08-01 close: "if i dont need it take it out — we already reviewed"): live set = **snapped preview (default) · edit proposals (when fresh) · plain**; the closed-gate colorings (anchor tiers / support / consistency / snap review) hidden behind `?allviews=1` (dim hint in the row) | DONE 08-01 | user |
| 6r | S3 propose_edits v2 re-run on the FRESH state (post-R6 resolved 82 + R7 compose layers) — closes the R5b staleness note; same code, prompt_version 2, sonnet | **DONE 08-01 late** — 0 delete candidates (verified honest against the layers: 0 none_plausible, no all-edges-dropped object) · **4 ADDs (window wall 0.75 · keyboard 0.7 · mouse 0.65 · blanket 0.55)** · 0 petitions; see R5c — **PASSED 08-01** | user |
| 6s | **PH1 snap v1 — SNAP + BOX ADJUDICATION** (user design 08-01 late, born from the curtain-thickness diagnosis: 7 good measurements, 1 bleeding mask, q=0.05 fusion too weak at n=8): scripted snap = pass-A PROPOSAL; docket = LARGE ∧ arch-involved support (top/alternate/against) ∪ judge suspect_box → ONE batched sonnet call, typed menu (ADOPT_REFIT_AND_SNAP / SNAP_AS_IS / NO_SNAP / DEFER_TO_SURGERY); REFIT = pure-code MAD re-fuse from raw lift-pool members (provenance chain resolved→manifest→lift_poolc); pass B re-snaps with verdicts applied; --no-llm = v0 verbatim | **BUILT + RUN 08-01 late** — docket 6: curtain REFIT (thickness 0.449→0.206 m, wall delta 0.251→0.008 — flag RESOLVED) · obj_023 REFIT (depth trim 0.13) · AC NO_SNAP (doubt preserved) · 3 SNAP_AS_IS · LARGE 18→16; see R8 — **GATE OPEN** | user |
| 6t | **S2 v7 against-slot fix** (user-spotted via the AC card): code matcher no longer counts against-slot hits as CONFIRMED; they fall to the LLM leftovers (docket shows "ruled AGAINST"); re-run 1 fresh call → AC IN_WALL edge DROPped, 12 DROP / 4 KEEP; S3 re-run (0 deletes, adds variance: window out, wardrobe back); snap NOT stale (doesn't read consistency) | **DONE 08-01 late** — see R9 | user |
| 6u | **S1 v7 TYPE-PRIOR TIEBREAK** (user design 08-02, the AC case): observationally-equivalent candidates broken by kind-typical support; tiebreaker only; defiance must be stated. Full re-judge 82/82 (3 calls) | **RUN 08-02** — AC softened (0.62 + wall alt 0.35, no flip) · door → embedded_in wall ✓ · **⚠ obj_023 bookshelf flipped floor→wall-mounted** (anchors 30→29) · 12 shelf-nest reshuffles; downstream refresh HELD for the obj_023 ruling; see R10 — **GATE OPEN** | user |
| 6v | **S1 v8 BOTTOM-EDGE EVIDENCE** (starved-judge fix): per-item line = where each view measured the lowest visible point (74/82); template reads disagreement as occlusion. Full re-judge + chain refresh (S2 10 calls · snap · S3) | **RUN 08-02** — obj_023 FLIPPED BACK to floor 0.60 ("likely truncation" — textbook) · books → inside 0.8–0.9 · doors → wall · anchors 30 · **⚠ snap curtain verdict FLIPPED to DEFER (run variance, no verdict cache — the R8 slim curtain is out of the layer)** · S3 adds: mouse out, wardrobe/trash in; see R10b — **GATE OPEN** | user |
| 6w | **snap v1.2 CACHE + RULINGS + reframed docket** (R10b/R11): adj prompt v2 (majority rule, magnitude never a defer reason), "k of n AGREE" framing, flags with direction; snap_cache.json (evidence-keyed) + snap_rulings.json (user pins); AC pinned NO_SNAP pending eyeball | **DONE 08-02** — curtain ADOPT 0.85 (flag read correctly), re-run = 0 LLM calls; see R11 — **GATE OPEN**. Accepted-not-built: surface-based support vocabulary (on_top/inside/…, leans_on retired) | user |
| 6x | **AC GROUND TRUTH (user 08-02: wall-mounted) + S1 rulings mechanism** (`supported_by_rulings.json`, mirror of snap's; ruling = options[0] by:"user"). v9 real-gap prompt rule tried first — did NOT flip the AC + reshuffled synonym families (prompt accretion limit). Chain refreshed: AC snaps wall-flush, off the suspect lists; curtain/shelf verdicts stable | **DONE 08-02** — see R12 (closed). Queued: surface vocab rework + witness verb fix | user |
| 6i | pipeline map redrawn: 3.1 = S1 supported_by → S2 consistency → S3 screening → S4 shopping; cards updated; propose-edits node dashed; J6 card v3 note | DONE 07-27 (user pre-approved "update the pipeline viewer") | — |
| 6j | 07-30 session: R3 RULED (floor) → root-cause chain → appearance v4 (geometry-blind) + v5 (ROW-SHEETS) adopted in describe_nodes.py; viewer review-mode colors + existence badges dropped from titles + ctx crops in the click card (+ /graph_crops_ctx/ route); map: J6 v4/v5 notes + OLD C1–C7 column REMOVED (user); hybrid escalation designed (safety net, re-time later) | DONE 07-30 — v5 chain ran: obj_001 fixed end-to-end (rests_on floor 0.6, anchor back; 30 anchors / 14 demoted); obj_083 flip-flopped to none_plausible (run-to-run instability = v6 motivation); consistency v5-layer: 84 confirmed / 25 DROP / 3 KEEP (fact-consolidation shift) | user |
| 6k | **v6 STRUCTURED TESTIMONY adopted (user 07-31)**: appearance v6 = intrinsic-only description + support_view (GENERIC contacts: floor/horizontal_surface/vertical_surface/ceiling/**not_visible**, never names the neighbor — the invention channel closed) · supported_by v6 consumes support_view instead of prose support-claims (witness reports contact geometry, judge matches to candidates). Probe 07-30 on 8 hard cases: 7/8 (obj_001 floor ✓, obj_083 honest not_visible + "seen through glass" intrinsic ✓, obj_013 gave vertical only — dual-contact under-report, watch); full v6 chain (describe → supported_by → consistency) | **DONE 07-31** — 89/89 described (all intrinsic-only); supported_by v6: 30 anchors / 14 demoted (obj_001 floor **0.75**, shelf alt 0.2 ✓ · obj_083 stable rests_on desk 0.35, no more none_plausible flip-flop · obj_013 collapsed to rests_on bookshelf-top **0.9** · **obj_002 AC DEMOTED**: rests_on bookshelf-top 0.55 vs wall-mount 0.4 — user eyes) · **multi-option 5→30** (mostly second-place candidates 0.2–0.4 inside the duplicate-shelf nest — dedup evidence, not indecision; open Q: viewer "contested" threshold) · consistency: 77 confirmed / 26 alt / 13 DROP + 8 KEEP, 0 audit flags. STDIN fix both bridges (WinError 206: v6 prompts crossed the 32k argv cap — prompts now piped). | user |
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
graph design predicted would surface at judge time. **User verdict (08-01):
PASS, provisional ("results make sense, pass for now") — reviewed on the v6
sheet (13 DROP / 8 KEEP after the v6 supported_by re-run) via the viewer's
new consistency review mode (box colors = per-edge verdicts, jCsRev toggle +
card section; serve.py /consistency.json route). User-spotted invariant
VERIFIED in code + data: no DROP ever touches a supported_by relation —
structurally guaranteed (matched edges are code-stamped before the LLM sees
leftovers, consistency.py:245) and empirically 0/13 drops conflict with any
option (supporter, alternate, or against) of the subject.**

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
rule. **User verdict (07-30): FLOOR — the context crops clearly show the
plant in a planter on the floor.** The description is wrong; root-cause
decomposition (07-30 session): (1) the box is occlusion-truncated (0.42 m
tall, bottom 0.19 m above floor — misses the planter base) → box-surgery
queue; (2) the appearance item line LEAKS GEOMETRY ("bottom 0.19 m above
the floor") into what supported_by treats as independent pixel testimony —
circular evidence, fix = drop/neutralize that line in the appearance
prompt; (3) the VLM saw 256px contact-sheet tiles, not the full-res crops
(tile-resolution lever: bigger tiles / per-object escalation). obj_001's
supported_by verdict (rests_on shelf 0.55) is therefore WRONG with cause
understood.

**07-30 controlled diagnostic (cause ISOLATED = BATCH BLEED):** appearance
v4 (geometry-blind item lines, PROMPT_VERSION 4) re-ran 89/89 — obj_001
STILL "on a wooden shelf" → the geometry leak was real but not
load-bearing here. Two solo calls, same instruction/model: (A) the exact
256px sheet tiles → "on the wooden floor"; (B) full-res context crops →
"on the wooden floor next to a shelf" (the true arrangement, adjacency
included). Batched-with-7-neighbors = shelf (2 independent samples, v3+v4
runs); solo = floor (2/2, both resolutions). Resolution exonerated;
sheet-mates (several books-on-shelves items) contaminate the answer — the
obj_030 reason-bleed family, now experimentally confirmed. Lever = batch
composition/size or per-object calls for the appearance pass (general fix,
no per-scene knowledge), not tile size.

**07-30 experiment round 2 (mechanism pinned = SHEET LAYOUT; fix
ADOPTED):** timed on sheet 1's 8 objects, same instruction/model —
grid sheet (the old 4-col mixed layout): 16.1 s, obj_001 shelf (now 3/3
wrong across independent runs) · ONE-BY-ONE in one call (per-item images,
answer-before-next; shared context KEPT): 52.6 s, floor ✓ → shared
context alone doesn't cause the error; the fused grid does (cross-tile
contamination — user's "confused where is where" hypothesis) ·
**ROW-SHEET** (one item per color-framed row, number burned into each
crop, dark separators, prompt forbids cross-row reading): **15.0 s,
floor ✓ — the fix is FREE.** ADOPTED as appearance PROMPT_VERSION 5
(build_sheet rewritten in describe_nodes.py; v4 geometry-blind lines
kept). HYBRID escalation designed + trigger tested (top supported_by
conf < 0.6 → one-by-one re-describe; mechanically selected
obj_001+obj_006 on batch 1) — kept as the safety net for what layout
can't fix; its timing run hit API 529 (server overload), re-time later.
Row-sheet side observations: door description improved ("stands in a
doorway"), AC support line drifted ("above a desk") — single-sample
noise, watch on the full run.

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

**08-01 RE-RUN on the v6 layer (the v0 output above was STALE):**
dispositions 17 floor / 11 wall-flush / 2 ceiling / 26 on-object /
**31 INTERNAL_SURFACE** (was 13 — v6 moved bookshelf contents onto
boards) / 1 inside / 1 embedded. **LARGE corrections 7 → 18.** Knowns
persist (obj_096 picture 0.315 · obj_014 curtain 0.251 · obj_005 monitor
0.219 · obj_088 0.206 · obj_043 0.154). v6-driven newcomers: **obj_001
plant floor-snap 0.191 = exactly its known truncation float** ·
**obj_002 AC 0.255 up to bookshelf-top — quantifies the demoted verdict;
if the AC is really wall-mounted this is the smoking gun (open eyeball
item)** · obj_083 now 0.15 to desk (was 0.94 to floor — verdict change) ·
book cluster in/near the duplicate-shelf nest: obj_048 0.31→obj_140,
obj_050 0.242 / obj_042 0.229 →obj_022, obj_038 0.147 / obj_044
0.142 →obj_043, obj_087 0.171, obj_110 0.124 · obj_023 shelf 0.184 ·
obj_075 basket 0.112 · obj_013 picture 0.101. VIEWER (08-01): snap
review mode on the scene-graph row — box colors by correction size
(red >10 cm / yellow 2–10 cm / green ok / dim no-move), white ghost
outline = snapped AABB + correction line, click card shows
disposition+magnitude; serve.py /snap.json route. **User verdict
(08-01): PASS, provisional — with a standing RULING: dependent
(non-anchor) objects have no exact target yet BY NATURE — e.g. books
should sit on shelf LEVELS, but interior levels don't exist in the box
model; real levels arrive with shopped meshes (S4). So large
corrections on dependents are expected noise, not findings. The
stage's real invariants = (1) anchors correct, (2) sub-object
relationship edges correct; exact dependent placement is deferred to
mesh time. (Consistent with the INTERNAL_SURFACE rule: observed
height IS the shelf.) Open eyeball item obj_002 AC stays open — that
one is an anchor-class question (wall vs bookshelf).**

### R5 · propose_edits full run on bedroom_marble (08-01) — GATE OPEN

**What:** `compose/propose_edits.py` first full (LLM) run, on the v6 layer.
Deletes: 4 doubt-flagged candidates → one batched confirm/deny → **3 DELETE
(obj_061 book 0.72, obj_076 book 0.70, obj_083 plant 0.75) / 1 KEEP
(obj_093 shelf)**. Adds: **5 proposals, every one with declared support**
(blanket on:obj_008 bed 0.8 · keyboard on:obj_039 desk 0.75 · mouse
on:obj_039 0.6 · wardrobe floor 0.55 · trash can floor 0.55). Output
isolated in `compose/edit_proposals.json` — nothing consumes it. VIEWER
(08-01): edits review mode (red DELETE / green KEEP / yellow unjudged /
dim never-flagged; blue floating "+ADD" labels at declared support; card
shows verdict + raw signals).

**Why:** the loop's add/delete channel needs a reviewed proposer before it
earns its wire (07-27 direction, dashed on the map).

**Look for:** (1) **PROVISIONAL FINDING — the two book DELETEs look like a
signal-semantics artifact:** the aggregator's duplicate-regex matched
consistency DROP reasons saying "Duplicate wall contact" — but that meant
duplicate *FACT* (inherited wall-touch, R2's consolidation family), not
duplicate *OBJECT*; the LLM then confirmed deletion on that misread
("leaving weak support for the book as a standalone object" — existence was
never in doubt). If confirmed at review: fix = aggregator distinguishes
edge-duplicate from object-duplicate signals (or the confirm prompt states
the object's existence evidence). (2) obj_083 plant DELETE 0.75 — rests on
the honest chain (conf 0.35 + dropped wall edge); genuinely plausible
(v6 intrinsic: "seen through glass") but decide vs the R3 lesson: boxes
lie, pixels rule — your eyes on its ctx crops. (3) obj_093 KEEP — the
duplicate-shelf question correctly deferred to SAME_CANDIDATE judging
rather than deletion? (4) The 5 adds — all plausible bedroom items;
wardrobe/trash-can are the speculative pair (conf 0.55).

**Provisional verdict:** MIXED — adds look sane and correctly conservative;
obj_083/obj_093 verdicts are defensible; the two book DELETEs are probably
WRONG with cause understood (signal semantics, not LLM failure). **User
verdict: superseded by R5b (the v1 output was regenerated by the v2 run).**

---

### R5b · propose_edits v2 rework run (08-01) — GATE OPEN

**What:** v2 of `compose/propose_edits.py` (user design: "pipe the exact
wordings"). Detectors: the R5 'duplicat' regex REMOVED (code never
interprets prose) and the existence-disputed detector REMOVED (contract
check: `materialize_verdicts.py` already strips disputed nodes from
resolved; `resolved['removed']` carries them — the detector could only
accuse objects absent from the inventory). The audit judge now receives
each candidate's consistency verdicts VERBATIM plus all 13 dropped-edge
wordings scene-wide, is told duplication is NOT a delete reason, and may
report `duplicate_suspicions` → code-validated pairs written as
`reopen_petitions` (referrals to the J1 pair judge / future screening
holds; unwired). Run: candidates 4 → 1; **plant obj_083 FLIPPED to KEEP
0.6** ("benign box grazes on an oversized box, not a ghost"); **4 ADDs**
(wardrobe 0.75 · keyboard 0.75 · mouse 0.65 · trash can 0.5); **0
petitions**.

**Why:** R5's provisional finding confirmed — the book DELETEs were a
signal-semantics artifact. The v2 design keeps interpretation inside the
one LLM that owns the stay/go decision (no-orchestrator rule).

**Look for:** (1) Books + shelf correctly ABSENT from candidates (the bug
class is structural now — word sightings cannot create accusations).
(2) The plant FLIP: v1 said DELETE 0.75 on the same typed signal; v2's
richer verbatim evidence flipped it to KEEP 0.6 — read its reason: does
"oversized box, benign grazes" match your R3 pixels-rule read of the ctx
crops? If you rule the plant real, v2 got it right where v1 got it wrong.
(3) 0 petitions is CORRECT on v6 (grep: only 3 'duplicat' wordings exist,
all fact-duplication phrasings — the R2-era "probable duplicate shelf"
sentence is not in the v6 layer). The shelf-nest question therefore still
has NO nomination path — settled direction: non-visual dedup consuming
these petitions + inventory, slotted at/after screening. (4) ADD variance:
blanket (v1's top add, 0.8) vanished in v2; wardrobe rose 0.55 → 0.75.
Same prompt intent, different runs — is add-pass stability worth a
mitigation (e.g. union of N runs), or acceptable for a proposer?

**Provisional verdict:** the rework does what was designed — accusations
are typed-signal-only, prose is read only by the judge, and the judge's
plant reversal is better-reasoned than v1's. Adds remain sane but show
run variance. **User verdict: pending (R5b) — NOTE: output now STALE
(the graph re-ran underneath it, see R6); re-run propose_edits after the
compose chain refresh and judge the fresh file instead.**

---

### R6 · PART_OF retirement + J0 triage + graph re-run to resolved (08-01B) — GATE OPEN

**What:** pair-judge menu v2 (SAME/DISTINCT; PART_OF retired — user
ruling: fragments are SAME, "not separately shoppable → not a node";
contents DISTINCT). New J0 pair triage (`graph/triage_pairs.py`):
nesting facts (containment ≥ .90, recorded by build_edges since today)
→ one batched text call → NOMINATE/SKIP, nominate-on-doubt. Full graph
replay twice. Final: **102 detections → 86 clusters → 82 shipping / 4
removed**. Judge tallies: triage 94 → 6/88 (all contents skipped);
pair judge 20/20 → 18 SAME / 2 DISTINCT. Shelf corner RESOLVED:
obj_043 = {043,080,093,140} · obj_023 = {023,047,088} · books each
hold one IN edge · no loose "shelf" nodes. Backup:
`scene_graph.json.bak-0801-prepartof`.

**Why:** the shelf-in-shelf investigation exposed (a) the vague PART_OF
category (books-ruled-part-of-shelf needed a downstream REINTERPRET),
(b) the IoU-floor nomination blind spot (3 pairs at containment 1.0
never judged). The retirement fixes (a); triage fixes (b) at text-call
cost.

**Look for (viewer :8321, hard refresh; compose review modes are STALE
— ignore them):** (1) obj_043 and obj_023 merged clusters — do the
pooled crops read as ONE unit each? (2) **obj_083 plant REJECTED** —
contradicts the R3-era leaning and propose-edits v2's KEEP; your eyes
on the record-layer ctx crops decide. (3) obj_059 verdict flip
(rejected → "small glass decorative") — run instability, same crops.
(4) obj_062 renamed lamp → "air conditioner" (coherence said fan/linear
light; a second ceiling AC is suspicious). (5) books-in-shelf pair:
DISTINCT first-try under v2 — the vocabulary fix working. (6) triage's
6 nominations vs 88 skips — any obvious miss in the skip list?

**Provisional verdict:** machinery behaved exactly as designed
(deterministic replay, cache discipline, self-checks all PASS); the
corner outcome matches the user's stated intent. The three flagged
verdicts (obj_083 / obj_059 / obj_062) are model calls on thin crops —
genuinely open, user judges pixels. **User verdict (08-01 evening):
PASS, provisional ("i think this is good") — reviewed in the resolved
view after the viewer stale-gate cleanup (see 6l); no per-item
findings raised. The R6 look-for items (obj_083 crops, obj_062 second
AC, obj_002 wall-vs-bookshelf) were not individually ruled — they
remain open eyeball items. User then ordered the compose chain re-run
through snap.**

---

### R7 · compose chain refresh on the post-R6 resolved layer (08-01 evening) — GATE OPEN

**What:** supported_by → consistency → snap re-run on the 82-cluster
resolved layer (R6 output). Viewer: :8321, hard refresh — the compose
review modes un-staled automatically (6l gate); edits stays hidden
(propose_edits not re-run). Files:
`D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\compose\{supported_by,consistency,snap}.json`.

**Why:** every compose verdict must describe the graph that exists;
the merges (shelf nests → obj_043 / obj_023) and 4 removals changed the
candidate space under all three modules.

**Numbers vs the v6-on-89 baseline:**
- supported_by: 82/82 resolved · **30 anchors / 9 demoted** (was 14) /
  **16 multi-option** (was 30 — the duplicate-shelf runner-ups vanished
  WITH the duplicates, as predicted) / **0 none_plausible**. obj_002 AC
  demoted again (bookshelf vs wall-mount still the open question).
- consistency: 77 CONFIRMED / 11 ALT / 1 TRANSITIVE / 24 kept-geometric /
  1 kept-arrangement · leftovers 15 → **11 DROP / 4 KEEP** · 0 audit
  flags. New drops worth eyes: obj_027 picture-IN-book ("box overlap
  misread as containment") · obj_054 basket-IN-chair (pedestal can't
  contain it — matches J6's under-chair reading) · curtain-ON-desk drape.
  Rest = the familiar inherited wall-graze family.
- snap: 17 floor / 11 wall-flush / 2 ceiling / 23 on-object /
  25 internal-surface / 4 inside-container · **18 LARGE**. Anchor-class
  knowns persist: obj_096 picture 0.315 · obj_014 curtain 0.251 ·
  obj_005 monitor 0.219 · obj_023 shelf 0.206 · obj_001 plant 0.191 ·
  obj_043 shelf 0.154 · **obj_002 AC 0.255 up to bookshelf-top — still
  the smoking gun for the wall-vs-bookshelf call**. The book-cluster
  LARGEs are dependents = advisory only (R4 standing ruling).

**Look for (viewer review modes, in effort order):** (1) supported_by
mode: the 9 demotions + obj_002's verdict — agree? (2) consistency mode:
the 11 drops, esp. obj_027 and obj_054; (3) snap mode: any LARGE on an
ANCHOR that isn't already a known suspect box. (4) The un-ruled R6
eyeball items remain: obj_083 ctx crops (rejected — record layer only),
obj_062 "air conditioner" rename.

**Provisional verdict:** PASS — the chain reproduced every standing
verdict on the merged layer, multi-option collapsed exactly where dedup
removed the ambiguity source, and no new none_plausible/audit flags
appeared. **User verdict (08-01 evening): PASS, provisional — reviewed
via the new snapped-preview view ("i think the snap seems fine"); no
per-item findings. Open eyeball items carry forward: obj_002 AC
wall-vs-bookshelf, obj_062 second-AC rename, obj_083 crops.**

---

### R5c · S3 propose_edits v2 on the fresh post-R6/R7 state (08-01 late) — PASSED

**What:** the R5b-mandated re-run — same v2 code (prompt_version 2, sonnet),
now on the fresh scene-graph state (82-cluster resolved + R7 supported_by /
consistency). Results: **0 delete candidates** (deletes empty) · audit call
still ran over the 11 dropped-edge wordings → **0 duplicate petitions** ·
**4 ADDs**: window (wall, 0.75, "curtain obj_014 with no window in
inventory") · keyboard (on:obj_039 desk, 0.7) · computer mouse (on:obj_039,
0.65) · blanket (on:obj_008 bed, 0.55). Output:
`D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\compose\edit_proposals.json`.
Viewer edits mode un-stales automatically (6l gate): :8321, hard refresh,
view dropdown → "edit proposals".

**Why:** R5b's verdict was pending on a file the graph re-ran underneath;
every compose verdict must describe the state that exists.

**Zero-candidates verification (code check, not model):** the fresh layers
contain 0 none_plausible objects and NO object whose every support-type
edge was DROPped; the one weak-top-conf object (obj_087, <0.5) keeps live
support edges, so per the two typed signals 0 candidates is CORRECT —
honest emptiness, not a silent failure. The old candidate family vanished
legitimately: obj_083 was removed by the graph itself (R6 REJECTED), and
the book accusations were the retired regex (structurally impossible now).

**Look for:** (1) empty deletes — agree that "nothing to delete" is the
right reading of the fresh state, or does your eye still want a candidate
(obj_002 AC? it has live support edges, so typed signals correctly stay
silent)? (2) The 4 adds vs the actual room — **window is the interesting
one**: first run to notice curtain-without-window, and it lands exactly
where S4 screening owns doors/windows/curtains. (3) **Add variance, third
data point** — v1: blanket/keyboard/mouse/wardrobe/trash-can · v2-stale:
wardrobe/keyboard/mouse/trash-can · v2-fresh: window/keyboard/mouse/
blanket. Keyboard+mouse = the stable core; wardrobe/trash-can/blanket/
window rotate. Decide: union-of-N-runs mitigation, or acceptable for a
proposer whose output faces screening anyway? (4) 0 petitions again
correct (the 11 drop wordings are all fact-duplication phrasings).

**Provisional verdict:** PASS (provisional) — the module behaved per the
v2 contract on the fresh state: accusations stayed typed-signal-only and
the empty result traces honestly to the layers; adds are sane and
conservative with declared support, run variance remains the one open
design question (carried from R5b look-for 4). **User verdict (08-01
late): PASS — "this is great… this makes a lot of sense"; the 4 adds and
the empty delete list both accepted. The add-variance question was not
ruled on — carries forward as a screening-time design point. This closes
the R5 chain (R5 superseded → R5b stale → R5c passed).**

---

### R8 · PH1 snap v1 — snap + box adjudication, first run (08-01 late) — GATE OPEN

**What:** snap rebuilt per user design ("snap proposes; flagged boxes get
an agent"): pass A = the old scripted snap, now a proposal; docket = LARGE
corrections whose support involves architecture (top pick, alternate, or
ruled-against candidate) ∪ judge suspect_box pointers — dependents (books
/ baskets) stay advisory per the R4 ruling; ONE batched sonnet call picks
per case from a typed menu; REFIT is pure code (MAD outlier rejection over
the raw per-view lift measurements, provenance chain
resolved.members → manifest.members → lift_poolc.json); pass B re-snaps
everything with adopted refits substituted and held boxes pinned.
Degrade verified: `--no-llm` reproduces v0's output exactly (same 18
LARGE). Output:
`D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\compose\snap.json`
(viewer :8321, snapped-preview view reads the new layer).

**Run results (docket 6):**
- **obj_014 curtain — ADOPT_REFIT_AND_SNAP 0.65:** the diagnosed outlier
  (pp40 mask, score 0.39, z_hi 4.572) rejected; thickness 0.449 → 0.206 m;
  wall-flush delta 0.251 → **0.008 m** — the thick box WAS the wall gap;
  both flags resolved by one mechanical fix.
- **obj_023 bookshelf — ADOPT_REFIT_AND_SNAP 0.7:** two low-score members
  (one view, pano_y315_pm40) rejected; depth (z_lo) trimmed 0.13 m; floor
  delta unchanged at 0.206.
- **obj_002 AC — NO_SNAP 0.7:** wall-vs-bookshelf attribution doubt
  (surfaced from supported_by's `against` field) correctly preserved —
  held in place, disposition HELD_NO_SNAP.
- **obj_096 / obj_001 / obj_043 — SNAP_AS_IS:** no refit evidence, no
  live attribution doubt → scripted move stands.
- LARGE corrections 18 → 16 (curtain resolved, AC held).

**Why:** the curtain postmortem showed suspect boxes are often one bad
measurement, mechanically reversible from evidence already in the state;
the shrink-experiment lesson (agent chooses, code executes) shaped the
menu design.

**Look for:** (1) curtain in the snapped preview — 20 cm thick and flush
to its wall now; the physical change you asked about. (2) obj_023's
refit: the agent's REASON says "shorter height" but the refit touched
DEPTH (z_lo) — right verdict, sloppy axis language; its floor-float flag
(0.206 in y) is still open. (3) AC held — agree that not snapping is
right until the wall-vs-bookshelf eyeball? (4) obj_096 picture: SNAP_AS_IS
despite being the deepest suspect (0.315) — no refit was available (its
members don't show a clean outlier); is wall-flush the right call or
should it have been DEFER? (5) Docket rule: books correctly excluded?

**Provisional verdict:** PASS pending your eyes — the module did what was
designed: mechanical refits only where member evidence supports them, the
one attribution-doubt case held rather than baked in, degrade path exact.
Known softness: agent reasons can misname axes (cosmetic, verdicts sound);
obj_096 got the weakest ruling (0.55) on the thinnest evidence. **User
verdict: pending (R8).**

---

### R9 · S2 v7 — the against-slot bug (08-01 late, user-spotted) — FIXED + RE-RUN

**What:** the user, reading the AC's card after R8, asked why obj_002 had
BOTH "on bookshelf" and "in wall" edges confirmed. Trace: consistency's
Part-B code matcher (`consistency.py:249`) counted a hit on an option's
**against** slot as CONFIRMED_SUPPORT — silently blessing the exact edge
the support ruling had REJECTED, and (worse) exempting it from the
leftover judge, the one pass that reads evidence. Rationale-at-the-time:
"this edge is already accounted for → don't spend a judge slot"; it
conflated *examined* with *confirmed*. Fires only on contested calls
(against slots are rare) — precisely the cases worth surfacing.

**Fix (v7):** supporter-slot-only matching; against-hits fall through to
the LLM leftover lane; the leftover docket's support-summary line now
appends ", ruled AGAINST <id>" so the judge sees the contradiction.

**Re-run:** 16 leftovers (15 cached, 1 fresh call) — the AC wall edge
judged **DROP**: "Support analysis already found obj_002 resting on
obj_023 and explicitly rejected the wall." Sheet now 12 DROP / 4 KEEP /
76 CONFIRMED (was 11/4/77). The wall-vs-bookshelf question itself stays
OPEN (against field + snap HELD_NO_SNAP + your eyeball item) — the drop
follows the current ruling; if your eyes overturn it, S1 re-runs and this
edge gets re-judged.

**Downstream refresh:** S3 propose_edits re-run (consistency is its
input): 0 deletes / 0 petitions again; adds = blanket 0.85 · keyboard
0.8 · mouse 0.75 · wardrobe 0.55 — **the R5c-passed window add vanished
this run** (4th variance data point: keyboard+mouse stable in all 4
runs; window appeared in exactly 1). Snap NOT re-run: it does not read
consistency.json, so the R8 artifact stands. HONEST NOTE: the R5c-passed
edit_proposals.json has been regenerated — same character, different add
tail; the standing variance question (union-of-N?) just got more urgent
for screening design.

---

### R10 · S1 v7 — type-prior tiebreak, full re-judge (08-02) — GATE OPEN, downstream refresh HELD

**What:** user design after the AC discussion ("flush fit and resting are
observationally equivalent — why did it tip to the shelf when that defies
common sense"): the S1 judge prompt gains a TIEBREAK-BY-TYPE block — when
two candidates both fit the numbers and testimony, weigh what objects of
this kind typically rest on / mount to; tiebreaker ONLY (clear
measurements still win — generated scenes are weird); rulings that defy
type must say so. PROMPT_VERSION 6→7, cache invalidated, full re-judge:
82/82, 3 calls. v6 layer backed up to the session scratchpad
(`supported_by_v6.json`).

**Headline results:**
- **obj_002 AC: did NOT flip** — still leans_on bookshelf, but confidence
  0.75 → **0.62**, and **mounted_on wall is now a ranked alternate
  (0.35)**, not just an against-footnote. The witness's "rests flat" line
  still outweighed the prior; the doubt is now structural (two live
  options), which is arguably the honest verdict.
- **obj_128 door: rests_on floor → embedded_in wall (0.55)** — the prior
  working exactly as intended.
- **⚠ obj_023 bookshelf: rests_on floor 0.65 → mounted_on WALL 0.55** —
  the surprising ripple. Its box floats 21 cm above the floor (the known
  LARGE flag), so the judge now reads "floats + flush to wall" as
  wall-mounted shelving. Physically possible, but a 1.6 m bookshelf
  standing on the floor with a truncated box is at least as likely — and
  this flip DEMOTES a floor anchor (anchors 30 → 29) and re-parents the
  AC's supporter. THE R10 eyeball item.
- 12 further top-support changes, almost all book/basket reshuffles
  inside the two shelf nests (the known noisy dependent family — inside→
  rests_on reinterpretations, sibling swaps). Multi-option 16 → 8.
  Confidence shifts: pictures dropped ~0.2 (prior: pictures hang OR
  stand — honest doubt), small shelf items rose ~0.2.

**Downstream NOT refreshed yet:** S2/PH1/S3 still describe the v6 layer.
Held because obj_023's flip is a structural anchor change — refreshing
would bake it into consistency verdicts, snap targets (books re-snap
against a wall-mounted shelf), and propose_edits. **Rule on obj_023 (and
skim the AC's new two-option verdict) first; then the chain re-runs.**

**Provisional verdict:** the tiebreaker did what it was designed to do in
2 of 3 headline cases (door fixed, AC honestly softened); obj_023 shows
the prior's failure mode — a truncated box making the "typical" story
lose to a plausible-but-unusual one. If your eyes say floor-standing,
options: revert just obj_023 via ruling, or sharpen the prompt (floats
explained by truncation should favor the floor). **User verdict:
pending (R10).**

---

### R10b · S1 v8 — bottom-edge evidence + full chain refresh (08-02) — GATE OPEN (supersedes R10's hold)

**What:** the obj_023 postmortem ("why can't the agent see a 1.6 m
bookshelf stands on the floor?") answered: the judge was STARVED — the
lift pool knew 9 of 11 views never saw below ~80 cm (occlusion), but
nothing piped that to S1. v8: every item now carries a **Bottom-edge
evidence** line (where each view measured the lowest visible point,
heights above floor + image-edge clips; >25 cm cross-view disagreement
annotated as "lower part hidden from most views — true bottom may be
lower still"). 74/82 objects got lines. Template explains how to read
it. PROMPT_VERSION 7→8, full re-judge (3 calls; v7 backed up in the
session scratchpad).

**Headline: obj_023 FLIPPED BACK — rests_on floor 0.60** with the
textbook reason: "strongly disagreeing view depths indicate the lower
part was occluded; as standing furniture it must rest on the floor
despite the 20.6 cm computed gap, which is likely truncation." Starved-
judge hypothesis CONFIRMED: same model, same tiebreaker, one evidence
line = correct verdict. Also: AC stable (rests_on shelf 0.65 + wall alt
0.35) · plant obj_001 floor 0.55 ("likely an unlisted low stand") ·
BOTH doors now mounted_on wall · the book family systematically moved
rests_on → **inside** shelf compartments at HIGH confidence (0.8–0.9,
12 objects — the evidence lines saying "views agree" seem to have
emboldened cleaner verdicts) · anchors back to 30 · multi-option 8→13.

**Chain refreshed on v8** (obj_023 concern resolved, hold lifted):
- S2: 80 CONFIRMED / 9 ALT / **11 DROP / 4 KEEP** (10 fresh calls). The
  AC wall edge is now SUPPORT_ALT (kept — wall is a ranked alternate
  now, not ruled-against; the R9 drop correctly un-happened).
- PH1 snap (docket 7, +obj_127 door): obj_023 refit re-adopted 0.75 ·
  AC NO_SNAP again · door obj_127 NO_SNAP (tie preserved) · **⚠ CURTAIN
  FLIPPED TO DEFER_TO_SURGERY 0.55** — same evidence as R8's ADOPT 0.65,
  opposite verdict, and its reason MISREADS the judge flag (cites it as
  doubt against the refit when the flag says the box is oversized, i.e.
  FOR it). The R8 slim-curtain result you eyeballed is gone from the
  layer this run. Adjudication run-variance is now a DEMONSTRATED
  problem: snap has NO verdict cache (unlike every other judged module).
  LARGE list 16 → 12 (books absorbed into INSIDE_CONTAINER by the v8
  "inside" verdicts).
- S3: 0 deletes / 0 petitions · adds wardrobe 0.75 / blanket 0.8 /
  keyboard 0.7 / trash can 0.55 (5th run: mouse dropped out this time;
  keyboard ever-present).

**Look for (R10b):** (1) the v8 layer in the support view — esp. the
books-now-"inside" family: better or over-confident? (2) obj_023 floor +
refit — matches your pixels? (3) the curtain snap regression — the fix
direction is an adjudication CACHE keyed by evidence (verdicts persist
across runs like S1/S2 caches) + optionally seeding user-passed verdicts;
approve and it gets built. (4) AC: two-option verdict honest enough?

**Provisional verdict:** v8 = the right architecture lesson (feed the
judge, don't blame it) with a confirmed win on obj_023; the snap variance
is the new sore spot — cache before next run. **User verdict: pending
(R10b).**

---

### R11 · snap v1.2 — cache + rulings + reframed docket (08-02) — GATE OPEN

**What (the "agent or structural?" answer — structural, three fixes +
memory):** adjudication prompt v2 states the decision rule (the MAJORITY
matters; correction magnitude alone is NEVER a reason to defer; thin =
few total measurements or a split vote); the docket now says "k of n
per-view measurements AGREE" instead of "one outlier rejected"; judge
flags arrive with their direction stated ("this box is likely oversized
— SUPPORTS correcting it"). Plus the missing memory: **snap_cache.json**
(verdicts frozen to their evidence, like every other judged module) and
**snap_rulings.json** (hand-written user pins that outrank cache and
model; `--fresh` respects them).

**Test run (empty cache — a clean experiment on the reframing):**
- **Curtain: ADOPT_REFIT 0.85** (was DEFER 0.55) — reasoning now cites
  the flag CORRECTLY: "7 of 8 measurements agree, **corroborating** the
  prior flag that this box was oversized." Structural theory confirmed
  a second time: same model, reframed inputs, right answer, higher
  confidence than ever.
- obj_023 shelf: ADOPT 0.85 ("9 of 11 agree — strong majority").
- door obj_127: NO_SNAP 0.55 — nuanced: "refit is strong for box size,
  but support scores are close, snapping would bake in an uncertain
  choice." The menu semantics being used exactly as designed.
- **AC flipped to SNAP_AS_IS 0.6** (read 0.65-vs-0.35 as a "clear
  lead") — the close/clear boundary is still model judgment, and this
  would have baked in the bookshelf answer while the wall-vs-bookshelf
  eyeball is OPEN → **pinned NO_SNAP in snap_rulings.json** (first use
  of the mechanism; note says the pin stands until the user rules on
  the crops).
- Confirmation re-run: **1 user-ruled + 6 cached + 0 LLM calls** —
  byte-stable layer, variance dead.

**Final layer:** curtain slim (0.206 m) + flush; obj_023 refit + floor
snap; AC + door held; LARGE 12 (all knowns/dependents).

**Look for:** (1) slim curtain back in the snapped preview; (2) the AC
pin — happy with NO_SNAP-until-eyeball as its resting state?; (3) the
cached verdicts' reasons (all printed in the run log / snap.json) — any
you'd overrule, pin it in snap_rulings.json; (4) NEXT DESIGN (accepted
08-02, not yet built): the support-vocabulary rework — surface-based
menu (on_top / inside / mounted_on / hangs_from / embedded_in; leans_on
retired into on_top+against) killing the rests_on/inside and rests_on/
leans_on overlaps that let judges wander between synonyms with real
snap consequences.

**Provisional verdict:** PASS pending eyes — deterministic, correctly
reasoned, user-pinnable; the remaining docket variance (close/clear
attribution calls) is now containable by pins until the vocabulary
rework tightens it at the source. **User verdict: pending (R11).**

---

### R12 · the AC ground truth — v9 real-gap rule + S1 rulings mechanism (08-02) — CLOSED (user GT recorded)

**User ruling: the AC (obj_002) is WALL-MOUNTED — ground truth**, closing
the R6/R7 open wall-vs-bookshelf eyeball item.

**Autopsy of the wrong call (why the judge said bookshelf):** (1) the
appearance witness OVERCLAIMED — "bottom edge rests flat on top of a
wooden furniture surface" is a weight verb asserted from pixels that
cannot show weight or a 5 cm air gap; (2) the v6 doctrine makes
testimony king, so the claim broke the "tie" and disarmed the type
prior; (3) BENEATH_TOL's truncation generosity laundered the REAL gap
(3 agreeing un-clipped views put the AC bottom 5–10 cm ABOVE the shelf)
into "noise-scale". The decisive data was in the packet; the inference
rule wasn't.

**v9 REAL-GAP RULE tried first** (prompt: views AGREE → believe the gap;
witness verbs read as "appears adjacent"; gap forgiveness only for
untrusted bottoms): **did NOT flip the AC** (rests_on 0.5, reason calls
the 4.9 cm gap "the tightest numeric fit" while admitting near-tied) and
reshuffled the synonym families again (books inside↔rests_on both
directions; doors regressed to floor). LESSON: prompt-rule accretion has
hit its limit — three stacked rules now interact and churn; the vocab
redesign is the real fix for the churn, and GROUND TRUTH BELONGS IN THE
STATE, not in ever-fatter prompts.

**S1 RULINGS MECHANISM built** (`compose/supported_by_rulings.json`,
mirror of snap's): a user ruling becomes options[0] (by:"user"), the
judge's differing options demoted to audit alternates. obj_002 pinned
mounted_on arch_wall_z_high 0.95 with the autopsy note. Re-run: 82
cached + ruling applied = 0 calls. The obsolete snap NO_SNAP pin removed
(purpose served).

**Chain refreshed:** AC now snaps WALL_FLUSH (4.5 cm, small — off the
docket and off the LARGE list entirely); curtain + obj_023 verdicts
STABLE on re-ask (ADOPT 0.85 with correct flag reading — the v1.2
framing holds); LARGE 14 (books back in via the v9 rests_on churn —
vocab-redesign fodder); S3 6th run: keyboard 0.85 / mouse 0.75 /
blanket 0.6 / trash can 0.55.

**Standing state:** v9 layer + 1 user ruling. Known churn families
awaiting the accepted SURFACE VOCABULARY rework (on_top / inside /
mounted_on / hangs_from / embedded_in; leans_on retired): books
(inside↔rests_on), doors (mounted_on↔rests_on floor). Also queued from
the autopsy: witness-side fix — describe_nodes detail verbs should say
"appears adjacent/in contact", never weight verbs.

---

## PARKED — screening draft (earlier this session, now a later step)

Compose-or-skip per anchor (`COMPOSE` / `SKIP_ARCH` / `HOLD`), one batched call,
`anchor_cast.json` + review sheet. To be redesigned on top of support stories when
reached — its anchor input will come from story readings, not touch edges. Open
discussion points recorded 07-26G: what SKIP means for the composed scene's judge
comparison; HOLD's blast radius on dependents.
