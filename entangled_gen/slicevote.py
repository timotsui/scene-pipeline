"""SLICE-VOTE VOTE — the box-repair stage (USER-DESIGNED 2026-08-06
cone-map session; hardened over 4 whole-scene living runs 08-06/07,
REVIEW_LOG R-S2-26..30, all USER-PASSED).

STATUS: user-passed on living_marble (R-S2-29 + R-S2-30); bedroom
regression WAIVED by user 08-06. NOT yet wired into the canonical
runner — map promotion pending. Output stays a PREVIEW manifest until
wiring. Served in the viewer as the "slicevote" box-source layer.

RENDER PRINCIPLE — GOVERNS EVERY VOTE RENDER (user ruling 2026-08-08):
"the slice is just an INVISIBLE bounding region that tells the camera
roughly where the object is, so we can vote out what is BETWEEN the
camera and the object to get a clear view. Everything else stays
rendered." The slice / slab is a LOCATOR, never the picture: it decides
WHO MAY BE CLAIMED, never WHAT IS DRAWN. A render therefore removes one
thing only — the gaussians inside the view cone that sit in front of the
object — and keeps everything else: the wall the object hangs on or sits
in, an opening's glazing, the neighbours on the same plane, the floor
under it, the room and the landscape behind it. That is what
segmentation needs to recognise anything.
This applies to BOTH render families. The tier-1/2 CARD renders cut at
the object box's nearest corner (t_near). The PERP re-box render cuts at
the NEARER of the box's nearest corner and the object's own PLANE at the
aim point. Both then subtract NEAR_MARGIN. Neither has a "keep only the
slab" term any more (the perp render kept one until 2026-08-08, which is
why the door / ceiling-light tiles were mostly black void).
DELIBERATE EXCEPTION: the TIER 3 isolation retry — and the clean 3/4
page view — really are the slice alone on black. That is the whole point
of that tier: a last-resort look with every distractor removed.

Per resolved graph node:
0. EXEMPTIONS (geometric, never label lists): ceiling-mounted (top
   within 0.35 m of the shell ceiling + bottom in the upper half of
   the room) -> kept_ceiling; WALL PROTRUSION (user ruling 2026-08-07
   late, REPLACING the old flush+thin test) -> kept_wall: the box
   TOUCHES OR CROSSES a shell wall plane (its facing face within
   0.20 m of the plane, or extending past it) AND protrudes into the
   room interior <= WALL_PROTRUDE_MAX = 0.20 m (protrusion for a
   high-side wall = plane - box_lo on that axis, clamped >= 0; low
   side mirrored). Depth BEYOND the plane is deliberately IGNORED —
   openings (glass door, window) carry their mass at or beyond the
   wall and the old thin test dropped them (the R-S2-36-era obj_034
   regression is the motivating case). Census basis for 0.20:
   flat/opening objects protrude 0.00-0.16 m (doors, glass door,
   window, television, curtain, picture); real furniture starts at
   0.26 (plant) then 0.35+ (magazines, bookshelves) — 0.20 sits in
   open water. The rule also deliberately UN-exempts the old test's
   false exempts (plant, shelf magazines — the R-S2-30 "surprise
   wall exemptions" carried open), which are now voted. Recorded
   with protrusion_m + the wall id.
   floor-flush (bottom within 0.20 m of the shell floor + < 0.30 m
   tall) -> kept_floor (user ruling 2026-08-07: rugs/mats are the
   wall-flush disease rotated to the floor — protected structurally,
   no class names). All keep the resolved box — flat objects have no
   side silhouette and their slices degenerate.
0a. PERP CAM RE-BOX (user design 2026-08-07) for the WALL and CEILING
   exempts only: skipping the vote leaves them on the ORIGINAL one-shot
   pano-lift box, which DRIFTS ALONG its own plane (glass door). Their
   two IN-PLANE extents are, however, exactly what ONE face-on view
   shows. So each runs a single view-tunnel render perpendicular to its
   plane (slab = the object's box grown 0.30 m in-plane, spanning the
   plane to its far face plus 0.35 m of room-side context), detects +
   SAMs, claims the slab dots through the mask (>= 200 required), and
   replaces ONLY the in-plane extents with their 1-99 percentile box.
   The normal axis is untouched — depth is the one thing a face-on view
   cannot measure.
   FRAMING IS TAKEN FROM THE PLANE (user ruling 2026-08-08: "the only
   really possible center for something flush on a wall/floor/ceiling
   is ON that plane"). The camera aims at the point whose NORMAL-axis
   coordinate is the PLANE's value and whose two IN-PLANE coordinates
   are the ORIGINAL BOX's in-plane centre (the identity anchor), and
   the frame is sized from the ORIGINAL BOX's in-plane extent x
   PERP_MARGIN. The slab is NOT used for framing — it only supplies the
   dots that get claimed. (A slab-centroid aim + slab-span frame was
   tried 2026-08-07 late and REVERTED 2026-08-08: for a wall OPENING the
   slab spans the box's full depth, which for the glass door is 6.6 m of
   outdoor scenery seen through the glass, so both the centroid and the
   span were dominated by landscape — the camera ended up 6.6 m back,
   outside the room, and the frame clipped the door. Do not re-add it.)
   The perp eye is NOT clamped into the shell: a wide object simply
   cannot be framed from inside its own room, and we are rendering a
   point cloud, so a camera standing "inside" a wall is legal. Only an
   absolute PERP_MAX_DIST cap applies; dist_m is always recorded.
   Guards: an in-plane center jump > 1.0 m or an extent
   change > 3x either way REJECTS the candidate (recorded in
   rule.rebox, original ships). No detection / thin slab / no room for
   the camera all keep the original, always with a recorded reason.
   The too-thin 'kept' rows do NOT get this treatment. One code path,
   parameterized by (axis, plane, side) — ceiling and all four walls.
0b. SHELL ELECTORATE FILTER (user ruling 2026-08-07, the L-notch floor
   finding): a dot lying on a measured shell plane (floor/wall/ceiling
   within SHELL_EPS) is STRUCTURE and cannot be ELECTED as an object
   member — claims are ray volumes with no depth test, so notch/gap
   floor dots collect claims from cameras whose rays end on the object
   behind them. Renders/claims unchanged (caches stay valid); the
   filter zeroes those dots' votes at tally time. HALF-SPACE form
   (2026-08-07 late, obj_014): at-or-behind a shell plane (minus
   SHELL_EPS) is ineligible — the old ±eps band re-admitted
   wall-interior fuzz. Exempt (kept_*) objects never vote, so
   flat-on-shell objects are unaffected.
1. SLICE: PRIMARY = top-box vertical prism — GroundingDINO box on the
   cached WSL top/ctop plan render (prior-location-gated), corners
   cast across the OBJECT's height band, margin min(30%, 0.35 m)/side.
   THE PLAN VIEW IS CHECKED BEFORE IT IS BELIEVED (bug fix 2026-08-08,
   user-diagnosed on obj_020 / obj_068 — see the FRAME_* constants):
   the ORIGINAL box is projected into the candidate plan camera first,
   and if the frame CUTS it, or it fills more than FRAME_MAX_FILL of
   an axis, that camera cannot frame the object. The fix is a camera
   along the SAME view direction with the SAME aim and the SAME fov,
   pulled back until the box fits FRAME_TARGET_FILL of both axes, and
   re-rendered as <id>_topfit.png (params-sidecar gated like every
   other render; content = a copy of what the plan render it replaces
   draws, ceiling-clipped exactly as 'ctop' when the eye ends up above
   the ceiling); detection then runs on THAT image. AFTER detecting, a
   box within TOP_EDGE_PX of an image border is CUT BY THE FRAME on
   that side, not by the object — and the answer to that is the SAME
   as the answer to a prior that does not fit (user ruling 2026-08-08):
   TAKE ANOTHER SHOT, PULLED BACK, AND LOOK AGAIN. Up to
   TOP_FIT_RETRIES re-shoots along the same view direction / aim / fov,
   each standing off far enough that the DETECTION's screen extent
   would land near FRAME_TARGET_FILL, rendered as <id>_topfitN.png and
   re-detected under the same prior gate; the ladder stops at the first
   detection clear of every border. ONLY when the object is still cut
   off after the ladder does the footprint fall back to keeping the
   projected ORIGINAL box's extent on the truncated sides (rays through
   off-image pixels are still valid rays), and a detection still
   touching all four borders is discarded outright. Every shot lands in
   the rule record as top_shots, alongside top_frame /
   top_det_truncated.
   WHICH DETECTION IS BELIEVED IS NO LONGER A CONFIDENCE CONTEST (user
   ruling 2026-08-08, measured on obj_020 — the full table lives with
   the DET_* constants). The detector returns several boxes; gdino_best
   admits them exactly as before (no full-frame box; in-prior/det >=
   DET_PRIOR_MIN) and then ranks the admitted ones by HOW WELL EACH
   MATCHES WHERE THE OBJECT SHOULD BE — untruncated candidates first,
   then the harmonic mean (F1) of in-prior/det and covers-prior, with
   the detector score only breaking near-ties. On obj_020 that swaps a
   neighbouring chair covering 13.9 % of the prior for the right chair
   at 98 % containment, and the re-shoot that used to be needed to
   recover from the wrong pick is no longer spent. NO EXTRA MODEL
   CALLS. The top view records the whole shortlist and the reason in
   rule.top_choice, with rule.top_choice_overruled_score true whenever
   the pick was not the highest-scoring admitted box.
   FALLBACK (no top detection) = original-box wedge, capped margin.
   Slices are NOT clamped to the shell — renders and ballot keep full
   context (a shell clamp was tried and reverted 2026-08-07); wall
   dots are stopped from being ELECTED by the half-space electorate
   filter at tally time.
2. RENDER + DETECT, escalation ladder (user design 08-07):
   TIER 1  4 near-cardinal VIEW-TUNNEL cards at object height, cut by
           the RENDER PRINCIPLE above: t_near = the smallest depth
           along the view direction over the OBJECT BOX's 8 corners,
           and every gaussian inside the view cone nearer than
           t_near - NEAR_MARGIN is dropped. Nothing else is touched.
           (The old rule culled up to the SLICE's FAR depth minus the
           slice members, which deleted the walls beside and behind
           the object and coupled the pictures to the slice geometry;
           card renders have been DECOUPLED from the slice since
           2026-08-08.) Re-detect stays gated to the slice's screen box;
   TIER 2  if >=3 of 4 cards unproductive (<50 claimed dots): add 4
           EYE-HEIGHT cardinal tunnel cards as extra voters (Marble is
           biased toward eye-height capture — proven on obj_004 book:
           0/4 at object height, 4/4 at eye height);
   TIER 3  election still empty: isolation retry (slice alone on
           black) with the cards re-detected;
   TIER 4  original box ships, status 'kept' (recorded, never silent).
3. VOTE: cards + TOP view's mask + ORIGINAL standpoint (pano-mask
   union = ONE voter); dot kept at >=3 votes (gate degrades only when
   fewer voters exist); anchored cluster wins, culled ones recorded.
4. PANO-MASK FILTER (user option-2, formerly "arm assignment"). PANO
   MASKS = the node's founding masks from the original pano-funnel
   views (rig_sp0 crops) — the graph's identity evidence, as opposed
   to the vote's fresh identity-blind card detections. Each node
   keeps the vote survivors ITS OWN pano masks vouch for (L-sectional
   split); cluster-box fallback when sp0 coverage is thin;
   <50%-volume flag -> judge.
5. OUTLIER GUARD (user rule): shipping box > OUTLIER_K x original
   volume -> original ships (kept_outlier), vote box recorded as doubt.
6. SHELL CLIP on every SHIPPED box (user ruling 2026-08-07 late,
   "boolean out all the strictly external volume"): at output time
   every box that SHIPS — the kept_* exemption entries AND the final
   voted/outlier box — is intersected with the shell interior
   [XLO..XHI] x [CEIL..FLOOR] x [ZLO..ZHI]. If the intersection
   collapses on an axis (< MIN_SLAB = 0.02 m) a MIN_SLAB-thick slab
   is kept FLUSH against the plane the box sat at/beyond, the other
   two axes keeping their clipped extents — a fully-outside opening
   becomes a thin panel AT its wall. Honesty: when the clip changed
   anything the rule record gains clip = {pre-clip box + per-axis
   deltas}, and boxes.shipping carries the clipped box. The raw
   vote/pano/original boxes stay recorded UNCLIPPED — they are
   evidence, not shipping geometry.

Outputs (per scene): scene_manifest_slicevote_preview.json,
pool_retake/slicevote_report.json (rule.tiers records escalation),
pool_retake/conemap.json (viewer cone-map layer), conemap_obj_*.png,
cone_map.html, pool_retake/rows/<id>[.exempt].html (per-object page
fragments — the sidecars that let a partial run rebuild a COMPLETE page).

PARTIAL RUNS ARE FIRST CLASS (user order 2026-08-08: "restructure so we
can do the partial runs first — debugging is inefficient if we need a
full run every time"). `--only obj_034,obj_006` now REPAIRS the
whole-scene documents instead of replacing them:
  * the startup image wipe is SCOPED to the ids being processed, so no
    other object's cone-map row loses its pictures;
  * slicevote_report.json / scene_manifest_slicevote_preview.json /
    pool_retake/conemap.json are MERGED ON WRITE — the existing document
    is loaded, only the processed ids' entries are replaced, every other
    entry is kept VERBATIM, and objects are emitted in RESOLVED-NODE
    ORDER so the files stay diff-stable. An id on disk that this run did
    not process is never dropped. Absent/corrupt document -> this run's
    entries only, said out loud in the log;
  * cone_map.html is rebuilt COMPLETE from the per-object row sidecars
    (processed ids' fragments are rewritten, everyone else's are read
    back off disk).
PROVENANCE IS THE GUARD THAT MAKES MERGING HONEST. Every entry a run
produces is stamped prov = {run_id, run_at, params_hash, source_sha}
(params_hash = short sha256 of the tunable-constant dict, source_sha =
short sha256 of this file's own source). Each document header carries
run_kind ("full"/"partial"), the run's ids, params_hash, source_sha,
mixed_provenance, provenance_summary {source_sha: [ids]} and
canon_eligible — TRUE ONLY for a full run with no mixed provenance. The
status string stays "UNTESTED-PREVIEW"; a partial or mixed document is
explicitly NOT canon, and cone_map.html prints a mixed-provenance banner
(project convention: stale = BADGED, never hidden).

RENDER STALENESS IS DECIDED BY PARAMETERS, NOT BY FILENAME (user order
2026-08-08 — root cause of the poisoned 08-08 01:00 run). The WSL
renderer skips any png that already exists, so a render whose CAMERA or
CULL changed but whose NAME did not used to be silently reused, and the
stage then detected on the old picture while projecting with the new
camera. Every render this stage requests now carries a sidecar
pool_retake/slices/<render_name>.params.json holding the hash of
everything that determines the image: camera eye / aim / fov, res, the
cull rule string + its margin, and a sha of the exact kept-gaussian set
that was written to the ply. Before a render is requested the sidecar is
compared; on MISMATCH OR MISSING SIDECAR the png is DELETED so the
renderer must regenerate it, and the decision is printed. Card,
eye-height, isolation, clean-3/4 and perp renders are all covered.
THE MANUAL "wipe slices/vote_*.png by hand after a slice-geometry edit"
RULE IS RETIRED — nothing needs wiping by hand any more. The det
overlays are still wiped unconditionally (scoped to this run's ids):
they are drawn by this stage, not by the renderer, so a run whose
detection now fails must not leave last run's overlay behind.

Run:  PYTHONUTF8=1 HF_HUB_OFFLINE=1 python slicevote.py
      --scene living_marble [--only obj_004,...] [--gate 3] [--res 768]
      [--run-id r20260808-0130]
      (PYTHONUTF8 required when stdout is redirected — cp1252 chokes
      on the vote glyphs)
"""
import argparse
import hashlib
import json
import math
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw
from scipy import ndimage
from scipy.spatial import ConvexHull
from matplotlib.path import Path as MplPath

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402
from pano_lift import crop_cam_raw  # noqa: E402
# camera math lives in ONE place (vote_cams.py) so the J8 sheet builder
# can annotate these renders with the very cameras that made them
from vote_cams import (FOV_GOOD, OFF_AXIS, RES, WALL_PAD,  # noqa: E402
                        make_cam, roty, top_cam_for)

ap = argparse.ArgumentParser()
ap.add_argument("--scene", required=True)
ap.add_argument("--only", default="",
                help="comma-separated node ids (default: all resolved). "
                     "A PARTIAL RUN REPAIRS, IT DOES NOT REPLACE: the "
                     "image wipe is scoped to these ids, the report / "
                     "preview manifest / conemap.json are merged on write "
                     "(every unprocessed id kept verbatim, objects emitted "
                     "in resolved-node order) and cone_map.html is rebuilt "
                     "complete from the per-object row sidecars. The "
                     "resulting documents are stamped run_kind=partial and "
                     "canon_eligible=false")
ap.add_argument("--gate", type=int, default=3,
                help="votes required (degrades when fewer voters exist)")
ap.add_argument("--res", type=int, default=RES)
ap.add_argument("--run-id", dest="run_id", default="",
                help="short id stamped on every entry this run produces "
                     "(default: derived from the run start time)")
a = ap.parse_args()

SCENE = a.scene
# ---- RUN IDENTITY (provenance stamps, see the docstring) -------------
RUN_AT = datetime.now().astimezone().isoformat(timespec="seconds")
RUN_ID = a.run_id.strip() or datetime.now().strftime("r%Y%m%d-%H%M%S")
SOURCE_SHA = hashlib.sha256(
    Path(__file__).read_bytes()).hexdigest()[:12]
# ids named on the command line — needed BEFORE the graph is read so the
# startup wipe can be scoped to them (see below)
ONLY_IDS = [s.strip() for s in a.only.split(",") if s.strip()]
RES = a.res        # this run's resolution (default = vote_cams.RES)
DET_THR = 0.20
PAD = 0.30
CAP_M = 0.35
EMPTY_R = 0.30
EMPTY_MAX = 1500
DIL_ISO = 8
OUTLIER_K = 8.0
SHELL_EPS = 0.03   # m — shell electorate filter (user 2026-08-07, in the
                   # approved 2-3 cm band; shell is collider-agreed 5-36mm)
WALL_TOUCH = 0.20  # m — a face this close to a wall plane (or past it)
                   # counts as touching that wall
WALL_PROTRUDE_MAX = 0.20   # m — max intrusion into the room interior for
                   # the wall exemption. Census (living_marble): flat /
                   # opening objects protrude 0.00-0.16 (doors, glass
                   # door, window, television, curtain, picture); real
                   # furniture starts at 0.26 (plant) then 0.35+
                   # (magazines, bookshelves) — 0.20 sits in open water.
