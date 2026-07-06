# Overnight session 2026-07-04 → 07-05 — what we did, what we got, what's next

> **Layout note (2026-07-05 evening):** `out/` has since been reorganized into
> per-scene folders (`out/<scene>/...`, see `out/README.md`); path mentions below
> use the old flat naming.

> Start-here doc for the next session. Everything below is on disk and re-runnable.
> Companion: `out/report.html` (all-scene visual comparison), `README.md` (repo/run
> mechanics), `out/queue.log` + `out/queue2.log` (run history).

## TL;DR

- **8 scenes generated** (0 failures), all auto-extracted to object manifests +
  LLM composition packages.
- **The full pipeline closed end-to-end twice**: text → splat → views → seg → lift →
  package → LLM composes placements → machine constraint check → render. Playroom
  (4 placements, all PASS) and bedroom (incl. one veto-revise cycle).
- **Big finding: the generator's spatial incorrectness is STRUCTURAL.** The
  empty-box control room has the *worst* geometry of all 8 scenes. Photorealism and
  geometric correctness are fully decoupled ("looks right, measures wrong").
- **Spatial/dimensional prompting helps a little** (~+10 pp floor coverage,
  seed-variance 0 pp) — mitigation, not fix.
- **Built a debugging/tooling suite**: live 3D viewer (inspect/measure/place),
  habitable-envelope maps, placement probe, spot suggester, scene prep, report gen.
- **Desk-into-bedroom placement was geometrically impossible** — no legal 1.2 m spot
  exists in that room (max placeable ≈ 0.8 m). Task parked for a joint design
  session, now with the data to have it.

## 1. What ran overnight

| batch | scenes | result |
|---|---|---|
| queue 1 (further scenes) | bedroom, livingroom, kitchen | all rc=0, ~65 min each |
| queue 2 (spatial-prompting experiment) | ctrlroom (empty-box control), bedroomdim (explicit meters), livingspatial (explicit relations), bedroom_s1 (same prompt as bedroom, seed 1) | all rc=0 |

Auto-extraction after each batch (`post_queue.ps1` / `post_queue2.ps1`): 4-yaw GPU
views → GroundingDINO+SAM seg → depth-lift manifest → composition package. Then
`scene_ready.py --all` added viewer payloads + envelopes for everything.

## 2. The experiment: does spatial prompting fix spatial correctness?

Metrics from the habitable envelope (floor coverage = % of room area with
detectable floor; warp = local floor height spread, flat real room ≈ 0):

| scene | prompt lever | floor coverage | warp p5..p95 (m) |
|---|---|---|---|
| **ctrlroom** | empty box, "rectangular, flat ceiling" | **15% (worst)** | **−0.32..+0.43 (widest)** |
| playroom | baseline | 19% | ..+0.43 |
| bedroom | baseline | 30% | −0.05..+0.38 |
| bedroom_s1 | same prompt, seed 1 | 30% | −0.08..+0.38 |
| bedroomdim | + explicit dimensions | 39% | −0.03..+0.43 |
| kitchen | baseline | 35% | +0.03..+0.43 |
| livingroom | baseline | 38% | −0.17..+0.38 |
| livingspatial | + explicit relations | 48% | +0.12..+0.43 |

**Readings:**
1. **Structural failure.** The most explicitly-spatial prompt (empty rectangular
   room) produced the worst geometry. Likely mechanism: the pipeline's monocular
   depth (ZoeDepth) collapses on textureless white surfaces — emptiness *hurts*.
   Prompting cannot fix this. Killer figure pair:
   `out/views_ctrlroom/gpu_yaw000.webp` (looks clean/photoreal) vs
   `out/envelope_ctrlroom_heatmap.png` (geometry is garbage).
2. **Prompting still helps**: +9 pp (bedroomdim vs bedroom) and +10 pp
   (livingspatial vs livingroom), while seed variance is 0 pp (bedroom_s1 ==
   bedroom). Real, repeatable, modest. Warp unchanged everywhere.
3. Caveat: warp values clip at the ±0.45 m local-floor search band (several scenes
   hit +0.43) — true warp may exceed reported.

## 3. Pipeline status (all stages proven)

1. text → splat: SceneDreamer360, WSL, stable (README has the full patch/crash log).
2. splat → views: week5 `shot.py` (splat-transform GPU), camera sidecars per shot.
3. views → 2D objects: `seg_views.py` (GroundingDINO+SAM; per-room vocab or
   `--prompt`; any scene name).
4. 2D → 3D manifest: `lift_views.py` (fast z-buffer depth at sidecar cams,
   median/IQR mask trim, label+IoU3D cross-view merge) → `out/scene_manifest_<sc>.json`
   + ID-annotated box overlays on the photoreal views (the verification artifact —
   plan views alone are not useful).
5. manifest → LLM package: `agent_package.py` → `out/package_<sc>/` (GUIDE.md:
   frame + object table + occupancy grid + OUTPUT CONTRACT). Consumed by Claude to
   compose placements; `render_proposal.py` machine-checks the 5 constraints and
   renders proposals. **Two-stage lesson: JSON constraints = legality; VLM look at
   proposal renders = taste. Both needed** (bedroom v1 passed numerically, failed
   visually; v2 passed both).
