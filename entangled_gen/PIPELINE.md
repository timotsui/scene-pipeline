# entangled_gen — stage contracts

The pipeline is a chain of stages that communicate ONLY through files in the
per-scene data folder `OUT/<scene>/` (data root comes from `local_paths.json`,
see `paths.py`). No stage imports another stage's internals. Therefore:
**swapping a method for any stage = writing the same output files in the same
format.** Nothing downstream knows or cares which implementation produced them.

**CONTRACT CHANGES 2026-08-12/13 (R-S2-159..167b, details in docs/REVIEW_LOG.md):**
- NEW TOOL `scene_yaw.py` (pre-runner, like `scene_scale.py`): measures the
  room's continuous yaw (room_shell.measure_plan_yaw, spikiness voting) and
  de-tilts the WHOLE scene state once (splat xyz + gaussian quats, collider,
  manifests, boot extents RECOMPUTED from the rotated cloud). Guard:
  `frame_bootstrap.yaw_applied`; re-runs verify (~0). Backups `*_preyaw.*`.
  Two-pass protocol: apply → chain re-run from stitch.
- `room_shell.py` solid rule: DENSITY GATE (Otsu split of tall-cell log
  density, applied only when modes ≥4x apart) + WALK-THROUGH SLAB (material
  must span waist 0.9 → crown 1.9, standard-room fractions). Trace de-rotation
  is SHEET-ONLY; state-writing runs record `plan_yaw_deg` in the polygon
  block instead. ⚠ shells produced before 08-13 predate these rules.
- `slicevote.py` wall handling is non-convex-safe: capture needs REACH (box
  interval within WALL_TOUCH of the plane) + majority-REST on the segment's
  same-plane family span; `shell_clip` = AABB of (footprint ∩ interior
  polygon), Sutherland-Hodgman; fully-outside boxes are left alone.
- `compose/shopping.py`: flat floor-coverings (FLAT_AXIS_M) are see-through
  for the anchor/sub tier — beds on rugs stay anchors.
- `compose/propose_edits.py`: ADD CHANNEL DEAD by user ruling (`--keep-adds`
  revives); swap-ins landing outside the polygon: near → snap flush to the
  closest wall's EXTERIOR face, truly far (> own body length) → dropped,
  swap infeasible.
- `compose/fit_preview.py`: pillow-evidence facing is a REQUIREMENT — the
  90/270 yaws get the fit canon's 15% (FACE_EVIDENCE_TOL) when the strict 5%
  gate blocks them. Front = yaw @ perm @ +z (NO pca term — crooked-file
  fronts cancel; R-S2-166b).
- `compose/fit_declip.py`: meshes ENTIRELY beyond a wall are never dragged
  inside — near-outside snaps flush to the wall's EXTERIOR face (quantized
  DOWN, never across the plane), truly far left where measured.

**CONTRACT CHANGES 2026-08-10 (R-S2-66..71, details in docs/REVIEW_LOG.md):**
- `pano_recenter.py` SP4 children now carry `members_inline` evidence
  (view + 2D rect + scene-relative image path); `build_graph.py` cuts their
  crops like any member's. A node with zero crops = counted loud warning.
- `graph/crops/` and `graph/crops_ctx/` are WIPED AND REBUILT every run
  (skip-existing served dead objects' pictures across scene re-runs).
  `build_graph.py --recrop` is gone.
- The vote records a blocked re-box measurement as a ballot candidate
  (`rebox_rejected_smaller.proposed_box` / `rebox_truncated.measured_candidate`
  in `graph/vote_doubts.json`); J8 can ship it (`rebox_candidate`). The gate
  escalates, never decides.
- materialize rule 5 (J9): SAME_PRODUCT is pairwise EDGES; the product size is
  written INTO each member's box in its own orientation, support-face
  anchored. No `canonical_size` node field. Edges re-derive after the resize.
- `sub_object`-flagged nodes skip J9's pools (recorded in
  `same_product.json.excluded_sub_objects`); they still face J1/J8.

## Stages and their file contracts

