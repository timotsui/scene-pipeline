# SESSION 2026-08-21 HANDOFF — POLY SHELL BUILT + USER-PASSED; WIRE THE CONSUMERS

(Real date 2026-08-09, third session that day. RECONSTRUCTED: the
session was closed accidentally before a handoff was written; this file
was rebuilt next session from REVIEW_LOG R-S2-60..62c +
PLAN_ROOM_SHELL.md, both of which WERE saved before the close. The
gate pass in §1 was given verbally at the START of the next session.)

## 1. THE HEADLINE — the room boundary method is SETTLED and PASSED

`room_shell.py --poly` (W4 polygonal shell) is the adopted room
boundary method. **User gate PASSED** (user, 2026-08-09 next-session
opener: "the room boundary method should be used. yes.").

Final recipe (R-S2-62c):
**trace → close → merge to majority planes → 2 m architectural bar
(wall groups AND connector chains) → one segment per chain.**

Result on living_marble: **5 segments, 5 measured / 0 inferred** —
west 12.3 m, north 5.3, east 9.0, south 4.3, one 3.4 m diagonal
connector closing the SW pocket (ink 0.76). The user's original design
statement realized: snap cardinal where possible, one arbitrary
connective piece adjusts to fit.

    out/living_marble/room_shell_poly.json   (the shell contract, poly form)
    out/living_marble/room_shell_poly.png    (overlay the user judged)

The four rules, each bought with a visible failure this scene
(R-S2-62): (1) solid = dense WALL-BAND material, not v1's
reaches-the-ceiling (dense Marble ceiling defeated it); (2) TALL rule
1.4 m (sofa dent); (3) FLOOR rule OUTSIDE the box only (window band vs
pocket; inside, furniture shadows the floor); (4) MIN WALL GROUP 2.0 m
(wall_04 was a shelf). Iteration rulings: 2 m bar unified to connector
CHAINS (R-S2-62b, killed the shelf chamfer, kept the pocket ramp),
then one-segment-per-chain (R-S2-62c).

## 2. ALSO THIS SESSION (earlier)

- **R-S2-60 — obj_018 scoring fix LANDED:** DET_EDGE_PENALTY 0.7 → 0.1
  in slicevote.py, verified by replaying every recorded race (22
  top-view winners unflippable in [0, 0.7]; obj_018 perp flips to the
  clean small light at ≤0.13; obj_034 replayed — neither candidate
  edge-touched, fix can't regress it). Honest caveat on record: edge
  flag is a PROXY, not principled; ballot + retry still undesigned.
  NOT re-run — the graph still carries run-17's obj_018 box.
- **Cone map grew the evidence view:** all 22 top-view races now have
  score tables + all-candidates images (vote_obj_XXX_top_cands.png),
  via regenerable scratchpad scripts.
- **R-S2-61 — obj_001 door:** first full casualty of the box-room
  assumption (box entirely beyond ZLO dragged onto the wall and
  clipped to a 4 cm sliver; no single step wrong, the gap is
  compositional). This is what triggered the W4 design and build.

## 3. OPEN, IN THE ORDER I'D TAKE THEM

1. **Wire the poly-shell consumers** (PLAN_ROOM_SHELL.md §3-W4, now
   unblocked by the gate pass): vote-stage wall assignment walks the
   segment list instead of 4 planes; shell_clip cuts against the
   traced outline; perp re-box cameras aim per claiming segment's
   normal. Cardinal walls stay exact axis-aligned planes (existing box
   math survives); a box assigned to a connector keeps the
   axis-aligned box that fits inside. Decide "beyond the shell"
   handling here — obj_001's door corner is OUTSIDE the polygon and
   that is a consumer decision, not a tracing one (R-S2-62 nit c).
2. **Card-race audit** (~100 cached-render replay detections to
   certify DET_EDGE_PENALTY can't shift any card vote; user-approved,
   deferred behind obj_001 → now behind the wiring).
3. **The J9 gate — blocks compose, SIXTH+ session open:**
   out/living_marble/graph/same_product_sheets/index.html.
4. obj_018 ballot + retry design (R-S2-58/59); culled-camera audit
   renders (await go); carried split-piece/declip/support_clip items.

## 4. WHAT IS ON DISK

Committed: NOTHING (three sessions running). Uncommitted in
scene-pipeline: room_shell.py (--poly mode, this session),
PLAN_ROOM_SHELL.md (§3-W4 + W4 row), REVIEW_LOG.md (R-S2-60..62c),
slicevote.py (DET_EDGE_PENALTY + det_choice caching), view_cams.py,
node_views.py, serve.py, PIPELINE.md, pipeline_map.html, handoffs.

Data (out/living_marble/): room_shell_poly.json/.png,
room_shell_audit.json/.png (first living_marble audit), the 22
vote_obj_XXX_top_cands.png + tables in cone_map.html, obj_034/obj_038
perp replay artifacts.

## 5. GOTCHAS THAT DECIDED THINGS

- v1's hidden assumption: "solid = reaches the ceiling" only worked
  because bedroom's ceiling splat was thin. Band-density is the
  scene-agnostic reading.
- plt.contour fragments a jagged mask — Moore-neighbour trace instead;
  plain Douglas-Peucker degenerates on a closed loop — closed-loop DP.
- Furniture faces are not walls: anything cardinal under 2 m of traced
  length total is furniture against architecture.
- Topology first, then geometry: connectors keep their measured angle;
  their ENDPOINTS absorb all closure error — walls never move.
