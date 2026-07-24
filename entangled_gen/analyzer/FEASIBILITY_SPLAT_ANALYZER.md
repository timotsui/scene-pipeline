# Feasibility: splat_analyzer as an external detector on our bedroom splat

Date: 2026-07-20 (Step 2 — analyzer-repo-probe, read-only study; no code was run, nothing installed)
Repo clone: `D:\T\Documents\GeorgiaTech\Summer2026\Research\code\reference\splat_analyzer` (github.com/nigelhartman/splat_analyzer, HEAD `a3cd884`)
All file:line references below are relative to that clone.

"Splat" throughout means a 3D Gaussian splat scene file (.ply or .spz). "OWLv2" is Google's open-vocabulary 2D object detector (you give it text labels, it returns 2D boxes). "gsplat" is the nerfstudio CUDA rasterizer library that renders Gaussian splats.

---

## Summary verdict

**YES, we can run it as-is on our PLY, with two caveats.**

1. **Local CLI mode is real and standalone** — `run_local.py` is a thin wrapper over `pipeline.run_pipeline()`; it never imports FastAPI/Docker/server code. One command, writes everything to one output directory.
2. **Caveat 1 — orientation:** the tool applies NO transform to the input splat, but its camera poses are built assuming the splat file is in the standard 3DGS "y-down" frame, i.e. **physical up = file −Y**. Our `gen_raw.ply` raw frame (physical up = −y under the rot180 convention) **matches this assumption directly** — the raw file is likely the right input, NOT a copy rotated to y-up. Must be verified with one cheap `--quality low` run and a human look at the rendered frames (I do not judge images; user does).
3. **Caveat 2 — environment:** torch is deliberately **unpinned**, but the practical no-compile install path pins us to **Python 3.10 + torch 2.4.x + CUDA 12.4** (the only combination with prebuilt gsplat 1.5.3 binary wheels). That is an isolated environment, separate from the off-limits Windows system python (torch 2.6.0+cu124). Recommendation: WSL Ubuntu-24.04 conda env (details below).

Output boxes come back in the **input file's native coordinate frame and units** (no recentering, no rotation, no normalization), so they are directly comparable to our own 3D boxes with no frame conversion beyond what we already track for gen_raw.ply.

---

## a. Local CLI — exact command

Entry script: `run_local.py` (repo root). It parses args, checks the file exists, warns if CUDA is absent, and calls `pipeline.run_pipeline()` — see `run_local.py:24-58`. It imports only `torch`, `pipeline`, `config` (`run_local.py:18-21`); no FastAPI/server code touches this path, so local CLI mode truly exists standalone.

```
python run_local.py --ply <scene.ply> --prompt "bed, chair, table, lamp" ^
    --quality high --job_dir <absolute output dir> ^
    --score_threshold 0.12 --min_votes 8 --min_peak_score 0.40
```

Flags (all defined at `run_local.py:27-34`, defaults from `config.py`):

| Flag | Default | Meaning |
|---|---|---|
| `--ply` | required | Path to `.ply` or `.spz` splat |
| `--prompt` | required | Comma-separated labels, e.g. `"chair, table"`. Each label is wrapped as `"a photo of a {label}"` for OWLv2 (`pipeline.py:160`) |
| `--quality` | `medium` | Camera-count preset: `low`=24, `medium`=90, `high`=192 views (`config.py:17-22`) |
| `--job_dir` | `./out_<name>` relative to CWD (`run_local.py:45`) | Pass an absolute path |
| `--score_threshold` | 0.12 | OWLv2 per-frame confidence cutoff (`config.py:45`) |
| `--min_votes` | 8 | A cluster must contain detections from ≥ this many frames (`config.py:46`) |
| `--min_peak_score` | 0.40 | Cluster's best single-frame score must reach this (`config.py:47`) |

Not exposed on the CLI: render resolution (512×512, `config.py:28-29`), renderer choice (`auto` → gsplat on CUDA, `renderers/__init__.py:36-45`), and the camera-placement parameters (`config.py:37-42`). Changing those means editing `config.py` or calling `pipeline.run_pipeline()` with a custom `PipelineConfig`.

