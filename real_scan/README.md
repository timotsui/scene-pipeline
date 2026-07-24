# real_scan — real-scan leg (formerly week5/splat_to_placement)

> **Module note (2026-07-05):** copied into scene-pipeline as the real-scan
> module. CODE ONLY — `data/` (3.9 GB), `triage*/`, `outputs/`, `views/` stay in
> `CS-8903-OVM/week5/splat_to_placement/` (scripts here still assume a local
> `data/` — wire paths up when this module is actively resumed). The realplayroom
> scene is ALSO served by `entangled_gen/` via its `local_paths.json` week5 root.
> Frame caveat: this predates the 2026-07-05 coordinate-frame resolution — see
> `../entangled_gen/PIPELINE.md`; realplayroom's manifest needs re-lifting there.

# splat_to_placement — OVM pipeline workspace (original doc)

Take a Gaussian splat of a room → a **grounded scene representation** → object **placement**,
to compare against **GLTS** (we replace GLTS's cold-from-text scene-graph proposal with a
splat-grounded one). Full rationale: `../DIRECTION_extraction-bridge_2026-06-22.md`.

**Principle (memo §13):** cleaning/canonicalization is *adapter work, not the contribution*.
Keep it minimal + off-the-shelf. The contribution is the source-agnostic core (perceive → extract → place).

## Sources (two, satisfies the ≥2-source eval mandate, memo §13)
- **WORKING / perception PoC = `data/superspl/playroom.ply`** — SuperSplat "Playroom", **full export**
  (3,548,374 g, **full SH** f_dc+f_rest_0..44, standard INRIA schema). **USED RAW — no clean step**
  (user decision 2026-06-22: scene looked best untouched; our SOR/opacity pass was too aggressive, dropped 45%).
  It is **Y-up + slightly tilted** — DON'T rewrite the file; compute up-vector / camera orientation on the fly
  when a top-down is needed (non-destructive). Real-capture lane: **no GT**. Source/license: SuperSplat scene —
  CONFIRM license before paper use. (Our own SOG decoder `decode_sog_zip.py` produced a lower-fidelity 2.37M /
  degree-0 version; the manual SuperSplat PLY export supersedes it.)
- **GT / measurement = InteriorGS `0062_839922`** (dining room). Clean, **metric (m), Z-up, + GT labels**
  (`labels.json`: 3D oriented boxes + categories) → no cleaning. `data/raw/InteriorGS/0062_839922/`. Gated HF
  `spatialverse/InteriorGS`. Compressed PlayCanvas → `decompress_interiorgs.py` → `room_uncompressed.ply`.
  (160 single-room scenes triaged; pulled candidates `0182/0143/0028/0202/0089/0160/0096` also in `data/raw/InteriorGS/`.)
- **BACKUP (messy real) = Mip-NeRF360 `room`** in `data/raw/room.ply` (needed `02_clean`). The switch away from
  it is *why cleaning is not central* (§13).

**SOG decode note:** SuperSplat `.sog` = meta.json + webp planes (means_l/u 16-bit pos, scales/sh0 256-codebook,
quats smallest-three w/ alpha=largest-idx). Tiled exports have LOD levels; use only finest (`0_*` tiles).
`decode_sog.py` = loose webps; `decode_sog_zip.py` = zip bundle.

## Layout
```
data/raw/InteriorGS/0062_839922/   InteriorGS scene (compressed ply + GT labels + structure + occupancy)
                                   room_uncompressed.ply = decoded standard 3DGS (USE THIS)
data/raw/room.ply                  Mip-NeRF360 backup (messy real capture)
data/cleaned/                      02_clean outputs (only needed for the messy Mip-NeRF360 source)
outputs/                           renders / visualizations
0X_*.py / decompress_interiorgs.py pipeline stages + InteriorGS adapter
```
All numpy/matplotlib so far — **no CUDA, no install** beyond the base env.

## Stages
| # | Script | Does | Status |
|---|---|---|---|
| 00 | `decompress_interiorgs.py` / `decode_sog*.py` | compressed `.ply` / SOG → standard 3DGS PLY | ✅ |
| 01 | `01_inspect.py` | load PLY (numpy), report geometry/color/opacity, 3 projections | ✅ |
| 02 | `02_clean.py` | *(messy real sources only)* opacity → crop → RANSAC de-tilt. **NOT used** (playroom kept raw). | ✅ |
| 03 | `03_render.py` | CPU splat renderer — **ABANDONED** (4 min/view). Use splat-transform instead. | ✗ deprecated |
| 04 | `04_orbit.py` | orbit renders via splat-transform | ⚠ camera-framing wip |
| 05 | `05_planview.py` | **numpy orthographic PLAN view** — WORKS, complete coverage, returns world extent (=pixel↔world map) | ✅ |

## RENDERING — current state & the open blocker (2026-06-22, resume here)
- **`splat-transform` (npm, installed, GPU works, ~5s/view)** is the real renderer (PlayCanvas engine). Negative
  CLI values **need `=`** (`--filter-value="y,lt,-0.3"`, `--camera=...`).
