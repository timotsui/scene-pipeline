# SESSION 2026-08-09 HANDOFF — THE CARVE DAY (R-S2-19 verdict → pool retake)

(Real date 2026-08-06 evening; names run ahead. Continues
SESSION_2026-08-08_HANDOFF.md. REVIEW_LOG R-S2-19..R-S2-25 carries the
full evidence trail; commits edaf972..31d4b89, ~15 this session.
PUSH = user's job.)

## THE ARC (one line each)

1. R-S2-19 verdict: scale PASS; user found outrageous boxes → forensics:
   whole-frame "photo" detections + splat-porosity depth streaks + fusion
   amplification. Fixes: whole-frame guard, nearest-cluster depth,
   image-word query screen, wordpiece repair, MAD bound gate (bedroom
   regressions clean).
2. Directional prior (USER idea) A/B-won and PROMOTED: map node 2b
   pano_bearings + seg --bearings per-view term filter.
3. First full judge chain on true meters: 46-node resolved graph; glass
   door renamed by J4; removals with human-grade reasons.
4. Streak class (book/plant/desk protrude through the table): traced to
   POROSITY — 41% of book-mask pixels z-buffer through the thin object
   onto a gapless floor ramp; single-standpoint rig can never bound the
   ray axis (all crops = one pano = one eye).
5. Retake experiments, all preview-only, user-driven design each round:
   v1 far-perpendicular aimed renders → bubble panos (sp1 +1.1x, sp2
   +1.1z; --rig/--eye-offset in stitch/bearings/lift) → v3 compose →
   POOL RETAKE (experiments/pool_retake.py) = the promotion candidate.
6. Pool design (user end to end): 4 near-cardinal (10°) + near-top +
   clip-top plan view (renderer clip_y_gt; camera above clipped ceiling;
   fires when in-room top culled OR object can't fit frame) + 2 near-perp
   (65°); GENERAL cull (in-shell + empty-eye-sphere — bottom view dies
   naturally); object-height cameras first (cull arbitrates upward);
   good-lens rule (fov 55, distance derived); edge-trust (frame-clipped
   side contributes nothing).
7. ⭐ CLAIM MODEL (user): "the projection ray volume votes, not the box" —
   a view's claim = the cone of rays through its SAM mask; membership =
   projects-inside-mask; NO side-view lift/depth at all. Coalition carve:
   most-agreeing pair seeds, concurring views join, dissenters (wrong
   same-class instance) dropped, strict intersection.
8. ⭐ Plan view settled the sofa: L-SECTIONAL (obj_011_ctop_det.png);
   ruling = two honest arm boxes + PART_OF_STRUCTURE via the queued
   multiplicity judge (NO hand-wired edge — Rule #1).

## THE OPEN DECISION (calibrate WITH the user, next session first thing)

**The k-rule knob.** Strict coalition-AND: book [0.38,0.06,0.31] (best),
but overcarves soft many-view objects (pillow 0.23/0.15/0.17, plant
height 0.16) because SAM masks are PARTIAL silhouettes — intersecting 7
partials < object. 2-of-N voting: robust, but pairwise cone crossings
keep streak segments (book 0.75 deep). Candidate synthesis: visibility-
normalized supermajority (claims/eligible-voters per point), or adaptive
k by view-agreement, or per-class softness. DO NOT tune on living's
answer key — design the rule, verify on bedroom, run living blind.

## STATE / FILES

- Viewer :8321: green layer "parallax retake · carved (preview)" =
  latest pool result (46 objects, labels carry per-object status);
  set A/B layers; snap-to-eye buttons sp0/sp1/sp2 (NOTE sp0 stands at
  2.29 true m — pre-norm 1.6 scaled; sp1/sp2 true 1.6).
- Evidence page: out/living_marble/retake_views.html (rebuild via
  scratchpad build_pool_views_page.py — 8 columns, det overlays).
- Reports: pool_retake/pool_report.json (+ parallax_retake/,
  bubble_retake/ from earlier iterations — superseded but kept).
- The smoke set for regression: obj_004 book, obj_039 desk, obj_069
  plant, obj_011/obj_063 sofa arms, obj_068 chair (wrong-instance case),
  obj_026 pillow (soft partial case).

## QUEUE (in order)

1. k-rule calibration (above) → full pool run → user gate.
2. Promotion to map: sp1/sp2 pano stages + repair stage between J7 and
   S1 (pool retake); canonical runner update.
3. Multiplicity judge (wire-ready probe A): PART_OF_STRUCTURE for the
   sofa arms; plan-view tiles (clip-top renders) as stimuli; fragments
   from the carve = its geometric evidence.
4. Shell-clip for openings (glass door 6.04 — the one remaining monster).
5. S1 → support_clip (compose/support_clip.py, preview-tested; ON edges
   must be REBUILT post-carve — streaked geometry poisoned them AND S1's
   witness) → compose chain on honest sizes.
6. Parked: visibility-planner candidate pruning; detection caches for
   determinism; per-view detection instability on repeated classes;
   two-standpoint sensing promotion (record-then-judge ingesting both
   pools as SAME_CANDIDATE).

## GOTCHAS (carried)

GPU clock lock resets on reboot (`nvidia-smi -lgc 0,1500`, admin — this
session used a UAC elevate via Start-Process). Retake render caches are
camera-dependent: ANY camera-geometry edit ⇒ wipe pool_retake/*.png
(same-name reuse is the stale-cache poison). WSL renderer now supports
per-target clip_y_gt. corr gate at 0.12 for defined-convention renders.
