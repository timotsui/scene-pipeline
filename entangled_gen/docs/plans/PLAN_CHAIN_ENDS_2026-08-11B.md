# PLAN — make the chain start at the beginning

(Real date 2026-08-11, session B. Owns the work listed in
`SESSION_2026-08-25B_HANDOFF.md` §5f and §6b. This file is the plan AND
the progress log: update it at every state change, so a fresh agent can
resume from it alone.)

## THE GOAL

A pipeline that runs top to bottom, unattended, over 100 fresh Marble
bundles, as designed.

## THE STATE THIS PLAN STARTS FROM

From a raw bundle, **nothing runs unattended**. The middle third
(vote → grouped → composed) is wired, gated, timed and resumable.
Everything before it — intake, the pano funnel, and the whole
record → judged → resolved half — is about twenty hand-run commands that
no script contains.

Do not repeat the claim that the pipeline runs 100 scenes.

---

## GROUNDING DONE BEFORE ANY EDIT (2026-08-11B, verified on disk)

Three corrections to the handoff, each checked rather than assumed.

**1. §5f item 1 is already fixed.** `run_scene.py:825` is no longer a
`NameError` — commit `99070c5` fixed it. The file parses; line 825 is
inside the fit-loop fallback string.

**2. §5b's "four globs" is one glob once the lane is decided.**

| site | lane | reached on a fresh bundle? |
|---|---|---|
| `seg_pano_overlay.py:41` | dead | only if the dead lane runs |
| `lift_pano.py:91` `*_collider.glb` | dead | same |
| `lift_pano.py:250` `*_pano.png` | dead | same |
| `crop_pano.py:79` `*_pano.png` | LIVE | only when `--pano` is omitted, and the map's invocation passes `--pano rig_sp0/pano_selfrender.png` |

Fixing all four before deciding the lane would have been three fixes to
code that should not run at all. This is the ordering the session prompt
warned about, and the warning was right.

**3. §6b is safe — the thing that would have made it lossy does not
hold.** `build_voted.py:209` calls `edge_carry.carry()`, which
RE-DERIVES geometry through `build_edges.derive_edges`
(`edge_carry.py:259`) and writes
`graph["voted"] = {nodes, edges, nesting, …}` (`build_voted.py:243`).
`nesting` — the facts J0 triages on — is already in the voted layer. So
`rederive_voted_edges.py` reproduces, in a half-layer, what the whole
layer already carries.

**4. The ceiling is 34, re-counted.** `week8/marble-harvest/worlds/`:
323 worlds, 318 `prompt.txt`, 318 `.spz`, **34 `collider.glb`**, 36
`pano_rgb_0.png`. `frame_bootstrap.py:61` refuses without a collider.
Note `pano_lift.py` does NOT need the collider — it lifts against the
ply (`pano_lift.py:77`) — so the collider requirement lives entirely in
intake's frame contract.

---

## THE DECISION THAT UNBLOCKS EVERYTHING ELSE — what `--phase core` IS

**Ruled by the user 08-11: the map is generally correct, and things
marked stale leave the core pipeline.** Applied here deliberately.

`pipeline_map.html` draws ONE intake lane, and every downstream stage
reads its outputs:

```
1 · WORLD generate (Marble bundle)  →  INTAKE frame_bootstrap.py
P1  pano_stitch.py                     rig_sp0/pano_selfrender.png
P2  crop_pano.py --pano … --out-dir rig_sp0/crops
2v  vocab_build.py
2b  pano_bearings.py                   rig_sp0/vocab_bearings.json
P3  seg_batched.py                     rig_sp0/seg_batched20/detections.json
P4  pano_lift.py                       rig_sp0/lift_poolc.json
P5  pano_recenter.py --suffix c        scene_manifest_pano2c_rc.json (108)
P6  manifest_filter.py --thr 0.30      …_rc_f30.json (102, adopted)
N1  scene_scale.py
4w  room_shell.py
4g1 graph/build_graph.py
```

`--phase core` in `run_scene.py` runs a DIFFERENT lane: `crop_pano`
(default out-dir) → `vocab_from_prompt` → `seg_views` →
`seg_pano_overlay` → `lift_pano` → `manifest_pano_to_raw`, writing
`pano_crops/`, `seg_pano/`, `scene_manifest_pano.json`. That is
`PIPELINE.md`'s "pano path — week8 object-ID lane (alternative stages
2–4)". **Nothing downstream reads any of its outputs**, and
`out/living_marble/` — the scene the whole chain was verified against —
has no `pano_crops/` and no `seg_pano/` at all.

