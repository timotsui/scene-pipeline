# 2026-07-15B handoff — C7 loop built, 3 live runs, blind-zone finding

Same day as SESSION_2026-07-15_HANDOFF.md (collider closeout); this session
built the C7 loop instead of starting with the facing rule — user call:
"write the shape of the loop stage first or we will be stuck smoothing the
pipeline forever". Facing stays a C6 initializer problem.

## What exists now (all in composition/)

- **`loop.py`** — the C7 propose→verify loop per the README "C7 loop
  contract": v1 ops = `add` + `nudge` ONLY (swap/remove/flip deferred);
  one VLM critique per iteration over ORIGINAL/RECREATION pairs, per-edit
  free geometric validation → apply → re-render → before/after VLM verify;
  accept ONLY "better"; append-only `package/edits.jsonl` (Reflexion memory
  — rejections carry WHY into the next critique, identical re-proposals are
  key-blocked, corrected variants invited); resume keeps numbering + memory.
  `add` runs the C1–C5 chain in-process for the one box (NO CLIP — no
  detection crop; best fit in the C5 band wins) and appends to
  shortlists2/picks2 with `source:"loop"` on accept.
- **`collide.py`** — deterministic mesh collision: solid voxel occupancy,
  3 cm pitch, global-grid snap, cache on placement signature; pair score =
  shared/smaller voxels, RATIO_MAX 0.05; nudges may not WORSEN a collision
  past it, adds must come in under it. CLI: `python collide.py --scene <sc>`.
- **`place2.py`** — optional per-entry `yaw` (render-frame deg, rotates
  about placed bbox center; floor contact survives) and
  `composite_views(outdir, prefix, splat_bg)`; defaults unchanged.

## The three runs (bedroom_marble, sonnet surrogate via bridge)

1. **Run 1** (splat-composite recreations): 1 accept — door obj_012 yaw
   +45° (the loop repairing FACING from renders). But recreations
   composited meshes OVER the splat → user spotted the flaw: missing
   objects never look missing, mesh changes get backfilled. Zero adds, 3
   dscale nudges falsely called "identical" (pixel diffs said 16k–60k px).
   Archived: `package/loop/run1_splatbg/`.
2. **Run 2** (mesh-only recreations, flat grey; splat only in ORIGINAL
   targets): splat-masking confirmed — 2 adds proposed immediately;
   "window air conditioner unit" ACCEPTED end-to-end (single-box chain live
   inside the loop = pick-object-after-layout demonstrated). collide.py
   later showed that AC interpenetrates the window (0.093) — VLM-plausible,
   geometrically wrong; motivated the collision gate.
3. **Run 3** (collision gate + feedback): 0 accepts, 11 calls, 4 iters —
   and 0 is CORRECT. 5 adds + 1 nudge rejected on real mesh collisions
   (incl. blocking the AC from moving DEEPER into the window, 0.093→0.296);
   the VLM answered feedback with corrected variants, never exact repeats.

## KEY FINDING: judge-camera blind zones auto-reject adds

The 4 horizontal fov-75 cameras at the center rig cannot see (a) the floor
within ~2.1 m of the rig — three floor-mat adds rendered 0 px in ALL views —
or (b) the four 15° wedges between views (poster add at x≈-0.95, z≈-0.93:
0 px everywhere). Verify then honestly reports "identical" → neutral →
reject. Same root cause as the detection coverage gap, now measured from
the judging side. **The camera coverage fix (6 yaws at 60° + a raised,
downward-tilted or off-center camera) is the loop's next unblock** — cheap
here: new judge pairs only need splat renders from the new cameras
(rendertools) + the same composite call; no re-detection required.

Secondary: sonnet's verify misses small REAL changes (3–4k px edits called
identical) — neutral-reverts are safe but cap fine tuning. Crop-zoom of the
edited region into the verify prompt, or a stronger judge, are the options.

## State / open user judgments

- `composed_state2.json` = base + door yaw + AC add;
  `composed_state2_base.json` = pre-loop snapshot; canonical
  `composed2_view_*.png` + glb rebuilt. Verdicts PENDING on: door edit, AC
  add (weigh its 0.093 window interpenetration), recomposed-base renders
  (from the earlier session), Marble bare-walls question.
- Full trace: `package/edits.jsonl` + `package/loop/critique_it*.json`.
- Queued idea (user, this session): plug OUR base scene into the GLTS loop
  — fills the "our init + their loop" cell of the 2×2 ablation
  (init × refinement); needs a feasibility read of TreeSearchGen's loop
  seam first; park until the loop is stable.

## Rerun

`python loop.py --scene bedroom_marble [--max-iters 4] [--max-edits 4]
[--model sonnet]` from `composition/`, Windows python — resumes journal.
Collision table: `python collide.py --scene bedroom_marble`.
