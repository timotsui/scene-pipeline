# PLAN — SHOPPING MODULE (started 2026-08-02/03)

## What this module is (user design, this session)

Shopping produces **ordered asset candidates for each object box** in the
scene state. It does NOT pick-and-place-and-verify — that is the FIT LOOP,
the next module, which walks each item's candidate list until one fits.

**Order of battle (user ruling):** ANCHOR objects first (things standing
on the floor / mounted on walls or ceiling) to limit the search tree.
Anchors run until fit. Then, per fitted anchor, its sub-objects (things
on/in it) get shopped and fitted against the REAL mesh (books need real
shelf boards; the pillow lands on the actual mattress).

## Rulings that shaped this design (2026-08-02 late session)

1. **Sandbox ruling:** the original scene's job ended at extraction. The
   layout is ours now. NO truth gate — proposals are not checked against
   the original pixels for existence. The room photos survive only as a
   STYLE guide (used when choosing between candidates, later).
2. **Screening is dissolved** — there is no separate filter module. The
   "filter" is shopping's list-writing step: an item that has no match
   in the asset library simply is not bought (door handle: no such
   category → the door asset covers it). The filter question is about
   OUR LIBRARY vs the proposal — never about the original scene.
3. **"Comes with" checks parked:** whether beds come pre-dressed etc.
   (readable from candidate descriptions/thumbnails) is deferred until
   real double-blanket problems appear. The fit loop is the safety net.
4. Every boxed add + both feasible swaps enter the list (no entry gate).
   Swapped-out detections are not shopped; swap-ins are.
5. Stretching policy (uniform vs fill-the-box) belongs to the fit loop.
6. Style-based picking = later, at pick time, with room photos as mood
   reference. Not in v1 candidates.

## Module contract

- **Gets:** scene_graph.json[resolved] (real objects, boxes verbatim) +
  edit_proposals.json (adds with boxes, feasible swaps) +
  supported_by.json (who is an anchor, who sits on whom).
- **Decides:** for each ANCHOR-tier item — the ordered candidate list
  from the objathor library (category match tiers + orientation-aware
  size fit + mount filter), or an honest NO_MATCH record. Sub-objects
  are LISTED but deferred (tier: sub, with their anchor named).
- **A mistake looks like:** an item silently missing from the list, a
  wall item offered floor-only assets, or candidates that cannot
  possibly fit the box.

## Anchor / sub classification

- Real object: top supported_by option's supporter starts with `arch_`
  → anchor. Otherwise sub, grouped under its supporter's anchor.
- Add: support `floor`/`wall`/`ceiling` → anchor; `on:obj_X` → sub of X.
- Swap-in: inherits the first swapped-out item's tier; children of
  swapped-out items re-hang on the first swap-in (the loop already
  records out_children).

## Steps + progress

