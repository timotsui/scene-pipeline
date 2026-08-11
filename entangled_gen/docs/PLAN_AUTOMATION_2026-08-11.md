# PLAN — make the graph chain run unattended over 100 scenes

Opened 2026-08-11 (overnight, orchestrated). Source of the work:
`docs/AUTOMATION_READINESS.md` §5. User ask: *"fix this and make sure we
can run 100 scenes automated with smooth and no problems, with clear
boundaries between modules, and clear state checkpoints in between."*

This file is the canonical plan AND the progress log. Update it on every
state change. Resume protocol: read §0, then §3 for the next unchecked box.

---

## 0. HARD CONSTRAINTS FOR THIS SESSION

1. **DO NOT run J9 (`judge_same_product`) on `living_marble`.** There is
   an open USER GATE on that scene (crops-per-member ruling + the
   five-chair question). Running it consumes the gate.
2. **DO NOT mutate `out/living_marble/scene_graph.json`.** All end-to-end
   verification happens on a COPY scene (`autotest_living`).
3. **No threshold tuning, no gate changes.** This is plumbing only.
   `ctop` (AUTOMATION_READINESS §4.1) is explicitly OUT OF SCOPE.
4. Backward compatibility: `--apply` must keep being ACCEPTED everywhere
   it exists today (as a no-op) so no doc, script, or handoff breaks.

---

## 1. THE SHAPE OF THE FIX

Today the 11-step order and its flags live in a person's head and in a
markdown file. The fix is to make them a **data structure in one file**,
and to make every stage state its own preconditions and postconditions.

    graph/stages.py     THE ORDER. One row per stage: name, argv,
                        reads (layer that must be current+fresh),
                        writes (layer it must leave current+fresh),
                        llm (does it spend model calls).
    graph/scene_gate.py THE CHECKPOINT. Given a scene, answer: is the
                        state legal right now / after stage X / at the end.
    run_scene.py        THE RUNNER. Walks stages.py, calls the gate
                        between every stage, stops on the first failure.

"Clear boundaries between modules" = each stage reads one named layer and
writes one named layer, and nothing else. "Clear state checkpoints
in between" = the gate runs between every pair and fails loudly.

---

## 2. THE FOUR DEFECTS BEING CLOSED

| # | defect (AUTOMATION_READINESS ref) | fix |
|---|---|---|
| D1 | 6 stages no-op without a flag, exit 0 (§2.1) | invert defaults: do the work; `--dry-run` to opt out |
| D2 | `node_evidence` writes a layer with holes (§2.2) | refuse to write when `problems > 0` unless `--allow-holes` |
| D3 | nothing gates on the run FINISHING (§2.3) | `scene_gate.py`, called between stages and at the end |
| D4 | the chain is not in the runner (§2.4) | `stages.py` + `run_scene.py` |

---

## 3. WORK ITEMS — progress

Status: [ ] not started · [~] in progress · [x] done · [!] blocked

- [x] **W1 — invert defaults in 5 modules** (D1)
      record_vote_doubts, build_voted, rederive_voted_edges,
      materialize_layers, node_views. `--apply` kept as an accepted
      no-op; `--dry-run` is the opt-out; node_views uses `--no-render`.
- [x] **W2 — node_evidence: defaults + no holes** (D1, D2)
      Refuses to write `shown` when any node has no picture, exit 2,
      unless `--allow-holes` (which is then recorded IN the layer).
      `--dry-run` made truly inert (it was still rebuilding the recut dir).
- [x] **W3 — `graph/stages.py` + `graph/scene_gate.py`** (D3)
- [x] **W4 — extend `run_scene.py` to the full 11 steps** (D4)
      Walks `stages.CHAIN`; the eleven commands appear nowhere in it.
      `gate.before` / stage / `gate.after(since=t0)` around every stage,
      `gate.final` at the end. `--phase`, `--from/--until`, `--skip`,
      `--no-llm`, `--list`, `--continue-on-fail`, `--dry-run`. Writes
      `run_scene_<runid>.json` per scene.
