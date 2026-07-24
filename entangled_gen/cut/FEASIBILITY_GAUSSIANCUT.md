# GaussianCut Feasibility Study (Step 1, read-only probe)

Date: 2026-07-20
Code examined: https://github.com/umangi-jain/gaussiancut cloned at commit `93d24a4` to
`D:\T\Documents\GeorgiaTech\Summer2026\Research\code\reference\gaussiancut`
(referred to below as `<REPO>`; all file:line citations are into that clone).

GaussianCut = graph-cut segmentation of a pretrained 3D Gaussian Splatting (3DGS) model:
given 2D object masks in a few views, it (1) "coarse stage": splats each mask onto the
Gaussians with a custom CUDA kernel to score every Gaussian as foreground/background,
then (2) "fine stage": runs a CPU min-cut (PyMaxflow) over a k-nearest-neighbor graph of
all Gaussians to produce the final foreground Gaussian set.

Our splat under test:
`D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\gen_raw.ply`
(1,920,000 Gaussians, exported from a World Labs Marble world).

---

## Summary verdict

**Yes, we can run GaussianCut on gen_raw.ply — with fabricated scaffolding, no changes to the splat itself, and one known crash to pre-empt.**

1. The PLY itself is compatible as-is. GaussianCut loads the splat with the standard 3DGS
   `GaussianModel.load_ply`, which reads exactly the properties our file has
   (x/y/z, f_dc_0..2, opacity, scale_0..2, rot_0..3) provided we set `sh_degree = 0`
   (our file has zero `f_rest_*` properties, i.e. spherical-harmonics degree 0, and the
   loader's assert passes exactly when `3*(0+1)^2 - 3 == 0`). Normals are not read.
2. We must fabricate the surrounding directory scaffolding that the official-3DGS loader
   expects: a `cfg_args` text file, a `point_cloud/iteration_N/point_cloud.ply` layout,
   a COLMAP `sparse/0/` camera set (text format is fine), a matching `images/` folder
   (an image file must exist for every listed camera), and a `multiview_masks/` folder.
   No COLMAP run is needed — we write the camera files ourselves from our render-view
   JSONs.
3. One real code landmine for SH-degree-0 splats: the render steps hardcode 15 `f_rest`
   coefficients (SH degree 3) in two places and will crash on our degree-0 model.
   The segmented foreground PLY is saved to disk BEFORE the crashing render step, so
   even unpatched we get the main output; a 2-line patch (or zero-padding our PLY to
   SH degree 3) makes the render steps work too.
4. Two CUDA extensions must be compiled (`diff-gaussian-rasterization` with a custom
   `apply_weights` kernel, and `simple-knn`). The vendored rasterizer is modified, so a
   prebuilt stock wheel cannot be substituted. The `glm` math-header library the build
   needs is missing from the vendored tree and must be supplied.
5. The whole pipeline is headless once masks exist. Segment-and-Track-Anything is only
   the upstream interactive mask-making tool; nothing from it is imported at graph-cut
   runtime, so our own SAM masks drop in directly.
6. Recommended environment: a fresh conda env inside WSL Ubuntu (not native Windows),
   torch 2.1.1 + CUDA 12.1, because the CUDA extensions must compile against the env's
   torch and the Windows system python (torch 2.6.0+cu124) is off limits.

---

## 2a. Dataset format

**Loader identity.** GaussianCut vendors the official graphdeco-inria 3DGS scene loader
essentially verbatim. Scene type is detected in
`<REPO>\gaussian-splatting\scene\__init__.py:47-53`:
- if `<source_path>\sparse` exists → COLMAP loader (`sceneLoadTypeCallbacks["Colmap"]`),
- else if `<source_path>\transforms_train.json` exists → Blender/NeRF loader,
- else `assert False, "Could not recognize scene type!"`.

**Camera format (COLMAP branch, the one we would use).**
`<REPO>\gaussian-splatting\scene\dataset_readers.py:132-142`: reads
`sparse/0/images.bin` + `sparse/0/cameras.bin`; on ANY exception it falls back to
`sparse/0/images.txt` + `sparse/0/cameras.txt` (bare `except:` at line 138), so
hand-written COLMAP **text** files are fully supported. Only undistorted pinhole models
are accepted — `SIMPLE_PINHOLE` or `PINHOLE`
(`dataset_readers.py:85-95`, hard assert otherwise).

**Original images are REQUIRED for every camera.**
`dataset_readers.py:97-99`: for each entry in `images.bin/txt` the loader does
`Image.open(os.path.join(images_folder, basename(extr.name)))` — a missing image file is
an immediate crash. The image folder is `<source_path>\images` by default, overridable
with `--images` (`dataset_readers.py:144`). Our views are `.webp`; PIL opens webp, and
the matching key `image_name` is the basename with everything after the first `.`
stripped (`dataset_readers.py:98` — note: `split(".")[0]`, so no extra dots in
filenames).

**Resolution.** The render resolution comes from the loaded IMAGE size, not from the
COLMAP intrinsics; intrinsics width/height are used only to convert focal length to
field of view (`dataset_readers.py:85-93`). So the image aspect/FoV must be consistent
with the intrinsics or renders and mask-splatting are distorted, but there is no
explicit width==width check. Watch out: images wider than 1600 px are silently
downscaled to 1600 unless `--resolution 1` is passed
(`<REPO>\gaussian-splatting\utils\camera_utils.py:22-39`). Our 900x900 views are safe.

**COLMAP 3D points: a file must exist, but its content is unused for our case.**
`dataset_readers.py:157-170`: the loader looks for `sparse/0/points3D.ply`; if absent it
tries to convert `points3D.bin` then `points3D.txt` — if none of the three exists the
final text read raises an uncaught exception. However, `fetchPly` failures ARE caught
(lines 167-170, `pcd = None`), and when a trained model iteration is loaded the point
cloud is never used (`scene\__init__.py:81-87` takes the `load_ply` branch, not
`create_from_pcd`). Conclusion: we must place a small valid `points3D.ply` (or even a
dummy file) at `sparse/0/points3D.ply`, and its contents do not matter for segmentation.

**Train/test split.** With `eval` false (the default we would use) all cameras are
training cameras (`dataset_readers.py:148-153`), which matters because the coarse stage
skips masks attached to test cameras (`utils\render_utils.py:255-256`).

**Directory scaffold we would fabricate** (COLMAP text route):

```
<source_path>\                      (also passed as --scene_path)
├── sparse\0\cameras.txt            PINHOLE intrinsics, written by us
├── sparse\0\images.txt             world-to-camera qvec/tvec per view, written by us
├── sparse\0\points3D.ply           tiny dummy point cloud
├── images\gpu_yaw000.webp ...      our rendered views (every camera listed must exist)
└── multiview_masks\gpu_yaw000.png  binary masks (any subset of views)

<model_path>\
├── cfg_args                        one-line Namespace(...) text file, written by us
└── point_cloud\iteration_1\point_cloud.ply    = copy of gen_raw.ply
```

## 2b. Splat model loading

**Load path.** `segment_render.py` builds `GaussianModel(dataset.sh_degree)` and
`Scene(dataset, gaussians, load_iteration=args.iteration)` with `--iteration` default
`-1` (`<REPO>\gaussian-splatting\segment_render.py:30, 60-62`). `Scene` then resolves
the highest `iteration_N` folder under `<model_path>\point_cloud`
(`scene\__init__.py:37-41`; `utils\system_utils.py:26-28` — the `point_cloud` folder
must exist and contain at least one `iteration_<int>` subfolder) and calls
`self.gaussians.load_ply(<model_path>\point_cloud\iteration_<N>\point_cloud.ply)`
(`scene\__init__.py:81-85`). So yes: the standard 3DGS
`point_cloud/iteration_*/point_cloud.ply` convention.

**PLY attributes read** (`scene\gaussian_model.py:255-296`):
- `x`, `y`, `z` (line 258-260)
- `opacity` (line 261) — expected to be the raw pre-sigmoid logit, as in standard 3DGS
  (`opacity_activation = torch.sigmoid`, line 63)
- `f_dc_0`, `f_dc_1`, `f_dc_2` (lines 263-266)
- every property named `f_rest_*`, with a hard assert on the count:
  `assert len(extra_f_names) == 3*(self.max_sh_degree + 1)**2 - 3` (line 270).
  With `sh_degree = 0` the required count is **0**, which our file satisfies.
- every `scale_*` (lines 277-281) — log-scale expected (`scaling_activation = exp`, line 58)
- every `rot_*` (lines 283-287) — quaternion, normalized on use (line 66)
- Normals (`nx/ny/nz`) are NOT read anywhere in `load_ply` (they are only written as
  zeros by `save_ply`, lines 216-233).

**Non-official splats CAN be dropped in — the PLY is only read — but two metadata files
must be fabricated:**
1. `cfg_args` is effectively REQUIRED. `arguments\__init__.py:104-113` opens
   `<model_path>\cfg_args` and only catches `TypeError`; a missing file raises an
   uncaught `FileNotFoundError`. The file content is a Python `Namespace(...)` literal
   that is `eval()`-ed (line 113). Because `ModelParams` is constructed with
   `sentinel=True` (all its command-line defaults become `None`,
   `arguments\__init__.py:20-38, 47-57`), any model parameter not given on the command
   line must come from `cfg_args`. Minimal working content for us:
   `Namespace(sh_degree=0, source_path='<abs source path>', model_path='<abs model path>', images='images', resolution=-1, white_background=False, data_device='cuda', eval=False)`
   (command-line values override the file when non-None, lines 115-118).
2. The `point_cloud\iteration_N\` folder layout (previous paragraph).

`cameras.json` and `input.ply` are NOT required: they are only written (not read) and
only when no trained iteration is being loaded (`scene\__init__.py:55-67`).

**SH-degree-0 landmine (the one real code bug for us).** Two render-stage code paths
hardcode 15 `f_rest` coefficients, i.e. SH degree 3:
- fine stage: `utils\render_utils.py:154-156`
  (`gaussians_colored._features_rest[remove_gauss == 1] = torch.zeros((M, 15, 3), ...)`),
  executed unconditionally at the top of `render_gc_sets` (lines 147-156, BEFORE the
  `if select_images:` gate at line 157);
- coarse stage: `utils\render_utils.py:386-388`, executed only when `--select_images`
  is given (gate at line 370).
On our degree-0 model `_features_rest` has shape (N, 0, 3), so assigning a (M, 15, 3)
tensor crashes with a shape mismatch (whenever M > 0). Mitigations, in order of
preference:
  (a) 2-line patch replacing the hardcoded `15` with `gaussians._features_rest.shape[1]`, or
  (b) zero-pad gen_raw.ply with 45 `f_rest_*` float properties and run with
      `sh_degree=3` (adds 45 x 4 B x 1.92 M = ~346 MB to the file and ~4x the GPU
      feature memory), or
  (c) run unpatched and accept the crash: the segmented foreground PLY and the
      per-Gaussian index mask are already saved before `render_gc_sets` is called
      (`segment_render.py:88-94` calls `graphcut_segmentation` first, which saves at
      `utils\graphcut.py:177-178`), so only the visualization renders are lost.

## 2c. Masks

- **Location:** `<scene_path>\multiview_masks\` where `--scene_path` is its own
  command-line flag (`segment_render.py:46`), independent of `source_path`
  (`utils\render_utils.py:230` for `mask_type='multiview'`). Pointing `--scene_path` at
  the same directory as `source_path` reproduces the README layout.
- **Naming:** the mask filename stem must EXACTLY equal the camera's `image_name`
  (image filename with everything after the first `.` stripped). Matching logic:
  `utils\render_utils.py:236-246` compares `masks_all[index].split('.')[0]` to
  `camera.image_name`. Extension of the mask file itself is irrelevant (PNG fine).
- **Format:** opened with PIL, converted with `torchvision.transforms.ToTensor`,
  bilinearly resized to the camera's image resolution, then binarized with
  `mask[mask > 0] = 1.0` (`utils\render_utils.py:257-267`). So: binary PNG with values
  0/255 works; mask resolution does NOT need to match the image (it is resized); any
  nonzero pixel counts as foreground. **Use single-channel (grayscale) PNGs**: the code
  does `.repeat(3, 1, 1)` (line 266), which turns a 1-channel mask into the 3 channels
  the CUDA kernel expects, but would turn an RGB mask into 9 channels — undefined
  behavior against the 3-channel kernel buffer (`NUM_CHANNELS 3` in
  `<REPO>\gaussian-splatting\submodules\diff-gaussian-rasterization\cuda_rasterizer\config.h`).
- **Subset of views: yes.** The loop iterates over the mask files, not the cameras, so
  any subset of views may have masks; the README states a single mask is acceptable
  (`<REPO>\README.md:22`). Caveat: every mask must match SOME camera — an unmatched
  mask leaves an empty-list placeholder that crashes at `render_utils.py:262`
  (the length assert at lines 248-250 is vacuous because both lists are constructed
  with the same length).
- **Threshold interplay:** per-Gaussian foreground weight is averaged only over the
  views that were processed (`render_utils.py:327-329`), and Gaussians with average
  weight >= `--foreground_threshold` (default 0.9; the code comment recommends 0.3 for
  360-degree inward scenes, `segment_render.py:39-40`) seed the graph-cut source. With
  few masks, an object seen but unmasked in one view is heavily penalized — threshold
  will need tuning for our 4-7 view setup.

## 2d. Rasterizer and dependencies

- **Both CUDA extensions are required and vendored in-repo** (no git submodule
  metadata — there is no `.gitmodules`; the sources are checked in):
  - `<REPO>\gaussian-splatting\submodules\diff-gaussian-rasterization` — imported at
    module scope in `scene\gaussian_model.py:24` and `gaussian_renderer\__init__.py:14`.
  - `<REPO>\gaussian-splatting\submodules\simple-knn` — imported at module scope in
    `scene\gaussian_model.py:20` (`from simple_knn._C import distCUDA2`), so it must be
    built even though `distCUDA2` is only used during training-style initialization.
- **The vendored rasterizer is MODIFIED — a stock prebuilt wheel will not work.** It
  adds an `apply_weights` CUDA kernel
  (`cuda_rasterizer\apply_weights.cu`, listed in the extension's `setup.py` sources;
  Python wrapper `diff_gaussian_rasterization\__init__.py:223-276` calling
  `_C.apply_weights`). This is the mechanism that back-projects 2D mask weights onto
  Gaussians (`scene\gaussian_model.py:239-254`). The idea comes from GaussianEditor
  (acknowledged in `<REPO>\README.md:56`) but the code is fully vendored —
  **no separate GaussianEditor clone is needed** (grep for `gaussianeditor` over all
  `.py` files: zero hits).
- **Missing build input: glm.** The extension's `setup.py` adds include path
  `third_party/glm/`, but the vendored `third_party\` contains only
  `stbi_image_write.h` — the glm header library (a git submodule in the original
  graphdeco repo) did not survive vendoring. Fix at env-build time: clone
  https://github.com/g-truc/glm into
  `<REPO>\gaussian-splatting\submodules\diff-gaussian-rasterization\third_party\glm`
  (header-only, no compilation of its own). Four files include `glm/glm.hpp`
  (`apply_weights.h`, `backward.h`, `forward.h`, `rasterizer_impl.cu`).
- **Debug compile flags:** the rasterizer's `setup.py` passes nvcc `-g -G`
  (device-side debug). `-G` disables most kernel optimization — expect slow rasterization
  unless we drop the flag when building (an env-build decision, not needed for
  correctness).
- **`environment.yml` (top level, `<REPO>\environment.yml`), complete list:**
  - conda: `plyfile`, `pytorch=2.1.1`, `torchvision=0.16.1`, `ffmpeg`, `numpy`,
    `pandas=2.2.2`, `scipy=1.10.0`, `scikit-learn==1.3.2`, `matplotlib`, `pillow`,
    `requests`, `tqdm`, `pymaxflow`
  - pip: `opencv-python`, `torchmetrics>=0.7.0`, `lightning-utilities>=0.8.0`, `lxml`,
    plus the two local submodule builds.
  - **No python pin and no CUDA pin** (no `cudatoolkit`/`pytorch-cuda` entry — the
    README just says "ensure the pytorch and cuda versions are compatible",
    `<REPO>\README.md:18`). scipy 1.10.0 caps python at <= 3.11; python 3.10 is the
    safe choice. Note the inner `gaussian-splatting\environment.yml` (python 3.7.13 /
    torch 1.12.1 / cudatoolkit 11.6) is the stale official-3DGS file and is NOT the one
    GaussianCut's README installs.
- **Segment-and-Track-Anything is NOT needed at graph-cut runtime.** It is vendored as
  a sibling directory but nothing under `<REPO>\gaussian-splatting\` imports it
  (verified by grep for `Segment|sam_track|SegTracker|aot`, case-insensitive: only
  false-positive hits on the word "segmentation" in `graphcut.py`). It is purely the
  upstream interactive tool used to author `multiview_masks`; our own SAM masks replace
  it, and none of its (heavy) dependencies need to be installed.

## 2e. Invocation and outputs

**Scripts.** `<REPO>\scripts\` contains a single template, `sample.sh`:

```
python3 gaussian-splatting/segment_render.py -m 'path/to/optimized/3dgs/model' \
  --scene_path='/path/to/dataset/and/masks' \
  --identifier='identifier' \
  --mask_type='multiview' \
  --foreground_threshold=0.9 \
  --select_images='image(s)/name/to/evaluate'
```

A per-scene config script is just this command with concrete paths. Relevant flags
(`segment_render.py:30-53` plus graph-cut hyperparameters registered in
`utils\graphcut.py:12-28`): `--iteration` (default -1 = latest), `--mask_type`
(`spiral` | `multiview` | `scribble`; we use `multiview`), `--foreground_threshold`,
`--identifier` (suffix for all output folders), `--select_images` (list of image stems
to render, or `all`; empty list = no renders), `--scene_path`, `--skip_coarse` /
`--skip_gc` (note both are `type=bool`, so ANY non-empty string including "False"
parses as True — only pass them at all when wanted), and graph-cut weights
`--sig_pos_neigh --sig_col_neigh --sig_pos_term --sig_col_term --weight_color
--weight_pos --user_weight_term --cluster_term`. Cluster/edge counts are fixed
attributes, not flags (`num_edges=10`, `terminal_clusters_source=5`,
`terminal_clusters_sink=5`, `leaf_size=40` — `arguments\__init__.py:71-76`; the class
never calls the parser, so these are NOT overridable from the command line).

**What lands where (all under `<model_path>`; `{id}` = `--identifier`,
`{mt}` = `--mask_type`).** Note the README's "coarse_results/" and "fine_results/"
names do not exist in code; the actual directories are:

| Path | Producer | Content |
|---|---|---|
| `graphcut_{id}\gaussians_source_{mt}.ply` | coarse, `render_utils.py:340-342` | coarse foreground Gaussians (weight >= threshold), standard 3DGS PLY |
| `graphcut_{id}\gaussians_sink_{mt}.ply` | coarse, `render_utils.py:353-357` | coarse background Gaussians |
| `graphcut_{id}\weights_source_{mt}.pt`, `weights_sink_{mt}.pt` | coarse, `render_utils.py:358-365` | per-Gaussian boolean masks (torch tensors, length = all Gaussians) |
| `graphcut_{id}\gaussians_source.ply` | fine, `utils\graphcut.py:177` | **FINAL graph-cut foreground PLY — this is our "foreground.ply"** |
| `graphcut_{id}\remove_source.pt` | fine, `utils\graphcut.py:178` | per-Gaussian 0/1 tensor over ALL input Gaussians; 1 = assigned to sink (background) |
| `coarse_{id}\select\{renders,gt,masks}\*.png` | only if `--select_images`, `render_utils.py:370-392` + `render_set` 91-116 | coarse visualization renders (blacked-out background + white/black mask render) |
| `fine_gc_{id}\select\{renders,gt,masks}\*.png` | only if `--select_images`, `render_utils.py:157-169` | fine visualization renders |

**Getting foreground.ply + background.ply:** foreground is written directly
(`graphcut_{id}\gaussians_source.ply`). Background is NOT written by the fine stage;
derive it with a ~10-line script that loads `remove_source.pt` and selects the
`remove == 1` rows out of the input PLY (index order in the tensor equals vertex order
in the PLY — the fine stage operates on the full loaded model with no reordering,
`utils\graphcut.py:98-99, 162-174`).

**Interactivity: none.** Given masks on disk, `segment_render.py` is fully headless —
no UI, no prompts, no server. All interactivity lives in the upstream (and unused-by-us)
Segment-and-Track-Anything tool.

## 2f. GPU / runtime expectations

Nothing is stated anywhere — no VRAM, GPU model, or runtime numbers in either README,
the code, or the scripts (grep for vram/memory/GPU over the repo: no hits). Reasoned
estimates for our 1.92 M-Gaussian scene:

- **GPU:** forward-only rasterization + weight accumulation. At SH degree 0 the model is
  ~14 floats/Gaussian = ~107 MB; the coarse stage holds the model plus two deep copies
  (`render_utils.py:197-198`) and the fine stage two more (`segment_render.py`/
  `graphcut.py`), still well under 2 GB even with render buffers. Comfortable on the
  RTX 4080 (16 GB). All camera ground-truth images are also kept on the GPU
  (`scene\cameras.py:39`), trivial for a handful of 900x900 views. (If we chose the
  SH-3 zero-padding mitigation instead of the 2-line patch, multiply feature memory by
  ~4x — still fine.)
- **CPU (the actual bottleneck):** the fine stage is pure CPU — scikit-learn KDTree over
  all 1.92 M positions with k=10 neighbor queries, then a PYTHON loop over all 1.92 M
  Gaussians adding ~19 M edges one `g.add_edge` call at a time
  (`utils\graphcut.py:119-152`), then PyMaxflow min-cut on a 1.92 M-node graph. Expect
  tens of minutes up to a few hours for the loop alone; several GB of RAM for the
  maxflow graph. Nothing here is a blocker, but plan for a long single-threaded stage.

---

## 3. Our splat: gen_raw.ply header vs. GaussianCut's loader

Header read from
`D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\gen_raw.ply`
(binary_little_endian 1.0, element vertex 1920000):

| Property in our file | Loader requirement (`gaussian_model.py:255-296`) | Verdict |
|---|---|---|
| `x`, `y`, `z` (float) | required (lines 258-260) | match |
| `scale_0..scale_2` (float) | all `scale_*` read by prefix (lines 277-281); log-scale semantics assumed | match (3 scales = standard anisotropic) |
| `f_dc_0..f_dc_2` (float) | required (lines 263-266) | match |
| `opacity` (float) | required (line 261); pre-sigmoid logit semantics assumed | match (see risk 3 on semantics) |
| `rot_0..rot_3` (float) | all `rot_*` read by prefix (lines 283-287); w-x-y-z quaternion assumed | match |
| — no `f_rest_*` at all | count must equal `3*(sh_degree+1)^2 - 3` (assert, line 270) | match ONLY with `sh_degree=0` in `cfg_args` (0 required = 0 present). SH degree is 0, i.e. flat color per Gaussian, no view-dependent color. |
| — no `nx/ny/nz` | never read | irrelevant |

Property ORDER in the header differs from what official 3DGS writes (ours interleaves
scale before f_dc), but the loader reads by property name via `plyfile`, so order is
irrelevant.

**Compatibility verdict: loadable as-is with `sh_degree=0`.** The only degree-related
failure is the hardcoded-15 `f_rest` assignment in the two render paths described in
2b — pre-empt with the 2-line patch (preferred) or SH-3 zero-padding.

---

## 4. Environment recommendation: WSL Ubuntu conda

**Recommendation: build the GaussianCut environment as a fresh conda env in WSL Ubuntu,
not on native Windows.** Reasoning:

1. **A fresh env is mandatory either way.** GaussianCut pins `pytorch=2.1.1` /
   `torchvision=0.16.1` (`<REPO>\environment.yml:8-9`). The Windows system python runs
   torch 2.6.0+cu124 and is explicitly off limits (and downgrading it would break the
   segmentation/lifting GPU stack). So there is no "reuse existing env" option; the
   question is only where the new env lives.
2. **The two CUDA extensions must be compiled from source** against the env's torch
   (the vendored rasterizer is modified — no prebuilt wheel exists). On native Windows
   this requires a Visual Studio C++ toolchain version compatible with both the CUDA
   toolkit and torch 2.1.1's expectations — a classically fragile combination for the
   3DGS extensions. In WSL Ubuntu it is a plain gcc + nvcc build, the path the repo
   authors and virtually all 3DGS forks actually test.
3. **WSL already has working conda + CUDA** (existing conda envs and CUDA workloads run
   there today). The RTX 4080 (Ada, sm_89) is supported by torch 2.1.1 builds for
   CUDA 12.1 (`pytorch-cuda=12.1` from the pytorch channel, or pip
   `torch==2.1.1+cu121`). No conflict with the Windows-side torch 2.6.0+cu124 — WSL
   envs are fully separate.
4. **Concrete env sketch** (for the later build step, NOT executed now): python 3.10
   (unpinned upstream; scipy 1.10.0 caps at 3.11), `pytorch=2.1.1 pytorch-cuda=12.1`,
   the rest of `environment.yml` as listed in 2d, clone glm into the rasterizer's
   `third_party\glm` before `pip install` of the two submodules, and ensure a CUDA 12.1
   nvcc is visible (conda `cuda-toolkit` 12.1 works if the WSL system CUDA differs).
   Optionally drop the `-g -G` nvcc flags in the rasterizer's `setup.py` for speed.
5. **Disk note:** C: is at ~77 GB free and the WSL vhdx is already large; the new env +
   torch cu121 is roughly 8-10 GB. Acceptable, but worth keeping in mind before adding
   more.

---

## 5. Open risks

1. **Camera-frame convention (the big one).** We must synthesize
   `sparse/0/images.txt` (world-to-camera quaternion + translation, COLMAP convention:
   camera looks down +z, y down) and `cameras.txt` (PINHOLE fx fy cx cy) from our
   render-view JSONs (e.g.
   `D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7\entangled_gen\out\bedroom_marble\views\gpu_yaw000.json`,
   which stores `cam`, `look`, `up`, `fov`, `res` per view). Our RAW-space PLY has
   physical up = -y under the rot180 convention, and this project has already been
   bitten once by an up-sign/mirror error (the ST mirror bug). The COLMAP extrinsics
   must be expressed in the SAME world frame the PLY vertices live in, with no extra
   flip; a mistake produces plausible-looking but mirrored/upside-down mask projections
   and silently garbage segmentation. Mandatory verification before any real run: use
   GaussianCut's own render path (`--select_images` writes `renders\` next to `gt\`)
   and have the user compare render vs. ground-truth image for alignment — per our
   verification rules, the user judges the visuals, one view at a time.
2. **Field-of-view semantics.** Our view JSON stores `fov: 75.0` for 900x900 output; we
   must confirm whether our renderer treats that as vertical or horizontal FoV before
   computing the COLMAP focal length (square images make fx = fy IF pixels are square
   and FoV is symmetric — verify against our render tool's projection code, not by
   assumption).
3. **Attribute semantics of gen_raw.ply.** The loader assumes standard 3DGS semantics:
   `opacity` = pre-sigmoid logit, `scale_*` = log-scale, `rot_*` = w-x-y-z quaternion,
   `f_dc_*` = SH DC coefficients (not raw RGB). Our own week5/week7 render tools treat
   gen_raw.ply as a standard 3DGS PLY and produce correct images, which is strong
   evidence the Marble-to-PLY conversion followed the convention — but a one-time
   numeric sanity check (e.g. opacity value histogram: logits span roughly [-10, 10];
   linear opacities would sit in [0, 1]) is cheap and worth doing before the first run.
4. **Mask channel count.** Write single-channel grayscale PNGs. A 3-channel mask
   silently becomes a 9-channel tensor fed to a 3-channel CUDA buffer
   (`utils\render_utils.py:266`).
5. **Mask/image naming.** Mask stem must exactly match the image stem; stems are taken
   with `split('.')[0]`, so no extra dots; an unmatched mask crashes with an obscure
   `AttributeError` (see 2c).
6. **Sparse view coverage.** We have 4-11 rendered views of the bedroom, and detection
   coverage is already known to be uneven (60 degrees of the room never rendered).
   GaussianCut accepts any number of masks, but Gaussians on the object's unseen side
   are decided purely by the graph smoothness term — segmentation quality on the
   occluded side is an open empirical question. The `--foreground_threshold` default of
   0.9 is likely too aggressive for few views (code comment suggests 0.3 for inward
   360-degree scenes); expect tuning.
7. **Fine-stage runtime.** Python-loop graph construction over 1.92 M Gaussians x 10
   edges; expect a long (possibly hours) CPU stage per run. Fine for one-object
   experiments; batching many objects would motivate vectorizing that loop later.
8. **Boolean flag quirk.** `--skip_coarse` / `--skip_gc` use `type=bool`: passing the
   string "False" yields True. Only include these flags when skipping is intended.
9. **Hardcoded 15 f_rest render crash** (detailed in 2b) — must be handled before the
   first end-to-end run, otherwise the run dies after the (already-saved) graph-cut
   output when it tries to render.
