# SESSION 2026-08-25C HANDOFF — the pipeline ran end to end; your job is to make that boring

(Real date 2026-08-11, the day's third session. REVIEW_LOG R-S2-91..109.
Previous handoff: SESSION_2026-08-25B_HANDOFF.md. Commits
`b8f87f2..3ecde77`, 22 of them, tree clean.)

## READ THIS FIRST, IN THIS ORDER

1. This file, §0 through §4. Do not skim §3 — it is the trap list.
2. `docs/PARKED.md` — what NOT to work on, now five items.
3. `graph/stages.py` — the pipeline IS this file: four tuples
   (INTAKE 11 · RECORD 10 · CHAIN 12 · COMPOSE 13 incl. prep_viewer),
   the named funnel constants at the top, `PHASES_ORDER`.
4. `docs/PLAN_CHAIN_ENDS_2026-08-11B.md` — this session's working
   record: the six-defect table and every user ruling.

---

## 0. THE ONE-LINE TRUTH

**A raw Marble bundle became a furnished room through every one of the
46 stages, gates green, final gate PASS — but it took SIX fix-and-resume
cycles to get there. The pipeline has NEVER completed in one
uninterrupted invocation. Making that happen, on a scene that has never
run, is the whole job.**

## 1. WHAT THIS SESSION DID (summary; the primary record is REVIEW_LOG R-S2-91..109)

- **The chain now starts at the beginning.** Two new stage tables:
  `INTAKE` (frame→stitch→crops→vocab→bearings→detect→lift→recenter→
  filter→scale→shell) and `RECORD` (build_graph→build_edges→J0→J1→J5→
  build_judged→J3→J4→J6→resolved). `--phase` is now
  `core|record|graph|compose|all`, same table in both runners
  (`stages.PHASES_ORDER`). `--bundle <folder>` creates a scene from a
  world with no hand step, and refuses to repoint an existing one.
- **`fresh02`** (world `188a1d3f`, a rustic attic): intake 11/11
  (872.7 s), record 10/10 (345.6 s), graph 12/12 (~330 s), compose 12/12
  (1376.8 s). 15 objects placed, 0 clips, fit loop ran to DRY in 2
  rounds unprompted. First compose result ever with NONE of the five
  hand-fix files present at start.
- **Eight defects fixed**, six of them findable ONLY on a fresh scene
  (the six-defect table is in PLAN_CHAIN_ENDS). The headline one:
  `edge_carry` passed `wall_claim_dist` a plane where it wants a
  geometry, so **every layer from `voted` down had ZERO IN_WALL edges on
  every scene the project ever built**. fresh02's `voted` carries 31.
- **§6b executed:** `voted_edges` half-layer and `graph['vote']` block
  retired; loop-back judges read the voted LAYER via
  `scene_state.judge_view()`; `--edges-from voted` (the old spelling
  refuses with instructions). Proven equivalent pair-for-pair before
  removal.
- **Frame contract retuned at the right knob** (user ruling):
  `BOUNDS_TAIL_PCT` 0.5→0.05, margin untouched. 14→**29 of 34** worlds
  runnable. 33 of 34 colliders sit entirely inside their true cloud —
  the frames were never wrong; the percentile crop was.
- **Three caches, all verified byte-identical warm-vs-warm:** vocab
  (3m33s→3.0 s; global per-TERM dictionary + per-image pano cache — and
  it made the stage REPRODUCIBLE, the pano look-pass is nondeterministic),
  propose_edits (7m49s→0.17 s, per-scene, keyed on full prompt),
  consistency (pre-existing). ⚠ ALL THREE BUY RE-RUNS ONLY. A fresh
  scene still pays full price.
- **`paths.report_guard`**: a review-page builder may fail without
  killing a stage whose real output is committed (user ruling). Loud,
  writes `report_failures.json`, gate WARNs until fixed. Wired at ONE
  site (node_evidence); its docstring says why nowhere else.
- **User rulings executed:** `support_clip` RETIRED (banner on file),
  sub rounds DEFERRED, fit_feedback re-shop NOT BUILT (all three in
  PARKED.md §§3-5), `grouped` now inherits `shown` (28/28, was 0/28 —
  "a core function"), `prep_viewer` is the 46th stage (gate knows
  `repo:` paths now), fleet validates `--from/--until/--skip` at launch.

## 2. THE JOB: MAKE ONE UNINTERRUPTED RUN BORING

