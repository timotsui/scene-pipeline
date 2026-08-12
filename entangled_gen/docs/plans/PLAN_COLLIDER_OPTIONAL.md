# PLAN — make the collider optional, and take the corpus from 29 to ~313

(Written 2026-08-11 by the orchestrator, from a code audit, at the user's
direction. NOT started. This file is the plan AND the progress log:
update it at every state change so a fresh agent can resume from it
alone. Review-log entries start at **R-S2-110**.)

## THE CONTRACT — what this work is

**What it gets:** a Marble bundle that has `splats.spz` and `prompt.txt`
but **no `collider.glb`** — 284 of the 318 downloaded worlds.

**What it decides:** where the floor and ceiling are, without the mesh
that currently supplies them.

**What a mistake looks like:** a scene runs all 45 stages, the gate says
PASS, and every box in it is measured from a floor that is not the floor.
Nothing crashes. This is the failure mode to design against — not a
crash, a confident wrong answer.

---

## WHY — the user's decision, recorded

The user ruled 2026-08-11: **trust Marble's positioning.** The collider
is the pipeline's one independent check that a bundle is the right way
up. Giving it up is the cost, it was weighed, and it was accepted.

The evidence that makes it defensible is not new: `PLAN_SCENE2_LIVING.md:207`
records a header sweep over **all 318 harvested worlds** finding one
uniform encode. That covers the 284 colliderless worlds too. The
per-world collider check was belt-and-braces on top of a corpus-wide
fact already established.

**The prize:** 29 runnable worlds today; **~318 after** — every
downloaded world, including the 5 that fail the frame contract today.
See OPEN QUESTION 1 for why those 5 come back.

---

## THE AUDIT THIS RESTS ON (2026-08-11, code read, not run)

Every consumer of the collider in the live stage tuples:

| site | what it does | breaks without it? |
|---|---|---|
| `frame_bootstrap.py:93` | refuses a bundle with no collider | **YES — stops at stage 1 of 45** |
| `frame_bootstrap.py:112` | the frame sanity check | **YES — this is the thing being given up** |
| `frame_bootstrap.py:146` | `floor_y`/`ceiling_y` from mesh bounds | **YES — the only functional use** |
| `graph/stages.py:245` | declares 2 collider artifacts | **YES — gate fails a stage that cannot write them** |
| `room_shell.py:235` | "collider agrees Δ 0.02 m" on each wall | no — evidence only, `cands[0]` picks the wall |
| `viewer/serve.py:1164` | optional mesh checkbox | no — 404s cleanly |

`amodal_boxes.py`, `collider_register.py`, `lift_pano.py` also read it and
are in **no** stage tuple.

`graph/stages.py:247` already says it: *"THE ONE STAGE THAT NEEDS THE
COLLIDER … Nothing later needs it."*