**DECISION: `--phase core` becomes the map's lane. The other six stages
leave the runner. Their module files stay on disk**, the same treatment
the user's own §6b ruling gave `rederive_voted_edges.py`.

`envelope.py` is NOT in the tuple: the map parks it 07-26 and draws it
with no outgoing arrow.

**The one thing that breaks if this is done carelessly.**
`compose/pick.py:139` builds the room's mood sheet from `pano_crops/` —
a dead-lane output. Delete the lane without repointing it at
`rig_sp0/crops` and the model choosing every asset is shown four blank
white squares on every scene, permanently, instead of only on
`living_marble`.

---

## THE ORDER OF WORK

| # | step | who | state |
|---|---|---|---|
| 1 | §6b — retire `voted_edges` + the `graph['vote']` block | orchestrator | |
| 2 | apply the lane decision: dead lane out, `pick.py` repointed | orchestrator | |
| 3 | `INTAKE` tuple in `stages.py`; `slicevote` derives its filenames | orchestrator + agent | |
| 4 | `RECORD` tuple + the three missing order refusals | agent | |
| 5 | a producer for `bundle_path.txt` | agent | |
| 6 | the honest test: a bundle that has never run, end to end | orchestrator | |

`stages.py` edits stay with the orchestrator — it is the authority file
and three writers would collide.

### Deliberately not in this plan

- the harvester's collider step (§5c) — harvesting, not wiring
- the five undeclared compose loop-back files (§4b) — needs a ruling
- `support_clip`, sub rounds (PH2r) — both wait on a user ruling
- `ctop` and anything specific to J9 — `docs/PARKED.md`

---

## WHAT COUNTS AS EVIDENCE

A pass on `autotest_bedroom` does not mean the chain works. That scene
is a clone carrying hand-fixes that steer the result — `snap_rulings.json`
pins marked `USER_RULING` that outrank the model, `fit_walk.json`
overriding the picks, `rotation_check.json`, `fit_feedback.json`, a prior
`fitted_preview.json`. None is declared in `stages.py`. A fresh scene has
none of them and gets a different answer with no crash and no warning.

**Any claim of the form "the pipeline works" must be backed by a scene
that has never run before, or it is not evidence.**

Before step 6 the user must set the GPU clock lock in an ADMIN shell —
`nvidia-smi -lgc 0,1500`. The machine hard-powers-off under GPU burst
without it (`docs/POWER_CRASHES.md`; four crashes on 08-10). `-pl` is
OEM-locked, and the lock does not survive a reboot.

---

## OPEN QUESTIONS THIS WORK RAISED — for the user, none blocking

1. **Should `pick` REFUSE on a blank mood sheet?** Today it degrades
   loudly (fixed 08-11B — it was degrading silently). A scene whose rig
   crops are missing would have every asset chosen with no sense of the
   room's style, and still pass the gate. Refusing would block the
   scene; counting it in `scene_gate.quality_notes` beside the
   slice-fallback number would not. Not invented either way here.
2. Still open from the handoff §7 and untouched: `support_clip`, sub
   rounds (PH2r), `fit_feedback`'s re-shop scope, the five undeclared
   compose loop-back files (§4b), the paper's metric.

---

## PROGRESS LOG

- **2026-08-11B, opened.** Read the handoff, `PARKED.md`, `stages.py`,
  the map, `PIPELINE.md`. Grounding above verified on disk. Plan agreed
  with the user: all six steps this session, steps 3–5 delegated.

- **STEP 1 DONE** — `b8f87f2`, REVIEW_LOG R-S2-91. §6b A–D all four.
  The half-layer is out of the chain, the loop-back judges read the
  voted layer via a new `scene_state.judge_view()`, `graph['vote']` is
  retired across its four readers, and `vote_doubts.json` is the one
  copy.

  **It uncovered a defect worth more than the retirement.**
  `edge_carry.py:176` handed `wall_claim_dist` a wall's `plane` where
  the function reads `geometry["plane"]` and `geometry["extent"]`
  itself, so every wall lookup missed and **every layer from `voted`
  onward carried zero IN_WALL edges** — 18 missing on living, 24 on
  bedroom, against 19 in `resolved`. Silent, because the layers had no
  wall edges to be stale. Compose reads `grouped`; a wall-mounted object
  arriving with no IN_WALL edge has nothing holding it up. Same two
  lines also dropped W5 connector segments.

  After the fix the retirement proved itself: the voted layer's
  re-derived edges match `graph['voted_edges']` **pair for pair** on
  both scenes (85 and 145 edges, zero difference).

  Also caught before it shipped: vote-exempt nodes reach J8 without
  `tiers`/`slice`, which the retired block defaulted and the docket card
  joins unguarded — living's `obj_018` exactly. Defaulted; docket now
  verified identical to the old one on all three scenes.

  ⚠ **The layers ON DISK are not fixed by this.** Every existing scene
  still has zero IN_WALL from `voted` on until its chain is re-run. The
  fresh-scene run is what will show the corrected numbers.

