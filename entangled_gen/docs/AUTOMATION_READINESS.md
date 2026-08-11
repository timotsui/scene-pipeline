# RUNNING THE GRAPH CHAIN UNATTENDED — how to run it, and what is still broken

> ⚠ **PARKED ITEMS live in [PARKED.md](PARKED.md)** — the top-view
> (`ctop`) problem and everything specific to J9 were parked by user
> ruling 2026-08-11. They are counted and reported on every scene, and
> are deliberately not being worked on.


Written 2026-08-11, rewritten the same day after the work in
`docs/PLAN_AUTOMATION_2026-08-11.md` landed. The goal this serves is
Rule #1: **the pipeline runs itself over ~100 scenes with no human in the
loop.**

The first version of this file said the chain was not automatable and
listed what to fix. That is done. **The eleven hand-typed commands are
gone, the flags are inverted, and a gate runs between every stage.** If
you are holding an old command line from a handoff or from shell history,
read §3 before you use it — the flags on it no longer mean what they used
to.

---

## 1. HOW YOU ACTUALLY RUN THIS

One scene, both phases, end to end:

```
python run_scene.py --scene living_marble
```

Many scenes, one after another, with nobody watching:

```
python run_fleet.py --scenes bedroom_marble,living_marble
python run_fleet.py                     # every scene with a splat on disk
```

With no `--scenes` and no `--scenes-file`, the fleet takes
`paths.gen_scenes()` — every folder under `out/` that has a `gen_raw.ply`.
Names are checked against disk BEFORE anything runs, so a typo costs you a
second and not a night.

### run_scene.py — the useful options

| flag | when you reach for it |
|---|---|
| `--scene S` | required, except with `--list`. |
| `--phase core\|graph\|all` | `core` = pictures to 3D boxes. `graph` = the vote to `grouped`. Use `graph` when the geometry is already built and you only want the chain. |
| `--from K` / `--until K` | re-run a slice of the graph chain, e.g. `--from settled --until j9` after fixing something in the middle. Keys come from `graph/stages.py`. |
| `--skip a,b` | drop named stages. One flag covers both phases — core names and graph keys both work. An unknown name stops the run instead of being ignored. |
| `--no-llm` | run only the free stages. Use it to shake out plumbing without spending model calls. The scene will NOT be complete, the final gate is skipped, and the summary says so loudly. |
| `--dry-run` | print every command and every gate check that WOULD happen, and execute nothing. Use it before a long night. |
| `--list` | print the chain as a table and exit. No scene needed. |
| `--continue-on-fail` | keep going after a failure and report all of them, instead of stopping at the first. |
| `--box-thr F` | GroundingDINO box threshold for the core `seg` stage (default 0.35). |

### run_fleet.py — the useful options

| flag | when you reach for it |
|---|---|
| `--scenes a,b` / `--scenes-file f` | an explicit list. The file takes one name per line; `#` comments and blank lines are ignored. |
| `--exclude a,b` | drop scenes from whichever list you gave. |
| `--resume` | skip every scene whose final gate ALREADY passes. A fleet interrupted at scene 60 restarts without redoing the first 59. |
| `--scene-timeout S` | seconds one scene may take before it is killed and recorded as `timeout`. Default 4 hours; `0` means no limit. This is the outer bound on a wedged scene. |
| `--stop-on-fail` | stop the whole fleet at the first scene that does not pass. Off by default, on purpose: one bad scene must not stop the night. |
| `--dry-run` | print the plan — scene list, per-scene command line, timeout, report paths — and run nothing. |
| `--phase`, `--from`, `--until`, `--skip`, `--no-llm`, `--box-thr` | passed straight through to `run_scene.py` and mean there exactly what they mean there. |

Every fleet writes `out/fleet_<runid>.json` and `out/fleet_<runid>.html`:
one row per scene with its verdict, its time, the stage it died on, and
the gate's WARN/INFO lines. That page, not console scrollback, is what
you read in the morning. Each scene also writes
`out/<scene>/run_scene_<utc>.json`.