The user's words: *"reassure our pipeline is smooth, runnable and
correct. this is prep for the 100 scene batch."* World SELECTION for the
batch is the user's and is NOT your job.

**The bar:** `python run_scene.py --scene <new> --bundle <world>` on a
world that has NEVER run, completing all 46 stages with ZERO
intervention, final gate PASS. That has never happened — fresh02 needed
six resumes because six defects stood in the way. They are fixed; the
next run answers whether more are hiding.

**The order of work:**

1. **Static sweep** — imports, `run_scene.py --list` (46 stages),
   `--dry-run` on `autotest_living` (all four phases plan),
   `run_fleet.py --dry-run` over two scenes.
2. **Gate reports** on `fresh02`, `autotest_living`, `autotest_bedroom`
   — all three must PASS (fresh02 with exactly the four known WARNs of
   §3.2, no new ones).
3. **THE RUN.** Pick a BOX-SHAPED runnable world (green "runnable"
   filter in `marble-harvest/catalog/CORPUS_REVIEW.html`; read its
   prompt; avoid attic/loft/A-frame/vaulted — see §3.4). Unclaimed =
   no `out/*/bundle_path.txt` points at it. Then ONE command,
   `--phase all`, and DO NOT touch the scene by hand while it runs.
   ~55 min. If a stage fails: fix at the source scene-agnostically,
   log it at the NEXT FREE R-S2 number (a parallel session's
   PLAN_COLLIDER_OPTIONAL.md reserved 110+ — see §5), resume — and the
   bar then becomes running ONE MORE fresh world clean, because a
   resumed run is not the proof.
4. **The fleet path** — once one scene runs clean, `run_fleet.py` over
   2–3 scenes (the fresh one + clones) to prove the driver, the resume,
   and the morning report. Read the report the way the user will.
5. **Write the go/no-go** for the 100-batch, with the honest arithmetic:
   ~55 min/scene × N, sequential by design, GPU-locked. 100 scenes ≈
   4 days of machine time. 29 runnable worlds exist today, so "100
   scenes" awaits the user's corpus decision anyway — size the estimate
   to what exists.

## 3. THE TRAPS — every one of these bit someone this session

### 3.1 A PASSING CLONE PROVES NOTHING
Six of eight defects were invisible on every dev scene because dev
scenes carry artifacts the pipeline no longer produces (stale
`envelope.npz`, the retired `voted_edges` block, old `pano_crops/`, a
pre-existing graph). Evidence = a scene that has never run. This is the
session's central lesson and the reason your bar is a fresh world.

### 3.2 fresh02 IS A MACHINERY SPECIMEN, NOT A CLEAN ARTIFACT SET
Its final gate PASSes with **four true WARNs** — `bearings` and
`detect` stale against `vocab.json`, `shopping` and `rotation_check`
stale against `edit_proposals.json` — all caused by cache-testing
modules BY HAND outside `run_scene` after the run. Do not chase them;
do not "fix" the scene. Also its geometry is WRONG on purpose: it is an
attic, the shell decided the room is 1.64 m tall, and `scene_scale`
degraded to 1.0 (PARKED §3). Machinery evidence only.

### 3.3 DO NOT RUN MODULES BY HAND ON A SCENE MID-ANYTHING
That is how §3.2 happened, twice, in the session that also built the
locks against it. If you must run a module directly for debugging, use a
throwaway clone, never a scene whose artifacts anyone will read.

### 3.4 BOX ROOMS ONLY, AND READ THE PROMPT BEFORE ADOPTING
The shell fits vertical planes and one flat ceiling. Pitched/sloped
anything ⇒ garbage height ⇒ scale degrades. PARKED §3.

### 3.5 GPU PROTOCOL (docs/POWER_CRASHES.md — the machine HARD POWERS OFF)
- Clock lock `nvidia-smi -lgc 0,1500` from an ADMIN shell. ⚠ You cannot
  query whether it is on: nvidia-smi never reports an applied -lgc, and
  the GPUClockLock task runs as SYSTEM (invisible unelevated). The only
  proofs: the receipt at apply time, or `clocks.sm` ≤1500 under load in
  the watcher log. This session measured peak EXACTLY 1500 at 89.6 W —
  the lock was on. A crash IS a reboot and the boot task re-applies.
- ONE `watch_gpu.ps1` instance only. Two share the CSV and throw
  "Stream was not readable" (happened tonight; a day-old one from 08-10
  was still running — check with Get-CimInstance before starting one).

