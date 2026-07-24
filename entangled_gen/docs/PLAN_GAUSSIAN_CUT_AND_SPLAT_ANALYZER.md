# PLAN — Gaussian cut-out (GaussianCut) + detection comparison (splat_analyzer)

**This is the canonical plan + progress doc for this effort.** The orchestrating
agent MUST update the Progress Log below at every state change (step launched,
step finished, checkpoint passed, decision made). On session clear or crash, a
fresh agent resumes by reading this doc top to bottom, then continuing from the
first non-done row in the Progress Log. Do not start a step whose gating
checkpoint has not been passed by the user.

- Created: 2026-07-20
- Last updated: 2026-07-21 (Checkpoint 5 SECOND PASS presented; env builds
  still running)
- **OVERNIGHT RUN COMPLETE (2026-07-22 early AM).** Both lanes done; watchdog
  deleted (job finished its purpose; it caught 1 real double-stall + 1 real
  fine-run event loss, and raised 2 false alarms — both benign).
  MORNING ENTRY POINT: walk `docs\REVIEW_LOG.md` R1→R6 top to bottom.
  - Analyzer lane: env ✅ → runs ✅ (16 s low / 64 s high, 103 objects) →
    bridge ✅ (19/19 matched, no frame issues) → comparison page + cyan
    viewer layer ✅. Checkpoint 4's TWO decisions await user (R3).
  - Cut lane: SAM2 masks ✅ (R1; pass 4 falsified the base-mask lever —
    R4-is-desk-geometry hypothesis for user) → env ✅ (12 GB, extensions
    built) → cut attempt 1 partial fail (R4) → diagnostic → attempt 2
    obj_004_v2 w=3 PASS-WITH-REMNANTS (R5; w=10 kept in WSL) → cut review
    package ✅ → integration demo + background resolver + PIPELINE.md
    stage entry ✅ (R6; swap numerically verified, visually subtle because
    the mesh occludes the ghost region).
  - NOT done, by design (user-reserved): C4 adoption + batch-seeding
    decisions; C6 final verdict; cut-as-default-background; Step 12 batch.
  - Uncommitted code accumulated (commit as Timotsui after user review):
    cut\ + analyzer\ modules, viewer additive layers, place2 resolver,
    PIPELINE.md cut section, render_cut_review --variant.
