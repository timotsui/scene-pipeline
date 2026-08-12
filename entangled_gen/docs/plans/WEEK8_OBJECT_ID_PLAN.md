# Week 8 — object identification & segmentation v2 (Marble-bundle pipeline)

> Living document (created 2026-07-07, rewritten same day after the design
> discussion: two-layer identification + recall net + enrichment). Update the
> Status column + status log as we go; sessions are expected to end mid-plan.
> Builds on GEN_BACKEND_EVAL_PLAN.md and SESSION_2026-07-05C_HANDOFF.md.

## Decision & goal

**Object identification moves to the Marble download bundle** (user 2026-07-07:
"path of least resistance"). The end goal is a more detailed, accurate, and
complete scene manifest — not just labeled boxes — because downstream
composition ("pick object after layout") is only as good as what each manifest
slot records.

The design is the proven Grounded-SAM assembly line (names → boxes → masks),
extended into 3D with the Marble bundle's assets, plus two additions the
generic recipe can't do:
- a **completeness audit** against the collider mesh (an object can hide from
  every image pass, but not from the mesh — being in the mesh is what
  "existing in the scene" means), and
- a **VLM enrichment layer** so each object carries appearance / material /
  style / relations, not just a label (a floor plan vs a design brief).

## Why the current identification is weak (baseline)

Current eval-kit path (seg_views.py + lift_views.py on 4 splat renders):

| Question | Current answer | Failure mode |
|---|---|---|
| What's in the scene? | hardcoded per-room vocab | can't find what it doesn't name (yoga mat, AC unit) |
| Where in 2D? | GroundingDINO on 4 fuzzy splat renders | degraded input, 4 viewpoints, misses |
| Where in 3D? | splat depth z-buffer + 4-hypothesis frame calibration | inference stacked on inference |

## What the Marble bundle provides (inputs)

`in/Cozy Sunlit Study Bedroom/` (downloaded 2026-07-07):

| File | Role in the pipeline |
|---|---|
| `*_pano.png` | clean 360° equirect render — the 2D detection substrate |
| `*_collider.glb` | metric surface mesh — exact 3D via ray-casting + the completeness audit |
| `prompt.txt` | the scene's *specification* — base detection vocabulary |
| `*.spz` | splat (source of out/bedroom_marble/gen_raw.ply) — novel views for occluded spots |
| `*_prompt.jpg` | the image prompt (reference only) |

Principle: **intent for searching, observation for describing** — prompt.txt
seeds the vocab; the pano (what Marble actually built) is ground truth for
detection and description.

## Pipeline v2 (7 stages)

    pano.png ──slice──► perspective crops (2 zoom levels)
                             │
    prompt.txt ─nouns─┐      │
    Florence-2/RAM ───┴─► vocab (union) ──► GroundingDINO (boxes, per crop)
                                                 │
                                            SAM (masks)
                                                 │
                              mask pixels → rays → ∩ collider.glb
                                                 │
                                     3D boxes, merged by label+IoU
                                                 │
                    ┌── completeness audit ──────┤
                    │   • VLM inventory diff     │
                    │   • mesh-residual check    │
                    │   • novel splat views      │
                    │   (loop back to detect) ───┘
                    │
                    ▼
            VLM enrichment (per-object crops + scene relations)
                    │
                    ▼
            scene_manifest.json (extended schema) + overlays + viewer

1. **Names** — extract object nouns from prompt.txt; union with Florence-2 or
   RAM tags over the pano crops (catches objects Marble added beyond the
   prompt). Vocab is a word list either way — extra words are nearly free.
2. **Boxes** — GroundingDINO over perspective crops sliced from the equirect
   (detectors degrade on equirect distortion; start 8 yaws × 2 pitches).
   Second pass at a tighter zoom level for small objects (remotes, books,
   handles). Map boxes back to pano coords.
3. **Masks** — SAM per box. NOT optional here (unlike the generic 2D recipe):
   a box's rays hit the wall behind the lamp; the mask confines rays to the
   object's actual pixels. Existing SAM-vit-base stays (SAM 2 = later option;
   its headline gain is video).
