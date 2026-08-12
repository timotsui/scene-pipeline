# PLAN — room shell (measured world architecture: walls · ceiling · floor)

Canonical plan + progress doc, production-session workflow rules apply
(progress log updated on every state change; checkpoints are hard stops).

- Created: 2026-07-26 (late session, straight after the graph-record build)
- Current state: 🔴 W3 USER GATE OPEN (REVIEW_LOG R11) — W0/W1/W2 done
  same session; shell measured + in the record + drawn in the viewer
- Scene: bedroom_marble first

## 1. Purpose (plain language)

The scene-graph record's architecture nodes are currently placeholders:
the 4 wall planes are the 1st/99th percentile of splat point extent
(an axis-aligned bounding rectangle — never fitted, never verified), the
ceiling is a single inherited number, and `envelope.py` still reads the
RETIRED legacy manifest for floor/ceiling/extents. Meanwhile 29 IN_WALL
facts in the record are measured against those unverified planes.

This effort makes the world SHELL a measured, evidence-carrying part of
the record: wall planes (as N segments, not an assumed box), ceiling,
floor — each with fit evidence — plus the collider mesh as an independent
cross-check where a Marble bundle provides one.

Division of labor (user question answered 07-26): `room_shell` OWNS the
architecture measurement; `envelope.py` keeps the clearance/floor-warp/
placement-check role and gets REWIRED to read the shell (its legacy
manifest dependency dies there).

## 2. User decisions (2026-07-26)

- GO on the staged plan (W0 audit → W1 measure → W2 record → W3 viewer).
- Collider cross-check IN — user: "the collider mesh i am seeing is
  rather good." Still Marble-only: recorded as evidence, degrades to
  absent on other scenes, never a hard dependency (generality rule).
- **NOT strictly 6-sided:** anticipate rooms that are not a box. The
  shell is a set of wall SEGMENTS (fit planes with extents); a
  rectangular room is the N=4 special case, not the schema.

## 3. Steps

### W0 — audit (report only, no pipeline changes)
`room_shell.py --audit`: splat point density histograms perpendicular to
each current envelope bound (is there a wall-like density peak, and where
is it vs the p1/p99 placeholder?); ceiling/floor peaks from the y
histogram; a top-down occupancy boundary image (reveals non-box shape);
collider planar-patch extraction (face-normal clustering → large planes)
as the independent column. Out: `out/<scene>/room_shell_audit.json` +
plots. GATE: numbers reviewed before W1 fitting choices.

### W1 — measured shell (deterministic, scene-agnostic)
Fit the shell from the splat: free-space/occupancy boundary traced and
simplified to wall segments (N not fixed); per segment a plane fit from
nearby points with evidence (point count, residual, density peak
sharpness); ceiling plane measured; floor = envelope's warp map (kept).
Cross-checked against collider planes when present (recorded delta).
Out: `out/<scene>/room_shell.json` (the shell contract). envelope.py
rewired to consume it (legacy manifest read removed).

### W2 — record integration
build_graph.py: envelope placeholder nodes replaced by shell nodes
(arch_wall_00..NN with measured planes + evidence, arch_ceiling,
arch_floor + warp summary). build_edges.py: IN_WALL recomputed against
measured segments + gains the node's projected on-wall footprint (u-v
rect) — windows/doors become recorded wall regions.

### W3 — viewer layer · USER GATE
Translucent clickable wall/ceiling quads from the shell, card with fit
evidence + attached openings; user judges against the splat (and against
the collider layer they already trust).

### W4 — polygonal shell v2: TRACE → CLOSE → MERGE (user design 2026-08-09, NOT built)
The v1 fitter picks one wall per axis side — a 4-wall box room. That
assumption crushed obj_001 (a door entirely beyond the ZLO plane, in an
unmodeled pocket, dragged onto a wall it never touched and clipped to a
4 cm sliver) and cannot represent this scene's real outline (the x_high
wall runs past the z_low wall; living_marble audit 2026-08-09: x_low /
z_low density peaks sit 0.5–1.7 m BEYOND the fitted v1 walls, widths
0.76 / 0.91 m — spread material, not one sheet). The schema is already a
list of segments; only the fitter and its consumers change.

