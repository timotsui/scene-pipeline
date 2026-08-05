# PLAN — PH2 FIT LOOP (physical fitting; design started 2026-08-03B)

## Module contract (draft, from the stage-entry discussion)

- **Gets:** compose/picks.json `final_candidates` (the k=3 style-ranked
  candidates per anchor box — THE semantic→physical handoff baton),
  the measured room shell, real asset meshes (yaw-canonicalized), the
  64 deferred subs grouped per anchor.
- **Decides:** for every box, WHICH of its 3 candidates actually
  stands in the room, and its final pose. First stage where real
  meshes replace boxes as the scene's truth.
- **A mistake looks like:** a placement accepted that looks wrong in
  renders, an item silently dropped when its 3 candidates run dry, or
  a verdict that resizes/re-styles instead of moving to the next
  candidate.

## Stage position (user ruling 08-03B)

Fit loop = **PH2 in 3.2 PHYSICAL** (map redrawn; was S5 in semantic).
With k=3 the WHAT is decided upstream — choosing among 3 pre-approved
candidates is a tiebreak; the loop's real work is mesh placement.
Collide gate = PH3, box surgery = PH4.

## Rulings so far (08-03B)

1. **ROTATION CHECK FIRST.** Rotation is corrected BEFORE candidate
   evaluation — every candidate is judged at its best rotation, so a
   good product is never rejected for standing backwards.
2. **FREE SPIN.** The check offers arbitrary yaw — not cardinal-only.
   (Current strips use 45° steps as the question granularity.)
3. Two-layer design: **geometric pre-spin** (the facing evidence
   ladder in fit_preview — free, 26/30 on this room) + a **judged
   visual check** (the orientation last pass; per-category rules
   banned). Skip the judge where geometry fully constrains facing
   (wall-mounted); judge only free-standing / heuristic / conflict
   items — effort follows error cost.
4. Candidates arrive NATIVE SIZE. Open: is no-rescale absolute in the
   loop too, or is stretch a last resort?

## CANON 2026-08-04 (evening) — PHYSICAL PLACEMENT RULES (user: "this
## is correct. this is canon.")

All in compose/fit_preview.py + compose/fit_check.py, live in the
preview and the viewer's fit / fit-check views:

1. **FIT TARGET = SNAPPED BOX.** Meshes place into snap.json's
   adjudicated `snapped_aabb` (observed graph box = record only;
   invented adds/swaps keep proposal boxes). The bed stood 84 mm in
   the floor before this.
2. **MESH-FLUSH ATTACHMENT.** After placement the ACTUAL mesh face is
   pushed flush to its mount surface (floor: bottom; wall: back along
   the wall normal — doors were 171/80 mm off their walls; ceiling:
   top). No gravity anywhere: verticality is scene data (the box), the
   check only verifies attachment. Wall items whose box reaches the
   floor: bottom-align (door rule; parked, not yet coded).
3. **PCA CARDINAL SNAP (the obj_032 lesson).** Min-area rotated
   rectangle over the footprint hull; de-rotate the mesh's TRUE axes
   to cardinal before any footprint/facing logic (gated: only when the
   oriented rect is ≥5% tighter than the AABB and >1°). Caught 4/31
   assets baked crooked in-file (+30.7/+42.5/+30.2/+30.2°) — obj_032's
   "oversize +142%" was this artifact; true footprint 1.53×0.47 vs box
   1.55×0.47, an exact fit. Recorded per item as `pca_snap_deg`.
4. **ROTATION IS CARDINAL-ONLY.** Long axis (AABB, ELONG 1.2) aligns
   to the box's long axis; free small-yaw REJECTED by experiment
   (fit_rotate_test: its "wins" were walls items cocked 45° — metric
   gaming; fit_cardinal_test: 19/20 flagged items already at their
   best cardinal). Clipping is NOT in the rotation objective (user
   ruling) — rotation corrects axes, clip resolution is a later step.
5. **NO STRETCH, ruled.** Native size absolute; a short/oversized
   asset is a candidate problem (walk style #2/#3 → re-shop
   complaint), never a scale fix. (Door-height last-resort question
   stays parked.)
