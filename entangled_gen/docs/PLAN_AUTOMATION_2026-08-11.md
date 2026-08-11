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

## 5. THE SECOND AUDIT — hazards AUTOMATION_READINESS.md missed

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