| # | step | state |
|---|------|-------|
| 1 | shopping.py: list + classify + category match + shortlists (pure code except the existing one-batch unmatched-label mapper) → compose/shopping.json | DONE 08-02C (a9fad3e) — 32/32 anchors, 63 subs deferred |
| 2 | review artifacts: contact sheets (AFK) + review_server.py --shopping viewer (:8322) | DONE 08-02C |
| 3 | user review of list + candidates | contact sheets + test fit sent; verdict pending |
| 4 | pipeline map redraw: screening box dissolves into shopping (user approved) | DONE 08-02C (4b951b6) |
| 5 | fit_preview.py: #1 candidates naively placed → compose/fitted_preview.glb, served as the viewer's "fitted preview" HUD layer (user: part of the output process; re-run after every shopping run) | DONE 08-02C |
| 6 | fit loop = NEXT MODULE (not here) | — |
| 7 | pick.py: STYLE joins the pick (user 08-03: "look and feel is just as important"). Shopping's size-fit order kept VERBATIM; style judge ranks the top 8 per item; output = SEPARATE style ranking in picks.json (user: no blend yet -- combine policy OPEN) | first run DONE 08-03B: 8 calls / 217 s / 31 items judged; viewer :8322 shows style strip + per-item judge rows |
| 7a | JUDGE MODE RULING (user 08-03B): IMAGE judge is CANON -- catalog descriptions are honest-but-gestalt-blind (the barn-door case: "wooden door with two metal hinges" = a crazy barn door) and cannot be the comparison basis; descriptions stay as captions only. TEXT+MOOD experiment archived (scratchpad text_style_results.json / text_mood_results.json): text-only 87 s 18/31 top-1 agreement; +1-call mood paragraph (10 s, caught the purple yoga mat) fixed the invented-item blind spot (shifts 3.5->0.75) at 88 s total. Revisit ONLY if per-scene call cost becomes the bottleneck; re-captioning the catalog thumbnails = the blueprint then | ruled |
| 7b | SHEETS v2 (user 08-03B: "same problem as mega panels -- make sure the agent can distinguish one tile from another"): dark TILE_GAP bars WITHIN rows (flush white thumbs bled), one-tile-one-product prompt language, per-item row_<id>.png saved and shown inline in :8322 ("what the judge saw"). PROMPT_VERSION 1->2 => pick_cache invalidated BY DESIGN: next live run re-judges all 31 on the v2 sheets | sheets rebuilt zero-call; re-judge awaiting user go |
| 7c | FINAL OUTPUT RULING (user 08-03B: "k=3 candidates for each object box"): the shopping process ENDS at final_candidates = the STYLE judge's top 3 per box (fit top-3 fallback when unjudged); fit order + style order both kept for audit, NOT blended (combine policy still open — "maybe a combined score later"). pick.py writes it; existing picks.json patched in place (31/31); viewer blue bar marks the kept 3; MAP MADE CANON (S4 node = SHOPPING + STYLE PICK · k=3, s2/s3 cards updated) | ruled + wired |
| 7d | STAGE BOUNDARY REDRAW (user 08-03B: "the fit loop should be part of the physical stage"): with k=3 the WHAT decision is upstream — the fit loop's real work is mesh placement. Map redrawn: 3.1 SEMANTIC ends at S4; picks.json k=3 = the SEMANTIC→PHYSICAL HANDOFF BATON; fit loop = PH2 in the 3.2 band (collide → PH3, surgery → PH4) | canon |
| 8 | ORIENTATION: user ruling 08-03 late — does NOT join the pick, becomes its OWN SEPARATE STEP later. Prototype finding (code removed, uncommitted): re-searching perm x tiling with an orientation term (ORIENT_W=0.3 x (1 - reachable-front dot), footprint-legal yaws per place_candidate's rule) resolved ALL 4 declared face_conflicts on bedroom_marble (reach >= 0.92 on all 31 picks; chair/rug/mat traded a slightly worse fit for a reachable perm). Rebuild from this note when that step comes | parked |

## USER RULING 08-03 (end of day): orientation LAST PASS

Per-category evidence rules (pillow marks the bed head) do NOT scale
— "we can't do this for every one." The rulebook below stays as the
cheap geometric first draft (decides 26/30 on this room for free);
the FIT LOOP adds a final judged ORIENTATION PASS that starts from
these decisions + the declared face_conflict records and visually
corrects the remainder. Do not add more category rules.

## Facing rulebook (v6, 08-03) + generalization watch-list

Evidence ladder (all geometry except tier 4): wall-mounted → thin-axis
wall normal · wall-hugging → same, among qualifying walls · subs →
inherit host front (host chain) · free-standing → witness observation
(line-of-sight converted; ±45° quantized) · invented/no-front →
near-wall/room-middle guess. Raw witness readings always recorded
(viewer whiskers) — geometry outranks, never erases.

**Scene-calibration watch-list (checked 08-03, user asked "did we
hardcode anything non-generalizable" — no IDs/scene names anywhere,
but three constants):**
1. ⚠ wall-hug edge gap 0.30 m — the VALUE was calibrated on
   bedroom_marble (true huggers ≤0.23, next walls 0.37+). RE-TEST ON
   SCENE #2; if it wobbles, derive per scene from the snap layer's
   measured box-error statistics instead of a constant.
2. thin-axis ratio 1.3 (shape-based, low risk).
3. near-wall heuristic distance 0.6 m (guesses only, lowest stakes).

## Donor code (reuse, do not rewrite)

- composition/retrieve2.py: match_categories (tiered), shortlist_box
  (fit score: aspect residual + |log scale| + upright penalty + tiling),
  map_labels_agent (one batched call for lift-noise labels), mount
  filter (_mount_ok: onWall/onFloor flags).
- composition/thumbs.py: dataset-level thumbnail cache
  (<OBJATHOR>/_thumbs/, 895 cached).
- composition/measure.py cache: 755 measured mesh sizes override the
  (partly lying) annotation sizes.
- docs/S4_SHOPPING_DESIGN_NOTES.md: mined contracts + 17 open
  questions from the old C1–C5 composition experiments.
