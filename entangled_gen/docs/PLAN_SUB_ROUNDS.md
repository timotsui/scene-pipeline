# PLAN — SUB ROUNDS (the 64 deferred subs; started 2026-08-05C)

## CANON 2026-08-05C — SUPPORT RECURSION (user: "this seems like a
## loop... technically we can keep looping for sub sub objects")

**SR0 — SUB ROUNDS = THE FIT LOOP, ONE SUPPORT LEVEL DOWN.** Not a
new stage: re-enter PH2 with re-bound parameters — level-N fitted
meshes' support surfaces become level-N+1's shell, deferred subs
become the items. Recurse until no level has deferred items (the
data already carries depth: plant obj_003 → host basket obj_012 →
anchor shelf obj_022). A sub whose host is not yet fitted DEFERS to
the next level — hosts before riders, the anchors-first ruling
applied recursively.

Level-N parameterization, each gate-ratified on obj_043 (8 subs):

- **SR1 — SEED IN THE FITTED FRAME.** The search starts at the
  observed anchor→sub offset re-expressed on the anchor's fitted
  pose (declip + snap folded in; applied spins rotate offsets about
  the anchor center). Frame law: fit_box is RAW, declip_move_m is
  RENDER, the GLB is the placed truth.
- **SR2 — SURFACES FROM THE FITTED MESH.** "Floor" generalizes to
  board extraction: upward faces (normal_y > 0.65), height-clustered
  (gap 35 mm), small patches dropped; a board = height + footprint
  rect + headroom. No usable surface → the sub records NO_BOARD and
  is skipped honestly, never forced.
- **SR3 — NEAREST-BOARD ASSIGNMENT + CLAMP.** Bottom snapped to the
  nearest board by seed bottom; footprint clamped inside the board
  rect; too-tall/too-wide FLAGGED, not resolved.
- **SR3b — ATTACHMENT-CLASS GATE (08-05C, the window-on-curtain-fold
  case):** before board assignment, classify the sub from its OWN
  evidence — a sub whose box sits IN A WALL (thin axis = wall
  normal, center within 0.12 m of the plane) is arch-class, NOT a
  board rider: route to the wall channel (observed box = the correct
  placement, the relation router put it there), skip boards. Wall
  channel itself = unwired (same gap as rung 3). LESSON: test the
  OBSERVED box, not the seed — attachment class is a property of the
  observation; the curtain's −0.13 z wall-flush dragged the seeded
  window 1 cm past the threshold.
