# S4 SHOPPING — design notes from the old C1–C5 chain (mined 2026-07-27)

**Status: REFERENCE for the future S4 design — NOT a design.** Compiled by a
research pass over `composition/` + the retrieval-era handoffs, on the user's
07-27 directive ("reference the old pipeline to see if there is any ideas that
are good; other approaches OK; keep everything modular with evaluable I/O").
The S4 design itself gets written only when the step is reached
(PLAN_COMPOSE_LOOP.md method).

## Headline conclusions

1. **Crown jewels to port verbatim:** `retrieve2.fit()` (6-permutation
   orientation-aware fit, uniform-scale factoring, tiling k=1..3) and
   `pick.py`'s policy — **dimension is a GATE (fit cap + scene-median scale
   band), relevance chooses INSIDE it**; never argmax on fit.
2. **The module the redesign is for:** `match_categories()` + the label→
   category agent map. Judged canonical names remove the detector-noise-repair
   job; the COVERAGE job remains (objathor has no rug category). Appearance
   fields enter SCORING, never the gate (rug-hijack lesson: free text must not
   gate).
3. **Drop:** `_mount()`/`WALL_LABELS` (superseded by supported_by), MIN_CONF
   detector threshold (existence is the graph's judgment), the v0
   token-overlap path, `crops.py` as a module (graph ships crops), `bridge.py`
   (LLM channel = the call_claude pattern).
4. **Dataset-level caches are inherited, not rebuilt:** `_mesh_sizes.json`,
   `_mesh_yaw.json`, `_thumbs/`, `_clip_vitb16.npz` under the objathor root.
   `fixup.py` = the cache-coherency tool (repoint its imports).
5. **`loop.py apply_add()` (lines 137–211) is the working re-shop template**
   (shortlist → measure → refresh_sizes → RE-shortlist → gate) — lift into
   `reshop_one()`; judge-driven replaces DO have crops + a complaint, so the
   old no-CLIP-for-adds carve-out dies.

## 1. The old chain, module by module (verified against code)

Contract rule (composition/README.md): stages talk ONLY through files in
`out/<scene>/package/`. Canonical order — note the deliberate **double
retrieve2** (annotation sizes recall → measured sizes precision):

    retrieve2 → measure → retrieve2 → thumbs → relevance → pick → place2

- **C1 `retrieve2.py`** — per manifest box ≤24 ranked candidates →
  `package/shortlists2.json` (candidate = uid, category, size_cm, score,
  k/axis/perm/scale, aspect_resid, log_scale; lower score = better).
  Mechanisms: MIN_CONF 0.35; `match_categories()` CATEGORY FIELD ONLY
  (descriptions never vote) tiers 0 exact / 1 token-subset / 2 overlap /
  3 unmatched; `map_labels_agent()` one batch LLM label→category map
  (validated against the real category list; tier becomes the STRING
  "agent" — typing inconsistency to fix); `fit()` 6 axis perms, optimal
  uniform log-scale factored out, score = aspect residual + 0.5·|log scale| +
  0.3 upright penalty; `best_fit_config()` tiling k=1..3 along the long
  horizontal axis, 0.25/copy penalty; `_mount()` hardcoded WALL_LABELS +
  0.25 m floor heuristic (→ DROP), `_mount_ok()` gates on catalog
  onWall/onFloor/onObject flags (→ KEEP). Doc drift: README says `yaw_fit`,
  code writes `perm`.
- **C1-support `retrieve.py`** — `catalog()` reads objathor
  annotations.json.gz; **Y-UP GATE**: annotation `size` is z-up for ~72% of
  the catalog; real size from thor_metadata bbox, overridden by the
  measured-mesh cache; `refresh_sizes()` = sanctioned mid-process refresh
  (same row objects → mutation visible to all holders; what re-shop needs).
  The v0 `shortlist()`/`run()` path (token overlap + blind agent pick) is
  dead.
- **C2 `thumbs.py`** — orientation-correct thumbnail cache, dataset-level
  (`_thumbs/<uid>[_perm].png`); `perm_rotation()` lives here and is the
  shared rotation primitive (proper rotation, parity absorbed, never a
  mirror) — export somewhere neutral.
- **C2.5 `measure.py`** — true mesh extents post-yaw-fix (`_mesh_sizes.json`),
  canonical-yaw cache (`_mesh_yaw.json` = the re-measure key), robust
  density-edge extents + junk census (`_mesh_robust.json`, flag ratio <0.90).
  `footprint_yaw()` min-area rectangle, accepted only if footprint shrinks
  ≥8%; yaw recovered MOD 90° — facing unresolved. Chicken-and-egg documented:
  measure only walks already-shortlisted uids → hence the double retrieve2.
- **C2.5-support `assets_thor.py`** — loader + THE catalog swap point;
  applies `_fixups/<uid>.glb` overrides, cached yaw, user-gated
  `prune_protruding` (never drops a component >15% of surface area).
- **`fixup.py`** — purges every cache that baked in old geometry for a uid
  (sizes, robust, thumbs, GLB, CLIP image keys; text keys preserved).
- **C3 `relevance.py`** — CLIP ViT-B/16: `clip` = clean crop ↔ orientation-
  corrected thumb; `clip_txt` = "{category}. {description}" ↔ crop; NEVER
  merged (low clip + high clip_txt = suspect render/orientation, not wrong
  asset). Additive write-back into shortlists2.json; embedding cache
  `_clip_vitb16.npz`. Re-orders, never filters.
- **C3-support `crops.py`** — projects 3D AABBs into views, picks the view
  with MAX PROJECTED AREA; `<id>_clean.png` (tight, no lines) = CLIP query,
  `<id>.png` (padded, green box) = human view.
- **C4 `review_server.py` :8322** — LOOK-ONLY review (explicit user
  decision); two strips per box (fit order, CLIP order); FITS / PICK / #n /
  ↻90° / agent-mapped badges. LATENT BUG: `b.conf.toFixed(2)` crashes on
  loop-added boxes with conf null. Companion `asset_viewer.py` :8323 (yaw
  fix toggle, robust-vs-full boxes, census flags).
- **C5 `pick.py`** — admissible = fit score ≤0.8 AND scale within (0.5,1.6)×
  SCENE-MEDIAN implied scale (the scene is internally non-metric — bedroom
  ×0.77–0.83 — so coherence is measured against the scene's own median;
  "paper-worthy" per handoff); winner = argmax `clip` among admissible;
  empty band → top-5 by fit flagged `gate_relaxed`; picks2.json thin record
  + 4 alternates.
- **C6/C7 context:** `place2.py` (tiling realizer `_sub_boxes`) → PH1 donor;
  `collide.py` → PH2 donor; `loop.py apply_add()` = the re-shop template.

## 2. What the handoffs recorded (worked vs failed)

**Worked:** v2 shortlists/picks "much better" than v0 (the one direct user
verdict); category-only gate killed the description-hijack (query "rug" →
"footstool with a red rug on it"); y-up gate; true-size measurement caught
lying annotation bboxes (window shutters 14 vs 54 cm); canonical-yaw fix;
scene-median scale anchor; fit-as-tolerance-band + CLIP inside (only one
gate_relaxed on bedroom_marble); single-box chain re-entry proven end-to-end
(the AC unit add, loop run 2).

**Failed / lessons:** ~34% of shortlisted uids (100/293) authored rotated
about up, clustered ±30° — the annotation's pose_z_rot_angle was RECORDED
but never applied to vertices; a rotated mesh's AABB inflates up to √2/axis,
poisoning fit, perm, scale, and picks (bed footprint 2.64→1.52 m² after
fix). Yaw recoverable only mod 90°; facing unresolved (front=+z convention
UNVERIFIED). Junk geometry inflates AABBs the same way (obj_013
triangle-shelf, 26% of depth; 48/293 census-flagged; fixups user-gated —
books-on-a-shelf would be wrongly pruned). Lexical tiers leak style
("computer monitor" tier-1 admits "computer"). Catalog gaps: NO rug
category → functional stand-ins via the agent map. Detector labels are
noise, detection starved not broken. USER VERDICT on record: "these assets
are kind of shit" — mesh/texture quality is the ceiling; assets_thor +
catalog() = the declared swap point. Cache staleness after geometry fixes
motivated fixup.py. Loop-side: splat-backed judge renders masked missing
objects; judge-camera blind zones auto-rejected adds; sonnet verify missed
3–4k-px changes.

**From the new-graph work (query construction):** names feed retrieval,
disputed nodes get skipped (R13); identity still noisy (obj_030, obj_083 —
shopping must not blindly trust judged names for flagged nodes); crop
choice is now a real decision: tight `graph/crops/` probably right for
CLIP image-image; context `graph/crops_ctx/` (red outline + neighbors) for
VLM eyes, likely POLLUTES CLIP.

## 3. Reuse verdicts (one line each)

KEEP AS-IS: `measure.py` (feed uids from the cast list), `assets_thor.py`,
`thumbs.py` (retarget input; export perm_rotation), `retrieve.catalog()` +
`refresh_sizes()`, `fit()`/`best_fit_config()` verbatim, `pick.py`
structurally (retune: scene median over the cast list; add
`pick_one(node, exclude_uids, complaint)`; store description in the pick
record), `asset_viewer.py`.

KEEP WITH CHANGES: `match_categories()`+agent map (judged name + appearance
as scoring context, category gate unchanged, fix tier typing), `relevance.py`
(query = graph evidence crop; add appearance-string↔thumb text axis; decide
multi-view pooling), `review_server.py` (cast-list input, conf-null fix,
appearance+support+complaint panel), `fixup.py` (repoint cache imports).

DROP: `_mount()`/WALL_LABELS, MIN_CONF, v0 shortlist path, `crops.py`
(keep the max-projected-area idea), `bridge.py`, `loop.py` file (keep
apply_add as the reshop_one template).

## 4. Open questions the S4 design must answer

Contracts: (1) cast-list schema — recommend keeping the shortlist/cast
split so re-shops rewrite a small file and the viewer keeps its data;
(2) additive write-back vs sidecar for scores; (3) re-shop provenance
{shopped_at_iter, superseded_uid, complaint, excluded_uids} + ban policy;
(4) anchors-first — dependents same pass with deferred flag, or second
pass?; (5) does package/ survive; (6) which name field for provisional /
disputed nodes; (7) which crop (tight vs context, which member, pooling).

Catalog: (8) objathor paths + caches resolved via comp_paths.py — new code
must NOT import comp_paths (sys.path cycle); add objathor accessors to
entangled_gen/paths.py; (9) inherit dataset caches (coverage for new judged
names unknown); (10) can pose_z_rot_angle replace geometric yaw measurement
(would kill the double retrieve2)?; (11) record a facing hint (front=+z
UNVERIFIED); (12) coverage audit: 92 judged names vs catalog categories
BEFORE fit math matters; (13) catalog-agnostic now or later ("assets are
the ceiling").

Policy: (14) appearance → third additive score inside the band, never the
gate; (15) where an LLM may act in selection (recommend: replace only,
choosing among already-admissible); (16) re-shop termination: max re-shops
per node + uid ban list (old loop's MAX_ITERS lesson); (17) single-node
re-shop must reuse the FROZEN scene-median scale, never recompute from one
node.

## Dependent-placement contract (user ruling 08-01, from the R4 snap review)

Sub-objects (books on shelves etc.) have NO exact position target until
their parent is a real mesh: the box model carries no interior levels.
Standing contract for S4:

- The graph hands over RELATIONSHIPS + verbatim boxes; a dependent's
  observed RELATIVE placement (height fraction of the parent's vertical
  span, lateral offset within the footprint) is the mesh-independent
  evidence — derive it from the boxes at shopping time, no earlier stage
  computes it.
- When a parent is shopped: re-resolve its children against the mesh's
  real interior (shelf boards, drawer cavities), using observed relative
  height as the level selector, in support-chain order (snap's
  supporters-before-dependents rule extended forward).
- Snap-analyzer output classes: anchor corrections = suspect-box
  evidence; dependent corrections = advisory only, never work orders.
