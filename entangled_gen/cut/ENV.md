# GaussianCut environment (Step 3 — gaussiancut-environment-build)

Status: **SUCCESS** — built 2026-07-21. Both vendored CUDA extensions compiled and
installed; full smoke test passed including real kernel execution on the GPU.

GaussianCut = graph-cut segmentation of a 3D Gaussian splat (cuts a chosen object's
Gaussians out of a scene splat, seeded by 2D masks). This document records the isolated
environment that runs it, how to invoke it from Windows, and every deviation from a
stock install.

---

## 1. Where everything lives

| What | Location |
|---|---|
| WSL distro | `Ubuntu-24.04` (user: root) |
| Conda env | `gaussiancut` at `/root/miniconda3/envs/gaussiancut` (12 GB) |
| Runnable patched repo | `/root/gaussiancut` (130 MB, clone of commit `93d24a4` + patches below) |
| Pristine reference clone (do NOT modify) | `D:\T\Documents\GeorgiaTech\Summer2026\Research\code\reference\gaussiancut` |
| This doc | `D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen\cut\ENV.md` |

Total disk used: **12 GB env + 130 MB repo ≈ 12.1 GB** (inside the WSL vhdx; WSL had
944 GB free before the build).

## 2. Invocation pattern (what a Windows-side script calls)

No `conda activate` is needed at runtime — calling the env's python binary directly
resolves everything (proven by the smoke test). From PowerShell or cmd:

```
wsl -d Ubuntu-24.04 -- /root/miniconda3/envs/gaussiancut/bin/python /root/gaussiancut/gaussian-splatting/segment_render.py -m <model_path> --scene_path <scene_path> --identifier <id> --mask_type multiview --foreground_threshold 0.3
```

- Scripts that `cd` first (repo-relative imports): segment_render.py is normally run
  from the `gaussian-splatting` folder. Safe general form:
  `wsl -d Ubuntu-24.04 -- bash -c "cd /root/gaussiancut/gaussian-splatting && /root/miniconda3/envs/gaussiancut/bin/python segment_render.py <args>"`
- Interactive shell for debugging:
  `wsl -d Ubuntu-24.04 -- bash -lc "source /root/miniconda3/etc/profile.d/conda.sh && conda activate gaussiancut && bash"`
- **Gotcha:** if you drive `wsl` from Git Bash (MSYS) instead of PowerShell/cmd, MSYS
  path-conversion can silently mangle arguments containing URLs or colon+slash patterns
  (it destroyed a pip `--index-url` during this build). Use PowerShell/cmd for wsl
  one-liners, or prefix `MSYS_NO_PATHCONV=1`.

## 3. Pinned versions actually installed