6. asset placement (splat surgery): `splat_place.py` — cut real object gaussians by
   AABB from one splat, translate+scale into another (verified); **yaw rotation has
   a known quaternion-convention bug (spiky render) — avoid `--yaw`**.

Extraction is generator-agnostic: the same seg+lift ran unmodified on the REAL
week5 SuperSplat playroom (desk found in 5 views → obj_009).

## 4. Tool inventory (all in this folder)

| tool | what it does | run |
|---|---|---|
| Live viewer | multi-scene 3D inspector: point cloud, manifest boxes, clearance floor overlay, click-to-inspect (metric info panel), click-to-place → writes live placement file, arrow-nudge/rotate, measure tool (M), camera bookmarks (B → shot.py cmd), capture (C → `out/viewer_caps/latest.png` for LLM feedback) | `python viewer/serve.py --scene bedroom --port 8321` → http://localhost:8321 (dropdown or `?scene=X`) |
| `envelope.py` | habitable envelope: per-5 cm-cell LOCAL floor height + clearance; heatmap + warp map; `check_placement()` API | `python envelope.py --scene X` |
| `splat_probe.py` | "why can't I place here": floor/clearance/nearby objects + verdict at any (x,z) | `python splat_probe.py --scene X --box=cx,cz,W,H,D` |
| `suggest_spots.py` | inverse probe: ALL legal spots for a W×H×D box, ranked, NMS; `--write-live` shows ghosts in viewer | `python suggest_spots.py --scene X --size 1.2x0.75x0.6 --write-live` |
| `splat_clean.py` | floater census/cull (bedroom: 33 k dark opaque gaussians shrouding the rig = the black blobs) | `python splat_clean.py --ply out/gen_X_raw.ply [--cull-dark --out ...]` |
| `scene_ready.py` | idempotent per-scene prep: lift→package→viewer payload→envelope | `python scene_ready.py --all` |
| `make_report.py` | rebuilds `out/report.html` (all scenes: prompt/views/plan/envelope/metrics) | `python make_report.py` |
| `splat_place.py` | asset cut+place between splats (yaw broken) | see §3.6 |
| Live placement files | the LLM/user edit these; viewer updates in 0.5 s | `out/live_placement_<scene>.json` |

Gotchas burned tonight: PS 5.1 + non-ASCII in .ps1 (keep ASCII); argparse negative
values need `--flag=value`; `clocks` lock resets on reboot (`nvidia-smi -lgc 300,1500`
elevated, before ANY gen run); black "holes" with soft edges = floater gaussians,
sharp edges = true no-data.

## 5. Placement post-mortem (why the desk kept failing)

Three numerically-legal desk placements failed in reality: (1) inside a
floor-to-ceiling curtain (unmanifested), (2) inside an unmanifested wardrobe front,
(3) sunk 27 cm into the warped floor. Then `suggest_spots` proved **no legal 1.2 m
desk spot exists in the room at all** (0.8 m → exactly 2 spots; 0.4 m → many).
Lessons now encoded in tools: object footprints ≠ free space (need the envelope);
manifests miss soft/planar volumes (curtains, closet fronts); bottom-align must use
LOCAL floor height. The 4-yaw rig also has diagonal blind wedges — the veto pass
missed the curtain corner.

## 6. Next steps (decision needed, then mechanics)

**The strategic fork (user decision):**
- **(a) Accept the envelope** — compose small objects (≤0.8 m) in generated rooms;
  works today, demonstrates the full loop.
- **(b) Attack the generator** — trial LayerPano3D (quality-leader fallback, torch
  2.4, FLUX 12B pano is heavy on 12 GB); days of infra.
- **(c) Shift eval weight to the real-scan leg** (extraction already proven there)
  and use the generated-leg failure analysis as a paper contribution in itself.
- Recommendation on the table: **(c) + (a)** now, (b) if time allows.

**Parked jointly (do NOT resume unilaterally):** desk-into-bedroom placement — the
design session should decide the viewer-in-the-loop placement flow (suggest_spots →
ghosts → human/VLM pick → splat surgery → render).

**Mechanical debt (any time):**
- Fix `splat_place.py` yaw quaternion convention (test against splat-transform).
- Envelope: widen/de-clip the floor-search band; treat curtains/planar soft volumes.
- Render-test `splat_clean --cull-dark` (needs GPU; before/after the black blobs).
- Multi-view mask association in lift (bed was 1-view → box underestimates); buffer
  manifest boxes in the composer contract; doors/windows as keep-clear zones.
- Viewer nice-to-haves: info panel click needs a real-browser test; drag-to-move.

**Paper hooks from tonight:** structural-vs-prompt spatial correctness result +
metric (floor coverage / warp from the envelope); "looks right, measures wrong"
decoupling; manifest-vs-envelope free-space distinction; two-stage
legality/taste composition; provenance-free extraction symmetry (real vs generated).
