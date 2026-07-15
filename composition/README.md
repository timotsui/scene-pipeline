# composition — recreate a lifted scene from library assets

Stages communicate ONLY through files in `out/<scene>/package/` (same rule as
`entangled_gen/PIPELINE.md`): swapping a stage = writing the same files in the
same format; nothing downstream cares which implementation produced them.

## Recreate path (current, reworked 2026-07-14 — "pick object after layout")

The lifted `scene_manifest.json` IS the layout. Each stage is judged
PER-OBJECT at its checkpoint before the next stage runs.

| # | stage | module | reads | writes (THE CONTRACT) |
|---|-------|--------|-------|------------------------|
| C1 | shortlist | `retrieve2.py` | `scene_manifest.json` + objathor `annotations.json.gz` | `package/shortlists2.json` |
| C2 | thumbnails | `thumbs.py` | shortlists2.json + objathor meshes | `<objathor>/_thumbs/<uid>.png` (dataset-level cache) |
| C3 | relevance | `relevance.py` (CLIP ViT-B/16 via transformers, GPU) | shortlists2.json + clean crops + thumbs | additive `clip` field per candidate in `shortlists2.json` + `_thumbs/_clip_vitb16.npz` embedding cache |
| C4 | inspect | `review_server.py` (localhost:8322) | shortlists2.json + `views/` + thumbs | `package/review_crops/<obj>{,_clean}.png` (viewer is LOOK-ONLY; two strips per box: dimension-fit order and CLIP-relevance order; glowing frame = native size fits inside the box) |
| C5 | pick | `pick.py` — dimension gate (fit cap + scale band around the scene-median scale), argmax `clip` inside it | shortlists2.json | `package/picks2.json` |
| C6 | place (base) | `place2.py` — perm rotation + uniform fit scale + tiling; facing (0/180) unresolved | picks2.json + shortlists2.json + manifest | `package/composed_state2.json` + `composed2_view_*.png` + `composed_scene2.glb` |
| C7 | refine/loop | later this week (facing, occlusion, render-variant judging of alternates) | composed_state2.json + composites | TBD |

Run C1: `python retrieve2.py --scene <sc>` (`--no-agent` offline,
`--compare` prints v0's pick, `--top N` table depth).
Run C2: `python thumbs.py --scene <sc>` (only cache misses render).
Run C3: `python relevance.py --scene <sc>` (embeds only cache misses).
Run C4: `python review_server.py --scene <sc> --port 8322` (`--recrop` redoes
crops). **C4 is the user checkpoint for judging the stages**, not for driving
them: two candidate strips per box (dimension-fit order, CLIP-relevance
order), glowing frame marks native-size-fits-inside; selection is C5's job.

### The two ranking axes (user priorities, in order)

1. **Dimension** — candidates gated by CATEGORY ONLY (tiers: exact string >
   token subset > any token overlap; descriptions never vote — this killed the
   v0 rug→"footstool with a red rug on it" hijack). Ranking = orientation-aware
   fit over all 6 axis-aligned orientations (`perm[i]` = asset axis on world
   axis i, y = up): the two y-up perms are free, re-upping perms pay
   `UPRIGHT_PENALTY` — they exist to catch mis-authored meshes (rugs standing
   on their side). Optimal uniform scale factored out; the residual is aspect
   mismatch and `|log scale|` is penalized (`LAMBDA_SCALE`) so assets keep a
   coherent scene scale. Tiling k=1..3 along the long horizontal axis
   (`TILE_PENALTY` per extra copy). Labels with no lexical category match go
   through ONE batch agent call (functional stand-ins allowed, e.g.
   rug→doormat; objathor has NO rug/carpet category). Perms are realized as
   PROPER rotations (`thumbs.perm_rotation`, sign absorbs parity) for both
   thumbnails and placement.
2. **Style/relevance** — scored at C3, never in C1: CLIP ViT-B/16
   image-image similarity between the object's clean view crop
   (`review_crops/<id>_clean.png`, no drawn box lines) and each candidate's
   ORIENTATION-CORRECTED thumbnail. Additive `clip` field; it re-orders,
   never filters. A second additive field `clip_txt` ("category. description"
   vs the crop) is a cross-check only: low `clip` + high `clip_txt` = suspect
   thumbnail (orientation/render), not a wrong asset.

### C5 pick policy

Fit is a TOLERANCE BAND, never an argmax: admissible = fit `score <= 0.8` AND
rescale within ×0.5..×1.6 of the SCENE-MEDIAN implied scale (the lifted world
is uniformly off real scale — bedroom_marble runs ×0.83 — so coherence is
measured against its own median, not ×1.0). Winner = argmax `clip` among
admissible; empty band → top-5 by fit, flagged `gate_relaxed` (on
bedroom_marble only obj_016, a sliver lift-artifact box, relaxes). Top-3
alternates are kept in picks2.json for a render-variants/VLM judgment at
placement time.

### File contracts

`shortlists2.json`: `{scene, boxes:[{id,label,conf,center,size,aabb_min,
aabb_max,views,mount,match_tier,categories,candidates:[{uid,category,
description,size_cm,score,k,axis,yaw_fit,scale,aspect_resid,log_scale},...]}]}`
— candidates sorted best-fit first (viewer shows rank `fit #N`); score is
internal (lower = better). All manifest coords RAW frame, meters. `size_cm`
= the asset's THOR-mesh bbox extents in cm, `[x, y, z]` with **y = up** (the
y-up gate in `retrieve.catalog()`): the annotation's own `size` field is
z-up-ordered for ~72% of the catalog and inconsistent for the rest (measured
2026-07-14 vs the mesh bboxes), so it is never used for fitting.