- [ ] **W8 — harden against the audit findings** (see §5)
- [x] **W5 — end-to-end unattended verification on `autotest_living`**
      (2.0 GB clone of living_marble, made 08-11; archives excluded)

      **THE CHAIN FINISHED, UNATTENDED, AND THE GATE SAID SO.** Stages
      `doubts` through `views` were driven by hand first (they are the
      slow GPU ones); `evidence -> j9 -> grouped` then ran through
      `run_scene.py` with no human in the loop:

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

      This is the first run of this pipeline whose completion was
      CHECKED rather than assumed. J9 really ran (91 s, real model
      calls) — on the throwaway clone, so `living_marble`'s open J9
      gate is untouched and still the user's to decide.

      **THEN THE WHOLE THING, THROUGH THE FLEET DRIVER, IN ONE
      COMMAND.** `run_fleet.py --scenes autotest_living --phase graph
      --from doubts` — ten of the eleven stages (everything but the
      hour-long `vote`), no human in the loop, every gate green both
      before and after every stage:

      ```
      doubts       rc=0    0.2s   before=True after=True
      voted        rc=0    0.1s   before=True after=True
      voted_edges  rc=0    0.1s   before=True after=True
      j8           rc=0    9.2s   before=True after=True
      j8s          rc=0    9.9s   before=True after=True
      settled      rc=0    0.2s   before=True after=True
      views        rc=0   44.7s   before=True after=True
      evidence     rc=0    2.0s   before=True after=True
      j9           rc=0   52.5s   before=True after=True
      grouped      rc=0    0.2s   before=True after=True
      [run_fleet] 1 passed, 0 not, in 0h01m59s
      ```

      Two minutes, because a re-run is nearly free: the judge caches hit
      and the render fingerprints matched, so almost no GPU and almost
      no model calls. That is the property that makes `--resume` and a
      hundred scenes affordable.
- [x] **W7 — `run_fleet.py`, the batch driver** — scene list / file /
      discovery, `--exclude`, `--resume` (skips scenes whose gate already
      passes), `--scene-timeout` (default 4 h), `--stop-on-fail`. One bad
      scene never stops the night. Writes `out/fleet_<runid>.{json,html}`
      with a row per scene carrying the verdict AND the gate's WARN/INFO
      lines, so a scene that PASSED but is poor is visible in the morning.
      Verified: a deliberately broken scene failed at its first gate in
      0.0 s, the good scene ran and passed, the fleet carried on, exit 1.
- [x] **W8 — harden against the audit findings** (§5): atomic writes
      everywhere, corrupt-manifest now fatal, the unbounded `.ply` header
      loop bounded, truncated overlay PNGs detected and re-made, model
      outages fatal instead of silently becoming verdicts, judge failure
      counts recorded, caches flushed per case.
- [ ] **W6 — docs: AUTOMATION_READINESS updated, REVIEW_LOG entry, handoff**

---

## 4b. THE THIRD PASS — the user's own questions (2026-08-11, later)

User asked, in their words: *"Do we have clear module boundaries? Can we
run partial chains and partial modules, and will it know it needs to
override / supersede? Re-running some modules — is it clear, and can it
lead to stale things being used? Any naming confusion with stale stuff?
Always a single source of truth for scene state? And when running
multiple projects, can they live in isolation?"*

**WHAT WAS PROVED BY HAND FIRST.** Re-running a middle module directly,
not through the runner, on a scene that was already finished:

```
before:  live record..shown          stale [grouped]
$ python graph/materialize_layers.py --scene S --settle-only
[state] `settled` rewritten — marked stale: shown, grouped
after:   live record..settled        stale [shown, grouped]   current: settled
$ python graph/scene_gate.py --scene S --before j9
FAIL  layer `shown` is STALE — `settled` was rewritten after it was
      built, so it was computed from inputs that no longer exist.
```

So the supersede-and-invalidate machinery works, and the current layer
correctly falls back. That is the good news, and it is the core of what
was asked.

**FOUND GAP 1 — A STAGE RUN BARE DEGRADES INSTEAD OF REFUSING.** The
gate protects the RUNNER. Run a module by hand and it is on its own.
Asked to judge a scene whose evidence layer had just gone stale, J9
answered:

