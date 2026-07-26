# SESSION 2026-07-25 HANDOFF — analyzer deep-dive, ANALYSIS restructure, vocab + detect bake-off

Read this first on resume. `pipeline_map.html` (repo root) is the source of
truth for the pipeline shape; this doc records what changed today, what
awaits USER JUDGMENT, and what's wired vs pending.

## Decisions made today (all user-confirmed)

1. **Step skeleton v2:** 1 WORLD → **2 ANALYSIS** (sub-stages 2.1 OBSERVE ·
   2.2 DETECT · 2.3 LIFT · 2.4 PLACE) → 3 COMPOSE. Map redrawn as horizontal
   bands with titles/margins. History annotations ("was …") scrubbed.
2. **2y (4-yaw render) RETIRED. No standalone yaw track.** The splat lane is
   now **hybrid h** = analyzer observation (multi-standpoint 360° sweep) +
   our detection stack + OUR mask lift (3h2, was 3y2) + a port of the
   analyzer's vote filter into the fuse.
3. **Candidate a reframed:** splat_analyzer is NOT a third paradigm — it's
   the yaw paradigm with coverage turned up. Its detect is word-list OWLv2
   (the old map's "no word list / pure geometry" claim was wrong). Its lift
   is 1-px + fabricated z-extent (superseded by 3h2). Its standpoint
   sampling is random-with-guardrails (density band-pass, no visibility
   reasoning). Sub-map: `scene-pipeline/splat_analyzer_map.html`.
4. **Pano track KEPT** as possibly complementary; decide later.
5. **Word list ADOPTED (vocab_build.py):** exactly two sources — prompt
   mining ∪ fast-VLM image mining (claude.exe haiku on bundle pano + 8
   level sweep frames). Word list = an OBSERVE output (map node 2v, middle
   column under the view producers). Room dict = fallback only.
   `seg_views.py` now prefers `OUT/<scene>/vocab.json`.
6. **Collider mesh:** user-verified "generally good" in the viewer (new
   unlit fill+wireframe layer). ICP registration says scale 0.95008 —
   promoting the ICP matrix into `manifest_pano_to_raw.py` is the candidate
   fix for the pano lane's convention transform; **DEFERRED until after the
   front-end cleanup.**

## AWAITING USER JUDGMENT (next session starts here)

- **DETECT bake-off page** (built today, not yet reviewed):
  `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\detect_compare.html`
  Ours (GroundingDINO+SAM raw, thr .35, top-20/frame): 1639 dets / 154 of
  192 sweep frames. Theirs (OWLv2 POST-VOTE survivors only — tool never
  writes raw): 2482 evidence boxes / 160 frames. Plus ours on the 20 pano
  crops (195 dets, same vocab), no analyzer equivalent.
  LOOK FOR: (1) real objects on our side that the vote killed everywhere;
  (2) real objects only OWLv2 finds (the only argument for running both
  detectors); (3) whether our junk is scattered (vote fixes) or consistent
  across frames (vote would CONFIRM it); (4) who catches small stuff
  (pencil holder / pot / books).
- **vocab.json lists** (user wanted to evaluate):
  `…\out\bedroom_marble\vocab.json` — 27 terms (22 prompt · 13 pano ·
  9 frames). Pano = workhorse (only source of pencil holder/pot); frames
  weak + unstable in 4-image batches; prompt-only list is partly VLM
  under-reporting (desk lamp/office chair/monitor DO exist in scene).
- **Standpoints page** (how the analyzer sees):
  `…\out\bedroom_marble\analyzer\standpoints_view.html` + viewer :8321
  "analyzer cams" layer (serve.py route /analyzer_cameras.json).
- **R1–R7 in docs/REVIEW_LOG.md — still ALL blank.** R3's "103 vs 19" now
  has documented confounds (bigger vocab + synonym duplication + patched
  8-per-label cap saturation; 5 labels hit the cap, 8× "bed"): see the 3a2
  card caveat on the map.

## Key idea parked at session end (spec next: the 3h2 fuse contract)

> UPDATE 2026-07-25 (later session): spec DRAFTED — `docs/SPEC_3H2_FUSE.md`,
> awaiting user review. Nothing implemented.

**Unified lift pool.** Pano↔RAW is verified (A2b: p_raw = (x, −y−H, z),
H=1.31 here, pano eye at RAW (0,−1.31,0)). So pano crops can be lifted by
splat z-buffer depth FROM THE PANO VIEWPOINT — no collider, no
registration risk. Then pano crops + sweep frames = ONE pool of views →
same detect → same SAM masks → same mask lift → ONE vote pool. Candidate p
stops being a separate lane and becomes the sharpest views in the pool.
Vote-filter port upgrades over theirs: 3D-IoU clustering (not radius),
visibility-normalized vote threshold (not absolute 8), size-agreement as a
third signal; keep two-sidedness (≥k frames AND one confident peak); lower
detect thr 0.35 → ~0.2 once the vote exists.

## New/changed files today (ALL UNCOMMITTED in scene-pipeline)

- `splat_analyzer_map.html` (NEW) — sub-map of the ext tool's 7 stages.
- `pipeline_map.html` — full restructure (bands, hybrid, vb node, caveats).
- `entangled_gen/vocab_build.py` (NEW) — the adopted word-list builder.
  Gotcha: claude -p auto-allows reads only under cwd → pano call runs with
  cwd = bundle dir. haiku model; 3 calls/scene.
- `entangled_gen/detect_compare.py` (NEW) — bake-off page builder.
- `entangled_gen/seg_views.py` — vocab.json priority (+ prints source).
- `entangled_gen/viewer/serve.py` — /analyzer_cameras.json route
  (newest analyzer/job_*/transforms.json; ?job= override).
- `entangled_gen/viewer/index.html` — "analyzer cams" layer (numbered
  standpoint spheres + 192 look rays); collider layer fixed (was
  rendering BLACK: lit material + failed light → now unlit fill +
  wireframe); HUD labels de-collided ("collider mesh" vs "amodal:collider").
- Data (not code): `out/bedroom_marble/` gained `vocab.json`,
  `seg_sweep/` (192-frame GroundingDINO+SAM run), `seg_pano_v2/` (crops
  rerun with vocab.json), `detect_compare.html` + `detect_compare/`,
  `analyzer/standpoints_view.html`.

Suggested commit split when asked: (viewer additions) / (map restructure +
sub-map) / (vocab_build + seg_views wiring + detect_compare).

## Environment notes

- HuggingFace was 429-rate-limiting HEAD checks → run seg with
  `HF_HUB_OFFLINE=1` (models cached). Applies to any transformers load.
- Viewer server was started today: `python entangled_gen/viewer/serve.py
  --scene bedroom_marble` on :8321 (may still be running).

## Standing open items (unchanged today)

- FIND details + graph node pruning wait on R1–R7 verdicts.
- Rewires pending from the 2y retirement: seg input → job frames (done as
  a manual run today, not wired into scene_ready), lift cameras →
  transforms.json adapter, agent package photos, C7 reference photos.
- PIPELINE.md still describes the pre-07-24 shape (viewer leads, doc lags)
  — renumber after the FIND/OBSERVE details land.
- 8 old manifests still need re-lift (ST mirror bug follow-up).
- vocab TODO: reverse-containment merge (chair/office chair, mat/yoga
  mat); per-image or stronger-model frame calls; RAM/Florence-2 as the
  someday open-source swap.
