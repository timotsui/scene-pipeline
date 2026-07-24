# ENV — splat_analyzer environment (Step 4 — analyzer-environment-build)

- Status: **SUCCESS** (built + smoke-tested 2026-07-21)
- Purpose: isolated environment that runs splat_analyzer's standalone local CLI
  (`run_local.py`) — the Gaussian-splat object-detection tool from
  github.com/nigelhartman/splat_analyzer — with ZERO compilation (this machine has
  no nvcc / CUDA compiler; everything installed from prebuilt binary wheels).
- Companion docs: feasibility study at
  `D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen\analyzer\FEASIBILITY_SPLAT_ANALYZER.md`;
  plan at `D:\T\Documents\GeorgiaTech\Summer2026\scene-pipeline\entangled_gen\docs\PLAN_GAUSSIAN_CUT_AND_SPLAT_ANALYZER.md`.

## Where everything lives

| What | Path |
|---|---|
| WSL distro | `Ubuntu-24.04` (user `root`) |
| Conda env name | `splatanalyzer` |
| Env directory | `/root/miniconda3/envs/splatanalyzer` (5.7 GB) |
| Env python (direct, no activation needed) | `/root/miniconda3/envs/splatanalyzer/bin/python` |
| Runnable repo copy | `/root/splat_analyzer` (15 MB, git clone of the reference at HEAD `a3cd884`) |
| Reference clone (READ-ONLY, never modify) | `D:\T\Documents\GeorgiaTech\Summer2026\Research\code\reference\splat_analyzer` |
| HuggingFace model cache | `/root/.cache/huggingface` (593 MB, all of it the OWLv2 model) |

## Activation + invocation pattern (callable from Windows)

The robust pattern uses the env's python binary directly — no `conda activate` needed:

```
wsl -d Ubuntu-24.04 -- bash -c "cd /root/splat_analyzer && /root/miniconda3/envs/splatanalyzer/bin/python run_local.py --ply <PLY> --prompt '<labels>' --quality <low|medium|high> --job_dir <ABSOLUTE_OUT_DIR>"
```

Concrete example for Step 5 (the bedroom_marble scene; WSL sees drive D: as `/mnt/d`):

```
wsl -d Ubuntu-24.04 -- bash -c "cd /root/splat_analyzer && /root/miniconda3/envs/splatanalyzer/bin/python run_local.py --ply '/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out/bedroom_marble/gen_raw.ply' --prompt 'bed, nightstand, lamp, chair, rug, curtain, picture frame' --quality low --job_dir '/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out/bedroom_marble/analyzer/out_low'"
```

Interactive activation (only if a human wants a shell inside the env):

```
wsl -d Ubuntu-24.04
source /root/miniconda3/etc/profile.d/conda.sh && conda activate splatanalyzer
```

Notes:
- Always pass `--job_dir` as an ABSOLUTE path (default is relative to the current
  working directory).
- The OWLv2 model is already cached; runs work offline. To force offline, prefix
  the python command with `HF_HUB_OFFLINE=1`.
- Optional: `WMD_DEVICE=cpu` moves the OWLv2 detector off the GPU (renderer still
  requires CUDA).

## Pinned versions (verified installed)

| Package | Version | Source |
|---|---|---|
| python | 3.10.20 | conda (`conda create -n splatanalyzer python=3.10`) |
| torch | **2.4.1+cu124** | `https://download.pytorch.org/whl/cu124` |
| torchvision | 0.19.1+cu124 | same index |
| gsplat | **1.5.3+pt24cu124** | `https://docs.gsplat.studio/whl/pt24cu124` (BINARY wheel, `--no-deps`) |
| transformers | 4.50.3 | PyPI (repo pin) |
| numpy | 1.26.4 | PyPI (`numpy<2` repo constraint; the torch install briefly pulled numpy 2.2.6, step 4 downgraded it correctly) |
| scipy | 1.15.3 | PyPI (repo pin) |
| opencv-python-headless | 4.11.0.86 | PyPI (repo pin) |
| imageio | 2.37.3 | PyPI (repo pin) |
| plyfile | 1.1.3 | PyPI (repo pin) |
| Pillow | 12.2.0 | PyPI (repo leaves unpinned) |
| six | 1.17.0 | PyPI (repo pin) |
| ninja / jaxtyping / rich | 1.13.0 / 0.3.7 / 15.0.0 | PyPI (gsplat runtime deps, installed manually because gsplat used `--no-deps`) |