```
[same_product] evidence: graph['shown'] is STALE (its input was
rewritten) — falling back to detector crops; re-run node_evidence.py
                                                             ...exit 0
```

It noticed, it said so, and it carried on with worse evidence and
reported success. ABSENT and STALE are being treated the same, and they
are not the same thing: absent means the stage never ran, which is a
documented and defensible degradation; stale means the stage DID run and
its input has since changed, which is a chain-ordering error.

### THE ANSWERS, IN SHORT

| question | answer |
|---|---|
| single source of truth for scene state | YES for the back half of the pipeline, NO for the front half and for `compose/` — being fixed |
| clear module boundaries | the DECLARED boundary was accurate for 4 of 11 rows and conservative-but-wrong for 6; the errors all leaned SAFE at the layer level and DANGEROUS at the file level — fixed by declaring file inputs |
| partial chain / partial modules | safe when driven by the runner; a module run bare had no protection — being fixed |
| re-running a module supersedes correctly | YES for the three stages that stamp; NO for five that write a layer and never stamp — being fixed |
| naming confusion | one live wrong-block read (fixed); several stale docstrings |
| scenes isolated from each other | on disk YES, thoroughly. The GPU is the one unarbitrated shared resource — being fixed with a lock |

### THE THREE STRUCTURAL HOLES, AND WHAT WAS DONE

**HOLE A — the staleness machinery only understood LAYERS, and half of
what these stages read is a FILE.** `graph['vote']`, `graph['voted_edges']`
and the three judge verdict sidecars are inputs to `settled` that can
neither be marked stale nor mark anything stale. Re-run `j8` by itself and
it rewrites `multiplicity.json`, which `settled` was built from — every
layer still reports fresh, `check()` passes, the end-of-run gate passes.

FIXED. `scene_state.stamp()` now records `written_at` on every layer;
`stages.py` gained an `inputs` field naming the files each stage consumes
that another stage produced; `scene_gate.stale_inputs()` compares the two.
Proven both ways on a test scene: silent when ordered, and when
`multiplicity.json` was touched after `settled` was built —

```
FAIL  `settled` was built 24s BEFORE its input graph/multiplicity.json
      was last written. The stage that writes that file has run since,
      so `settled` was built from something that no longer exists.
```

**HOLE B — five modules write a chain layer and never stamp it.**
`materialize_verdicts` (`resolved`), `build_judged` (`judged`),
`build_edges` (`record`), `migrate_walls_w5` (three at once) and
`compose/support_clip --apply` (`resolved`, in place). The layer changes,
everything after it keeps looking fresh, and both freshness answers still
agree because the pointer was never touched. `support_clip` is the sharpest:
one flag silently invalidates a finished scene's whole downstream stack.
FIXED by adding the stamp.

**HOLE C — the wrong block was being read for J1 merge verdicts.**
`materialize_layers.same_verdict_pairs` had a docstring naming
`voted_edges` over code that preferred `voted`. `voted` is edge_carry's
re-derived copy made at build time; `voted_edges` is where a later,
deliberate re-judgement lands. So re-judging a duplicate pair after the
vote did NOTHING — which is exactly the repair the §4 chair problem calls
for. FIXED: both blocks are read, keyed by pair, `voted_edges` winning a
disagreement.

**FOUND GAP 2 — `--only` SHRINKS A WHOLE-SCENE FILE.** `node_views.py
--only a,b` filters the node set and then writes `node_views.json`
containing ONLY those nodes, silently dropping every other node's plan.
That directly contradicts the project's own graph-edit rule — a module
inherits the whole structure and edits the named parts. A partial run
must not quietly delete what it was not asked about. — hazards AUTOMATION_READINESS.md missed

A separate read-only audit of all eleven stages, looking for what the
readiness doc did not cover. Ranked worst first. Fixed items are marked.

1. **[FIXING] `scene_graph.json` rewritten whole, non-atomically**, by
   four stages. `write_text` truncates to zero then streams 1.5 MB back.
   That file is the WHOLE scene and is NOT re-derivable — detection,
   lifting, description and edges all sit upstream. Two of the four run
   right after a GPU stage, which is exactly where this machine cuts out.
   `record_vote_doubts` already did temp-then-rename; that is now
   `paths.write_atomic` and every stage uses it.