6. **FIT CHECK v1 (report-only).** compose/fit_check.py: bounds
   (vertex-exact vs shell planes, 5 mm tol) + pairwise clip (2 cm
   lattice voxels of the REAL meshes, AABB only as prune; ≤4 shared
   cells = contact). fit_check.json + viewer 'fit check' view (red
   OOB / orange clip / red wire overlap regions). After rules 1–5:
   3 OOB + 27 clip pairs remain, all honest (curtain height, obj_043
   depth, wardrobe size = true candidate problems; chair×desk overlap
   = judge-blessable contact).
7. **ROTATION APPLY GATE with measurement basis.** rotation_check
   verdicts record `measured_uid`; fit_preview applies HIGH-confidence
   non-zero verdicts ONLY when the placed asset uid matches — verdicts
   never transfer across assets. Also canon: the preview places
   picks.json style #1 (final_candidates), shopping size-fit #1 only
   as fallback.

## CANON 2026-08-04 (night) — DECLIP + STAGE REORDER (user)

8. **JIGGLE DECLIP (compose/fit_declip.py, user design "bounce away
   like a 3D game"):** position-based penetration resolution, static
   shell, PLANE CONSTRAINTS (floor/ceiling items move in the floor
   plane x/z; wall items move in their WALL plane — along-wall AND
   vertical, normal locked flush), items MAY leave their fit box (the
   box seeds, it does not cage; out_of_box_mm recorded), flat items
   (<6 cm) exempt as clip participants (rug rule), moves lattice-
   quantized (2 cm int key-shifts, no re-voxelization in the loop),
   verified after by an independent fit_check pass. First full run:
   0 OOB (curtain slid 140 mm down its wall plane — the ceiling poke
   resolved by the y freedom), residual clip mass = the true-oversize
   items only. Stage order: fit_preview → fit_declip → fit_check.
9. **DRY-LIST RULE (the wardrobe lesson):** if truly NOTHING fits
   within the margin (default = the 15% strict mark), the item goes
   BACK to what it was supposed to be: swaps revert to their out-items
   (swap_r3n1 wardrobe → bookshelf obj_023: every library wardrobe
   fails its clamped 0.33 m-deep envelope — the proposal box, not the
   library, was the lie), adds drop entirely, detections re-shop with
   an honest complaint (or stand flagged). Infeasible proposals DIE at
   fit time; that is the stage doing its job.
10. **ROTATION CHECK MOVED OUT OF THE LOOP (user reorder, "it is
   expensive"):** PH2a is set aside from the fit path — candidate
   walks and re-shops do NOT re-trigger it. It runs ONCE after the
   loop converges, on the final asset set. The measured_uid gate makes
   this safe automatically: stale verdicts are inert on new assets
   (uid mismatch), surviving assets keep their applied yaws
   (basis-carry). User will run the rotation check after.

## CANON 2026-08-04 (late night) — THE MECHANICAL LOOP IS COMPLETE
## (user: "oh shit. this is good. save to canon")

Loop = place → jiggle → check → WALK → repeat until dry; ran to dry on
bedroom_marble tonight (2 passes): 0 OOB, residuals = rug-class +
≤1.3 L contact grazes. All deterministic, ~1 min/cycle, no judge calls.

11. **CANDIDATE WALK (compose/fit_walk.py):** finding-implicated items
    whose current pick overshoots MARGIN 0.15 step down their style
    top-3 to the best-fitting sibling (GAIN 0.02); choices accumulate
    in fit_walk.json, fit_preview applies them (pick_source "walk");
    all-3-dry → complaint (obj_058 picture = first; policy for
    walking past the style 3 = OPEN). First run walked 5 (desk
    17→13%, obj_043 29→14%, obj_023 18→11%, baskets incl. 78→21%) —
    the 73 L desk×bookshelf collision vanished; jiggle then converged
    in 17 rounds because the wall row finally fits the wall
    (measured overfull before: 5.63 m of furniture on 4.34 m).
12. **WALK-BACK FEEDBACK (compose/fit_feedback.py, rule 9 coded):**
    items whose BEST candidate scores > DRY 0.65 (the measured gap:
    clamped swap envelopes 9.94/0.71 vs detections ≤0.61 — flagged
    constant, re-measure scene #2) write rejections shopping.py
    consumes: swaps revert to out-items, adds drop. Ran: BOTH
    invented swaps died (wardrobe + wall shelf, clamped-envelope
    disease), obj_017 picture + obj_023 bookshelf restored and shop
    at 6%/11%. Re-pick changed 12 assets → all old rotation verdicts
    correctly inert (uid gate); rule 10 covers the single closing
    rotation check.
13. **JIGGLE LOCKS refined (both user-spotted in the viewer):**
    (a) WALL-ADJACENCY LOCK: floor item starting within HUG_M 0.30 of
    a wall keeps that wall (normal axis frozen; slide-along free;
    corners pinned); shell push-back BYPASSES the lock (lock = "don't
    leave the wall", never "stay embedded in it"). (b) TUCKED-ITEM
    EXEMPTION: the lock holds only if the witness's observed facing
    agrees the item BACKS the wall — observed facing TOWARD the wall
    (the obj_000 desk chair) = tucked furniture, jiggles free.
14. **DUAL ATTACHMENT (the floating-door fix; user: "a door belongs
    to both a wall and a floor"):** attachment is a box-derived SET,
    not a single class — a wall item whose fit box reaches the floor
    (<0.10 m) is floor-standing: mesh bottom-aligned to the box
    bottom (never y-centered mid-air), y locked in the jiggle.
    Caught all 3 doors; recorded per item as `attachment`.

OPEN after tonight: closing rotation check (rule 10, user runs it) →
visual judge round vs refcam photos → obj_058-style walk-past-the-3
policy → sub rounds (the 64 deferred subs) → PH3 collide gate at
convergence. Map edits queued: fit_check/fit_declip/fit_walk/
fit_feedback nodes + PH2a repositioned outside the loop.
REFACTOR CANDIDATE (ratified direction, not urgent): unify the three
attachment mechanisms (judged mount / wall+floor dual attachment /
hug lock) into ONE box-derived attachment SET per item — every shell
surface the box touches — with all jiggle locks derived from it;
corners and ceiling-wall cabinets then fall out naturally.

## CANON v2, 2026-08-04 (later) — 4-CANDIDATE CHOICE, SAME CAMERA

**Supersedes the direct-ask ruling below** (user: "if we have something
that works and don't rely on the asset implied presets, let's just do
that"). One call per referenced object: the detection photograph (mirror
corrected, rose drawn) + FOUR SEPARATE full-size renders of the object
isolated in the test fit at 0/90/180/270°, all from the photo's own
camera, rose beside the object, neutral filenames — "which candidate
matches the real one?" Degrees = the pick's mapping, in code.

Why this form won, measured on the bed (the day's benchmark object,
GT 180° reconfirmed by image reading):
- **Comparison works where naming fails.** The judge misread the isolated
  render's facing 6/6 times under every prompt/framing/compass variant —
  but picked the correct 180° candidate first try (79 s, 6 turns).
  Choice never asks it to name the render's orientation.
- **No dependence on asset front semantics.** The day's root cause: the
  bed asset's canonical +z is its HEAD, while the scene-side pillow rule
  defines front = FOOT — a 180° semantic gap no existing check covers
  (the face_dot only verifies rotation math). The choice form is immune,
  and a pick that disagrees with the pose record's prediction FLAGS such
  assets automatically.
- Separate full-size images fixed what killed the 8-tile strip (judge
  zoom-tooling); the shared camera fixed cross-view transfer; the rose is
  read correctly (model spelled out the arrow geometry unprompted,
  matching the computed anchors exactly).

Fallbacks unchanged: swaps inherit the replaced object's photo with the
swap declared; strict adds keep the plausibility direct ask. QUEUED
library work (separate from this stage): ratify per-category front
semantics ("bed front = foot end"), store as a tag, flip this bed
asset's canonical yaw 180° via the fixup channel.

Mirror-corrected reference, stimulus-keyed reply cache (prompt + image
bytes), per-call clean folders, waves, measured costs — all as below.

**08-04 CLOSE-OUT MEASUREMENTS (user: small problem, stop here):**
(a) OBJECT-FRAMED CROP adopted (candidates cropped to projected box ∪
rose + 70 px; geometry-driven, uniform): wall 8.7→6.5 min, bed 180°
at HIGH confidence / 6 turns, 31/31 answered (ceiling-light timeout
gone). Model time unchanged (~48 min) and the ≥10-turn tail persists
(13 calls) — the tail is EVIDENCE-LIMITED, not framing-limited.
(b) Proof: 13 of 31 answers CHANGED between room-framed and cropped
stimuli — all in the small/symmetric tail (3 doors, pictures, rug,
baskets); verdicts there are stimulus-sensitive noise. The stable core
(bed, side table, yoga mat, obj_035) held.
(c) Two-stage describe→choose (desc_choice_test.py) tried one-shot:
bed HIT cheap (3+5 turns) but the tail fails at the SOURCE — basket
photo "heavily blurred/backlit", mat description derailed. Not adopted:
no gain where the single call fails, equal where it succeeds.
**Consequence for applying yaws (proposal, awaiting user): apply only
HIGH-confidence non-zero verdicts; low/medium non-zero = flag for the
fit loop's judge rather than a silent spin. A wrong basket yaw is
invisible; a confidently wrong bed yaw is the costly case — effort
follows error cost.**

**FINAL, 08-04 WRAP (user: "make the one we got canon and lets wrap
up"):** (d) FOOTPRINT PRUNE (user idea, deterministic 0/180-vs-4 by
observed-box fit) tried full-scene: sound geometry, ~15% cheaper, but
the BINARY lineup broke the bed benchmark (180 high-conf → 0 medium) —
the 90/270 candidates evidently serve as contrast anchors. REJECTED
from the default path by the user; kept behind `--prune` with the
measurement. (e) CANON FINAL = cropped 4-candidate choice, rose on ref
AND candidates (ref rose now unconditional — a describe prompt once
promised a rose the ref lacked and the judge spent 20 turns honestly
failing to find it). Canonical run on record (rotation_check.json):
31/31 answered, bed 180° HIGH / 6 turns, high-conf non-zero = bed +
door obj_127 (the two the confidence gate would apply). Superseded
records kept beside it: _2cam, _roomframed, _4cand (pre-rose-ref),
compass_bed. Also measured then shelved: free-form orientation
describe (front/axis/NONE — the basket self-classified "none" at 9 s;
the natural router if the tail ever matters). Rotation check CLOSED as
a research topic; remaining decision = the apply gate, then it's just
a stage that runs.

## ANNEXED 2026-08-05 — TOP-DOWN STIMULUS, REJECTED ON MEASUREMENT
## (user: "ok nvm this is not a great approach. annex it")

User experiment: keep the 4-candidate choice but swap the camera —
judge from ABOVE instead of from the room. No top-down PHOTOGRAPH
exists (the pano rig is at eye height), so the reference is the SPLAT
rendered from overhead with the ceiling clipped, and the candidates use
that same overhead camera. Both sides then live in the render frame, so
unlike the photo path there is no mirror to correct.

Full scene, same model and one-call-per-object protocol as canon:
**31/31 answered, 302 s wave, $7.08.** Agreement with canon 15/31 —
but split by where it matters:

- canon says NON-ZERO (the 10 that earn the check): **1/10**
- canon says 0 ("leave it"): 14/21

It answered 0° on 22 of 31 (canon: 21), so it looks calibrated in
aggregate while being blind to the actual flips — a stage that says "no
change" to everything scores 21/31 here and is worth nothing. Confidence
is ANTI-correlated: high-conf 1/3, low-conf 6/10, so the usual salvage
(keep only confident verdicts) makes it worse. Mount barely matters
(floor 8/16, wall 6/14) — the prediction that wall objects would fail
and floor objects survive was wrong.

Cause: looking straight down removes the vertical evidence. Headboards,
seat backs, door swings and shelf fronts are upright surfaces seen
edge-on from overhead. The single object it got right, the yoga mat, is
the one whose orientation is a flat rectangle in plan.

Caveat kept on the record: canon is not GT, it is the other format's
answer; only the bed carries user GT.

**MODEL FRAGILITY — and the user's stated reason for the verdict
(08-05: "this is a more risky approach. i maintain the annex").** On
obj_008 the images are BYTE-IDENTICAL between two runs and the answers
are opposite, both at HIGH confidence: the sonnet wave picked c (180°),
three subagents on the stronger session model picked a (0°, = canon).
Worse, both gave the SAME justification — "head/pillow end at top in
both" — so the `why` text is not diagnostic; it cannot be used to tell a
correct read from a wrong one. Candidates a and c are mirror images from
overhead, separated only by which end the pillow blob sits on.

This was NOT resolved by re-running the 10 non-zero items on the stronger
model (offered, user declined) — so it remains open whether 1/10 measures
the viewpoint or the model. The verdict does not rest on that number: a
stimulus whose answer flips with the model, at high confidence, on
identical pixels, is too fragile for a stage that runs unattended. The
perspective stimulus is not known to be immune, but it has a benchmark
hit behind it and this does not.

Artifacts (kept, not deleted): `compose/topdown_check.json`,
`compose/topdown_check/<oid>_td/` (per-call folders, stimulus-keyed
replies), `compose/review_shots/topdown.html` (review page,
`experiments/build_topdown_viewer.py`), builders
`experiments/topdown_choice_test.py` (`--flip-bed` reproduces the blind
benchmark condition) and `experiments/topdown_align_check.py`.

TWO FINDINGS SURVIVE THE REJECTION — they are not annexed:

1. **splat-transform works in the RENDER frame.** It applies
   diag(-1,-1,1) to a .ply on load, so its camera, `--look-at`, `--up`
   AND `-B` clip box all take RENDER coords — the frame fitted_preview
   is already in. Fitted from 4 clip-box observations against the ply:
   perm (0,1,2), signs (-1,-1,1), zero error. Passing raw coords puts
   the eye 2.4 m under the floor on the mirrored side of the room and
   renders bare floor. (Also: shot.py's argparse rejects flag values
   starting with `-`; use `--k=v`.) Every prior trusted use was a
   HORIZONTAL camera, where this is invisible.
2. **The room is yawed ~5.5° vs the world axes** — splat wall points
   -5.50° (peak score 4.6x the score at 0°), collider wall normals
   +5.75° over 39 m² of wall, two independent sources. Root cause:
   `detect_frame` only scores four DISCRETE hypotheses (identity /
   mirX / mirY / rot180); nothing ever estimates a continuous yaw, so
   room_shell's axis-aligned walls are the best axis-aligned fit to a
   rotated room (its 0.47–0.50 m half-max wall peaks ≈ 5 m·sin 5.5°).
   **USER RULING 08-05: accepted, not corrected** — "the rotation
   module can just prefer cardinal directions so its ok". Not a defect;
   do not re-open.

## SETTLED 2026-08-04 — ROTATION QUESTION FORMAT IS CANON (v1 — the
## direct ask; SUPERSEDED by v2 above, kept for the measurement record)

**User ruling: the rotation check is the DIRECT ASK. One call per
object: the mirror-corrected detection photograph + the placed view +
the room context, "how far must it turn to match the real one."**
Ground truth the user disclosed after the runs (blind protocol kept —
never in any prompt): the bed's correct answer is 180°, and the direct
ask said 180° from both cameras, with the same stated reason (pillow
end swapped). Cost 49–115 s / 4–8 turns per call, the cheapest arm by
3–10x.

Dropped, both on measurement (rotref_one records, 08-04):
- **8-tile strip** — the 3156px composite is unreadable after the
  harness downscale, so the judge spends 20–29 turns building zoom
  tools (PIL/ffmpeg/System.Drawing expeditions), 273–359 s per call,
  one >480 s timeout that killed a run; and it reads neighboring files
  in its cwd. User: "it is our job to give it things that makes it
  easy to make decision" (now in the effort-allocation memory).
- **propose→verify** — the verify step coin-flips: camA reversed its
  own correct 180° proposal back to 0° while camB confirmed the same
  flip; 15–16 turns when it self-argues. The propose half IS the
  direct ask; the verify half adds cost and noise, not safety.

Preconditions the canon call inherits (all built 08-04, in
`fitloop_rotref_parallel.py`): reference mirrored back to true
left-right (the pano frame is a DEFINED mirror — PLAN_SELF_PANO_RIG);
objects with no detection evidence fall back to the plausibility
question (lookup, not judgment: 28 of 31 placed have evidence, the 3
add/swap items do not); stimuli at native readable size; calls run
concurrently (waves; a failed call records no-answer, never kills the
run; replies on disk are reused).

OPEN, carried honestly: the chair's direct asks disagreed across
cameras (camA 0° vs camB 180°, mirror-corrected) — chair GT not yet
disclosed; single-camera choice (which one?) is not yet ruled. Bed
evidence says the answer is stable per camera A on the bed; camera
question (experiment A) still awaits the user's strip verdict.

## NEXT SESSION — FIRST THING (user, end of 08-03C) — SUPERSEDED by
the 08-04 canon ruling above; review flow now lives in
`review_shots/index.html` (latest run only, build_rotq_viewer.py)

**REVIEW THE ROTATION EXPERIMENTS. Both are RUN; both wait on the
user's eyeballs — nothing downstream in this stage moves until the
verdicts land.** One folder holds everything:
`out/bedroom_marble/compose/review_shots/`
  - `rotcheck_cam{A,B}_<id>.png` — experiment A, 8 strips
  - `rotq_sheet_cam{A,B}_<id>.png` — experiment B, 8 sheets
    (4 tiles: as placed | arm1 | arm2 | arm3, ONE camera per sheet so
    the answer is judged and not the view)
  - `rotq/` — raw replies, verbatim prompts, rotq_record.json,
    rotq_timing.md
Offered and not built: a scrolling `index.html` in that folder with
each arm's angle + stated reason beside its picture.

### Experiment B result (08-03C, run complete, 24/24 answered)

Machinery: `entangled_gen/experiments/fitloop_rotq_test.py` (arm2
reuses the experiment-A strips verbatim). Run in BOTH cameras because
A was still unreviewed — deliberately not letting A gate B.

**Timing** — wall 1098 s, rendering only 21.8 s (2%); calls SERIAL so
concurrency could not corrupt the numbers.

| arm | calls | s/condition | vs arm1 |
|---|---|---|---|
| arm1 direct angle | 8 | 24.0 | — |
| arm3 propose-verify | 16 | 41.4 | 1.7× |
| arm2 8-tile choice | 8 | 69.1 | 2.9× |

**The 08-03B cost assumption ("costs are similar where it matters —
model calls") is WRONG on wall clock.** Diagnosed, not guessed:
trivial `claude -p` = 3.2 s · +read one 384 px view = 7.0 s · +read the
3156 px 8-tile strip = 9.4 s. So the stimulus costs ≤6 s; the rest is
the AGENTIC LOOP. Instrumented with `--output-format json`: arm1 = 3
turns / 1.2k output tokens / 27 s, arm2 = **25 turns / 16.1k output
tokens / 261 s** — the model re-reads the strip tile by tile (no crop
files left behind, so it is re-reading, not slicing). Arm2 also swung
126 s → 261 s → 69 s avg on identical prompts: **the variance is the
finding, not the mean.** Untried knob: `--max-turns` to force a
one-look answer (changes what arm2 IS → would be a 4th arm).

**Answers** (degrees, CCW seen from above)

| item | cam | arm1 | arm2 | arm3 |
|---|---|---|---|---|
| obj_109 chair | A | 0 | 0 | 0 |
| obj_109 chair | B | 0 | 0 | **+180** |
| obj_008 bed | A | 0 | 0 | 0 |
| obj_008 bed | B | 0 | **+90** | 0 |
| obj_022 bookshelf | A | 0 | 0 | 0 |
| obj_022 bookshelf | B | 0 | 0 | 0 |
| obj_025 side table | A | 0 | **+90** | 0 |
| obj_025 side table | B | 0 | **−135** | 0 |

Three things for the user's verdict to settle:
1. **arm1 said 0° in 8/8 — it never once proposed a rotation.** Either
   every placement is already right, or the direct-angle question does
   not fire. An arm that always says "fine" is free and useless. This
   is the most decision-relevant question in the run.
2. **arm2 contradicts itself across cameras on half the items** (bed
   0 vs +90; side table +90 vs −135) — same object, same 8 rotations
   offered, different camera. That is experiment A's question
   answering itself.
3. **Two arms read the same image oppositely.** obj_109 camB — arm1:
   "backrest faces the wardrobe, seat opens toward the desk,
   plausible"; arm3's verify: "backrest currently faces toward the
   desk, seat turned away." That flip is arm3's ONLY non-zero answer
   in the run. Separately, arm2 justified −135° on the side table with
   "drawer faces point outward into the room" — the identical
   justification arm1 gave for 0°.

Ops gotcha found the hard way: **`claude -p` can only read images
inside its cwd tree.** Arm2's first run returned "I need permission to
read that image file" in 9.6 s and scored a non-answer because the
strip lived one directory up. Stimuli are now copied into the call's
cwd. This will bite any future stage that points a judge at an image
outside its working directory.

### A. Camera verdict (user eyeballs, strips already rendered):
`out/bedroom_marble/compose/review_shots/rotcheck_cam{A,B}_<id>.png`
— 4 items (obj_109 chair, obj_008 bed, obj_022 shelf, obj_025 table),
8 free-yaw tiles each (tile 1 = as placed, +45°/tile).
  - camA = judge standpoint (0, 1.6, 0), adaptive zoom
  - camB = dedicated 3/4 per item (room-center side, elevated)
  Judge: in which camera can a model actually TELL rotations apart?
  Chair seat direction, bed head end, shelf front, occlusion, size.

### B. ROTATION-QUESTION EXPERIMENT — RUN 08-03C (design as specified 08-03B; result above)

Head-to-head on the same 4 items, user eyeballs = GT:
  1. **Direct angle** — item-in-scene image + context view, ask "how
     many degrees do we rotate?" RISK on record: witness facing v8
     was ±45°-quantized and oblique-noisy for a SINGLE estimate; this
     chains two estimates + a sign convention.
  2. **8-tile multiple choice** — "which tile looks right?" (the
     ranking-beats-scoring bet).
  3. **Propose-verify hybrid** — direct angle → apply → ONE re-render
     → "correct now, or adjust?" (converges in ~2 renders when the
     guess is decent; verify catches sign/quantization errors).
  ~~Costs are similar where it matters (model calls); strips spend
  ~16s extra rendering.~~ **FALSIFIED 08-03C — true on call count,
  off by ~3× on wall clock; see the result block above.** Render
  machinery ready:
  `entangled_gen/experiments/fitloop_rotcam_test.py` (promoted from
  session scratchpad; loads fitted_preview.glb into render frame,
  spins about the item's vertical center axis, gray shell context).

## Open design questions (parked from the stage-entry discussion)

1. Round shape — whole-room rounds (place all → render → judge all →
   fix → repeat until a dry round) vs item-by-item convergence.
2. Verdict menu — typed set (accept / wrong-look→next candidate /
   wrong-facing→rotation check / doesn't-fit→next or re-shop / ...);
   does the judge see the 7 judge views?
3. Anchors → subs sequencing — anchors converge first (standing
   ruling); can a sub failure reopen its anchor?
4. Where PH3 collide runs — inside each round or once after
   convergence.
5. File contract — the placement state the judge/viewer/PH3 read.
6. Re-shop channel — list-dry → back to shopping with a complaint
   (the AC / ceiling light / pictures cases: 0 candidates within 15%).

## Inherited context

- Orientation prototype finding (resolved 4/4 face_conflicts, config
  re-search + ORIENT_W): PLAN_SHOPPING.md row 8.
- Facing evidence ladder + scene-calibration watch-list (wall-hug
  0.30 re-test on scene #2): PLAN_SHOPPING.md.
- Known warts riding in: light-switch mis-anchor, wrong-twin
  referent, obj_062 box seen by no view.
- Shopping stage record: PLAN_SHOPPING.md rows 7–7d (native fit,
  image judge canon, k=3, map redraw).
