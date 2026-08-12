# SESSION 2026-08-24 HANDOFF — the machine, the evidence layer, and J9's door

(Real date 2026-08-10 into 2026-08-11. REVIEW_LOG R-S2-79..82.
Previous handoff: SESSION_2026-08-23_HANDOFF.md.)

## THE HEADLINE

Two things blocked the scene and both are cleared. The **machine** was
hard-crashing under GPU load — diagnosed, mitigated, documented. Then the
**evidence** every judge reads turned out to be stale for 35 of 45 nodes —
fixed at source and promoted into a graph layer that J9 now reads.

**J9 IS READY TO RUN AND HAS NOT BEEN RUN.** The sheets are built, no
model calls spent. Everything below is the state it will run against.

---

## 1. WHERE TO PICK UP

**Look at this first:**
`out/living_marble/graph/same_product_sheets/index.html` — exactly what
J9 will judge on, 8 pools, every member with a picture.

**Then one decision, then run it:**
J9 currently sees ONE picture per member (its main photo). Each node now
also carries supplementary views (235 across the scene) that it is NOT
being given. For a "same product?" judgement two angles may beat one.
Changing it changes what the judge sees, so it wants a ruling.

WHERE THAT CHANGE IS MADE, if the user says yes:
`graph/judge_same_product.py` -> `member_crop_paths()`. It early-returns
`[shown[mid]]` — the main photo alone — when the node has one. To give the
judge more, append from `graph['shown'][nodes][id]['shown']['views']`
(each entry has `path`, `view`, and `occluders_removed`) up to
`CROPS_PER_MEMBER` (currently 2, line ~112). The sheet builder already
lays out up to that many side by side, so nothing else needs touching.
⚠ Some supplementary views are cone-culled — occluders in front of the
object were deleted. `occluders_removed` marks them. The user ruled that
acceptable for evidence but the judge is not currently told; if those go
in, say so in the prompt.