MIN_SLAB = 0.02    # m — thinnest slab a shell-clipped shipping box may
                   # collapse to (kept flush against its plane)
NEAR_MARGIN = 0.05  # m — VIEW-TUNNEL cull margin (user ruling
                   # 2026-08-08): a card render drops only what sits in
                   # the view cone NEARER than the object box's nearest
                   # corner minus this margin. Everything at or behind
                   # the object — including the wall beside it and the
                   # room behind it — stays in the picture.
# ---- TOP-VIEW FRAMING (user-diagnosed bug, 2026-08-08) ---------------
# The slice footprint is built from the TOP-VIEW detection box, and that
# box used to be trusted unconditionally. Two ways that lies, both
# measured on living_marble:
#   obj_020 "chair" — detection [515, 2, 768, 344] on a 768 px render:
#     it TOUCHES the top and right borders. The object runs off the
#     frame, the detector boxes only the visible part, and the slice was
#     cut there — after which the elected box can NEVER reach outside
#     that slice.
#   obj_068 "chair" — the ORIGINAL box projects to [0, 0, 768, 768]: it
#     fills the whole frame, so the camera cannot see the object at all.
#     gdino_best's 30 %-of-detection-area prior gate then passes
#     everything, and the accepted detection covered 8 % of the
#     projected prior at score 0.45 — the slice was built around that
#     8 %.
# So the plan camera is now CHECKED BEFORE IT IS BELIEVED (fits the
# whole box, uncut, at a sane size), RE-FRAMED along the same view
# direction when it does not, and the detection's border contact is
# treated as missing evidence rather than as the object's real edge —
# the same doctrine as PERP_EDGE_PX above. The obj_068 half of that
# note is now only half true: the gate really does still pass a box
# covering 8 % of the prior (it is an ADMISSION test, not a ranking),
# but such a box no longer WINS unless nothing better was returned —
# see the DET_* constants below.
FRAME_MAX_FILL = 0.80    # of an image axis — a projected original box
                         # wider than this (or cut by the frame at all)
                         # means the view cannot frame the object
FRAME_TARGET_FILL = 0.60  # of an image axis — what the re-framed camera
                         # pulls back to. fov is left untouched; only
                         # the stand-off along the SAME view direction
                         # changes, so the picture stays the same view
TOP_FIT_MAX_DIST = 40.0  # m — absolute sanity cap on that stand-off (no
                         # shell clamp: this is a point cloud and the
                         # camera may leave the room, exactly as
                         # PERP_MAX_DIST allows for the perp camera)
TOP_EDGE_PX = 4          # px — border-truncation guard band on the top
                         # detection (same value/meaning as
                         # PERP_EDGE_PX, which guards the perp re-box)
# ---- CHOOSING AMONG DETECTIONS (user ruling 2026-08-08) -------------
# CONFIDENCE IS NOT A LOCATION TEST. gdino_best used to keep the
# HIGHEST-SCORING box that cleared the admission gate, and on obj_020
# "chair" (top view, prior [131,101,645,544] in 768x768) the model
# returned all three of these:
#     score  box                    in-prior/det  covers-prior  border
#     0.430  [515,   2, 768, 344]      0.365         0.139       YES
#     0.413  [125, 154, 518, 478]      0.984         0.549       no
#     0.384  [127,   3, 766, 481]      0.640         0.857       YES
# — and picked row 0, the NEIGHBOURING chair, 13.9 % of the prior and
# running off two edges, because it beat the CORRECT chair (row 1, 98 %
# inside the prior, clear of every border) by 0.017 of score. The right
# answer was already in the list; we discarded it.
# So the admitted candidates are now ranked by PRIOR MATCH and
# confidence only breaks ties. The match is SYMMETRIC — the harmonic
# mean (F1) of in-prior/det and covers-prior — so a box that merely
# SWALLOWS the prior cannot win on containment alone, and a box that
# sits inside a corner of it cannot win on coverage alone.
# A pure F1 still prefers row 2 (0.733) over row 1 (0.705), so a second
# rule follows the same evidence doctrine as everywhere else in this
# stage: a box touching a frame border is CUT BY THE FRAME, its extent
# is not a measurement, and it loses to any admitted candidate that is
# clear of every border. Row 1 wins. NO EXTRA MODEL CALLS — this only
# changes which of the detections we already have is kept.
DET_PRIOR_MIN = 0.30     # in-prior/det ADMISSION gate. Unchanged value
                         # and unchanged meaning (it was the literal 0.3
                         # inside gdino_best); it decides WHO MAY BE
                         # CONSIDERED, never who wins. Not a knob to
                         # retune when a pick looks wrong — the ranking
                         # below is what picks.
DET_EDGE_PENALTY = 0.7   # a detection touching a frame border is probably
                         # CUT OFF, so its combined score is discounted (not
                         # vetoed). User ruling 2026-08-08: rank admitted
                         # candidates by score x prior-match x this penalty.
DET_EDGE_PX = 4          # px — border contact band for the ranking's
                         # untruncated preference (same value/meaning as
                         # TOP_EDGE_PX / PERP_EDGE_PX, and deliberately
                         # equal to TOP_EDGE_PX so the re-shoot ladder
                         # and this ranking agree on what "truncated"
                         # means — see the ladder)
# ---- RE-SHOOT A TRUNCATED DETECTION (user ruling 2026-08-08) --------
# The framing check above already knows the honest answer when the
# PRIOR does not fit the frame: take another shot from further back and
# look again. A truncated DETECTION is the same problem seen one step
# later, and it used to get a different, weaker answer — the footprint
# was PATCHED out to the projected prior. A patch is a guess; another
# picture is a measurement. So a truncated detection now re-shoots too,
# and the patch survives only as the last resort after the ladder runs
# out. Same camera doctrine as the re-frame: same view direction, same
# aim, same fov, only the stand-off changes.
TOP_FIT_RETRIES = 2        # extra plan shots allowed per candidate view
                           # when the detection comes out truncated (so
                           # at most 3 detections). The ladder stops at
                           # the first detection clear of every border.
TOP_RESHOOT_SAFETY = 1.10  # small margin on the computed pull-back, so
                           # a re-shoot lands comfortably inside
                           # FRAME_TARGET_FILL rather than exactly on it

sd = paths.scene_dir(SCENE)
rdir = sd / "pool_retake"
rdir.mkdir(exist_ok=True)
sdir = rdir / "slices"
sdir.mkdir(exist_ok=True)
rowdir = rdir / "rows"          # per-object cone_map.html fragments
rowdir.mkdir(exist_ok=True)
# STALE-CACHE POISON (user finding 2026-08-08, obj_034): the WSL
# renderer skips by FILENAME, not by content. THE FIX IS THE PER-RENDER
# PARAMS SIDECAR (see the docstring and render_gate below) — every png
# this stage requests is compared against a hash of its own camera +
# cull + kept-gaussian set and deleted when they disagree. The blanket
# perp wipe that stood here is therefore GONE (2026-08-08): the sidecar
# subsumes it exactly, a second mechanism doing the same job would only
# hide sidecar bugs, and reusing an UNCHANGED perp render is the whole
# point of making partial runs cheap.
#
# What still needs an unconditional wipe: the DET OVERLAYS. They are
# drawn by this stage, not by the renderer, so no sidecar governs them,
# and a run whose detection now fails must not leave the previous run's
# overlay on the page.
#
# SCOPED TO THIS RUN'S IDS (2026-08-08, partial-runs-first): under
# --only, another object's cone-map row still points at its own det
# pictures, and deleting them would leave the rebuilt page full of
# broken images. A full run wipes every id, exactly as before.


def _wipe_ids(ids):
    """Delete the det overlays belonging to `ids` (None = all).
    Id-prefix safe: obj_005 must not take obj_005_c00's pictures with
    it, so the segment between 'vote_<id>_' and '_det.png' must be a
    single view token (card0/eyecard0/iso0/top/perp/slice34 — none of
    them contain an underscore)."""
    n = 0
    if ids is None:
        for f in sdir.glob("vote_*_det.png"):
            f.unlink()
            n += 1
        return n
    for nid in ids:
        pre, suf = f"vote_{nid}_", "_det.png"
        for f in sdir.glob(f"{pre}*{suf}"):
            if "_" in f.name[len(pre):-len(suf)]:
                continue            # belongs to a longer id, not this one
            f.unlink()
            n += 1
    return n


_nwiped = _wipe_ids(ONLY_IDS or None)
_scope = (f"{len(ONLY_IDS)} requested id(s)" if ONLY_IDS
          else "the whole scene")
print(f"[vote] run {RUN_ID} src {SOURCE_SHA} — wiped {_nwiped} stale "
      f"det overlay(s) for {_scope}; render staleness is decided by the "
      f".params.json sidecars", flush=True)


def to_wsl(p):
    p = str(Path(p).resolve())
    return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")


# ---- raw ply rows (subset writing keeps every gaussian attribute) ----
PLY = paths.ply(SCENE)
print("[vote] reading raw ply rows ...", flush=True)
_f = open(PLY, "rb")
_header = [_f.readline(), _f.readline()]
_names, _n = [], None
while True:
    line = _f.readline()
    _header.append(line)
    ls = line.strip()
    if ls.startswith(b"element vertex"):
        _n = int(ls.split()[-1])
    elif ls.startswith(b"property"):
        _names.append(ls.split()[2].decode())
    elif ls == b"end_header":
        break
ROWS = np.fromfile(_f, dtype="<f4",
                   count=_n * len(_names)).reshape(_n, len(_names))
_f.close()
col = {nm: i for i, nm in enumerate(_names)}
alpha_all = 1 / (1 + np.exp(-ROWS[:, col["opacity"]]))
KEEP = alpha_all > 0.3
ROWS_K = ROWS[KEEP]
xyz = ROWS_K[:, [col["x"], col["y"], col["z"]]].astype(np.float32)
print(f"[vote] {len(xyz):,} gaussians after opacity filter", flush=True)


def write_subset_ply(mask, out_path):
    sub = ROWS_K[mask]
    with open(out_path, "wb") as f:
        for line in _header:
            if line.strip().startswith(b"element vertex"):
                f.write(f"element vertex {len(sub)}\n".encode())
            else:
                f.write(line)
        sub.astype("<f4").tofile(f)
    return len(sub)


# ---- RENDER STALENESS BY PARAMS, NOT BY FILENAME (user order
# 2026-08-08) ----------------------------------------------------------
# The WSL renderer skips any png that already exists. So before we ask
# for a render we fingerprint EVERYTHING that determines the image —
# camera (eye / aim / fov), resolution, the cull rule + its margin, and
# the exact kept-gaussian set that will be written to the ply — and
# compare it with the sidecar left by whoever made the png on disk. Hash
# differs, or no sidecar at all: the png is DELETED so the renderer has
# to regenerate it. Never silent: every reuse and every delete prints.
CULL_TUNNEL = "in_cone & depth < t_near(object box) - NEAR_MARGIN"
CULL_SLICE = "slice members only (isolation / clean 3-4 view)"
CULL_PERP = ("in_cone & depth < min(t_near(object box), t_plane(aim)) "
             "- NEAR_MARGIN")
# The re-framed plan view draws exactly what the cached plan render it
# replaces draws — nothing new is culled, the camera only stands further
# back. 'top' is the whole scene; 'ctop' (and any re-frame that ends up
# above the ceiling) is the SAME clip-top the pool render uses.
CULL_TOPFIT = "none — whole scene, as the 'top' plan render"
CULL_TOPFIT_CLIP = "clip_y_gt CEIL+0.08 — as the 'ctop' plan render"


def _keep_sha(keep):
    """Content hash of a kept-gaussian boolean mask (the 'id set')."""
    return hashlib.sha256(
        np.packbits(np.asarray(keep, bool)).tobytes()).hexdigest()[:16]


def render_gate(view, cull_rule, cull_margin, keep):
    """Fingerprint one requested render, drop a stale png, write the
    sidecar. Returns True when the renderer will have to regenerate."""
    name = view["name"]
    payload = {"eye": [round(float(v), 6) for v in view["eye"]],
               "aim": [round(float(v), 6) for v in view["aim"]],
               "fov": round(float(view["fov"]), 6), "res": int(RES),
               "cull": {"rule": cull_rule,
                        "margin": round(float(cull_margin), 6)},
               "keep_sha": _keep_sha(keep)}
    h = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]
    side = sdir / f"{name}.params.json"
    png = sdir / f"{name}.png"
    old = None
    if side.exists():
        try:
            old = json.loads(side.read_text(encoding="utf-8")).get("hash")
        except Exception as e:                               # noqa: BLE001
            print(f"[vote] sidecar {side.name} unreadable ({e}) — "
                  "treating the render as stale", flush=True)
    fresh = (old == h)
    if png.exists() and not fresh:
        png.unlink()
        print(f"[vote] render {name}: params {old or 'MISSING sidecar'} "
              f"-> {h} — png DELETED, will regenerate", flush=True)
    elif png.exists():
        print(f"[vote] render {name}: params match ({h}) — reusing png",
              flush=True)
    side.write_text(json.dumps({"hash": h, **payload}, indent=1),
                    encoding="utf-8")
    return not fresh


g = json.loads((sd / "scene_graph.json").read_text(encoding="utf-8"))
nodes = g["resolved"]["nodes"]
# RESOLVED-NODE ORDER — the canonical emit order for every merged
# document and for the rebuilt cone_map.html (keeps files diff-stable).
ALL_IDS = [n["id"] for n in nodes]
ALL_RANK = {nid: k for k, nid in enumerate(ALL_IDS)}
if ONLY_IDS:
    want = set(ONLY_IDS)
    nodes = [n for n in nodes if n["id"] in want]
    _missing = sorted(want - set(ALL_IDS))
    if _missing:
        print(f"[vote] --only: {_missing} not in the resolved graph "
              "— ignored", flush=True)
PROCESSED_IDS = [n["id"] for n in nodes]
RUN_KIND = "full" if set(PROCESSED_IDS) == set(ALL_IDS) else "partial"
print(f"[vote] run_kind={RUN_KIND} — processing {len(PROCESSED_IDS)} of "
      f"{len(ALL_IDS)} resolved node(s)", flush=True)
eye0 = np.array(json.loads((sd / "rig_sp0" / "pano_selfrender_meta.json")
                           .read_text())["eye_raw"])
sh = json.loads((sd / "room_shell.json").read_text())
CEIL, FLOOR = sh["ceiling_y_raw"], sh["floor_y_raw"]
below_ceil = xyz[:, 1] > (CEIL + 0.08)
_r2r = sh["frame"]["raw_to_render"]
_xs, _zs = [], []
for w in sh["walls"]:
    v = w["plane_upright_m"] * (_r2r[0] if w["axis"] == "x" else _r2r[2])
    (_xs if w["axis"] == "x" else _zs).append(v)
XLO, XHI, ZLO, ZHI = min(_xs), max(_xs), min(_zs), max(_zs)
# the four wall planes as (axis, plane value, side) — side +1 means the
# room interior lies BELOW the plane (a high-side wall), -1 above it
WALLS = [(0, XLO, -1, "XLO"), (0, XHI, +1, "XHI"),
         (2, ZLO, -1, "ZLO"), (2, ZHI, +1, "ZHI")]


def wall_protrusion(lo, hi):
    """WALL PROTRUSION RULE (user ruling 2026-08-07 late, replacing the
    old flush+thin test). A box is wall-exempt when it TOUCHES OR
    CROSSES a shell wall plane (its facing face within WALL_TOUCH of
    the plane, or extending past it) AND protrudes into the room
    interior by at most WALL_PROTRUDE_MAX. Depth beyond the plane is
    deliberately ignored — an opening (glass door, window) keeps its
    mass at or beyond the wall. Returns (wall_id, protrusion_m) for
    the least-protruding qualifying wall, else None."""
    best = None
    for axi, v, side, wid in WALLS:
        if side > 0:                       # interior is at x/z < v
            touches = hi[axi] > v - WALL_TOUCH
            protr = v - lo[axi]
        else:                              # interior is at x/z > v
            touches = lo[axi] < v + WALL_TOUCH
            protr = hi[axi] - v
        protr = max(float(protr), 0.0)
        if touches and protr <= WALL_PROTRUDE_MAX:
            if best is None or protr < best[1]:
                best = (wid, protr)
    return best


def shell_clip(lo, hi):
    """SHELL CLIP (user ruling 2026-08-07 late: "boolean out all the
    strictly external volume"). Intersect a SHIPPING box with the shell
    interior. If an axis collapses below MIN_SLAB, keep a MIN_SLAB slab
    flush against the plane the box sat at/beyond (the other axes keep
    their clipped extents). Returns (lo, hi, clip_record|None)."""
    olo = np.asarray(lo, float)
    ohi = np.asarray(hi, float)
    nlo, nhi = olo.copy(), ohi.copy()
    for axi, (blo, bhi) in enumerate(((XLO, XHI), (CEIL, FLOOR),
                                      (ZLO, ZHI))):
        cl, ch = max(olo[axi], blo), min(ohi[axi], bhi)
        if ch - cl < MIN_SLAB:
            if olo[axi] <= blo and ohi[axi] < bhi:      # at/beyond low
                cl, ch = blo, blo + MIN_SLAB
            elif ohi[axi] >= bhi and olo[axi] > blo:    # at/beyond high
                cl, ch = bhi - MIN_SLAB, bhi
            else:                       # degenerate box in the interior
                c = min(max(0.5 * (olo[axi] + ohi[axi]), blo + MIN_SLAB / 2),
                        bhi - MIN_SLAB / 2)
                cl, ch = c - MIN_SLAB / 2, c + MIN_SLAB / 2
        nlo[axi], nhi[axi] = cl, ch
    d_lo, d_hi = nlo - olo, nhi - ohi
    if not (np.abs(d_lo) > 1e-6).any() and not (np.abs(d_hi) > 1e-6).any():
        return nlo, nhi, None
    rec = {"pre_lo": [round(float(v), 3) for v in olo],
           "pre_hi": [round(float(v), 3) for v in ohi],
           "d_lo": [round(float(v), 3) for v in d_lo],
           "d_hi": [round(float(v), 3) for v in d_hi]}
    return nlo, nhi, rec


def ship_box(lo, hi, rule):
    """Clip a shipping box to the shell and record the clip honestly.
    Returns {"lo": [...], "hi": [...]} (rounded, ready for output)."""
    nlo, nhi, rec = shell_clip(lo, hi)
    if rec is not None:
        rule["clip"] = rec
    return {"lo": [round(float(v), 3) for v in nlo],
            "hi": [round(float(v), 3) for v in nhi]}


def in_bounds(eye):
    return (XLO + WALL_PAD < eye[0] < XHI - WALL_PAD
            and ZLO + WALL_PAD < eye[2] < ZHI - WALL_PAD
            and CEIL + WALL_PAD < eye[1] < FLOOR - WALL_PAD)


