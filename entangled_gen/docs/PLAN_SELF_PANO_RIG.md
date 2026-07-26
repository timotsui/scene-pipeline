# PLAN — self-rendered pano rig from the splat

**== REVISED (user, 2026-07-26 late): 20% CONFIDENCE FLOOR EVERYWHERE —
the 0.40 gate dropped ("just makes things more confusing"). Chain rerun as
suffix 'c': seg_batched --box-thr 0.20 --topk 40 -> pano_lift --min-score
0.20 --gate-peak 0.20 (gate = no-op, kept 150/150) -> pano_recenter, which
is now THE post-detection filter: 20 refined, 15/23 marginal singletons
REFUTED by close-up, 8 confirmed; enrichment found 0 new children (all 76
candidates already known at the 20% floor — the first round now sees
everything). Canonical manifest: scene_manifest_pano2c_rc.json, 135
objects (toy 15, basket 14, picture 24, window 7...), floor min +0.012,
floor-ish median +0.107. Viewer delta layers: Δ recenter 35, Δ gate kills
0. Suffix-'b' (0.35/0.40) manifests kept on disk. Minor artifact noted:
one 'conditioner' label (canonicalization split of 'air conditioner'). ==**

**== UPDATE 2026-07-26 (daytime session) — post-processing begins: hard
score filter (user: "just a hard filter from the boxes we already have, no
reruns"). manifest_filter.py (NEW, generic --thr) on the canonical
manifest at 0.30 → scene_manifest_pano2c_rc_f30.json: 102 objects, drops 6
(obj_113/121/122 toy, obj_119/147 book, obj_149 conditioner — the label
-split artifact dies for free). CAVEAT logged: 3 of the 6 are
retake_confirmed (close-up verified, scores .27-.28) — the hard filter
overrules the retake verifier on them; drops preserved in the file's
filtered_out. Viewer layer "pano track · f30 (score ≥ 0.30)" for A/B vs
canonical. **f30 ADOPTED (user: "i think this works")** — post-processing
base going forward.

Post-processing step 2 — DEDUP (manifest_dedup.py, NEW, same session).
Design settled with user: high mutual 3D overlap = one physical object
(two rigid objects can't share a volume), so merge GEOMETRY and keep every
LABEL (primary = highest-scoring member, rest -> alt_labels — resolves the
"lamp ceiling fan" dual-name worry without guessing); box-in-box nesting
survives automatically (high containment but LOW IoU). Confident zone
IoU>=0.6: pure geometry, no model. Gray zone (IoU 0.4-0.6 +
containment>=0.9): ONE batched claude.exe haiku call judges the label pair
same-vs-part-of (cached in dedup_llm_cache.json; degrade = keep both).
**USER RULE recorded this session: NO hard-coded synonym/label lists —
pipeline must run on all scenes unmodified; local LLM = the swap for
online-averse users.** Result: 102 -> 92 objects (9 merge groups: chair+
office chair, rug+mat+yoga mat, side table+desk, lamp+ceiling light, 3x
door+window incl. 1 LLM-ruled, 2x bookshelf+shelf; LLM ruled
bookshelf|shelf + book|shelf = part-of -> kept). 8 kept-but-overlapping
pairs (the bookshelf granularity thicket) in the file's overlap_report.
scene_manifest_pano2c_rc_f30_dd.json; viewer "pano track · f30+dedup".
AWAITING USER VERDICT (R9). ==**

**== CANONICAL (user, 2026-07-26): this IS the pano track — drop the "2.0"
framing. Final chain = self-rendered pano (0,0)+1.6m -> 20-crop rig ->
batched-vocab detect (seg_batched.py) -> z-buffer lift (pano_lift.py
--seg-dir seg_batched --suffix b) -> robust merge q.05 -> confidence gate
peak>=0.40 -> recenter round (pano_recenter.py --suffix b). Manifest:
scene_manifest_pano2b_rc.json — 77 parents + 11 children (9 books, pillow,
bookshelf); 17 objects bound-refined, 8 phantom singletons refuted by their
own close-ups, floor-ish q75 +1.40 -> +0.80, floor min +0.011. Viewer:
"PANO TRACK (canonical)" (+ pre-recenter comparison entry). Marble-pano
lane relabeled "pano 1.0 (superseded)". ==**

UPDATE 2026-07-26 (later): **pano-as-canonical-artifact BUILT** (user "try
it" after the retake-ladder discussion — GPU once per standpoint, then all
crops/strips CPU). pano_stitch.py: 6 cube faces (2048px, fov 95, WSL gsplat)
→ equirect 8192x4096 (22.8 px/deg equator, 1.8x Marble's density) in
crop_pano's A2 convention; pano frame = pure rot180-about-z of RAW (NO
mirror — unlike Marble's pano), eye (0, -1.571, 0) = (0,0)+1.6m.
MECHANICALLY VERIFIED: pano-resampled crops reproduce the direct SP1 rig
renders at corr +0.975..+0.989 (yaw-sign pairing: pano yaw θ = rig raw yaw
−θ, recorded in pano_selfrender_meta.json). crop_pano.py gained --out-dir;
20 crops in rig_sp0/crops/. **SP1 PASSED (user, 2026-07-26): "pano now
looks good"** — after one fix: the first stitch used a pure rotation and
read left-right flipped (user caught it); pano frame is now MIRROR-Y of raw
(the readability mirror — Marble's pano had it deliberately; ours is
DEFINED not estimated, zero registration). Re-verified vs mirrored direct
renders: corr +0.981..+0.991. Crops are mirror images (like Marble's
always were; detector-indifferent, lift exact via recorded mapping).
**SP2 PASSED (user "ok cool seems good"):** self-pano crops detect at
near-parity with Marble's (11.7 dets/img, mean 0.471, 32% >=0.5, 25 labels
vs benchmark 9.8 / 0.478 / 39% / 25; sweep frames 8.5 / 0.451 / 23%).
Overlays folded into pano_review.html.
**SP3 RAN (pano_lift.py):** crop cams pano->raw via the defined mirror
(improper R by design — maps the mirrored crops' pixels to true RAW rays),
20/20 mini-G1 verified (+0.32..+0.88). 233 lifted (94 truncated 40%),
robust merge q.05 -> scene_manifest_pano2.json (93 objects, 11 weak),
gate -> scene_manifest_pano2_gated.json. GATE REVISED (user 2026-07-26):
**confidence-only, peak >= 0.40, NO vote requirement** — the votes>=2 bar
killed 12 fine-confidence single-view objects (audit: incl. the real
computer monitor at 0.466, toys, books — small objects detected only in
the crop aimed near them). Gated = 69 objects (was 57 under the two-sided
gate; ungated 93). Votes stay recorded per object for the future
retake-verifier (aim a recenter crop at low-vote objects, confirm/refute
— the G4-validated policy), which replaces vote-killing when built. **Pedestal test PASSED: floor-gap min +0.014** (pano
1.0's +0.065 pedestal absent). Floor-ish median +0.139, q75 tail 1.13 —
single-standpoint truncation/occlusion, the retake-ladder's future work.
Both manifests in the viewer ("pano 2.0 · rig lift + gate" / "(ungated)").
AWAITING USER VERDICT vs the other 8 method sources.

Status: ACTIVE 2026-07-26. User decisions taken: **option (b) rig-direct**;
**standpoint (0, ·, 0), eye 1.6 m above floor** ("one pano from the 0,0
point"). SP1 executed same night (pano_rig.py → out/<scene>/rig_sp0/):
20/20 cameras verified (corr +0.31..+0.88; far-wall yaws 135-225 lowest —
distance, not error). sp1_review.html AWAITING USER VERDICT. Context for
why this ordering: the vote-gated sweep manifest was judged "slightly
better but does not totally beat pano" — the rig is the attempt to combine
pano-crop image quality with splat-exact geometry.
Companion: PLAN_SPLAT_RECENTER.md (the sweep/retake lane this will be
compared against). Scene: bedroom_marble.

## 1. Decision being implemented (user, 2026-07-26)

Bring the panorama back **as a rendering format we choose, self-rendered
from the splat** — NOT Marble's pano. This does not reverse "pano scrapped
as base": what was scrapped was a FOREIGN pano (unknown camera, collider
-mesh registration → the measured +6.5 cm pedestal; fixed 4608x2304
ceiling). Here the base frame stays the splat, the camera is OURS, so
pixel→ray→3D is exact by construction — zero registration — and resolution
is whatever we render.

Why: attacks the detection-coverage gap structurally (old planned views:
60° of the room never rendered, 15/20 detections in one view, exactly 1
cross-view merge). A single-standpoint rig gives full angular coverage with
no view planning. Accepted limitation: one standpoint fixes ANGULAR
coverage, not occlusion; 2–3 standpoints (each with exact geometry) is the
later extension and stays a parameter from day one.

## 2. OPEN — implementation option (USER DECIDES)

**(a) True equirect first.** Render a high-res equirectangular image from
the splat (needs a new renderer: native equirect or cubemap-stitch), then
run the existing `crop_pano.py` rig on it unmodified (its u-modulo sampler
already handles the ±180° seam, crop_pano.py:55).
- pro: human-viewable overview pano for free; crop_pano.py untouched;
  exact parity with how the old pano lane made crops.
- con: a renderer we don't have yet (gsplat has no equirect camera —
  cubemap-stitch means 6 renders + stitching + cube-edge quality seams);
  every crop is a resample OF a render (double resampling).

**(b) Rig-direct.** Skip the equirect: render the same 20-camera rig
(8 yaws @ pitch 0 · 8 @ −40 · 4 @ +40, FOV 75, from `crop_pano.py`'s rig
table) DIRECTLY from the splat at the chosen standpoint. Optionally a
cheap low-res equirect later, for viewing only.
- pro: **the renderer already exists and is verified tonight** —
  `analyzer/render_targets_wsl.py` (the analyzer's own gsplat path, WSL
  env) rendered 18 aimed views with per-render camera verification at corr
  0.45–0.81. The rig is just 20 fixed aim directions instead of 18
  computed ones. One resample, best per-crop quality, no new renderer.
- con: no human-viewable pano artifact (unless the optional viz equirect
  is added later); crop_pano.py's SAMPLER is bypassed (only its rig table
  is reused — the seam-handling praise transfers to the rig geometry, not
  the code path).

Recommendation: **(b)**, and not only for less work — for a reason learned
tonight: `shot.py`/splat-transform FAILED mechanically for arbitrary
interior cameras (9/18 blank renders; PLAN_SPLAT_RECENTER.md G4 notes), so
ANY new render path must be the WSL gsplat one anyway, and that path is
per-view pinhole, which IS option (b)'s shape. Option (a) would build a
second new renderer on top of it just to resample it back into pinholes.

## 3. OPEN — standpoint (USER DECIDES; a parameter either way)

Default proposal: the recentered origin (the generator standpoint the
splat was recentered around, eye at floor + 1.6 m up — same convention the
viewer's startup camera now uses). Alternatives: the analyzer's best
standpoint, or a clearance-map argmax. Multi-standpoint (2–3) is the
documented v2, not in this plan's gates.

## 4. What is reused vs new (verified against today's code)

| piece | status |
|---|---|
| rig table (20 cams: yaw/pitch/fov) | reuse from crop_pano.py (constants) |
| renderer | reuse analyzer/render_targets_wsl.py — generalize input to a camera list (eye + yaw/pitch or aim), keep c2w annotation + 1 s GPU pacing |
| per-render camera verification (mini-G1) | reuse corr-check from sweep_recenter.py — house rule: every frame crossing verified |
| detect+SAM | seg_views.py unmodified (`--views-dir <rig dir> --glob 'sp_*.png' --pace 2`, vocab.json auto) |
| depth for lift | splat z-buffer with the exact c2w cams (lift_sweep.lift_frame + MatCam) — unchanged mechanics |
| per-axis trust + merge | lift_sweep.merge_per_axis unchanged |
| sidecar contract | NEW (small): per-crop json stores eye/yaw/pitch/fov AND the exact c2w (the G4 lesson: store what the renderer actually used, self-heal-able) |
| adaptive retakes on top | sweep_recenter.py already consumes any lift pool — compose in a later gate |

What does NOT need to change: viewer (a new box_sources entry is one
registry line), vocab, SKIP/synonym handling.

## 5. Gates (strict order; one assumption per gate; user judges visuals)

- **SP1 — rig render + camera verify.** Render the 20 rig views at the
  chosen standpoint (768 px, option-b path). Mechanical: mini-G1 corr per
  view (expect ≥0.4 like tonight's retakes). Then USER JUDGES the crops
  (right-side up, sane coverage, no voids). Deliverable: contact-sheet
  page + corr table.
- **SP2 — detection coverage.** seg_views over the 20 crops; page in the
  detect_compare.html style. Acceptance question (user judges): does the
  rig see what the 192-frame sweep saw — especially the objects the old
  planned views missed (the 60° hole) — with only 20 images?
- **SP3 — lift + merge → manifest.** lift_sweep machinery on the rig pool
  → scene_manifest_rig.json → viewer box source next to G3's. Mechanical
  acceptance: floor-gap min ~0 (no pedestal), then USER VERDICT in viewer
  vs "splat · sweep mask-lift (G3)" (94 objects / 154 frames) — the real
  question: how close does 20 planned views get to 192 blind ones?
- **SP4 — recenter 2.0 (user go 2026-07-26; spec expanded).** Aimed
  CPU-resampled crops from the self-pano, THREE shot purposes:
  1. **completion** — targets: objects with weak/truncated bounds; aim at
     the merged 3D box center, fov fit 1.8x (clip 30-100); detections
     admitted to the pool only if same-label + overlapping an existing
     object (G4 v3 rule), then robust re-merge.
  2. **verification** — targets: single-vote objects (vote-killing is OFF
     per user; the retake confirms or REFUTES with evidence). Refuted ->
     dropped from the rc manifest, recorded.
  3. **enrichment (NEW, user 2026-07-26)** — targets: container-label
     objects (shelf/bookshelf/desk/side table/bed/basket/pencil holder/
     pot...). Zoomed shot per container; detections whose lifted box is
     CONTAINED in the parent (and not the parent's own label) become
     CHILD objects with a `parent` field + `sub_object` flag — the
     hierarchy preserves world richness (books on the shelf, pens in the
     holder) WITHOUT entering the room-scale merge: the child layer is
     where close-up granularity lives, structurally ending the G4
     fragmentation problem. Children dedup vs existing objects and
     siblings; gated at peak>=0.40 like everything else.
  Angularly-huge targets (needed fov > 100) are SKIPPED and reported in
  v1 (cylindrical strip = next rung, not yet implemented).
  Output: scene_manifest_pano2_rc.json (+ viewer source). Every shot
  camera mini-G1-verified; seg paced 2 s.
  - **STATUS: RAN 2026-07-26 (pano_recenter.py).** 32 shots (31/32 cams
    verified; 2 door targets skipped needing >110° — first customers of
    the cylindrical strip). Results: bounds refined IN PLACE on 25
    objects, TRUE weak-bound 6 -> 1; verification 8/11 confirmed, 3
    phantom books refuted+dropped; 4 children attached (books + a nested
    bookshelf; 37 candidates deduped as already-known — correct); floor
    -ish gap median +0.166 -> +0.128, q75 +1.43 -> +0.96. 66 parents + 4
    children in the viewer ("pano 2.0 · +recenter (SP4)").
  - **ARCHITECTURAL LAW (learned the hard way, 3 failures then fixed):
    close-up measurements NEVER re-enter the room-scale merge.** First
    SP4 attempt re-merged 98 admitted detections -> weak bounds 6->49
    (same pathology as sweep G4 v1/v3). Final form: completion shots
    refine their own target's bounds in place; enrichment shots feed the
    child layer; verification shots return only a yes/no. The merge runs
    ONCE, on first-round measurements only. This law belongs in the 3h2
    fuse spec too.

## 5b. The retake ladder (settled with user 2026-07-26)

Escalation order for objects the default rig fails on, cheapest first —
all but the last are CPU-only resamples/renders from the SAME standpoint:

1. **Tile-edge cut** → recentered resample from the pano/standpoint (a
   fresh crop aimed at the object; the equirect sampler's u-wrap makes
   tile boundaries and the ±180 seam free).
2. **Angularly huge** (needed pinhole fov > ~110°, e.g. wardrobe at arm's
   length spanning 128°) → **cylindrical-projection strip** (user-chosen
   design): render/resample a wide strip (up to ~150-160° azimuth) in
   cylindrical projection — mild uniform distortion, verticals stay
   straight, detectors tolerate it far better than fisheye pinhole edges.
   The lift is UNAFFECTED because it never required pinhole — only a known
   pixel→ray map, which we own for any projection we generate. Needs: (i)
   one measured check of detector/SAM quality on cylindrical imagery
   before trusting it (add to SP2 or a mini-gate), (ii) edge-trust
   bookkeeping adapted to the strip's edges (top/bottom behave like
   pinhole; left/right map to azimuth limits).
3. **Occlusion** (photons never reached the eye) → standpoint #2 (one
   more GPU pano/rig pass; multi-standpoint fusion = the documented v2).
4. **Step-back** (direct splat render from a moved camera) → demoted to
   last resort; kept available via the WSL renderer.

## 5c. Batched-vocab detection (user idea, 2026-07-26 — ADOPTED for pano2)

FINDING: GroundingDINO confidence drops with prompt length. Measured on the
picture wall (pano_y270_pp00): 30-term mega-prompt -> 5 paintings at
0.35-0.37; 3-term prompt -> 21 at 0.37-0.48 (zoomed crop: 0.55). Second
finding: the FIRING term matters — 'picture.' alone finds ZERO, 'painting.'
fires (keep expansion synonyms, in different batches). Third: composition
effects exist (a few strong classes scored slightly softer under batching —
door 0.58->0.54, bed 0.66->0.53) — prompt CONTEXT matters, not just length;
open question for the detect band.

seg_batched.py: vocab round-robin into 6 batches of ~5 (synonyms land in
different batches so they never compete in one prompt), per-batch detect,
canonicalize, per-image same-label cross-batch NMS (IoU .5), top-30, SAM
once. Same output contract as seg_views. Result on the rig crops: 233 ->
325 dets; picture 46 -> 95 (mean up .389 -> .412), rug 0 -> 6. Lifted via
pano_lift --seg-dir seg_batched --suffix b -> scene_manifest_pano2b(_gated):
**85 gated objects, picture 26 (was 11)**, rug/yoga mat/ceiling light newly
surviving; floor min +0.012. Viewer source "pano 2.0 · batched detect".
NOTE: SP4 recenter has NOT yet been re-run on the batched base.

## 6. Known risks / carried-over lessons

- GPU: pace all renders (1 s) and detect (2 s) — [[laptop-gpu-crash]];
  per-item resume everywhere (renders skip-if-exists, dets per-view).
- Ceiling/floor pitch rows point near ±90° only at pitch ±40 — no
  degenerate-up cases in the rig; the renderer guards anyway.
- The G4 close-up granularity fragmentation does NOT apply to SP1–SP3
  (uniform fov 75 rig) but returns at SP4 — flagged there.
- occlusion: single standpoint accepted; do not over-interpret SP2 misses
  that are actually occlusion (they motivate standpoint #2, not detector
  blame).