4. **3D** — each mask pixel = a ray from the pano camera; intersect with the
   collider mesh (trimesh; subsample pixels like lift_views MAX_LIFT_PX);
   hit points → metric 3D box; merge across crops in 3D by label + IoU
   (reuse lift_views merge logic). No depth estimation, no frame hypotheses.
5. **Completeness audit** (the recall net — answers "did we find everything?",
   which no single stage otherwise asks):
   a. *VLM inventory diff*: one scene-level VLM pass "list every object you
      see" → diff vs detections → missed names re-enter stage 2; still-missed
      → VLM gives rough region → SAM directly.
   b. *Mesh-residual check*: mesh surface − floor/walls/ceiling − all claimed
      object boxes = unexplained geometry. Cluster leftovers into blobs; each
      blob = a localized miss. Visible blob → pano crop → VLM "what is this?".
      Occluded blob → render a novel splat view aimed at it → identify.
      Metric: **% of mesh surface explained** — a free numeric completeness
      score per scene, comparable across backends, no eyeballs needed.
6. **Enrichment** — after the object set is complete: per-object crop from the
   pano → VLM describes color / material / style / contents / facing; one
   scene-level pass for support+adjacency relations ("monitor on desk") and
   scene character. Cropping sidesteps the VLM localization weakness and binds
   each description unambiguously to its object.
7. **Manifest** — same `scene_manifest.json` contract extended per object:
   `description`, `material`, `facing`, `relations[]`, plus scene-level
   `style/lighting` and `mesh_explained_pct`. Downstream (viewer, envelopes)
   reads the old fields unchanged. New stages become entries in PIPELINE.md
   when they exist.

## Models

| Worker | Model | Status |
|---|---|---|
| names (top-up) | Florence-2 (or RAM) — trial both, they only emit words | new, small download |
| boxes | GroundingDINO base (HF) | already wired (seg_views.py) |
| masks | SAM vit-base (HF) | already wired (seg_views.py) |
| audit + enrichment VLM | **DECISION (user):** API VLM (½ session, pennies, online) vs local Qwen2.5-VL-7B (+1 session install, free/offline) | open |

## Ground rules (verification workflow)

- USER judges all visuals; Claude prepares artifacts + numbers only.
- Plan-first: each ▶ step proposed before execution; ⛔ CHECKPOINT blocks on
  the user. One assumption verified at a time.
- Render-based path (seg_views/lift_views) stays untouched as the fallback for
  backends without a pano/mesh bundle.

## Execution plan (est. ~3 working sessions)

### Session A — core geometric path (stages 1–4)

