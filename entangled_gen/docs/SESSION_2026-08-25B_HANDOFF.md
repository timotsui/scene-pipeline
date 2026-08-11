# SESSION 2026-08-25B HANDOFF — the pipeline became a chain; the chain is still short at both ends

(Real date 2026-08-11, one long session. REVIEW_LOG R-S2-84..88.
Previous handoff: SESSION_2026-08-25_HANDOFF.md, which covers the first
half of this same day.)

## READ THIS FIRST, IN THIS ORDER

1. `docs/PARKED.md` — what is deliberately NOT being worked on.
2. This file §1 (the one-paragraph state) and §7 (what needs the user).
3. `docs/PLAN_AUTOMATION_2026-08-11.md` — the full working record.
4. `graph/stages.py` — the chain, as data. It IS the pipeline now.

---

## 1. WHERE THIS GOT TO

The user's goal, restated by them several times: **a pipeline that runs
top to bottom, unattended, over 100 fresh scenes, as designed.**

What exists now: three phases (`core`, `graph`, `compose`) driven by one
command, with a checkpoint on both sides of every stage, a fleet driver
that survives a bad scene, and a per-module timing rollup.

What is still missing, and it is the headline: **the chain does not
start at the beginning.** `stages.CHAIN` begins at the vote and reads
`resolved`. Nothing in any phase BUILDS `resolved`. Ten designed
record→judged→resolved stages are absent. **A genuinely fresh Marble
bundle would run the core, reach the vote, and stop.** Both test scenes
only worked because they are clones that already had a `resolved` layer.

So: the machinery is right, one third of the pipeline is not wired into
it, and that is the single most important thing left.

---

## 2. WHAT IS RUNNING RIGHT NOW (may have finished)

- **A compose run on `autotest_bedroom` — FINISHED, PASS.** All ten
  stages, rc=0, gates green on both sides, 25 minutes:

  ```
  supported_by 499.7s  consistency 169.5s  snap 14.1s
  propose_edits 541.1s  shopping 8.8s  pick 149.0s
  fit_preview 2.6s  fit_check 13.9s  fit_declip 109.7s  fit_walk 0.1s
  ```

  ⚠ **READ THAT PASS CORRECTLY.** It means every stage did what it
  promised. It does NOT mean the chain is as designed: this run used the
  WRONG compose order (check before declip), ran the fit block ONCE
  instead of to dry, and never ran rotation_check or fit_feedback — see
  §4. `fit_walk` at 0.1 s is the guaranteed no-op that audit predicted.
  **The gate verifies stages, not sequence.** Only an audit against the
  design catches the second, which is why §4 exists.
- **An agent editing `graph/stages.py` and `run_scene.py`** to fix the
  compose order, add two missing stages, and make the fit block iterate.
  **If `stages.py` looks half-finished, that is why — check `git diff`
  before assuming damage.**
- **An audit agent** on fresh-scene readiness (what happens starting
  from 100 bundles and nothing else). Its answer is not in this file.

⚠ The viewer is running on port 8321 against `living_marble`.

---

## 3. WHAT WAS BUILT

| file | what it is |
|---|---|
| `graph/stages.py` | **THE ORDER, as data.** Rows: command, layer read, layer written, artifacts, file inputs, llm/gpu cost. Two tuples: `CHAIN` (graph) and `COMPOSE`. |
| `graph/scene_gate.py` | **THE CHECKPOINT.** `before` / `after` / `final`, plus quality notes. Exit 3 = gate failure. |
| `run_scene.py` | one scene, three phases, gate around every stage, run log, timing block |
| `run_fleet.py` | many scenes; one bad scene never stops the night; `--resume`; per-scene timeout; morning HTML+JSON with per-module timing |
| `glts_run.py` | the GL-TreeSearch baseline on our prompts, isolated + timed |
| `compare_methods.py` | four-axis comparison, deliberately no combined score |
| `docs/PARKED.md` | the two things the user annexed |

Key behaviours that did not exist this morning:

- **Writing is the default.** Six stages used to no-op without a flag and
  exit 0. `--dry-run` is now the opt-out. ⚠ `--apply` / `--render` /
  `--recut` / `--reshoot` still parse and DO NOTHING — an old command
  line from a handoff now does MORE than its author expected.