---

## 2. THE CHAIN IS NO LONGER WRITTEN DOWN HERE

The old version of this file listed eleven commands with their flags.
That list is gone, because a list in prose cannot be executed, checked or
resumed, and a second copy of it goes stale the day someone edits the
first.

**The order is data in `graph/stages.py`.** One row per stage: the layer
it reads, the layer it writes, the files it must produce, whether it
spends model calls, whether it wants the GPU. `run_scene.py` walks that
table; the eleven commands appear nowhere in it. To see the chain:

```
python run_scene.py --list          # or: python graph/stages.py
```

Two pieces of hard-won reasoning live in that order and are worth keeping
in front of you. Both are also written in `stages.py` next to the rows
they explain.

**`materialize_layers` runs TWICE, and the `--settle-only` one must come
first.** The same module writes `settled` with `--settle-only` and
`grouped` without it. `grouped` is J9's own output. Run the full one
early and you write `grouped` from a state J9 has never seen — the
mistake made by hand on 08-11, and why `grouped` ended that night marked
stale. Geometry first, group last.

**`node_evidence` reads `settled` BY NAME, never "whatever is current".**
Its output is the evidence J9 judges on, and `grouped` is J9's verdict.
Evidence taken from `grouped` would hand J9 back its own answer as proof
of itself. This is also why the gate requires a stage's input layer to be
"present and fresh" rather than "current": re-running a middle stage while
a later layer exists is legal, reading a STALE layer is not.

---

## 3. THE FLAGS ARE INVERTED NOW

Six stages used to do nothing without a flag and exit 0 doing it. That is
fixed by turning it round: **writing is the DEFAULT everywhere.**

| stage | how you opt OUT of the work now |
|---|---|
| `record_vote_doubts` | `--dry-run` |
| `build_voted` | `--dry-run` |
| `rederive_voted_edges` | `--dry-run` |
| `materialize_layers` | `--dry-run` |
| `node_views` | `--no-render` |
| `node_evidence` | `--dry-run`, `--no-recut`, `--no-reshoot` |

`node_evidence` also has `--allow-holes` (see §4).

**THE OLD FLAGS STILL PARSE AND DO NOTHING.** `--apply`, `--render`,
`--recut` and `--reshoot` are still accepted so that no old script, doc or
handoff crashes — but they are no-ops. This matters in one direction:
an old command line does not fail, it just quietly does more than the
person who wrote it expected. `node_views.py --scene S` renders;
`node_views.py --scene S --render` renders too and always did. But
`node_evidence.py --scene S --apply` now also recuts and reshoots.
Nothing silently does LESS than it looks like, which is the failure mode
that mattered, but do not read an old line as documentation.

---

## 4. THE GATE — `graph/scene_gate.py`

The gate asks the questions no stage can answer about itself, and it asks
them between every pair of stages.

```
python graph/scene_gate.py --scene S --report          # the whole scan
python graph/scene_gate.py --scene S --final           # did the run finish
python graph/scene_gate.py --scene S --before evidence
python graph/scene_gate.py --scene S --after evidence --since <epoch>
```

- `--before K` — the layer stage K reads is present and NOT stale.
- `--after K` — stage K wrote the layer, the graph blocks and the files it
  promised, and (with `--since`) wrote them DURING this run. The mtime
  test is the generic way to catch a stage that exits 0 having done
  nothing: a file that merely exists proves only that some earlier run
  made it.
- `--final` — the chain ended on `grouped`, no layer is stale, and the
  evidence layer is whole.
- `--report` — the per-stage scan plus the final check, read-only.

### Exit codes

| code | meaning |
|---|---|
| 0 | pass |
| 1 | an ordinary crash |
| 2 | `node_evidence` REFUSED: the evidence layer would have had holes |
| 3 | a gate failed |

