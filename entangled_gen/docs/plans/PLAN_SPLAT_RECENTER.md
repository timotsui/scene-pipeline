# PLAN — splat-base lift + adaptive recenter (pano scrapped as base)

Status: STARTED 2026-07-25 (late session). Governing doc for resume.
Decision (user, 2026-07-25): **the pano is no longer the base.** Reason: the
pano lane measures against the collider mesh (a second artifact with its own
scale — ICP found 0.95008 vs the splat), so every pano-lane box pays a
registration tax (measured: uniform +6.5 cm floor pedestal on recenter C0/C1).
The splat lane is same-artifact end to end (splat renders + splat z-buffer
depth), the property that makes the old yaw4 manifest sit on the floor.
Supersedes the pano-pool parts of SPEC_3H2_FUSE.md (its lift/vote design
still applies; pano crops demoted from pool member to "maybe later").

**What we keep from the pano experiments (method, not data): the recenter
idea + per-axis trust** — proven on the pano lane (floor-object under-reach
+0.55 m → +0.10 m when recenter shots joined the merge). On splat renders it
gains: any render resolution, camera can MOVE (step back / sidestep, not just
re-aim), and no frame tax.

## Inputs (all exist, bedroom_marble)

- splat: out/<scene>/gen_raw.ply (RAW frame; depth + render source)
- first-round views: analyzer/job_high/frames/frame_%04d.png (192, 512x512,
  130 deg fov, 8 standpoints)
- cameras: analyzer/job_high/transforms.json (fl 119.375, cx=cy=256, c2w
  4x4 per frame — CONVENTION UNVERIFIED, hence G1)
- detections+masks: seg_sweep/ (GroundingDINO+SAM, vocab.json, thr .35,
  154/192 frames, from the 07-25 bake-off run)

## Gates (strict order; one assumption per gate; user judges all visuals)

- **G1 — camera convention (mechanical).** New adapter transforms.json ->
  r3-style cam. Candidates: {c2w, w2c} x {OpenCV y-down z-fwd, OpenGL y-up
  z-back}. For each: color z-buffer the splat means through ~8 sample frames,
  correlate vs the real frame png (same trick as lift_views.detect_frame).
  PASS = one candidate dominates every sampled frame. No user judgment
  unless ambiguous.
  - STATUS: **PASSED 2026-07-25** — c2w_opencv: mean corr +0.563 vs +0.223
    (w2c_opencv), +0.033/+0.008 (opengl variants); 7/8 frame wins (frame_0163
    marginally preferred w2c_opengl, +0.348 vs +0.310 — noise, aggregate
    decisive). Winner stored in analyzer/job_high/g1_convention.json.
- **G2 — single-frame sweep lift (visual).** Lift ONE good frame's
  detections via z-buffer mask lift with the adapted cam; project boxes back
  into that frame + 2 neighbors. USER JUDGES overlays.
  - STATUS: artifacts built 2026-07-25 (frame_0066, 16/20 dets lifted;
    overlays seg_sweep/g2_overlay_frame_0065/0066/0067.png) — AWAITING USER
    VERDICT. Numbers-side sanity: shelf 1.88 m tall, office chair 0.83 m,
    "book" boxes are shelf-row shaped (~0.1 x 0.2 x 0.65) — plausible scales,
    small floor gaps. No visual conclusion drawn (user judges).