**Where the collider's floor number actually travels.** Into
`frame_bootstrap.json`, then `pano_stitch.py:72` uses it to place the eye
1.6 m up. That is the end of the line. Everything from `room_shell`
onward reads `shell["floor_y_raw"]` — measured from the splat, not
inherited (`room_shell.py:17`: *"Floor/ceiling: y-histogram peaks
(measured, not inherited)"*). Confirmed in `slicevote`, `build_edges`,
`build_judged`, `describe_nodes`, `compose/propose_edits`.

**Two facts that make the substitute cheap:**

1. `room_shell.fit_shell` consumes only the ply, `extent_p1`/`extent_p99`
   (splat percentiles) and `raw_to_render` (a constant). Nothing from the
   pano, nothing from detection. **The floor measurement can run at stage
   1.** It sits at stage 11 for its wall fit, not because it needs
   anything from stages 2–10.
2. The camera height does not need to be *right*, only *recorded*.
   `pano_stitch` writes `eye_raw` into `pano_selfrender_meta.json` and
   `pano_lift.py:69` reads it back — *"eye (defined, not estimated)"*. A
   floor estimate off by 4 cm means the virtual camera stands 4 cm
   higher, correctly recorded. It does not propagate as error.

And the mesh was never the accurate source anyway —
`frame_bootstrap.py:162` calls its floor *"skirt-level, ~3 cm outside
true surfaces."*

---

## THE WORK — four steps

### Step 1 — `frame_bootstrap.py`: stop refusing, measure instead

- `:93` — a missing collider is no longer fatal. A missing `.spz` still is.
- `:146` — when there is no collider, get `floor_y`/`ceiling_y` from the
  splat.
- Record **which way it got them** in `frame_bootstrap.json` (a
  `floor_source` field: `"collider"` or `"splat"`). Every scene must
  carry this. It is what lets 300 runs be sorted afterwards by whether
  they were measured or estimated.
- When a collider IS present, **keep both the check and the mesh floor.**
  Nothing about the 29 good worlds should change. A re-run of `fresh02`
  must produce a byte-identical `frame_bootstrap.json`.

**⚠ THE TRAP. Do not call `measure_floor_ceiling(pts)` on raw points.**
It splits the y range at its midpoint and takes the strongest peak on
each side. `room_shell.py:201-208` records what happened on
`living_marble`: floater gaussians leaking through openings, 10+ m
outside the room, dragged the split — *"the fitter called the real floor
'ceiling' and a floater cluster 'floor'."* Clip to
`extent_p1`/`extent_p99` ± `SEARCH` first, exactly as `fit_shell` does at
`room_shell.py:210-215`. Those extents come from the splat, so they are
available at stage 1.

Reuse `room_shell.measure_floor_ceiling` — do not write a second one.
Two floor estimators that can disagree is a defect waiting to happen.

### Step 2 — `graph/stages.py`: the gate must not fail an honest scene

`:245` declares `collider_registered.glb` and `collider_registration.json`
as artifacts of the `frame` stage. A colliderless scene cannot write
them, and `scene_gate.after()` fails the stage for it — correctly, by its
own rules. Make the declaration conditional, or move those two files to a
form the gate treats as optional.

**Do not weaken the gate generally to fix one stage.** The no-op trap is
the reason the gate exists.

### Step 3 — the proof: a colliderless scene, end to end

`fresh03`, from a bundle with no collider that has never been run. Not a
clone. `PLAN_CHAIN_ENDS_2026-08-11B.md` lists six defects that only a
genuinely fresh scene could find, five of them the same shape: *code that
works because the dev scene carries an artifact the pipeline no longer
produces.* A clone proves nothing here.

**Before the run the user must set the GPU clock lock in an ADMIN shell:
`nvidia-smi -lgc 0,1500`.** The machine hard-powers-off under GPU burst
without it (`docs/POWER_CRASHES.md`, four crashes on 08-10). The lock
does not survive a reboot.

Budget from `fresh02`: intake 872 s, record+judge 346 s, graph ~330 s.

### Step 4 — the number that says it worked

Run the corpus census again and update
`week8\marble-harvest\catalog\` — `build_catalogue.ps1` still reports
"Runnable: 29" and would be wrong the moment step 1 lands.

---

## WHAT COUNTS AS EVIDENCE

**The gate passing is not enough.** The gate checks machinery, never
whether an answer is good, and a wrong floor passes every check in it.

The claim to prove is: **a colliderless scene's floor agrees with a
collidered scene's floor.**

The test that proves it costs nothing: take the 29 worlds that HAVE a
collider, measure the floor both ways, and compare. That is 29 paired
measurements of the same rooms, and the spread is the honest error bar on
every colliderless scene the pipeline will ever run. Do this in step 1,
before `fresh03` — it is cheap, it needs no GPU, and if the two disagree
by more than a few cm on any world, this plan is wrong and should stop.

Report the spread. Do not tune anything to make it smaller.

---

## DELIBERATELY NOT IN THIS PLAN

- **The harvester's collider step.** Separate question, possibly free
  corpus: the 284 manifests contain **no collider URL at all**, so the
  extractor never saw one offered — this is not a failed download of a
  known file. Collider availability tracks pano availability almost
  exactly (33 of 34 have both; same download menu), and the colliderless
  worlds skew old (155 of them "11 months ago"). Worth one experiment —
  re-harvest 2–3 colliderless worlds and see whether a collider URL
  appears now. If it does, the ceiling of 34 was a harvest bug and the
  check survives. **Cheap, and it does not block this plan.**
- **The worlds gate needs more work (user, 2026-08-11).** Deciding which
  worlds are worth running is a separate design question, and this plan
  deliberately does not touch it. All this work does is stop the frame
  contract from standing in for that decision, which it was never fit to
  do. `catalog\CORPUS_REVIEW.html` is where that review would go.
- Anything in `docs/PARKED.md`.

---

## OPEN QUESTIONS — for the user, none blocking

1. ~~Blocklist the 5 known frame failures.~~ **SETTLED BY THE USER
   2026-08-11 — do not do this.** The earlier draft of this plan called
   `363c0b4f` a "genuinely broken world" because its collider floats
   3.83 m above every splat in the scene. That was wrong, and the user
   corrected it: **a collider that disagrees with its splat says the
   COLLIDER is wrong, not the world.** The splat may be perfectly good.
   The frame contract was only ever a check that two files agree — it
   was never a judgement about whether a room is worth running, and
   nothing in this work should treat it as one.

   Consequence: **the 5 frame-FAIL worlds become runnable too.** The
   corpus target is ~318, not ~313. Keep the check where a collider
   exists (it still catches a real disagreement worth logging), but it
   must not refuse the scene once the collider is optional.
2. **Should `floor_source: "splat"` be reported in
   `scene_gate.quality_notes`?** It never fails a scene, but it is
   exactly the kind of number that lets 300 runs be sorted afterwards —
   the same treatment `slice_fallback` gets.

---

## PROGRESS LOG

- **2026-08-11, written, not started.** Audit above is a code read; no
  colliderless scene has been run. The claim holds until `fresh03`
  finishes.

- **2026-08-11, user ruling folded in.** A disagreeing collider condemns
  the collider, not the world — see OPEN QUESTION 1. The blocklist
  recommendation is withdrawn, the 5 frame-FAIL worlds are back in, and
  the target is ~318. The worlds gate is named as separate work. Handed
  to the next session; nothing has been edited in code.

- **2026-08-11C, STEP 1 RAN AND ITS STOP RULE FIRED. WORK STOPPED, no
  code edited. AWAITING THE USER'S RULING.** (REVIEW_LOG R-S2-110 is the
  full record.) All 34 collider worlds measured both ways, replicating
  exactly the code this plan would ship (fit_shell's clip +
  `room_shell.measure_floor_ceiling`, imported). The 29 frame-PASS
  worlds: **median |Δfloor| 3.6 cm, 24 of 29 within 12 cm**, sign
  uniformly the documented skirt offset. **Five exceed 10 cm** (d2f4cb95
  0.11, 220c321e 0.27, 36fa9852 0.34, 28d61433 0.56, 6425f0fd 2.24 — the
  last is the Lisbon OUTDOOR street, not a room), so by this plan's own
  rule the work stopped before any edit.
  **The diagnosis inverts the assumption:** slab counts show the
  COLLIDER floor hanging below a level where the splat has little or no
  mass on every outlier (36fa9852: 13 points at the mesh floor vs
  310,632 at the splat peak) — the mesh skirt is the wrong one, the same
  shape as the ruling above. Two structural facts for the ruling:
  room_shell already measures the canonical floor with this same
  function at stage 11 (so downstream boxes on the outliers already use
  the splat number today), and the collider floor travels only into the
  pano eye height (on 28d61433 today the camera stands ~2.15 m above the
  real floor and the world counts as runnable).
  **Also found:** the audit table above missed a consumer —
  `run_scene.py` `BUNDLE_NEEDS` (~:363) refuses a colliderless bundle at
  `--bundle` adoption. Add it to the step list when work resumes.
  Data: `floor_pairs.jsonl` + scripts in the 08-11C session scratchpad
  (path in R-S2-110).

- **2026-08-11C, later. USER: interiors only for now.** The two outdoor
  street worlds (6425f0fd, 8a62c661) are out of the decision. A visual
  review page was built for the ruling — scene photo + splat X-ray side
  view with both floor lines per world:
  `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week8\marble-harvest\catalog\FLOOR_DEVIATION_REVIEW.html`.
  Interior picture: 24 of 27 interior frame-PASS worlds agree within
  12 cm; deviants are d2f4cb95 (11 cm), 220c321e (27), 36fa9852 (34),
  28d61433 (56) + interior frame-FAILs 6040d57f (24), 4378be67 (121),
  363c0b4f (457); 77eda2e2's floors agree (2.4 cm — its failure is a
  side wall). On every deviant the collider floor runs through near-empty
  space. Still stopped; awaiting the ruling.

- **2026-08-11C, USER RULING: "splat floor wins." STEPS 1–2 BUILT AND
  VERIFIED (REVIEW_LOG R-S2-111).** One floor source everywhere: every
  scene measures floor/ceiling from the splat with room_shell's own
  clip + histogram (imported, one estimator by construction); a present
  collider still runs the agreement check and is registered only on
  PASS — a FAIL condemns the collider, prints loudly, and the scene
  continues colliderless. Five files: frame_bootstrap.py, stages.py
  (`artifacts_optional`), scene_gate.py, run_scene.py (BUNDLE_NEEDS —
  the audit-gap consumer), scene_scale.py (collider-conditional
  rescale). The fresh02 byte-identity test is superseded by the ruling
  (field-diff verified instead: only floor_y/ceiling_y + the two new
  record fields differ). Three throwaway-scene path tests + in-process
  gate checks PASS; final gates of fresh02/autotest_living/
  autotest_bedroom unchanged.
  **REMAINING: step 3 (fresh04, a never-run colliderless world, end to
  end — queued behind the fresh03 collider-world proof run now in
  flight) and step 4 (rebuild the catalogue).**

- **2026-08-11C, later. Step 4 DONE early** (the code landed, so the
  catalogue was already wrong): build_catalogue.ps1 reworked — runnable
  = downloaded and kept (**318**), collider status is now a property
  (29 agree / 5 condemned / 284 none), "frame FAIL" badge renamed
  "collider condemned". Summary states the worlds gate stays open.
  **Step 3 update:** fresh03 (collider world 44205719) ran 33 stages
  clean then hit the connector-wall defect class in compose
  (supported_by + snap, third and fourth readers; fixed scene-
  agnostically, R-S2-112). fresh04 = 0f874584 (colliderless vintage
  bedroom, box room, never run) is picked and queued; it carries BOTH
  proofs: the one-command bar and the colliderless path.

- **2026-08-11C, night. ✅ THE PLAN IS COMPLETE (R-S2-114).** fresh04 —
  colliderless, never run — completed ALL 46 stages from one command
  with zero intervention, final gate PASS, 65.3 min. Every designed
  colliderless behavior ran live: splat-measured floor, INFO gate lines
  for the absent collider files, measure-only scale branch, furnished
  room, 35/35 nodes pictured, 2/39 slice fallbacks. All four steps of
  this plan are done: paired test (110), the code (111, plus the
  connector fixes 112/113 fresh03 forced), the proof (114), the
  catalogue (Runnable: 318). Batch readiness: `docs/GO_NOGO_100_BATCH.md`.