`run_scene.py` uses the same four, and passes a stage's 2 through so a
fleet can tell a refusal from a crash. Its own usage errors leave by the
crash door (1) rather than argparse's default 2, so a typo is never
mistaken for a refusal.

### FAILURE versus WARN/INFO — the important distinction

**The gate checks the MACHINERY, not the answers.** A box can be legal
and wrong. So:

- **FAIL** = something is broken. The scene stops. Missing layer, stale
  layer, promised file not written this run, chain did not end on
  `grouped`, evidence layer with holes.
- **WARN / INFO** = a quality number. It is recorded on the scene, shown
  in the fleet table, and **never fails a scene.** Where the acceptable
  line falls is the user's judgement, not the gate's.

The quality numbers it reports (`scene_gate.quality_notes`):

| line | what it means |
|---|---|
| INFO — N nodes fell back to a full-height wedge | the plan view found nothing, so nothing re-measured the box and it shipped roughly as it arrived. This is the §5.1 `ctop` defect, counted per scene. |
| WARN — N SAME_CANDIDATE edges have no verdict | the vote moved boxes into a new "these might be one object" pair, and no judge in the chain answers a candidate raised after the vote. They ship as separate objects. See §5.4. |
| WARN — the vote is not canon-eligible | the vote run was partial (`--only`) or merged boxes from more than one code revision. Everything built on top inherits that. |
| WARN — J8 / J8s / J9: N of M verdicts DEFAULTED | the call failed and a default was recorded instead of a decision. One is noise; forty means a token expired and the scene is confident-looking fiction. |
| INFO — N nodes carry a supplementary view with occluders deleted | the judge saw the object unobstructed, which a photograph would not be. |

---

## 5. THE SCAN — the gate does it for you

The old version of this file had five hand-typed python one-liners here.
They are gone. `scene_gate.py --report` runs all of them:

- live layers, stale layers, current layer, `scene_state.check()`
- the `shown` counts (`nodes` / `with_picture` / `problems`)
- per-stage before/after, with the reason for every failure
- the quality numbers of §4

```
python graph/scene_gate.py --scene S --report
```

PASS = live layers end at `grouped`, nothing stale, `check()` true,
evidence layer whole. There is nothing left here to type by hand.

---

## 6. THE DEFECTS THAT SURVIVE

None of these is fixed. Each says whether it STOPS a run or merely makes a
scene worse.

### 6.1 `ctop` plan shots have NEVER detected anything — 0 for 11
**OPEN. Does not stop a run. Makes the scene worse.**

The vote's plan view has two cameras: `top` (inside the room) and `ctop`
(above the ceiling, ceiling deleted, near-vertical). Measured on
living_marble: **`top` 22 detections / 23 shots, `ctop` 0 / 11.**

`ctop` is the fallback, so by design it is handed the hardest objects —
tall things and things high on shelves. On living that was all three
bookshelves, all five magazines, the floor lamp, the plant and the tv
stand. When it fails, the slice falls back to a full-height wedge that
only constrains left–right, so nothing re-measures the box and it ships
roughly as it arrived. The gate counts these per scene as INFO.

Not a regression: the pre-rewiring borrowed renders are the SAME pictures
(mean pixel difference < 2/255). It has presumably always been this way
and was invisible because the review sheet did not show the plan shot.

**Explicitly OUT OF SCOPE.** It is a design question about how the vote
sees tall and flat objects, it needs the user's judgement, and the chain
runs without solving it — it just measures those objects poorly and says
so.

### 6.2 `node_views.py --only <ids>` REWRITES the whole plan file
**OPEN. Does not stop a run; corrupts the plan if you use the flag.**

`--only` filters the node set and then writes `node_views.json` containing
ONLY the named nodes, silently shrinking the file every downstream reader
trusts. Fine for a scoped repair you are watching; wrong if anything later
expects the whole scene. The automated chain never passes `--only`, so
this is a hazard for hand repair, not for a fleet.