| # | stage | current method | reads | writes (THE CONTRACT) |
|---|-------|----------------|-------|----------------------|
| 1 | generate | Marble (harvest bundle = pano + splat + collider + prompt; downloader in week8/marble-harvest). Candidate local backends live under `gen/<method>/` (hunyuanworld, matrix3d, spag4d, worldmirror — see `docs/GEN_BACKEND_EVAL_PLAN.md`) | prompt | `gen_raw.ply` (3DGS ply, 62-float layout) + `bundle_path.txt` (→ bundle with `prompt.txt`) + optional `generator_pano.jpg`, `pano_frames/` |
| 1.5 | intake (fresh scenes, 2026-08-06) | `frame_bootstrap.py` — TRUSTED-BUNDLE contract: spz==collider frame; splat-transform spz→ply = rot180-about-x ALWAYS, so pipeline frame = rot180x(bundle). Zero estimation; one loud self-check (rotated collider bounds ⊂ splat bounds ±0.5 m) that REFUSES on contract-violating bundles (old vintages → `collider_register.py` search instead) | `bundle_path.txt` (→ spz + collider); converts `gen_raw.ply` if missing | `collider_registered.glb` + `collider_registration.json` (T = diag(1,−1,−1)) + `frame_bootstrap.json` (`floor_y`/`ceiling_y` from rotated-collider bounds, `up`, `pano_to_raw_signs` — the pano funnel's frame source on scenes without the legacy sweep manifest) |
| 2 | render | `rendertools/shot.py` (splat-transform GPU) | `gen_raw.ply` | `views/gpu_yaw{000,090,180,270}.webp` + same-stem `.json` sidecars (`cam`,`look`,`up`,`fov`,`near`,`res`) |
| 3 | segment | `seg_views.py` (GroundingDINO + SAM) | the webps | `seg/detections.json` (`{view: [{label,score,box},...]}`) + `seg/<view>_masks.npy` (bool `(n,H,W)`, SAME ORDER as detections) |
| 4 | lift | `lift_views.py` (point z-buffer depth + unproject + merge) | masks + sidecars + ply | `scene_manifest.json` (see frame contract below) + `seg/manifest_overlay_*.png` + `seg/manifest_plan_*.png` |
| 5 | envelope | `envelope.py` (occupancy voxels → floor/clearance) | ply + manifest | `envelope.npz` + `envelope_heatmap.png` + `viewer/data/<scene>_clearance.json` |
| 6 | package | `agent_package.py` | manifest + overlays | `package/GUIDE.md` + copied views/overlays + manifest |
| 7 | compose/verify | `../composition/` (stages C1–C5, see its README for the sub-stage contracts) + `render_proposal.py`, `splat_place.py`, viewer | package + envelope | `package/shortlists2.json`, `picks2.json`, `composed_*`; augment path: `compose_proposal.json` + `proposal_*` renders |

Orchestration: `scene_ready.py` runs the missing CPU stages (4→6) per scene by
file mtimes. GPU stages (1–3) are launched explicitly (see `gen/*/` runners for
the historical batch pattern).

Stage 4.5 (optional, applied on bedroom_marble 2026-07-15): `amodal_apply.py
--scene <sc> --method splat` rewrites `scene_manifest.json` with one amodal
method's boxes — snapshotting the modal manifest to `scene_manifest_modal.json`
first, `--revert` to undo. Downstream needs no change (file contract), but IS
stale after it: box size drives fit scores, so the composition chain must
re-run from C1.

Side experiments (not in the chain): `collider_register.py` →
`collider_registration.json` (bundle collider → RAW 4×4 + `collider_registered.glb`
for the viewer's `collider` layer; see below), `amodal_boxes.py` +
`amodal_compare.py` → `amodal_boxes.json` + `amodal_comparison/` (occluded-box
extension, method comparison).

## The cut lane — object removal from the splat (side lane, 2026-07-21)

Removes a chosen object's Gaussians from `gen_raw.ply` (GaussianCut graph
cut, seeded by per-view masks), leaving a background splat with the object
cleanly gone — the fix for the entanglement/ghost problem that the
tinted-floor clean view only works around. `background.ply` keeps
`gen_raw.ply`'s exact 62-float layout and Gaussian order, so it drops into
every existing renderer/viewer unchanged. Inputs are per (scene, object id);
a re-cut writes a NEW variant folder (`obj_004_v2`), never overwriting an
earlier attempt.

| # | stage | current method | reads | writes (THE CONTRACT) |
|---|-------|----------------|-------|----------------------|
| c1 | view-pack | `cut/prep_views.py` | `gen_raw.ply` + view sidecars | `cut/dataset/` (15×900² PNGs + COLMAP `sparse/0` + `sidecars/*.json` + `verification.json` with per-view object UVs) |
| c2 | mask-pack | `cut/make_masks.py` (SAM box-prompt; SAM2 propagation pass) | the object's manifest box + `cut/dataset/` | `cut/dataset/multiview_masks/<view>.png` (L-mode, {0,255}, stems match the dataset images) |
| c3 | graph-cut | `cut/run_cut.py` (GaussianCut, WSL `gaussiancut` env) | ply + dataset + masks | `cut/<obj>[_vN]/foreground.ply` (the object's Gaussians) + `background.ply` (scene minus object) + `stats.json` (counts, threshold/weight choice, purity + spatial checks) |
| c4 | review | `cut/render_cut_review.py` | cut outputs + dataset sidecars | `cut/<obj>[_vN]/renders/` (before/after/fg + crops) + `cut_review.html` (Checkpoint 6 page) |

**Background resolver (consumer contract, integration directive
2026-07-21):** downstream composition renders choose their backdrop through
`../composition/place2.resolve_background(scene, mode)`:

- `auto` (default): use the scene's newest `cut/*/background.ply` (newest by
  mtime — a re-cut variant is always newer than its base, so `obj_004_v2`
  supersedes `obj_004`; cuts are single-object for now, so newest = the most
  complete cut available) composited behind the meshes; when the scene has NO
  cut background, fall back to the EXISTING tinted-floor clean path
  unchanged — un-cut scenes/objects never break.
- `cut` / `tinted` / `original`: force one source for testing (`cut` errors
  when no cut background exists; `original` = the ghost-visible splat).
- CLI: `python place2.py --scene <sc> --background auto|cut|tinted|original`
  → `package/composed2b_view_*.png`; all pre-existing place2 invocations
  (default, `--clean`) are untouched. In cut mode the per-camera backdrop
  reuses the review's `renders/after_<view>.png` when the resolution matches,
  else renders `background.ply` via splat-transform into
  `cut/bg_renders/<variant>/` (a cache — the cut outputs themselves stay
  read-only).

Docs: `cut/FEASIBILITY_GAUSSIANCUT.md` (formats + loader constraints),
`cut/ENV.md` (WSL env build), `docs/PLAN_GAUSSIAN_CUT_AND_SPLAT_ANALYZER.md`
(plan + progress log). Demo artifact: `../composition/integration_demo.py`
(moved there 2026-07-23 — it composes, so it lives with composition; the cut
lane's outputs reach it as files) → `OUT/<scene>/cut/integration_demo/
integration_demo.html` (same composition over original / cut / tinted
backgrounds, side by side).

## The pano path — week8 object-ID lane (RETIRED FROM THE RUNNER 2026-08-11)

> ⚠ **STALE AS A PIPELINE CLAIM.** `run_scene.py --phase core` ran this
> lane until 2026-08-11; by the user's ruling that the map is right and
> stale things leave the core pipeline, `core` now runs the CANONICAL
> funnel (`stages.INTAKE`: frame_bootstrap → pano_stitch → crop_pano into
> rig_sp0/crops → vocab_build → pano_bearings → seg_batched → pano_lift →
> pano_recenter → manifest_filter → scene_scale → room_shell). Nothing
> downstream reads this lane's outputs (`pano_crops/`, `seg_pano/`,
> `scene_manifest_pano.json`). The modules stay on disk; the table below
> is kept as their reference. **The authority for what runs is
> `graph/stages.py`** — four tuples, 46 stages, REVIEW_LOG R-S2-93/94.

Same viewpoint as the yaw views, better angular resolution (98 boxes vs 19 on
bedroom_marble), NOT more coverage. Communicates through the per-scene folder:

| # | stage | script | reads | writes (THE CONTRACT) |
|---|-------|--------|-------|----------------------|
| p1 | crop | `crop_pano.py` | bundle equirect pano | `pano_crops/*.webp` + same-stem `.json` sidecars |
| p2 | vocab | `vocab_from_prompt.py` | bundle `prompt.txt` | `seg_pano/vocab.txt` (GroundingDINO prompt: nouns + synonyms; also printed for capture) |
| p3 | segment | `seg_views.py --views-dir pano_crops --out-dir seg_pano --prompt <vocab>` | crops + vocab | `seg_pano/detections.json` + `seg_pano/<crop>_masks.npy` (same formats as stage 3) |
| p4 | gate | `seg_pano_overlay.py` | crops + detections | `seg_pano/pano_overlay.png` + crop montage (user checkpoint) |
| p5 | lift | `lift_pano.py` | crops + seg_pano + collider | `scene_manifest_pano.json` |
| p6 | raw variants | `manifest_pano_to_raw.py` | `scene_manifest_pano.json` | `scene_manifest_panoraw_*.json` (viewer variants via `?man=`) |

Side utility: `tag_crops.py` → `seg_pano/tags.json` (per-crop open-vocab tags).

## The analyzer lane — detection comparison (side lane, 2026-07-21)

Compares our manifest against an EXTERNAL splat_analyzer run (WSL tool; its
`analyzer/<job>/interactions.json` + transforms are produced OUTSIDE this
module and dropped into the scene folder — no in-repo producer).

| # | stage | script | reads | writes (THE CONTRACT) |
|---|-------|--------|-------|----------------------|
| a1 | bridge | `analyzer/bridge_boxes.py` | `analyzer/<job>/interactions.json` + manifest + `envelope.npz` | `analyzer/bridged_boxes.json` (manifest-style boxes, RAW frame) + `analyzer/match_report.json` |
| a2 | compare | `analyzer/build_comparison.py` | bridged + match + interactions | `analyzer/comparison.html` (Checkpoint 4 page); viewer layer via `/analyzer_boxes.json` |

## The graph lane — semantic scene graph (2026-07-22, plan: docs/PLAN_SCENE_GRAPH.md)

Unifies the extractions into one graph. ORDERING: needs a1 (bridged boxes) and
stage 5 (`envelope.npz`) to have run for the scene.

| # | stage | script | reads | writes (THE CONTRACT) |
|---|-------|--------|-------|----------------------|
| g1 | nodes | `graph/build_graph.py` | `analyzer/bridged_boxes.json` + `match_report.json` + manifest + envelope | `scene_graph.json` (nodes) |
| g2 | edges | `graph/build_edges.py` | `scene_graph.json` | `scene_graph.json` (geometric edges filled; self-check exits 1 on violation) |
| g3 | appearance | `graph/describe_nodes.py` (VLM via claude.exe) | scene_graph + analyzer frames | `graph/crops/` + appearance fields in `scene_graph.json` |
| g4 | review | `graph/graph_review.py` | scene_graph (+ match + composed_state2) | `graph_review.html`; viewer layer via `/scene_graph.json` |

**Numbering note:** "Step N" in analyzer/cut/graph docstrings refers to the
checkpoint list of the governing plan doc (`docs/PLAN_GAUSSIAN_CUT_AND_SPLAT_
ANALYZER.md` for analyzer+cut, `docs/PLAN_SCENE_GRAPH.md` for graph). The stage
ids here (1–7, p1–p6, c1–c4, a1–a2, g1–g4) are the pipeline contract numbering;
mapping: a1=Step 6, a2=Step 8, c1=Step 7, c2=Step 9, c3=Step 10, c4=Step 11.

## What the sources can and cannot know (2026-07-15)

**Everything is single-viewpoint.** The 4 `gpu_yaw*` views all sit at the same
camera position (`0,1.6,0`), yawed 90° apart — it is a panorama cut in four,
with ZERO parallax; the pano path is the same viewpoint at better angular
resolution (98 boxes vs 19), NOT more coverage of what hides behind what.

**But truncation is mostly a MASK problem, not an observation problem.** The
splat has 473 occupied 5 cm voxels in the gap under the bed and 197 under the
shelf — that geometry was seen (a 1.6 m camera looks under a bed at a shallow
angle) and is simply not in SAM's mask, and the lift only unprojects mask
pixels. That is exactly why the splat-occupancy method works. Do not repeat the
stronger claim that occluded geometry "was never observed": measure first.

**Coverage hole (unfixed, 2026-07-15):** `fov 75` horizontal × 4 views 90°
apart = 300° of 360°. Four 15° wedges are never rendered at all, so nothing in
them can be detected. Fix = render 6 views at 60° spacing (or widen the fov)
and re-run seg + lift.

**Detection is effectively single-view.** On bedroom_marble GroundingDINO finds
15 objects in `gpu_yaw000` and 2/1/2 in the other three (doors only). 20 raw
detections → 19 manifest objects: exactly ONE cross-view merge, so nearly every
box rests on one view's opinion with no corroboration. Whether the other three
directions are genuinely bare or the generator only elaborated its front is a
USER judgment, not yet made.

**The bundle collider is REDUNDANT, not incapable.** It registers well
(`collider_register.py`: scale 0.9498, t_y −1.23, no rotation; splat→surface
p50 1.4 cm) and it DOES do the job asked of it — run as an amodal method it
extends bed/side table/shelf/desk/planter to the floor, agreeing with splat on
5 of 6 boxes (it misses only the lamp). It contains the furniture too (voxels
inside every detected box; the chair at 0.97 of the splat's count). What it
never does is add anything: under every occluded box it holds LESS than the
splat, and residual-blob clustering (subtract detected boxes + room shell,
connected-component the rest) finds it nothing the splat lacks. It is a mesh
derived FROM the splat. Live value: it is CLEAN (no floaters), so agreement
with splat-occupancy is a precision check that an extension is not a floater
artifact — weak corroboration, since the two are not independent.

For semantics it is out for a different reason: untextured (2D detectors need
appearance) and one fused connected component of 83.7k verts (+2 six-vertex
scraps), no submeshes or names. NB the "collider CC-growth" plan was first
struck for that CC count — FAULTY reasoning: components would be clustered on a
residual occupancy grid, not on mesh topology. It was re-tested properly
(residual blobs) and only then closed.

## The coordinate-frame contract (stage 4 output; user-verified 2026-07-05)

ALL stored coordinates are in the RAW ply frame. Raw is "upside-down": the
upright/render world (what the webps, SuperSplat and the viewer's default
display show) is `raw * frame.raw_to_render` (elementwise sign flip,
self-inverse; rot180-about-Z ⇒ `[-1,-1,1]`). Physical up = `frame.up`
(= `[0,-1,0]` under rot180, so `floor_y > ceiling_y` numerically).

`scene_manifest.json` frame block:
```json
"frame": {"space": "raw", "up": [0,-1,0],
          "floor_y": 1.727, "ceiling_y": -1.599,
          "extent_p1": [...], "extent_p99": [...],
          "raw_to_render": [-1,-1,1], "frame_hypothesis": "rot180",
          "frame_calib_corr": {"identity":..., "mirX":..., "mirY":..., "rot180":...},
          "calib_views": 4}
```
Stage 4 self-calibrates this per scene (`detect_frame`: 4 sign hypotheses
correlated against the actual webps over ALL views) — a new generator with a
different ply convention is handled automatically, but VERIFY a new source once
with the cube method: `debug_cube_ply.py` (color=coordinate debug splat) +
user's eyes in SuperSplat/our viewer, and `debug_frame_hypotheses.py` for the
numeric screen.

## Adding an alternative method for a stage

- **New generator (stage 1):** make `gen/<method>/` with its launch scripts.
  It must deposit `gen_raw.ply` in a new `OUT/<scene>/` folder (plus optional
  pano artifacts). Then run stages 2→6 unchanged. First scene from a new
  source: run the frame verification above.
- **New segmenter (stage 3):** write `detections.json` + `<view>_masks.npy` in
  the exact formats/ordering above; stage 4 consumes them unchanged.
- **New depth/lift (stage 4):** free choice of method, but the output manifest
  MUST carry the frame block and raw-frame coords; overlays are the user's
  verification artifact — always produce them.
- **New renderer (stage 2):** webps + sidecars in the same fields; NB the
  sidecar cams are in the RENDER (upright) frame — that is part of the
  contract, and exactly the subtlety that caused the 2026-07-05 saga.

Keep methods side-by-side (folder per method), never edit a working method in
place to become another.

## N1 · Scene scale — measured normalization (BUILT 2026-08-06, USER PASS)

Marble's export scale varies per world (bedroom ~1.0; living measured
0.699). `scene_scale.py --scene <sc>` runs AFTER manifest_filter, once per
scene: one cached LLM call gives per-class typical size + tight/loose
reliability (never a curated table); s = robust median of observed/typical
over confident tight-class objects; DEGRADES to s=1.0 (loud) when n < 5
or rel-MAD > 0.15.

**Apply = a STATE TRANSFORM, not a re-run (user ruling 08-06).** k = 1/s
multiplies every meter-bearing artifact of the scene state in place, then
the single pass simply continues at the shell:
`gen_raw.ply` (xyz ×k, log-scales +ln k) · `collider_registered.glb` ·
frame block floor/ceiling/extents · ALL pano-track manifests
(`scene_manifest_pano2c*.json`: aabb/center/size/floor fields) ·
`rig_sp0/lift_pool<sfx>.json` · `pano_selfrender_meta.json` eye.
Pixels (pano/crops/masks/shots) and words (vocab) carry no meters and are
untouched — P1–P5 are NEVER re-run (seg is scale-free; lift/recenter
outputs are linear, multiplying verified boxes is exact; re-detecting
injects variance — the P1-re-entry experiment measured 0.846 wide-spread
on re-detected fragments). Forfeited nicety: the pano eye is no longer an
absolute 1.6 m (standpoint is a parameter).

Originals kept as `*_prescale.*`; second apply REFUSED via
`frame_bootstrap.json: scale_applied`. Contract file: `scene_scale.json`
(evidence table + decision). Queued: measure from `graph[resolved]`
instead of f30 (fragments pollute the median; resolved gave 0.74).

## 2b · Directional prior — term bearings (USER IDEA, PROMOTED 2026-08-06)

`pano_bearings.py --scene <sc>` runs between vocab and detect: ONE VLM call
on `rig_sp0/pano_selfrender.png` locates each canonical term horizontally
(equirect: azimuth = (xfrac − 0.5)·360; the self-render is in the A2 yaw
frame the crops are cut in, so bearings compare to crop yaws with NO
offset — the bundle pano is deliberately not used, its x-origin is
Marble's). Contract file: `rig_sp0/vocab_bearings.json`
(`{bearings_deg: {term: [deg,…]}}` + unlocated list + raw reply).

`seg_batched.py --bearings <file>` then filters each view's query terms:
a term whose canonical has bearings is searched only in views within
±90° of one; UNLOCATED terms stay in every view (the prior narrows only
on positive location evidence — VLM misses degrade to the old global
behavior, never to blindness). Synonyms follow their canonical term.

A/B verified on living (pano2d vs pano2c, user-confirmed): kills
wrong-side phantoms (weak mislabels merging into fake objects) and
sharpens survivors (shorter per-view prompts score higher, the 07-26
batching effect). KNOWN LIMIT: direction cannot separate two candidates
along the same ray — same-bearing depth phantoms remain the judges' job.

## Scene-graph stages — record, then judge (formalized 2026-07-26)

All graph stages read and write ONE file, `OUT/<scene>/scene_graph.json`
(two canonical files would drift). Layering rule: the RECORD layer (nodes,
evidence, geometric edges, open questions) is deterministic and NEVER
edited after it is built; every judge writes VERDICTS as additive fields,
and `graph["judged"]` is a derived view reproducible at any time from
record + cached verdicts. All judge prompts are FIXED VERSIONED TEMPLATES
filled by deterministic code (`PROMPT_VERSION` is salted into each cache
hash, so template edits automatically re-judge). Bridge: claude.exe
subscription (API-key env vars stripped). Degradation: LLM unavailable ⇒
names stay provisional, pairs/floaters stay unresolved, nothing gets
disputed — never a guess. Gates seen in the docs were DEV-TIME scaffolding
only; production runs this chain unattended.

| # | stage | script | reads | writes (THE CONTRACT) |
|---|-------|--------|-------|----------------------|
| G1 | record — nodes | `graph/build_graph.py` | f30 manifest + room_shell + rig crops + prompt.txt | `scene_graph.json` nodes (f30 VERBATIM, no pre-merges, full label multisets, evidence pointers) + `graph/crops/`. W5 (08-10): a shell carrying the `polygon` block yields one arch wall node per SEGMENT (`arch_wall_00..NN`, cardinal planes + connectors, `source: "envelope"`); no block ⇒ v1 4-wall nodes unchanged. `room_shell.py` default mode now runs the polygon fit itself (degrades to v1 + `polygon_error` on fit failure — never a silent skip) |
| G2 | record — edges | `graph/build_edges.py` | scene_graph.json nodes | edges: ON·IN·IN_WALL·ATTACHED·INTERPENETRATES + SAME_CANDIDATE queue + NEAR fallbacks (no-floater invariant, truncation facts) + per-node `nesting` facts (containment ≥ 0.90 pairs recorded on the smaller node — the box-inside-box trail the IoU floor excludes; added 08-01); self-check exits 1 on frame/invariant violation. W5 (08-10): wall claims via `wall_claim_dist` — a segment only claims a box whose footprint overlaps its extent (+0.10 slack); connectors claim by signed distance to their line; v1 room-spanning walls behave as before |
| J0 | pair triage — text-only docket (08-01) | `graph/triage_pairs.py` | record `nesting` facts (containment ≥ .90 pairs the IoU floor excludes) | NOMINATE/SKIP per pair, one batched text call (asymmetric: nominate on doubt — a wrong skip ships a duplicate); NOMINATEs appended additively as SAME_CANDIDATE edges (`zone: semantic`, `nominated_by: triage`) + `graph/triage_pairs_cache.json`; degrade = no new nominations |
| J1 | pair judge | `graph/judge_pairs.py` | SAME_CANDIDATE edges + crops | `verdict` blocks (SAME / DISTINCT — v2 08-01, PART_OF retired: fragments are SAME, contents DISTINCT) on those edges + `graph/judge_pairs_cache.json` |
| J5 | floater judge | `graph/judge_near.py` | NEAR edges + crops (deterministic menu: code classifies candidates, model reads pixels; `--selftest` = zero-LLM regression) | `verdict` blocks on NEAR edges + `graph/judge_near_cache.json` |
| J2 | merge view (zero LLM) | `graph/build_judged.py` | record + J1/J5 verdicts | `graph["judged"]`: clusters (union-find over SAME), remapped/re-derived edges, naming queue, support conflicts; self-checks (partition, no-floater) |
| J3 | naming judge | `graph/judge_names.py` | judged naming queue + crops | canonical `name` + provenance on judged clusters + `graph/judge_names_cache.json` |
| J4 | coherence judge (text-only; runs ONCE — its flags are a queue, never a re-scan trigger) | `graph/judge_coherence.py` | the judged view (post-merge, post-naming — order matters) | `coherence_flags` (relation / existence / label_geometry) + `existence: "disputed"` on judged clusters + `graph/judge_coherence_cache.json`; `--digest-only` prints the room digest |
| J6 | appearance + J4-flag resolution — the single TERMINAL judge pass | `graph/describe_nodes.py` (absorbing judge_cases.py's queue machinery — PLAN_SCENE_GRAPH.md §0a.8) | judged clusters + crops + J4's flag queues | `appearance` blocks + existence/rename/edge adjudications + caches. Runs ONCE; what it doesn't settle SHIPS. v2 evidence pack (07-26, PROMPT_VERSION 2): every existence/rename case gets a zoomed-out red-box CONTEXT TILE + a truncation fact line, and existence verdicts include `PART_OF_STRUCTURE` → `existence: "structure"` (the obj_138 door-frame lesson: identity is unanswerable at tight-crop zoom) |
| J7 | materialize verdicts — verdicts become the box/edge set | `graph/materialize_verdicts.py` (1 batched cached mapping call) | `graph["judged"]` (existence states + case verdicts) | `graph["resolved"]`: shipping nodes (judged geometry VERBATIM) minus rejected/structure/disputed (removals listed with provenance); REINTERPRET sentences → closed edge vocab ON/IN/ATTACHED/NEAR/NONE; REJECT + endpoint-removed edges dropped (recorded) + `graph/resolve_cache.json`. NO box surgery (stage contract, user 07-26); the shrink experiment is retired behind `--shrink` as placement-stage donor code |

Downstream contract (user ruling 2026-07-26): **`graph["resolved"]` is
the CANONICAL handoff** — the scene-graph stage stops there. The record
and pre-edit judged views are archived IN PLACE in the same file as
immutable audit layers (delete `graph["resolved"]` and J7 reproduces it
from judged + cache). Box GEOMETRY is verbatim from the judged layer:
all box surgery belongs to the next stage, which receives the
suspect-box work orders (obj_014 curtain / obj_109 chair / obj_023
shelf on bedroom_marble) and the open deep-box flags inside the layer's
provenance. There is NO iteration loop at the graph stage — J1–J5
fixed, J4 once, J6 once, J7 deterministic+cached, ship.

## ⭐ THE LAYER CHAIN — every stage is an EDIT on the scene graph (2026-08-09)

USER DESIGN RULE: "each module is an edit on the scene graph, and it has
to inherit all the properties and information. only modify, add, edit,
delete etc. but overall structure should be the same!" And: "we need to
always have a single source of truth for the state of the scene, which
should have the latest and greatest."

    record -> judged -> resolved -> voted -> settled -> grouped

Each layer is a WHOLE graph — nodes AND edges, plus everything the layer
before it carried — named for what its stage did. Living state
(living_marble): record 71/175 · judged 51/110 · resolved 46/92 ·
voted 46/82 · settled 45/77 · grouped 45/77 (nodes/edges), 0 dangling
edges, 0 edgeless nodes, 0 conflicts.

### `graph/scene_state.py` — THE single source of truth

- the CHAIN is declared once, here. Readers call `scene_state.nodes(g)` /
  `.edges(g)` / `.current(g)` and NEVER name a layer. Adding a stage =
  adding its name to CHAIN; every consumer follows.
- two answers that must AGREE: the chain ORDER, and the POINTER the
  writing stage stamps into `graph["layer"]["canonical"]`. `check()`
  reports a disagreement rather than preferring one — a mismatch means a
  stage wrote a layer and did not declare it.
- a layer is eligible to be current only when WHOLE (it has nodes), so a
  half-layer can never become the state of the scene.

### `graph/edge_carry.py` — the edges follow the nodes (one definition)

- RE-DERIVE the geometry on the layer's own boxes. Every edge type is a
  claim about boxes, and a moved box forms edges with nodes it never
  touched, so re-checking former neighbours is not enough. 45 nodes =
  990 pairs ≈ 5 ms, no model calls.
- INHERIT what geometry cannot regenerate: judge fields (status /
  verdict / nominated_by / triage, J6's edge re-examination) AND edges a
  judge CREATED — J0 nominates pairs below the geometric SAME_CANDIDATE
  gate and adds its own `zone: semantic` edge, found by `nominated_by`,
  not by type.
- RECORD what cannot land: `judge_fields_unplaced`,
  `judged_edges_consumed_by_a_merge`, `judged_edges_lost_to_node_removal`.

### `graph/build_voted.py --scene <s> [--apply]` -> graph["voted"]

- reads: graph["resolved"], scene_manifest_slicevote_preview.json (the
  elected boxes), pool_retake/slicevote_report.json (the vote record),
  graph/vote_doubts.json, graph["judged"] + appearance_cache_v2.json.
- writes: a WHOLE layer. Each node keeps everything `resolved` had, plus
  `geometry` = the ELECTED box, `geometry_superseded` = a HISTORY of the
  boxes it has lost (oldest first, each labelled with the stage), `vote`
  = the whole vote record (status, tiers, slice note, votes cast/needed,
  plan fill, every candidate box, the top-view choice trail), `doubts`,
  `appearance` (J6's description) and `provenance`.
- a node the vote never reached keeps its box and is listed `not_voted` —
  never passed off as elected.

### `graph/materialize_layers.py --scene <s> [--settle-only] [--apply]`

- `--settle-only` -> graph["settled"]: J8 box rulings, J8s split pieces,
  J1 SAME merges, applied to `voted` copied forward whole.
- without it -> graph["grouped"]: the same, plus J9's same-product
  annotations (product_group + canonical_size; NO box is resized).
- a REPLACED box is pushed onto `geometry_superseded` — nothing is
  overwritten without a record.
- a NEW node (split piece) inherits everything its parent held, with the
  inherited `vote` stamped `measured_on=<parent>` and the inherited
  `appearance` stamped `describes=<parent>`, so neither is ever read as
  the piece's own measurement.

### Order matters: J9 judges the SETTLED layer

    build_voted --apply
    materialize_layers --settle-only --apply     (geometry + node set)
    judge_same_product                            (J9 reads graph["settled"])
    materialize_layers --apply                    (folds J9 in -> grouped)

J9 used to read the raw vote manifest while running AFTER J8/J8s/J1, so
it judged superseded geometry — 3 of 11 set members were stale, including
a size-to-buy copied from a node J1 had deleted. Judging the settled
layer removed the CAUSE of materialize's conflicts rather than recording
the symptom: conflicts went 2 -> 0.

## VOTE-BOX stage · slicevote.py (the elected boxes; layer written by build_voted.py)

Position: between graph["resolved"] and S1. Its boxes become
graph["voted"] (see THE LAYER CHAIN above) — the manifest is the stage's
raw output, the LAYER is what everything downstream reads. IN THE RUNNER
SINCE 2026-08-11: it is the first row of graph/stages.py, so
`run_scene.py` runs it like any other stage. ⚠ pipeline_map.html still
draws it as a dashed node and has NOT been updated — the map is the
user's authority and is theirs to change. Design lineage:
docs/SLICEVOTE.md; evidence trail: docs/REVIEW_LOG.md R-S2-26, R-S2-84.

- `slicevote.py --scene <s> [--only ids] [--gate 3]`
  - reads: scene_graph.json (resolved), cached pool top/ctop renders,
    rig_sp0 masks + lift pool, gen_raw.ply, room_shell.json
  - method: top-box vertical prism slice (height-band footprint, margins
    capped min(30%, 0.35 m); fallback original-box wedge) -> the slice
    rendered ALONE (subset .ply, WSL renderer, 4 near-cardinals) ->
    6-voter election (cardinals + top mask + original member-mask union
    as ONE voter) at gate 3 -> anchored cluster -> per-node arm
    assignment (own-mask survivors; <50%-volume flag)
  - writes: scene_manifest_slicevote_preview.json (status
    UNTESTED-PREVIEW), pool_retake/slicevote_report.json,
    pool_retake/conemap.json (+ cone_map.html, the viewer's TEMPORARY
    cone-map layer)
- `graph/record_vote_doubts.py --scene <s>` — typed open questions
  (pano_vs_cluster / culled_clusters / slice_fallback) ->
  graph/vote_doubts.json (SIDECAR; record-proper integration via the
  describe pass rides the gated map promotion)
- `graph/judge_same_product.py --scene <s> [--dry-run]` — OWN judge-chain
  pass (user ruling: NOT inside the multiplicity judge): same-name
  proximity groups + geometric shared anchor -> one LLM verdict per
  group (same product? ONE canonical size?) -> graph/same_product.json.
  VERDICTS NEVER RUN; shopping consumer NOT wired.
  (compose/uniform_instances.py = superseded first draft.)

Canon gates, in order: user pass on R-S2-26 -> bedroom regression
(standing set + no-growth) -> living-46 blind -> runner wiring + solid
map node. Nothing committed as of 2026-08-06 late.


## NODE VIEWS — aimed renders that follow the box (CANON 2026-08-09, R-S2-57)

`graph/node_views.py` + `graph/view_cams.py` (camera math lifted verbatim
from experiments/pool_retake.py — the vote_cams precedent: one copy of a
camera definition). USER RULING: "this is canon. we use this one."

- reads: scene_graph.json (CURRENT layer via scene_state — never a named
  layer), room_shell.json, rig_sp0/pano_selfrender_meta.json (eye0),
  pool_retake/ *.png + pool_targets.json (the reuse candidates and the
  cameras that took them), gen_raw.ply (emptiness probe, opacity >= 0.3)
- decides per node, from its CURRENT box:
  1. the camera set — 4 near-cardinals, near-top, 2 near-perps, clip-top
     fallback; general cull (inside the shell + 0.3 m, emptiness probe);
     every culled view records the WALL that killed it. A split piece
     needs no special path — a box that never existed has nothing to keep.
  2. per standable view: `reuse_prior` / `to_be_reshot` / `to_be_shot`.
- THE REUSE RULE: reuse an existing pool shot when it still frames
  TODAY'S box through its own recorded camera — in-frame >= INSIDE_FRAC
  (0.95) AND zoom >= 1/ZOOM_FACTOR (1.5) of what a RETAKE would deliver.
  The bar is the retake, not an ideal (the obj_008 ruling: a clamped
  camera can never fill the frame with a 16 cm object, and the retake
  would stand in the same clamped spot). No box-agreement term — 3D IoU
  was tried and REJECTED (2 cm on a 16 cm object destroys IoU with zero
  visible drift). No recorded camera -> retake. Geometry-only: the rule
  cannot see occlusion (on record; a third condition, not a re-tune).
- writes: graph/node_views/<node>_<view>.png (+ _box.png overlay drawn
  with the shared vote_cams projection; `#` in a split-piece id becomes
  `_p` in filenames), per-view .params.json fingerprint sidecars
  (eye/aim/fov/res/clip/ply/box — mismatch DELETES the png so the WSL
  renderer must redraw; its skip-if-exists is the 08-06 stale-faces
  failure mode), graph/node_views.json (every decision + its reasons),
  graph/node_views/index.html (the decision sheet, reshoots outlined).
- run: decide-only by DEFAULT (no GPU); `--render` = one WSL gsplat
  batch; `--include-culled` / `--culled-only` = audit renders of the
  cameras the cull rejected. HOUSE RULE: nothing renders without an
  explicit user go.
- consumers: NOT WIRED — which views each judge is shown is a separate
  packaging decision, deliberately not made here. graph/crops/ untouched
  (a crop is a detection record; a render must never overwrite one).
- living state 08-09: 220 standable = 165 reused + 55 fresh (86 s wall,
  0 blank, overlays on all 55); 114 culled, 110/114 agreeing with
  pool_retake's own cull. Evidence sheets: graph/reuse_decision/ (both
  boxes drawn through the shot's own camera; retakes outlined red),
  graph/views_as_j8_left_them/ (the untouched baseline).