Deliberately NOT installed: `fastapi`, `uvicorn`, `python-multipart` — server-mode
only; `run_local.py` never imports them (feasibility doc §a/§b).

Torch-safety check: after ALL installs, `torch.__version__` re-verified as
`2.4.1+cu124` (the build script hard-fails if pip ever re-resolves torch). The
Windows system python (torch 2.6.0+cu124) was never touched — everything here is
inside the WSL conda env.

## gsplat: binary wheel, zero compilation — evidence

1. Wheel downloaded from the dedicated index as
   `gsplat-1.5.3+pt24cu124-cp310-cp310-linux_x86_64.whl` (21.9 MB); the
   `+pt24cu124` local-version tag exists ONLY on the binary index, never on PyPI
   (PyPI's `gsplat 1.5.3` is a pure-python wheel that JIT-compiles CUDA kernels at
   first use — that one was avoided via `--index-url ... --no-deps`).
2. Installed package contains the precompiled CUDA extension
   `/root/miniconda3/envs/splatanalyzer/lib/python3.10/site-packages/gsplat/csrc.so` (69 MB).
3. `import gsplat` took **1.20 s** (a JIT build takes many minutes and would be
   impossible anyway — `which nvcc` finds nothing in the distro).
4. A real rasterization call ran the CUDA kernel successfully (smoke D below).
5. `~/.cache/torch_extensions` gained NO new entries (the one existing entry,
   `py310_cu126/nvdiffrast_plugin`, is dated 2026-07-06/07 — an unrelated leftover
   predating this build).

## OWLv2 detection model (pre-downloaded, Step 5 runs offline-fast)

- Model id: **`google/owlv2-base-patch16-ensemble`** (the exact id
  `pipeline.py:146-147` loads; 155.0 M parameters).
- Cache: `/root/.cache/huggingface/hub/models--google--owlv2-base-patch16-ensemble`
  — **593 MB** total (single ~620 MB safetensors blob + processor configs).
  The 1.5–2 GB estimate in the feasibility doc was an overestimate; this is the
  *base* OWLv2 model and it is fully downloaded (verified by loading the processor
  with `HF_HUB_OFFLINE=1`, which fails on partial caches).

## Smoke-test transcript (2026-07-21, exit code 0)

```
=== [A] OWLv2 pre-download (google/owlv2-base-patch16-ensemble) ===
OWLV2_DOWNLOAD_OK params=155.0M
593M    /root/.cache/huggingface
593M    /root/.cache/huggingface/hub/models--google--owlv2-base-patch16-ensemble
=== [B] smoke 1: torch CUDA ===
torch 2.4.1+cu124 | cuda.is_available: True | device: NVIDIA GeForce RTX 4080 Laptop GPU
=== [C] smoke 2: gsplat import timing (must be seconds, no JIT compile) ===
gsplat 1.5.3+pt24cu124 | import took 1.20s
=== [D] smoke 3: actual gsplat CUDA rasterization kernel (1 gaussian, 256x256) ===
RASTER_OK shape=(1, 256, 256, 3) alpha_max=0.899 wall=1.27s
=== [E] smoke 4: OWLv2 processor loads OFFLINE from cache ===
transformers 4.50.3 | OWLv2 processor loaded offline from cache: Owlv2Processor
=== [F] smoke 5: run_local.py --help ===
usage: run_local.py [-h] --ply PLY --prompt PROMPT
                    [--quality {low,medium,high}] [--job_dir JOB_DIR]
                    [--score_threshold SCORE_THRESHOLD]
                    [--min_votes MIN_VOTES] [--min_peak_score MIN_PEAK_SCORE]
Run 3DGS object detection locally.
=== [G] disk usage ===
conda env:  5.7G
repo copy:  15M
HF cache:   593M
SMOKE_ALL_OK
```

(Section C's raw log also printed a "torch_extensions JIT cache appeared" warning —
that was a false positive from a naive existence check; the directory pre-existed
with a 2026-07-06 timestamp and gained nothing. See evidence list above.)

## Disk used

| Item | Size |
|---|---|
| conda env `/root/miniconda3/envs/splatanalyzer` | 5.7 GB |
| repo copy `/root/splat_analyzer` | 15 MB |
| HuggingFace cache `/root/.cache/huggingface` | 593 MB |
| **Total** | **~6.3 GB** (inside the WSL virtual disk on C:) |

