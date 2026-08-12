# SESSION 2026-08-25 HANDOFF — the pipeline runs itself

(Real date 2026-08-11, overnight, orchestrated while the user slept.
REVIEW_LOG R-S2-84. Previous handoff: SESSION_2026-08-24_HANDOFF.md.)

## THE HEADLINE

The ask was: *"it cannot run autonomously from top to bottom. Fix this and
make sure we can run 100 scenes automated with smooth and no problems,
with clear boundaries between modules, and clear state checkpoints in
between."*

**It runs.** Ten of the eleven graph-chain stages — everything but the
hour-long vote — ran from ONE command, with no human in the loop, and
every checkpoint passed before and after every stage:

```
[run_fleet] 1 scene(s) from --scenes
[1/1] autotest_living: PASS  0h01m59s
  doubts  voted  voted_edges  j8  j8s  settled  views  evidence  j9  grouped
  all rc=0, all gates before=True after=True
  final gate PASS: ended on `grouped`, no stale layers, 46/46 nodes have a picture
```

**`living_marble` WAS NOT TOUCHED.** Its `scene_graph.json` is unchanged
since 02:49, before this session. All the work was done against
`autotest_living`, a 2.0 GB clone made for the purpose. **Your J9 gate on
`living_marble` is still open and still yours to decide.**

---

## 1. WHERE TO PICK UP

**Read this first:** `docs/PLAN_AUTOMATION_2026-08-11.md`. It is the plan,
the progress log, the second audit, and the list of what was deliberately
NOT fixed. Everything below is a summary of it.

**Two things want your judgement, and neither blocks anything:**

1. **The J9 question from last session is still open** — does J9 see one
   picture per member or two? Nothing done overnight touched it. The
   change site is still `graph/judge_same_product.py` ->
   `member_crop_paths()`.

2. **NEW: the chain has no judge for a duplicate the vote itself
   creates.** See §4. This was found by running the chain and comparing
   node counts, and it is a design decision, not a repair.

**To run a scene now:**

```
python run_scene.py --scene S                    one scene, both phases
python run_scene.py --list                       print the chain
python run_scene.py --scene S --phase graph --dry-run    see the plan
python run_fleet.py                              every scene with a splat
python run_fleet.py --scenes-file tonight.txt --resume
python graph/scene_gate.py --scene S --report    is this scene healthy
```

---

## 2. WHAT CHANGED, AND WHY

### The order stopped living in a person's head

`graph/stages.py` is the chain as DATA — one row per stage naming the
command, the layer it reads, the layer it writes, the files it must
produce, and whether it costs model calls or GPU. The eleven commands now
appear in no runner and in no document. Add a stage by adding a row.

That row is also the module's whole boundary with everything else, which
is what "clear boundaries between modules" turned out to mean in practice:
a stage may look at nothing older than `reads` and must leave `writes`
current and fresh.

### The checkpoint

`graph/scene_gate.py` asks the questions no stage can ask about itself:

| | question |
|---|---|
| `before` | is the layer this stage reads present and NOT stale? |
| `after` | did this stage really write, JUST NOW, what it promised? |
| `final` | did the run FINISH — nothing stale, chain ended on `grouped`? |

Exit 3 for a gate failure, distinct from 1 (crash) and 2 (`node_evidence`
refusing an evidence layer with holes).

**The mtime test is the point.** `after` requires each promised file to
have been written DURING that stage's run. Existence only proves some
earlier run made it. Told on the clone that `doubts` had just run when it
had not, the gate answered:

> `graph/vote_doubts.json` exists but was NOT written by this run (last
> written 10097s before the stage started). The stage did nothing and
> exited 0 — the next stage would have read the previous run's answer.

That is the hazard the whole exercise was about, caught mechanically.

### The six no-op flags are inverted

Writing is now the DEFAULT in `record_vote_doubts`, `build_voted`,
`rederive_voted_edges`, `materialize_layers` and `node_evidence`;
`--dry-run` is the opt-out; `node_views` uses `--no-render`.

⚠ **`--apply`, `--render`, `--recut` and `--reshoot` still parse and now
DO NOTHING.** They were kept so no old script breaks — but it means an old
command line from a handoff or from shell history now misleads in the
opposite direction. The docs say so; you should know it too.

### `node_evidence` will not write a layer with holes

Exit 2, naming the nodes. `--allow-holes` overrides and records the gap IN
the layer. A gap in the evidence stops the scene because a judge
downstream reads that layer as proof.

### `run_fleet.py` — the hundred

One bad scene never stops the night. `--resume` skips scenes whose gate
already passes. `--scene-timeout` (4 h default) bounds a wedged scene.
The morning table (`out/fleet_<runid>.{json,html}`) puts the gate's WARN
and INFO lines beside each verdict, because **a scene can PASS and still
be poor** — the gate checks the machinery, never the answers.

---

## 3. THE SECOND AUDIT — what the readiness doc had missed

Most of it is fixed. The full list is in the plan doc §5.