2. **[FIXING] A corrupt preview manifest is swallowed and the data
   replaced.** `slicevote.merge_entries` catches the parse error, prints
   one line, and rewrites the manifest with THIS RUN'S ids only — every
   other object's elected box gone, exit 0. Now fatal.
3. **[FIXING] A `while True` that never ends on a truncated `.ply`.**
   The header parser appends `b""` forever at EOF; RAM climbs until the
   machine swaps to death. A hang is worse than a crash unattended.
4. **[REPORTED] Concurrency 8 multiplies GPU renders, not just LLM
   lanes.** J8 builds its stimulus INSIDE the worker, so up to 8
   concurrent WSL rasterisations run on the machine whose failure mode
   is GPU burst. Behind those lanes there is no rate-limit backoff: one
   immediate retry, then a default verdict. NOT changed — the
   concurrency ruling is the user's (08-04) and reversing it is a
   judgement, not a repair.
5. **[FIXING] A model outage becomes a full set of confident-looking
   defaults, exit 0.** Auth, invalid-key and credit-balance errors are
   swallowed by the same handler that catches a timeout. Token expires
   at scene 40 and the next 60 burn identically, every gate passing.
   Now: those three are fatal, and every stage records how many verdicts
   were defaults rather than decisions.
6. **[FIXING] The model-call cache is written once, at the very end.**
   An unguarded GPU render inside `split_cuts`'s loop can throw past it,
   discarding every call the stage paid for.
7. **[FIXING] A truncated `_box.png` is never repaired**, because
   staleness there is mtime-only — and a cut during `im.save` leaves a
   file NEWER than its source. `node_evidence` then hands it to J9 as
   the node's one picture. (The doc's "renders are fingerprinted" claim
   is true of the WSL renders, not of these overlays.)
8. **[REPORTED, now surfaced] `canon_eligible` is computed, written, and
   gated on by nothing.** A scene resumed with `--only` mixes boxes from
   two code revisions, says so honestly in its header, and the chain
   builds on it without comment. The gate now WARNs.
9. **[REPORTED] `subprocess.run(..., shell=True)` timeouts do not kill
   the renderer.** The child is `cmd.exe`; the real work is inside WSL
   and keeps the GPU after Python gives up. `node_views`' timeout is
   7200 s, so one wedged render costs two hours before anyone finds out.
   `run_fleet` gets a per-scene timeout as the outer bound, and its
   comment says orphans must be checked for by hand.

Checked and found CLEAN: nothing interactive anywhere; no hardcoded
scene name inside the chain; nothing written outside the scene dir; no
unseeded randomness (the one RNG is seeded).

### ISOLATION — the answer, and the lock

**On disk, isolation is genuinely good and was verified rather than
assumed.** Every stage in the chain writes only inside
`paths.scene_dir(scene)`; every temporary `.ply` and render-target JSON
carries the node id and lives in the scene's own folder; every judge
cache is per-scene; the one module-level cache is keyed by a path that
contains the scene; no `glob()` in the chain can match another scene's
files (the `bedroom` / `bedroom_marble` prefix hazard does not exist —
the scene name is only ever a whole path component); nothing reads the
working directory. A hundred scenes run one after another cannot leak
into each other.

**The GPU was the one shared thing nothing arbitrated.** There was no
lock, semaphore or queue anywhere in the repo. The only mitigation was a
`time.sleep(1.0)` inside each renderer process — which does nothing when
several processes render at once. And it was already being exceeded
WITHIN a single scene: J8 runs 8 workers and, since v2.4, builds its
render inside the worker, so one scene could put 8 rasterisations on the
card at once. On a machine that hard-powers-off under GPU burst.

FIXED. `paths.gpu_lock()` — an `O_CREAT|O_EXCL` lock file at
`out/gpu.lock`, deliberately the one shared mutable file in the design —
now wraps all five WSL render call sites. `paths.scene_lock(scene)`
refuses a second run of the same scene and names the other pid, because
`write_atomic` prevents a torn write but not a LOST UPDATE.