### 3.6 THE VIEWER
`viewer/data/<scene>.bin` is built by the `prep_viewer` stage now, so
new runs appear automatically. Old scenes need
`python viewer/prep_scene.py --scene <s>` once. Viewers die with the
terminal that (transitively) launched them; WMI-detached mostly
survives. Port 8321 historically living_marble; use 8322+ for others.

### 3.7 HOUSE RULES THAT ARE LOAD-BEARING HERE
- **No observation-triggered tuning** (rule #1): a threshold may not
  move because a test scene tripped it. Tonight's frame-contract change
  was legal only because a 34-world census + a user ruling backed it.
- **Trust the primary record, never a summary** — including YOUR OWN
  truncated grep output, which caused a real miss tonight (R-S2-102).
  Authority: pipeline_map.html → owning PLAN doc → REVIEW_LOG →
  docstrings → summaries.
- Every fix gets a REVIEW_LOG entry (R-S2-110 onward) with the
  What/Why/What-a-mistake-looks-like contract intro.
- Commit as Timotsui / timotsuihc@gmail.com. Plain English everywhere.

## 4. THINGS THAT LOOK WRONG BUT ARE RIGHT

| looks wrong | is right because |
|---|---|
| `graph['voted_edges']` / `graph['vote']` still in OLD scenes' files | retired blocks are read SECOND for pre-08-11 scenes; fresh scenes never get them (fresh02 has neither) |
| `rederive_voted_edges.py`, `support_clip.py`, `judge_cases.py` on disk | retired-on-disk convention; each carries a banner; do not wire them |
| dev scenes' layers have 0 IN_WALL edges on disk | built before the edge_carry fix; only a re-run rewrites them; fresh02 is the proof the fix works |
| `scale` ran but scene not rescaled (fresh02) | honest degrade — attic geometry, PARKED §3 |
| `fit_walk` seconds ≈ 0 in timing tables | it is the loop's exit test; near-zero when the loop is dry |
| `--phase core` runs different modules than old docs describe | the lane decision (R-S2-93); old week8-lane modules retired from the runner |
| four WARNs on fresh02's final gate | §3.2, self-inflicted, documented, left standing because they are TRUE |

## 5. UNTOUCHED AND WAITING (not yours)

- **World selection for the batch** — the user's, explicitly.
  `CORPUS_REVIEW.html` is built for it. 29 runnable · 5 frame-fail ·
  284 no-collider · 117 skipped-or-unsure.
- **living_marble** — not modified in any of today's three sessions.
  J9 gate open; user has ruled it low-priority ("fine as long as it
  kind of works").
- **The 284 missing colliders** — BUT SEE `docs/PLAN_COLLIDER_OPTIONAL.md`,
  which appeared from a PARALLEL session (not this one): it records a
  user ruling to trust Marble's positioning and make the collider
  optional, taking the corpus 29 → ~313. NOT started, and it RESERVES
  review-log numbers R-S2-110+. If that work has begun by the time you
  read this, coordinate before touching frame_bootstrap; either way LOG
  YOUR OWN ENTRIES AT THE NEXT FREE R-S2 NUMBER, not blindly at 110.
- Everything in PARKED.md: ctop, J9 quality, slanted walls, sub rounds,
  fit_feedback re-shop.

## 6. WHERE EVERYTHING IS

| thing | path |
|---|---|
| the pipeline, as data | `graph/stages.py` |
| the checkpoint | `graph/scene_gate.py` |
| one scene / many | `run_scene.py` / `run_fleet.py` |
| this session's record | `docs/PLAN_CHAIN_ENDS_2026-08-11B.md` + REVIEW_LOG R-S2-91..109 |
| corpus pages | `…\CS-8903-OVM\week8\marble-harvest\catalog\CORPUS_REVIEW.html`, `FRAME_CONTRACT_REVIEW.html`, `CATALOGUE.html` (NOT a git repo) |
| worlds | `…\CS-8903-OVM\week8\marble-harvest\worlds\<uuid>\` |
| scene output root | `…\CS-8903-OVM\week7\entangled_gen\out\` (paths.py OUT) |
| global vocab dictionary | `OUT\vocab_term_cache.json` (user-approved; PROMPT_VERSION-salted) |
| review-artifact failure marker | `out\<scene>\report_failures.json` (gate WARNs on it) |