| Component | Version | Source |
|---|---|---|
| python | 3.10.20 | conda (defaults) |
| torch | 2.1.1+cu121 | pip, index `https://download.pytorch.org/whl/cu121` |
| torchvision | 0.16.1+cu121 | pip, same index |
| cuda-toolkit (nvcc) | 12.1.1 (nvcc 12.1.105) | conda `-c nvidia/label/cuda-12.1.1` |
| gcc_linux-64 / gxx_linux-64 | **11.4.0** (see surprise #4 — 12.x fails) | conda-forge |
| numpy | **1.26.4** (pinned; see surprise #2) | pip |
| setuptools | **69.5.1** (pinned; see surprise #3) | pip |
| scipy | 1.10.0 | pip (upstream pin) |
| scikit-learn | 1.3.2 | pip (upstream pin) |
| pandas | 2.2.2 | pip (upstream pin) |
| PyMaxflow | 1.3.2 | pip |
| plyfile | 1.1.3 | pip |
| opencv-python | 4.11.0.86 | pip |
| torchmetrics | 1.9.0 | pip |
| lightning-utilities | 0.15.3 | pip |
| pillow / matplotlib / lxml / tqdm / requests / ninja | 12.2.0 / 3.10.9 / 6.1.1 / 4.69.0 / (latest) / 1.13.0 | pip |
| diff_gaussian_rasterization | 0.0.0, built from the **vendored MODIFIED** source (custom `apply_weights` kernel) | local build |
| simple_knn | 0.0.0, built from vendored source | local build |

Omitted from upstream `environment.yml` on purpose:
- `ffmpeg` — only reached through `cv2.VideoWriter`; the pip opencv wheel bundles codecs.
- Everything for Segment-and-Track-Anything — not imported anywhere at graph-cut
  runtime (verified in the feasibility probe).

## 4. Build steps that were actually needed

1. `git clone /mnt/d/T/Documents/GeorgiaTech/Summer2026/Research/code/reference/gaussiancut /root/gaussiancut` (commit `93d24a4`).
2. `conda create -n gaussiancut python=3.10 -y`
3. `pip install torch==2.1.1 torchvision==0.16.1 --index-url https://download.pytorch.org/whl/cu121`
4. `pip install numpy==1.26.4 plyfile pandas==2.2.2 scipy==1.10.0 scikit-learn==1.3.2 matplotlib pillow requests tqdm PyMaxflow opencv-python "torchmetrics>=0.7.0" "lightning-utilities>=0.8.0" lxml ninja`
5. `pip install setuptools==69.5.1` (required — see surprise #3)
6. `conda install -n gaussiancut -y -c nvidia/label/cuda-12.1.1 cuda-toolkit`
7. `conda install -n gaussiancut -y -c conda-forge gcc_linux-64=11 gxx_linux-64=11`
   (first tried 12.4.0 — fails, surprise #4)
8. **glm fix** (known missing build input): cloned https://github.com/g-truc/glm into
   `/root/gaussiancut/gaussian-splatting/submodules/diff-gaussian-rasterization/third_party/glm`,
   checked out `5c46b9c07008ae65cb81ab79cd677ecc1934b903` (the commit upstream
   graphdeco 3DGS pins). Header-only; nothing to compile.
9. Applied the source patches in §5 (SH-0 fix + dropped nvcc debug flags).
10. Built both extensions with the env's own toolchain:

```bash
PREFIX=/root/miniconda3/envs/gaussiancut
export PATH=$PREFIX/bin:/usr/bin:/bin
export CUDA_HOME=$PREFIX
export CC=$PREFIX/bin/x86_64-conda-linux-gnu-gcc
export CXX=$PREFIX/bin/x86_64-conda-linux-gnu-g++
export TORCH_CUDA_ARCH_LIST=8.9        # RTX 4080 Laptop = Ada, sm_89
export MAX_JOBS=4
cd /root/gaussiancut/gaussian-splatting/submodules/diff-gaussian-rasterization
$PREFIX/bin/pip install . --no-build-isolation
cd /root/gaussiancut/gaussian-splatting/submodules/simple-knn
$PREFIX/bin/pip install . --no-build-isolation
```

Notes on why these exact flags:
- `--no-build-isolation` is mandatory (setup.py imports torch; isolated build env has none).
- torch's cpp_extension automatically passes `-ccbin $CC` to nvcc when `CC` is set
  (`site-packages/torch/utils/cpp_extension.py:578-585`). Do **not** also set
  `NVCC_PREPEND_FLAGS='-ccbin …'` — nvcc rejects a duplicated `-ccbin`.
- Host gcc 13.3 (Ubuntu 24.04 system compiler) is too new for CUDA 12.1 nvcc; the conda
  gcc-11 toolchain inside the env is what nvcc uses.

## 5. Patches applied to /root/gaussiancut (git diff, verbatim)

Patch A = the user-approved SH-degree-0 fix (both render paths hardcoded 15 `f_rest`
coefficients and would crash on our degree-0 `gen_raw.ply`; now derived from the loaded
model). Patch B = dropped nvcc `-g -G` device-debug flags from the rasterizer build
(`-G` disables kernel optimization; correctness unaffected — build-speed/runtime-speed
decision recorded here). Untracked addition: `third_party/glm/` clone (§4 step 8).

```diff
diff --git a/gaussian-splatting/submodules/diff-gaussian-rasterization/setup.py b/gaussian-splatting/submodules/diff-gaussian-rasterization/setup.py
index ce9c3d0..7ca5ba7 100644
--- a/gaussian-splatting/submodules/diff-gaussian-rasterization/setup.py
+++ b/gaussian-splatting/submodules/diff-gaussian-rasterization/setup.py
@@ -28,8 +28,6 @@ setup(
             "rasterize_points.cu",
             "ext.cpp"],
             extra_compile_args={"nvcc": [
-                "-g",  # Enable debugging information for nvcc
-                "-G",
                 "-I" + os.path.join(os.path.dirname(os.path.abspath(__file__)), "third_party/glm/")]})
         ],
     cmdclass={
diff --git a/gaussian-splatting/utils/render_utils.py b/gaussian-splatting/utils/render_utils.py
index eaf1b8e..abbc211 100644
--- a/gaussian-splatting/utils/render_utils.py
+++ b/gaussian-splatting/utils/render_utils.py
@@ -152,7 +152,7 @@ def render_gc_sets(gaussians, scene, dataset: ModelParams,
         gaussians_colored._features_dc[remove_gauss == 1] = torch.ones(
             (int(remove_gauss.sum()), 1, 3), device="cuda") * RGB2SH(0)
         gaussians_colored._features_rest[remove_gauss == 1] = torch.zeros(
-            (int(remove_gauss.sum()), 15, 3),
+            (int(remove_gauss.sum()), gaussians_colored._features_rest.shape[1], 3),
             device="cuda")  # gaussians._features_rest * 0.0
         if select_images:
             camera_list = scene.getTrainCameras().copy() + scene.getTestCameras(
@@ -384,7 +384,7 @@ def render_coarse_sets(gaussians, scene, scene_path:str,dataset: ModelParams,
             gaussians_colored._features_dc[selected_mask == 1] = torch.ones(
                 (int(selected_mask.sum()), 1, 3), device="cuda") * RGB2SH(0)
             gaussians_colored._features_rest[selected_mask == 1] = torch.zeros(
-                (int(selected_mask.sum()), 15, 3),
+                (int(selected_mask.sum()), gaussians_colored._features_rest.shape[1], 3),
                 device="cuda")  # gaussians._features_rest * 0.0
             render_set(dataset.model_path,
                        "coarse_{}/select".format(identifier), scene.loaded_iter,
```

## 6. Surprises hit during the build (in order)

1. **MSYS path mangling**: invoking `wsl … pip install --index-url https://…` from Git
   Bash destroyed the URL (slashes stripped) and the command silently did nothing
   useful. All wsl one-liners were switched to PowerShell.
2. **numpy 2.x crept in**: `pip install torch==2.1.1` pulled numpy 2.2.6 (incompatible
   with torch 2.1-era binaries). Fixed by pinning `numpy==1.26.4` (scipy 1.10.0 needs
   <1.27 anyway).
3. **setuptools 83 breaks torch cpp_extension**: `ModuleNotFoundError: No module named
   'pkg_resources'` during both extension builds (pkg_resources was removed from new
   setuptools). Fix: `pip install setuptools==69.5.1`.
4. **gcc 12 host compiler + nvcc 12.1 + torch's bundled pybind11 = compile failure**:
   `pybind11/detail/cast.h:45:120: error: expected template-name before '<' token`.
   This is the known nvcc/pybind11 parse bug; gcc 11 as nvcc host compiler avoids it.
   Fix: `gcc_linux-64=11 gxx_linux-64=11` (11.4.0). This is why the env carries gcc 11,
   not 12, despite CUDA 12.1 nominally supporting gcc ≤12.2.
5. **`simple_knn._C` cannot be imported before torch** (`ImportError: libc10.so`): the
   extension links against torch's libs and relies on `import torch` having loaded
   them. The repo's own code always imports torch first, so this only affects
   hand-written test snippets.
6. **conda retry-loop false positive** (process note): piping `conda install … | tail`
   made the pipeline exit 0 even when conda failed; the first cuda-toolkit "success"
   had installed nothing. Re-ran with `set -o pipefail` and verified with
   `conda list` + `nvcc --version` afterward.

## 7. Smoke-test transcript (exact output, 2026-07-21)

```
=== 1. torch / CUDA ===
torch 2.1.1+cu121
cuda available: True
device: NVIDIA GeForce RTX 4080 Laptop GPU
torch cuda build: 12.1
=== 2. CUDA extensions ===
diff_gaussian_rasterization OK; has apply_weights kernel: True
simple_knn OK: distCUDA2
=== 3. repo-level import (from /root/gaussiancut/gaussian-splatting) ===
GaussianModel import OK; instantiated with sh_degree=0
=== SMOKE TEST PASSED ===
```

Plus real kernel execution on the GPU:

```
distCUDA2 kernel executed on GPU; mean sq dist: 0.006178866606205702
```

(`apply_weights` presence is verified on the compiled module; it is the custom
mask-back-projection kernel this whole lane depends on — a stock rasterizer wheel
would not have it.)

## 8. What the next step (Step 7 — view-pack) needs from here

- The env does NOT need activation from Windows; use the §2 one-liner.
- `segment_render.py` expects the fabricated dataset scaffold described in
  `FEASIBILITY_GAUSSIANCUT.md` §2a (cfg_args with `sh_degree=0`, COLMAP text
  `sparse/0/`, `images/`, `multiview_masks/`, `point_cloud/iteration_1/point_cloud.ply`).
- Frame gotcha still open (feasibility §5 risk 1): COLMAP extrinsics must be written in
  gen_raw.ply's RAW frame (physical up = −y). Verify via GaussianCut's own
  `--select_images` render-vs-gt outputs, judged by the user.