Two details worth keeping:
- **Stale locks are broken by PID LIVENESS, not by a timeout.** The
  failure being survived is a power cut: the lock file outlives its
  owner. If only a timeout could clear it, one crash at 01:00 would cost
  the rest of the night. Recovery from a dead holder is immediate; the
  (generous, 2 h) age limit is only a backstop for a recycled pid or a
  lock written by another host.
- **`os.kill(pid, 0)` is NOT the liveness test on Windows** — it calls
  `TerminateProcess`, so the obvious portable idiom would kill the
  process it was asking about. `OpenProcess` + `GetExitCodeProcess` is
  used instead.

Both proven across real, separate processes: two children's critical
sections did not overlap, a lock left by a dead pid was broken in 0.00 s,
and a second run of a live scene was refused by name.

⚠ STILL TRUE: a scene killed by `--scene-timeout` could leave its
renderer running inside WSL, where the Windows process tree cannot reach
it. `run_fleet` now kills the Windows tree with `taskkill /T /F`,
confirms the pid is gone, and then makes a separate best-effort
`wsl -e pkill` — reporting what it found rather than assuming.

### PROVED BY ACCIDENT — a hard kill, and the locks recovered

A mistyped command started a full vote on the finished clone (`--until
settled` with no `--from` starts at `vote`, not where you meant). It was
killed with `taskkill /T /F` mid-render. That was an unplanned but exact
rehearsal of the power-cut case:

- **Both lock files outlived their owners** — `out/gpu.lock` and the
  scene's `.scene.lock`. The next acquirer broke each one in 0.01 s and
  0.00 s respectively, naming the dead pid and what it had been doing.
  This is the PID-liveness rule earning its keep: a timeout-only design
  would have stalled every later scene for two hours.
- **The scene itself was undamaged.** `autotest_living` still passed its
  final gate on `grouped`, 46/46 nodes with a picture — because the vote
  writes its manifest at the END, and every whole-scene write is atomic.

### A REAL USABILITY BUG THE FIRST LONG RUN EXPOSED

The vote on `autotest_bedroom` was run as `--until vote`. It succeeded —
42 minutes, `after` gate PASS — and then the runner reported **FAIL**,
because the final gate asked "did the chain reach `grouped`?" and it had
not. It had not because that is what was asked for.

FIXED. A deliberately partial run (`--until` short of the end, `--skip`,
`--no-llm`) now reports **INCOMPLETE**, never FAIL, prints which option
made it partial, and says how to check the scene properly. Reporting an
obeyed instruction as a failure is how a gate teaches people to ignore
it, which is the one thing it cannot survive.

Also surfaced by that run, and genuinely correct: `scene_state.check()`
FAILED with *"newest whole layer is 'resolved' but nothing has stamped
graph['layer']['canonical']"*. That scene's `resolved` was written by
`materialize_verdicts` before tonight's stamping fix — so the gate found
HOLE B in the wild, on a real scene, unprompted. It self-heals the moment
any stamping stage runs.

---

## 4c. THE THREE-SCENE RUN — and the blocker only a fresh scene could show

Scenes chosen so they were NOT alike: `autotest_bedroom` (a genuinely
fresh room, 82 objects, never voted), `autotest_living` (already
finished), `autotest_living2` (mid-chain, and named as a prefix-sibling
of the first on purpose, to test for glob collisions — there were none).

```
[1/3] autotest_bedroom: CRASHED at graph/settled  0h03m18s
[2/3] autotest_living:  PASS                      0h01m55s
[3/3] autotest_living2: PASS                      0h09m58s
      2 passed, 1 not, in 0h15m11s
```

**THE CRASH IS THE POINT. `materialize_layers --settle-only` — the
geometry pass that runs BEFORE J9 — required J9's output file.** On a
fresh scene that file cannot exist, so `--settle-only` could never
succeed on a scene that had not already been through the chain once. It
was invisible for as long as it existed because every scene it was
developed on had a stale `same_product.json` lying around from an earlier
session. A hundred-scene run would have failed on scene 1.

