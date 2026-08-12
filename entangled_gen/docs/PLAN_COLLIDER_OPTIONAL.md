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

**The prize:** 29 runnable worlds today; ~313 after (318 downloaded,
minus the 5 known frame failures — and those 5 can no longer be
detected, see OPEN QUESTION 1).

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
- Whether the 284 worlds are *good rooms*. They pass the frame question;
  nobody has looked at them. `catalog\CORPUS_REVIEW.html` is where that
  review would go.
- Anything in `docs/PARKED.md`.

---

## OPEN QUESTIONS — for the user, none blocking

1. **The 5 known frame failures become invisible.** `363c0b4f` is
   genuinely broken (collider floating 3.83 m above every splat, zero
   splats within 25 cm of that face). Once colliders are optional, a
   world like that with no collider ships a complete, confident, wrong
   scene. Options: keep refusing the 5 that are known bad by ID; or
   accept it and rely on the header sweep. **Recommendation: keep the
   check wherever a collider exists** (already in step 1), and blocklist
   those 5 by ID. It costs nothing and preserves every check currently
   held.
2. **Should `floor_source: "splat"` be reported in
   `scene_gate.quality_notes`?** It never fails a scene, but it is
   exactly the kind of number that lets 300 runs be sorted afterwards —
   the same treatment `slice_fallback` gets.

---

## PROGRESS LOG

- **2026-08-11, written, not started.** Audit above is a code read; no
  colliderless scene has been run. The claim holds until `fresh03`
  finishes.