## Step-5 watch items (copied from the feasibility study — do not skip)

1. **First run MUST be `--quality low` (24 frames) purely for the orientation
   eyeball.** The tool silently assumes the splat file's frame has physical up =
   file −Y (the standard 3D-Gaussian-splatting convention). Our `gen_raw.ply` raw
   frame should match, but if a y-up copy is fed in, EVERY frame renders
   upside-down with no error — detections degrade silently. The user (never the
   agent) must look at a few `frames/frame_XXXX.png` in the job dir and confirm
   rooms are right-side up before any medium/high run.
2. **Do not judge detection quality on the low preset.** `--min_votes` defaults
   to 8, tuned for the 90/192-frame presets; against low's 24 frames it is
   aggressive (an object seen from one standpoint appears in ~8 frames total).
   For real runs use `--quality medium`/`high`, or lower `--min_votes` when
   forced to run low.
3. **Hard cap: at most 3 objects per label** (`max_per_label = 3`,
   `pipeline.py:280` — not a CLI flag). Scenes with 4+ instances of one label
   (e.g. "picture frame") get truncated; needs a one-line source edit in
   `/root/splat_analyzer/pipeline.py` if it bites.
4. Output `position` is a score-weighted centroid of visible-surface points (not
   a volumetric box center) and the box z-extent is fabricated as
   (width+height)/2 — account for this in the Step 6/8 comparison.
5. Always pass an absolute `--job_dir`; a high run writes 192 × (RGB PNG + depth
   NPY + depth PNG) ≈ a few hundred MB.

## Rebuild recipe (if the env is ever lost)

```
wsl -d Ubuntu-24.04
/root/miniconda3/bin/conda create -n splatanalyzer python=3.10 -y
/root/miniconda3/envs/splatanalyzer/bin/pip install torch==2.4.1 torchvision==0.19.1 --index-url https://download.pytorch.org/whl/cu124
/root/miniconda3/envs/splatanalyzer/bin/pip install gsplat==1.5.3 --index-url https://docs.gsplat.studio/whl/pt24cu124 --no-deps
/root/miniconda3/envs/splatanalyzer/bin/pip install "transformers==4.50.3" "numpy<2" "imageio==2.37.3" "plyfile==1.1.3" "opencv-python-headless==4.11.0.86" Pillow "scipy==1.15.3" "six==1.17.0" ninja jaxtyping "rich>=12"
```

Risk noted in the feasibility doc: if the `docs.gsplat.studio` wheel host ever
disappears, the zero-compile path dies with it — consider archiving
`gsplat-1.5.3+pt24cu124-cp310-cp310-linux_x86_64.whl` from pip's cache
(`/root/.cache/pip`) if that becomes a concern.

## Runnable-copy modifications (deviations of `/root/splat_analyzer` from reference HEAD `a3cd884`)

- **2026-07-21 — per-label cluster cap 3 → 8** (Step 5 phase 2, coordinator-approved,
  one line at the `_cluster_detections` call site, `pipeline.py:280`). Reason: the
  bedroom_marble manifest contains 4 doors + 3 shelves; the hard cap of 3 would
  truncate the comparison run. The reference clone on D: is untouched. Exact diff
  (`git diff` inside `/root/splat_analyzer`):

```diff
diff --git a/pipeline.py b/pipeline.py
index 7479e72..5fa1704 100644
--- a/pipeline.py
+++ b/pipeline.py
@@ -277,7 +277,7 @@ def run_pipeline(ply_path: str, prompt: str, job_dir: str,
         clustered = _cluster_detections(
             raw_detections,
             eps_m=transforms.get("scene_radius", scene_radius) * 0.20,
-            max_per_label=3,
+            max_per_label=8,
             min_votes=cfg.min_votes,
             min_peak_score=cfg.min_peak_score,
         )
```

  The function-signature default at `pipeline.py:76` (`max_per_label=3`) was
  deliberately left unchanged — the call site always passes the value explicitly,
  so only the approved line differs from HEAD. Observed in the phase-2 high run
  on bedroom_marble: the new cap of 8 itself binds (5 labels returned exactly 8
  clusters: bookshelf, book, painting, shelf, bed).