**The algorithm (user's rule, three passes in this order):**
1. **TRACE what you can.** Follow the wall material in the top-down
   occupancy map wherever it is dense enough to trust. Output: an open
   polyline of measured segments, each with evidence (point count,
   residual, peak sharpness) — same evidence style as v1 planes.
2. **CLOSE the polygon.** Bridge every gap with an added segment so the
   outline is a closed loop and "inside" is defined everywhere. Added
   segments are MARKED inferred, never measured — record-then-judge; a
   box assigned to an inferred segment is a weaker claim and downstream
   must be able to see that.
3. **MERGE similar planes.** Collapse near-collinear neighbours into one
   segment. CARDINAL SNAP is a special case of the merge: a segment
   within tolerance of an axis merges onto the axis direction, position
   set by the density spike. What cannot snap survives as a CONNECTOR
   at its measured angle; connector ENDPOINTS absorb all closure error
   (walls never move to make the loop close). Topology first, then
   geometry.
The order is load-bearing: trace before close (never invent where you
could measure), close before merge (merging an open polyline can weld
across a genuine doorway gap that close should have bridged explicitly).

**Mesh role (user 2026-08-09): VALIDATION ONLY.** The collider stays
what it is in v1 — an independent second opinion recorded as deltas,
never a source the fit depends on (Marble-only asset; the fit must work
without it).

**Consumer changes (all in the vote stage's wall handling + shell_clip):**
wall assignment walks the segment list instead of 4 planes; the clip
cuts against the traced outline; the perp re-box camera aims at the
claiming segment's normal. Cardinal walls stay exact axis-aligned
planes so existing box math survives; boxes assigned to a cardinal wall
clip exactly as today. An angled connector defines interior only; if a
box is ever assigned to a connector, keep the axis-aligned box that
fits inside (conservative, never wrong-side-of-the-wall). Arbitrary-
angle WALLS stay out of scope — every box in the graph is axis-aligned
and compose snaps to a 2 cm lattice; the connectors are the only
non-cardinal geometry.

### W5 — consumer wiring (PLANNED 2026-08-09 4th session; awaiting go)

**Where the box-room assumption lives (audited):** slicevote.py builds
`XLO/XHI/ZLO/ZHI` + the 4-row `WALLS` table from room_shell.json at
load (lines ~625–637); five consumers feed off it:
1. `wall_protrusion()` — the wall-exemption test (4 infinite planes)
2. `shell_clip()` — the shipping clip (axis-aligned box intersect)
3. `in_bounds()` — camera-eye sanity (rectangle test)
4. the shell ELECTORATE filter — dot eligibility (6 half-spaces, ~2061)
5. `perp_for_exempt()` — plane row (axis, value, side, id) per wall
Everything else (build_graph/build_edges/envelope) reads room_shell.json
v1 directly and is OUT OF W5 SCOPE (record integration = W6, later).

**D3 — contract file (USER RULED 2026-08-09):** `room_shell.py` default mode gains the
polygon: a `"polygon"` block (clean_polygon: vertices + 5 segments,
converted to RAW frame alongside upright) written INTO room_shell.json.
room_shell_poly.json stays a review artifact. One shell contract file;
consumers never read the review artifact. Fallback: no polygon block →
current 4-plane behaviour, byte-identical (bedroom_marble unaffected
until re-run).

**The five edits (slicevote.py only):**
1. **wall_protrusion → segment walk.** Test against each CARDINAL
   segment: touch/protrude vs its plane exactly as today, but only
   where the box footprint OVERLAPS the segment's endpoint extent
   (+ WALL_TOUCH slack) — a wall elsewhere in the outline can no longer
   claim a distant box (the obj_001 disease). Connector segments: same
   overlap test against the connector's line; a connector-claimed box
   is exempt with the connector as claimant (see D2).
2. **shell_clip → local per-segment clip.** For each cardinal segment
   whose extent overlaps the box footprint, clip against its half-plane
   (today's behaviour, made local). Connector overlap: clip to the
   largest axis-aligned box inside the connector's half-plane
   (conservative, per §W4). Floor/ceiling unchanged. NO clip for
   beyond-shell boxes (D1).
3. **in_bounds → point-in-polygon** (2D ray-cast on the RAW-frame
   vertices, inset WALL_PAD) + the y band as today.
4. **Electorate filter → signed inside-the-polygon by > SHELL_EPS**
   (vectorized point-in-polygon + distance to the outline) + the y
   half-spaces as today. Census print unchanged.
5. **perp plane rows** — cardinal claimant: unchanged path (axis,
   plane, side from the segment). Connector claimant: per D2.

**D1 — beyond the shell (USER RULED 2026-08-09 4th session): treat as
before; COMPLETELY outside = IGNORED.** A box that touches or crosses
the outline behaves exactly as today (wall exemption if it qualifies,
local shell clip). A box whose footprint sits ENTIRELY outside the
polygon is ignored: excluded from shipping, recorded as
`dropped_outside_shell` with the evidence (never silent). Measured
fact that de-fanged the decision: with the final 5-segment polygon
obj_001's door is 55% INSIDE (center inside), a 6 cm overhang past the
east wall — an ordinary wall-protrusion exemption (0.077 m) on the
pocket-side wall; the R-S2-62 corner-outside note was against the
intermediate polygon.

**D2 — connector-claimed boxes (USER RULED 2026-08-09): NO perp
re-box.** Exempt `kept_wall` with the connector as claimant, resolved
box kept, rec says "connector claimant — no face-on camera" (the perp
machinery is axis-aligned; connectors are the only non-cardinal
geometry and stay that way). Revisit only if a real scene shows drift
on a connector.

**Verify:** re-run the vote on living_marble; obj_001 must ship
verbatim + flagged; the 22 recorded top races and obj_018/obj_034
replays must be unaffected (no detector inputs change); diff every
shipped box vs run 17 and account for each change (expected movers:
wall-exempt boxes near the pocket + anything previously clipped to a
wall it never touched).

## 4. Progress log

| # | Step | Status | Artifacts / notes | Updated |
|---|---|---|---|---|
| W0 | audit | **DONE — findings below** | `room_shell.py --audit` → `out/bedroom_marble/room_shell_audit.json` + `.png` | 2026-07-26 |
| W1 | measured shell | **DONE** | user rulings: vertical-prism assumption GO; "clean and workable" scope; BOTH plane tiers recorded. `room_shell.py` (default mode) → `room_shell.json`: floor 0.000 / ceiling +2.764 (upright), 4 wall segments — x_low −2.430 (collider Δ7mm) · x_high +1.908 (Δ36mm) · z_low −0.927 (Δ27mm) · z_high +4.191 (Δ5mm) — each with 3–5 parallel surfaces (≤0.6 m, top-5; curtain plane +1.51/+1.61 and the z_low visible face −0.726 captured). `envelope.py` REWIRED: reads the shell (legacy p1/p99 read = fallback only); rerun → floor warp tightened to ±0.03 m | 2026-07-26 |
| W2 | record integration | **DONE** | `build_graph.py`: architecture nodes from the shell when present (measured planes + evidence + parallel surfaces; grid-bounds fallback kept); `build_edges.py`: wall lookup id-agnostic (N segments OK), IN_WALL edges gain on-wall footprints (tangent + y intervals, raw); rerun: IN_WALL 29→32 against measured planes, self-check PASS | 2026-07-26 |
| W3 | viewer + **USER GATE (open)** | **BUILT** | architecture nodes drawn as thin gray clickable slabs in the "graph record" layer (walls from plane+extent, floor/ceiling spanning the wall rectangle), new "architecture" sub-toggle; card shows plane value, fit points, collider agreement Δ, parallel surfaces; clicking a wall tints all its IN_WALL neighbors. REVIEW: R11 in REVIEW_LOG.md | 2026-07-26 |
| W5b | executed (user: no full re-run, for time) | **DONE 2026-08-09 (4th session)** | partial vote obj_001+obj_018 (door reboxed 2.27×0.97 at the pocket wall; light = run-14 outcome, ballot/retry still open) + snap of the other 44 boxes (7 moved 2–34 mm) + graph wall migration (graph/migrate_walls_w5.py: arch_wall_00..04, 67 IN_WALL edges re-pointed, axis-keep margin, zero dupes) + rebuild voted→settled→grouped (all self-checks PASS). D1 hardened: OUTSIDE_DROP_M 0.5 (obj_034 wall-zone case). Manifest = partial+snap, canon_eligible false until a full re-run. R-S2-64 | 2026-08-09 |
| W5 | consumer wiring | **BUILT 2026-08-09 (4th session)** | D1/D2/D3 user-ruled (see §3-W5). room_shell.py: polygon folded into room_shell.json (5 segments, raw-frame planes + interior sides + connector normal precomputed); v1 rewrite warns when it drops the block. slicevote.py: all five consumers polygon-aware behind `POLY is not None` (segment-walk wall claim with tangent-overlap guard, local shell clip + largest-inside-box connector cut, point-in-polygon in_bounds + electorate, D2 connector claimant = no perp, D1 fully-outside = dropped_outside_shell row, never shipped, never silent). 17/17 offline checks pass (scratchpad test_w5_geometry.py: obj_001 claimed by the pocket wall at 0.077 m, z NOT dragged; _pip vs matplotlib on 5000 pts; v1 fallback reproduces the old behaviour). REVIEW_LOG R-S2-63. NOT re-run: the graph/manifest still carry run-17 boxes | 2026-08-09 |
| W4 | polygonal shell v2 (trace→close→merge) | **USER GATE PASSED 2026-08-09** ("the room boundary method should be used") after two iteration rulings: 2 m bar unified to connector CHAINS, then ONE SEGMENT PER CHAIN → final 5 segments, all measured (R-S2-62b/c). NEXT: consumer wiring (W5 below). Build notes: | `room_shell.py --poly` → `out/<scene>/room_shell_poly.json` + `.png` (NO consumers). living_marble: 9 segments, 8 measured / 1 inferred — rectangle + the SW pocket with its angled connectors. Four rules earned on failures: band-density solid (dense Marble ceiling defeats reaches-ceiling), tall rule 1.4 m (sofa dent), floor rule OUTSIDE the box only (window band vs pocket; inside, furniture shadows the floor), min wall group 2.0 m (user: wall_04 was a shelf — furniture faces are not walls). Moore boundary trace (plt.contour fragments). OPEN nits: shelf corner = chamfer vs square; west wall split into 2 records on one plane; obj_001's corner still outside the polygon | 2026-08-09 |

### W0 findings (bedroom_marble, 2026-07-26; positions UPRIGHT)

- **Placeholders are wrong, as suspected:** real density peaks sit INSIDE
  the p1/p99 box by 0.02–0.40 m (x_low worst: peak −2.052 vs bound
  −2.457).
- **Floor/ceiling are fine:** splat peaks 0.000 / +2.764; collider says
  −0.015 / +2.768 (agreement ≤ 4 mm splat↔collider); the frame values are
  within 3 cm. No action needed beyond recording the measured values.
- **Splat and collider AGREE on visible wall surfaces** — x_high: splat
  +1.802 vs collider +1.803 (!); z_high: +4.20 vs +4.186; x_low: −2.052
  vs −2.022; z_low: −0.727 sharp splat peak, collider strongest at −0.794.
- **The room is NOT a 4-plane box** (user's anticipation confirmed):
  the collider shows MULTIPLE parallel planes per side — x: {+1.803,
  +1.944} and {−2.022, −2.423}; z_low: {−0.634, −0.794, −0.954}; z_high:
  {+4.046, +4.186}. Reading: visible-surface planes (wardrobe fronts /
  curtain planes / alcove faces) sit 0.1–0.4 m inside the outer
  structural planes. Splat peaks track the VISIBLE surfaces (that is
  what cameras see). Oblique (non-axis) collider area: 16.9 of 93 m².
- **W1 gate question (user):** what is "the wall" for the shell — the
  OUTER structural plane (collider outermost, e.g. x −2.423/+1.944,
  z −0.954/+4.186), the VISIBLE surface plane (splat peaks), or BOTH
  recorded (outer = shell, inner parallels = sub-shell features per
  side)? Recommendation: BOTH — record-then-judge says record
  faithfully; placement cares about visible surfaces, architecture
  cares about structure.

## 5. Resume protocol

Read this doc fully → verify artifacts on disk → continue from the first
non-done row → never skip an unpassed gate.