Fixed: optional in the constructor, required in `run()` where the
verdicts are actually applied. The fresh scene then ran its remaining
stages and PASSED — 82/82 nodes with a picture, chain ended on `grouped`,
nothing stale. **3 of 3 now pass.**

The two other scenes ran and passed WHILE the first was failing, which is
the isolation property the fleet exists for.

### WHERE THE TIME GOES

```
stage      n    total   share    mean     max   worst scene
views      2    540.2   59.3%   270.1   495.0   autotest_living2
j8         3    203.6   22.4%    67.9   197.1   autotest_bedroom
j9         2    136.1   15.0%    68.1    84.4   autotest_living2
j8s        3     24.3    2.7%     8.1    14.2   autotest_living
evidence   2      4.0    0.4%
doubts / voted / voted_edges / settled / grouped: under a second each
```

Rendering views is ~60% of the cost and scales with how many boxes moved;
the judges are ~40%. The seven bookkeeping stages together are under two
seconds. On the fresh scene alone, `views` was 81% of the run.

### A QUALITY FINDING THE TABLE SURFACED

**On the fresh bedroom, 55 of 82 objects (67%) were never re-measured** —
the vote's plan view found nothing and the box shipped roughly as it
arrived. On the living room it is 9 of 46 (20%). Same machinery, three
times worse on a room it was not developed against.

Nothing is broken; the scene simply is not measured, and it says so. This
is the `ctop` defect (§6.1 / AUTOMATION_READINESS 4.1) and it remains out
of scope by ruling — but it is much more expensive than the one-scene
figure suggested, and that is worth knowing before scaling to 100.

### THE MACHINE

17,139 GPU samples on 08-11: peak 1500 MHz, peak 104 W, **zero samples
above the lock**, including under J8's eight concurrent workers. No
crashes. Compare the unlocked July record on the same card: 2415 MHz,
203 W.

### Findings to carry (not fixed tonight)

- ⚠ **THE CHAIN HAS NO JUDGE FOR A DUPLICATE THE VOTE ITSELF CREATES.**
  Found 2026-08-11 by re-running the documented chain on the clone and
  comparing it against the original, node by node. The clone came out
  with 46 settled nodes; `living_marble` has 45.

  What happens: `build_edges` proposes SAME_CANDIDATE edges — "these two
  might be one object" — and J1 (`judge_pairs.py`) answers them. But J1
  runs on the RECORD, long before the vote. The vote then moves every
  box, and that can propose a BRAND NEW candidate no judge in the chain
  ever sees. On this scene it did: two chairs, `obj_020` and `obj_068`,
  ended up 96% contained in one another. `materialize` merges only pairs
  whose verdict is SAME, so an unjudged candidate is silently not merged
  and the scene ships a duplicate object.

  Why it was invisible: `living_marble`'s `settled` layer HAS the merge,
  recorded on 08-10. Its `voted` and `voted_edges` were rebuilt on 08-11
  — AFTER — and that rebuild wiped the verdict, because both stages
  re-derive edges geometrically and nothing carries a verdict forward.
  So the merge survives only as a fossil in a layer whose inputs are
  gone. Re-run the chain today and it does not happen.

  This is NOT fixed here. Answering it means either a judge that runs on
  post-vote candidates or a rule that carries J1's verdicts across the
  vote, and both are design decisions with the user's name on them.
  What WAS done: `scene_gate.quality_notes` now WARNs, on every scene,
  when a SAME_CANDIDATE edge reaches the end with no verdict — so the
  hole is counted on all 100 runs instead of being silently absorbed.

- ⚠⚠ **COMPOSE READS THE PRE-VOTE LAYER.** Every module in `compose/`
  takes its boxes and edges from `graph["resolved"]` — the layer as it
  stood BEFORE the vote elected anything. `consistency.py`,
  `propose_edits.py`, `supported_by.py`, `snap.py`, `support_clip.py`
  all do it; `pick.py`, `fit_preview.py` and `fit_declip.py` read
  appearance from `judged` for the same reason. On `living_marble` that
  means placing and shopping against boxes where the glass door is 6.04 m
  instead of 0.02 m, with no split pieces and with merged-away nodes
  still present.

  The files themselves show it is an oversight rather than a decision:
  `supported_by.py` already fixed APPEARANCE to `scene_state.nodes()`
  with a comment explaining why `judged` was wrong — while the boxes four
  lines above stayed on `resolved`. `snap.py` calls
  `scene_state.nodes()` on line 201 and `graph["resolved"]` on line 358.

  NOT FIXED, and it is the biggest single correctness finding of the
  night. It is also outside the chain — `stages.CHAIN` ends at `grouped`
  and no gate covers compose at all — so it neither blocks nor is caught
  by anything built here. Fixing it changes what gets placed and bought,
  which is the user's call, not a plumbing repair.

