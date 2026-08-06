# SESSION 2026-08-05C HANDOFF — SUB ROUNDS: obj_043 EXPERIMENT DONE

## ⚠ SUPERSEDED SAME DAY — the session continued far past this file.
## THE CURRENT RECORD = PLAN_SUB_ROUNDS.md (canon SR0–SR9 + progress
## rows) + REVIEW_LOG.md 08-05C entries + the PH2r card in
## pipeline_map.html. Summary of what came after this handoff:
## canon SR0–SR9 + map PH2r node (support recursion = same loop per
## level) · FLEET over all 15 anchors (per-anchor
## sub_experiment/<anchor>/cp*, overview index.html, --overview-only)
## · SR3b wall-gate (window-on-curtain-fold; OBSERVED box tested) ·
## SR4b host-covers + verification ladder (text rung + AUTONOMOUS
## thumbnail-judge rung 2, host_covers_cache.json) · SR4c sub dry
## rule (= anchor rule 9) · SR4d sub-brings-host · SR8 per-board 1D
## legalization (bounce-apart rejected: oscillates) · SR9 capacity
## triage (tile-drop → spill → kill): fleet 77 → 3 overlap pairs,
## 32 tile drops, 14 spills, 0 kills; residual = one wide+tall B4
## triple = runner walk-down material. OPEN: runner walk-downs ·
## wall channel + rung-3 face-mount · level-2 riders · merge into
## fitted_preview · graduation out of experiments/ · front/back
## constraint (from 08-05B) · EVERYTHING UNCOMMITTED.

Continues SESSION_2026-08-05B_HANDOFF.md. Day session; outcome: **the
isolated sub-round experiment on anchor obj_043 ran END TO END through
five user-gated checkpoints (all passed), producing the ALIGN TRICK +
ALIGN-BEFORE-SHOP corrections on the way.** Rotation optimization
stays PARKED (user, session start: constraints keep it sane).

Plan/log docs: PLAN_SUB_ROUNDS.md (rulings + per-CP progress),
REVIEW_LOG.md (6 new entries). Code: experiments/sub_round_cp{1..5}.py.
Data: out/bedroom_marble/compose/sub_experiment/ (cp1..cp5, cp4_aligned,
cp5_align, cp5_final — each with index.html review page).

## THE PIPELINE THAT NOW EXISTS (experiment-grade, one anchor)

1. **CP1 seeds** — sub offsets re-expressed on the fitted anchor pose
   (delta = declip + floor-snap, verified vs GLB; yaw hook ready).
2. **CP2 boards** — upward-face height clustering on the fitted mesh:
   6 boards @ 0.05..1.77 m (B5 = top surface).
3. **CP3 assignment** — nearest board by seed bottom + footprint clamp:
   8/8, zero flags, reproduced the observed per-level pairing.
4. **CP4 retrieval** — CHEAP BY CLASS (user ruling via question: top-1
   category+size, no judge; weak matches flagged; runners recorded).
5. **CP5 placement** — place_candidate reused verbatim (host-inherited
   facing, k tiles, bottom-on-board); raw pass → align pass → final.

## THE TWO CORRECTIONS BORN THIS SESSION

- **ALIGN TRICK** (cp5 --align): align_upright() snaps each asset's
  OBB axes to nearest world axes — fixes baked roll/pitch lean that
  the yaw-only canon PCA cannot. Angles 2.3–45.5° on these 8. CAVEAT:
  nearest-cardinal is ambiguous at ~45° (three assets at 45.5° landed
  upright; a harder lean would snap to lying-down — tiebreak-by-box-
  aspect is the fix if it ever bites).
- **ALIGN-BEFORE-SHOP** (cp4 --aligned; user insight: the align
  changes the AABB → fit scores AND k multipliers were computed on
  lean-inflated catalog sizes): top-12 re-measured on aligned AABBs,
  cached (sub_experiment/aligned_size_cache.json, 35 uids — seed of a
  catalog column). RESULT: 4/8 picks changed; the 45.5° leaner
  dropped from every slot; obj_048 fit 0.231→0.082. cp5_final placed
  the new picks, uids verified.

## FRAME + INFRA FINDINGS (real, documented in the scripts)

- **fitted_preview.json fit_box is RAW frame** (byte-identical x/z to
  the observed box); **declip_move_m is RENDER frame** (verified vs
  the GLB, which is the placed truth). First CP1 run had a silent
  3.4 m error from assuming render.
- **shot.py silently renders BLANK above 1024 px** (1024 fine, 1050+
  ~10 KB webp) — RES pinned 1024 + a <30 KB blank-render guard in
  every sub_round script.
- Viewer :8321 died with the reboot; relaunched via WMI (PID 11988,
  full python path needed — bare "python" gives ReturnValue 9).

## ACCEPTED WARTS / OPEN ITEMS (next session)

- **Generalize to the other 14 anchors** — incl. the oddball subs
  whose anchors are doors/pictures (no boards; skip-or-wall-hang was
  deliberately left undecided) and obj_022's 28 subs.
- **Asset content** — the "basket" + some book picks render shoe-like
  (user: "thats the asset problem", accepted for now); the judged
  pass hook (flags) exists when fidelity starts to matter.
- **1 same-board overlap pair** — recorded in every CP5 run,
  unresolved (raw ruling: no declip among subs yet).
- **Graduation** — align_upright + aligned-size cache into
  compose/shopping.py + fit_preview.py proper, sub rounds onto the
  pipeline map (experiment stayed off-map by design), then the 64-sub
  full run. ALSO STILL QUEUED from 08-05B: front/back constraint
  (reverts obj_035's 180; user should eyeball that picture first).
- **ALL UNCOMMITTED** — this session's files AND 08-05B's (commit =
  user's call).
