# SPEC — 3h2 fuse contract: unified lift pool + ported vote filter

Status: DRAFT 2026-07-25, awaiting user review. Nothing here is implemented.
Parent decision: SESSION_2026-07-25_HANDOFF.md §"Key idea parked at session
end". Map nodes: 2.3 LIFT (3h2) + the fuse. This spec is the contract to
implement against once approved.

## 1. One-paragraph statement

Pano crops and analyzer sweep frames become ONE pool of views. Every pool
view goes through the same detect (GroundingDINO + SAM, vocab.json), the
same mask lift (our z-buffer median-depth lift), into ONE set of lifted
3D detections in the RAW splat frame. A ported-and-upgraded version of the
analyzer's two-sided vote filter clusters and gates them. Candidate p
(pano lane) stops being a separate lane — pano crops are just the sharpest
views in the pool. Output is scene_manifest.json, same schema as today
plus vote metadata.

## 2. Why (recorded rationale)

- Our current lift merges with exactly 1 cross-view merge on bedroom_marble
  (detection-coverage finding): merging is starved, not broken. The vote
  filter is the analyzer's answer to the same problem and only works WITH
  dense coverage — which the 192-frame sweep now provides.
- Pano↔RAW is verified (A2b / panoraw_c): p_raw = (x, −y−H, z), H = 1.31
  for bedroom_marble (derived from mesh floor_y), pano eye at RAW
  (0, −H, 0). So pano crops can be lifted by splat z-buffer depth FROM THE
  PANO VIEWPOINT — no collider, no ICP registration risk.
- The analyzer's own lift is 1-px + fabricated z-extent — superseded. Its
  depth_*.png are 8-bit L (0–255, checked 2026-07-25) — visualization
  only, NOT metric. Our z-buffer over the splat means is the only depth
  oracle in the pool.

## 3. Inputs (file contracts, per scene)

| input | path (under OUT/<scene>/) | producer | notes |
|---|---|---|---|
| splat | gen_raw.ply (via paths.ply) | WORLD | z-buffer depth source |
| sweep frames | analyzer/job_high/frames/frame_%04d.png | analyzer OBSERVE | 512×512, 192 on bedroom_marble |
| sweep cameras | analyzer/job_high/transforms.json | analyzer OBSERVE | fl_x/fl_y/cx/cy/w/h + per-frame 4×4 c2w `transform_matrix` + scene_center/scene_radius. Cameras are ALREADY in the RAW ply frame (bridge_boxes.py: "no transform applied anywhere") |
| pano crops | pano_crops/ (crop_pano.py) + their yaw/pitch/fov sidecars | pano OBSERVE | each crop = perspective cam at the pano eye |
| word list | vocab.json → queries.gdino | vocab_build.py (2v) | seg_views.py already prefers it |
| detect+masks | seg_pool/ (new dir): detections.json + <view>_masks.npy | seg_views.py run over the pool | today's seg_sweep/ (192 frames) + seg_pano_v2/ (20 crops) are the manual prototypes of this |

## 4. Camera adapter (transforms.json → our Cam)

New: `analyzer/cams_from_transforms.py` (or a function in the fuse script).
Maps each `transform_matrix` (c2w) + intrinsics to the `r3.Cam`
constructor (pos/look/up/fov/res) or, cleaner, to a Cam built directly
from R,t,f,cx,cy.

OPEN — convention of the 4×4 (OpenGL −z-forward vs COLMAP +z-forward,
row/col major) must be VERIFIED, not assumed (gate G1 below). The check is
mechanical, not visual: color z-buffer the splat means through the adapted
camera and correlate against frame_%04d.png (same trick as
lift_views.detect_frame); the correct convention wins every frame with
corr ≫ the alternatives. No frame-sign hypothesis search is needed after
that — sweep cameras live in RAW, so the lift runs natively in RAW and
detect_frame's raw→render calibration is NOT part of this path.

## 5. Pano crops as pool views

- Each crop's camera: position = pano eye IN PANO FRAME (origin), rotation
  from the crop's yaw/pitch, fov/res from the crop sidecar.
- Lift runs in the PANO frame (z-buffer needs splat points in that frame:
  transform splat means by the INVERSE of panoraw_c, i.e.
  p_pano = (x_raw, −y_raw − H, z_raw) — self-inverse in form), then lifted
  points map to RAW via panoraw_c. Alternative (equivalent): build the
  crop camera directly in RAW by conjugating with panoraw_c. Implementer
  picks one; the spec requirement is only that G3 verifies it.
- H comes from scene_manifest_pano.json frame.floor_y (per-scene), same
  derivation manifest_pano_to_raw.py uses. NOT hardcoded.

## 6. Lift (unchanged mechanics, new home)

Per pool view: depth = depth_zbuffer(splat means, cam) → per-detection
mask ∩ finite depth → median/IQR depth trim → unproject → 2–98 pct AABB.
Same constants as lift_views.py (MIN_MASK_PX 400, MAX_LIFT_PX 30000)
except SCORE_MIN drops (see §7 thr change). Label canonicalization BEFORE
voting: SYNONYMS map ∪ reverse-containment merge (chair/office chair,
mat/yoga mat — the vocab TODO) — synonym duplication inflates votes and
was an R3 confound; it MUST be resolved at lift time, not post-hoc.