- **G3 — full sweep lift + per-axis merge (visual via viewer).** All 154
  frames, per-axis trust merge (port from recenter_experiment), manifest ->
  viewer box source "sweep · mask lift" + floor-gap stats. Success: floor-ish
  median ~ 0 (the yaw4 number), coverage >> 19 objects.
  - STATUS: RAN 2026-07-26 (lift_sweep.py --all): 1493 lifted / 154 frames
    (627 = 42% edge-truncated), merged -> **94 objects** (18 weak-bound).
    Floor gap: min +0.006 (**no pano pedestal — same-artifact claim holds**),
    floor-ish median +0.078 (yaw4 ref +0.02; the q75 +0.678 tail = truncated
    bottoms). scene_manifest_sweep.json + seg_sweep/lift_pool.json; viewer
    source "splat · sweep mask-lift (G3)". AWAITING USER VERDICT in viewer.
  - **G3 ADDENDUM — merge-inflation finding (user hypothesis, CONFIRMED
    2026-07-26):** union fusion (min/max of member bounds) is a
    max-statistic — box volume inflates with member count: corr(log n, log
    inflation) = +0.84; 21+ members -> median 4.2x, worst 26x (curtain, 42
    members). THIS — more than image sharpness — is why pano C1 (median 5
    members/object) looked better than the sweep (up to 111). Secondary
    factor, also measured: pano crops detect better (39% of dets >= 0.5 vs
    sweep frames' 23%; 12.8 vs 3.9 px/degree). Fix: group_box(q) soft
    quantile — q=0.05 (5th/95th pct of trusted bounds) chosen over q=0.1
    (which trimmed TRUE floor-contact extremes: floor-ish +0.19). q=0.05:
    104 objects, inflation 21+members 4.2x->2.5x, corr ->+0.70, floor-ish
    median +0.107, floating tail q75 +0.678->+0.391.
    scene_manifest_sweep_robust.json, viewer source "splat · sweep
    robust-merge (q.05)". Union manifest kept for A/B. Applies upstream to
    the 3h2 fuse spec (its vote/fuse should NOT use raw union either).
- **G4 — adaptive recenter on splat renders (visual).** Find truncated
  detections in the G3 pool; for each (deduped): aim a NEW splat render at
  the cut edge (bias aim toward the truncated side), step BACK if fov would
  exceed ~100 deg; re-detect (GPU — pace 2 s/crop per [[laptop-gpu-crash]]);
  lift; per-axis merge round 2. Compare C0-style vs C1-style floor-gap +
  per-label counts.
  - STATUS 2026-07-26: mechanics DONE, merge policy OPEN, wip manifest in
    viewer ("splat · +retakes (G4 wip)").
    - Renderer detour: shot.py/splat-transform FAILED mechanically for
      aimed interior cameras (9/18 blank despite the z-buffer model seeing
      2-12% of points; inconsistent orientation on the rest). Replaced by
      analyzer/render_targets_wsl.py — the analyzer's own gsplat path in
      the WSL splatanalyzer env, cameras as c2w_opencv built from eye/aim.
      mini-G1 per render: 16/18 verified at corr .45-.81 (2 excluded).
    - 18 weak-bound targets, 18 aimed shots (0 needed step-back), detect
      paced 2 s (seg_views.py --pace). 232 lifted from retakes.
    - **KEY FINDING: only 1/18 targets re-found by its own aimed close-up**
      (e.g. the "plant" close-up sees lamp/curtain there). Weak-bound
      groups are mostly detector junk; the retake doubles as a VERIFIER —
      the vote-filter idea arriving from a different door. Recorded per
      target in seg_sweep/rc/targets.json ("confirmed").
    - Admission policies tried: v1 admit-all (94->106 objects, weak 18->83
      — collateral close-up junk); v2 target-label-only (~0 admitted —
      close-ups re-classify); v3 confirm-and-refine (admit only if
      overlapping an existing same-label object): 207 admitted, 92 objects,
      BUT weak 18->69 — close-up GRANULARITY MISMATCH (individual books vs
      the sweep's book-rows) fragments merge groups. OPEN DESIGN QUESTION
      for the fuse: granularity-aware grouping (containment-into-group
      before anchor-splitting?) or restrict retakes to bound-refinement
      only (never new anchors).

## Code homes (scene-pipeline, NOT scratchpad — 07-25 crash zero-filled a
scratchpad experiment script; durable code lives in the repo)

- entangled_gen/analyzer/cams_from_transforms.py — adapter + G1 check
- entangled_gen/lift_sweep.py — G2/G3 lift (evolves into the 3h2 lift_pool)
- G4 script TBD after G3 passes

## Open questions

- vote filter (3h2 spec section 7) enters at G3 or after G4? Current lean:
  after G4, so the recenter round feeds the same pool before gating.
- pano crops: keep as auxiliary pool views later? (user: scrapped as BASE;
  complementary use undecided)
