# 2026-07-15 handoff — collider closed out, amodal applied, base scene recomposed

READ THIS FIRST (supersedes the collider claims in SESSION_2026-07-14B).

## Where this session ended

The base scene is RECOMPOSED from amodal-extended boxes on yaw-fixed assets
(6/19 boxes extended, chain re-run C1→C6, 25 instances from 19 picks).
**Renders + viewer handed to the user; verdict NOT yet given.** Facing is still
unresolved, so the orientation gap the user flagged on 07-14 persists —
this run changed box extents and scale, not orientation.

NEXT: the C7 loop, starting with the facing rule. It is gated on ONE unverified
assumption — `front = +z` in the objathor canonical frame (composition/README
known-limits). Verify that first (contact sheet: N unambiguous assets rendered
from a camera on +z looking −z, yaw fix on, no perm — if the convention holds
every asset faces the camera; user judges). Only then implement: perm fixes
which asset axis lands on which world axis, so facing is just the 0/180 sign —
pick the sign maximizing the dot with the direction toward the room interior;
`mount: wall` points away from its wall.

## Built this session (all in entangled_gen/)

- `collider_register.py` (NEW) → `collider_registration.json` + `collider_registered.glb`.
  48 signed axis perms scored on VOXEL OCCUPANCY (not bbox IoU) → ICP, scale free.
  bedroom_marble: identity rotation, scale 0.9498, t_y −1.23, voxel IoU 0.683,
  splat→surface p50 1.4 cm. `load_T(sc)` is the accessor.
- `amodal_apply.py` (NEW, stage 4.5) → rewrites `scene_manifest.json` from one
  amodal method; snapshots `scene_manifest_modal.json`; `--revert` undoes.
  APPLIED: `--method splat`, 6/19 boxes extended.
- `amodal_boxes.py` — `load_collider_pts` now READS the registration and never
  searches (the old best-of-8-sign-flips is deleted); output carries
  `collider_registration` instead of `collider_flip`/`collider_iou`.
- `viewer/` — new `collider` layer (`/collider.glb`, `showColl`); the glb is
  baked in the RAW frame so it takes NO r2r flip, unlike composed/GLTS.

## Findings (the point of the session)

**Collider: REDUNDANT, not incapable — closed as a source.** It registers well
and it DOES extend occluded boxes (agrees with splat on 5/6: bed, side table,
shelf, desk, planter → floor; misses the lamp). It has the furniture (voxels in
every detected box; chair at 0.97 of the splat's count). It just never ADDS:
less than the splat under every occluded box, and residual-blob clustering
(subtract detected boxes + room shell → connected components) finds it nothing
the splat lacks. It is a mesh derived FROM the splat. Untextured + one fused CC
⇒ no semantic use either. Residual value: it is CLEAN, so agreement with
splat-occupancy is a floater-artifact check (weak — not independent).

**Truncation is mostly a MASK problem, not an observation problem.** The splat
has 473 occupied 5 cm voxels under the bed, 197 under the shelf. That geometry
WAS seen; it is just not in SAM's mask, and the lift only unprojects mask
pixels. This is why splat-occupancy works. Earlier claims that occluded
geometry "was never observed" are wrong — measure before repeating them.

**Detection is starved, not broken** (see the `detection-coverage-gap` memory):
`fov 75` × 4 views = 300° of 360°, so four 15° wedges are NEVER RENDERED;
15/20 detections are in `gpu_yaw000` (the other three see doors only); 20 raw
detections → 19 objects = exactly ONE cross-view merge. GroundingDINO itself is
fine (chair 0.88, bed 0.80).

## Open user judgments (nobody has made these)

1. The recomposed base renders (`package/composed2_view_*.png`, viewer :8321
   `composed` layer) — the verdict this session was recomposed for.
2. Are `gpu_yaw090/180/270` genuinely bare walls-and-doors, or did Marble only
   elaborate the room in front of its generation viewpoint? Bears on the whole
   recreate premise, not just detection.
3. Whether to spend on the coverage fix: 6 views at 60° spacing (closes the 60°
   hole) + off-center cameras (real parallax; the splat is a 3D asset, we are
   not stuck with Marble's viewpoint) → re-run seg + lift.

## Rerun

- Registration: `python collider_register.py --scene bedroom_marble`
- Amodal: `python amodal_boxes.py --scene <sc>` → `amodal_compare.py` →
  `amodal_apply.py --scene <sc> --method splat` (or `--revert`)
- Chain after any box change (box size drives fit → picks):
  `retrieve2 → measure → retrieve2 → thumbs → relevance → pick → place2`
  (all `--scene bedroom_marble`, from `composition/`, Windows python)
- Viewer: `python entangled_gen/viewer/serve.py --scene bedroom_marble --port 8321`
  (kill by PORT, not by window title: `Get-NetTCPConnection -LocalPort 8321`
  → `Stop-Process` — a stale server silently serves stale code)

## Not committed

`collider_register.py`, `amodal_apply.py` (new) + `amodal_boxes.py`,
`viewer/index.html`, `viewer/serve.py`, `PIPELINE.md`, `composition/README.md`,
`docs/SESSION_2026-07-14B_*` (modified). scene-pipeline commits as
Timotsui / timotsuihc@gmail.com.
