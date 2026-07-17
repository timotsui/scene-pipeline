# 2026-07-17B handoff — judge-camera coverage fix DONE, loop run 4, collision viewer layer

Follows SESSION_2026-07-17_HANDOFF.md (same day: package reorg / clean view).
This session closed the loop's "next unblock" from 07-15B.

## 1. Judge-camera coverage fix (the blind-zone unblock) — BUILT + RUN

- **`entangled_gen/render_judge_views.py`** (new): renders 7 splat views per
  scene, all from the SAME standpoint as the old rig (0, 1.6, 0) — 6 yaws at
  60° spacing tilted down ~14° (look height 0.85 m, fov 75) + 1 straight-down
  view (fov 85, up 0,0,-1). Tiles the viewing sphere like pano cutouts: no
  wedge gaps, floor visible from 0 m (down view covers 0–1.5 m, ring beyond
  ~1.3 m). No raised/off-center camera needed → no splat-degradation risk.
  Writes `views/judge_*.webp` + shot.py-format sidecars. `gpu_yaw*` files
  untouched (detection provenance). Run for bedroom_marble.
- **Wiring**: `place2.judge_sidecars(sc)` (judge_* if present else gpu_yaw*);
  `composite_views(..., sidecars=)`; loop targets/recreations/camera-summary
  use it. Detection, canonical `composed2_view_*`, review tooling stay on
  gpu_yaw*. Smoke-verified: pose math checked numerically (straight-down pose
  valid, floor points at ~1 m project in-frame); judge_down's 0 mesh px is
  genuine (all current objects outside its cone — checked per object).
- **`plan_view.webp`** (user asked): camera 4.6 m above room center, ceiling
  removed via `--near 2.2`. Named plan_view NOT judge_* so the loop ignores
  it. `views/plan_view.webp`.

## 2. Loop run 4 (iters 6–9, 9 VLM calls) — blind-zone failure mode GONE

Every edit rendered visible pixels; verify reasons now cite specific views.
- ACCEPTED (1): "basket with plant" on left shelf @(-2,2.25,-0.25). State +
  canonical renders + glb + clean views updated.
- Rejected on merit: poster NEUTRAL, ceiling light NEUTRAL (bad asset — two
  stacked shapes), wall art WORSE, curtain collision 0.303, pet bowl
  collision 0.080, plant WORSE (VLM placed it outside its own target view).
- Iter 9 proposed nothing → clean self-stop.
- **Bottleneck moved cameras → judgment quality**: NEUTRAL verdicts on
  arguable improvements = the known "verify misses small/ambiguous changes"
  issue. Next quality lever: crop-zoom into verify prompt or stronger judge.

## 3. Loop report page (user: "difficult to see what is what")

**`composition/loop_report.py`** (new) → `package/loop/report.html`: every
attempted edit in journal order, color-coded verdict + reason, ORIGINAL/
BEFORE/AFTER strips auto-picked by pixel diff (only views where the edit
changed pixels, top 3). Old blind-zone edits show as "no view shows a pixel
change" rows — the historical problem is visible in-page. Regen after each
run: `python loop_report.py --scene <sc>`. NOT yet auto-run by loop.py.

## 4. Collision visibility (user: "collision is the most implicit problem")

- **`collide.py --export`** → `package/collisions.json`: pairs + labels +
  RENDER-frame AABBs of the SHARED voxels (report(boxes=True)).
- **Viewer layer**: serve.py `/collisions.json` + index.html "collisions"
  checkbox — bright red filled boxes + wide labels for pairs > 0.05, dim red
  outlines for tolerated contacts. Draws the interpenetration REGION, not
  the objects. Verified end-to-end via curl.
- Current table (13 pairs): lamp×window **0.205** (PRE-EXISTING, worst in
  scene) and window×AC 0.093 are the only two over threshold. Flagged to
  user: the base scene's own boxes sin worse than the loop's AC add —
  relevant to their pending AC verdict and to whether 0.05 is right.
- NOT auto-refreshed by the loop (offered, not yet requested).

## 5. Viewer launchers (repo root, double-click)

`launch_viewer.bat` (3D placement viewer :8321), `launch_pick_review.bat`
(:8322), `launch_asset_viewer.bat` (:8323), `stop_viewers.bat` (kills
listeners on those ports — for orphans only; closing a launcher window
stops its server). Default scene = a `set SCENE=` line in each.

## User rules established this session (also in memory)

- **Plain-language rule**: define every project shorthand on first use per
  conversation; no undefined codenames ("C7 loop" complaint).
- Side observation flagged to user: door meshes float mid-wall (e.g.
  obj_016 spans y 1.34–1.78) — C6 placement/asset defect, untouched.

## Open / next

- User verdicts pending: basket add (new), door yaw, AC add (0.093 vs the
  pre-existing 0.205 lamp), Marble bare-walls, judge-view quality (they saw
  the 7 splat views + smoke overlays; no verdict recorded).
- Verify-quality lever (crop-zoom or stronger judge) is now the loop's
  binding constraint.
- Optional wiring: loop.py auto-runs loop_report.py + collide.py --export
  at end of run.
- Parked (unchanged): our-init + GLTS-loop ablation; facing rule (C6);
  detection-side coverage gap (would need re-detection on new views).