- **PLAN VIEW is solved via numpy** (`05_planview.py`, `outputs/26_plan_clean.png`): orthographic top-down,
  project onto XZ (Y-up), keep BELOW-ceiling gaussians (`y<-0.1`, drops the offset-Y ceiling that blocks the
  view), paint topmost gaussian per cell. Complete + correct framing + free pixel↔world. Numpy is the RIGHT
  tool for the 2D plan (not a crutch).
- **✅ PERSPECTIVE CALIBRATED (2026-06-22)** — first reliable scriptable interior view found by eye:
  `python shot.py --preset interior` (cam=`-1.5,1.2,-2`, look=`-1.5,1.2,-5`, fov 90), saved as the `interior`
  preset in `shot.py`. These are **ST-space** coords, not raw-PLY / `05_planview` coords.
  - **✅ CENTER STANDPOINT (2026-06-22)** — stepped +0.7 forward (−z) from `interior`, originally
    cam=`-1.5,1.2,-2.7`, look=`-1.5,1.2,-5.7`, fov 90 (saved as `fwd07.webp`). Stands ~map center:
    **playroom behind, staircase/entry ahead**. Canonical standpoint for turn-around panoramas.
  - **✅ RECENTERED PLY (2026-06-22)** — baked the standpoint into the geometry so we never have to remember
    its coords: `splat-transform -w data/superspl/playroom.ply -t 1.5,-1.2,2.7 data/superspl/playroom_centered.ply`
    (translate by T=`(1.5,-1.2,2.7)` = −fwd07). Now **`0,0,0` IS the center standpoint** and `0,0,-3` its forward
    look. `playroom_centered.ply` is the new default `--ply` in `shot.py`; presets `center`/`interior` were
    rewritten into this centered frame. To get back the original ST-space coords, **subtract T**. Verified by
    re-render: `python shot.py 0,0,0 0,0,-3` on the centered PLY matches `fwd07.webp` exactly.
  - **✅ PLAN VIEW (2026-06-23)** — top-down plan on the centered PLY, clipped at the standpoint plane. Two
    parts: (1) look straight down −y from the ceiling side, (2) clip ceiling/upper half with a box capped at
    `y=0` (eye/standpoint height). Shared clip box: `--box=-4.3,-5,-3.3,2.5,0,2.5`. Pan center settled at
    XZ≈(0.5, 0.0). Note `=` syntax so the leading `-` in `--box`/`--up` isn't parsed as a flag. **Two canonical
    variants kept on purpose:**
    - **True plan (near-orthographic, recommended for layout)** — high eye + narrow fov → straight walls, real
      footprint. Saved `views/plan_floor_tight9.webp`.
      ```
      python shot.py 0.5,16,0.0  0.5,-1,0.0  --up=0,0,-1  --fov 17  --box=-4.3,-5,-3.3,2.5,0,2.5
      ```
    - **fov-90 plan (standardized with the perspective/eye-level shots)** — fov 90 forces a low eye (y≈1.2), so
      it's an oblique wide-angle, not flat: walls bow and furniture *sides* show. Saved `views/plan_fov90.webp`.
      ```
      python shot.py 0.5,1.2,0.0  0.5,-1,0.0  --up=0,0,-1  --fov 90  --box=-4.3,-5,-3.3,2.5,0,2.5
      ```
    Not presets (presets store only cam/look/fov, not the `--box`/`--up` that make the plan) → recorded here.
    Centered-frame axes: **ceiling=+y, floor=−y**; in this top-down frame screen-right=+x, screen-down=+z.
    Feathered streaks on the staircase side = the real unscanned capture void, not a clip artifact.
  - The y sign confirms the flip: raw room interior is at *negative* Y (floor Y≈−2.84, ceiling Y≈0), yet the
    working camera sits at *positive* y=+1.2 → consistent with **`(x,y,z)→(x,−y,−z)`** on ST import.
  - ⬜ *Still to pin:* exact x/z mapping (one viewpoint confirms the sign-flip but doesn't fully determine the
    transform). Render 2–3 more shots at varied x/z → back out numpy-world→ST-world so any `05_planview`
    pixel/world coord auto-converts to an ST camera. Until then, perspective views are driven from presets/by eye.

## Key findings / lessons (so we don't re-derive)
- Mean/median "center of mass" can land in a **void** — content is clustered to one side; a 360 pano from the
  mean was mostly empty. Use the **dense floor footprint** center instead: playroom floor center XZ≈(1.25,-1.98),
  span ~4m; ceiling peak at Y≈0; floor at Y≈-2.84.
- Perspective cameras placed from raw coords fight occlusion + ST's coordinate flip → orthographic numpy wins for plan.
- playroom is a **partial real capture** (one side genuinely unscanned = real void, not a framing bug) → InteriorGS
  (complete, metric, GT) is the better workhorse; playroom = the messy-real second source.
## Findings so far (these define the contribution, not bugs)
- **No absolute scale** — COLMAP units are arbitrary (room core ≈ 7×18×5 units). Metric truth must come from the verify layer.
- **Not gravity-aligned** — raw splat is tilted; floor-plane estimation (generic canonicalization) is required. ✅ handled in 02.
- **Floater halo** — full bbox 46×30×60 vs room core ~7×18×5; source-specific, removed in 02 (kept minimal).