| # | Step | Gate | Status |
|---|------|------|--------|
| A1 | Bundle probe (numbers only): pano resolution; collider trimesh load, bounds, watertightness; bounds vs gen_raw.ply splat; spz↔ply correspondence note | ▶ | DONE 07-07 (see log) |
| A2 | **Verify pano camera pose IN THE MESH FRAME** (that's the pair the lift needs; splat only matters for novel views/viewer). A1 numbers suggest mesh = eye-origin +y-up (floor −1.675 ≈ eye height below origin), splat = floor-origin raw (up=−y) — NOT the same frame. Render an equirect from the mesh at origin (depth/normal shading) → side-by-side vs downloaded pano. Fallback: fit yaw/height. Then a separate small check for mesh↔splat offset (needed later for viewer + old-manifest comparison) | ⛔ user judges | TODO |
| A3 | Vocab from prompt.txt nouns (list shown to user) | ▶ | TODO |
| A4 | `seg_pano.py`: equirect→crops (8 yaws × 2 pitches + zoom pass) → GroundingDINO+SAM → pano-coord detections + overlays | ⛔ user judges overlays | TODO |
| A5 | `lift_pano.py`: mask rays ∩ collider → 3D boxes → merge → manifest (base schema) + overlays + viewer scene. RISK: trimesh ray speed without embree → subsample | ⛔ user judges boxes in viewer | TODO |

### Session B — recall net (stage 5)

| # | Step | Gate | Status |
|---|------|------|--------|
| B1 | ~~Florence-2/RAM tags → re-run delta~~ **PULLED FORWARD into A4 (user 07-07: get all names from prompt AND image, look for them all at once).** tag_crops.py (Florence-2 <OD>, names only, min-2-crops filter vs hallucination) → union with prompt vocab → ONE detection pass → ONE lift. Staged prompt-only run was kept as the verified baseline | ⛔ overlays | MERGED into A4 |
| B2 | Mesh-residual audit → leftover blobs + `mesh_explained_pct`; blob crops identified (VLM); novel splat views for occluded blobs | ⛔ user reviews blob verdicts | TODO |

### Session C — enrichment + verdict (stages 6–7)

| # | Step | Gate | Status |
|---|------|------|--------|
| C1 | VLM inventory diff + per-object enrichment + relations → extended manifest | ▶ then ⛔ spot-check descriptions | TODO |
| C2 | Old vs new comparison artifact (render-based manifest vs pano-based) on bedroom_marble: object count, labels, box plausibility, completeness score | ⛔ user verdict → default path for marble scenes | TODO |

## Open questions / parked

- VLM choice (API vs local Qwen2.5-VL) — user decision, affects Session C (+1
  session if local).
- Second marble scene (playroom prompt) after the bedroom path is proven.
- Non-marble backends: HW1 emits its own pano → stages 1–3 apply with
  splat-depth standing in for the collider; Florence-2/RAM becomes the primary
  name source there (no prompt.txt). Out of scope until marble works.
- Per-gaussian splat segmentation (assign gaussians to objects via the same
  rays) — natural extension, park until boxes are good.
- SAM → SAM 2 upgrade — modest single-image gain, don't churn working code.
- Week-8 data location: out/ stays under week7/entangled_gen/out via paths.py
  (week folders are data-only anyway); revisit only if it grates.

## A2b RESOLVED 2026-07-07 late — pano↔splat transform (user + numeric)

**p_raw = (x_pano, −y_pano − 1.31, z_pano)** — mirror-y + shift; splat and
collider share orientation, the PANO is the mirrored export (real Marble
artifact, user-verified on full pano vs splat). Height 1.31 measured from
floors (viewer's 1.6 was 29 cm off — boxes floated). Numeric residual:
rug/yoga-mat bottoms within 8 mm of the splat floor density peak (y_raw
0.006). Remaining visual "float" on bed/desk = visible-surface boxes
(occluded undersides) — module-4 candidate: snap floor-standing objects to
floor_y. Discovery detour: crop_pano crops are L-R MIRRORED vs the true
pano (r3.Cam right-axis convention; crop-vs-slice corr 0.76 mirrored vs
0.51 direct) — internally consistent (masks↔rays same mapping, manifest
unaffected) but a cosmetic fix + re-run is queued for the module-2 cleanup.
Viewer additions: serve.py `?man=<variant>` manifest switch + index.html
passthrough; manifest_pano_to_raw.py emits panoraw_{a,b,c}; **panoraw_c =
the verified transform** (viewer: ?scene=bedroom_marble&man=panoraw_c on
:8321). USER: boxes aligned in viewer.

## Frame relations of a Marble bundle (measured 2026-07-07, bedroom scene)

All three exports describe the SAME world in DIFFERENT undeclared
conventions (no metadata in the download — reverse-engineered here):

| Export | Convention (measured) | Scene-dependence |
|---|---|---|
| splat (.spz→ply) | floor-origin, up=−y ("raw") | fixed convention |
| collider (.glb) | camera-origin, mirror-y of the pano frame | fixed convention |
| pano (.png) | equirect with the OPPOSITE longitude direction vs our sampler → reads as a left-right mirror | fixed convention |
| camera height H | pano/mesh camera sits H above the floor; splat origin = floor ⇒ raw = (x, −y−H, z) of pano | **PER SCENE** (bedroom: H=1.31) |

H is auto-derivable, no eyes needed: H = −mesh_floor_y (pano frame, from
collider bounds; 1.34 here) or refined by the splat in-room floor density
peak (1.31; the 3 cm gap = collider-vs-splat floor discrepancy). VERIFY ON
SCENE 2 which fixed conventions actually hold across scenes.

LONG-TERM (module-3 hardening, user's suggestion): replace convention
knowledge with direct GEOMETRY REGISTRATION splat↔mesh — search the 8
axis-sign hypotheses + vertical shift minimizing splat-to-mesh distance.
Zero assumptions, zero eyes, per scene. The manual detective work of
2026-07-07 was this algorithm executed by hand.

## NEXT SESSION (user request 2026-07-07 close): RUN IT END TO END

Goal: one clean E2E run of the pipeline, bundle → viewer, no hand-holding.

1. **Write `run_scene.py`** (thin orchestrator, module boundaries intact):
   bundle path in → vocab (prompt ∪ tags) → crops → seg → lift → manifest
   variants → prints the viewer URL. Each module stays independently
   runnable; the orchestrator only chains their CLIs.
2. **Fix the crop mirror first** (crop_pano right-axis convention; masks↔rays
   stay consistent either way, but crops become human-readable) — then the
   E2E run regenerates everything cleanly from scratch.
3. **Target scene: a SECOND Marble bundle (playroom prompt)** — proves
   scene-generality + tests which frame-relations-table conventions are
   truly fixed vs per-scene. ⛔ USER: download the playroom bundle from
   Marble into in/<name>/ (spz + collider + pano + prompt.txt), then write
   out/<scene>/bundle_path.txt (one line, bundle folder path).
   Fallback if no new bundle: re-run bedroom_marble E2E from bare inputs.
4. Gates: same dev-time checkpoints (pose sanity via the yaw-scan number,
   detection overlays, viewer boxes) — full artifact paths listed at every
   gate per the standing rule.

Pickup facts: viewer = `python viewer/serve.py --scene <sc> --port 8321`,
URL `?scene=<sc>&man=panoraw_c`. Marble transform: pano→raw = (x, −y−H, z),
H auto-derived from mesh floor_y (manifest_pano_to_raw.py default). All
code pushed (master 531f8fb; secret-fix history rewrite done, old HF token
revoked). HF login NOT needed (all pipeline models cached/public). Windows
python rule: NEVER let pip upgrade torch (2.6.0+cu124; use --no-deps).

## Status log

- 2026-07-07: v1 plan written (pano+collider+prompt.txt as substrates).
- 2026-07-07 (later): v2 rewrite after design discussion — two-layer
  identification (locate → audit → enrich), Grounded-SAM assembly line
  confirmed as the industry-standard shape (we already run workers 2+3),
  completeness audit via mesh residual, VLM enrichment layer, extended
  manifest schema. User go 2026-07-07 evening: "do it, let's try" —
  Session A begins. Nothing executed yet.
- 2026-07-07 A1 DONE (probe_marble_bundle.py, scratchpad; trimesh 4.12.2
  installed to Windows python). Findings:
  - pano 4608x2304 RGB, exact 2:1 equirect ✓
  - collider: 1 geometry, 83,738 verts / 167,323 faces, NOT watertight
    (surface shell — fine for ray-hits; rays may leak through open windows/
    doorways: treat no-hit rays as "outside", don't crash). Bounds
    lo[-2.08,-1.68,-1.04] hi[2.67,1.34,4.95] → 4.75 × 3.02 × 5.99 m,
    plausible metric room ✓
  - splat gen_raw.ply 107.5 MB, 1,228,254 gaussians (opacity≥0.3);
    p1[-1.94,-2.79,-0.94] p99[2.46,0.03,4.18]
  - **FRAME FINDING: mesh and splat are NOT in the same frame.** x/z agree
    under IDENTITY (not rot180Z!), but y disagrees: mesh y∈[-1.68,1.34]
    (floor 1.68 below origin ≈ EYE-ORIGIN, +y up, eye height 1.68 —
    consistent with glTF +y-up) vs splat y mass ∈[-2.8,0.03] (floor≈y0,
    up=−y raw ⇒ FLOOR-ORIGIN — consistent with viewer/serve.py note
    "marble: floor-origin, eye at +1.6" and the 07-07 ladder probes around
    y=−1.6). Likely relation: y-flip + ~1.6-1.7 m shift, x/z unchanged —
    but percentiles are floater-contaminated; A2 verifies visually.
  - spz 27.6 MB (no decoder; gen_raw.ply is its conversion — counts/bounds
    consistent with a room-scale scene, deeper check not needed now).
  Consequence for A5: lift in the MESH frame (pano pose likely origin/eye
  there); convert manifest to the splat/raw frame only at write-time once
  the mesh↔splat offset is verified in A2's second check.
- 2026-07-07 A2 artifact prepared (a2_pose_check.py, scratchpad; embreex
  installed — trimesh embree backend works, 663K rays in seconds). Numbers:
  origin cast hit rate 99.9% (origin is inside the room); depth median
  1.67 m ≈ the A1 eye-height figure; yaw scan peak at 359.7° ≈ 0 offset —
  equirect convention (center=+Z, θ→+X, v0=up) appears to match Marble's
  with identity yaw. Panel for user: out/bedroom_marble/pose_check/
  pano_vs_mesh.png (pano / mesh headlight render / blends at 0 + best yaw).
  NOTE: existing views/gpu_yaw*.json show the prior session rendered the
  splat from cam (0,+1.6,0) up=+y — inconsistent with A1 splat bounds
  reading; mesh↔splat check (A2b) still open.
- 2026-07-07 **A2 RESOLVED in 3 rounds (user-verified)**. Round 1
  (identity): user — upside down. Round 2 (rot180Z): wrong — a rotation
  also mirrors left-right; user caught that the truth is a REFLECTION
  through the ground plane, not a rotation ("flipped through the world xy
  plane, not rotated 180 like the splat"). Round 3 (mirror-y only,
  diag(1,-1,1)): **user: aligned**; yaw scan peak at exactly 0 px, score
  2.66 (vs 1.92 / 1.63 wrong orientations — sharp peak only in the correct
  one). **VERIFIED POSE: pano camera at mesh origin; p_pano = diag(1,-1,1)
  · p_glb (glb is mirrored through the ground plane — handedness flip);
  zero yaw; equirect convention image-center=+Z, θ toward +X, v=0 up.**
  In the corrected (pano) frame the mesh spans y ∈ [-1.344, +1.675] →
  floor 1.34 below eye, ceiling 1.68 above, room height 3.02 m.
  CONSEQUENCES: (a) A5 ray-caster must apply the same mirror to the mesh
  before casting; face-normal/winding handedness flips with it (shade with
  |n·d|, orient normals toward the ray origin when needed). (b) A2b
  hypothesis: splat raw frame = pano frame via rot180Z + y-offset ≈ floor
  level — verify when the viewer/comparison needs it, does not block A3-A5.
  Panels kept: pose_check/pano_vs_mesh_round{1_identity,2_rot180z,3_mirrorY}.png.
- 2026-07-07 A3+A4 EXECUTED (user: "best judgment, pipeline not job-specific").
  New pipeline files in the repo: vocab_from_prompt.py (spaCy noun-chunk
  extraction, generic STOP list + STAPLES; bundle found via
  out/<scene>/bundle_path.txt — one line, path to the download folder),
  crop_pano.py (equirect→pinhole crops + gpu_*.json-format sidecars; rig
  8×fov75@pitch0 + 8@−40 + 4@+40, 960px ≈ native pano density so NO zoom
  pass needed at 4608-wide panos), seg_pano_overlay.py (gate artifacts),
  paths.py += pano_crops_dir/seg_pano_dir. spaCy + en_core_web_sm and
  embreex installed to the Windows python. seg_views.py ran UNMODIFIED on
  the 20 crops (--views-dir/--glob/--out-dir/--prompt). Vocab (22 terms):
  bed. bookshelf. book. side table. shelf. basket. toy. desk. window.
  office chair. computer monitor. desk lamp. picture. air conditioner. rug.
  yoga mat. plant. ladder. door. pillow. curtain. ceiling light.
  Result: 172 detections ≥0.35 across 20 crops (dupes expected — crops
  overlap; 3D merge dedups in A5). Histogram top: book 53, shelf 29,
  door 17, bookshelf 15, toy 10 … NOTE door=17 smells like false positives
  (wardrobe/window panels reading as "door") — user's eyes will tell.
  MISSING at ≥0.35: yoga mat, picture (both in vocab) — check overlays.
  ⛔ A4 GATE OPEN: seg_pano/pano_overlay.png + crops_boxes.png sent to user.
- 2026-07-07 (cont.) USER: outlines good. B1 pulled forward per user (one
  unified name pass instead of stages). tag_crops.py added (Florence-2 <OD>
  via the NATIVE transformers 5.x implementation — use
  florence-community/Florence-2-base; microsoft/'s repo ships stale remote
  code that crashes on 5.x). INCIDENT: pip deps for Florence (timm) silently
  replaced torch 2.6.0+cu124 with 2.12.1+cpu — restored from the cu124
  index; RULE saved to memory (windows-python-env): --no-deps or verify
  torch after any pip install into the Windows python. Tag hygiene added
  (all generic): STOP += house/person/face/... (scene words, people);
  NORMALIZE += bookcase→bookshelf, houseplant→plant, cabinetry→cabinet;
  union drops word-subset tags (table ⊂ side table). Florence tags on 20
  crops (min-2-crops filter) → exactly 1 genuinely new name: **cabinet**.
  UNIFIED PASS (23 terms): 168 detections ≥0.35. Deltas vs prompt-only run:
  yoga mat now detected (1 crop, threshold luck); cabinet found NOTHING
  ≥0.35 (Florence's cabinetry = hallucination or sub-threshold — the B2/C1
  audits arbitrate); picture still 0 (wall art everywhere per prompt —
  known detector weakness, prime recall-net case); door still 17 (staple
  suspicion stands). ⛔ A4 GATE (round 2) OPEN.
- 2026-07-07 (cont.) USER on ac_check.png: the AC detections are a REAL
  in-room unit — **the scene has TWO ACs (Marble added one beyond the
  prompt's window-mounted unit)**. Nice validation of observation-beats-
  intent + a manifest test case (expect 2 AC objects). User also flagged
  laundry/canvas draped over shelves (naming failure — neither prompt nor
  Florence named them; Florence's 1-crop 'box'/'cupboard' guesses were cut
  by the min-2 filter; the C1 strong-VLM inventory is the systematic fix)
  and the uncaught wall pictures. EXPERIMENT (targeted pass, thr 0.22,
  picture synonyms): **"picture" was a WORDING failure, not a detector
  failure** — "painting" hits the same wall art at 0.41-0.49, ~8 frames on
  the gallery wall; "wall art" returns whole-wall region blobs (dropped).
  FIXES (generic): EXPAND synonym mechanism in vocab_from_prompt
  (picture→painting/picture frame/poster; canonicalize() maps labels back,
  handles GD token-concat labels like "picture frame photo"); seg_views
  gained --box-thr; anti-blob rule (drop detections covering most of a
  crop) goes into lift_pano. Final unified vocab = 26 words incl.
  synonyms. Re-running the full pass; overlay to user next.
- 2026-07-07 FINAL PASS: 198 detections; picture 0→27 (canonical). USER
  DIRECTION: keep pipeline pieces MODULAR — module 1 NAME (vocab_from_
  prompt + tag_crops; later + VLM inventory/recall loop), module 2
  FIND+SEGMENT (crop_pano + seg_views — takes ANY word list), module 3
  LIFT (lift_pano), module 4 AUDIT+ENRICH (later; autonomous recall-loop
  design discussed and logged — propose/verify/reconcile to fixpoint,
  contradiction set instead of human eyes; human gates are DEV-TIME ONLY).
- 2026-07-07 **A5 EXECUTED — E2E COMPLETE** (lift_pano.py): 198 detections
  → mask rays ∩ collider (embree, glb mirrored to pano frame per A2) →
  depth-trim → greedy label+IoU3D merge → **97 objects,
  scene_manifest_pano.json** (frame "pano"; render-path
  scene_manifest.json left untouched for C2). Sizes metrically sane:
  doors 1.0×2.2 m wall slabs, monitor 0.53×0.33×0.07, AC 0.69×0.49 by the
  window, rug 2 cm thick, wall pictures 1-2 cm deep on the wall plane.
  Label mix: book 25 (shelf ROWS granularity), picture 16, shelf 16,
  door 7, bookshelf 5, basket 5, toy 5 … bed/chair/monitor/side table/
  yoga mat ×1. Fix applied: canonicalize() needs the module-1 vocab
  (reads prompt + tags.json) to collapse GD token-concat labels.
  KNOWN OPENS for module 4: only 1 of the 2 ACs became an object;
  cabinet unresolved; laundry/canvas unnamed; shelf-vs-bookshelf spatial
  duplicates (label-blind dedup); door×7 plausibility = user's eyes.
  ⛔ A5 GATE: manifest_overlay_pano.png + manifest_plan_pano.png sent.
- 2026-07-07 **A5 GATE PASSED** — user: "looks correct for now, needs
  improvement but lets do that later." SESSION A / CORE PATH COMPLETE
  E2E (bundle → names → detect/segment → lift → 97-object metric
  manifest). NEXT when resumed: (a) A2b mesh↔splat offset (unblocks
  viewer display of these boxes over the splat + C2 comparison),
  (b) module 4 recall loop (autonomous discovery — design in the
  2026-07-07 log entries; VLM choice API-vs-local still open),
  (c) known-opens list from the A5 entry (2nd AC, cabinet, laundry,
  label-blind dedup, door×7 audit), (d) second marble scene (playroom)
  to prove scene-generality.
- 2026-07-14 **run_scene.py WRITTEN + CLEAN E2E RUN** (the 07-07 "NEXT
  SESSION: RUN IT END TO END" step 1). `run_scene.py` = thin subprocess
  orchestrator, chains crop_pano → vocab_from_prompt → seg_views (--views-dir
  pano_crops --glob "pano_*.webp" --out-dir seg_pano --prompt <vocab>
  --box-thr 0.35) → seg_pano_overlay → lift_pano → manifest_pano_to_raw;
  imports only paths.py, each module stays independently runnable; --skip
  <stages> to reuse GPU outputs; stops on first nonzero rc; prints per-stage
  summary + viewer URL. Persists the GD vocab to seg_pano/vocab.txt.
  Ran clean on bedroom_marble from bare inputs in **59 s** (subagent, to keep
  logs out of context): 20 crops, 25-term vocab, **199 detections in 19/20
  crops** (pano_y180_pp40 = up-look, 0 dets), **98 objects** →
  scene_manifest_pano.json, panoraw_{a,b,c} variants. Reproduces the 07-07
  hand-run (97→98, i.e. 198→199 dets). Lift stats: mesh floor −1.34 ceil 1.67
  (matches A2 pose), 0 dropped (weak/blob/thin), **31.0% of mesh surface area
  claimed** (the free completeness metric module 5 wanted). VLM DECISION
  RESOLVED (user 2026-07-14): **use Claude as the VLM surrogate instead of an
  API / local Qwen** — for module-4 audit+enrichment AND the "observation"
  naming (can replace Florence). run_scene.py is NEW + UNCOMMITTED (naming
  stage currently = vocab_from_prompt only; Florence/surrogate top-up not
  wired into the orchestrator yet). NOT done this session: crop mirror fix,
  module 4, second scene. Viewer launched + verified (HTTP 200) then stopped.