def empty_at(eye):
    d = xyz - eye
    return int((np.einsum("ij,ij->i", d, d) < EMPTY_R * EMPTY_R).sum())


# MatCamLite / make_cam / roty / top_cam_for now live in vote_cams.py
# (imported above) — ONE definition, shared with the J8 sheet builder.

import torch  # noqa: E402
dev = "cuda" if torch.cuda.is_available() else "cpu"
from transformers import (AutoProcessor,  # noqa: E402
                          GroundingDinoForObjectDetection,
                          SamModel, SamProcessor)
print("[vote] loading detector ...", flush=True)
gd_proc = AutoProcessor.from_pretrained("IDEA-Research/grounding-dino-base")
gd = GroundingDinoForObjectDetection.from_pretrained(
    "IDEA-Research/grounding-dino-base").to(dev)
gd.eval()
sam = SamModel.from_pretrained("facebook/sam-vit-base").to(dev)
sam_proc = SamProcessor.from_pretrained("facebook/sam-vit-base")

man = json.loads((sd / "scene_manifest_pano2c_rc_f30.json").read_text())
f30_by_id = {o["id"]: o for o in man["objects"]}
pool_j = json.loads((sd / "rig_sp0" / "lift_poolc.json").read_text())["pool"]
dets_all = json.loads((sd / "rig_sp0" / "seg_batched20" /
                       "detections.json").read_text())
_vc, _vm = {}, {}


def pano_mask(m):
    view = m["view"]
    if view not in _vm:
        f = sd / "rig_sp0" / "seg_batched20" / f"{view}_masks.npy"
        _vm[view] = np.load(f) if f.exists() else None
    masks = _vm[view]
    if masks is None:
        return None
    for i, d in enumerate(dets_all.get(view, [])):
        if all(abs(d["box"][k] - m["box"][k]) < 1.0 for k in m["box"]):
            return masks[i] if i < len(masks) else None
    return None


def view_cam0(view):
    if view not in _vc:
        side = json.loads((sd / "rig_sp0" / "crops" / f"{view}.json")
                          .read_text())
        _vc[view] = crop_cam_raw(side, list(eye0))
    return _vc[view]


def gdino_best(img, prompt, prior_box=None):
    """Detect `prompt` and keep the detection that best matches WHERE THE
    OBJECT SHOULD BE — not the most confident one (user ruling
    2026-08-08; the obj_020 table lives with the DET_* constants).

    Rejects, unchanged: a full-frame box (>= 95 % of both axes), and —
    when a prior is given — anything whose in-prior/det containment is
    below DET_PRIOR_MIN. That gate is ADMISSION only.

    Among the admitted, the winner is the highest COMBINED SCORE:
        combo = detector score x prior match x edge penalty
    where prior match is the harmonic mean (F1) of in-prior/det and
    covers-prior (symmetric, so neither swallowing the prior nor hiding
    in a corner of it wins on its own), and the edge penalty is
    DET_EDGE_PENALTY when the box touches a frame border (probably cut
    off) and 1.0 otherwise. A candidate must be BOTH plausible and in
    the right place; nothing is vetoed outright.
    With no prior there is nothing to match against and score is all we
    have, which is the old behaviour.

    Returns None, or (score, box, choice). THE FIRST TWO ELEMENTS ARE
    WHAT THEY ALWAYS WERE, so every call site keeps working; `choice`
    is the decision, written down for whoever wants to record it:
      {"chosen": index into "candidates", "decided_by": str,
       "n_candidates": int, "overruled_score": bool,
       "candidates": [{score, box, containment, coverage, match,
                       touches_edge}, ...]}   # in ranked order
    """
    inputs = gd_proc(images=img, text=prompt + ".",
                     return_tensors="pt").to(dev)
    with torch.no_grad():
        outputs = gd(**inputs)
    det = gd_proc.post_process_grounded_object_detection(
        outputs, inputs["input_ids"], threshold=DET_THR,
        text_threshold=0.25, target_sizes=[img.size[::-1]])[0]
    W, H = img.size
    parea = None
    if prior_box is not None:
        parea = (max(0.0, prior_box[2] - prior_box[0])
                 * max(0.0, prior_box[3] - prior_box[1]))
    cands = []
    for score, box in zip(det["scores"], det["boxes"]):
        b = [float(x) for x in box]
        if (b[2] - b[0]) >= 0.95 * W and (b[3] - b[1]) >= 0.95 * H:
            continue
        contain = cover = match = None
        if prior_box is not None:
            ix0, iy0 = max(b[0], prior_box[0]), max(b[1], prior_box[1])
            ix1, iy1 = min(b[2], prior_box[2]), min(b[3], prior_box[3])
            inter = max(0, ix1 - ix0) * max(0, iy1 - iy0)
            area = (b[2] - b[0]) * (b[3] - b[1]) + 1e-9
            contain = inter / area
            if contain < DET_PRIOR_MIN:       # ADMISSION gate, unchanged
                continue
            cover = inter / max(parea, 1e-9)
            match = (0.0 if (contain + cover) <= 0 else
                     2.0 * contain * cover / (contain + cover))
        edge = bool(b[0] <= DET_EDGE_PX or b[1] <= DET_EDGE_PX
                    or b[2] >= W - 1 - DET_EDGE_PX
                    or b[3] >= H - 1 - DET_EDGE_PX)
        cands.append({"score": round(float(score), 3),
                      "box": [round(v, 1) for v in b],
                      "containment": (None if contain is None
                                      else round(float(contain), 3)),
                      "coverage": (None if cover is None
                                   else round(float(cover), 3)),
                      "match": (None if match is None
                                else round(float(match), 3)),
                      "touches_edge": edge,
                      "_box": b, "_score": float(score),
                      "_match": (0.0 if match is None else float(match)),
                      "_edge": edge})
    if not cands:
        return None
    idx = list(range(len(cands)))
    top_score_i = max(idx, key=lambda i: cands[i]["_score"])
    if prior_box is None:
        for c in cands:
            c["combo"] = c["score"]
            c["_combo"] = c["_score"]
        order = sorted(idx, key=lambda i: -cands[i]["_combo"])
        ci = order[0]
        why = "score only — no prior to match against"
    else:
        # ONE COMBINED SCORE (user ruling 2026-08-08), replacing the
        # untruncated tier + match + score-tiebreak ladder: a candidate
        # must be BOTH plausible (detector score) AND in the right place
        # (prior match); a box running off the frame is probably cut off,
        # so it is DISCOUNTED, not vetoed.
        #   combo = score * match * (DET_EDGE_PENALTY if it touches a border)
        # Verified before landing: on all 22 recorded top-view choices the
        # combo picks exactly what the ladder picked (zero differences),
        # AND it fixes obj_034 glass door, where the ladder went wrong —
        # its candidates are (0.619, match 0.610 -> combo 0.378) and
        # (0.224, match 0.810 -> combo 0.181). Match alone preferred the
        # 0.224 sprawl because the door's prior is the DRIFTED box the
        # re-box exists to correct, so "covers the prior" rewarded filling
        # a box already known to be wrong; multiplying by the detector's
        # own confidence discounts it without any path-specific rule.
        for c in cands:
            v = (c["_score"] * c["_match"]
                 * (DET_EDGE_PENALTY if c["_edge"] else 1.0))
            c["_combo"] = v
            c["combo"] = round(v, 4)
        order = sorted(idx, key=lambda i: -cands[i]["_combo"])
        ci = order[0]
        why = ("only candidate" if len(cands) == 1
               else "best combined score")
    ch = cands[ci]
    choice = {"chosen": order.index(ci), "decided_by": why,
              "n_candidates": len(cands),
              "overruled_score": bool(ci != top_score_i),
              "candidates": [{k: v for k, v in cands[i].items()
                              if not k.startswith("_")} for i in order]}
    return (ch["_score"], ch["_box"], choice)


def sam_mask(img, box, dil):
    sinp = sam_proc(img, input_boxes=[[box]], return_tensors="pt").to(dev)
    with torch.no_grad():
        souts = sam(**sinp, multimask_output=False)
    mask = sam_proc.image_processor.post_process_masks(
        souts.pred_masks.cpu(), sinp["original_sizes"].cpu(),
        sinp["reshaped_input_sizes"].cpu())[0].squeeze(1).numpy()[0] > 0
    return ndimage.binary_dilation(mask, iterations=dil)


def fragments_box(K, prior_lo, prior_hi):
    if len(K) < 50:
        return None, []
    vox = np.floor(K / 0.15).astype(np.int64)
    uniq, inv_idx = np.unique(vox, axis=0, return_inverse=True)
    parent = list(range(len(uniq)))

    def find(i):
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    vset = {tuple(v): i for i, v in enumerate(uniq)}
    for i, v in enumerate(uniq):
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for dz in (-1, 0, 1):
                    j = vset.get((v[0] + dx, v[1] + dy, v[2] + dz))
                    if j is not None and j != i:
                        ri, rj = find(i), find(j)
                        if ri != rj:
                            parent[rj] = ri
    roots = np.array([find(i) for i in range(len(uniq))])
    frag_of_pt = roots[inv_idx]
    frags = []
    for root in np.unique(frag_of_pt):
        m = frag_of_pt == root
        if m.sum() < 50:
            continue
        flo = np.percentile(K[m], 1, axis=0)
        fhi = np.percentile(K[m], 99, axis=0)
        ilo, ihi = np.maximum(flo, prior_lo), np.minimum(fhi, prior_hi)
        ov = (np.prod(np.clip(ihi - ilo, 0, None))
              / max(np.prod(fhi - flo), 1e-9))
        frags.append({"n_pts": int(m.sum()), "overlap_prior": float(ov),
                      "lo": flo, "hi": fhi, "mask": m})
    if not frags:
        return None, []
    frags.sort(key=lambda f: (-round(f["overlap_prior"], 2), -f["n_pts"]))
    return frags[0], frags


import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

VIEW_COLORS = {"card0": "#e41a1c", "card1": "#377eb8",
               "card2": "#4daf4a", "card3": "#984ea3",
               "eyecard0": "#ff9e9e", "eyecard1": "#9ecfff",
               "eyecard2": "#a8e6b0", "eyecard3": "#d9a8e8",
               "iso0": "#b01214", "iso1": "#2a5f8f",
               "iso2": "#3a8a41", "iso3": "#763f80",
               "top": "#ff7f00", "sp0-original": "#888888",
               "slice": "#ffffff"}


def draw_box(ax, lo, hi, ax0, ax1, color, ls, lw, label=None, flip1=False):
    x0, x1 = lo[ax0], hi[ax0]
    y0, y1 = lo[ax1], hi[ax1]
    if flip1:
        y0, y1 = -hi[ax1], -lo[ax1]
    ax.add_patch(Rectangle((x0, y0), x1 - x0, y1 - y0, fill=False,
                           edgecolor=color, linestyle=ls, linewidth=lw,
                           label=label))


# ================= PERP CAM RE-BOX (user design 2026-08-07) ===========
# The exempt objects (kept_wall / kept_ceiling) skip the vote entirely,
# so they still carry the ORIGINAL one-shot pano-lift box — which drifts
# ALONG its own plane (the glass door is the motivating case: the box
# slides sideways along the wall it hangs on). The vote's slice/vote
# machinery cannot help them (a flat object has no side silhouette), but
# ONE FACE-ON view can: seen perpendicular to its plane, the object's
# two IN-PLANE extents are exactly what the image shows. So: render one
# perpendicular view-tunnel card, detect+SAM the object, claim the
# slab's dots through that mask, and replace ONLY the two in-plane
# extents. The normal axis keeps whatever it had (depth is what the
# face-on view cannot see). Scene-agnostic: ceiling and all four walls
# run the SAME code, parameterized by (axis, plane, side).
PERP_GROW = 0.30       # m — in-plane grow of the object box for the slab
PERP_SLAB_PAD = 0.35   # m — room-side depth of context kept in the slab
PERP_MIN_CLAIM = 200   # dots the mask must claim for a re-box to be tried
PERP_MAX_SHIFT = 1.0   # m — in-plane center jump that REJECTS the re-box
PERP_MAX_RATIO = 3.0   # x — in-plane extent change that REJECTS it
PERP_MARGIN = 1.4      # framing margin on the ORIGINAL BOX's in-plane
                       # extent (+40%) — the frame is sized from the box,
                       # never from the slab (user ruling 2026-08-08)
PERP_MAX_DIST = 25.0   # m — absolute cap on the perp stand-off. There is
                       # deliberately NO shell clamp: the eye may stand
                       # outside the room when the object is too wide to
                       # frame from inside it (user ruling 2026-08-08).
PERP_DET_PAD = 40      # px — generous slack on the projected prior box
PERP_EDGE_PX = 4       # px — border-truncation guard band (was a local
                       # inside perp_rebox; module level so it is covered
                       # by PARAMS_HASH like every other tunable)

# ============ PROVENANCE (partial-run guard, 2026-08-08) ==============
# params_hash fingerprints EVERY tunable constant this stage decides
# with. Together with source_sha (this file's own text) it is what makes
# a merged document honest: an entry stamped with a different hash was
# produced by a different stage, and the header says so out loud.
PARAMS = {"SHELL_EPS": SHELL_EPS, "WALL_TOUCH": WALL_TOUCH,
          "WALL_PROTRUDE_MAX": WALL_PROTRUDE_MAX, "MIN_SLAB": MIN_SLAB,
          "OUTLIER_K": OUTLIER_K, "PAD": PAD, "CAP_M": CAP_M,
          "DET_THR": DET_THR, "DIL_ISO": DIL_ISO, "EMPTY_R": EMPTY_R,
          "EMPTY_MAX": EMPTY_MAX, "gate": a.gate, "RES": RES,
          "PERP_GROW": PERP_GROW, "PERP_SLAB_PAD": PERP_SLAB_PAD,
          "PERP_MIN_CLAIM": PERP_MIN_CLAIM,
          "PERP_MAX_SHIFT": PERP_MAX_SHIFT,
          "PERP_MAX_RATIO": PERP_MAX_RATIO, "PERP_MARGIN": PERP_MARGIN,
          "PERP_DET_PAD": PERP_DET_PAD, "PERP_EDGE_PX": PERP_EDGE_PX,
          "PERP_MAX_DIST": PERP_MAX_DIST, "NEAR_MARGIN": NEAR_MARGIN,
          "FRAME_MAX_FILL": FRAME_MAX_FILL,
          "FRAME_TARGET_FILL": FRAME_TARGET_FILL,
          "TOP_FIT_MAX_DIST": TOP_FIT_MAX_DIST,
          "TOP_EDGE_PX": TOP_EDGE_PX,
          "TOP_FIT_RETRIES": TOP_FIT_RETRIES,
          "TOP_RESHOOT_SAFETY": TOP_RESHOOT_SAFETY,
          "DET_PRIOR_MIN": DET_PRIOR_MIN,
          "DET_EDGE_PENALTY": DET_EDGE_PENALTY,
          "DET_EDGE_PX": DET_EDGE_PX}
PARAMS_HASH = hashlib.sha256(
    json.dumps(PARAMS, sort_keys=True).encode()).hexdigest()[:12]
PROV = {"run_id": RUN_ID, "run_at": RUN_AT,
        "params_hash": PARAMS_HASH, "source_sha": SOURCE_SHA}
print(f"[vote] params_hash {PARAMS_HASH}", flush=True)

# NOTE on the camera's up vector: make_cam / the WSL renderer share ONE
# c2w_from_eye_aim with world up [0,-1,0] AND the same degenerate
# fallback (fwd parallel to up -> right = fwd x +x). A wall camera is
# horizontal, so world y is its up; a ceiling camera looks straight up
# the y axis and lands in the fallback, which yields camera-up = +x —
# exactly the horizontal up this design asks for, and identical on both
# sides of the WSL boundary. No camera-math change was needed.


def perp_run_renders(targets_json, ply_path):
    """Standalone one-shot render (the in-loop run_renders is defined
    after the exemption paths have already `continue`d)."""
    _py = "/root/miniconda3/envs/splatanalyzer/bin/python"
    _scr = to_wsl(HERE / 'analyzer' / 'render_targets_wsl.py')
    cmd = ("wsl -d Ubuntu-24.04 -- bash -c \"cd /root/splat_analyzer && "
           f"{_py} '{_scr}' --targets '{to_wsl(targets_json)}' "
           f"--ply '{to_wsl(ply_path)}' --out '{to_wsl(sdir)}' "
           f"--res {RES}\"")
    subprocess.run(cmd, check=True, timeout=1800, shell=True)


def _fig(fname, cap):
    return (f"<figure><img src='pool_retake/slices/{fname}' "
            f"loading='lazy'><figcaption>{cap}</figcaption></figure>")


# ============ TOP-VIEW FRAMING CHECK + RE-FRAME (bug fix 2026-08-08) ==
# See the FRAME_* constants for the two measured failures this exists
# for. Pure camera math + one render; no policy lives here.


def box_screen_ext(cam, cn):
    """RAW (UNCLIPPED) screen extent [u0, v0, u1, v1] of a box's 8
    corners in one camera, or None when any corner is at/behind the
    image plane (a projection that cannot be reasoned about). Unclipped
    on purpose: the whole point is to see how far the object runs OFF
    the frame."""
    u, v, z = cam.project(cn)
    if not np.all(z > 0.2):
        return None
    return [float(u.min()), float(v.min()), float(u.max()), float(v.max())]


def frame_verdict(cam, cn):
    """Can this camera FRAME this box? Returns
    (ext|None, clipped_sides, fill_x|None, fill_y|None, ok)."""
    ext = box_screen_ext(cam, cn)
    if ext is None:
        return None, ["behind_camera"], None, None, False
    sides = []
    if ext[0] < 0:
        sides.append("left")
    if ext[1] < 0:
        sides.append("top")
    if ext[2] > RES:
        sides.append("right")
    if ext[3] > RES:
        sides.append("bottom")
    fx = (ext[2] - ext[0]) / RES
    fy = (ext[3] - ext[1]) / RES
    ok = (not sides and fx <= FRAME_MAX_FILL and fy <= FRAME_MAX_FILL)
    return ext, sides, fx, fy, ok


def pullback_cam(aim, eye, fov, scale):
    """Stand-off SCALED by `scale` along the camera's own view
    direction. Same aim, same fov, same TOP_FIT_MAX_DIST sanity cap as
    reframe_cam — the difference is only what sets the distance:
    reframe_cam fits a 3D BOX (the prior), this one takes a scale
    computed from a 2D DETECTION extent, which no 3D box describes.
    Returns (dist, cam, capped) or None for a degenerate ray."""
    aim = np.asarray(aim, float)
    d = np.asarray(eye, float) - aim
    dist = float(np.linalg.norm(d))
    if dist < 1e-6:
        return None
    u = d / dist
    dist *= float(scale)
    capped = False
    if dist >= TOP_FIT_MAX_DIST:
        dist, capped = TOP_FIT_MAX_DIST, True
    return dist, make_cam(aim + u * dist, list(aim), fov, RES), capped


