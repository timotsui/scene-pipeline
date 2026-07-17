# 2026-07-17 handoff — package reorg, carved-splat rejected, clean view

Short session between the 07-15 loop work and the next pipeline push.
Read SESSION_2026-07-15B_LOOP_HANDOFF.md for the loop state — nothing
about the loop changed here.

## What happened

1. **package/ reorg** (`out/bedroom_marble/package/`): top level now holds
   ONLY current-implementation outputs (composed2 renders/state/glb,
   edits.jsonl, picks2/shortlists2, loop/ trace). Legacy v0/v1 chain +
   the flawed loop run1 moved to `package/_archive/`; Jul-7 junk deleted
   (webp view copies, manifest overlays, stale manifest copy, empty
   jiggle_history, review_crops — regenerable via `review_server.py
   --recrop`).

2. **Carved-splat representation: BUILT then REJECTED (user judgment:
   cutout quality bad).** The idea: delete in-box gaussians from
   gen_raw.ply, difference-matte (black+white bg renders → true alpha),
   composite meshes over the carved splat + synthetic floor. It worked
   mechanically (332,816/1.92M gaussians dropped, honest holes) but the
   plain-AABB cutouts looked bad. carve.py + data deleted, paths.py
   reverted; do NOT re-suggest without a much tighter carve (hull/mask).

3. **Clean view adopted instead** — `python place2.py --scene <sc>
   --clean`: mesh-only render of the EXISTING composed_state2.json (loop
   edits kept; no state rebuild — build_state would drop yaw nudges) over
   a synthetic floor plane, no gsplat. Floor tint = `_splat_floor_color`:
   median splat color in a 3 cm band at floor height, inner 80% of the
   footprint (bedroom_marble: (143,100,63) from 402,933 pts; grey
   fallback). Writes `package/composed2c_view_*.png`. Kept from the
   experiment: `_rgba_pass` refactor (regression-verified: pixel-identical
   modulo ≤31-intensity antialias jitter on ≤91/810k px) + `_floor_mesh`.

## Three view flavors now (place2.composite_views splat_bg)

- `True`   → splat-backed `composed2_view_*` (canonical in-context; NOTE:
  backfills missing objects, halos undersized meshes — flattering)
- `False`  → bare grey (C7 loop judge — untouched this session)
- `"clean"`→ meshes + tinted floor `composed2c_view_*` (honest
  representation for manual viewing)

## Open / next (unchanged from 07-15B)

- **NEXT UNBLOCK: judge-camera coverage fix** — 6 yaws at 60° + a raised
  or off-center camera; the 4×fov-75 rig blind zones (floor <2.1 m, four
  15° wedges) auto-reject adds. Then re-run the loop.
- User verdicts still pending: door yaw edit, AC add (0.093 window
  interpenetration), Marble bare-walls question.
- Parked: our-init + GLTS-loop ablation cell (needs TreeSearchGen loop
  seam feasibility read).
