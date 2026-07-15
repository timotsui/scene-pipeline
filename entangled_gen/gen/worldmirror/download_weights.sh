#!/bin/bash
# download_weights.sh — fetch ONLY the WorldMirror 2.0 weights (~5 GB) from
# tencent/HY-World-2.0; the sibling HY-Pano-2.0 (80B pano stage) is 169 GB
# and is NOT wanted locally. Downloads into the default HF cache so
# WorldMirrorPipeline.from_pretrained() hits cache at run time.
set -e
source /root/miniconda3/etc/profile.d/conda.sh
conda activate worldmirror
python - <<'PY'
from huggingface_hub import snapshot_download
p = snapshot_download("tencent/HY-World-2.0",
                      allow_patterns=["HY-WorldMirror-2.0/*"])
print("weights at", p)
PY
echo "WORLDMIRROR_WEIGHTS_OK"
