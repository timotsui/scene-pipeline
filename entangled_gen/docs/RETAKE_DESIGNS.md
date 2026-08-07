# Retake designs — the carve lineage (2026-08-06, R-S2-22..25)

The problem all of these attack: splat POROSITY (rays slip through thin
objects onto a depth-continuous background — 41% of the book's mask
pixels measured the floor behind it, max depth jump 6 cm) combined with
a ONE-STANDPOINT rig (every crop resamples one pano, so no cross-view
check can bound the ray axis). Boxes streak along the viewing ray; only
a genuinely different viewpoint can cut them. All designs below are
scene-agnostic, uniform over all resolved nodes (no human-flagged
suspects), and degrade to keep-original + flag. All preview-only until
promotion.

## v1 — the side-view retake (R-S2-22) ⭐ THE PROVEN BASELINE

**USER VERDICT: "the most successful of the three" (08-06); still the
reference the later designs are judged against.**

Mechanics (code: `experiments/parallax_retake.py` at commit f595253 —
the file has since evolved; that commit is the runnable v1):

1. ONE aimed render per object from a FAR standpoint: camera placed
   perpendicular (90°; later 65° — see below) to the original
   eye→object ray, stand-off ~2.2× object size (clamp 1.0–3.5 m),
   shell-clamped, fov fit to the box. WSL gsplat, batch, resumable.
2. mini-G1 corr verification of every retake camera (house rule).
3. GroundingDINO re-detect of the node's name in the render, best
   overlap with the reprojected original box; SAM → mask; z-buffer lift
   → side box.
4. Carve = interval on the ORIGINAL's dominant ray axis (the one axis
   the side view measures laterally = trusts).
5. **Point refilter** (the part every later design kept): the original
   sp0 masks' 3D points, restricted to the established ray interval,
   re-derive the box on ALL axes — the side view says *where along the
   ray* the object is; the original view's own points say everything
   else. Kills the vertical streak too.
6. Other-side fallback on failure; keep + flag when both fail.

Results on living (46 nodes): 27 carved / 19 kept. Desk
[2.53,0.79,2.40]→[1.91,0.75,1.38] (legs+height preserved), plant →
[0.14,0.33,0.17], window depth 2.30→1.85, floor lamp 0.88→0.42.
**Idempotence: known-good boxes moved ±3 cm** — safe to run uniformly.

Limits that drove the later designs: (a) occlusion — the book was
invisible from both far sides (chairs); (b) exact-perpendicular views
see thin objects edge-on (user: "no shape") → 65° near-perpendicular;
(c) corr-gate false alarms on flat/textureless targets (17/46);
(d) side-view choice was blind (no visibility planning).

## v2 — bubble retake (R-S2-23/24)

Aimed CROPS from extra panos rendered inside the empty "bubble" around
the generation standpoint (sp1 +1.1x, sp2 +1.1z; visibility guaranteed
by construction — every object was detected from ~there). Zero
per-object renders. Weak knife: 1.1 m baseline = 20–30° parallax; as a
REPLACEMENT for v1 it lost (user judged the ladder worse); as an extra
constraint SOURCE it earns its keep (solved the book v1 couldn't see).

## v3 — compose (user: "more than 1 extra retake")

Both ±65° far sides ALWAYS run + bubble bands, all constraints in ONE
point refilter. 38/46. Superseded by the pool.

## v4 — pool retake (R-S2-25, current; `experiments/pool_retake.py`)

Candidate pool per object: 4 near-cardinal (10° — cardinals measure the
box's axes head-on; exact cardinals hit axis-aligned thin objects
edge-on), near-top + CLIP-TOP plan view (ceiling clipped from the splat,
camera above the roof, unclamped stand-off — fires when the in-room top
is culled or the object cannot fit the frame; settled the sofa = an
L-SECTIONAL), 2 near-perp (65°). GENERAL cull, no special-cased views:
out-of-shell-bounds or non-empty eye sphere dies (the bottom view dies
naturally). Object-height cameras first, cull arbitrates upward.
Good-lens rule (fov 55, distance derived). Edge-trust: a frame-clipped
detection side contributes nothing ("extends beyond one square").

**Claim model (user): "the projection ray volume votes, not the box"** —
a view's claim is the cone of sight-lines through its SAM mask;
membership = projects-inside-mask; NO side-view lift/depth (side-view
porosity drops out). Coalition carve: most-agreeing pair seeds
("2+ intersecting ⇒ a fragment of the object is there"), concurring
views join, wrong-instance dissenters dropped, strict intersection;
consensus fragments beyond the primary ship as multiplicity evidence.

## OPEN: the k-rule knob (calibrate with the user, then bedroom-verify,
then living BLIND)

Strict coalition-AND: book [0.38,0.06,0.31] (best ever) but overcarves
soft many-view objects (SAM masks are PARTIAL silhouettes; intersecting
7 partials < object: pillow 0.23/0.15/0.17). 2-of-N voting: robust to
outliers but pairwise cone crossings readmit streak segments (book 0.75
deep). Candidates: visibility-normalized supermajority
(claims ÷ eligible viewers per point), agreement-adaptive k, per-class
softness. v1's axis-interval carve is the fallback that never had this
knob — one more reason it stays the documented baseline.

## Standing regression set (living)

obj_004 book (thin, occluded from far sides) · obj_039 desk (big,
floor-standing) · obj_069 plant (soft, repeated class) · obj_011/obj_063
sofa arms (L-sectional, multiplicity) · obj_068 chair (wrong-instance
views) · obj_026 pillow (soft partial silhouettes). Evidence pages:
retake_views.html (per-view renders + detected box/mask).