### 6.3 Big objects cannot be framed from inside the room
**OPEN. Does not stop a run. Makes the evidence weaker.**

`view_cams.standoff` wants `1.5 x half-extent / tan(27.5deg)`, which for a
3 m object is ~4.6 m in a room 4.7 m wide. The camera is pulled back
toward the capture standpoint instead of the view being dropped (culls
fell 114 -> 53), but a camera pulled 5 m is no longer really the view it
claims to be. `pulled_in_m` on each view records how far it moved; treat
large values with suspicion.

### 6.4 THE CHAIN HAS NO JUDGE FOR A DUPLICATE THE VOTE ITSELF CREATES
**OPEN. Does not stop a run. Ships a duplicate object.**

`build_edges` proposes SAME_CANDIDATE edges — "these two might be one
object" — and J1 (`judge_pairs.py`) answers them. But **J1 runs on the
RECORD, long before the vote.** The vote then moves every box, and that
can propose a BRAND NEW candidate that no judge in the chain ever sees. On
`living_marble` it did: two chairs, `obj_020` and `obj_068`, ended up 96%
contained in one another. `materialize` merges only pairs whose verdict is
SAME, so an unjudged candidate is silently not merged and the scene ships
a duplicate object.

Found 2026-08-11 by re-running the documented chain on a clone and
comparing node by node: the clone came out with 46 settled nodes,
`living_marble` has 45. It was invisible because `living_marble`'s
`settled` layer HAS the merge, recorded 08-10 — but its `voted` and
`voted_edges` were rebuilt on 08-11, AFTER, and both stages re-derive
edges geometrically with nothing carrying a verdict forward. So the merge
survives only as a fossil in a layer whose inputs are gone. Re-run the
chain today and it does not happen.

Answering it means either a judge that runs on post-vote candidates or a
rule that carries J1's verdicts across the vote. Both are design decisions
with the user's name on them. **What was done instead: the gate now WARNs
on every scene when a SAME_CANDIDATE edge reaches the end with no
verdict**, so the hole is counted on all 100 runs rather than silently
absorbed.

### 6.5 J8's concurrency of 8 multiplies GPU renders, not just model lanes
**OPEN, REPORTED NOT CHANGED. Can take the machine down mid-fleet.**

`CONCURRENCY = 8` in `judge_multiplicity.py` and `judge_same_product.py`
(user ruling 08-04: "lanes are couriers, compute is cloud-side"). But J8
builds its stimulus INSIDE the worker, so up to 8 concurrent WSL
rasterisations can run at once — on the machine whose failure mode is GPU
burst (`docs/POWER_CRASHES.md`). Behind those lanes there is no rate-limit
backoff either: one immediate retry, then a default verdict.

Not changed, because reversing a user ruling is a judgement and not a
repair. If a fleet keeps dying on J8, this is the first thing to look at.

### 6.6 `subprocess.run(..., shell=True)` timeouts do not kill a WSL render
**OPEN. Costs hours; leaves orphans that fight the next run for the GPU.**

The child process is `cmd.exe`; the real work is inside WSL and keeps the
GPU after Python gives up. `node_views`' own timeout is 7200 s, so one
wedged render costs two hours before anyone finds out.
`run_fleet --scene-timeout` is the outer bound, but killing the
`run_scene.py` process does not kill a renderer it started inside WSL
either. **If you see repeated `timeout` rows in a morning report, check
for orphans (`wsl -e ps aux`, and `nvidia-smi`) before starting another
fleet.**

### 6.7 `graph['shown']` stores supplementary view paths ABSOLUTE
**OPEN. Harmless on one machine; breaks a moved scene folder.**

The main picture path is relative to the scene dir; the supplementary view
paths are absolute. Mixed, and it means a scene folder cannot be moved,
copied or archived without breaking those references. Not a blocker for
100 runs on one machine — each run rewrites them. Worth a one-line fix in
`node_evidence.write_layer`.

