# RUNNING THE GRAPH CHAIN UNATTENDED — what is missing, and how to finish it

Written 2026-08-11. The goal this serves is Rule #1: **the pipeline runs
itself over ~100 scenes with no human in the loop.**

Everything from the vote onward currently runs BY HAND, one command at a
time. That is how it was run on 2026-08-10/11 and it worked — but a
human chose each command and each flag. This file is what a next agent
needs to make that unnecessary.

---

## 1. THE CHAIN, IN ORDER, WITH THE FLAGS THAT ACTUALLY DO SOMETHING

Verified by running it end to end on `living_marble`, 2026-08-11.

```
 1  slicevote.py                  --scene S
 2  graph/record_vote_doubts.py   --scene S --apply
 3  graph/build_voted.py          --scene S --apply
 4  graph/rederive_voted_edges.py --scene S --apply
 5  graph/judge_multiplicity.py   --scene S                 (J8,  LLM)
 6  graph/split_cuts.py           --scene S                 (J8s, LLM)
 7  graph/materialize_layers.py   --scene S --settle-only --apply   -> settled
 8  graph/node_views.py           --scene S --layer settled [--render]
 9  graph/node_evidence.py        --scene S --recut --reshoot --apply -> shown
10  graph/judge_same_product.py   --scene S                 (J9,  LLM)
11  graph/materialize_layers.py   --scene S --apply                 -> grouped
```

**STEP 7 AND STEP 11 ARE THE SAME MODULE, AND THE DIFFERENCE MATTERS.**
`materialize_layers` writes `settled` with `--settle-only` and `grouped`
without it. Run the full one too early and you write `grouped` from a
state J9 has not seen — which is exactly the mistake made on 08-11 and
why `grouped` ended the night marked stale. Geometry first (7), group
last (11).

**WHY 8 AND 9 SIT WHERE THEY DO.** `node_evidence` reads `settled` BY
NAME, never "whatever is current", because it feeds J9 and `grouped` is
J9's own output — evidence taken from `grouped` would hand J9 back its
own verdict as proof of itself. So step 7 must have run, and step 11
must not have.

**STEP 8 IS USUALLY FREE.** On the 08-11 run it needed 0 renders for 33
of 35 repairs, because the vote's own renders already framed the boxes.
`--render` only costs GPU when a node genuinely has no usable picture.

---

## 2. THE BLOCKERS — WHAT MUST BE FIXED BEFORE THIS CAN BE LEFT ALONE

### 2.1 Six stages do NOTHING without a flag, and exit 0 doing it

| stage | silently a no-op unless you pass |
|---|---|
| `record_vote_doubts` | `--apply` |
| `build_voted` | `--apply` |
| `rederive_voted_edges` | `--apply` |
| `materialize_layers` | `--apply` |
| `node_views` | `--render` |
| `node_evidence` | `--apply --recut --reshoot` (three of them) |

This is the single biggest hazard. A runner that forgets a flag gets
**success and no work done**, and the next stage reads the previous
run's answer. `record_vote_doubts` is the case already on record: without
`--apply` it updates `vote_doubts.json` but NOT the graph `vote` block
J8 reads, and J8 has judged stale doubts because of it.

**THE FIX: invert the defaults.** `--apply` becomes the default; add
`--dry-run` to opt out. The safe default for an unattended chain is "do
the thing", because a missing flag should be an error, not silence.
Every one of these already prints a clear DRY line, so the dry path
survives as an explicit choice.

### 2.2 `node_evidence` writes a layer with HOLES and calls it done

Run it with `--apply` but without `--recut --reshoot` and it writes
`graph['shown']` with `problems: N` — nodes whose picture was planned but
never produced. Observed: `43 node(s) with a picture, 2 problem(s)`, exit
0. On scene 57 of 100 that is a silent hole in the evidence a judge then
uses.

**THE FIX:** refuse to write the layer when `problems > 0` unless an
explicit `--allow-holes` is passed. A gap in the evidence layer should
stop the scene.

### 2.3 Nothing checks the run FINISHED

A scene can end with `grouped` marked stale and the runner reports
success. The information is all there — `scene_state.check()` passes,
`graph['layer']['stale']` lists it, the log says
`[state] ... marked stale` — but nothing gates on it.

**THE FIX:** an end-of-scene gate that fails the scene when any layer in
`graph['layer']['stale']` is non-empty, or when
`scene_state.current_name(graph) != 'grouped'`.

### 2.4 The chain is not in the runner at all

`run_scene.py` stops at `lift_pano` / `manifest_pano_to_raw` — the
geometric core. Steps 1–11 above exist only in this file and in whatever
a human remembers. PIPELINE.md still says of the vote: *"Still not in
the canonical runner; dashed node on pipeline_map.html."*

**THE FIX:** extend `run_scene.py` with the 11 steps, `--skip` support
per stage as it already has, and stop-on-first-failure as it already
does. The order and the flags then live in ONE place.

---

## 3. THE SCAN — HOW TO CHECK A SCENE RAN PROPERLY

Run these after a scene. Each is cheap and answers one question.

### 3.1 Did every stage actually write?

```powershell
python -c "
import json,sys; sys.path.insert(0,'graph'); import scene_state
g=json.load(open(r'<scene_dir>/scene_graph.json',encoding='utf-8'))
print('live layers :', scene_state.present(g))
print('stale       :', (g.get('layer') or {}).get('stale'))
print('current     :', scene_state.current_name(g))
print('check()     :', scene_state.check(g))
"
```

PASS = live layers end at `grouped`, `stale` is empty, `check()` is True.

### 3.2 Did the evidence layer come out whole?