- **SR4 — RETRIEVAL EFFORT FOLLOWS ERROR COST.** Same shortlist
  machinery as anchors; subs default CHEAP BY CLASS (top-1
  category+size, no judge), weak matches flagged for a later judged
  pass. The style-judged k=3 remains the anchor-tier mode.
  **SR4b — HOST COVERS IT (08-05C, the door-handle case):** a sub
  whose matched category IS its own host's category is a PART of the
  host — the host asset already includes it; drop with HOST_COVERS,
  never buy. (Killed 3 "door handle"→whole-door buys; spared
  monitor-on-desk and picture-on-shelf, whose host categories
  differ. Blanket tier-0-only was considered and REJECTED on data —
  it would have killed those two correct tier-1 matches.)
  **SR4b-v — HOST_COVERS VERIFICATION LADDER (user 08-05C: "how do
  we determine if something is already on the host"):** rung 1
  (WIRED, code-only): the host's PLACED asset's catalog description
  — the part word appearing = verified ("door with silver handle";
  positive mentions trustworthy, SILENCE IS NOT ABSENCE, the
  descriptions-are-gestalt-blind lesson) → all 3 handle firings
  verified_text. Rung 2 (QUEUED): silent description → UNVERIFIED
  flag → one-look judge on the host's thumbnail, cached per
  uid × part — the generalized comes-with check (bed→blanket case:
  obj_008's bed description says "green blanket", so the blanket
  add's NO_MATCH drop was accidentally right). Rung 3 (OPEN): part
  verified MISSING → the sub is a FACE-MOUNT placement problem on
  the host's vertical surface — attachment class not yet built.
  **SR4b-v2 — RUNG 2 WIRED (08-05C):** silent description → ONE
  thumbnail look ("does this asset VISUALLY INCLUDE a <part>?"),
  sonnet, cached per uid × part (host_covers_cache.json), fully
  autonomous — NO user pins (prime directive). First firing: the
  curtain asset judged includes=false HIGH for "window" ("only
  curtain fabric and a rod/valance") → the window stays a LIVE
  WALL_CHANNEL need, not host-covered. Category-equal + judge-false
  → HOST_LACKS_PART + NO_MATCH (library gap, still no buy).
  **SR4d — SUB BRINGS HOST (08-05C, "White window ... and green
  curtain"):** a candidate whose description mentions the HOST's
  category would duplicate the host — prefer clean candidates; if
  every candidate brings it, keep the list + SUB_BRINGS_HOST flag.
  **SR4c — DRY LIST = ANCHOR RULE 9, SAME LOOP (user: "our goal is
  to use the same loop"):** the shortlist runners ARE the walk; best
  of the WHOLE shortlist over DRY (0.65, the anchors' constant) →
  the list is dry → adds drop entirely, detections drop with a
  recorded complaint (no re-shop exists at sub tier — the cheap path
  already searched the full category pool; the complaint = a
  library-gap record for the judged pass). First firing: obj_059
  "small glass decorative", best 0.931 — honest gap, recorded.
- **SR5 — THE ALIGN TRICK.** At asset load: OBB axes snapped to the
  nearest world axes (minimal rotation) — fixes baked roll/pitch
  lean the yaw-only PCA cannot. Known ambiguity at ~45°; tiebreak-
  by-box-aspect is the queued fix if it bites.
- **SR6 — ALIGN BEFORE SHOP.** Fit scores and k multipliers are
  computed on the ALIGNED AABB (measured once per uid, cached in
  aligned_size_cache.json — the seed of a catalog column). Proven:
  4/8 picks changed on obj_043; the worst leaner dropped everywhere.
- **SR8 — SUB-JIGGLE = PER-BOARD 1D LEGALIZATION (08-05C late).**
  fit_declip re-bound: per board, sort along the long axis, two-pass
  interval sweep (push-right then pull-back), short axis clamps into
  the board depth; y locked, 5 mm lattice, moves recorded,
  wide-exempt untouched. Bounce-apart TRIED AND REPLACED (pairwise
  moves oscillate — separating one pair shoves the third object; the
  obj_043 1→2 regression). A board whose items + gaps exceed its
  span is OVER_CAPACITY as a whole: left untouched, recorded.
  **FINDING (the fleet's 77 overlap pairs): almost the entire
  overlap mass is OVER-CAPACITY, not jitter** — obj_022 board 6
  needs 6.37 m on 1.5 m (14 items), obj_032 3.45 m on 1.5 m. Cause =
  HEIGHT COLLAPSE: stand-ins shorter than the real shelves push
  several observed levels onto one board via nearest-board
  assignment. → resolved by SR9 same session.
- **SR9 — CAPACITY TRIAGE BEFORE JIGGLE (08-05C late; user: "if
  something's total length simply isn't possible, kill or walk").**
  Deterministic ladder per over-capacity board, BEFORE legalization,
  so no-converge cycles cannot exist: **pass 0 — TILE REDUCTION**
  (user: "multi sub fills one box — we don't have to kill the
  entire box"): k-tiled rows shed copies from the high end, never
  below 1 — frees the most length, loses the least content;
  **pass 1 — SPILL**: evict the item whose OBSERVED height is
  furthest from the board (the height-collapse victim) to the
  nearest-height board with room, bottom re-snapped, dy recorded;
  **pass 2 — KILL**: no board has room → adds drop, detections drop
  with the anchor-level under-capacity complaint (the future
  anchor-walk feedback). Wide-exempt items are never evicted.
  FLEET RESULT: 77 → 3 overlap pairs via 32 tile drops + 14 spills
  + ZERO kills; the 3 residual = one B4 triple flagged
  footprint_wider+too_tall since CP3 — runner walk-down material,
  not jiggle material.
- **SR7 — PLACEMENT = place_candidate VERBATIM.** Host-inherited
  facing, k tiles filling the row, bottom-on-board. Sub-level
  jiggle = SR8, capacity triage = SR9 (both wired 08-05C late),
  host physics = SR10–SR12 (canonized 08-06); still open: the wall
  channel, level-2 riders, merge into fitted_preview, graduation
  out of experiments/.

## CANON 2026-08-06 — HOST PHYSICS (user: "i think this is great.
## lets cannonize all this"; code = experiments/sub_round_cp7.py,
## user-gated on obj_022 then fleet-run over all 15 anchors)

- **SR10 — UNDERSIDE BOARDS ARE CEILINGS.** cp2's up-face filter
  admits plank BOTTOM faces when the asset's normals are flipped
  (the messy-library census striking again): a sparse board
  (area < 0.3× a full board's) sitting 0–60 mm BELOW it is that
  plank's underside. It is NOT a standing surface — it is the
  physically correct CEILING of the compartment below; items seated
  on one are re-seated up onto the plank top. Headroom of a board =
  distance to the next surface above of any kind (an underside =
  the true ceiling). Fix-at-source option (trimesh fix_normals at
  load) stays queued; the classifier makes the pipeline immune
  either way.
- **SR11 — SUBS COLLIDE WITH THE HOST (user: "this is not jiggling
  with the host object itself").** Per standing board, host-mesh
  occupancy is measured on fit_check's 2 cm voxel lattice between
  board and ceiling → FREE INTERVALS along the board's long axis.
  Dividers/side panels split a board into cubbies; a front-face
  coverage probe (voxel curtain at the edge facing the host front,
  >0.6 covered = ENCLOSED, e.g. doors) closes compartments
  entirely. Intervals become PSEUDO-BOARDS for SR9/SR8 — capacity
  = free length, spills can only land in measured open space,
  enclosed boards evict their squatters, the sweep runs inside
  cubbies. ⚠ force_ax: an interval shorter than the board depth
  must inherit the BOARD's long axis, never recompute from its own
  rect (the obj_030 wrong-cubby bug). ⚠ Y_BLOCK_MIN 0.10: host
  cells under 0.10 m over the board are surface RELIEF (mattress
  folds — the obj_008 pillow was killed by its own duvet), not
  obstacles; flagged constant, re-test on scene #2. Honest
  accounting ships with it: cross-level overlap pairs, per-item
  ceiling protrusion, host-clip count (>4 cells past contact,
  fit_check's rule) — cp6's same-board-only count is superseded.
- **SR12 — RUNNER WALK-DOWNS (rule 11 one level down).** An item
  taller than its board's headroom walks its recorded shortlist
  runners — each trial-placed (native size, align trick, same k
  tiles, same box) — and takes the first that fits under the
  ceiling with 5 mm slack. No runner fits → TOO_TALL_DRY: the item
  STAYS (no silent content loss), the complaint is the library-gap
  / stand-in-under-capacity record — anchor-walk feedback, same
  channel as SR9 kills.
- **Fleet result (08-06):** obj_022 cross-level 28→7, host clips
  13→3, 4 walked, 4 kills (under-capacity complaint); obj_032
  7→0 xlvl, 6→3 host, protrusions 3→4 (re-seating SURFACES
  violations that were hidden inside planks — honest); obj_008
  pillow survives; obj_043 3→0 host; residuals all trace to
  too-tall dry items or stand-in under-capacity, none to the
  machinery. Viewer: "subs" layer = /subs_preview.glb, merged best
  pass per anchor (experiments/build_subs_preview.py — re-run
  after any sub-round pass; no stale stamp yet).

## Module contract (draft)

- **Gets:** shopping.json `subs_deferred` (64 items: name, observed box,
  host, anchor), the FITTED anchors (fitted_preview.json poses + real
  meshes), the measured room shell.
- **Decides:** for every sub, WHICH support surface of its fitted
  anchor it stands on, its final pose there, and (via its own
  retrieval round) which asset stands in for it.
- **A mistake looks like:** a book floating between boards, a sub
  placed on the wrong board because its seed ignored the anchor's
  move, a sub silently dropped, or a placement that reopens a
  converged anchor.

## USER RULINGS (2026-08-05C, session start)

1. **SEED IN THE FITTED FRAME.** Each sub's search STARTS at the same
   relative anchor→sub offset it had in the observation, re-expressed
   on the anchor's FITTED pose (jiggle/walk translation + any applied
   spin). The fitted mesh differs from the reference-scene anchor, so
   the search around that seed needs a VERY LARGE margin — but the
   seed is where it starts.
2. **ISOLATED EXPERIMENT FIRST.** One anchor before any pipeline
   wiring: **obj_043** (bookshelf, 8 subs: 1 basket + 7 books) —
   exercises board extraction + multi-board assignment while staying
   judgeable in one look. (obj_022's 28 subs would drown the first
   read; the desk obj_039 has no board problem.)
3. **CHECKPOINTS + REVIEW PAGES.** Every step is a checkpoint with a
   review page; the USER judges each before the next step runs
   (standing rule: Claude never concludes from images).
4. Rotation optimization is PARKED (user, session start): the
   wall-legality constraints keep it sane; revisit later.

## Experiment layout

Code: experiments/sub_round_cp*.py (sandbox — no pipeline files
touched). Data: out/bedroom_marble/compose/sub_experiment/cp<N>/
(each with index.html = the review page).

## Checkpoints

- **CP1 — seed transform.** Sub observed boxes → anchor-relative
  offsets → seeds on the fitted pose. Yaw delta = rotcheck_applied
  (plus an extent-swap sanity flag); obj_043 carries 0. Review: table
  + top-down and elevation splat shots with observed boxes vs seeds
  overlaid. GATE: do the seeds land where the books should start?
- **CP2 — board extraction.** Upward-facing horizontal patches of the
  fitted obj_043 mesh, clustered by height → boards with polygons.
  Review: boards drawn over the mesh render + heights table.
- **CP3 — assignment + clamp.** Sub → nearest board by seed height;
  XZ clamped into the board polygon (large margin per ruling 1).
- **CP4 — retrieval.** k=3 for the 8 subs (cheap-path decision after
  seeing cost). Review: pick sheets.
- **CP5 — place + render.** Bottom-flush on the board, host-inherited
  facing (fit_preview contract), same-board declip. Review:
  before/after + top-down.

Adoption (map drawing, generalization to all 15 anchors, the door/
picture oddball subs) waits until the experiment passes.

GRADUATION NOTE (08-05C, user question): level-1 anchors are fully
independent → the fleet parallelizes one-worker-per-anchor (cache
behind a lock) on real hardware. Serial on THIS machine by design —
the laptop hard-powers-off under stacked GPU bursts
([[laptop-gpu-crash]]); the driver's 2 s pacing is that gotcha.
Also: the 5-process-per-anchor shape wastes ~12 s/anchor on
python/torch startup — production form = one process, all steps
in memory.

## Progress

- 2026-08-06: **CP7 HOST-AWARE WALK-DOWNS built + USER PASSED on
  obj_022** (experiments/sub_round_cp7.py; candidate canon for
  SR10+, not yet ratified): (a) underside-boards (flipped-normal
  plank bottoms 44–48 mm below a full board, admitted by cp2's
  up-face filter) detected → kept as compartment CEILINGS, squatters
  re-seated onto the plank top; (b) too-tall items WALK their cp4
  runners (trial-placed, align trick, same k) — 4 walked, 7 dry
  kept with TOO_TALL_DRY; (c) HOST FREE SPACE: per-board free
  intervals on fit_check's 2 cm voxel lattice (dividers/side
  panels subtracted; front-coverage access test for doored
  compartments) → intervals = pseudo-boards for SR9/SR8 (force_ax
  pins the long axis — short intervals otherwise flip to the board
  depth: the obj_030 wrong-cubby bug, fixed); (d) honest physics
  report: cross-level pairs 28→7, ceiling protrusions 9→4, host
  clips 13→3; residual = the B4 too-tall trio (runners dry,
  over-capacity) — anchor-walk material. COST: 4 kills on B3 (no
  board has room) = the under-capacity complaint. B1 "doors" =
  actually dividers (mesh evidence). NEXT here: generalize cp7 to
  the fleet, or promote into the SR canon on ratification.

- 2026-08-06 LATE: **CP7 FLEET RUN over all 15 anchors** (user "go";
  serial, 2 s pacing; cp7 added to sub_round_all.py STEPS + overview
  links/shot/bits; idle guard for cp6-idle anchors, empty-scene
  guard when everything dies). TWO FIXES ON THE WAY: (a) obj_008 bed
  — the free-space probe read MATTRESS RELIEF as obstacles (0.44 m
  free for a 0.75 m pillow → pillow killed → empty-scene crash);
  new Y_BLOCK_MIN 0.10 = host cells under 0.10 m over the board are
  relief, not obstacles (⚠ flagged constant, scene #2). (b) walked-
  then-killed items left stale mesh entries (KeyError) — guarded.
  FLEET RESULT: 8 idle/quiet anchors · obj_022 as gated (28→7 xlvl,
  13→3 host, 4 kills) · obj_032: 2 re-seated, 7→0 xlvl, 6→3 host,
  4 dry, protrusions 3→4 (re-seats SURFACE previously-hidden
  violations — honest) · obj_008 pillow survives (1 host-clip
  contact w/ bed relief) · obj_043 3→0 host clips · obj_039 1 dry.
  Overview: sub_experiment/index.html (cp7 shots + links).
  **FLEET CP7 USER GATE OPEN.**

- 2026-08-05C LATE: CANON SR0–SR7 written (above) · pipeline map
  gains PH2r SUPPORT RECURSION (node+card `subr`, honest EXP badge)
  · scripts generalized (per-anchor sub_experiment/<anchor>/cp*,
  level-2 deferral at CP1, NO_BOARD honesty at CP3/CP5) ·
  **LEVEL-1 FLEET RUN over all 15 anchors**
  (experiments/sub_round_all.py, serial by design — laptop GPU
  gotcha; 545 s + one obj_007 empty-GLB fix + rerun): **56 placed ·
  16 cp3 flags · 1 no-board skip (ceiling light) · 6 level-2
  deferred (riders wait for their hosts) · 77 same-board overlap
  pairs** — the overlap mass is obj_022-class crowding = exactly the
  missing sub-jiggle (SR7 note). Overview page:
  out/bedroom_marble/compose/sub_experiment/index.html (row per
  anchor, final front shot inline, links to every CP page;
  --overview-only rebuilds it from disk). **FLEET USER GATE OPEN.**

- 2026-08-05C: plan written; CP1 building.
- 2026-08-05C: CP1 RUN (experiments/sub_round_cp1.py) — delta
  [-0.06, +0.154, 0] raw (= declip + floor-snap, verified vs GLB),
  yaw 0, swap flag clear, 8 seeds within the shelf footprint.
  FRAME FINDINGS: fit_box = RAW frame; declip_move_m = RENDER frame;
  shot.py blank above 1024 px (RES pinned + size guard).
  Review page: out/bedroom_marble/compose/sub_experiment/cp1/
  index.html. CP1 USER GATE PASSED (user: "ok. try it").
- 2026-08-05C: CP2 RUN (experiments/sub_round_cp2.py) — 6 boards on
  the fitted obj_043 mesh @ 0.05/0.39/0.74/1.08/1.42/1.77 m above
  floor (~0.34 m spacing; top surface = B5). Sub observed heights
  0.79/1.13/1.46/1.79 sit ~0.04 m above boards B2..B5 — clean
  correspondence; the 2.11 m basket rides above the top. Review page:
  out/bedroom_marble/compose/sub_experiment/cp2/index.html.
  CP2 USER GATE PASSED (user asked for + got the asset overlaid:
  stand-in = two-column cabinet, DOORS over B0/B1, open above; subs
  all map to the open part).
- 2026-08-05C: CP3 RUN (experiments/sub_round_cp3.py) — 8/8 assigned,
  boards B2..B5, ZERO flags; y snaps +0.09..+0.14 (books) / −0.19
  (basket onto the top surface), xz clamps ≤ 46 mm. Note: the
  anchor's floor-snap (−0.154 render y) pushed seed bottoms BELOW
  their boards; nearest-board assignment recovered the observed
  per-level pairing exactly. Review page:
  out/bedroom_marble/compose/sub_experiment/cp3/index.html.
  CP3 USER GATE PASSED (user: "seems fine").
- 2026-08-05C: CP4 ruling (AskUserQuestion): CHEAP BY CLASS — top-1
  category+size fit, no judge; weak matches flagged for a later
  judged pass. CP4 RUN (experiments/sub_round_cp4.py): 8/8 picked,
  all tier-0 exact category, scores 0.12–0.25, ZERO flags, 0 judge
  calls. Book boxes are ROWS → picks carry k=2/3 side-by-side copies
  (CP5 must honor k). Runner-ups recorded for walk-downs. Review
  page: out/bedroom_marble/compose/sub_experiment/cp4/index.html.
  CP4 USER GATE PASSED (user; noted the thumbnails' books look
  TILTED — probably messy assets; ruling: place RAW first, then the
  PCA trick).
- 2026-08-05C: CP5 RAW pass RUN (experiments/sub_round_cp5.py,
  --pca flag exists for the re-run) — 8/8 placed via fit_preview.
  place_candidate reused verbatim (PCA snap stubbed out), facing =
  host inheritance, k tiles honored, 1 same-board overlap pair
  (recorded, unresolved). subs_preview.glb saved raw-frame. HONESTY
  NOTE: the canon PCA snap is YAW-only (footprint); the visible book
  LEAN (roll/pitch, baked in-file) is a different defect — the PCA
  re-run will NOT straighten it. Review page:
  out/bedroom_marble/compose/sub_experiment/cp5/index.html.
  CP5 RAW GATE PASSED (user: "indeed all the stuff are rather
  tilted"; the shoe-looking basket asset accepted as an asset
  problem; ruling: "lets do the align trick").
- 2026-08-05C: ALIGN TRICK built + RUN (sub_round_cp5.py --align →
  cp5_align/, raw pass kept for comparison): align_upright() snaps
  the asset's OBB axes to the nearest world axes (minimal rotation;
  fixes baked roll/pitch AND yaw skew — canon PCA is yaw-only and
  could not straighten the lean; back-front sign ambiguity dumped on
  a horizontal axis, facing ladder owns it downstream). Applied
  angles 2.3–45.5° across the 8 subs; canon PCA stayed ON (0 extra).
  Books stand upright in the render. NEAR-45° CAVEAT recorded:
  nearest-cardinal can snap a hard lean to lying-down; three assets
  hit 45.5° — they landed upright this run, fragile in general.
  Review page: out/bedroom_marble/compose/sub_experiment/cp5_align/
  index.html (raw|align side-by-side). CP5 ALIGN GATE PASSED (user:
  "interesting!").
- 2026-08-05C: ALIGN-BEFORE-SHOP (user insight: aligning changes the
  AABB, so shopping's fit scores AND the k multiplier were computed
  on lean-inflated catalog sizes). Built: cp4 --aligned — catalog
  shortlist → top-12 re-measured on ALIGNED AABBs (align_upright at
  load, cached in sub_experiment/aligned_size_cache.json, 35 uids
  measured — the cache is the seed of a catalog column) → re-ranked.
  RESULT: 4/8 PICKS CHANGED; the 45.5° leaner (09f50342) dropped
  from every slot; obj_048 fit 0.231→0.082. cp5 --align
  --picks-dir cp4_aligned --out cp5_final rerun: 8/8 placed upright,
  uids verified == picks, 1 overlap pair persists. Pages:
  sub_experiment/cp4_aligned/index.html (CHANGED tags vs cp4) +
  sub_experiment/cp5_final/index.html. **FINAL GATE OPEN.**
