# SESSION 2026-08-06 HANDOFF — CP7 HOST PHYSICS CANONIZED (SR10–SR12)

Continues SESSION_2026-08-05C_HANDOFF.md (whose own header says its
current record = PLAN_SUB_ROUNDS.md — same here). One session;
outcome: **the sub rounds gained real physics against the host mesh
— underside-boards-as-ceilings, voxel free-space intervals
(dividers/doors), runner walk-downs — user-gated on obj_022, fleet-
run over all 15 anchors, CANONIZED as SR10–SR12, and the subs joined
the 3D viewer as a layer.** PLAN_SUB_ROUNDS.md "CANON 2026-08-06" =
the authoritative rules; REVIEW_LOG 08-06 entries = the gates.

## NEXT SESSION — FIRST THINGS

1. **NITS** (user, end of session: "we will do nits next session") —
   no list was made; walk the cp7 pages + viewer with the user.
   **THEN: SCENE #2** (user: "most importantly we will run on other
   scene after") — see SCENE #2 READINESS below.
2. Still-open sub-round items (canon SR7 tail): **wall channel**
   (arch-class subs + rung-3 face-mount) · **level-2 riders** (6
   deferred) · **merge into fitted_preview** · **graduation out of
   experiments/** (align+cache into shopping.py/fit_preview.py,
   cp1–cp7 as one process).
3. **Front/back constraint** — STILL queued from 08-05B (reverts
   obj_035's 180; user should eyeball that picture first).
4. Map: PH2r card still wears the EXP badge — accurate until
   graduation; update the card text to mention SR10–SR12 when the
   user approves the drawing step.

## WHAT LANDED (chronology = the four user prompts)

1. **User caught two defects on the fleet thumbnails:** (a) cp2
   board extraction admits plank UNDERSIDES (flipped normals) —
   obj_022 has 3 sparse boards 44–48 mm below full ones; 6 subs
   were seated INSIDE planks. (b) Sub jiggle was same-board-only —
   cross-level collisions (tall items through the plank above)
   invisible; cp6's "3 residual overlaps" was really 28 cross-level
   pairs on obj_022 once measured.
2. **cp7 v1 (walk-downs + cross-level accounting), obj_022:**
   underside re-seat + runner walk-downs + honest report. User then
   caught the deeper hole: "this is not jiggling with the host
   object itself" — v1's re-triage had spilled baskets into the
   cabinet's closed-door compartment.
3. **cp7 v2 (HOST-AWARE):** host voxel occupancy (fit_check 2 cm
   idiom) → per-board FREE INTERVALS → pseudo-boards for SR9/SR8;
   front-coverage access test for doored compartments. Findings on
   the way: B1's "doors" are actually two vertical DIVIDERS (mesh
   evidence — three cubbies); force_ax bug (short intervals flipped
   their long axis to the board depth → obj_030 in the wrong cubby,
   clipping a divider). obj_022 final: cross-level 28→7,
   protrusions 9→4, host clips 13→3; COST 4 kills on B3 =
   under-capacity complaint. USER PASS.
4. **Fleet run (all 15 anchors, serial, 2 s pacing):** two more
   fixes — obj_008's pillow was killed by MATTRESS RELIEF read as
   obstacles (new Y_BLOCK_MIN 0.10: host cells <0.10 m over the
   board = relief not obstacle; ⚠ flagged constant) + walked-then-
   killed stale-mesh guard + idle/empty-scene guards. 8 active / 7
   idle anchors; obj_032 7→0 xlvl 6→3 host but protrusions 3→4
   (re-seats SURFACE hidden violations — honest); obj_043 3→0.
   USER PASS → **CANON SR10–SR12**.
5. **Viewer subs layer:** experiments/build_subs_preview.py merges
   per-anchor best pass (cp7 > cp6 > cp5) → compose/subs_preview.glb
   (8 anchors, 65 nodes); serve.py route /subs_preview.glb; "subs"
   checkbox in index.html (clone of fitted-preview layer, raw frame,
   unlit). NO auto-rebuild/stale stamp — re-run the build script
   after any sub-round pass. Server restarted via WMI (PID 24668,
   [[windows-detached-server-gotcha]]; HEAD unsupported by design —
   probe routes with GET).

## SCENE #2 READINESS (user: nits next session, "and then most
## importantly we will run on other scene after")

**Scan verdict (end of 08-06, all checks pass):** all 10 chain
scripts compile · cp7 records for all 15 anchors internally
consistent (n_items == rows, no unknown boards, no killed ghosts,
glb+render+page present) · merged layer covers every placed sub
(65 nodes / 45 subs) · viewer routes 200 (an earlier 404 scare was
a PowerShell probe artifact: `"$u?scene"` eats the `?` into the
variable name — probe with literal URLs) · no scene- or object-
specific logic in code (obj ids only in docstrings + overridable
--anchor defaults; the fleet driver derives anchors from
shopping.json).

**Entry condition for a new scene:** the upstream chain through
compose must exist per paths.py — shopping.json (subs_deferred +
items), fitted_preview.glb/.json, snap/graph records, manifest
frame, gen_raw.ply. Then: `sub_round_all.py --scene <name>` runs
cp1→cp7 per anchor and builds the overview;
`build_subs_preview.py --scene <name>` refreshes the viewer layer.

**⚠ FLAGGED CONSTANTS — the scene-#2 watch list (sub-round chain;
the anchor-loop five are already flagged in PLAN_FIT_LOOP):**

- cp2 boards: UP_DOT 0.65 · cluster GAP 0.035 (< plank thickness
  splits undersides out — SR10 depends on this) · MIN_AREA 0.02 ·
  MIN_SPAN 0.12
- cp6/cp7 jiggle: INSET 0.01 · LATTICE 0.005 · item GAP 0.005
- cp7 host physics: PLANK_MAX 0.06 · PHANTOM_AREA_FRAC 0.3 ·
  PITCH 0.02 (fit_check's) · CONTACT_CELLS 4 · Y_PAD 0.03 ·
  **Y_BLOCK_MIN 0.10** (relief-vs-obstacle — tuned on ONE bed) ·
  MIN_RUN 0.06 · CURTAIN 0.03/0.08 · COVER_ENCLOSED 0.6 ·
  SLACK 0.005
- Known geometry risk: boards/intervals/jiggle are all WORLD-AXIS
  aligned; bedroom_marble is only ~5.5° yawed
  ([[room-yaw-and-splat-transform-frame]] — the pipeline never
  estimates continuous yaw). A strongly yawed scene #2 would
  inflate footprints and degrade the 1D sweeps — watch the cp2
  board rects first.

## STATE

- **Docs:** PLAN_SUB_ROUNDS.md (canon SR10–SR12 + 2 progress rows) ·
  REVIEW_LOG.md (2 new entries, both USER PASS) · this file.
- **Code (experiments/):** sub_round_cp7.py (new, ~900 lines) ·
  build_subs_preview.py (new) · sub_round_all.py (cp7 in STEPS +
  overview links/shot/bits).
- **Viewer:** serve.py (+/subs_preview.glb route) · index.html
  (+subs layer). Server alive :8321 PID 24668, scene
  bedroom_marble.
- **Data (out/bedroom_marble/compose/):** sub_experiment/<anchor>/
  cp7/ for all 15 (8 with placements_walked.json + subs_walked.glb +
  front.png, 7 idle stubs) · sub_experiment/index.html (overview,
  cp7 shots) · subs_preview.glb (19.7 MB merged layer).
- **COMMITTED as 9a74f84** ("Sub rounds SR0-SR12: support recursion
  fleet + host physics canon + viewer subs layer", 16 files — this
  session AND the whole 08-05C backlog, one coherent changeset).
  Tree clean. PUSH = user's job (settings deny git push here).