### 6.8 The GPU clock lock — CLOSED
`tools/install_gpu_clock_lock.ps1` registered the scheduled task
**`GPUClockLock`**: `nvidia-smi -lgc 0,1500` as SYSTEM at every startup.
Since the failure IS a reboot, the lock is back before anyone logs in.
Note one claim made when this was proposed and later found FALSE: an
unelevated session CANNOT fire the task with `schtasks /run`. Re-applying
the lock mid-session still needs an admin shell.

---

## 7. WHAT IS ALREADY SAFE

Worth knowing so it is not re-litigated:

- **Stale layers resolve themselves.** Writing layer N marks N+1..end
  stale automatically (`scene_state.stamp`), and a stale layer is skipped
  by `current()`. On a fresh scene nothing downstream exists, so the sweep
  does nothing.
- **J9 degrades instead of failing.** No `shown` layer, or a stale one,
  and it falls back to detector crops and SAYS SO in the log. A scene that
  skipped `node_evidence` still completes — which is exactly why the
  gate's own `final()` FAILs when the `shown` counts are missing.
- **The vote is deterministic.** `obj_010` voted twice under one
  sha/params gave identical intermediates to the digit, so a difference
  between runs is code or parameters, never drift.
- **Every stage prints an additive check** — how many other top-level
  graph blocks it touched. Should always be 0.
- **Renders are fingerprinted.** A changed camera DELETES the stale png
  rather than silently reusing it. **The one exception has just been
  fixed:** the `_box.png` overlays have no params sidecar and were judged
  fresh purely by being newer than their source — and a power cut during
  `im.save` leaves a truncated png NEWER than its source, which every
  later run would keep and hand to J9 as the node's one picture.
  `node_views.whole_image()` now verifies any overlay that looks fresh,
  deletes a truncated one, and draws it again.
- **The scene graph is written atomically everywhere.** `paths.write_atomic`
  writes beside the target and renames, so a reader sees the whole old
  file or the whole new one and never a mixture. `scene_graph.json` is
  1.5 MB, holds the WHOLE scene, and is NOT re-derivable — detection,
  lifting, description and edges all sit upstream. Four stages used to
  truncate it to zero and stream it back, two of them right after a GPU
  stage, which is exactly where this machine cuts out.
- **A corrupt preview manifest is now fatal** instead of being swallowed
  and rewritten with only this run's ids.
- **A model outage is now fatal.** Auth, invalid-key and credit-balance
  errors used to be caught by the same handler as a timeout and become a
  full set of confident-looking defaults, exit 0.

---

## 8. EVIDENCE — and its limits

The chain was run end to end **unattended** on a throwaway 2.0 GB clone of
`living_marble` (`autotest_living`), so that the real scene's open J9 gate
was not consumed. `evidence -> j9 -> grouped` ran through `run_scene.py`
with no human in the loop:

```
[run_scene] PASS  scene=autotest_living  93.5s
  ok  evidence  settled -> shown     2.0s
  ok  j9        shown   -> -        91.3s
  ok  grouped   shown   -> grouped   0.2s
  final gate: PASS
    PASS  the chain ended on `grouped`
    PASS  no stale layers
    PASS  evidence layer whole: 46/46 nodes have a picture
```

J9 really ran — 91 s of real model calls, not a stub. **This is the first
run of this pipeline whose completion was CHECKED rather than assumed.**

The gate's negative cases were proved too: asked to run `evidence` while
`settled` was stale it refused and named the layer whose rewrite
invalidated it; told that `doubts` had just run when it had not, it caught
the lie from the artifact's mtime.

**BE HONEST ABOUT WHAT THIS IS.** It is ONE scene, and only the last three
stages of it ran unattended — the slow GPU stages were driven by hand
first. Nothing here is evidence that 100 scenes will run. It is evidence
that the machinery to run them, and to notice when they go wrong, now
exists. The 100-scene claim is not made.