def reframe_cam(aim, eye, fov, cn):
    """Pull the camera BACK along its own view direction until the box
    projects inside FRAME_TARGET_FILL of both axes. Same eye direction,
    same aim, SAME FOV — only the stand-off changes, so the re-framed
    picture is the same view, just wider. Returns
    (dist, cam, fill_x, fill_y, capped) or None for a degenerate ray."""
    aim = np.asarray(aim, float)
    d = np.asarray(eye, float) - aim
    dist = float(np.linalg.norm(d))
    if dist < 1e-6:
        return None
    u = d / dist
    cam, fx, fy, capped = None, None, None, False
    for _ in range(60):
        cam = make_cam(aim + u * dist, list(aim), fov, RES)
        _ext, _sd, fx, fy, _ok = frame_verdict(cam, cn)
        if capped:
            break
        if _ext is None:                       # corners behind the lens
            grow = 1.5
        else:
            grow = max(fx, fy) / FRAME_TARGET_FILL
            if grow <= 1.0:
                break
            grow = min(max(grow, 1.02), 4.0)
        dist *= grow
        if dist >= TOP_FIT_MAX_DIST:
            dist, capped = TOP_FIT_MAX_DIST, True
    return dist, cam, fx, fy, capped


def top_fit_render(nid, name, vname, eye, aim, fov, clip_ceiling):
    """Render ONE re-framed plan view with the vote's own renderer.
    CONTENT IS A COPY OF THE PLAN RENDER IT REPLACES — nothing new is
    culled: the whole scene for a 'top' view, the ceiling clipped
    exactly as 'ctop' does (clip_y_gt CEIL+0.08) when the camera ends up
    above the ceiling. Params-sidecar gated like every other render, so
    it regenerates when the camera moves and is reused otherwise."""
    view = {"name": vname, "label": f"{nid} {name} plan re-frame",
            "eye": [float(v) for v in eye], "aim": [float(v) for v in aim],
            "fov": float(fov)}
    keep = below_ceil if clip_ceiling else np.ones(len(xyz), bool)
    render_gate(view, CULL_TOPFIT_CLIP if clip_ceiling else CULL_TOPFIT,
                0.0, keep)
    png = sdir / f"{vname}.png"
    if not png.exists():
        cply = sdir / f"votectx_{vname}.ply"
        write_subset_ply(keep, cply)
        tf = sdir / f"votetgt_{vname}.json"
        tf.write_text(json.dumps([view], indent=1))
        perp_run_renders(tf, cply)
        cply.unlink(missing_ok=True)
    return png


def perp_rebox(nid, name, lo0, hi0, axi, plane_val, side, pid):
    """One face-on view -> new IN-PLANE extents for a vote-exempt
    object. `axi` is the plane's NORMAL axis, `plane_val` the plane's
    coordinate, `side` the WALLS-table sign (+1 = room interior lies
    BELOW the plane), `pid` its id. Returns
    (ship_lo|None, ship_hi|None, rec, strip_html) — None means KEEP the
    original box; `rec` always says why (never silent)."""
    ip = [k for k in range(3) if k != axi]
    inward = -side                      # into the room, along the normal
    rec = {"view": "perp", "plane": pid, "normal_axis": axi}

    # ---- SLAB: the object's own depth band, hugging its plane, plus
    # PERP_SLAB_PAD of room-side context; grown PERP_GROW in-plane.
    # Design decision: the band spans from the PLANE to the box's own
    # far face (whichever is further out) rather than starting at the
    # plane — an opening (glass door, window) carries its mass AT or
    # BEYOND the wall, and a plane-anchored band would exclude exactly
    # the dots we need.
    glo = np.asarray(lo0, float).copy()
    ghi = np.asarray(hi0, float).copy()
    for k in ip:
        glo[k] -= PERP_GROW
        ghi[k] += PERP_GROW
    nlo_s = min(float(lo0[axi]), plane_val) - 0.02
    nhi_s = max(float(hi0[axi]), plane_val) + 0.02
    if inward > 0:
        nhi_s += PERP_SLAB_PAD
    else:
        nlo_s -= PERP_SLAB_PAD
    glo[axi], ghi[axi] = nlo_s, nhi_s
    slab = np.all((xyz >= glo) & (xyz <= ghi), axis=1)
    n_slab = int(slab.sum())
    rec["slab_dots"] = n_slab
    if n_slab < PERP_MIN_CLAIM:
        rec["result"] = f"kept - slab too thin ({n_slab} dots)"
        print(f"[vote]  perp: slab too thin ({n_slab} dots) - "
              "original box kept", flush=True)
        return None, None, rec, ""
    sdots = xyz[slab]

    # ---- CAMERA: FRAME THE FLAT OBJECT FROM ITS PLANE (user ruling
    # 2026-08-08: "the only really possible center for something flush
    # on a wall/floor/ceiling is ON that plane").
    #   aim  = the plane's coordinate on the NORMAL axis, and the
    #          ORIGINAL BOX's in-plane centre on the other two (the
    #          identity anchor — the box is what says WHICH object).
    #   size = the ORIGINAL BOX's in-plane extent x PERP_MARGIN.
    # The slab plays NO part in framing; it only supplies the dots that
    # get claimed further down. (Slab-centroid aim + slab-span framing
    # was tried 08-07 late and reverted 08-08 — for a wall opening the
    # slab is 6.6 m of outdoor scenery seen through the glass, so both
    # the centroid and the span were landscape, not door.)
    ctr = 0.5 * (np.asarray(lo0, float) + np.asarray(hi0, float))
    ctr[axi] = float(plane_val)
    span = float(max(float(hi0[k]) - float(lo0[k]) for k in ip))
    rec["frame"] = {"aim": "plane + box in-plane centre",
                    "box_span_m": round(span, 3)}
    dist_need = max(PERP_MARGIN * 0.5 * max(span, 0.2)
                    / math.tan(math.radians(FOV_GOOD) / 2), 1.0)
    # NO SHELL CLAMP (user ruling 2026-08-08): an object too wide to
    # frame from inside its own room simply cannot be framed from
    # inside it, and clamping the eye to the shell is what clipped the
    # glass door. We render a POINT CLOUD, so a camera standing behind
    # a wall is legal — the view-tunnel cull removes whatever sits
    # between it and the object. Only an absolute sanity cap applies.
    dist_act = min(dist_need, PERP_MAX_DIST)
    eye = ctr.copy()
    eye[axi] = ctr[axi] + inward * dist_act
    rec["dist_m"] = round(dist_act, 3)
    rec["eye_outside_shell"] = not in_bounds(eye)
    if dist_act < dist_need - 1e-3:
        rec["dist_clamped"] = {"need": round(dist_need, 3),
                               "got": round(dist_act, 3),
                               "cap_m": PERP_MAX_DIST}
        print(f"[vote]  perp: stand-off capped at {dist_act:.2f} m "
              f"of {dist_need:.2f} m needed", flush=True)
    if dist_act < 0.15:
        rec["result"] = "kept - no room for a face-on camera"
        print("[vote]  perp: no room for a face-on camera - "
              "original box kept", flush=True)
        return None, None, rec, ""

    # ---- RENDER, view-tunnel style — SAME GOVERNING PRINCIPLE AS THE
    # CARDS (user ruling 2026-08-08, module docstring): the slab is an
    # INVISIBLE LOCATOR, not the picture. Cull ONLY what sits between the
    # camera and the object; everything at or beyond the cut stays — the
    # wall surface the object sits in, an opening's glazing, the scene
    # beyond it, the neighbours on the same plane.
    # THE CUT IS THE NEARER OF TWO ANCHORS, minus NEAR_MARGIN:
    #   (a) t_box   — the OBJECT BOX's nearest corner along the view dir;
    #   (b) t_plane — the object's own PLANE at the aim point (the aim
    #                 already sits ON the plane at the box's in-plane
    #                 centre, so its depth IS the plane's depth there).
    # BOTH ANCHORS ARE NEEDED. A ceiling light HANGS BELOW its plane, so
    # cutting at the plane alone would delete the light itself. A wall
    # opening's box starts BEYOND its wall (obj_034: box lo_x 2.844 vs
    # plane 2.661), so cutting at the box's near face alone would delete
    # the wall the door sits in. The minimum of the two keeps both.
    # The old rule (keep the slab, delete the rest of the frustum out to
    # the slab's far face) was slice-alone-on-black in disguise and is
    # what filled the door / ceiling-light tiles with void. Do NOT
    # re-add the `& ~slab` term — the slab's job is CLAIMING, below.
    cam = make_cam([float(v) for v in eye], [float(v) for v in ctr],
                   FOV_GOOD, RES)
    vdir = ctr - eye
    vdir = vdir / np.linalg.norm(vdir)
    cn = np.array([[x, y, z] for x in (lo0[0], hi0[0])
                   for y in (lo0[1], hi0[1])
                   for z in (lo0[2], hi0[2])], float)
    t_box = float(((cn - eye) @ vdir).min())
    t_plane = float((ctr - eye) @ vdir)
    cut_depth = min(t_box, t_plane) - NEAR_MARGIN
    uu, vv_, zz = cam.project(xyz)
    in_cone = ((zz > 0.05) & (uu >= -40) & (uu < RES + 40)
               & (vv_ >= -40) & (vv_ < RES + 40))
    hole = in_cone & (((xyz - eye) @ vdir) < cut_depth)
    rec["cull"] = {"rule": CULL_PERP, "margin": NEAR_MARGIN,
                   "t_box": round(t_box, 3),
                   "t_plane": round(t_plane, 3),
                   "cut_depth": round(cut_depth, 3),
                   "kept": int((~hole).sum()), "of": int(len(xyz))}
    print(f"[vote]  perp: cull t_box {t_box:.2f} / t_plane "
          f"{t_plane:.2f} -> cut {cut_depth:.2f} m; "
          f"{int((~hole).sum()):,} of {len(xyz):,} gaussians kept",
          flush=True)
    vname = f"vote_{nid}_perp"
    view = {"name": vname, "label": f"{nid} {name} perp ({pid})",
            "eye": [float(v) for v in eye],
            "aim": [float(v) for v in ctr], "fov": FOV_GOOD}
    # params sidecar: this camera moves whenever the box or the plane
    # moves, so a same-named png from an earlier build must not survive
    render_gate(view, CULL_PERP, NEAR_MARGIN, ~hole)
    cply = sdir / f"votectx_{vname}.ply"
    write_subset_ply(~hole, cply)
    tf = sdir / f"votetgt_{vname}.json"
    tf.write_text(json.dumps([view], indent=1))
    perp_run_renders(tf, cply)
    cply.unlink(missing_ok=True)
    png = sdir / f"{vname}.png"
    if not png.exists():
        rec["result"] = "kept - perp render missing"
        print("[vote]  perp: render missing - original box kept",
              flush=True)
        return None, None, rec, ""
    strip = _fig(png.name, f"PERP RE-BOX &middot; face-on view ({pid})")

    # ---- DETECT, gated to the original box's screen footprint
    img = Image.open(png).convert("RGB")
    cu, cv, cz = cam.project(cn)      # box corners, built for the cull
    ok = cz > 0.2
    pb = ([float(np.clip(cu[ok].min() - PERP_DET_PAD, 0, RES)),
           float(np.clip(cv[ok].min() - PERP_DET_PAD, 0, RES)),
           float(np.clip(cu[ok].max() + PERP_DET_PAD, 0, RES)),
           float(np.clip(cv[ok].max() + PERP_DET_PAD, 0, RES))]
          if ok.any() else None)
    best = gdino_best(img, name, prior_box=pb)
    if best is None:
        rec["result"] = "no detection - kept"
        print("[vote]  perp: no detection - original box kept", flush=True)
        return None, None, rec, strip
    rec["score"] = round(float(best[0]), 3)
    mask = sam_mask(img, best[1], DIL_ISO)
    ov = img.convert("RGBA")
    layer = Image.new("RGBA", ov.size, (0, 0, 0, 0))
    px = layer.load()
    ys, xs = np.nonzero(mask)
    for yy, xx in zip(ys[::4], xs[::4]):
        px[int(xx), int(yy)] = (0, 255, 90, 100)
    ov = Image.alpha_composite(ov, layer).convert("RGB")
    ImageDraw.Draw(ov).rectangle(best[1], outline=(255, 40, 40), width=4)
    ov.save(sdir / f"{vname}_det.png")
    strip += _fig(f"{vname}_det.png",
                  f"PERP RE-BOX &middot; mask+box ok({best[0]:.2f})")

    # ---- BORDER-TRUNCATION GUARD (user finding 2026-08-07): if the
    # mask (or the detection box) reaches within 4 px of an image
    # border, the evidence on that side is CLIPPED BY THE FRAME, not by
    # the object's real edge (obj_034 signature: slab 29,867 dots vs
    # 8,009 claimed). A truncated side must NOT pull its extent inward
    # from the original box; a frame truncated on ALL sides re-boxes
    # nothing. Never silent: the decision lands in rec.
    # (PERP_EDGE_PX now lives with the other PERP_* constants so
    # PARAMS_HASH covers it — same value, same behaviour.)
    trunc = set()
    bx0, by0, bx1, by1 = (float(v) for v in best[1])
    if xs.size:
        if xs.min() <= PERP_EDGE_PX or bx0 <= PERP_EDGE_PX:
            trunc.add("left")
        if xs.max() >= RES - 1 - PERP_EDGE_PX or bx1 >= RES - 1 - PERP_EDGE_PX:
            trunc.add("right")
        if ys.min() <= PERP_EDGE_PX or by0 <= PERP_EDGE_PX:
            trunc.add("top")
        if ys.max() >= RES - 1 - PERP_EDGE_PX or by1 >= RES - 1 - PERP_EDGE_PX:
            trunc.add("bottom")
    if trunc:
        rec["truncated_edges"] = sorted(trunc)
        print(f"[vote]  perp: mask touches image border(s) "
              f"{sorted(trunc)} - those sides keep the original extent",
              flush=True)
    if len(trunc) == 4:
        rec["result"] = "frame truncated on all sides — kept"
        print("[vote]  perp: frame truncated on all sides - "
              "original box kept", flush=True)
        return None, None, rec, strip

    # ---- CLAIM the slab's dots through the mask (mirrors card_votes)
    u2, v2, z2 = cam.project(sdots)
    inb = ((z2 > 0.05) & (u2 >= 0) & (u2 < RES - 1)
           & (v2 >= 0) & (v2 < RES - 1))
    cl = np.zeros(len(sdots), bool)
    cl[np.nonzero(inb)[0]] = mask[v2[inb].astype(np.int64),
                                  u2[inb].astype(np.int64)]
    nc = int(cl.sum())
    rec["claimed"] = nc
    if nc < PERP_MIN_CLAIM:
        rec["result"] = f"kept - only {nc} claimed dots (< {PERP_MIN_CLAIM})"
        print(f"[vote]  perp: only {nc} claimed dots - original box kept",
              flush=True)
        return None, None, rec, strip

    # ---- RE-BOX: in-plane extents only, normal axis untouched
    K = sdots[cl]
    new_lo = np.asarray(lo0, float).copy()
    new_hi = np.asarray(hi0, float).copy()
    for k in ip:
        new_lo[k] = float(np.percentile(K[:, k], 1))
        new_hi[k] = float(np.percentile(K[:, k], 99))
    # BORDER-TRUNCATION GUARD, part 2: map each truncated image border
    # to the world side it clips (probe: project a small in-plane step
    # from the aim point and read which way it moves on screen), and on
    # those sides keep the ORIGINAL extent — the evidence there is
    # incomplete, so only the sides with complete evidence re-box.
    if trunc:
        kept_sides = []
        for k in ip:
            probe = np.vstack([ctr, ctr])
            probe[1][k] += 0.1
            pu, pv, _pz = cam.project(probe)
            du, dv = float(pu[1] - pu[0]), float(pv[1] - pv[0])
            if abs(du) >= abs(dv):
                lo_b, hi_b = ("left", "right") if du > 0 else ("right", "left")
            else:
                lo_b, hi_b = ("top", "bottom") if dv > 0 else ("bottom", "top")
            if lo_b in trunc:
                new_lo[k] = float(lo0[k])
                kept_sides.append([k, "lo", lo_b])
            if hi_b in trunc:
                new_hi[k] = float(hi0[k])
                kept_sides.append([k, "hi", hi_b])
        rec["truncation_kept_sides"] = kept_sides
    rec["from"] = [[k, round(float(lo0[k]), 3), round(float(hi0[k]), 3)]
                   for k in ip]
    rec["to"] = [[k, round(float(new_lo[k]), 3), round(float(new_hi[k]), 3)]
                 for k in ip]
    # SANITY GUARDS (user rule): a re-box may refine, never jump. Wild
    # candidates are RECORDED, never shipped.
    oc = np.array([0.5 * (lo0[k] + hi0[k]) for k in ip])
    ncn = np.array([0.5 * (new_lo[k] + new_hi[k]) for k in ip])
    shift = float(np.linalg.norm(ncn - oc))
    ratios = [float((new_hi[k] - new_lo[k])
                    / max(float(hi0[k] - lo0[k]), 1e-6)) for k in ip]
    rec["center_shift_m"] = round(shift, 3)
    rec["extent_ratio"] = [round(r, 3) for r in ratios]
    why = []
    if shift > PERP_MAX_SHIFT:
        why.append(f"in-plane center moved {shift:.2f} m "
                   f"(> {PERP_MAX_SHIFT:.2f})")
    for k, r in zip(ip, ratios):
        if r > PERP_MAX_RATIO or r < 1.0 / PERP_MAX_RATIO:
            why.append(f"axis {k} extent x{r:.2f} "
                       f"(> {PERP_MAX_RATIO:.0f}x either way)")
    if why:
        rec["result"] = "REJECTED - " + "; ".join(why) + " - original kept"
        print("[vote]  perp: REJECTED (" + "; ".join(why)
              + ") - original box kept", flush=True)
        return None, None, rec, strip
    rec["result"] = "reboxed"
    print("[vote]  perp: reboxed in-plane from "
          + " x ".join(f"{hi0[k]-lo0[k]:.2f}" for k in ip) + " to "
          + " x ".join(f"{new_hi[k]-new_lo[k]:.2f}" for k in ip)
          + f" m ({nc} claimed dots)", flush=True)
    return new_lo, new_hi, rec, strip