- **The gate catches a stage that did nothing** by requiring its declared
  artifact to have been written DURING that stage (mtime vs stage start).
- **File-level staleness.** `scene_state.stamp` records `written_at`;
  `stages.py` declares each stage's file inputs; the gate flags a layer
  built before an input file changed. ⚠ **This check currently only
  iterates `CHAIN`, so every `inputs` tuple in `COMPOSE` is decorative.
  Fixing that is on the list.**
- **Locks.** `paths.gpu_lock` (one render at a time, all five WSL sites),
  `paths.scene_lock` (one writer per scene), `paths.dir_lock` (one writer
  per output dir). Stale locks clear on **pid liveness, not timeout** —
  the failure being survived is a power cut. `os.kill(pid,0)` is NOT a
  liveness test on Windows; it kills the process it asks about.
- **Atomic writes** everywhere via `paths.write_atomic`.

---

## 4. THE COMPOSE CHAIN IS WRONG AND IS BEING FIXED

An audit against `PLAN_FIT_LOOP.md` and `pipeline_map.html` found three
independent faults. All three are quoted canon, not opinion.

1. **`fit_check` and `fit_declip` are in the wrong order.** Canon rule 8:
   `fit_preview → fit_declip → fit_check`. `fit_declip` REWRITES
   `fitted_preview.glb/.json` in place, so with check first the check
   describes a scene that no longer exists — and **the Collision-Free
   number, the project's headline quality metric, is measured on the
   un-declipped scene.**