`picks2.json` (C5): `{<obj_id>: {uid, category, k, axis, perm, scale, fit,
clip, clip_txt, n_admissible, gate_relaxed, alternates:[{uid, fit, clip}]}}`
— `uid: null` = no candidates at all (leave the splat as-is for that box).
This is C6's input: `k`/`axis` say how many copies tile which axis, `perm`
the fit's orientation (realize via `thumbs.perm_rotation`), `scale` the
uniform rescale hint, `alternates` the runners-up for render-variant
judging.

## Augment path (v0, kept as-is — later enrichment pass)

LLM proposes NEW boxes into free space, then retrieve-and-place:
`propose.py` → `package/compose_proposal.json` → `retrieve.py` (v0
token-overlap scoring) → `composed_assets.json` → `place.py` → `jiggle.py`.
Orchestrator: `python compose_scene.py --scene <sc> --mode recreate|augment
--until propose|retrieve|place|loop`. (`recreate.py` is the v0 one-shot
recreate that C1–C4 replace; kept for `--compare`.)

## Shared infrastructure

- `bridge.py` — Claude agent surrogate for all LLM/VLM calls (claude.exe -p,
  subscription; strip the stale User-level ANTHROPIC_API_KEY from the env).
- `assets_thor.py` — objathor pkl.gz → textured y-up trimesh.
- `comp_paths.py` — objathor locations + entangled_gen `paths.py` interop.
- Frame: all stored coords RAW (up = -y on rot180 scenes); meshes/cameras
  composite in RENDER frame via `frame.raw_to_render` (see PIPELINE.md).

## Known limits (attack later, in order)

- extraction: only the 4-view gpu manifest (19 objects on bedroom_marble);
  the pano lift has 98 — switch source manifest once re-verified post
  mirror-fix.
- placement: no per-pixel occlusion vs the splat, uniform height-only
  scaling, no orientation canonicalization (`pose_z_rot_angle` unused).
- retrieval: category tiers are lexical (CLIP/visual scoring is a swap
  point); "computer monitor" tier-1 leaks dimension-right but style-wrong
  "computer" assets.