**RUNNING THINGS (both were left alive at session close, may not be):**
- viewer: launch via WMI `Win32_Process.Create` (a plain background
  process dies with the tool shell's job object) —
  `python -u viewer\serve.py --scene living_marble --port 8321`
- GPU watcher: `tools/watch_gpu.ps1`, launch the same way. See
  docs/POWER_CRASHES.md §6.

**Then:** `judge_same_product.py --scene living_marble` (LLM), followed by
`materialize_layers.py --scene living_marble --apply` to rebuild
`grouped`, which is correctly marked stale.

**THE CHAIR QUESTION HAS CHANGED SHAPE.** The old J9 gate was
"obj_021+028 vs obj_041+068 — two chair models or one?". **obj_068 no
longer exists** — J1 merged it into obj_020 (96% containment, recorded in
obj_020's `merged_from`). The chair pool is now FIVE:
obj_010, obj_020, obj_021, obj_028, obj_041. Ask the question again
against that set; the old framing does not apply.

---

## 2. STATE OF THE GRAPH (living_marble)

```
check()  : (True, 'current layer: shown')
current  : shown          stale: ['grouped']
live     : record, judged, resolved, voted, settled, shown
shown    : 45 nodes, 45 with a picture, 0 problems
vote     : run_kind=full, canon_eligible=True, run_id=r20260811-000149
```

`grouped` is stale ON PURPOSE — it was built before `shown` existed and
needs J9 + materialize to rebuild it. That is not a fault to fix, it is
the chain telling you what is owed.

---

## 3. WHAT LANDED, IN ORDER

### The machine (R-S2-79, docs/POWER_CRASHES.md)

Four hard power-offs in one day, three during vote runs. Not thermal
(71 °C peak), not a bugcheck — the rail collapses and the OS never sees
it. Mitigation is `nvidia-smi -lgc 0,1500` from an admin shell: peak
clocks 2400 → 1500 MHz, peak draw 140 → 99 W, zero crashes since.

The lock dies on reboot, and the failure IS a reboot — so a crash used to
clear it and the retry ran unprotected. ✅ **CLOSED 2026-08-11:**
`tools/install_gpu_clock_lock.ps1` was run and registered the scheduled
task **`GPUClockLock`** (nvidia-smi -lgc 0,1500, as SYSTEM, at every
startup, on-battery restrictions disabled). Nothing to do before a long
run any more.

⚠ One claim made while proposing it was FALSE and is corrected on record:
an unelevated session CANNOT trigger the task with `schtasks /run` — a
SYSTEM task is not visible or startable by a standard user. The boot case
is covered; re-applying mid-session still needs an admin shell.

Also found: **battery at 77 % health after only 78 cycles** (design
90,005 mWh, actual 69,260). Abnormal for the cycle count and a plausible
cause of the whole problem — a weak pack cannot cover the CPU+GPU burst
the adapter does not. USER PARKED the replacement; the decision rule is
in POWER_CRASHES.md §9 (read `batt_rate_mW` from a crash log first).

`tools/watch_gpu.ps1` logs GPU + battery at 1 Hz, one flushed line per
sample so the tail survives a power cut. Start it before long runs.

### The vote (R-S2-79/80)

Full re-run done, **canon_eligible=True**. Determinism verified (one node
voted twice under the same sha/params gave identical intermediates).
SHELL_EPS 0.03 → 0.05 by user ruling — walls improved, and the same
constant governs the floor so floor-standing objects lifted off the
ground. USER RULED: keep 5 cm everywhere, snap will re-seat them.
⚠ snap SHIFTS a box, never GROWS it, so the lost height persists into
shopping. Revisit if picks come back short.

**⚠ `ctop` HAS NEVER DETECTED ANYTHING: 0 for 11, while `top` is 22/23.**
`ctop` is the fallback plan camera and gets the hardest objects by
design, so 11 of 32 objects fall back to a full-height wedge that
re-measures nothing. Their boxes ship roughly as they arrived.
`materialize` flags them `slice_fallback`. NOT caused by any recent
change — the pre-rewiring renders are the same pictures (mean pixel diff
< 2/255). **Do not fix this casually**; it is a design question about how
the vote sees tall and flat objects.

### The evidence layer (R-S2-81/82) — the big one

**`graph['shown']` now exists** and is the state of the scene: `settled`
verbatim plus, per node, the ONE picture it is seen as, and the other
views that still frame it. J9 reads it and says so in the log. This
closed a gap the module was written for and never had: the gate and the
renderer were both write-only, while seven readers went on picking
detector crops by detection score.

**The main-photo rule (user):** crop from the default view → re-cut of
that same photo → and only then a new render. Final split:
**24 re-cut, 10 kept crop, 11 new render.** The new render is at the
CAPTURE HEIGHT at the position nearest the standpoint that can frame and
see the object; **7 of 11 came out at 0.00 m from the standpoint** — the
default camera, turned.

`scene_state.stamp()` now marks every downstream layer stale
automatically, so a rewritten layer cannot leave a newer-by-order layer
built from older inputs. On a fresh scene the sweep does nothing.

---

## 4. THE AUTOMATION GAP — read docs/AUTOMATION_READINESS.md

User-requested full write-up of what stops this running over 100 scenes.
**IT IS NOT AUTOMATABLE TODAY.** Three blockers:

1. **Six of ten stages do NOTHING without a flag and exit 0 doing it.**
   A runner that forgets one gets success and no work.
2. **`node_evidence` writes a layer with HOLES and calls it done.**
3. **Nothing gates on a run FINISHING** — a scene can end with a stale
   layer and report success.

Plus `run_scene.py` stops at `lift_pano` and knows none of the 11 graph
steps. The doc has the verified command order, the per-scene scan, and
the fix order. **User agreed to do this LATER — it is the next real
piece of work.**

⚠ ORDER GOTCHA: `materialize_layers` writes `settled` with
`--settle-only` and `grouped` without. Running the full one too early
writes `grouped` from a state J9 has not seen. That happened this
session and is why `grouped` ended stale.

---

## 5. UNCOMMITTED — NOW ~7 SESSIONS DEEP, 22 PATHS

```
M  graph/{build_voted, judge_multiplicity, judge_same_product,
          materialize_layers, node_views, record_vote_doubts,
          scene_state, split_cuts, view_cams}.py
RM graph/recrop_gate.py -> graph/node_evidence.py
RM experiments/pool_retake.py -> experiments/render_aimed_views.py
M  slicevote.py, vote_cams.py, viewer/{serve.py, index.html}
M  docs/{REVIEW_LOG, PLAN_NODE_EVIDENCE_2026-08-10}.md
?? docs/{AUTOMATION_READINESS, POWER_CRASHES}.md
?? tools/{install_gpu_clock_lock.ps1, vote_diff_sheet.py, watch_gpu.ps1}
?? docs/SESSION_2026-08-24_HANDOFF.md (this file)
```

✅ **COMMITTED 2026-08-11, working tree clean.**
- `dcee7e7` the evidence layer + the machine fix (everything above)
- `a8f369d` the PowerShell tools forced to plain ASCII

⚠ **PS 5.1 READS `.ps1` AS ANSI UNLESS THERE IS A BOM.** A single em-dash
inside a quoted string broke install_gpu_clock_lock.ps1 with a "missing
closing brace" reported twenty lines later; watch_gpu.ps1 had the same
fault and survived only because its em-dashes sat in comments. Keep .ps1
files ASCII. Related: NEVER edit a file via a PowerShell
Get-Content/Set-Content round-trip — it re-encoded view_cams.py mid-session
(BOM added, every em-dash mangled) and had to be repaired. Use the editor.

---

## 6. STILL TEMPORARY, REMOVE WHEN RULED

- `viewer/serve.py` box_sources: `vote_ab_old` / `vote_ab_new`, currently
  the SHELL_EPS 0.03 vs 0.05 pair.
- Backups scattered in `out/living_marble/`: `_pre_*_backup*.json`,
  `_powertest_backup/`, `node_views.json.*.bak`.

## 7. METHOD NOTE WORTH CARRYING

Three times this session I reported something working and the user found
it was not, by looking at the pictures. Every number being printed was
TRUE each time — in-frame percentage, distance-to-standpoint, attach
counts — and none could catch a constant vertical offset or a file
arriving from the wrong camera under the right name. For the unattended
run this is the real gap: a per-node metric that is true still cannot
tell you the picture is of the wrong thing.