Environment variable: `WMD_DEVICE=cuda|mps|cpu` overrides the device for OWLv2 only (`pipeline.py:34-44`). The renderer always needs CUDA (`renderers/gsplat_backend.py:23-28`); there is no CPU rasterizer (`renderers/__init__.py:40-45`).

One run also downloads the OWLv2 model `google/owlv2-base-patch16-ensemble` from HuggingFace on first use (`pipeline.py:146-147`), roughly 1.5–2 GB into the HuggingFace cache (redirect with `HF_HOME` if desired).

## b. Dependencies

From `requirements.txt:9-22` (the CUDA/server set; `requirements-mac.txt` is Mac-only and irrelevant):

```
fastapi==0.138.0            # server only — NOT needed for run_local.py
uvicorn[standard]==0.49.0   # server only — NOT needed for run_local.py
python-multipart==0.0.32    # server only — NOT needed for run_local.py
torch                       # UNPINNED — intentional, see below
torchvision                 # UNPINNED
gsplat==1.5.3
transformers==4.50.3        # OWLv2
numpy<2
imageio==2.37.3
plyfile==1.1.3
opencv-python-headless==4.11.0.86   # imported by pipeline.py:26 (import required even though unused)
Pillow
scipy==1.15.3               # cKDTree for camera placement
six==1.17.0
```

Key facts:

- **torch is deliberately unpinned** — the comment at `requirements.txt:5-8` says local installs should install a CUDA-matched torch FIRST, then the rest. The deployed server ran torch 2.1.0+cu121 (`Dockerfile:2`), so the code itself is not version-sensitive.
- **gsplat==1.5.3 ships NO compiled binaries on PyPI.** Verified via the PyPI API (2026-07-20): the only wheel is `gsplat-1.5.3-py3-none-any.whl` (pure Python) plus an sdist, and its dependencies include `ninja` — meaning the CUDA kernels are **JIT-compiled at first use** (needs nvcc + a C++ compiler at runtime), not at `pip install`. The README's line "gsplat compiles CUDA extensions on install" (`README.md:80`) describes the sdist path; the wheel path defers compilation to first run.
- **Prebuilt binary wheels DO exist** on the official index `https://docs.gsplat.studio/whl/pt24cu124/gsplat/` (verified 2026-07-20): `gsplat-1.5.3+pt24cu124-cp310-cp310-linux_x86_64.whl` **and** `gsplat-1.5.3+pt24cu124-cp310-cp310-win_amd64.whl`. Only combo available for 1.5.3: **torch 2.4 + CUDA 12.4 + Python 3.10** (`pt25cu124` and `pt26cu124` indexes return 404). This is the zero-compilation path on either OS.
- **transformers 4.50.3** for OWLv2 (pinned; matches on both requirements files).
- **Nothing is Linux-only.** fastapi/uvicorn/python-multipart are server-mode-only and can be skipped for the CLI; every remaining package has Windows and Linux wheels. `TORCH_CUDA_ARCH_LIST=8.9` (RTX 4080, per `README.md:192-199`) only matters if gsplat is compiled from source; the prebuilt wheel makes it moot.

## c. Camera "ring" — actually a density-aware sampler + panoramic sweeps

The README's marketing framing ("camera ring") is inaccurate. What the code does (`render_cameras.py`):

1. **Standpoint selection** (`render_cameras.py:290-411`, `_generate_camera_positions`): camera positions are sampled **inside** a robust bounding box of the splat point cloud (1st–99th percentile per axis rejects floater outliers, `render_cameras.py:310-312`, `config.py:37-38`). Each candidate's local splat density is measured with a KD-tree (built on ≤300k subsampled splats, `render_cameras.py:264, 317-330`); candidates are accepted by a **Gaussian band-pass on density** — rejecting both positions buried inside geometry and positions in empty void, favoring the "content-adjacent shell" (`render_cameras.py:333-357`). A Poisson-disk minimum separation (0.12 × bbox diagonal, `config.py:39`) spreads standpoints apart. Fallbacks: 3 relaxation rounds → farthest-point fill → legacy circle around the scene center (`render_cameras.py:361-399`). Deterministic (seed 42, `config.py:42`).
2. **Views per standpoint** (`render_cameras.py:414-440`, `_build_poses`): a full panoramic grid — `n_azimuth` headings × `n_elevation` tilts. Azimuths cover 0–360° evenly. Elevations are `linspace(−55°, +40°)` where the look direction's **file-frame Y component = sin(elevation)** (`render_cameras.py:422, 430-434`).
3. **Counts** (`config.py:17-21`): low = 3 standpoints × 4 az × 2 el = 24 frames; medium = 5×6×3 = 90; high = 8×8×3 = 192. Parameterizable only via the preset on the CLI; the granular counts live on `PipelineConfig` (`config.py:32-34`).
4. **Intrinsics**: 130° horizontal field of view, square 512×512, fl_y = fl_x (`render_cameras.py:507-511`) — very wide-angle.
5. **Look-at / up-vector**: `_lookat` builds camera-to-world in OpenCV convention (X right, Y down, Z forward) with world up = **+Y** (`render_cameras.py:244-261`). `look_targets` (nearest-content centroids) are computed and stored in transforms.json but NOT used for the poses — poses are pure panoramic sweeps (`render_cameras.py:403-411, 519`).