- Current state: **OVERNIGHT AUTONOMOUS MODE** (user authorization
  2026-07-21, going to sleep: "use your best judgment if you can and then
  assume its right to move on"). Checkpoints do NOT hard-stop tonight:
  Claude records a PROVISIONAL verdict in `docs\REVIEW_LOG.md` and
  proceeds. All provisional verdicts are re-judged by the user tomorrow —
  a reversal invalidates downstream work (acceptable; nothing original is
  ever deleted/overwritten, all outputs are new files). Scope: this
  overnight run only; hard stops resume when the user returns.
- Overnight priority order: (1) pass-3 masks → provisional glance →
  (2) [when gaussiancut env lands] Step 10 lamp cut → Step 11 review build →
  provisional Checkpoint 6 → (3) [when analyzer env lands] Step 5 run
  (low-quality orientation check first, then full) → Step 6 bridge → Step 8
  comparison build → provisional Checkpoint 4 → (4) only if lamp cut
  provisionally good: extend cuts to 2–3 more well-detected manifest objects
  (masks via the same SAM2 route; manifest-box seeding — the batch seeding
  decision stays with the user) → (5) INTEGRATION DEMO (user asked
  2026-07-21): place2 composition rendered over the CUT background splat
  (retrieved lamp asset at obj_004 pose, original lamp removed) + viewer
  layer + PIPELINE.md stage-contract entry for cut/. USER DIRECTIVE
  (2026-07-21): integrate WITH the existing fallback — background source
  resolves automatically per scene: cut background.ply if present, else the
  existing tinted-floor clean view; pipeline never breaks on un-cut
  scenes/objects; explicit override flags for testing both paths. NOT overnight (reserved
  for user): cut-background as composition DEFAULT (Checkpoint 6 call),
  analyzer adoption into detection (Checkpoint 4 call), full batch Step 12.
  GPU discipline: at most one heavy GPU job at a time (12 GB shared between
  WSL and Windows); the analyzer run and SAM2 mask generation must not
  overlap.
- **Watchdog heartbeat** (2026-07-21, user-requested): a session cron job
  fires every 30 min (:17/:47) — checks lane liveness on disk (ENV.md
  existence, env-size growth, step outputs), kicks/relaunches stalled
  subagents, launches next steps when gates open, updates this doc +
  REVIEW_LOG. Session-only: it dies with the session (crash → resume
  protocol §7 covers restart; the heartbeat must be re-created manually if
  a fresh session resumes overnight work). Delete via CronDelete when the
  user returns. Known stall mode it guards against: a subagent's background
  install/compile finishing without resuming the agent (happened once
  2026-07-21 to BOTH env builds; caught by manual check, both kicked).
  Heartbeat size baselines (MB, for growth comparison):
  - HB1: gaussiancut env 5651 (+~1250 since kick → cuda-toolkit installing,
    LIVE), splatanalyzer env 5787 (~done), HF cache 593 (OWLv2 mid-download,
    LIVE). No stalls, no gates open yet.
  - HB2: ALL SIZES FROZEN (5651/5787/593), no ENV.md, no extensions in
    site-packages → BOTH lanes stalled a SECOND time (lost background-task
    completion events). Both agents kicked with a policy change: NO MORE
    run_in_background — all remaining installs/compiles run foreground with
    chunked timeouts (nohup+logfile+poll only if a step must exceed 10 min).
- Next user contact: tomorrow — walk `docs\REVIEW_LOG.md` top to bottom.

**Checkpoint 1 outcome (2026-07-21):** user approved both WSL envs + the 2-line
SH-0 patch. User freed C: space first (C: now ~317 GB free; WSL vhdx purge
removed all old conda envs). Pre-flight verified: Ubuntu-24.04 WSL, user=root,
conda 26.3.2 intact (base only), gcc 13.3, NO nvcc (envs must bring their own
cuda-toolkit via conda; note CUDA 12.1 nvcc needs gcc ≤12 → use conda
compilers), GPU visible in WSL: **RTX 4080 Laptop 12 GB VRAM** (correcting the
16 GB assumption in earlier docs — still sufficient for both tools), 944 GB
free inside WSL.

---

## 1. Purpose (plain language)

Our pipeline (`entangled_gen`) generates a room as a **3D Gaussian splat** (a
cloud of colored blobs; renders like a photo from any angle), then detects the
objects in it, retrieves matching 3D mesh assets, and places them. Problem: the
original objects are baked into ("entangled with") the splat, so a placed mesh
asset coexists with the ghost of the original object. Current workaround is the
"clean view" (mesh-only render + splat-tinted floor).

Two tools, two independent lanes:

1. **GaussianCut lane** — [GaussianCut](https://github.com/umangi-jain/gaussiancut)
   (paper arXiv 2411.07555, official author code): graph-cut segmentation of
   the splat's actual Gaussians, seeded by 2D masks. Goal: cut a chosen
   object's Gaussians OUT of the existing bedroom_marble splat → a background
   splat with the object cleanly gone. Kills the ghost problem without
   regenerating anything.
2. **splat_analyzer lane** — [splat_analyzer](https://github.com/nigelhartman/splat_analyzer)
   (MIT): renders a ring of cameras around a splat, OWLv2 open-vocabulary 2D
   detection, depth back-projection, cross-view clustering → fused 3D boxes.
   Goal: run on the same scene and compare its boxes to our scene manifest, to
   fix our documented detection weakness (60° of the room never rendered,
   15/20 detections from one view, exactly 1 cross-view merge).

## 2. Decisions already made (do not re-litigate)

- **No World Labs Marble regeneration** — costs credits. We cut the splat we
  already have. (The "clean plate" idea from image-blaster is rejected for
  this reason.)
- **Scene = bedroom_marble** (the splat all recent loop/viewer work uses).
- **First cut target = the freestanding lamp** (well-detected, minimal contact
  with other geometry). User may override at Checkpoint 3.
- **Lanes are fully decoupled** (user-approved "Option 2"): the GaussianCut
  lane seeds its masks from the EXISTING manifest box for the lamp; the
  analyzer verdict only upgrades box seeding later, at Step 12 (batch).
  Neither lane ever blocks the other before Step 12.
- **Orchestration model**: the main agent is an ORCHESTRATOR. It spawns
  subagents to execute steps (parallel where the flow allows), updates this
  doc, and talks to the user at checkpoints. It does not grind through long
  step work in its own context.

## 3. Standing user rules that govern this work

- **User judges ALL visuals.** The agent never concludes from rendered images;
  it builds review artifacts and hands over absolute paths.
- **NO MANUAL WORK in the pipeline** (2026-07-21): the user reviews and
  judges at gates; they never produce or fix artifacts by hand. Bad automatic
  output → build a better automatic stage. Never design a manual fallback.
  (This retroactively KILLS the "Option B hand-paint" fallback in the C5
  decision below.) Rationale (user): **"the pipeline is text to cad"** — the
  product is fully generative text→3D-scene; checkpoints are development-time
  stage validation, the shipped pipeline runs with zero human steps.
- **Every checkpoint MUST arrive as a visual review artifact** (2026-07-20):
  contact sheet, overlay page, before/after render strip, or viewer layer —
  never raw JSON/PLY/numbers alone. Even the feasibility checkpoint gets its
  findings as readable docs; every later checkpoint gets images or viewer
  layers the user can look at.
- **Checkpoints are hard stops** — present results, wait for the user.
- **Make review/help requests SUPER OBVIOUS** (2026-07-21): any message or doc
  state that needs the user's eyes or hands leads with a loud banner
  (`🔴 WAITING ON YOU — <what>`) followed by a numbered list of exactly what
  to review/decide, each with full path + what to look for. Never bury a
  review request under status reporting.
- **Every review item spells out What / Why / Look-for** (2026-07-21): per
  artifact — What (the thing + full path), Why (what decision this review
  gates; what breaks if wrong), Look for (concrete visual pass/fail criteria,
  e.g. "red box hugs the lamp in every view; shifted or mirrored box = camera
  math wrong"). Purpose is stated every time, never assumed from context.
- **Plain language**: every step/checkpoint referenced as "Step N — name"
  (number = flow order, descriptive name = meaning). No bare codes.
- **Full absolute paths** in anything handed to the user for review.
- **Torch rule**: the Windows system python runs torch 2.6.0+cu124 for the
  GPU seg/render stack. NOTHING may install into or upgrade it. All new tool
  environments are isolated (WSL conda preferred).
- **Commit identity for scene-pipeline repo**: Timotsui / timotsuihc@gmail.com.
- **serve.py gotcha**: the viewer server is a route table with NO static
  handler — every new asset needs an explicit route in
  `scene-pipeline\entangled_gen\viewer\serve.py`.
- **Frame gotcha**: `gen_raw.ply` is RAW space; physical up = -y under the
  rot180 convention. See `docs/SESSION_2026-07-05C_HANDOFF.md` before writing
  any camera files for external tools. This is the #1 silent-failure risk.

## 4. Key paths

| What | Path |
|---|---|
| Pipeline code (canonical) | `D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen\` |
| Scene data root (out/) | `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\` |
| bedroom_marble splat | `...out\bedroom_marble\gen_raw.ply` (107 MB) |
| Scene manifest (boxes) | `...out\bedroom_marble\scene_manifest.json` |
| Existing GPU views + poses | `...out\bedroom_marble\views\` |
| Existing seg outputs (GroundingDINO+SAM) | `...out\bedroom_marble\seg\` |
| Reference clones (read-only) | `D:\T\Documents\GeorgiaTech\Summer2026\Research\code\reference\{gaussiancut, splat_analyzer}\` |
| GaussianCut lane module code (new) | `scene-pipeline\entangled_gen\cut\` |
| analyzer lane module code (new) | `scene-pipeline\entangled_gen\analyzer\` |
| 3D placement viewer | `launch_viewer.bat` → localhost:8321 |

## 5. Flow (numbers = execution order; ⟂ = runs in parallel)

```
splat_analyzer lane: Step 2 probe → Step 4 env → Step 5 run → Step 6 bridge → Step 8 compare → CHECKPOINT 4
GaussianCut lane:    Step 1 probe → Step 3 env → Step 7 views → CHECKPOINT 3 → Step 9 masks → CHECKPOINT 5
                     → Step 10 cut → Step 11 review build → CHECKPOINT 6
Merge only at:       Step 12 batch+integrate (needs Checkpoint 4 verdict + Checkpoint 6 approval)
CHECKPOINT 1 (after Steps 1⟂2) gates both env builds. CHECKPOINT 2 fires only on build failure.
```

### Step contracts

- **Step 1 — gaussiancut-feasibility-probe** *(read-only)*. Clone GaussianCut
  to reference dir; pin: dataset dir layout, camera file format, mask format,
  rasterizer + CUDA build needs, invocation, output artifacts; check
  `gen_raw.ply` header attributes vs what its loader reads; recommend
  WSL-vs-Windows. → writes `entangled_gen\cut\FEASIBILITY_GAUSSIANCUT.md`.
- **Step 2 — analyzer-repo-probe** *(read-only)*. Clone splat_analyzer to
  reference dir; pin: local-CLI invocation (ignore server/Docker mode), full
  dependency list and WHETHER IT PINS TORCH, camera-ring design, depth source,
  clustering, `interactions.json` schema; recommend isolation strategy.
  → writes `entangled_gen\analyzer\FEASIBILITY_SPLAT_ANALYZER.md`.
- **CHECKPOINT 1 — format-and-environment approval.** User reads both
  feasibility docs, approves environment locations.
- **Step 3 — gaussiancut-environment-build** ⟂ **Step 4 — analyzer-environment-build.**
  Isolated envs (per Checkpoint 1 decision) + smoke test each + `ENV.md` each.
- **CHECKPOINT 2 — build-trouble stop** *(conditional)*: only if a build
  fails; report exact errors, do not thrash.
- **Step 5 — analyzer-run**: splat_analyzer on the recentered/raw
  bedroom_marble PLY (decide from Step 2 findings which; record it), category
  vocabulary = same list our detection stage used. → `out\bedroom_marble\analyzer\`
  (raw `interactions.json` + its frames/depths).
- **Step 6 — format-bridge** (`analyzer/bridge_boxes.py`): `interactions.json`
  → manifest-style box JSON (separate file; NEVER writes the real
  `scene_manifest.json`). Prints sanity report; boxes outside the room
  envelope = frame-mismatch flag raised to user, not silently fixed.
- **Step 7 — view-pack** (`cut/prep_views.py`): ~15 views of bedroom_marble
  via existing render tooling (`rendertools\`), cameras written in the format
  Step 1 pinned. → `out\bedroom_marble\cut\dataset\`.
- **CHECKPOINT 3 — view-coverage review**: user reviews a contact sheet of
  the views (coverage of the lamp + any frame/orientation error).
- **Step 8 — detection-comparison-review build**: viewer layer (analyzer
  boxes in distinct color vs manifest boxes; explicit serve.py routes) + a
  comparison page (per-category counts, sole-source finds, cross-view merge
  counts, coverage vs the 60° blind wedge).
- **CHECKPOINT 4 — detection-quality judgment**: user decides (a) analyzer's
  fate: replace our detection stages / borrow camera-ring+clustering / keep as
  cross-check; (b) which box set seeds Step 12 batch masks.
- **Step 9 — mask-pack** (`cut/make_masks.py`): lamp's manifest 3D box
  projected into each Step-7 view → SAM box-prompt (existing seg stack) →
  per-view masks. → `out\bedroom_marble\cut\dataset\multiview_masks\`.
- **CHECKPOINT 5 — mask-quality review**: overlay review page; user
  approves/rejects per view (rejects are dropped — GaussianCut accepts any
  mask count). Fallback: user hand-masks in Segment-and-Track-Anything's UI;
  contract only cares that mask PNGs exist.
- **Step 10 — graph-cut-run** (`cut/run_cut.py`): GaussianCut on the
  assembled dataset → `out\bedroom_marble\cut\<object>\foreground.ply` +
  `background.ply` + Gaussian-count stats.
- **Step 11 — cut-review build**: render background.ply from the SAME seven
  judge-view cameras (`render_judge_views.py` rig) for before/after; viewer
  layers: original ↔ cut background ↔ extracted object (explicit serve.py
  routes).
- **CHECKPOINT 6 — cut-quality judgment**: user judges halos, floor holes,
  wall damage, foreground completeness.
- **Step 12 — batch-cut-and-integrate** *(gated on Checkpoints 4 + 6)*: cut
  all manifest objects (masks seeded per Checkpoint 4 verdict) → emptied
  background splat → `place2` composes on real background; implement the
  analyzer adoption decision.

## 6. Progress Log (orchestrator: update on EVERY state change)

| # | Step / Checkpoint | Status | Artifacts / notes | Updated |
|---|---|---|---|---|
| 1 | gaussiancut-feasibility-probe | **DONE** | `cut\FEASIBILITY_GAUSSIANCUT.md`; clone @ 93d24a4. Verdict: runnable on gen_raw.ply as SH-degree-0 (header verified, 1.92M Gaussians); needs fabricated scaffolding (cfg_args, COLMAP text sparse/0, images/ per camera); 2 CUDA extensions to build (vendored MODIFIED rasterizer — no stock wheel) + glm clone; SAM-Track NOT needed at runtime; SH-0 render crash landmine → 2-line patch; fine cut = CPU min-cut, maybe hours | 2026-07-20 |
| 2 | analyzer-repo-probe | **DONE** | `analyzer\FEASIBILITY_SPLAT_ANALYZER.md`; clone @ a3cd884 (MIT). Verdict: runs as-is on gen_raw.ply — frame assumption (up = file −y) MATCHES ours; output boxes in input-file frame; torch unpinned but only zero-compile path = py3.10 + torch 2.4.1+cu124 + prebuilt gsplat 1.5.3 wheel; run_local.py standalone CLI; ~7 GB VRAM; watch: max_per_label=3 cap, min_votes=8 vs 24-frame low preset, silent upside-down failure mode → first run eyeballed at --quality low | 2026-07-20 |
| C1 | format-and-environment approval | **PRESENTED — awaiting user** | decision items in §6a | 2026-07-20 |
| 3 | gaussiancut-environment-build | **DONE (SUCCESS)** | `cut\ENV.md`. Env `gaussiancut` (12 GB): py3.10.20, torch 2.1.1+cu121, nvcc 12.1.105, gcc 11.4 (12.4 hit pybind11 parse bug), PyMaxflow; BOTH vendored extensions built (apply_weights kernel verified on GPU), glm @5c46b9c0, SH-0 patch applied (+debug-flag drop; diffs in ENV.md §5). 6 surprises resolved (ENV.md §6; notable: setuptools 69.5.1 pin, numpy 1.26.4 pin, MSYS URL-mangling → PowerShell wsl calls). Runnable repo /root/gaussiancut | 2026-07-21 |
| 4 | analyzer-environment-build | **DONE (SUCCESS)** | `analyzer\ENV.md` (incl. Step-5 command template). Env `splatanalyzer`: py3.10.20, torch 2.4.1+cu124 (verified unchanged), gsplat 1.5.3+pt24cu124 binary wheel (`--no-deps`, real CUDA raster smoke-tested), transformers 4.50.3, OWLv2 = google/owlv2-base-patch16-ensemble cached 593 MB (loads offline). run_local.py --help clean. ~6.3 GB total. Note: HB2 stall report was a false alarm for this lane (OWLv2 base ≈ 620 MB, download was complete) | 2026-07-21 |
| C2 | build-trouble stop | (conditional) | — | |
| 5 | analyzer-run | **DONE (both phases)** | Phase 1 low: 16 s, 11 objects, orientation PROVISIONAL PASS (R2). Phase 2 high: **64 s**, 5.9 GB VRAM, 192 frames/8 standpoints, 12,564 raw → **103 final objects**, 7/8 standpoints contribute (phase-1 pathology gone; standpoint 0 = zero evidence). Cap raised 3→8 (diff in ENV.md); door NOT truncated at 7; cap 8 itself binds on 5 labels (bookshelf/book/painting/shelf/bed). Zero detections: office chair, yoga mat, potted planter. Data: `out\bedroom_marble\analyzer\job_high\interactions.json` (RAW frame, same as manifest). Caveats for bridge: surface-biased centroids, fabricated z-extent (w+h)/2, axis-aligned boxes | 2026-07-21 |
| 6 | format-bridge | **DONE** | `analyzer\bridge_boxes.py` → `bridged_boxes.json` (103 boxes ana_000–102, RAW frame). Envelope sanity: 2/103 centers outside, 43 partial overhangs (wall-flush + fabricated depth — expected), NO frame mismatch. `match_report.json`: 19/19 manifest matched (min 0.045 / med 0.258 / max 0.594 m); 67 analyzer-only clusters; synonym map documented. Watch: observed min cluster votes 3 vs config default 8 — semantics unresolved | 2026-07-21 |
| 7 | view-pack | **DONE** | `cut\prep_views.py` (standalone, idempotent). Dataset @ `out\bedroom_marble\cut\dataset\` (15×900² PNGs; COLMAP sparse\0 cameras.txt/images.txt/points3D.ply; shot.py sidecars for Step 9). Cameras: 7 judge-rig + 8 offset from 3 standpoints. Numeric checks ALL PASS: center round-trip 9.4e−16 m; vs 03_render.py Cam.project 0.0006 px; parsed by GaussianCut's own loader, reproj 0.0047 px. Lamp = obj_004, in frame 8/15 views (as designed) | 2026-07-21 |
| C3 | view-coverage review | **PASSED** | User verdicts: (1) lamp box hugs lamp → camera/COLMAP math VISUALLY CONFIRMED; (2) coverage accepted — lamp stands against window/wall, its back is physically unobservable from in-room (7/15 views not seeing it is by design); (3) obj_004 confirmed sole lamp target. Consequence recorded: wall-facing side of the cut has no mask evidence → inspect window/curtain damage behind lamp at Checkpoint 6 (note: known 0.205 lamp×window interpenetration sits exactly there) | 2026-07-21 |
| 8 | detection-comparison-review build | **DONE** | `analyzer\comparison.html` (C4 banner + count tables + match table + analyzer-only groups + caveats box); viewer: cyan "analyzer boxes" layer + label sprites, explicit `/analyzer_boxes.json` route (curl-verified 200/404, server killed after; vendoring changes untouched, additive edits only); `build_comparison.py` idempotent | 2026-07-21 |
| C4 | detection-quality judgment | **PRESENTED — REVIEW_LOG R3 (provisional analysis only; BOTH decisions reserved for user)** | Adoption call + batch-mask-seeding call await user; numeric picture strongly favors analyzer (19/19 matched, 91/103 multi-standpoint) but the 67 extra clusters need user eyes | 2026-07-21 |
| 9 | mask-pack (lamp, manifest box) | **DONE** | `cut\make_masks.py` (idempotent, `--views` partial redo). 8 masks @ `cut\dataset\multiview_masks\` — format verified vs GaussianCut contract (L-mode, {0,255}, stems match, stray files auto-purged). SAM = facebook/sam-vit-base (same stack as seg_views.py), box-prompt, best-of-3. All numeric guards pass (areas 0.19–1.95%, inside-fraction 0.88–1.00); stats in `mask_stats.json`. NOTE: obj_004 box spans 0.70–1.40 m height — anything of the lamp below 0.70 m lies outside every prompt | 2026-07-21 |
| C5 | mask-quality review | **pass 3 PROVISIONAL PASS (overnight, REVIEW_LOG R1)** — SAM2 video propagation (facebook/sam2.1-hiera-large via transformers 5.13.0, zero installs, torch unchanged 2.6.0+cu124); view order cut_d_lamp→b_right→b_lamp→b_left→yaw000→c_left→c_lamp→c_right; all 8 masks 100% in-box; Claude viewed 4/8 overlays incl. all previously-rejected views — clean lamp coverage, no window/table bleed. USER RE-JUDGES tomorrow. History: | User verdicts (2026-07-21): cut_c_lamp bleeds onto WINDOW (the dangerous systematic case), cut_d_lamp bleeds onto table, cut_c_right misses part of the lamp, all views bleed somewhat. Ruled normal for coarse box-prompts on a small object vs busy background — but not acceptable. **USER DECISION (explicit): Option A then Option B** — (A) upgrade make_masks.py with crop-zoom + positive center point + negative background points, redo ALL 8 for consistency, re-present; (B) any view A still gets wrong, the USER hand-paints the mask PNG (Option C stronger-model download held in reserve, needs separate approval; Option D accept-as-is rejected). **Second pass shipped 2026-07-21:** crop-zoom (2× rect, ×1.4–2.8) + shade-positive point (documented deviation: box-CENTER positive was numerically falsified — center lands on window pixels at pole height, spill 16–50% into obj_008 window box — replaced by shade point 20% below box top) + corner/window-zone negatives + box-consistent candidate selection. Areas grew in all 8 views (fixes under-segmentation); 5/8 inside-fraction 0.90–0.98; 3 flagged no-box-consistent-candidate: cut_b_lamp, cut_b_left, cut_c_left (vit-base ceiling at lamp/window boundary → Option B/C). Pass-1 archived (mask_stats_pass1.json, mask_overlays\pass1\). **SECOND PASS REJECTED by user 2026-07-21 ("its worse") — automatic SAM masking (vit-base) is exhausted per the documented decision; proceeding to Option B (user hand-paints), base set + tooling being decided. Numeric containment stats proved NOT predictive of user-judged mask quality — do not trust them as a gate for future objects.** | 2026-07-21 |
| 10 | graph-cut-run | **DONE** | `obj_004\foreground.ply` (**382** lamp Gaussians) + `background.ply` (1,919,618; layout-identical to gen_raw) + stats.json; 382+1,919,618=1,920,000 verified 3 ways; fg/bg semantics verified (graphcut.py:162-177, no swap possible). Threshold 0.6 chosen by census+purity rule (box census 2,232 exact / 4,352 @+10cm → band recalibrated [558,8928]); thr 0.3 rerun = bit-identical (choice moot). Fine stage **196 s** (not hours). fg 100% within box+0.15 m, stops 9 cm short of window face, `fg_in_plausible_band:false` flagged for honest review. HB6 "died" alert was FALSE — run had finished; watchdog looked one dir too high. ROOT CAUSE of night's stalls found: WSL kills nohup/setsid on wsl.exe exit → [[wsl-background-process-gotcha]] memory + run_cut.py detached-wsl.exe + done-marker pattern. `run_cut.py` ready for Step-12 batch | 2026-07-21 |
| 11 | cut-review build | **DONE** | `obj_004\cut_review.html` + renders\ (34 PNGs: 15 after-frames, 3 fg-only, 8+8 crops); viewer layers "cut background"/"lamp only" + additive `/cut_background.ply` `/cut_foreground.ply` routes (curl-verified, server killed); `render_cut_review.py` idempotent | 2026-07-21 |
| C6 | cut-quality judgment | **attempt-1 PROVISIONAL PARTIAL FAIL (R4) → improvement iteration running** | Orchestrator glance: extraction = shade+upper arm only; arm skeleton + base remain as ghosts (matches fg=382 vs census 2,232, nothing below 0.865 m). Machinery verified; selection under-covers thin/low geometry. Iteration 1 result (score_diagnostic.json): threshold lever DEAD (0.15/0.3/0.6 all byte-identical, fg=382). Two diagnosed causes: (1) BASE = structural mask gap — Step-9 prompts started at 0.675 m, base scores exactly 0.0 despite being rendered (mask never covered it); (2) POLE = fine-stage energy balance — 167 pole seeds ≥0.6 rejected by min-cut (smoothness n-links ≈10 vs unary weight 1; graphcut.py:135,149-152). **Iteration 2 (FINAL tonight), revised mid-flight:** pass-4 masks FAILED their target (SAM2 ignored box-bottom extension; 0/310 R4 Gaussians covered; masks ≈ pass 3) BUT exposed that R4 spans 0–0.70 m to the FLOOR → reinterpretation: R4 = desk-front/floor geometry masks CORRECTLY exclude (lamp is a desk lamp, base ON desk ~0.75 m = inside R2 band); R4 zeros are right behavior, hypothesis for user to verify. Re-cut DONE: w=3 winner (fg 582; R2 pole 0→170/254; R3 329/487; ZERO contamination all purity metrics; fg bottom 0.718 m = base-on-desk reached; w=10 kept in WSL for cheap flip). obj_004_v2\ complete + review package rendered. **R5 PROVISIONAL: PASS WITH REMNANTS** (faint arm trace + dark desk-level reveal smudge — user judges acceptability; R4-is-desk-geometry hypothesis logged for one-glance verification). Energy-balance diagnosis empirically confirmed: user_weight_term was the operative lever. Batch cuts NOT run (recipe needed per-object tuning — unvalidated for batching); integration demo proceeding on v2 | 2026-07-21 |
| 12 | batch-cut-and-integrate | not started (gated C4+C6) | — | |

### 6a. Checkpoint 1 decision items (presented 2026-07-20)

1. **Environments — recommendation: two SEPARATE WSL Ubuntu conda envs** (both
   probes independently landed on WSL):
   - GaussianCut env: python 3.10 + torch 2.1.1 + cu121; builds 2 vendored
     CUDA extensions (Linux gcc/nvcc far more reliable than MSVC); requires
     cloning glm headers into `third_party/glm` (missing from vendored tree).
     ~8–10 GB.
   - analyzer env: python 3.10 + torch 2.4.1+cu124 + prebuilt gsplat 1.5.3
     wheel from docs.gsplat.studio/whl/pt24cu124 (the ONLY zero-compile
     combination; PyPI's gsplat JIT-compiles and would fail). ~7–8 GB.
   - Combined ~15–18 GB onto the WSL vhdx on C: (C: has ~77 GB free —
     acceptable but flagged; vhdx is already 246 GB).
2. **SH-0 landmine fix — recommendation: 2-line patch** to GaussianCut's
   render_utils.py (hardcodes 15 f_rest coefficients; crashes on our
   degree-0 model) rather than padding our PLY to SH-3 (+346 MB). Foreground
   PLY is saved BEFORE the crash point either way.
3. **Noted for Step 5 (no decision now):** analyzer first run at
   `--quality low` with user eyeballing frames (silent upside-down failure
   mode); `max_per_label=3` hard cap may need a source edit; `min_votes`
   likely needs lowering for the 24-frame low preset.
4. **Noted for Step 7:** COLMAP pose synthesis from our view sidecars is the
   #1 frame-risk step; verification = GaussianCut's own render-vs-groundtruth
   outputs, judged by the user (visual).

## 7. Resume protocol (for a fresh agent after session clear / crash)

1. Read this doc fully. Read `plain-language-rule`, `verification-workflow`,
   `full-paths-for-review` memories (they are summarized in §3 but memories
   are authoritative).
2. Check the Progress Log for the first non-done row. Verify its claimed
   artifacts actually exist on disk before trusting the status (a crash may
   have interrupted mid-write).
3. If a subagent was mid-flight when the session died, its partial outputs
   are untrusted — rerun the step (steps are standalone and idempotent by
   design; outputs are plain files).
4. Continue as orchestrator: subagents do the work, this doc gets updated,
   the user gets checkpoints. Never skip a checkpoint the user hasn't passed.
