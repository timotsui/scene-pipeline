# SESSION 2026-08-07 HANDOFF — NITS CLOSED + THE CLEARING POINT

Continues SESSION_2026-08-06_HANDOFF.md. This was the nits session
that handoff queued; it ended at a deliberate **CLEARING POINT**:
bedroom_marble fully clean and verified, workspace decluttered,
context to be cleared, **next session = SCENE #2 from a fresh
start**. Canon record = PLAN_SUB_ROUNDS.md "CANON 2026-08-07";
gate record = REVIEW_LOG.md 08-07 entry.

## WHAT LANDED (all USER PASS)

1. **SR12b — HEIGHT-AWARE RELOCATION** (sub_round_cp7.py): spill
   targets check headroom (pseudo-boards carry ceil_y); walk-down's
   last rung before TOO_TALL_DRY relocates the item rigidly to the
   nearest-observed-height standing board fitting height+footprint.
   Walk fixes HEIGHT, triage fixes LENGTH.
2. **SR10 AT THE SOURCE** (cp2/cp3/cp6): undersides classified at
   extraction (`underside_of` in boards.json, ·ceil overlay, role
   column); cp3 assigns + cp6 spills to STANDING boards only; cp7's
   re-seat = safety net, 0 firings on the fixed chain.
3. **ROWABLE TILING GATE** (compose/shopping.py `ROWABLE_CATS` =
   book/books, `native_fit(rowable=)`, both call sites incl. cp4's
   aligned re-rank): k>1 tiling had FABRICATED objects — one desk
   lamp became 3 tiled lamps, one monitor twins (obj_039). Bonus:
   the k=1 re-rank flipped the monitor pick from a sci-fi arm to a
   real monitor. Interim stand-in for the multiplicity judge.
4. **MULTIPLICITY PROBE** (experiments/multiplicity_probe.py, 48
   calls; record + review page in
   out/bedroom_marble/compose/sub_experiment/_multiplicity_probe/):
   **Probe A (crop → single-or-row): 12/12 correct AND stable over
   3 runs** — wire-ready as a graph-stage judged attribute (row
   counts wobble, but the k ceiling only needs single-vs-row).
   **Probe B (crop + tiled render → reads-as-observed): stable,
   reasoned, but OVER-SCOPED** — it vetoed the lamp/monitor
   fabrications correctly AND ALSO the legit book row (style/variety
   mismatch) and the shelf case (my stimulus conflated asset match
   with composability — a fair retest needs a matching-height unit).
   B needs count-only scoping before it can gate anything.
   **TWO SOURCES OF k** (user): pixel count (graph judge) + modular
   composability (pick-time common sense — two shelf units may stand
   in for one big shelf; two lamps never read as one lamp).
5. **FLEET RE-RUN, all three fixes: 15/15 clean** — 8 active
   anchors, 37 subs; totals 2 relief-scale host clips (obj_060 on
   the bed, obj_068 on obj_023 — accepted class) · 0 cross-level ·
   0 protrusions · 0 dry · 8 kills (7 = obj_022 under-capacity
   complaints = anchor-re-shop food). Desk obj_039: lamp relocated
   onto the desktop, single lamp + single monitor. Consistency
   sweep verified all records fresh + artifacts present.
6. **VIEWER DECLUTTER** (viewer/index.html): main row = splat ·
   clip ceiling · hi-fi · fitted preview · subs · scene model only;
   new collapsed "tools / advanced" holds axes · human · collider ·
   clearance (now default OFF) · place (P) · rot/cam inputs;
   renamed "scene-pipeline viewer". All ids/routes/shortcuts kept.
   Server picked it up live (route-table server re-reads per
   request). ⚠ USER HUD EYEBALL STILL PENDING (was AFK) — first
   one-look next session.
7. **OUT/ CLEANUP**: 14 retired pre-Marble generator scenes +
   8 cold LucidDreamer caches (~13 GB) moved to
   out/archive/retired_2026-08-07/ (MOVED, not deleted). Kept:
   bedroom_marble · realplayroom (real-scan generality) ·
   glts_comparison_2026-07-14 (paper record) · infra dirs.
   **DECISION: Marble worlds are the scene format going forward.**

## ANCHOR-TIER CAVEAT (known, accepted)

fitted_preview is PRE-GATE: 4 anchors carry tiles — rug ×3
(deliberate doormat tiling, legit) · bookshelf obj_043 ×2 (modular,
arguably legit) · basket obj_009 ×2 + picture obj_035 ×2 (probably
the duplication disease). User ruled: leave them; re-judge when the
multiplicity judge lands. Do NOT re-run anchor shopping with the
blunt gate — it would collapse the rug to one doormat.

## NEXT SESSION — SCENE #2 (clean pipeline run, fresh context)

1. User one-look: the decluttered HUD (localhost:8321; restart via
   WMI if dead — [[windows-detached-server-gotcha]], serve.py).
2. **HARVEST a new Marble world** — needs the USER's browser step
   to mint the public CDN URL (week8/marble-harvest SOP) → lands as
   out/<scene>/gen_raw.ply + prompt.txt.
3. viewer/prep_scene.py → data/<scene>.bin → dropdown entry.
4. Run the canonical chain STAGE BY STAGE with user gates (the
   pipeline_map order): pano self-render → crop rig → vocab →
   detect → lift → merge/recenter → room shell → graph record →
   judge passes → S1–S4 → PH1 snap → PH2 fit loop → PH2a → sub
   rounds (sub_round_all.py) → build_subs_preview.py.
5. ⚠ WATCH LIST (from the 08-06 handoff, still current): room YAW
   (boards/intervals/jiggle are world-axis-aligned; check cp2 board
   rects early on a yawed scene) · Y_BLOCK_MIN 0.10 (tuned on ONE
   bed) · the anchor-loop five (DRY 0.65 · HUG 0.30 · MARGIN 0.15 ·
   FLAT 0.06 · dual-attach 0.10) · cp2 board constants (UP_DOT 0.65
   · GAP 0.035 · MIN_AREA 0.02 · MIN_SPAN 0.12 · PLANK_MAX 0.06 ·
   UNDERSIDE_AREA_FRAC 0.3).

## STILL QUEUED (unchanged priorities)

Multiplicity judge (graph stage; A wire-ready, B needs scoping) ·
wall channel (3 subs) · level-2 riders (6) · merge subs into
fitted_preview · graduation out of experiments/ · front/back
constraint (08-05B) · anchor re-shop channel for the under-capacity
complaints.

## COMMITS

d7f27a8 (nits: SR12b + SR10-src + rowable gate + probe + docs/map)
+ the wrap-up commit containing this handoff and the viewer
declutter. PUSH = user's job (settings deny git push here).