2. **The fit block is a LOOP and runs once.** Canon: "place → jiggle →
   check → WALK → repeat until dry". Exit condition on the map: `0 new =
   DRY`. A recorded living run took FOUR rounds. Running once ships the
   first naive placement on every scene.
3. **Two canonized stages are missing**: `rotation_check` (PH2a, CANON
   v2 08-04, runs ONCE after the loop, then a closing place+jiggle to
   apply its deltas) and `fit_feedback` (rule 12, the walk-back that
   lets shopping drop infeasible items).

Also: `fit_walk` as the LAST row is a guaranteed no-op — only
`fit_preview` reads `fit_walk.json`, and it never runs again.

**Correct order after the fix:**
`supported_by → consistency → snap → propose_edits → shopping → pick →
[fit_preview → fit_declip → fit_check → fit_walk] × until dry →
rotation_check → closing fit_preview + fit_declip`

---

## 5. THE BIG REMAINING WORK — THE RECORD HALF

Ruled order, from `PIPELINE.md:301-312` and `PLAN_SCENE_GRAPH.md:234`:

```
G1 build_graph  →  G2 build_edges
J0 triage_pairs →  J1 judge_pairs  ∥  J5 judge_near
J2 build_judged →  J3 judge_names  →  J4 judge_coherence
J6 describe_nodes  →  J7 materialize_verdicts   -> `resolved`
```

None is in any tuple. Suggested shape: a third tuple, `RECORD`, beside
`CHAIN` and `COMPOSE`, because `--phase graph` currently means "the vote
onward" and that meaning is worth keeping.

⚠ **The judge numbering is J3 = names, J4 = coherence.**
`PLAN_VOTEBOX_DOWNSTREAM.md` said "J4 names" twice; corrected 08-11, but
older copies and anyone's memory may still be wrong.

`migrate_walls_w5.py` also edits the pre-vote layers and is in no table —
decide whether it is still live or superseded by `build_graph`'s W5 path.

---

## 6. WHAT WAS FOUND AND FIXED TODAY (short list)

- A **fresh scene could never finish**: `materialize_layers --settle-only`
  required J9's output, which cannot exist before J9. Invisible because
  every dev scene had a stale copy. **Test on a scene that has never run.**
- **The Phase-B2 loop-back was missing** from the chain (J0/J1 re-run on
  `voted_edges` before J8). It is a user ruling of 08-07 and had been
  running by hand. Its absence shipped an unjudged duplicate — which was
  then written up TWICE as a design hole that did not exist. Now fixed;
  `AUTOMATION_READINESS §6.4` rewritten to stop teaching the error.
- **Compose read the pre-vote layer.** 29 of 45 objects on living moved
  >5 cm between `resolved` and the current layer; the glass door was
  6.04 m wide instead of 0.02 m. Fixed at 7 geometry + 3 appearance sites.
- `--only` was **deleting work it was not asked about** in `split_cuts`
  and `node_views`. Both now merge.
- A scene with **no splits** was a hard failure. Fixed.
- **GLTS exits 0 when its scene failed** — caught by checking artifacts,
  not the return code.
- **Two GLTS runs shared an output directory** (my error) and both
  reported success; `paths.dir_lock` added.
- Five modules **wrote a layer without stamping it**, so nothing
  downstream was marked stale.

---

## 7. WHAT NEEDS THE USER — nothing else is blocked on them

1. **`voted_edges`: live or retired?** `pipeline_map.html:669-680` draws
   the loop-back and the `voted_edges` half-layer as a **TOMBSTONE,
   RETIRED 08-09** (every layer must be whole; edges follow nodes inside
   a layer). But the code needs it: `judge_multiplicity` hard-exits
   without it, and the two loop-back judges only accept
   `--edges-from record|voted_edges`. The map is the user's stated
   authority; the 08-07 ruling says run it. **Do not resolve this
   silently.** Either the tombstone is stale and should be redrawn, or
   the judges need a `--edges-from voted` mode and the module retires.
2. **`support_clip`: in the chain or retired?** R-S2-22 puts it in the
   order; five consecutive handoffs call it a retirement candidate
   because it rewrites layer geometry in place. Currently excluded, with
   a note saying so.
3. **Sub rounds (PH2r)**: drawn on the map with the only loop arrow in
   step 3, user-passed — but the code is `experiments/sub_round_all.py`
   and the map badges it "not in fitted_preview yet". Promote or defer.
4. **`fit_feedback`'s re-shop scope**: the design says shopping consumes
   it "on its next run" and stops there. How wide that re-run should be
   is not ruled.
5. **The metric to report** (paper): recommendation is the LayoutVLM
   four — CF, Pos., Rot., PSA — because that is GLTS's EXTERNAL
   benchmark. Do NOT use their 3DTindo rubric: it is the PRM inside
   their own MCTS, so scoring with it is circular. No CLIP in their paper.
6. **`grouped` rebuilds from `voted` instead of inheriting `shown`**, so
   the per-node picture does not survive into the final layer.

Parked by the user, do not work on: the `ctop` top-view problem and
anything specific to J9. See `docs/PARKED.md`.

---

## 8. TEST SCENES

| scene | state | notes |
|---|---|---|
| `living_marble` | `shown`, `grouped` stale | **THE LIVE SCENE. Do not mutate.** Open J9 gate. |
| `bedroom_marble` | `resolved` | never voted; the honest "fresh-ish" scene |
| `autotest_living` | `grouped`, clean | clone of living; safe to destroy |
| `autotest_living2` | `grouped`, clean | second clone, prefix-sibling on purpose (glob-collision test) |
| `autotest_bedroom` | `grouped`, clean | clone of bedroom, 82 objects; **the best test scene** — it was genuinely unvoted |
| `autotest_broken` | empty graph | deliberate fixture: does the fleet isolate a bad scene |

GLTS outputs live in the TreeSearchGen checkout as
`output_ovm_<scene>/`, plus one
`output_ovm_bedroom_marble_CONTAMINATED_two_concurrent_runs` kept for
inspection.

---

## 9. THE METHOD LESSON, AND IT CAUSED TWO REAL DEFECTS

**Trust the primary record, never a summary.** Twice today a summary
document caused a bug in the code:

- `AUTOMATION_READINESS.md`'s eleven-step list omitted the Phase-B2
  loop-back. `stages.py` was built from that list and inherited the hole.
- `PLAN_COMPOSE_LOOP.md`'s opening line ("later modules are direction
  only, not designed") was written at the start of that work and is
  contradicted by the gate table in its own body, which records several
  USER PASSes. I repeated the header to the user as fact.

The authority order that actually holds: **`pipeline_map.html` → the
owning PLAN_*.md → REVIEW_LOG run records → module docstrings → summaries.**

Third time in two sessions that something reported success while having
done otherwise: the six no-op flags, GLTS's exit 0 on a dead scene, and
two runs sharing a directory. In every case each individual number being
printed was true.