def perp_for_exempt(nid, name, lo0, hi0, plane):
    """Run the perp re-box and package it for add_exempt. `plane` is the
    (axis, plane_value, side, id) tuple — WALLS row for a wall,
    (1, CEIL, -1, 'CEIL') for the ceiling (interior lies ABOVE the
    ceiling value in this y-DOWN frame)."""
    axi, pv, side, pid = plane
    try:
        slo, shi, rec, strip = perp_rebox(nid, name, lo0, hi0,
                                          axi, float(pv), side, pid)
    except Exception as e:                                   # noqa: BLE001
        slo, shi, strip = None, None, ""
        rec = {"view": "perp", "plane": pid,
               "result": f"kept - perp re-box failed: {e}"}
        print(f"[vote]  perp: FAILED ({e}) - original box kept", flush=True)
    if strip:
        save_row(nid, "exempt", f"""
<section>
<h2>{nid} — {name} <span style='font-weight:400;font-size:13px'>
(vote-exempt, perp re-box)</span></h2>
<p>plane {pid} &nbsp;·&nbsp; {rec.get('result', '?')}
&nbsp;·&nbsp; slab {rec.get('slab_dots', 0):,} dots, claimed
{rec.get('claimed', 0):,}</p>
<div class='strip'>{strip}</div>
</section>""")
    return slo, shi, rec


# ================= per-object: slice -> render -> detect -> vote =======
cm_objects = []
kept_exempt = []


# ---- cone_map.html ROW SIDECARS (partial-runs-first, 2026-08-08) -----
# The page used to exist only as two in-memory lists, so a partial run
# could only ever produce a partial page. Each object's fragment is now
# persisted as it is produced; the page is rebuilt at the end by reading
# the fragments of ALL resolved ids in node order, so an unprocessed
# object keeps its row (and its pictures, which the scoped wipe spared).
# Two kinds keep the page's existing two-section structure: "exempt"
# (the perp re-box rows) and "vote" (the slice+vote rows).
def _row_path(nid, kind):
    return rowdir / (f"{nid}.exempt.html" if kind == "exempt"
                     else f"{nid}.html")


def clear_rows(nid):
    """Drop both fragments for an id that is about to be reprocessed —
    a status flip (voted <-> exempt) must not leave two rows behind,
    and an object that now produces no row must lose its old one."""
    for kind in ("vote", "exempt"):
        _row_path(nid, kind).unlink(missing_ok=True)


def save_row(nid, kind, html_fragment):
    _row_path(nid, kind).write_text(html_fragment, encoding="utf-8")


def read_row(nid, kind):
    p = _row_path(nid, kind)
    try:
        return p.read_text(encoding="utf-8") if p.exists() else ""
    except OSError as e:                                     # noqa: BLE001
        print(f"[vote] row sidecar {p.name} unreadable ({e})", flush=True)
        return ""


def backfill_rows_from_page():
    """ONE-TIME MIGRATION (2026-08-08). The sidecars did not exist before
    this restructure, so on an existing scene the FIRST partial run would
    rebuild a page with only the ids it processed — the very failure this
    change is meant to kill. Split the cone_map.html already on disk into
    its <section> blocks and write any MISSING sidecar. Purely additive:
    an existing sidecar is never overwritten, and no page just means
    there is nothing to recover. Scene-agnostic (no id lists, no labels)
    and self-retiring — once every row has a sidecar it does nothing."""
    page = sd / "cone_map.html"
    if not page.exists():
        return 0
    try:
        txt = page.read_text(encoding="utf-8")
    except OSError as e:                                     # noqa: BLE001
        print(f"[vote] row backfill: cone_map.html unreadable ({e})",
              flush=True)
        return 0
    n = 0
    for m in re.finditer(r"<section>.*?</section>", txt, re.S):
        sec = m.group(0)
        h2 = re.search(r"<h2>\s*([^\s<]+)", sec)
        if not h2:
            continue
        kind = ("exempt" if "vote-exempt, perp re-box" in sec else "vote")
        p = _row_path(h2.group(1), kind)
        if p.exists():
            continue
        # the leading newline reproduces the fragment save_row writes
        p.write_text("\n" + sec, encoding="utf-8")
        n += 1
    if n:
        print(f"[vote] row backfill: recovered {n} cone-map row(s) from "
              "the existing cone_map.html", flush=True)
    return n


backfill_rows_from_page()


def add_exempt(nid, name, lo0, hi0, status, kept, extra=None,
               ship_lo=None, ship_hi=None):
    """Record a vote-exempt node. The ORIGINAL box is kept verbatim as
    evidence; the box that SHIPS is the shell-clipped one (step 6) —
    of the perp RE-BOXED extents when the face-on view produced them
    (ship_lo/ship_hi), otherwise of the original."""
    rule = {"kept": kept}
    if extra:
        rule.update(extra)
    boxes = {"original": {"lo": [round(float(v), 3) for v in lo0],
                          "hi": [round(float(v), 3) for v in hi0]}}
    if ship_lo is not None:
        boxes["rebox"] = {"lo": [round(float(v), 3) for v in ship_lo],
                          "hi": [round(float(v), 3) for v in ship_hi]}
    boxes["shipping"] = ship_box(lo0 if ship_lo is None else ship_lo,
                                 hi0 if ship_hi is None else ship_hi, rule)
    kept_exempt.append({"id": nid, "name": name, "nviews_vote": 0,
                        "status": status, "boxes": boxes, "rule": rule})


