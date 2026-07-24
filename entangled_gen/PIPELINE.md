# entangled_gen — stage contracts

The pipeline is a chain of stages that communicate ONLY through files in the
per-scene data folder `OUT/<scene>/` (data root comes from `local_paths.json`,
see `paths.py`). No stage imports another stage's internals. Therefore:
**swapping a method for any stage = writing the same output files in the same
format.** Nothing downstream knows or cares which implementation produced them.

## Stages and their file contracts

| # | stage | current method | reads | writes (THE CONTRACT) |
|---|-------|----------------|-------|----------------------|
| 1 | generate | Marble (harvest bundle = pano + splat + collider + prompt; downloader in week8/marble-harvest). Candidate local backends live under `gen/<method>/` (hunyuanworld, matrix3d, spag4d, worldmirror — see `docs/GEN_BACKEND_EVAL_PLAN.md`) | prompt | `gen_raw.ply` (3DGS ply, 62-float layout) + `bundle_path.txt` (→ bundle with `prompt.txt`) + optional `generator_pano.jpg`, `pano_frames/` |
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

## The pano path — week8 object-ID lane (alternative stages 2–4)

Same viewpoint as the yaw views, better angular resolution (98 boxes vs 19 on
bedroom_marble), NOT more coverage. Orchestrated end-to-end by `run_scene.py`
(reads `bundle_path.txt`); communicates through the same per-scene folder:

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