- **`scene_graph.json` was rewritten non-atomically by four stages.** It
  is 1.5 MB, it holds the whole scene, and it is NOT re-derivable —
  detection, lifting, description and edges are all upstream. Two of the
  four run right after a GPU stage, on the machine whose failure mode is a
  power cut. Now `paths.write_atomic` everywhere (temp, fsync, rename).
  Line endings deliberately unchanged, so no scene gets a spurious
  whole-file diff.
- **A corrupt preview manifest was swallowed** and the file rewritten with
  this run's ids only — every other object's elected box gone, exit 0.
  Now fatal.
- **The `.ply` header parser looped forever on a truncated file**,
  appending `b""` until the machine swapped to death. A hang is worse than
  a crash unattended. Now bounded.
- **A truncated `_box.png` was kept forever**, because staleness there was
  mtime-only and a cut during the save leaves a file NEWER than its
  source. It was then handed to J9 as the node's one picture. Now verified
  and re-made.
- **THE WORST ONE: a model outage was becoming a scene full of confident
  defaults.** Auth, invalid-key and credit-balance errors were caught by
  the same handler as a timeout. An expired token at scene 40 would give
  every J8 case `UNCLEAR conf 0.00`, ship every J8s region uncut, leave
  every J9 member unassigned — and every gate would pass, on all 60
  remaining scenes. Those three are now fatal. **The check was also in the
  wrong order**: a 401 exits non-zero too, so the old code raised a plain
  exit-code error and never reached the credential test. Each stage now
  records `judge_failures {defaulted, total, ids}`. **No threshold was
  invented** — where that line falls is your call, and the gate only
  reports the number.

---

## 4. THE NEW OPEN QUESTION — a duplicate nobody judges

Found by re-running the chain on the clone and comparing it node by node
against the original. The clone came out with **46 settled nodes; the
original has 45.**

`build_edges` proposes SAME_CANDIDATE edges — "these two might be one
object" — and J1 (`judge_pairs.py`) answers them. **But J1 runs on the
RECORD, before the vote.** The vote then moves every box, and that can
propose a brand new candidate that no judge in the chain ever sees. On
this scene it did: two chairs, `obj_020` and `obj_068`, ended up 96%
contained in one another. `materialize` merges only pairs whose verdict is
SAME, so an unjudged candidate is silently NOT merged and the scene ships
a duplicate object.

**Why nobody noticed.** `living_marble`'s `settled` HAS the merge,
recorded 08-10. Its `voted` and `voted_edges` were rebuilt on 08-11 —
after — and that rebuild wiped the verdict, because both stages re-derive
edges geometrically and nothing carries a verdict across. So the merge
survives only as a fossil in a layer whose inputs are gone. Re-run the
chain today and it does not happen.

**Not fixed.** Answering it means either a judge that runs on post-vote
candidates, or a rule that carries J1's verdicts across the vote. Both
have your name on them. What was done: the gate now WARNs on every scene
where a SAME_CANDIDATE edge reaches the end without a verdict, so the hole
is counted on all 100 runs instead of being absorbed in silence.

---

## 5. STILL OPEN, DELIBERATELY

- **`ctop` has never detected anything, 0 for 11.** Untouched. It is a
  design question about how the vote sees tall and flat objects, and the
  chain runs without solving it — it just measures those objects poorly
  and now says so on every scene (`9 of 46` on this one).
- **J8's concurrency of 8 multiplies GPU renders, not just model lanes.**
  Stimulus building moved inside the worker, so up to 8 concurrent WSL
  rasterisations run on the machine whose failure mode is GPU burst. NOT
  changed — the concurrency ruling is yours (08-04) and reversing it is a
  judgement, not a repair.
- **A `shell=True` timeout does not kill a WSL render.** Python kills
  `cmd.exe`; the renderer keeps the GPU. `run_fleet`'s per-scene timeout
  is the outer bound; orphans still need looking for by hand.
- **`graph['shown']` stores supplementary view paths ABSOLUTE** while the
  main picture path is relative. A scene folder cannot be moved or
  archived without breaking them. Left alone rather than changed under
  J9's open gate.

---

## 6. TEST ARTEFACTS ON DISK

- `out/autotest_living/` — the 2.0 GB clone. Safe to delete; it is where
  every destructive test ran.
- `out/autotest_broken/` — a scene with an empty graph, kept because it is
  a useful one-line regression fixture for "does the fleet isolate a bad
  scene". Delete if it bothers you.
- `out/fleet_2026*.json|html` — the test fleet reports.

---

## 7. METHOD NOTE

Last session's note said the gap for an unattended run is that *a per-node
metric that is true still cannot tell you the picture is of the wrong
thing.* That held again tonight, twice, and both times the answer was the
same: **compare a re-run against the original and look at what differs.**
The `--dry-run`-writes-nothing claim was checked by hashing the graph
before and after, not by reading the code. The duplicate-chair hole in §4
was found by counting nodes in two files, not by reasoning about the
chain. Neither would have been caught by anything the stages print about
themselves.