for n in nodes:
    nid, name = n["id"], n["name"]
    geo = n["geometry"]
    lo0 = np.array(geo["aabb_min"])
    hi0 = np.array(geo["aabb_max"])
    corners = np.array([[x, y, z] for x in (lo0[0], hi0[0])
                        for y in (lo0[1], hi0[1]) for z in (lo0[2], hi0[2])])
    print(f"[vote] {nid} {name}", flush=True)
    clear_rows(nid)     # this run owns this id's cone-map row from here

    # CEILING EXEMPTION (user ruling 2026-08-06 after R-S2-27): a flat
    # ceiling-mounted object has no side silhouette for the cardinals,
    # and the floor-anchored height band slices the whole room column
    # beneath it (the x288-x5027 blowups). Geometric test only — hangs
    # from the ceiling plane AND stays in the upper half of the room
    # (y-down frame: CEIL < FLOOR) — never a label list.
    room_h = FLOOR - CEIL
    if (lo0[1] - CEIL) < 0.35 and (hi0[1] - CEIL) < 0.5 * room_h:
        print("[vote]  ceiling-mounted — vote exempt, resolved box "
              "kept (in-plane extents from the perp re-box)", flush=True)
        # PERP RE-BOX: the vote is skipped, but one face-on view still
        # fixes the drifted in-plane (x,z) extents. Ceiling plane in the
        # y-DOWN frame: axis 1 at CEIL, interior ABOVE it -> side -1.
        _slo, _shi, _rec = perp_for_exempt(nid, name, lo0, hi0,
                                           (1, CEIL, -1, "CEIL"))
        add_exempt(nid, name, lo0, hi0, "kept_ceiling",
                   "ceiling-mounted — vote exempt (geometric: top "
                   "within 0.35 m of the shell ceiling, bottom in the "
                   "upper half of the room)",
                   {"rebox": _rec}, ship_lo=_slo, ship_hi=_shi)
        continue

    # WALL PROTRUSION EXEMPTION (user ruling 2026-08-07 late, REPLACING
    # the 2026-08-06b flush+thin test). Same disease as the ceiling one:
    # a wall-hugging object has no plan-view footprint, so the top
    # detection can't start and the full-height wedge slices a room
    # column in front of the wall (obj_002 x369). New geometric test:
    # the box TOUCHES OR CROSSES a shell wall plane AND protrudes into
    # the room interior <= WALL_PROTRUDE_MAX. Depth beyond the plane is
    # ignored on purpose — openings (glass door, window) have their mass
    # at or beyond the wall and the thin test dropped them (obj_034
    # regression). It also un-exempts the thin test's false exempts
    # (plant, shelf magazines, R-S2-30), which are now voted.
    _wall_hit = wall_protrusion(lo0, hi0)
    if _wall_hit is not None:
        _wid, _protr = _wall_hit
        print(f"[vote]  wall-protrusion {_protr:.2f} m at {_wid} — vote "
              "exempt, resolved box kept (in-plane extents from the perp "
              "re-box)", flush=True)
        # PERP RE-BOX: same treatment as the ceiling, on this object's
        # own wall plane — the drifting glass door is the motivating case.
        _wrow = next(w for w in WALLS if w[3] == _wid)
        _slo, _shi, _rec = perp_for_exempt(nid, name, lo0, hi0,
                                           (_wrow[0], _wrow[1], _wrow[2],
                                            _wid))
        add_exempt(nid, name, lo0, hi0, "kept_wall",
                   "wall protrusion — vote exempt (geometric: touches "
                   "or crosses a shell wall plane and protrudes "
                   f"<= {WALL_PROTRUDE_MAX:.2f} m into the room)",
                   {"wall": _wid, "protrusion_m": round(_protr, 3),
                    "rebox": _rec}, ship_lo=_slo, ship_hi=_shi)
        continue

    # FLOOR-FLUSH EXEMPTION (user ruling 2026-08-07, with the shell
    # electorate filter): rugs/floor mats are the wall-flush disease
    # rotated to the floor — flush to the shell floor AND thin
    # vertically. Must run BEFORE the electorate filter below, which
    # would otherwise gut a flat floor object's entire electorate.
    # y-down frame: an object's bottom is hi0[1]; FLOOR > CEIL.
    if (FLOOR - hi0[1]) < 0.20 and (hi0[1] - lo0[1]) < 0.30:
        print("[vote]  floor-flush — vote exempt, resolved box kept "
              "verbatim", flush=True)
        add_exempt(nid, name, lo0, hi0, "kept_floor",
                   "floor-flush — vote exempt (geometric: bottom "
                   "within 0.20 m of the shell floor and < 0.30 m "
                   "tall)")
        continue

    # ---- SLICE: prism primary, wedge fallback ----
    slice_mask, slice_info = None, ""
    top_ctx = None          # (cam, box, img, view name, score, eye)
    top_frame_rec = None    # framing check / re-frame  -> rule record
    top_trunc_rec = None    # border-truncation guard   -> rule record
    top_shots_rec = []      # every plan shot + re-shoot -> rule record
    top_choice_rec = None   # which detection was chosen -> rule record
    top_choice_overruled = False   # ... and whether that overruled score
    tcands, c0 = top_cam_for(n["geometry"], eye0, CEIL, WALL_PAD,
                             in_bounds, empty_at, EMPTY_MAX)
    for vname, teye, tfov in tcands:
        png = rdir / f"{nid}_{vname}.png"
        if not png.exists():
            continue
        cam = make_cam(teye, list(c0), tfov, RES)
        # ---- FRAMING CHECK, BEFORE DETECTING (bug fix 2026-08-08; see
        # the FRAME_* constants for the two measured failures). A plan
        # view that CUTS the object, or that the object nearly fills,
        # cannot be the ruler the slice is measured with: the detector
        # only ever sees the visible part, and the prior gate that is
        # supposed to keep the detection honest degenerates to
        # everything-passes. Same evidence doctrine as the perp re-box:
        # what the frame hides is missing evidence, not object edge.
        ext, clip_sides, fx, fy, fit_ok = frame_verdict(cam, corners)
        _why = []
        if ext is None:
            _why.append("box corner(s) behind the camera")
        else:
            if clip_sides:
                _why.append("frame cuts the box on "
                            + "/".join(clip_sides))
            if fx > FRAME_MAX_FILL or fy > FRAME_MAX_FILL:
                _why.append(f"box fills {max(fx, fy):.2f} of an axis "
                            f"(> {FRAME_MAX_FILL:.2f})")
        frec = {"view": vname, "reframed": False,
                "fit_before": "ok" if fit_ok else "; ".join(_why),
                "fill_x": None if fx is None else round(float(fx), 3),
                "fill_y": None if fy is None else round(float(fy), 3),
                "fill_before": [None if fx is None else round(float(fx), 3),
                                None if fy is None else round(float(fy), 3)],
                "dist_m": round(float(np.linalg.norm(
                    np.asarray(teye, float) - np.asarray(c0, float))), 3)}
        if not fit_ok:
            # ---- RE-FRAME AND RE-RENDER: same view direction, same
            # aim, same fov — stand further back until the whole box
            # fits FRAME_TARGET_FILL. The eye may leave the room (point
            # cloud; the perp camera has the same licence), and the
            # picture keeps whatever the cached plan render kept.
            print(f"[vote]  top frame: {vname} cannot frame the object "
                  f"({frec['fit_before']}) — re-framing along the same "
                  "view direction", flush=True)
            rf = reframe_cam(c0, teye, tfov, corners)
            if rf is None:
                frec["reframe"] = "skipped — degenerate view direction"
                print("[vote]  top frame: degenerate view direction — "
                      "cached plan render used as-is", flush=True)
            else:
                rdist, rcam, rfx, rfy, rcap = rf
                reye = rcam.pos
                clip_ceiling = (vname == "ctop"
                                or float(reye[1]) < CEIL + 0.08)
                rpng = top_fit_render(nid, name, f"{nid}_topfit", reye,
                                      c0, tfov, clip_ceiling)
                frec.update({"reframed": True, "render": rpng.name,
                             "eye": [round(float(v), 3) for v in reye],
                             "dist_m": round(float(rdist), 3),
                             "fov_kept": round(float(tfov), 3),
                             "target_fill": FRAME_TARGET_FILL,
                             "clip_ceiling": bool(clip_ceiling),
                             "fill_x": None if rfx is None
                             else round(float(rfx), 3),
                             "fill_y": None if rfy is None
                             else round(float(rfy), 3)})
                if rcap:
                    frec["dist_capped_m"] = TOP_FIT_MAX_DIST
                print(f"[vote]  top frame: re-framed to {rdist:.2f} m "
                      f"(fill {rfx:.2f} x {rfy:.2f}, fov {tfov:.1f} kept"
                      + (", ceiling clipped" if clip_ceiling else "")
                      + f") -> {rpng.name}", flush=True)
                if rpng.exists():
                    png, cam, teye = rpng, rcam, [float(v) for v in reye]
                else:
                    frec["reframed"] = False
                    frec["reframe"] = ("render missing — cached plan "
                                       "render used")
                    print("[vote]  top frame: re-frame render MISSING — "
                          "falling back to the cached plan render",
                          flush=True)
        top_frame_rec = frec
        # ---- SHOOT / RE-SHOOT LADDER (user ruling 2026-08-08) --------
        # A detection touching a border is CUT BY THE FRAME there, not
        # by the object's edge (obj_020 signature: [515, 2, 768, 344] —
        # 2 px from the top border, 0 px from the right). That used to
        # be PATCHED: the footprint was extended out to the projected
        # prior on the truncated sides. A patch is a GUESS. The framing
        # check above already answers the same question honestly when
        # the PRIOR does not fit — take another shot, pulled back, and
        # look again — so the DETECTION now gets that same answer:
        # same view direction, same aim, same fov, stand-off scaled so
        # the detection's screen extent lands near FRAME_TARGET_FILL,
        # re-rendered as <id>_topfitN.png (params-sidecar gated, same
        # content/clip rules) and re-detected under the SAME prior gate.
        # At most TOP_FIT_RETRIES extra shots; the ladder stops the
        # moment a detection is clear of every border. Every shot lands
        # in the rule record as top_shots, so a reviewer can watch the
        # object being brought into frame.
        # THE LADDER NOW FIRES ONLY WHEN THE CHOSEN CANDIDATE STILL
        # TOUCHES A BORDER (user ruling 2026-08-08). Nothing here had to
        # change for that: the border test below reads the box
        # gdino_best CHOSE, and since the choice now prefers an
        # untruncated candidate over a truncated one (DET_EDGE_PX ==
        # TOP_EDGE_PX, so both agree on what "touching" means), a
        # re-shoot is requested only when EVERY admitted candidate was
        # cut off — i.e. when another picture really is the only way to
        # see the whole object. obj_020 used to spend a re-shoot here
        # and no longer does.
        shots = []
        best = tb = praw_adopt = img = None
        trunc = []
        s_png, s_cam, s_eye = png, cam, teye
        for shot_k in range(TOP_FIT_RETRIES + 1):
            su, sv_, sz = s_cam.project(corners)
            ok = sz > 0.2
            # the prior's RAW screen extent (unclipped) — what the
            # last-resort patch below extends a cut-off detection out to
            praw = ([float(su[ok].min()), float(sv_[ok].min()),
                     float(su[ok].max()), float(sv_[ok].max())]
                    if ok.any() else None)
            pb = ([float(np.clip(su[ok].min(), 0, RES)),
                   float(np.clip(sv_[ok].min(), 0, RES)),
                   float(np.clip(su[ok].max(), 0, RES)),
                   float(np.clip(sv_[ok].max(), 0, RES))]
                  if ok.any() else None)
            s_img = Image.open(s_png).convert("RGB")
            s_best = gdino_best(s_img, name, prior_box=pb)
            srec = {"shot": shot_k, "view": vname, "render": s_png.name,
                    "dist_m": round(float(np.linalg.norm(
                        np.asarray(s_eye, float)
                        - np.asarray(c0, float))), 3)}
            if s_best is None:
                srec.update({"det_box": None, "score": None,
                             "fill_x": None, "fill_y": None,
                             "truncated_sides": None,
                             "action": "no detection"})
                shots.append(srec)
                print(f"[vote]  top shot {shot_k}: {s_png.name} — no "
                      "detection", flush=True)
                break
            s_tb = s_best[1]
            _iw, _ih = s_img.size
            s_trunc = []
            if s_tb[0] <= TOP_EDGE_PX:
                s_trunc.append("left")
            if s_tb[1] <= TOP_EDGE_PX:
                s_trunc.append("top")
            if s_tb[2] >= _iw - 1 - TOP_EDGE_PX:
                s_trunc.append("right")
            if s_tb[3] >= _ih - 1 - TOP_EDGE_PX:
                s_trunc.append("bottom")
            # PRIOR OVERLAP, RECORDED ONLY. Same fraction gdino_best's
            # gate thresholds (intersection / detection area), written
            # down so a reviewer can see whether the pulled-back view
            # still elects the same object and by how much. THE GATE
            # ITSELF IS UNTOUCHED — that is a separate decision.
            _pf = None
            if pb is not None:
                _ix0, _iy0 = max(s_tb[0], pb[0]), max(s_tb[1], pb[1])
                _ix1, _iy1 = min(s_tb[2], pb[2]), min(s_tb[3], pb[3])
                _pf = (max(0.0, _ix1 - _ix0) * max(0.0, _iy1 - _iy0)
                       / ((s_tb[2] - s_tb[0]) * (s_tb[3] - s_tb[1])
                          + 1e-9))
            srec.update({"det_box": [round(float(v), 1) for v in s_tb],
                         "score": round(float(s_best[0]), 3),
                         "fill_x": round((s_tb[2] - s_tb[0]) / _iw, 3),
                         "fill_y": round((s_tb[3] - s_tb[1]) / _ih, 3),
                         "truncated_sides": s_trunc,
                         "prior_frac": (None if _pf is None
                                        else round(float(_pf), 3))})
            # WHICH DETECTION WAS CHOSEN, AND WHY (user ruling
            # 2026-08-08). The model usually returns several boxes; the
            # ranking picks one and the loser is now visible next to the
            # winner. Recorded ONLY here — the card re-detect and the
            # perp re-box rank identically but do not record.
            _cd = s_best[2]
            _cl = _cd["candidates"]
            _ci = _cd["chosen"]
            _ru = next((c for k, c in enumerate(_cl) if k != _ci), None)
            _choice = {"chosen": _ci,
                       "chosen_match": _cl[_ci]["match"],
                       "chosen_score": _cl[_ci]["score"],
                       "n_candidates": _cd["n_candidates"],
                       "decided_by": _cd["decided_by"],
                       "runner_up_match": (None if _ru is None
                                           else _ru["match"]),
                       "runner_up_score": (None if _ru is None
                                           else _ru["score"]),
                       "candidates": _cl}
            # this shot is the one the slice is measured with, unless a
            # later shot succeeds
            best, tb, trunc, praw_adopt = s_best, s_tb, s_trunc, praw
            img, cam, png, teye = s_img, s_cam, s_png, s_eye
            top_choice_rec = _choice
            top_choice_overruled = bool(_cd["overruled_score"])
            print(f"[vote]  top pick: {_cd['n_candidates']} candidate(s), "
                  f"chose #{_ci} match "
                  + ("n/a" if _cl[_ci]["match"] is None
                     else f"{_cl[_ci]['match']:.3f}")
                  + f" score {_cl[_ci]['score']:.3f} by "
                  f"{_cd['decided_by']}"
                  + ("  [OVERRULED the highest score]"
                     if _cd["overruled_score"] else ""), flush=True)
            print(f"[vote]  top shot {shot_k}: {s_png.name} @ "
                  f"{srec['dist_m']:.2f} m det {srec['det_box']} "
                  f"score {srec['score']:.2f} fill "
                  f"{srec['fill_x']:.2f}x{srec['fill_y']:.2f} prior "
                  + ("n/a" if _pf is None else f"{_pf:.2f}")
                  + f" borders {'/'.join(s_trunc) or 'none'}", flush=True)
            if not s_trunc:
                srec["action"] = "clear of every border"
                shots.append(srec)
                break
            if shot_k >= TOP_FIT_RETRIES:
                srec["action"] = ("still truncated after "
                                  f"{TOP_FIT_RETRIES} re-shoot(s)")
                shots.append(srec)
                break
            # PULL BACK so the DETECTION's screen extent would land at
            # about FRAME_TARGET_FILL of the frame. On a TRUNCATED axis
            # the detection's own extent is not a measurement of the
            # object — it stops at the border — so the smallest extent
            # we can honestly assume there is the FRAME ITSELF, which
            # keeps every re-shoot a real pull-back instead of a
            # zoom-in (a cut-off detection is often small on screen).
            _cut_x = ("left" in s_trunc) or ("right" in s_trunc)
            _cut_y = ("top" in s_trunc) or ("bottom" in s_trunc)
            need = max(float(_iw) if _cut_x else s_tb[2] - s_tb[0],
                       float(_ih) if _cut_y else s_tb[3] - s_tb[1])
            grow = (need / (FRAME_TARGET_FILL * RES)) * TOP_RESHOOT_SAFETY
            grow = float(min(max(grow, 1.02), 4.0))
            pc = pullback_cam(c0, s_eye, tfov, grow)
            if pc is None:
                srec["action"] = "re-shoot skipped — degenerate view"
                shots.append(srec)
                break
            n_dist, n_cam, n_cap = pc
            n_eye = n_cam.pos
            n_clip = (vname == "ctop" or float(n_eye[1]) < CEIL + 0.08)
            n_png = top_fit_render(nid, name,
                                   f"{nid}_topfit{shot_k + 2}",
                                   n_eye, c0, tfov, n_clip)
            srec["reshoot"] = {"scale": round(grow, 3),
                               "dist_m": round(float(n_dist), 3),
                               "eye": [round(float(v), 3) for v in n_eye],
                               "render": n_png.name,
                               "clip_ceiling": bool(n_clip),
                               "dist_capped_m": (TOP_FIT_MAX_DIST
                                                 if n_cap else None)}
            if not n_png.exists():
                srec["action"] = ("re-shoot render MISSING — this shot "
                                  "stands")
                shots.append(srec)
                print("[vote]  top det: re-shoot render MISSING — "
                      "keeping this shot", flush=True)
                break
            srec["action"] = (f"truncated on {'/'.join(s_trunc)} — "
                              f"re-shot at {n_dist:.2f} m (x{grow:.2f})")
            shots.append(srec)
            print(f"[vote]  top det: truncated on {'/'.join(s_trunc)} "
                  f"— RE-SHOOT {shot_k + 1}/{TOP_FIT_RETRIES} at "
                  f"{n_dist:.2f} m (x{grow:.2f}"
                  + (", capped" if n_cap else "")
                  + (", ceiling clipped" if n_clip else "")
                  + f") -> {n_png.name}", flush=True)
            s_png, s_cam, s_eye = n_png, n_cam, [float(v) for v in n_eye]
        top_shots_rec.extend(shots)
        n_reshoots = max(0, len(shots) - 1)
        if best is None:
            slice_info = f"{vname}: no detection"
            continue
        praw = praw_adopt
        # ---- BORDER-TRUNCATION GUARD, LAST RESORT. Reached only when
        # the object is STILL cut off after the re-shoot ladder above.
        # The slice must not be cut where the frame was: on each
        # truncated side the footprint keeps the PRIOR (the projected
        # original box), which is the only evidence we have where the
        # camera could not look. Truncated on all four sides = no
        # usable evidence at all -> wedge fallback.
        fb = [float(v) for v in tb]        # the FOOTPRINT box
        _after = (f" (after {n_reshoots} re-shoot(s))" if n_reshoots
                  else "")
        if len(trunc) == 4:
            top_trunc_rec = {"view": vname, "sides": trunc,
                             "det_box": [round(float(v), 1) for v in tb],
                             "reshoots": n_reshoots,
                             "action": "detection unusable — wedge "
                                       "fallback" + _after}
            slice_info = (f"{vname}: detection touches all four borders "
                          "— unusable")
            print(f"[vote]  top det: {vname} detection touches ALL FOUR "
                  "borders" + _after + " — unusable, falling through to "
                  "the wedge", flush=True)
            continue
        if trunc:
            moved = []
            if praw is None:
                note = "prior not projectable — footprint left at the box"
            else:
                for _sd, _k, _fn in (("left", 0, min), ("top", 1, min),
                                     ("right", 2, max), ("bottom", 3, max)):
                    if _sd not in trunc:
                        continue
                    _new = float(_fn(fb[_k], praw[_k]))
                    if abs(_new - fb[_k]) > 0.5:
                        moved.append([_sd, round(fb[_k], 1),
                                      round(_new, 1)])
                    fb[_k] = _new
                note = ("footprint extended to the projected original box"
                        if moved else
                        "prior adds nothing on those sides")
            top_trunc_rec = {"view": vname, "sides": trunc,
                             "det_box": [round(float(v), 1) for v in tb],
                             "footprint_box": [round(v, 1) for v in fb],
                             "prior_box": (None if praw is None else
                                           [round(v, 1) for v in praw]),
                             "reshoots": n_reshoots,
                             "extended": moved, "action": note + _after}
            print(f"[vote]  top det: still truncated on "
                  f"{'/'.join(trunc)}" + _after + f" — {note}"
                  + (" " + str(moved) if moved else ""), flush=True)
        top_ctx = (cam, tb, img, vname, best[0], teye)

        def ray_plane_xz(u_px, v_px, y_plane):
            d = np.array([(u_px - cam.cx) / cam.f,
                          -(v_px - cam.cy) / cam.f, 1.0]) @ cam.R
            t = (y_plane - cam.pos[1]) / d[1]
            p = cam.pos + t * d
            return [p[0], p[2]]

        # footprint from the beam only across the OBJECT's height band
        # (prior top - 0.3m margin, down to the floor) — casting ceiling
        # to floor smeared the tilted beam ~0.7m sideways (obj_041/020
        # finding); the CUT below stays full-height, only the footprint
        # tightens
        y_top = max(CEIL + 0.1, lo0[1] - 0.3)
        foot = []
        # `fb` is the detection box, extended back out to the projected
        # prior on any side the frame truncated (guard above). Rays
        # through pixels OUTSIDE the image are still valid rays, which
        # is what lets the footprint reach past a cut-off detection.
        for uu, vv2 in ((fb[0], fb[1]), (fb[2], fb[1]),
                        (fb[2], fb[3]), (fb[0], fb[3])):
            for yp in (y_top, FLOOR):
                foot.append(ray_plane_xz(uu, vv2, yp))
        foot = np.array(foot)
        cen = foot.mean(axis=0)
        span = foot.max(axis=0) - foot.min(axis=0)
        marg = np.minimum(PAD * span, CAP_M)
        foot = cen + (foot - cen) * ((span + 2 * marg)
                                     / np.maximum(span, 1e-6))
        hull = MplPath(foot[ConvexHull(foot).vertices])
        slice_mask = below_ceil & hull.contains_points(xyz[:, [0, 2]])
        slice_info = (f"PRISM ({vname}"
                      + ("+refit" if frec.get("reframed") else "")
                      + (f"+reshoot{n_reshoots}" if n_reshoots else "")
                      + f" ok {best[0]:.2f})"
                      + (" [det truncated " + "/".join(trunc) + "]"
                         if trunc else ""))
        break
    if slice_mask is None:
        # FALLBACK: original-box wedge, capped margin, full height
        slice_mask = np.zeros(len(xyz), bool)
        nb = 0
        for fid in n.get("members", []):
            fo = f30_by_id.get(fid)
            if not fo:
                continue
            for mi in fo.get("members", []):
                if mi >= len(pool_j):
                    continue
                m = pool_j[mi]
                cam0 = view_cam0(m["view"])
                b = [m["box"]["xmin"], m["box"]["ymin"],
                     m["box"]["xmax"], m["box"]["ymax"]]
                dist0 = float(np.linalg.norm(
                    np.array(geo["center"], float) - eye0))
                cap_px = cam0.f * CAP_M / max(dist0, 0.5)
                pw = min(PAD * (b[2] - b[0]), cap_px)
                u, vv_, z = cam0.project(xyz)
                slice_mask |= ((z > 0.05) & (u >= b[0] - pw)
                               & (u <= b[2] + pw))
                nb += 1
        slice_mask &= below_ceil
        slice_info = f"FALLBACK WEDGE ({nb} sp0 boxes; {slice_info})"
    # NOTE: a SLICE SHELL CLAMP (slice_mask &= shell-interior) was tried
    # here 2026-08-07 and REVERTED the same day (user ruling: renders
    # keep wall context for segmentation — the clamp turned excluded
    # wall dots into cone-minus-slice "occluders" and blanked them from
    # the tiles; ballot safety = the half-space electorate filter at
    # tally; geometry cleanup = protrusion exemption + shell clip at
    # shipping). Do not re-add it.
    cidx = np.nonzero(slice_mask)[0]
    dots = xyz[cidx]
    # SHELL ELECTORATE FILTER (user ruling 2026-08-07; HALF-SPACE form
    # 2026-08-07 late, obj_014 wall-leak finding): structure is a side,
    # not a slab — a dot at or behind a measured shell plane (minus the
    # SHELL_EPS tolerance) is ineligible, including the wall-interior
    # splat fuzz the old ±eps band re-admitted. Votes zeroed at tally.
    # Census printed + recorded (measure-first doctrine).
    elig = ((dots[:, 1] < FLOOR - SHELL_EPS)
            & (dots[:, 1] > CEIL + SHELL_EPS)
            & (dots[:, 0] > XLO + SHELL_EPS)
            & (dots[:, 0] < XHI - SHELL_EPS)
            & (dots[:, 2] > ZLO + SHELL_EPS)
            & (dots[:, 2] < ZHI - SHELL_EPS))
    n_shell_dots = int((~elig).sum())
    print(f"[vote] slice: {len(dots):,} dots  [{slice_info}]  "
          f"(shell-plane ineligible: {n_shell_dots:,})", flush=True)
    if len(dots) < 100:
        print("[vote]   too few dots, skipping", flush=True)
        # TIER-4 doctrine: never silent — vote is impossible on this
        # slice, so the ORIGINAL box ships as a kept row (recorded like
        # the exemption rows, obj_017_c00 vanish fix 2026-08-07).
        _x = {"n_dots": int(len(dots))}
        if top_frame_rec is not None:
            _x["top_frame"] = top_frame_rec
        if top_shots_rec:
            _x["top_shots"] = top_shots_rec
        if top_choice_rec is not None:
            _x["top_choice"] = top_choice_rec
            _x["top_choice_overruled_score"] = top_choice_overruled
        if top_trunc_rec is not None:
            _x["top_det_truncated"] = top_trunc_rec["sides"]
            _x["top_det_extend"] = top_trunc_rec
        add_exempt(nid, name, lo0, hi0, "kept",
                   "slice too thin (< 100 dots) — "
                   "vote impossible, resolved box ships", _x)
        continue
    plyp = sdir / f"vote_{nid}.ply"
    write_subset_ply(slice_mask, plyp)

    # ---- RENDER: 4 near-cardinals of the slice, WSL renderer ----
    ctr = dots.mean(axis=0)
    dlo = np.percentile(dots, 2, axis=0)
    dhi = np.percentile(dots, 98, axis=0)
    half = float(max(dhi - dlo) / 2)
    dist = max(1.4 * max(half, 0.2)
               / math.tan(math.radians(FOV_GOOD) / 2), 1.2)
    views = []
    for k, base in enumerate([np.array([1.0, 0, 0]),
                              np.array([-1.0, 0, 0]),
                              np.array([0, 0, 1.0]),
                              np.array([0, 0, -1.0])]):
        dirv = roty(base, OFF_AXIS)
        eye = ctr + dirv * dist
        views.append({"name": f"vote_{nid}_card{k}",
                      "label": f"{nid} {name} card{k}",
                      "eye": [float(v) for v in eye],
                      "aim": [float(v) for v in ctr], "fov": FOV_GOOD})
    # clean 3/4 slice view for the page (rendered in the same WSL batch)
    d34 = np.array([1.0, 0.0, 0.65])
    d34 /= np.linalg.norm(d34)
    eye34 = ctr + d34 * dist
    eye34[1] = ctr[1] - 0.55 * dist        # y-down: minus = raise camera
    views.append({"name": f"vote_{nid}_slice34",
                  "label": f"{nid} {name} slice 3/4 view",
                  "eye": [float(v) for v in eye34],
                  "aim": [float(v) for v in ctr], "fov": FOV_GOOD})
    # VIEW TUNNEL (user design 2026-08-06 after R-S2-27; CULL RULE
    # REPLACED by user ruling 2026-08-08). Each card renders the FULL
    # scene minus what is IN FRONT OF THE OBJECT: gaussians inside this
    # camera's view cone (small pad for splat tails) whose depth along
    # the view direction is nearer than t_near - NEAR_MARGIN, where
    # t_near is the smallest depth over the OBJECT BOX's 8 corners.
    # Nothing else is removed — the object and every one of its
    # surroundings that is NOT blocking the view (the wall beside it,
    # the floor under it, the room behind it) stays in the picture,
    # which is what segmentation needs.
    # The old rule culled everything in the cone up to the SLICE's FAR
    # depth minus the slice members, which deleted the walls beside and
    # behind the object and coupled the pictures to the slice geometry.
    # THE CARD RENDERS ARE NOW DECOUPLED FROM THE SLICE: the slice still
    # decides who may be CLAIMED, never what is DRAWN. Claims are still
    # counted on slice dots only. Per-card plys are transient (≈ whole
    # scene).
    def ctx_render_jobs(card_views):
        jobs = []
        for v in card_views:
            veye = np.array(v["eye"], float)
            vdir = np.array(v["aim"], float) - veye
            vdir /= np.linalg.norm(vdir)
            t_near = float(((corners - veye) @ vdir).min())
            camk = make_cam(v["eye"], v["aim"], v["fov"], RES)
            uu, vv_, zz = camk.project(xyz)
            in_cone = ((zz > 0.05) & (uu >= -40) & (uu < RES + 40)
                       & (vv_ >= -40) & (vv_ < RES + 40))
            hole = in_cone & (((xyz - veye) @ vdir) < (t_near - NEAR_MARGIN))
            render_gate(v, CULL_TUNNEL, NEAR_MARGIN, ~hole)
            cply = sdir / f"votectx_{v['name']}.ply"
            write_subset_ply(~hole, cply)
            ctf = sdir / f"votetgt_{v['name']}.json"
            ctf.write_text(json.dumps([v], indent=1))
            jobs.append((ctf, cply, True))
        return jobs

    def run_renders(jobs):
        _py = "/root/miniconda3/envs/splatanalyzer/bin/python"
        _scr = to_wsl(HERE / 'analyzer' / 'render_targets_wsl.py')
        parts = [f"{_py} '{_scr}' --targets '{to_wsl(t)}' "
                 f"--ply '{to_wsl(p)}' --out '{to_wsl(sdir)}' --res {RES}"
                 for t, p, _tr in jobs]
        cmd = ("wsl -d Ubuntu-24.04 -- bash -c \"cd /root/splat_analyzer"
               " && " + " && ".join(parts) + "\"")
        subprocess.run(cmd, check=True, timeout=1800, shell=True)
        for _t, p, transient in jobs:
            if transient:
                p.unlink(missing_ok=True)

    def card_votes(card_views):
        """Detect+SAM each card render. Returns [(claims|None, info)];
        claims are over slice dots only."""
        out = []
        for v in card_views:
            vname = v["name"].split(f"vote_{nid}_", 1)[-1]
            png = sdir / f"{v['name']}.png"
            info = {"view": vname, "eye": v["eye"]}
            if not png.exists():
                info["why"] = "no_render"
                out.append((None, info))
                continue
            img = Image.open(png).convert("RGB")
            cam = make_cam(v["eye"], v["aim"], v["fov"], RES)
            u, vv2, z = cam.project(dots)
            inb = ((z > 0.05) & (u >= 0) & (u < RES - 1)
                   & (vv2 >= 0) & (vv2 < RES - 1))
            # context in frame: gate the re-detect to the slice's screen
            # footprint (same prior mechanism as the top view) so a
            # same-class object in the backdrop can't be picked
            pb = ([float(max(0, u[inb].min() - 20)),
                   float(max(0, vv2[inb].min() - 20)),
                   float(min(RES, u[inb].max() + 20)),
                   float(min(RES, vv2[inb].max() + 20))]
                  if inb.any() else None)
            best = gdino_best(img, name, prior_box=pb)
            if best is None:
                info["why"] = "no_redetect"
                out.append((None, info))
                print(f"[vote] {vname} no_redetect", flush=True)
                continue
            mask = sam_mask(img, best[1], DIL_ISO)
            ov = img.convert("RGBA")
            layer = Image.new("RGBA", ov.size, (0, 0, 0, 0))
            px = layer.load()
            ys, xs = np.nonzero(mask)
            for yy, xx in zip(ys[::4], xs[::4]):
                px[int(xx), int(yy)] = (0, 255, 90, 100)
            ov = Image.alpha_composite(ov, layer).convert("RGB")
            dr = ImageDraw.Draw(ov)
            dr.rectangle(best[1], outline=(255, 40, 40), width=4)
            ov.save(sdir / f"{v['name']}_det.png")
            cl = np.zeros(len(dots), bool)
            ui = u[inb].astype(np.int64)
            vi = vv2[inb].astype(np.int64)
            cl[np.nonzero(inb)[0]] = mask[vi, ui]
            info["why"] = f"ok({best[0]:.2f})"
            info["claimed"] = int(cl.sum())
            out.append((cl, info))
            print(f"[vote] {vname} ok({best[0]:.2f}) claims "
                  f"{int(cl.sum())}/{len(dots)}", flush=True)
        return out

    # ---- TIER 1: context cards at object height ----
    jobs = ctx_render_jobs(views[:4])
    tf = sdir / f"votetgt_{nid}.json"
    tf.write_text(json.dumps([views[4]], indent=1))  # clean slice34
    render_gate(views[4], CULL_SLICE, 0.0, slice_mask)
    jobs.append((tf, plyp, False))
    run_renders(jobs)
    card_res = card_votes(views[:4])
    tiers = ["context"]

    # ---- TIER 2: eye-height escalation (user design 2026-08-07) ----
    # Marble scenes are biased toward eye-height capture: splat quality
    # and the detector are both strongest from eye-height viewpoints.
    # When MOST object-height cardinals are unproductive (>=3 of 4 with
    # no detection or <50 claimed dots), add 4 eye-height cardinals
    # (same tunnel vote) as EXTRA voters.
    productive = sum(1 for cl, inf in card_res
                     if cl is not None and inf.get("claimed", 0) >= 50)
    if productive <= 1:
        tiers.append("eyeheight")
        print("[vote]  escalate: eye-height cardinals", flush=True)
        eye_y = max(CEIL + WALL_PAD, FLOOR - 1.6)
        eviews = []
        for k, base in enumerate([np.array([1.0, 0, 0]),
                                  np.array([-1.0, 0, 0]),
                                  np.array([0, 0, 1.0]),
                                  np.array([0, 0, -1.0])]):
            dirv = roty(base, OFF_AXIS)
            eeye = ctr + dirv * dist
            eeye = eeye.copy()
            eeye[1] = eye_y
            eviews.append({"name": f"vote_{nid}_eyecard{k}",
                           "label": f"{nid} {name} eyecard{k}",
                           "eye": [float(x) for x in eeye],
                           "aim": [float(x) for x in ctr],
                           "fov": FOV_GOOD})
        run_renders(ctx_render_jobs(eviews))
        card_res = card_res + card_votes(eviews)
    # ---- v4: the TOP view votes too (its SAM mask on the plan render)
    tcl, tinfo = None, None
    if top_ctx is not None:
        tcam, tb, timg, tvname, tscore, teye_v = top_ctx
        tmask = sam_mask(timg, tb, DIL_ISO)
        ovt = timg.convert("RGBA")
        layer = Image.new("RGBA", ovt.size, (0, 0, 0, 0))
        px = layer.load()
        ys, xs = np.nonzero(tmask)
        for yy, xx in zip(ys[::4], xs[::4]):
            px[int(xx), int(yy)] = (0, 255, 90, 100)
        ovt = Image.alpha_composite(ovt, layer).convert("RGB")
        ImageDraw.Draw(ovt).rectangle(tb, outline=(255, 40, 40), width=4)
        ovt.save(sdir / f"vote_{nid}_top_det.png")
        u, vv2, z = tcam.project(dots)
        inb = ((z > 0.05) & (u >= 0) & (u < RES - 1)
               & (vv2 >= 0) & (vv2 < RES - 1))
        cl = np.zeros(len(dots), bool)
        ui = u[inb].astype(np.int64)
        vi = vv2[inb].astype(np.int64)
        cl[np.nonzero(inb)[0]] = tmask[vi, ui]
        tcl = cl
        tinfo = {"view": "top", "why": f"ok({tscore:.2f})",
                 "eye": [float(v) for v in teye_v],
                 "claimed": int(cl.sum())}
        print(f"[vote] top   ok({tscore:.2f}) claims "
              f"{int(cl.sum())}/{len(dots)}", flush=True)
    # ---- v4: the ORIGINAL standpoint votes too (union of pano masks)
    ocl = np.zeros(len(dots), bool)
    n_msk = 0
    for fid in n.get("members", []):
        fo = f30_by_id.get(fid)
        if not fo:
            continue
        for mi in fo.get("members", []):
            if mi >= len(pool_j):
                continue
            m = pool_j[mi]
            mk = pano_mask(m)
            if mk is None:
                continue
            mkd = ndimage.binary_dilation(mk, iterations=6)
            cam0 = view_cam0(m["view"])
            hh, ww = mkd.shape
            u, vv2, z = cam0.project(dots)
            inb = ((z > 0.05) & (u >= 0) & (u < ww - 1)
                   & (vv2 >= 0) & (vv2 < hh - 1))
            hit = np.zeros(len(dots), bool)
            ui = u[inb].astype(np.int64)
            vi = vv2[inb].astype(np.int64)
            hit[np.nonzero(inb)[0]] = mkd[vi, ui]
            ocl |= hit
            n_msk += 1
    oinfo = None
    if n_msk:
        oinfo = {"view": "sp0-original",
                 "why": f"{n_msk} pano mask(s)",
                 "eye": [float(v) for v in eye0],
                 "claimed": int(ocl.sum())}
        print(f"[vote] sp0   {n_msk} masks   claims "
              f"{int(ocl.sum())}/{len(dots)}", flush=True)

    # ---- ELECTION (assemble + tally; re-runnable for tier 3) ----
    def assemble(card_res_):
        cls, inf = [], []
        for cl, i in card_res_:
            i = dict(i)
            if cl is not None:
                cls.append(cl)
                i["idx"] = len(cls) - 1
            inf.append(i)
        if tcl is not None:
            ti = dict(tinfo)
            cls.append(tcl)
            ti["idx"] = len(cls) - 1
            inf.append(ti)
        if oinfo is not None:
            oi = dict(oinfo)
            cls.append(ocl)
            oi["idx"] = len(cls) - 1
            inf.append(oi)
        return cls, inf

    def tally(cls):
        # USER 2026-08-06 late: 3-vote gate; degrades only when fewer
        # voters exist
        n = len(cls)
        vts = (np.sum(cls, axis=0).astype(np.int64) if cls
               else np.zeros(len(dots), np.int64))
        vts[~elig] = 0   # shell electorate filter (user 2026-08-07)
        need = min(a.gate, n) if n else 1
        p_and, _ = (fragments_box(dots[vts == n], lo0, hi0)
                    if n else (None, []))
        p_v2, frags = fragments_box(dots[vts >= need], lo0, hi0)
        win = np.zeros(len(dots), bool)
        if p_v2 is not None:
            win[np.nonzero(vts >= need)[0][p_v2["mask"]]] = True
        return n, vts, need, p_and, p_v2, frags, win

    claims, infos = assemble(card_res)
    (n_ok, votes, need_votes,
     prim_and, prim_v2, frags_v2, win_blob) = tally(claims)

    # ---- TIER 3: isolation retry (user-approved 2026-08-07) ----
    # Election still empty -> re-render the object-height cards with the
    # slice ALONE on black (run-1 mode, proven on small objects like the
    # book) and re-elect with the extra voters. Only after this can the
    # original box ship.
    if prim_v2 is None:
        tiers.append("isolation")
        print("[vote]  escalate: isolation retry (slice on black)",
              flush=True)
        iviews = [{"name": f"vote_{nid}_iso{k}",
                   "label": f"{nid} {name} iso{k}",
                   "eye": views[k]["eye"], "aim": views[k]["aim"],
                   "fov": FOV_GOOD} for k in range(4)]
        itf = sdir / f"votetgt_{nid}_iso.json"
        itf.write_text(json.dumps(iviews, indent=1))
        for _iv in iviews:
            render_gate(_iv, CULL_SLICE, 0.0, slice_mask)
        run_renders([(itf, plyp, False)])
        card_res = card_res + card_votes(iviews)
        claims, infos = assemble(card_res)
        (n_ok, votes, need_votes,
         prim_and, prim_v2, frags_v2, win_blob) = tally(claims)
    rule_flag = ""
    if frags_v2:
        biggest = max(frags_v2, key=lambda f: f["n_pts"])
        if biggest is not prim_v2:
            rule_flag = (f"anchored cluster ({prim_v2['n_pts']} pts) is "
                         f"not the biggest ({biggest['n_pts']} pts)")
    # ---- PANO-MASK FILTER (⚠ UNTESTED, user option-2 2026-08-06): multi-
    # node structures (L-sectional) share one vote cluster, so every
    # sibling node wraps the whole L. Each node keeps only the vote
    # survivors ITS OWN pano masks vouch for. Guard: falls back to
    # the cluster box when sp0 coverage of the survivors is too thin
    # (junk pano masks must not starve the node).
    prim_pano, pano_flag = None, ""
    if n_msk and prim_v2 is not None:
        # winning blob only (user ruling 2026-08-07 late): culled-blob
        # dots must not leak into the share comparison
        panok = win_blob & ocl
        if (panok.sum() >= 200
                and panok.sum() >= 0.10 * max(1, int(win_blob.sum()))):
            lo_a = np.percentile(dots[panok], 1, axis=0)
            hi_a = np.percentile(dots[panok], 99, axis=0)
            prim_pano = {"lo": lo_a, "hi": hi_a, "n_pts": int(panok.sum())}
            va = np.prod(np.maximum(hi_a - lo_a, 1e-6))
            vv = np.prod(np.maximum(
                np.array(prim_v2["hi"]) - np.array(prim_v2["lo"]), 1e-6))
            if va < 0.5 * vv:
                pano_flag = ("pano-filtered box is <50% of the cluster box "
                             "volume — possible multi-node structure (L?); "
                             "multiplicity judge territory")
        else:
            pano_flag = ("sp0 coverage too thin — pano-mask filter falls "
                         "back to cluster")
    # OUTLIER GUARD (user rule 2026-08-06b): a repair may refine, never
    # explode — if the box that would ship is > OUTLIER_K x the original
    # resolved volume, the original ships instead (kept_outlier). The
    # oversized vote box stays recorded (honest fallback, judge fodder).
    outlier_flag = ""
    _fin = prim_pano if prim_pano is not None else prim_v2
    if _fin is not None:
        _vf = np.prod(np.maximum(
            np.array(_fin["hi"]) - np.array(_fin["lo"]), 1e-6))
        _vo = np.prod(np.maximum(hi0 - lo0, 1e-6))
        if _vf > OUTLIER_K * _vo:
            outlier_flag = (f"voted box is {_vf/_vo:.0f}x the original "
                            f"volume (> {OUTLIER_K:.0f}x) — outlier "
                            "guard: original box ships, vote box "
                            "recorded as doubt")
    # PLAN-FILL (user rule 3, 2026-08-07 — adopted from the scene-wide
    # census: natural break 0.58 | 0.73, threshold 0.65 in open water):
    # elected dots' 10 cm-voxel footprint coverage of the vote box. Low
    # fill = the dots don't cover their own footprint — non-box shape
    # (L-sectional) or sparse giant. Recorded here; the doubt fires in
    # record_vote_doubts.py; the split-cell judge rules.
    plan_fill = None
    if prim_v2 is not None:
        _el = dots[votes >= need_votes]
        if len(_el):
            _lo2 = np.array(prim_v2["lo"]); _hi2 = np.array(prim_v2["hi"])
            _g = np.floor((_el[:, [0, 2]] - _lo2[[0, 2]]) / 0.10)
            _occ = len(set(map(tuple, _g.astype(np.int64))))
            _tot = int(np.prod(np.maximum(
                np.ceil((_hi2 - _lo2)[[0, 2]] / 0.10), 1)))
            plan_fill = round(min(_occ / max(_tot, 1), 2.0), 3)
    # PLAN-FILL v2 (2026-08-07 late; NOT the doubt trigger yet — recorded
    # for the offline k-sweep recalibration queued in R-S2-34's run-5
    # addendum): winning-blob dots only, cells clipped to the vote-box
    # footprint (true 0-1 fill), per-cell dot counts recorded so k (min
    # dots for an occupied cell) + threshold calibrate on one run's
    # full-data distribution.
    plan_fill2, plan_cells = None, None
    if prim_v2 is not None and win_blob.any():
        _wb = dots[win_blob]
        _lo2 = np.array(prim_v2["lo"]); _hi2 = np.array(prim_v2["hi"])
        _nx, _nz = (int(v) for v in np.maximum(
            np.ceil((_hi2 - _lo2)[[0, 2]] / 0.10), 1))
        _g = np.floor((_wb[:, [0, 2]] - _lo2[[0, 2]]) / 0.10).astype(
            np.int64)
        _in = ((_g[:, 0] >= 0) & (_g[:, 0] < _nx)
               & (_g[:, 1] >= 0) & (_g[:, 1] < _nz))
        _cells, _cnt = (np.unique(_g[_in], axis=0, return_counts=True)
                        if _in.any() else (np.empty((0, 2), np.int64),
                                           np.empty(0, np.int64)))
        plan_fill2 = round(len(_cells) / max(_nx * _nz, 1), 3)
        plan_cells = {"cell_m": 0.10, "nx": _nx, "nz": _nz,
                      "counts": [[int(cx), int(cz), int(c)]
                                 for (cx, cz), c in zip(_cells, _cnt)]}
        print(f"[vote]  plan_fill {plan_fill} | v2 {plan_fill2}",
              flush=True)
    ur = ("empty" if prim_v2 is None else
          " x ".join(f"{prim_v2['hi'][i]-prim_v2['lo'][i]:.2f}"
                     for i in range(3)))
    ua = ("" if prim_pano is None else
          "  pano " + " x ".join(
              f"{prim_pano['hi'][i]-prim_pano['lo'][i]:.2f}"
              for i in range(3)))
    print(f"[vote]  VOTE ≥{need_votes} of {n_ok}: {ur} m{ua}"
          + (f"  (culled {len(frags_v2)-1})" if len(frags_v2) > 1 else "")
          + (f"  ⚠ {rule_flag}" if rule_flag else "")
          + (f"  ⚠ {pano_flag}" if pano_flag else "")
          + (f"  ⚠ {outlier_flag}" if outlier_flag else ""), flush=True)

    # ---- figure ----
    Pc = dots[votes >= need_votes]
    wbase = Pc if len(Pc) >= 50 else dots
    wlo = np.minimum(np.percentile(wbase, 0.5, axis=0), lo0) - 0.4
    whi = np.maximum(np.percentile(wbase, 99.5, axis=0), hi0) + 0.4
    inw = np.all((dots >= wlo) & (dots <= whi), axis=1)
    Pw, votes_w = dots[inw], votes[inw]
    minis = [i for i in infos if "idx" in i]
    ncols = max(3, len(minis))
    fig, axes = plt.subplots(2, ncols, figsize=(4.2 * ncols, 9))
    fig.suptitle(f"{nid}  \u201c{name}\u201d \u2014 v3 slice+vote "
                 f"({slice_info}; {n_ok} cardinals)", fontsize=15)
    projs = [("plan view (from above)", 0, 2, False),
             ("front (x vs height)", 0, 1, True),
             ("side (z vs height)", 2, 1, True)]
    vmax = max(1, n_ok)
    for k in range(ncols):
        for r in (0, 1):
            axes[r, k].set_aspect("equal")
    for k, (title, a0, a1, flip) in enumerate(projs):
        ax = axes[0, k]
        y = -Pw[:, a1] if flip else Pw[:, a1]
        sc = ax.scatter(Pw[:, a0], y, c=votes_w, cmap="viridis", vmin=0,
                        vmax=vmax, s=2, alpha=0.7)
        ax.set_xlim(wlo[a0], whi[a0])
        ax.set_ylim((-whi[a1], -wlo[a1]) if flip else (wlo[a1], whi[a1]))
        draw_box(ax, lo0, hi0, a0, a1, "#888888", "--", 1.5,
                 "original box", flip)
        if prim_and is not None:
            draw_box(ax, prim_and["lo"], prim_and["hi"], a0, a1,
                     "#d62728", "-", 2.2, "ALL cardinals", flip)
        if prim_v2 is not None:
            draw_box(ax, prim_v2["lo"], prim_v2["hi"], a0, a1,
                     "#ff9900", "-", 1.6,
                     f"\u2265{need_votes} votes (anchored)", flip)
        if prim_pano is not None:
            draw_box(ax, prim_pano["lo"], prim_pano["hi"], a0, a1,
                     "#00bcd4", "-", 1.8, "pano-filtered (pano-mask "
                     "survivors)", flip)
        ax.set_title(title, fontsize=11)
        if k == 0:
            ax.legend(fontsize=8, loc="upper right")
    for k in range(len(projs), ncols):
        axes[0, k].axis("off")
    cbar = fig.colorbar(sc, ax=axes[0, :].tolist(), shrink=0.8,
                        ticks=range(vmax + 1), pad=0.01)
    cbar.set_label("cameras claiming the dot (4 cardinals + top + orig)")
    for k, info in enumerate(minis):
        ax = axes[1, k]
        cl = claims[info["idx"]][inw]
        colr = VIEW_COLORS.get(info["view"], "#000000")
        ax.scatter(Pw[~cl, 0], Pw[~cl, 2], c="#dddddd", s=2)
        ax.scatter(Pw[cl, 0], Pw[cl, 2], c=colr, s=2)
        ex_, ez_ = info["eye"][0], info["eye"][2]
        ax.annotate("", xy=(ctr[0], ctr[2]), xytext=(ex_, ez_),
                    arrowprops=dict(arrowstyle="->", color=colr, lw=1.6))
        ax.plot([ex_], [ez_], "o", color=colr, markersize=7)
        ax.set_title(f"{info['view']}  {info['why']}\n"
                     f"claims {info.get('claimed', 0)}/{len(dots)} dots",
                     fontsize=10)
    for k in range(len(minis), ncols):
        axes[1, k].axis("off")
    fig_path = rdir / f"conemap_{nid}.png"
    fig.savefig(fig_path, dpi=110, bbox_inches="tight")
    plt.close(fig)

    # ---- viewer export ----
    rng = np.random.default_rng(0)
    sub = (np.arange(len(dots)) if len(dots) <= 12000 else
           np.sort(rng.choice(len(dots), 12000, replace=False)))
    bits = np.zeros(len(dots), np.int64)
    for bi, cl in enumerate(claims):
        bits |= cl.astype(np.int64) << bi
    views_exp = [{"view": i["view"], "why": i["why"], "role": "",
                  "eye": i["eye"],
                  "color": VIEW_COLORS.get(i["view"], "#ffffff"),
                  "claimed": i.get("claimed")}
                 for i in infos if "idx" in i]
    bits |= np.ones(len(dots), np.int64) << len(claims)
    views_exp.append({"view": "slice", "why": slice_info, "role": "",
                      "eye": [float(v) for v in
                              (tcands[0][1] if tcands else eye0)],
                      "color": "#ff7f00", "claimed": int(len(dots))})

    def _box(prim):
        return (None if prim is None else
                {"lo": [round(float(v), 3) for v in prim["lo"]],
                 "hi": [round(float(v), 3) for v in prim["hi"]]})

    # TOP-VIEW FRAMING / TRUNCATION -> the rule record, so the doubts
    # writer and the judges see WHY a slice was measured the way it was.
    # top_det_truncated is ABSENT when the detection was clear of every
    # border (its presence is the flag).
    _topr = {}
    if top_frame_rec is not None:
        _topr["top_frame"] = top_frame_rec
    if top_shots_rec:
        _topr["top_shots"] = top_shots_rec
    # WHICH DETECTION THE RANKING CHOSE. top_choice_overruled_score is
    # TRUE when the chosen box was NOT the highest-scoring admitted one
    # — the obj_020 case, and the whole point of the ruling, so it is a
    # flag of its own rather than something a reader has to derive.
    if top_choice_rec is not None:
        _topr["top_choice"] = top_choice_rec
        _topr["top_choice_overruled_score"] = top_choice_overruled
    if top_trunc_rec is not None:
        _topr["top_det_truncated"] = top_trunc_rec["sides"]
        _topr["top_det_extend"] = top_trunc_rec

    cm_objects.append({
        "id": nid, "name": name, "aim": [float(v) for v in ctr],
        "nviews_vote": n_ok,
        "boxes": {"original": {"lo": [round(float(v), 3) for v in lo0],
                               "hi": [round(float(v), 3) for v in hi0]},
                  "strict": _box(prim_and), "vote2": _box(prim_v2),
                  "pano": _box(prim_pano)},
        "rule": {"need_votes": need_votes, "flag": rule_flag,
                 "pano_flag": pano_flag, "outlier": outlier_flag,
                 "tiers": tiers,
                 "culled_clusters": max(0, len(frags_v2) - 1),
                 "shell_ineligible_dots": n_shell_dots,
                 "plan_fill": plan_fill,
                 "plan_fill2": plan_fill2, "plan_cells": plan_cells,
                 "slice": slice_info, **_topr},
        "views": views_exp,
        "points": {"pos": [round(float(v), 3)
                           for v in dots[sub].reshape(-1)],
                   "votes": votes[sub].astype(int).tolist(),
                   "bits": bits[sub].astype(int).tolist()}})

    # ---- html row ----
    sz = lambda b: " x ".join(f"{b['hi'][i]-b['lo'][i]:.2f}" for i in range(3))  # noqa: E731
    stats = [f"original box: "
             f"{' x '.join(f'{v:.2f}' for v in geo['size'])} m",
             f"slice: {len(dots):,} dots ({slice_info})"]
    if prim_v2 is not None:
        stats.append(f"vote box (\u2265{need_votes} of {n_ok}, anchored): "
                     f"{sz(prim_v2)} m"
                     + (f" (+{len(frags_v2)-1} culled)"
                        if len(frags_v2) > 1 else ""))
    else:
        stats.append("vote box: (empty)")
    if prim_and is not None:
        stats.append(f"ALL-cardinals box: {sz(prim_and)} m")
    if rule_flag:
        stats.append(f"\u26a0 FLAG: {rule_flag}")
    if outlier_flag:
        stats.append(f"\u26a0 OUTLIER: {outlier_flag}")
    if len(tiers) > 1:
        stats.append("escalated: " + " \u2192 ".join(tiers))
    strip = ""
    f34 = sdir / f"vote_{nid}_slice34.png"
    if f34.exists():
        strip += (f"<figure><img src='pool_retake/slices/{f34.name}' "
                  f"loading='lazy'><figcaption>THE SLICE · clean 3/4 "
                  f"view ({len(dots):,} dots)</figcaption></figure>")
    ftop = sdir / f"vote_{nid}_top_det.png"
    if ftop.exists():
        strip += (f"<figure><img src='pool_retake/slices/{ftop.name}' "
                  f"loading='lazy'><figcaption>TOP VOTER · plan render, "
                  f"its mask+box</figcaption></figure>")
    for fsp in sorted(rdir.glob(f"conemap_sp0_{nid}_*.png")):
        strip += (f"<figure><img src='pool_retake/{fsp.name}' "
                  f"loading='lazy'><figcaption>ORIGINAL VOTER · sp0 "
                  f"pano mask</figcaption></figure>")
    for i in infos:
        vn = i["view"]
        if vn in ("top", "sp0-original"):
            continue
        f = sdir / f"vote_{nid}_{vn}_det.png"
        f2 = sdir / f"vote_{nid}_{vn}.png"
        src = f.name if f.exists() else (f2.name if f2.exists() else None)
        if src:
            strip += (f"<figure><img src='pool_retake/slices/{src}' "
                      f"loading='lazy'><figcaption>{vn} "
                      f"\u00b7 {i.get('why', '?')}</figcaption></figure>")
    save_row(nid, "vote", f"""
<section>
<h2>{nid} \u2014 {name}</h2>
<p>{' &nbsp;\u00b7&nbsp; '.join(stats)}</p>
<img class='big' src='pool_retake/{fig_path.name}'>
<div class='strip'>{strip}</div>
</section>""")