**Orientation / centering / scale assumptions:**

- **Centering: none required.** Standpoints derive from the actual point cloud's percentile bbox; scene center is computed, not assumed at the origin (`render_cameras.py:233-237, 504`).
- **Scale: effectively none required.** Clustering epsilon is scene-relative (0.20 × scene radius, `pipeline.py:279`); the only absolute-unit constants are a 0.1-unit floor on cluster scale (`pipeline.py:120`) and a 0.5-unit floor on scene radius (`render_cameras.py:237`) — harmless at room scale in meters.
- **Orientation: y-down file frame assumed (physical up = file −Y).** Derivation: with up=[0,1,0] the OpenCV camera basis makes image-down coincide with world +Y, so rendered frames are upright if and only if physical down = file +Y. This is the standard 3DGS/COLMAP convention, and the repo's own viewer confirms it: the viewer rotates the splat π about X for display in y-up three.js (`viewer/src/SplatView.js:169`) and mirrors annotations the same way, position (x,−y,−z) (`viewer/src/AnnotationParser.js:9-18`). The README's warning to check the splat is "right-side up" before running (`README.md:181`) is about exactly this. In this frame the elevation sweep −55°…+40° spans "55° toward the ceiling to 40° toward the floor"; with 3 elevations that is {−55°, −7.5°, +40°} per heading. **If a y-up file is fed in, every frame renders upside-down** — OWLv2 quality degrades and the elevation coverage flips; nothing crashes, so this failure is silent.
- **Consequence for us:** our `gen_raw.ply` raw frame (physical up = −y) matches the assumed frame. A copy rotated to y-up (if any of our recentered exports does that) would be the WRONG input. A pure translation-only recentered copy is fine (centering doesn't matter). Verify by running `--quality low` once and having the user look at a few `frames/frame_XXXX.png` — they must look right-side up.

## d. Depth and 2D→3D lift + cross-view fusion

- **Depth source: rendered from the splat itself by gsplat**, via a depth-as-color trick: each Gaussian's camera-space Z is fed to the rasterizer as a degree-0 spherical-harmonic "color", then decoded back (`renderers/gsplat_backend.py:50-77`). Result: per-pixel depth = camera-space Z in world units, 0 where nothing was hit (`renderers/base.py:7-12, 69-73`). Saved per frame as `depth_XXXX.npy` (raw float32) + `depth_XXXX.png` (visualization) (`render_cameras.py:459-464`). Note: the depth pass rasterizes one view at a time (loop at `gsplat_backend.py:64-77`) while RGB is batched (32 views/call, `render_cameras.py:33-35`) — depth is the slower half of rendering.
- **Box depth: median of a 5×5 pixel patch at the 2D box center**, using only valid (>0.01) depth pixels (`pipeline.py:206-217`). Fallback if depth missing/zero: distance from camera to scene center, or scene radius (`pipeline.py:175-177, 217-219`). This is a single depth per box, NOT a full per-pixel back-projection of the box region.
- **Lift** (`pipeline.py:51-73`): the 2D box **center pixel** is unprojected through K⁻¹ into a ray and placed at the sampled depth → one 3D point in world space. Box size: pixel width/height × depth / focal length → world width/height; **world depth-extent is fabricated as (width+height)/2** (`pipeline.py:223`). So each detection contributes a 3D point on the object's **visible front surface** (not its volumetric center) plus an approximate extent.
- **Cross-view fusion** (`pipeline.py:76-130`, `_cluster_detections`): per label, detections sorted by score; greedy clustering where the highest-score unused detection becomes a **fixed anchor** (never updated — explicitly to prevent centroid drift merging two nearby same-label objects, comment at `pipeline.py:82-85, 102-104`); all detections within `eps` of the anchor join. `eps = 0.20 × scene_radius` (`pipeline.py:279`). A cluster survives only if it has ≥ `min_votes` member frames AND a peak score ≥ `min_peak_score` (`pipeline.py:112-116`). Final position = score-weighted mean of member positions; final scale = per-axis median, floored at 0.1 (`pipeline.py:118-120`). At most **3 objects per label**, best-peak first (`pipeline.py:125-126, 280` — hard cap, not configurable from the CLI).
- Interaction to know: `min_votes=8` against the `low` preset's 24 frames is aggressive — a small object seen from one standpoint may only appear in ~8 frames total. Use `medium`/`high`, or lower `--min_votes` for `low`.

## e. Output schema

Everything lands in `--job_dir`:

| File | Content |
|---|---|
| `interactions.json` | Final detections (schema below) — `pipeline.py:310-320` |
| `transforms.json` | Camera intrinsics + all poses — `render_cameras.py:528-536, 559-564` |
| `frames/frame_XXXX.png` | Rendered RGB, 512×512 |
| `frames/depth_XXXX.npy` | Raw float32 depth, camera-space Z in world units, 0 = no hit |
| `frames/depth_XXXX.png` | Grayscale depth visualization (near=bright) — `render_cameras.py:447-456` |

`interactions.json` structure (exact, from `pipeline.py:294-320`):

```jsonc
{
  "objects": [
    {
      "label": "chair",                                  // prompt label, stripped
      "position": {"x": ..., "y": ..., "z": ...},        // world frame = INPUT PLY frame, input units;
                                                          // score-weighted cluster centroid — biased toward
                                                          // the object's visible surface, not its volume center
      "rotation": {"x": 0.0, "y": 0.0, "z": 0.0, "w": 1.0}, // ALWAYS identity quaternion — boxes are axis-aligned
      "scale":    {"x": ..., "y": ..., "z": ...},        // FULL extents (width, height, depth) in input units;
                                                          // z-extent is the fabricated (w+h)/2, floored at 0.1
      "frames": [                                         // supporting 2D evidence, best-score first,
        {"frame_idx": 17, "box": [x1,y1,x2,y2], "score": 0.61}  // pixel coords in the 512x512 frame
      ]
    }
  ],
  "frame_annotations": {                                  // reverse index: frame → drawn boxes
    "17": [{"label": "chair", "object_idx": 0, "box": [x1,y1,x2,y2], "score": 0.61}]
  }
}
```

Box parameterization: **axis-aligned center + full-size extents, no orientation** (rotation always identity). Coordinate convention: the same world frame as the input file — x,y,z in the file's axes and units; no conversion is applied anywhere in the pipeline (the π-about-X flip lives only in the browser viewer, `viewer/src/AnnotationParser.js:9-18`, and does not affect `interactions.json`).

`transforms.json` fields: `fl_x, fl_y, cx, cy, w, h`, `scene_center` (mean of splat means), `scene_radius` (80th-percentile distance from center, `render_cameras.py:233-237`), `camera_positions`, `look_targets`, and per frame `file_path`, `depth_path`, `transform_matrix` (4×4 camera-to-world, OpenCV convention), `position_idx` (which standpoint).

## f. Input formats and preprocessing

- **`.ply`**: standard 3DGS layout — x/y/z, opacity (logit), scale_0..2 (log), rot_0..3 (wxyz quaternion), f_dc_0..2, optional f_rest_* higher-order SH (`render_cameras.py:175-226`). Loaded raw; **no normalization, no recentering, no rotation, no rescaling** — the output frame IS the input frame.
- **`.spz`** (Niantic compressed, v1–v3): converted to `.ply` first (`render_cameras.py:44-168, 491-494`). Coordinates pass through numerically unchanged. Side effect worth knowing: the converted `.ply` is written **next to the input file** (`input.with_suffix(".ply")`, `render_cameras.py:492-493`), i.e. into the input's directory, and would silently overwrite a same-named `.ply` there.
- Our input should be `gen_raw.ply` directly (or a translation-only recentered copy); nothing else needed.

## g. VRAM / runtime knobs + license

- README hardware section (`README.md:185-199`): developed on an NVIDIA L40S 48 GB; `high` job ≈ 3–5 min there; **measured peak VRAM ≈ 7 GB, dominated by OWLv2**; stated minimum 8 GB, comfortable 12 GB. **RTX 4080 16 GB is comfortably sufficient.**
- Knobs that control cost:
  - `--quality` (24/90/192 frames) — the main runtime lever; detection is 1 OWLv2 forward pass per frame, unbatched (`pipeline.py:167-196`), and depth is 1 rasterization per frame.
  - `RENDER_BATCH = 32` module constant (`render_cameras.py:33-35`) — RGB views per GPU call; the file's own comment says decrease on OOM. Source edit, not a flag.
  - Render resolution 512×512 (`config.py:28-29`) — config edit, not a run_local flag.
  - `WMD_DEVICE=cpu` moves OWLv2 off the GPU if VRAM is ever tight (`pipeline.py:34-44`), at large speed cost.
- **License: MIT, confirmed** — `LICENSE.md:1-3`, "Copyright (c) 2026 Nigel Hartman"; also stated at `README.md:233-234`.

---

## Environment recommendation

**Recommended: WSL Ubuntu-24.04, new conda env, Python 3.10, torch 2.4.1+cu124, prebuilt gsplat wheel. Zero compilation.**

```
conda create -n splat_analyzer python=3.10
conda activate splat_analyzer
pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu124
pip install gsplat==1.5.3 --index-url https://docs.gsplat.studio/whl/pt24cu124
pip install "transformers==4.50.3" "numpy<2" imageio==2.37.3 plyfile==1.1.3 \
    opencv-python-headless==4.11.0.86 Pillow scipy==1.15.3 six==1.17.0
# (fastapi / uvicorn / python-multipart deliberately skipped — server-mode only)
```

Reasoning (machine facts checked read-only on 2026-07-20):

1. **The prebuilt gsplat wheel eliminates the entire compile risk**, and it exists only for Python 3.10 + torch 2.4 + CUDA 12.4 (`pt24cu124`, cp310, both linux_x86_64 and win_amd64). Any other torch (including matching our system's 2.6.0) forces a from-source/JIT CUDA build, which needs nvcc + a host compiler — **nvcc is not present on this machine's Windows PATH nor in WSL Ubuntu-24.04 (`/usr/local/cuda*` absent)**. Compiling would mean installing a CUDA toolkit somewhere — avoidable complexity.
2. **Windows native has no Python 3.10** — only 3.12 is installed (`py -0p`). The Windows path would require installing a second Python runtime system-wide; the WSL conda path pins python=3.10 inside the env with no system surface touched.
3. **WSL Ubuntu-24.04 is this machine's proven GPU stack** — five working CUDA conda envs already live there (HunyuanWorld, matrix3d, panfusion, spag4d, worldmirror), so RTX 4080 GPU passthrough into WSL is known-good.
4. **Total isolation from the off-limits Windows system python** (torch 2.6.0+cu124). The torch 2.4.1 pin lives only inside this env; nothing shared.
5. Cost: ~7–8 GB inside the WSL vhdx on C: (currently ~77 GB free; the vhdx is already 246 GB — acceptable for one env, but worth remembering given the standing C:-space concern). Plus ~1.5–2 GB OWLv2 download into the env user's HuggingFace cache on first run.

Fallback if WSL disk pressure becomes the constraint: native Windows works too — install a standalone Python 3.10 (e.g. `py.exe`-managed, untouched system 3.12), venv on D:, same torch 2.4.1+cu124 (Windows wheels exist) + the `win_amd64` prebuilt gsplat wheel. Same zero-compile property; just one more system-level install (the 3.10 runtime).

Run command for our scene (WSL sees D: as `/mnt/d`):

```
python run_local.py \
  --ply "/mnt/d/T/Documents/GeorgiaTech/Summer2026/<path to gen_raw.ply>" \
  --prompt "bed, nightstand, lamp, chair, rug, curtain, picture frame" \
  --quality low \
  --job_dir "/mnt/d/T/Documents/GeorgiaTech/Summer2026/scene-pipeline/entangled_gen/analyzer/out_bedroom_low"
```

First run at `--quality low` purely to verify frame orientation (user inspects `frames/frame_XXXX.png` for right-side-up rooms) before paying for a `high` run.

---

## Worth borrowing into our own detection stage (even if we drop the tool)

Context for these: our current pipeline renders a few fixed views, which left ~60° of the room never rendered, 15 of 20 detections in one view, and exactly one cross-view merge.

1. **Density band-pass standpoint sampling** (`render_cameras.py:290-411`): sample camera positions inside the scene's robust (1–99 percentile) bounding box, accept by a Gaussian band-pass on KD-tree local splat density (rejects both inside-geometry and empty-void positions), enforce Poisson-disk separation, farthest-point fill as guarantee. Directly attacks our blind-zone problem, is CPU-only (numpy + scipy), deterministic, and independent of the renderer — trivially portable into our render stage.
2. **Panoramic azimuth × elevation grid per standpoint with a wide FOV** (`render_cameras.py:414-440, 507-509`): every standpoint gets full 360° azimuth coverage at 2–3 tilts, 130° FOV. Guarantees no angular gaps per standpoint — a systematic version of what our 7-view same-standpoint judge rig does ad hoc.
3. **Two-sided vote filter for cross-view fusion** (`pipeline.py:112-116`): keep a 3D object only if it was detected in ≥ `min_votes` frames AND its best single-frame score ≥ `min_peak_score`. Simple, tunable false-positive suppression that only works when coverage is dense — the natural companion to fix our "1 cross-view merge" weakness.
4. **Fixed-anchor greedy clustering with scene-relative epsilon** (`pipeline.py:99-116, 279`): anchor = highest-score detection, never updated, radius = 0.20 × scene radius; prevents centroid drift from bleeding two adjacent same-label objects into one cluster. Aggregate as score-weighted position + per-axis median scale (`pipeline.py:118-119`).
5. **Depth-as-color rasterization + 5×5 median patch depth** (`renderers/gsplat_backend.py:50-77`, `pipeline.py:209-217`): get per-pixel depth from a vanilla gsplat call by rendering each Gaussian's camera-Z as a degree-0 SH color, then sample box depth as the median of valid pixels in a 5×5 patch at the box center. A cheap splat-native depth source if we ever want to lift without a monocular depth network.

## Open risks (ordered)

1. **Coordinate frame (highest).** The tool silently assumes physical up = file −Y (y-down 3DGS convention). Our raw frame should match, but the failure mode is silent (upside-down renders → degraded, weirdly-distributed detections, no error). Mitigation: mandatory `--quality low` orientation check of rendered frames before any real run; user judges the images. Also confirm which of our PLY copies (raw vs recentered) preserves up = −y before choosing the input.
2. **Position semantics differ from ours.** Its `position` is a score-weighted centroid of front-surface points (center-pixel depth), not a volumetric box center; its z-extent is fabricated as (w+h)/2; boxes are axis-aligned with identity rotation. A fair comparison against our boxes must account for a systematic toward-the-camera surface bias and unreliable depth extents.
3. **`max_per_label = 3` hard cap** (`pipeline.py:280`) — scenes with 4+ instances of one label (e.g. "picture frame") get truncated. Not CLI-tunable; needs a one-line source edit if it bites.
4. **torch 2.4 pin via the prebuilt wheel.** Isolated env makes this safe, but it means this env can never share packages with our torch 2.6 stack; and if gsplat's wheel host disappears we're back to source builds (mitigation: keep the downloaded wheel file).
5. **`min_votes` vs quality interplay.** Defaults (`min_votes=8`) are tuned for `medium`/`high` frame counts; `low`-quality validation runs should not be judged on detection quality, only on frame orientation.
6. **Disk side effects.** SPZ inputs write a converted PLY next to the input (not applicable to us using .ply, but noted); default `--job_dir` is relative to the current working directory — always pass absolute; a `high` run writes 192 × (RGB PNG + depth NPY + depth PNG) ≈ a few hundred MB per job.
