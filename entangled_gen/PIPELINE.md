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
| 7 | compose/verify | LLM + `render_proposal.py`, `splat_place.py`, viewer | package + envelope | `package/compose_proposal.json`, `proposal_*` renders, composed plys |

Orchestration: `scene_ready.py` runs the missing CPU stages (4→6) per scene by
file mtimes. GPU stages (1–3) are launched explicitly (see `gen/*/` runners for
the historical batch pattern).

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
