#!/bin/bash
# download_weights.sh — HunyuanWorld 1.0 weight pulls (WSL, env HunyuanWorld).
# Cache: default /root/.cache/huggingface (WSL ext4 vhdx on C:).
#
# GATED PREREQ (user, once, in a browser): accept licenses with your HF account
#   https://huggingface.co/black-forest-labs/FLUX.1-dev        (pano stage)
#   https://huggingface.co/black-forest-labs/FLUX.1-Fill-dev   (scenegen + img-cond)
# then in WSL:  hf auth login   (paste a READ token; 'huggingface-cli' is the
# deprecated name of the same tool)
set -o pipefail
source /root/miniconda3/etc/profile.d/conda.sh
conda activate HunyuanWorld

# public — PanoDiT/PanoInpaint LoRAs, 1.1 GB — DONE 2026-07-05
hf download tencent/HunyuanWorld-1

# gated — needed for step 1.2 (pano). ~24 GB.
hf download black-forest-labs/FLUX.1-dev

# gated — needed for step 1.3 (scenegen layer inpaint) and 1.5 (image
# conditioning). ~24 GB. Uncomment when 1.3 is a go:
# hf download black-forest-labs/FLUX.1-Fill-dev
