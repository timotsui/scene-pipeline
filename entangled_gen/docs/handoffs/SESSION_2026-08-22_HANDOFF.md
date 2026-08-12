# SESSION 2026-08-22 HANDOFF — POLY SHELL LIVE END TO END; NEXT IS J9

## LATE ADDITION (2026-08-10): PRE-J9 UNATTENDED-RUN AUDIT (R-S2-65)

User directive: everything must survive a no-human 100-scene run.
Three parallel scans + fixes, all compiled, geometry suite 20/20:
- compose/ no longer crashes on migrated graphs (literal
  arch_wall_x_low lookups -> shared arch_walls.py helper; wall-slab
  axis now read from the node, not the id string).
- migrate_walls_w5 source bug fixed ("room_shell_poly" -> "envelope",
  live graph patched) — a rederive can no longer drop every IN_WALL.
- build_graph is polygon-native for fresh scenes; build_edges/rederive
  wall claims are segment-aware (tangent guard + connectors), verified
  read-only against the live graph (23/27 identical, diffs explained).
- room_shell.py default mode runs the polygon fit itself (fit failure
  = recorded polygon_error + v1 degradation).
- paths.py reconfigures stdout/stderr to utf-8 (print-crash class
  dead); --scene is required=True in 17 stage scripts.
- KNOWN-OPEN (recorded in R-S2-65): envelope placement legality is
  floor-points-only (no in-polygon mask yet); legacy fallback naming;
  experiments/ hygiene; cosmetic detector strings.

(Real date 2026-08-09, fourth session that day. REVIEW_LOG R-S2-62d..64.
Previous session's handoff was reconstructed as
SESSION_2026-08-21_HANDOFF.md — read that for the W4 build story.)

## THE HEADLINE

The polygonal room shell is ADOPTED and WIRED THROUGH EVERYTHING:
contract file, all five vote-stage consumers, the shipped boxes, and
the scene graph's architecture + wall edges. The graph is rebuilt
through `grouped` with every self-check passing.

**NEXT SESSION = THE J9 GATE, with a clean upstream.**
    out/living_marble/graph/same_product_sheets/index.html
(ceiling-light trim split + chair split; on-disk chair reason =
BACKREST SHAPE. Open since the FIFTH session. It blocks compose.)

## WHAT HAPPENED THIS SESSION (all user-ruled)

1. **W4 gate PASSED** ("the room boundary method should be used") —
   5-segment polygon, all measured, one diagonal connector closes the
   SW pocket.
2. **W5 wiring BUILT** (R-S2-63): polygon folded into room_shell.json
   (D3); slicevote's five shell consumers walk the segment list —
   a wall claims/clips only where the box footprint overlaps its
   extent. D1 = entirely-outside boxes ignored (recorded, never
   silent) with OUTSIDE_DROP_M 0.5 wall-zone guard (obj_034's glass
   door sits 0.149 m outside and MUST live). D2 = connector claimant
   gets no perp re-box. v1 4-plane path preserved when no polygon
   block exists.
3. **Executed the cheap way** (user: "for time sake", R-S2-64):
   - partial vote `--only obj_001,obj_018`: the door is now a real
     2.27 × 0.97 m box IN the pocket wall (was a 4 cm sliver dragged
     2.45 m); the light reproduced run-14's outcome (penalty elected
     the clean candidate, ratio guard rejected the 3× shrink, original
     ships — ballot/retry are STILL the open fix, R-S2-58/59).
   - snap: 44 other boxes re-clipped offline to the new walls; 7 moved
     2–34 mm; backups *.pre_w5_snap.bak.
   - wall migration (graph/migrate_walls_w5.py): arch_wall_00..04
     replace the v1 four; 67 IN_WALL edges re-pointed by geometry with
     an axis-keep tie margin; obj_034/obj_035's historic tie-order
     claim corrected to the east wall; nothing deleted, drift > 0.10 m
     caveated; backup scene_graph.json.pre_w5_walls.bak.
   - rebuild: build_voted → materialize --settle-only → materialize
     (grouped). Additive checks PASS, no old wall id survives anywhere.

## OPEN, IN THE ORDER I'D TAKE THEM

1. **J9 gate** (above). Geometry moved only mm since the sheets were
   built (obj_001/018 are not in the split cases) — the sheets stand.
2. **obj_018 ballot + retry design** (R-S2-58/59) — the light still
   ships its oversized prior; the elected-but-rejected small box rides
   the doubt rec for a future ballot.
3. **Card-race audit** (~100 cached-render replays certifying
   DET_EDGE_PENALTY can't shift any card vote; user-approved earlier).
4. Carried: culled-camera audit renders (await go); split-piece fixes;
   declip rotation; support_clip retirement; viewer may need a drawer
   for the CONNECTOR arch node (no axis-aligned plane).

## HONEST STATE

- Preview manifest: run_kind=partial + snap stamps; canon_eligible
  FALSE until a full vote re-run (user accepted the trade).
- bedroom_marble still has no polygon block (v1 behaviour until
  --poly is run there).
- Committed: NOTHING (four sessions). Uncommitted in scene-pipeline:
  room_shell.py, slicevote.py, graph/migrate_walls_w5.py (NEW),
  graph/view_cams.py, graph/node_views.py, viewer/serve.py,
  PIPELINE.md, pipeline_map.html, docs (REVIEW_LOG R-S2-57..64, both
  plan docs, three handoffs).
- Scratchpad (regenerable): test_w5_geometry.py (20/20),
  reclip_w5_snap.py.

## GOTCHAS THAT DECIDED THINGS

- "Completely outside" cannot mean "beyond a wall": an opening carries
  its whole mass past the plane (obj_034, 0.149 m out). The D1 drop
  needs the wall-zone distance guard, and it must run BEFORE the
  exemptions (a fully-outside box still pattern-matches wall-flush).
- Corner objects hold TWO wall edges that tie at d≈0; re-pointing by
  raw nearest-distance welds both onto one wall. The axis-keep margin
  (0.05 m) preserves the judged relationship while still letting a
  decisively closer cross-axis wall win as a correction.
- The pipeline frame flips x between raw and upright: v1 wall NAMES
  (x_low) are upright, EDGE values are raw — when migrating, trust the
  recorded plane VALUE, never the name's side.
- matplotlib's contour/DP quirks (W4) and the layer-builder chain
  (voted/settled/grouped are REBUILT, never hand-edited) both held up
  under this session's use.
