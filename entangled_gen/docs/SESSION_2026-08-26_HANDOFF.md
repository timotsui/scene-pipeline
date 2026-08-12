# SESSION 2026-08-26 HANDOFF — the compose canon grew up in one night

(Real date 2026-08-11 → 08-12, one continuous session with the user in
the loop nearly the whole time. REVIEW_LOG **R-S2-110..128** — nineteen
entries. Previous handoffs: SESSION_2026-08-25C (the automation bar),
SESSION_2026-08-25D (bar met + collider optional). Tree NOT committed —
**a commit checkpoint is owed, many sessions deep.**)

**CLOSE-OUT STATE (the user's final instruction: "clean the pipeline, I
don't need a run right now"):** all 23 touched modules compile; --list,
full dry-run and fleet dry-run plan cleanly; final gates PASS on
fresh02/fresh03/autotest_living/autotest_bedroom.
⚠ ONE KNOWN LOOSE END: R-S2-128 (stale walk/pick choices voided against
current shopping) is CODED but fresh04's preview was mid-refit when the
user called stop — its GLB still shows the stale BED standing in for
console table obj_000. ONE command heals it and verifies 128:
`python run_scene.py --scene fresh04 --phase compose --from fit_preview`
(expect the "VOIDING stale walk choice" line, then obj_000 from the
table aisle). fresh04's last COMPLETED compose (the R-S2-127 run) is
the reference for the numbers below.

## 0. THE ONE-LINE TRUTH

**fresh04 — a never-run, colliderless world — went from raw bundle to a
furnished room with ZERO mesh collisions (0.0 L, was 66 L at first
compose) and 38/43 items placed, every absence carrying a named receipt
— under thirteen new user rulings that turned the compose stage from
"places whatever it bought" into "measures, escalates by meaning, and
abandons honestly."**

## 1. WHAT CHANGED (all logged; numbers = REVIEW_LOG entries)

**The scene/world layer (110–114, previous handoff, recap):** collider
OPTIONAL ("splat floor wins"), corpus 29→318 runnable; the one-command
bar met on fresh04; connector defect class closed (5 readers).

**The compose canon (115–127, this evening — trigger: the user's eye on
fresh04's preview, every time):**

| R-S2 | ruling / fix |
|---|---|
| 115 | clipping allowed but MINIMAL, no paired exemptions → minimal-clip net-descent pass in fit_declip |
| 116 | hug lock DIRECTIONAL (toward-wall slides legal; the frozen wardrobe) |
| 117 | allowed-clip margin `fit_check.ALLOW_L = 0.5 L` (overlaps under it = `contacts`, recorded not chased) |
| 118 | wall-backed floor furniture may not yaw (the 15° wardrobe) |
| 119 | ceiling adds placed on the ceiling (support/where reconciliation in propose_edits) + hug drift allowance |
| 119b | drift cap `HUG_DRIFT_M` user-set 0.2 → **0.3 after normalization** (eye-knob in true meters) |
| 120 | trimmed scale consensus (TRIM_X 2.0) + head-word shopping aisles ("tray table" shops tables) |
| 121 | normalized scenes VERIFY, never crash (second-apply guard routes to verification; gate-proof) |
| 122 | J9 full/partial coverage (partial members keep their measured box — the flattened-wardrobe fix) + wall items may sit in their wall |
| 123/124 | **THE SIZE BAR**: nothing places whose best candidate exceeds DRY 0.65 worst-axis — better absent than wrong-sized; `not_placed` receipts |
| 125 | FLAT axes (box < 0.15 m) measure ABSOLUTELY with 15 cm allowance (the thin-item massacre fix) |
| 126b/c | size-nominated escalation built → **withdrawn same night** (bed-for-console-table) |
| 127 | **escalation, user's design**: meaning nominates ≤3 catalog categories ordered by closeness, sequential one-aisle walk at the normal bar, then honest death; `substituted_as` + `escalation_trail` on record |

**Viewer:** clickable fitted assets; rich cards everywhere (description,
shot tile inline, provenance, asset catalog info + native size + fit%,
target box, substitution trail, name in the title). serve.py gained
`/shown_pic` + description/shown_pic in the materialized payload
(server restart needed after pulls). HUD fitted-preview tooltip updated.

**Scale truth:** fresh04 measured 0.66 → normalized (k=1.49) → re-measures
**s=1.049**. Two-pass protocol executed end-to-end for the first time
(and immediately found+fixed its guaranteed re-run crash, 121).

## 2. CURRENT STATE OF fresh04 (the reference scene)

- Final gate PASS; **0 clips / 0.0 L**; 38 placed / 5 honest absences
  (panel, curtain, wall molding, rug ×1 each — library gaps with
  trails; rug's best doormat = 0.686, two points over the bar).
- Substitutions live: bench→ottoman (0.546), console→table,
  **headboard→bed (0.554) — awaiting the user's eyeball**.
- 56-node grouped layer, J9 coverage verdicts in (wardrobe pool all
  partial → no size-share), metric room.

## 3. OPEN DECISIONS (the user's, none blocking a run)

1. **Wall definition**: fitted walls = outermost structural plane; the
   eye reads the paneling → furniture visually buries a few cm into
   wall dressing. "Which surface is the wall for fitting?"
2. **Invented-anchor authority**: `estimated_prior` boxes steer real
   furniture with full authority (menu on record: bounded authority /
   wall-anchored swaps / tier demotion).
3. **Panels as objects**: 17 molding panels ship as furniture; user
   said "fine" for now (options: PART_OF_STRUCTURE absorption, or
   exclude from shopping).
4. Headboard→bed stand-in verdict; bar nudge (0.65→0.70 would admit
   the rug's doormat and the old headboard) — eye calls.
5. Medium-confidence rotation verdicts (currently never applied;
   the known-crooked panel case is asset junk = user doesn't care).
6. One-shot re-shop (fit_feedback enforcement) — still unbuilt
   (PARKED #5); the size bar at the placer now covers most of its
   ground.

## 4. TRAPS THAT BIT THIS SESSION (add to your reflexes)

- **`--from X --phase all` re-runs the OTHER phases IN FULL** — it
  scopes only the table owning X. Cost one full funnel re-run tonight.
  Not yet fixed or logged as a defect; worth a refusal or a clearer
  semantic before batch nights.
- The preview file is rewritten MID-RUN several times (naive place →
  declip → walk rounds) — never judge it while a run is in flight.
- Compose re-runs after a METRIC change must clear stale-metric
  fit_feedback rejections (done once by hand this session).
- scene_gate's no-op trap caught MY OWN fix once (121) — write the
  promised file on every path.

## 5. WHAT NEXT (the road to 100 scenes)

1. **Commit checkpoint** (Timotsui / timotsuihc@gmail.com) — ask the
   user; many sessions of work uncommitted.
2. **fresh05**: the standing bar — every canon change of this session
   has run only on fresh04's compose; a never-run world, one command,
   zero intervention, validates 115–127 the only way that counts.
   Box-shaped interior; colliderless is fine now.
3. **First fleet night**: 3–5 user-picked interiors via run_fleet —
   doubles as the unproven multi-scene-execute proof.
4. **Worlds gate** (which of 318 are worth running) — user's design
   question, untouched by request.
5. pipeline_map.html card notes for S4 shopping / PLACE / JIGGLE /
   CHECK are stale w.r.t. 115–127 — map edits need user blessing
   (pipeline-viewer-authority), so bring exact proposed text.
6. PARKED.md unchanged otherwise (ctop, J9 pictures, slanted walls,
   sub rounds, re-shop).

## 6. WHERE EVERYTHING IS

Same table as SESSION_2026-08-25C §6, plus: this evening's record =
REVIEW_LOG R-S2-110..127; batch arithmetic = docs/GO_NOGO_100_BATCH.md;
collider plan (complete) = docs/PLAN_COLLIDER_OPTIONAL.md; floor review
page = …\marble-harvest\catalog\FLOOR_DEVIATION_REVIEW.html.
