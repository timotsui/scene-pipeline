#!/bin/bash
# run_scenedreamer360.sh  <prompt>  <out_raw_ply_wslpath>  <seed>
#
# Drives SceneDreamer360 for a single text prompt and copies the resulting
# gsplat.ply to <out_raw_ply>.
#
# Flow (main.py cli_main): PanFusion predict (runs on LightningCLI instantiation)
#   -> writes logs/4142dlo4/predict/e9zR4mvMWw7_test/pano.jpg
#   -> enhancement bypassed (patched out) -> multi-view projection
#   -> LucidDreamer/PanoSpaceDreamer 3DGS -> save_dir/gsplat.ply
#
# We drive main.py DIRECTLY (not run.py) with one clean prompt file so pano_id is
# deterministic ('e9zR4mvMWw7_test') and repeated runs don't trip run.py's rename.
#
# Repo patches applied (see git diff in repos/SceneDreamer360):
#   - main.py: '../logs' -> 'logs'; Enhance_img (Baidu) instantiation commented out
#   - luciddreamer.py: runwayml SD-inpaint -> community mirror; ZoeDepth path from __file__
set -o pipefail
PROMPT="${1:?prompt}"; OUT_PLY="${2:?out ply}"; SEED="${3:-1}"

source /root/miniconda3/etc/profile.d/conda.sh
set +u; conda activate panfusion

# WSL: the CUDA driver stub (libcuda.so) lives here and isn't on the loader path,
# so cuDNN's libcudnn_cnn_infer.so.8 fails to dlopen it. Also expose the wheel's cudnn.
export LD_LIBRARY_PATH="/usr/lib/wsl/lib:$CONDA_PREFIX/lib/python3.9/site-packages/nvidia/cudnn/lib:$LD_LIBRARY_PATH"

REPO=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/repos/SceneDreamer360
cd "$REPO" || exit 1

# one clean prompt file -> view_id 'test' -> pano_id 'e9zR4mvMWw7_test'
BLIP=data/Matterport3D/mp3d_skybox/e9zR4mvMWw7/blip3_stitched
mkdir -p "$BLIP"
find "$BLIP" -name '*.txt' -delete
printf '%s\n' "$PROMPT" > "$BLIP/test.txt"

python - "$SEED" "$BLIP/test.txt" <<'PY'
import json, sys
cfg = json.load(open('config.json'))
cfg['seed'] = int(sys.argv[1]); cfg['text'] = sys.argv[2]
cfg['campath_gen'] = 'fullscan'; cfg['campath_render'] = '1440'
json.dump(cfg, open('config.json','w'), ensure_ascii=False, indent=4)
PY

# PATCHED (entangled_gen) 2026-07-04e: clear the predict output dir before running.
# PanFusion.inference_and_save() early-returns if <output_dir>/prompt.txt exists
# (a resume guard). pano_id is deterministic ('e9zR4mvMWw7_test'), so without this
# every re-run reads run 5's STALE black pano.jpg and skips denoising entirely
# (tell: 'Predicting DataLoader 0: 100% ... 42 it/s' = instant, no 20-step denoise).
# This was the real cause of the "black output persists after the 04d fp32 fix":
# the fix was never exercised. Remove the whole dir so pano + views regenerate.
PREDICT_DIR="logs/4142dlo4/predict/e9zR4mvMWw7_test"
if [ -d "$PREDICT_DIR" ]; then
  echo ">>> clearing stale predict dir $PREDICT_DIR"
  rm -rf "$PREDICT_DIR"
fi

echo ">>> running SceneDreamer360 for: $PROMPT"
# NOTE: pointing at the stripped ckpt (optimizer_states/lr_schedulers removed;
# 9.23 -> 8.26 GB). Revert to --ckpt_path=last if it fails to load.
CKPT_REL=logs/4142dlo4/checkpoints/last.ckpt.stripped
[ -f "$CKPT_REL" ] || CKPT_REL=last
# precision: the two PanFusion UNets default to fp32 (trainer default precision:32)
# which peaked at 11.7 GB VRAM and froze the machine; a true-half policy halves the
# weights (~3.4 GB saved). VAE/text-encoder are already fp16.
# PATCHED (entangled_gen) 2026-07-04f: bf16-true, NOT 16-true. Run 6b (first run to
# actually denoise, after the 04e stale-guard fix) showed the UNet produces NaN
# latents BEFORE the VAE decode — the classic SD2 pure-fp16 instability (activations
# exceed fp16's 65504 max -> Inf -> NaN). fp16-VAE-decode (04d) was the wrong stage.
# bf16 has fp16's memory footprint (keeps the VRAM win) but fp32's exponent range,
# so no overflow. Ada sm_89 + torch 2.0.1 + xformers 0.0.22 all support bf16.
# PATCHED (entangled_gen) 2026-07-04g: traindata cache — generate_pcd costs ~1 h;
# if the later 3DGS stage dies (run 6e OOM), the relaunch resumes from this pickle.
# Keyed by prompt+seed so a different prompt can never reuse a stale cache.
OUT_DIR=/mnt/d/T/Documents/GeorgiaTech/Summer2026/CS-8903-OVM/week7/entangled_gen/out
CACHE_KEY=$(printf '%s|%s' "$PROMPT" "$SEED" | md5sum | cut -c1-10)
mkdir -p "$OUT_DIR/cache"
export ENTANGLED_TRAINDATA_CACHE="$OUT_DIR/cache/traindata_${CACHE_KEY}.pkl"
echo ">>> traindata cache: $ENTANGLED_TRAINDATA_CACHE"

# PATCHED (entangled_gen) 2026-07-04h: no densification — run 7 OOM'd when
# densify_and_split grew the 3M-point init past the VRAM cap mid-training.
# Dense depth-projected init doesn't need it (it exists for sparse SfM seeds).
export ENTANGLED_DENSIFY_UNTIL=0

WANDB_MODE=offline WANDB_RUN_ID=4142dlo4 \
  python main.py predict --data=Matterport3D --model=PanFusion --ckpt_path="$CKPT_REL" \
    --trainer.precision=bf16-true
RC=$?
echo ">>> pipeline rc=$RC"

PLY=$(find logs/4142dlo4/predict -name 'gsplat.ply' 2>/dev/null | sort | tail -1)
if [ -n "$PLY" ] && [ -f "$PLY" ]; then
  mkdir -p "$(dirname "$OUT_PLY")"; cp "$PLY" "$OUT_PLY"
  echo "OK copied $PLY -> $OUT_PLY"; exit 0
fi
echo "NO_PLY_PRODUCED (rc=$RC) — inspect $REPO/logs/4142dlo4"
exit 1