# ===================== MERGE ON WRITE + PROVENANCE ====================
# (partial-runs-first restructure, user order 2026-08-08). A run that
# processed a SUBSET must repair the whole-scene documents, not replace
# them: load what is on disk, swap in only the ids this run produced,
# keep everyone else VERBATIM, emit in RESOLVED-NODE ORDER. Provenance
# stamps are what make that honest — every entry says which build and
# which constants made it, and the header says out loud when they differ.
PROCESSED_SET = set(PROCESSED_IDS)


def _load_list(path, listkey):
    """Existing document's entry list, or [] with a spoken reason."""
    if not path.exists():
        print(f"[vote] merge: {path.name} absent — writing THIS RUN'S "
              "entries only", flush=True)
        return []
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
        lst = doc.get(listkey)
        if not isinstance(lst, list):
            raise ValueError(f"no '{listkey}' list")
        return lst
    except Exception as e:                                   # noqa: BLE001
        print(f"[vote] merge: {path.name} corrupt/unreadable ({e}) — "
              "writing THIS RUN'S entries only", flush=True)
        return []


def merge_entries(path, listkey, run_entries):
    """Replace only this run's ids, drop nothing else, order by node."""
    old = _load_list(path, listkey)
    fresh = {o["id"]: o for o in run_entries}
    merged = {}
    for o in old:
        oid = o.get("id")
        # a PROCESSED id is this run's to say — its old entry goes even
        # when the run produced none for THIS document (an object that
        # turned vote-exempt has no conemap entry any more)
        if oid is None or oid in PROCESSED_SET:
            continue
        merged[oid] = o
    merged.update(fresh)
    out = sorted(merged.values(),
                 key=lambda o: (ALL_RANK.get(o["id"], len(ALL_IDS)),
                                o["id"]))
    print(f"[vote] merge {path.name}: {len(fresh)} from this run + "
          f"{len(out) - len(fresh)} kept verbatim = {len(out)} entries",
          flush=True)
    return out


