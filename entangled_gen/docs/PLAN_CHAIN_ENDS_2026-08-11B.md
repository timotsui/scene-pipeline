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

  Remaining in step 2 — deleting the six dead-lane stages from
  `run_scene.py` — is held until the INTAKE tuple is ready, so the repo
  never has a `--phase core` that does nothing.
