# entangled_gen — stage contracts

The pipeline is a chain of stages that communicate ONLY through files in the
per-scene data folder `OUT/<scene>/` (data root comes from `local_paths.json`,
see `paths.py`). No stage imports another stage's internals. Therefore:
**swapping a method for any stage = writing the same output files in the same
format.** Nothing downstream knows or cares which implementation produced them.

## Stages and their file contracts

| # | stage | current method | reads | writes (THE CONTRACT) |
|---|-------|----------------|-------|----------------------|
| 1 | generate | SceneDreamer360 (PanFusion pano → per-crop ZoeDepth → 3DGS); runners in `gen/scenedreamer360/` | prompt | `gen_raw.ply` (3DGS ply, 62-float layout) + optional `generator_pano.jpg`, `pano_frames/` |
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