def prov_stats(entries):
    """(mixed?, {source_sha: [ids]}) over a merged entry list. An entry
    with no stamp counts as its own provenance ('unstamped') — a
    pre-provenance document mixed with fresh entries IS mixed."""
    summ, phs = {}, set()
    for o in entries:
        p = o.get("prov") if isinstance(o.get("prov"), dict) else {}
        summ.setdefault(p.get("source_sha") or "unstamped",
                        []).append(o["id"])
        phs.add(p.get("params_hash") or "unstamped")
    return (len(summ) > 1 or len(phs) > 1), summ


def prov_header(entries):
    """The document header's provenance block. STATUS SEMANTICS: the
    status string stays 'UNTESTED-PREVIEW'; canon_eligible is the
    machine-readable "one build, whole scene" test — a partial OR mixed
    document is explicitly NOT canon."""
    mixed, summ = prov_stats(entries)
    return {"run_kind": RUN_KIND, "run_id": RUN_ID, "run_at": RUN_AT,
            "run_ids": list(PROCESSED_IDS),
            "params_hash": PARAMS_HASH, "source_sha": SOURCE_SHA,
            "mixed_provenance": mixed, "provenance_summary": summ,
            "canon_eligible": (RUN_KIND == "full" and not mixed)}


# ---- stamp everything this run produced -----------------------------
for _o in cm_objects:
    _o["prov"] = dict(PROV)
for _kc in kept_exempt:
    _kc["prov"] = dict(PROV)

# ---- conemap.json (voted objects only) ------------------------------
# written BEFORE the shell clip below, exactly as before: the cone-map
# layer carries the unclipped evidence boxes.
cm_path = rdir / "conemap.json"
cm_merged = merge_entries(cm_path, "objects", cm_objects)
cm_path.write_text(json.dumps({"scene": SCENE, **prov_header(cm_merged),
                               "objects": cm_merged}), encoding="utf-8")

# ---- PREVIEW manifest + report (⚠ UNTESTED promotion) ----
objs = []
for o in cm_objects:
    if o["rule"].get("outlier"):
        box, status = o["boxes"]["original"], "kept_outlier"
    else:
        box = (o["boxes"].get("pano") or o["boxes"].get("vote2")
               or o["boxes"]["original"])
        status = ("voted_pano" if o["boxes"].get("pano")
                  else ("voted" if o["boxes"].get("vote2") else "kept"))
    # SHELL CLIP (step 6): only the box that SHIPS is clipped — the
    # original/vote2/pano boxes above stay recorded unclipped (evidence)
    ship = ship_box(box["lo"], box["hi"], o["rule"])
    o["boxes"]["shipping"] = ship
    lo, hi = ship["lo"], ship["hi"]
    flags = [status] + [f for f in (o["rule"]["flag"],
                                    o["rule"]["pano_flag"],
                                    o["rule"].get("outlier", "")) if f]
    objs.append({"id": o["id"],
                 "label": o["name"] + f" ({status} "
                          f"{o['rule']['need_votes']}v/"
                          f"{o['nviews_vote']})",
                 "score": 1.0, "aabb_min": lo, "aabb_max": hi,
                 "center": [round((x + y) / 2, 4)
                            for x, y in zip(lo, hi)],
                 "size": [round(y - x, 4) for x, y in zip(lo, hi)],
                 "n_detections": 1, "views": [], "flags": flags,
                 "prov": dict(PROV)})
for kc in kept_exempt:
    b = kc["boxes"].get("shipping") or kc["boxes"]["original"]
    lo, hi = b["lo"], b["hi"]
    objs.append({"id": kc["id"],
                 "label": kc["name"] + f" ({kc['status']})",
                 "score": 1.0, "aabb_min": lo, "aabb_max": hi,
                 "center": [round((x + y) / 2, 4)
                            for x, y in zip(lo, hi)],
                 "size": [round(y - x, 4) for x, y in zip(lo, hi)],
                 "n_detections": 1, "views": [],
                 "flags": [kc["status"], kc["rule"]["kept"]],
                 "prov": dict(PROV)})
man_path = sd / "scene_manifest_slicevote_preview.json"
man_objs = merge_entries(man_path, "objects", objs)
# by_status now describes the MERGED document, not just this run
by_status = {}
for _mo in man_objs:
    _s = (_mo.get("flags") or ["?"])[0]
    by_status[_s] = by_status.get(_s, 0) + 1
man_path.write_text(json.dumps(
    {"scene": SCENE, "status": "UNTESTED-PREVIEW",
     "source": "slicevote.py — slice-vote election (top-box prism / "
               "wedge fallback; view-tunnel context cards; 6-voter "
               f"election, gate {a.gate}; per-node pano-mask filter; "
               "ceiling / wall-protrusion / floor-flush exempt = "
               "kept_ceiling/kept_wall/kept_floor, wall+ceiling exempts "
               "re-boxed IN-PLANE from one perpendicular face-on view; "
               "outlier guard "
               f"{OUTLIER_K:.0f}x = kept_outlier; every shipped box "
               "clipped to the measured shell interior). "
               "Preview only; not on the pipeline map.",
     **prov_header(man_objs),
     "frame": {"space": "raw", "up": [0.0, -1.0, 0.0]},
     "n_objects": len(man_objs), "objects": man_objs}, indent=2))

rep_path = rdir / "slicevote_report.json"
results = merge_entries(rep_path, "results",
                        [{k: o[k] for k in ("id", "name", "nviews_vote",
                                            "boxes", "rule", "prov")}
                         for o in cm_objects] + kept_exempt)
rep_path.write_text(json.dumps(
    {"scene": SCENE, "stage": "slicevote",
     "status": "UNTESTED-PREVIEW", "gate": a.gate,
     **prov_header(results),
     "params": dict(PARAMS, FOV_GOOD=FOV_GOOD, OFF_AXIS=OFF_AXIS),
     "by_status": by_status,
     "results": results}, indent=1))

# ---- cone_map.html: COMPLETE under partial runs ----------------------
# rows come from the per-object sidecars, read for ALL resolved ids in
# node order — this run's were just rewritten, everyone else's are the
# ones on disk (whose pictures the scoped wipe deliberately spared).
exempt_frag = "".join(read_row(_i, "exempt") for _i in ALL_IDS)
vote_frag = "".join(read_row(_i, "vote") for _i in ALL_IDS)
exempt_list = [e for e in results
               if isinstance(e.get("rule"), dict) and "kept" in e["rule"]]
_mixed, _summ = prov_stats(results)
_others = {s: len(v) for s, v in _summ.items() if s != SOURCE_SHA}
# STALE = BADGED, NEVER HIDDEN (project convention): a mixed page shows
# every row and says in one line how many came from an older build.
prov_banner = ("" if not _mixed else
               "<p style='background:#fff4d6;border:1px solid #d9a900;"
               "padding:8px 10px;font-size:13px'><b>&#9888; MIXED "
               f"PROVENANCE</b> &mdash; {sum(_others.values())} of "
               f"{len(results)} objects on this page were produced by an "
               "EARLIER build ("
               + "; ".join(f"source_sha {s}: {n}"
                           for s, n in sorted(_others.items()))
               + f"); {len(_summ.get(SOURCE_SHA, []))} came from this "
               f"{RUN_KIND} run {RUN_ID} (source_sha {SOURCE_SHA}, "
               f"params_hash {PARAMS_HASH}). Nothing is hidden &mdash; "
               "re-run the full vote to make this page canon.</p>")

html = f"""<!doctype html><meta charset='utf-8'>
<title>v3 slice+vote \u2014 {SCENE}</title>
<style>
body{{font-family:system-ui,sans-serif;margin:24px;background:#fafafa}}
h1{{font-size:20px}} h2{{font-size:16px;margin:28px 0 4px}}
img.big{{max-width:100%;border:1px solid #ccc;background:#fff}}
.strip{{display:flex;gap:8px;overflow-x:auto;margin-top:8px}}
.strip figure{{margin:0;flex:0 0 auto}}
.strip img{{height:190px;border:1px solid #ccc}}
.strip figcaption{{font-size:11px;max-width:200px}}
p{{font-size:13px}}
</style>
<h1>v3 slice + vote \u2014 {SCENE}</h1>
{prov_banner}
<p>DESIGN (updated 2026-08-08): slice = top-box vertical prism (capped
margin; fallback = original-box wedge) \u2192 each card rendered by the
real WSL renderer as the FULL SCENE minus WHAT IS IN FRONT OF THE
OBJECT (gaussians inside the camera cone nearer than the object box's
nearest corner minus 0.05 m are culled; the object and every
surrounding that is not blocking the view \u2014 wall, floor, the room
behind \u2014 stay in the picture, which is what segmentation needs; the
card renders are DECOUPLED from the slice, which now only decides who
may be claimed; re-detect still gated to the slice's screen
footprint) \u2192 detector+SAM per render \u2192 6-voter election. Boxes: gray
dashed = original, red = all cardinals agree, orange = the vote gate,
cyan = pano-filtered. Ceiling-mounted, wall-protruding (touches a wall
plane and protrudes ≤ 0.20 m into the room) and floor-flush objects
are VOTE-EXEMPT (geometric tests) and keep their resolved box; a
voted box growing past the outlier guard (8x original volume) also
falls back to the original (kept_outlier), with the vote box recorded
as doubt. Every SHIPPING box is finally clipped to the measured shell
interior (strictly external volume booleaned out); the boxes drawn
here are the unclipped evidence.</p>
{("<p><b>vote-exempt (resolved box kept):</b> "
  + ", ".join(f"{e['id']} {e['name']} [{e['status']}]"
              for e in exempt_list) + "</p>")
 if exempt_list else ""}
{("<p>WALL / CEILING exempt objects additionally get a PERP RE-BOX (user "
  "design 2026-08-07): one face-on view-tunnel render perpendicular to "
  "their own plane, detector+SAM, and the mask's claimed slab dots set "
  "the two IN-PLANE extents (the normal axis is untouched — a face-on "
  "view cannot see depth). Guards: a candidate whose in-plane center "
  f"moves &gt; {PERP_MAX_SHIFT:.1f} m or whose extent changes by more "
  f"than {PERP_MAX_RATIO:.0f}x is recorded and REJECTED, original ships. "
  "Their rows are below.</p>" + exempt_frag)
 if exempt_frag else ""}
{vote_frag}
"""
(sd / "cone_map.html").write_text(html, encoding="utf-8")
_hdr = prov_header(results)
print(f"[vote] statuses {by_status}; run_kind={RUN_KIND} "
      f"mixed_provenance={_hdr['mixed_provenance']} "
      f"canon_eligible={_hdr['canon_eligible']}; wrote cone_map.html "
      f"+ conemap.json + scene_manifest_slicevote_preview.json "
      f"+ slicevote_report.json (⚠ UNTESTED-PREVIEW)", flush=True)