- ⚠ **`grouped` REBUILDS RATHER THAN INHERITS, SO THE PICTURES DO NOT
  SURVIVE.** `materialize_layers`' full pass does not read `shown` at
  all — the word does not appear in the file. It starts again from
  `voted` and re-applies the same four geometry rules `settled` did, then
  adds J9's grouping. So `grouped` is a SIBLING of `settled`, not a child
  of `shown`, and the per-node `shown` block — the picture the whole
  `node_evidence` stage exists to decide — is absent from the current
  layer. Anything calling `scene_state.nodes(graph)` after a finished run
  gets nodes with no pictures.

  This contradicts the project's own graph-edit rule (inherit the whole
  structure, edit the named parts) and quietly discards a stage's output.
  NOT FIXED — it is an architectural change to materialize. The stage
  table now says plainly that its `reads="shown"` is conservative rather
  than literal, and why.

- **`shown` stores supplementary view paths ABSOLUTE** while the main
  picture path is relative to the scene dir. Mixed, and it means a scene
  folder cannot be moved, copied or archived without breaking those
  references. Not a blocker for 100 runs on one machine — each run
  rewrites them — so it was left alone rather than changed under J9's
  open gate. Worth a one-line fix later in `node_evidence.write_layer`.

---

## 4. PROGRESS LOG

(append-only; newest at the bottom)

- 2026-08-11 orchestrator start. Read AUTOMATION_READINESS.md, run_scene.py,
  scene_state.py, the six modules' argparse blocks. Plan written.
- W1 + W2 landed (two subagents, in parallel). Both verified by
  `ast.parse` and `--help`; neither was run against a scene.
- W3 written and checked against the REAL `living_marble` graph,
  read-only. The gate independently reproduced the state the handoff
  describes — chain ends on `shown`, `grouped` stale, evidence whole at
  45/45 — and exited 3. That is the check that did not exist before: the
  same scene would previously have been reported as a success.
- Corrections made to W3 during that check: the "is this layer current"
  test now only applies immediately after a stage runs (in a
  retrospective scan an earlier layer sitting under a later one is the
  normal shape of a FINISHED scene, and flagging it made every complete
  run look broken); the stale message now names the layer whose rewrite
  invalidated it; `slice_fallback` is counted from `graph['vote']`, where
  it actually lives, not from node open questions.
- `autotest_living` cloned (2.0 GB, archives and prescale files excluded)
  and confirmed to be a faithful copy by running the gate on it.
- Proved the inverted defaults on the clone: `build_voted --dry-run` left
  the graph byte-identical; the plain run wrote it and the stale sweep
  marked `settled, shown, grouped` stale, exactly as designed.
- Proved the gate's two negative cases on the clone. Asked to run
  `evidence` (which reads `settled`) while `settled` was stale, it
  refused and named the layer whose rewrite invalidated it. Told that
  `doubts` had just run when it had not, it caught the lie from the
  artifact's mtime: *"exists but was NOT written by this run (last
  written 10097s before the stage started)"*. That is the silent-no-op
  hazard, detected.
- Re-ran the chain on the clone and it re-rendered every view rather
  than reusing any. Chased it down: the boxes really did move, by about
  a millimetre. `living_marble`'s `settled` was built 08-10 under
  SHELL_EPS 0.03; the constant became 0.05 on 08-11 and `settled` was
  never rebuilt. So the re-render is the fingerprint doing its job — a
  changed box means new cameras means new pictures — and it is one more
  sign that that scene's `settled` is a fossil.
