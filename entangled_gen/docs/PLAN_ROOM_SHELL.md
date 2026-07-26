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

## 4. Progress log

| # | Step | Status | Artifacts / notes | Updated |
|---|---|---|---|---|
| W0 | audit | **DONE — findings below** | `room_shell.py --audit` → `out/bedroom_marble/room_shell_audit.json` + `.png` | 2026-07-26 |
| W1 | measured shell | **DONE** | user rulings: vertical-prism assumption GO; "clean and workable" scope; BOTH plane tiers recorded. `room_shell.py` (default mode) → `room_shell.json`: floor 0.000 / ceiling +2.764 (upright), 4 wall segments — x_low −2.430 (collider Δ7mm) · x_high +1.908 (Δ36mm) · z_low −0.927 (Δ27mm) · z_high +4.191 (Δ5mm) — each with 3–5 parallel surfaces (≤0.6 m, top-5; curtain plane +1.51/+1.61 and the z_low visible face −0.726 captured). `envelope.py` REWIRED: reads the shell (legacy p1/p99 read = fallback only); rerun → floor warp tightened to ±0.03 m | 2026-07-26 |
| W2 | record integration | **DONE** | `build_graph.py`: architecture nodes from the shell when present (measured planes + evidence + parallel surfaces; grid-bounds fallback kept); `build_edges.py`: wall lookup id-agnostic (N segments OK), IN_WALL edges gain on-wall footprints (tangent + y intervals, raw); rerun: IN_WALL 29→32 against measured planes, self-check PASS | 2026-07-26 |
| W3 | viewer + **USER GATE (open)** | **BUILT** | architecture nodes drawn as thin gray clickable slabs in the "graph record" layer (walls from plane+extent, floor/ceiling spanning the wall rectangle), new "architecture" sub-toggle; card shows plane value, fit points, collider agreement Δ, parallel surfaces; clicking a wall tints all its IN_WALL neighbors. REVIEW: R11 in REVIEW_LOG.md | 2026-07-26 |

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