## 7. Vote filter port (upgrades over the analyzer's a7)

Analyzer baseline (pipeline.py:76-130): fixed-anchor clustering, eps =
0.20 × scene_radius, survive iff members from ≥8 frames AND best
single-frame score ≥0.40, ≤3 clusters per label.

Ported version — keep the two-sidedness, change four things:

1. **3D-IoU clustering, not radius.** Greedy same-label merge at
   MERGE_IOU (start 0.20, existing iou3d) — a radius eps treats a pencil
   holder and a wardrobe identically; IoU does not. Anchor order: by
   score, as today.
2. **Visibility-normalized vote threshold.** A cluster's denominator is
   the number of pool views that COULD see it: cluster center inside the
   view frustum AND not occluded (z-buffer depth at its projection within
   a tolerance of its distance). Survive iff votes / visible_views ≥
   VOTE_FRAC (start 0.15) AND votes ≥ VOTE_MIN_ABS (start 3) — replaces
   the absolute 8, which punishes objects visible from few standpoints
   (the analyzer's own "interplay trap" note).
3. **Size agreement as a third signal.** Per-cluster IQR of member box
   volumes; flag (do not kill, v1) clusters whose volume IQR/median
   exceeds SIZE_SPREAD_MAX (start 1.5). Killing on size waits for
   evidence it fires correctly.
4. **No per-label cap.** The ≤3/label cap dies ("picture frame" scenes);
   junk suppression is the vote's job.

Peak gate stays: best single-frame score ≥ PEAK_MIN (start 0.40).
Detect threshold drops 0.35 → 0.20 at seg time ONLY in pool mode — the
vote now does the gatekeeping the threshold used to do.

## 8. Output contract

OUT/<scene>/scene_manifest.json — same schema as lift_views.py §manifest,
frame block RAW (up = −y for marble bundles), plus per-object:

```json
"votes": 14, "visible_views": 61, "vote_frac": 0.23,
"sources": {"sweep": 12, "pano": 2},
"peak_score": 0.71, "size_spread": 0.4, "flags": []
```

Sidecars: seg_pool/fuse_debug.json (every cluster incl. killed, with kill
reason) — detect_compare.html-style review pages build from this.

## 9. Script shape

New `lift_pool.py` (lift_views.py stays frozen for the week5-style
gpu_yaw path until the map renumber): reads §3 inputs, runs §4–§8, CLI
`--scene`, `--job` (default newest job_*), `--no-pano` (sweep-only
ablation), `--vote-off` (raw pool manifest, for the G4 A/B). seg_views.py
gains `--views-dir/--glob` presets for the pool run (it already accepts
both; wiring into scene_ready is a LATER rewire, out of scope here).

## 10. Gated verification (one assumption per gate; user judges visuals)

- **G1 camera convention** (mechanical): correlation table over 4
  candidate conventions × 8 frames; winner must dominate uniformly.
  Deliverable: printed table, no user judgment needed unless ambiguous.
- **G2 single-frame sweep lift** (visual): lift ONE frame's detections,
  project boxes back into that frame + 2 neighbors. User judges overlay.
- **G3 pano crop lift** (visual): ONE crop lifted, box projected into the
  pano and into a nearby sweep frame. User judges.
- **G4 fuse A/B** (visual): full pool, `--vote-off` vs vote-on, review
  page in the detect_compare.html format + viewer manifest layer. User
  judges: what the vote killed that was real, what junk survived.
- Order strict: no gate starts until the previous one passes. Parameters
  in §7 are starting values; they move only on G4 evidence.

## 11. Out of scope (listed so they don't creep in)

- Amodal/occlusion completion (amodal_apply.py) — runs downstream of the
  fused manifest, unchanged.
- scene_ready/agent_package/C7-reference-photo rewires — separate task,
  after the map renumber.
- ICP scale promotion into manifest_pano_to_raw.py — deferred (handoff §6).
- Pano-lane keep/drop decision — this spec makes p a pool member; whether
  the standalone pano manifest path is retired is decided AFTER G4.

## 12. Open questions for review

1. VOTE_FRAC/VOTE_MIN_ABS starting values (0.15 / 3) — sane priors, or
   start stricter and loosen on G4?
2. Occlusion tolerance in the visibility test (fraction of center
   distance? absolute meters?) — proposal: max(0.15 m, 5% of distance).
3. Should pano-crop votes weigh more than sweep votes (sharper source),
   or does visibility normalization already cover it? Proposal: no
   weighting in v1; record `sources` and look at G4.
4. seg_pool re-run vs reuse: today's seg_sweep (thr .35) exists — rerun
   everything at thr .20, or G2/G3 on the existing data first and only
   rerun for G4? Proposal: the latter (cheaper, gates the GPU spend).