- **STEP 2, first half** — `2a3c351`. `compose/pick.py`'s mood sheet
  read the retired lane's directory, so the model choosing every asset
  saw four blank squares; repointed at `rig_sp0/crops` and the
  degradation made loud. Added `paths.rig_dir` / `rig_crops_dir`.
  `crop_pano.py`'s bundle fallback now resolves harvest bundles instead
  of raising a bare `StopIteration`.

- **STEPS 2 AND 3 DONE** — `f496c99`, R-S2-93. `--phase core` walks
  `stages.INTAKE`, the map's lane. The dead lane's six stages and their
  hand-written driver are out of the runner; the modules stay on disk.
  The funnel's flags are named constants and its filenames derive from
  them.

  Two gate bugs found doing it. **`scene_gate` loaded `scene_graph.json`
  unconditionally, and the whole funnel runs before that file exists —
  the first genuinely fresh scene would have died at its first stage.**
  Undiscoverable on a dev scene. And `stale_inputs` walked `CHAIN` only,
  so COMPOSE's `inputs` were decorative; now it walks all four and
  immediately found two of §4b's five contaminating files stale on
  `autotest_bedroom`. File stages report WARN, not FAIL — two findings
  are structural false positives (`scene_scale` rewrites its own input in
  place; the closing pass rewrites `rotation_check`'s).

- **STEP 4 DONE** — `045f9a5`, R-S2-94. `RECORD` is a fourth tuple and
  `--phase record` a fourth phase. `--phase graph` keeps meaning "the
  vote onward". Also: **`run_fleet --phase` offered only
  `("core","graph","all")`** — the hundred-scene driver could not be
  asked for compose at all. Both runners now read one
  `stages.PHASES_ORDER`.

- **STEP 5 DONE** — `3435216`. `--bundle` creates the scene and writes
  `bundle_path.txt`, refuses to repoint an existing scene, and refuses a
  bundle with no prompt, splat or collider.

- **THE CHAIN IS UNBROKEN.** One command plans **45 stages**: 11 intake,
  10 record+judge, 12 graph, 12 compose. Verified on a real unclaimed
  harvest world — `--scene fresh01 --bundle <uuid>` produced a scene
  directory containing one file and a complete plan to the end.

- **THE GPU LOCK IS ON, AND IT IS NOW MEASURED RATHER THAN ASSUMED.**
  Sampled during the `detect` burst on the live run: 16 samples above 30%
  utilisation, **peak exactly 1500 MHz, peak 89.6 W**. That matches
  `POWER_CRASHES.md`'s locked figure (93.8 W) against the ~190 W
  transients seen unlocked. This is the empirical proof R-S2-95 said was
  the only kind available.

- **STEP 6, FIRST ATTEMPT — `fresh01`, FAILED AT STAGE ONE.** R-S2-96.
  The machinery was right and the bundle was rejected: a deliberate
  refusal, gate caught it, run log written. Which led to:

- **THE FRAME CONTRACT WAS REJECTING 20 OF 34 WORLDS FOR THE WRONG
  REASON.** R-S2-97/98. With no trimming and no margin, **33 of 34
  colliders sit entirely inside their splat** — the frames are fine. The
  0.5th-percentile crop was discarding thinly-rendered corners. On the
  world that failed, the rejected face had 1,173 splats within 25 cm.
  USER RULING: loosen it. Applied on the PERCENTILE (0.5 -> 0.05),
  **not** the margin, which stays 0.5. Re-measured against the shipped
  code: **29 of 34 pass**, and the five that fail do so by 0.61–3.98 m,
  none marginally.

- **THE CATALOGUE NOW SAYS WHAT IS RUNNABLE**, which it never did — it
  showed `downloaded`, and downloaded is not runnable. Files (this tree
  is NOT a git repo; the harvest folder is data by convention):
  - `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week8\marble-harvest\tools\build_catalogue.ps1`
  - `…\catalog\frame_contract.json` (the measurement, per world)
  - `…\catalog\CATALOGUE.html` — badges + Runnable / Frame FAIL / No collider filters
  - `…\catalog\MASTER_catalogue.csv`, `DOWNLOADED_catalogue.csv` — two new columns
  - `…\catalog\_CATALOGUE_SUMMARY.md`

  **29 runnable · 5 blocked · 284 downloaded with no collider at all.**
  The collider, not this check, is what caps the corpus at 34 of 318.

- **⭐ STEP 6 — `fresh02` (`188a1d3f`, a rustic attic bedroom). THE
  MEASUREMENT HALF IS DONE AND THE FINAL GATE PASSES.** R-S2-99..104.
  33 of 45 stages from a bundle that had never been downloaded into a
  scene: intake 11/11 (872.7 s), record+judge 10/10 (345.6 s), graph
  chain 12/12 (~330 s). `[gate] PASS: final state of fresh02` — ended on
  `grouped`, nothing stale, evidence layer whole 28/28.

  ```
  record   52 nodes  102 edges  IN_WALL 29
  judged   37         85                27
  resolved 31         64                23
  voted    31        101                31
  settled  28         77                27
  shown    28         77                27
  grouped  28         82                27   (+5 SAME_PRODUCT)
  ```

  **The IN_WALL column is the point.** Before this morning every number
  from `voted` down would have been 0. This scene never contained the
  broken code.

  Compose (12 stages) is running.

---

## WHAT THE FRESH SCENE FOUND — six defects, and why a clone could not

Every one of these had been in the repo for weeks or months, and every
one was invisible on `living_marble`, `bedroom_marble` and their clones.
Five share a single shape: **code that works on a dev scene because that
scene carries an artifact the current pipeline no longer produces.**

| # | defect | why no clone could find it |
|---|---|---|
| 1 | `edge_carry` passed `wall_claim_dist` a plane where it wanted a geometry — **every layer from `voted` down carried 0 IN_WALL edges** | nothing crashed; the layers genuinely had no wall edges to be stale |
| 2 | `scene_gate` loaded `scene_graph.json` unconditionally — **would have killed the first fresh scene at its first stage** | every dev scene already has a graph |
| 3 | `pick`'s mood sheet read the retired lane's crop directory — **every asset chosen against four blank squares** | `bedroom_marble` still has the old `pano_crops/` |
| 4 | `build_graph` required `envelope.npz`, which the funnel correctly no longer produces | every dev scene has a leftover `envelope.npz` |
| 5 | `split_cuts` hard-required the retired `graph['voted_edges']` | every dev scene still has the block |
| 6 | `recut_rect` inverted its rectangle for a box projecting off-frame, **killing a stage after its layer was committed** | a geometric edge case no curated scene had produced |

Plus one I introduced and the same scene caught within minutes: the
`stale_inputs` extension told the operator to re-run `build_judged`,
which the design forbids because it would sweep the vote stale.

**The lesson for the next session, in one line: a passing run on a clone
is not evidence, and this is the list of what it hides.**

## THE RULINGS OF 2026-08-11B (late) — every open issue settled or parked

| issue | ruling | state |
|---|---|---|
| global vocab dictionary | **approved** | live |
| `grouped` inherits `shown` | **fix — "a core function"** | fixed, 28/28 on fresh02 |
| `prep_scene` | **make it a stage** | `prep_viewer`, last in COMPOSE |
| `support_clip` | **retire** | banner on the file, tuple note updated |
| `propose_edits` cache | **agree** | per-scene call cache, same shape as its neighbours |
| `fit_feedback` re-shop | **do not build** — asset library quality is out of scope; the pipeline only needs to prove rich + functional | PARKED.md §5 |
| paper metric | decide **after a batch works** | deferred |
| slanted walls / pitched roofs | defer | PARKED.md §3, with the fresh02 measurement |
| sub rounds (PH2r) | defer until a batch runs clean | PARKED.md §4 |
| ctop, J9 | stay parked; J9 "fine as long as it kind of works" | unchanged |
| **world selection** | **THE ONE REMAINING JUDGEMENT** — the user reviews `CORPUS_REVIEW.html` (29 runnable · 284 no collider · 52+65 skipped/unsure) | waiting on user |

## STILL OPEN — for the user, none blocking

- **Should a review-artifact crash fail its stage?** (R-S2-103) Defect 6
  killed `evidence` after `shown` was written and stamped; the runner
  said CRASH and the gate said the layer was whole, and both were right.
  Over a hundred scenes that costs scenes that actually succeeded.
  Wrapping report builders changes what "a stage failed" means, so it is
  a policy call, not a bug fix.
- **`vocab` is the most expensive stage in the funnel (293 s) and is
  uncached** — ~6 haiku calls every scene, re-spent on every re-run.
  The obvious lever if 100 scenes need to be cheaper.
- The frame-contract margin question is SETTLED (percentile 0.05,
  29/34 runnable) but the user's words were "widen the margin" and it
  was applied to the percentile — see the note at the top of R-S2-98.