```powershell
python -c "
import json
g=json.load(open(r'<scene_dir>/scene_graph.json',encoding='utf-8'))
sh=g.get('shown') or {}
print(sh.get('counts'))
"
```

PASS = `with_picture == nodes` and `problems == 0`.

### 3.3 Did the judges see the new evidence or fall back?

Grep the J9 log for the line it prints every run:

```
[same_product] evidence: graph['shown']: N node(s) carry a picture
```

FAIL = `graph['shown'] absent` or `graph['shown'] is STALE` — the judge
silently used detector crops instead.

### 3.4 How much of the vote was actually measured?

```
grep -c "FALLBACK WEDGE" <scene>/slicevote_*.log
```

On living_marble this was **11 of 31** slices. A fallback wedge means the
plan view found nothing and the box shipped roughly as it arrived — see
§4.1. Worth recording per scene; a scene where most slices fell back has
not really been measured.

### 3.5 Are the flags right?

The no-op trap in §2.1 is invisible from output. Until the defaults are
inverted, check the actual command line:

```
grep -E "record_vote_doubts|build_voted|rederive|materialize|node_evidence" run.log \
  | grep -v -- "--apply"
```

Any hit is a stage that did nothing.

---

## 4. KNOWN DEFECTS THAT SURVIVE INTO EVERY SCENE

### 4.1 `ctop` plan shots have NEVER detected anything — 0 for 11

The vote's plan view has two cameras: `top` (inside the room) and `ctop`
(above the ceiling, ceiling deleted, near-vertical). Measured on
living_marble: **`top` 22 detections / 23 shots, `ctop` 0 / 11.**

`ctop` is the fallback, so it is handed the hardest objects by design —
tall things and things high on shelves. On living that was all three
bookshelves, all five magazines, the floor lamp, plant and tv stand.
When it fails the slice falls back to a full-height wedge that only
constrains left–right, so nothing re-measures the box and it ships
roughly as it arrived. `materialize` now flags these as
`slice_fallback` open questions, which is how to find them per scene.

NOT a regression, NOT caused by the R-S2-77 rewiring: the pre-rewiring
borrowed renders are the SAME pictures (mean pixel difference < 2/255).
It has presumably always been this way and was invisible because the
review sheet did not show the plan shot. It does now.

### 4.2 `node_views.py --only <ids>` REWRITES the whole plan file

It writes `node_views.json` containing ONLY the named nodes, silently
shrinking the file every downstream reader trusts. Fine for a scoped
repair, wrong if anything later expects the whole scene.

### 4.3 The GPU clock lock does not survive a reboot

This machine hard-powers-off under GPU burst (docs/POWER_CRASHES.md).
The mitigation is `nvidia-smi -lgc 0,1500`, applied per boot — and since
the failure IS a reboot, **a crash always clears the lock and the retry
runs unprotected.**

✅ **CLOSED 2026-08-11.** `tools/install_gpu_clock_lock.ps1` was run and
registered the scheduled task **`GPUClockLock`** — `nvidia-smi -lgc 0,1500`
as SYSTEM at every startup, on-battery restrictions disabled. After a crash
the lock is back before anyone logs in.

⚠ Note a claim made when this was proposed and later found FALSE: an
unelevated session CANNOT fire the task with `schtasks /run`. A task
running as SYSTEM is not visible or startable by a standard user (access
denied on query, run, and reading the task file). The task covers the BOOT
case, which was the hole that mattered; re-applying mid-session still needs
an admin shell.

### 4.4 Big objects cannot be framed from inside the room

`view_cams.standoff` wants `1.5 x half-extent / tan(27.5deg)`, which for
a 3 m object is ~4.6 m in a room 4.7 m wide. The 08-11 change pulls the
camera back toward the capture standpoint instead of dropping the view
(culls fell 114 -> 53), but a camera pulled 5 m is no longer really the
view it claims to be. `pulled_in_m` on each view records how far it
moved; treat large values with suspicion.

---

## 5. FOR THE NEXT AGENT — THE ORDER I WOULD DO IT IN

1. **Install the GPU clock task** (§4.3). Everything else is pointless if
   the machine dies mid-run. One elevated click.
2. **Invert the six defaults** (§2.1). Mechanical, low risk, and it
   removes the failure mode that is hardest to notice. Re-run the chain
   on `living_marble` afterwards and diff the graph against
   `_pre_*_backup.json` — nothing should change.
3. **Make `node_evidence` refuse holes** (§2.2). Small.
4. **Extend `run_scene.py`** with steps 1–11 (§2.4). This is where the
   order stops living in a person's head.
5. **Add the end-of-scene gate** (§2.3), then run TWO scenes back to back
   unattended and check §3 on both.
6. Only then scale up.

**Do not** attempt §4.1 (the `ctop` failure) as part of this. It is a
design question about how the vote sees tall and flat objects, it needs
the user's judgement, and the chain runs without solving it — it just
measures those objects poorly and says so.

---

## 6. WHAT IS ALREADY SAFE

Worth knowing so it is not re-litigated:

- **Stale layers resolve themselves.** Writing layer N marks N+1..end
  stale automatically (`scene_state.stamp`), and a stale layer is skipped
  by `current()`. On a fresh scene nothing downstream exists so the sweep
  does nothing.
- **J9 degrades instead of failing.** No `shown` layer, or a stale one,
  and it falls back to detector crops and SAYS SO in the log. A scene
  that skipped `node_evidence` still completes.
- **The vote stage is deterministic.** `obj_010` voted twice under one
  sha/params gave identical intermediates to the digit, so differences
  between runs are code or parameters, never drift.
- **Every stage prints an additive check** — how many other top-level
  graph blocks it touched. Should always be 0.
- **Renders are fingerprinted.** A changed camera DELETES the stale png
  rather than silently reusing it.
