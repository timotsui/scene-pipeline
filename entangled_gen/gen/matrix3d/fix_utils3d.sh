#!/bin/bash
# fix_utils3d.sh — Matrix-3D's vendored MoGe (code/MoGe/scripts/infer_panorama.py)
# needs the OLD utils3d API (utils3d.numpy.icosahedron). install.sh grabbed
# git HEAD, where c7509ba renamed it (create_*_mesh). Install c7509ba's
# parent — the last pre-rename commit.
set -o pipefail
exec > >(tee /root/m3d_utils3d.log) 2>&1
source /root/miniconda3/etc/profile.d/conda.sh
conda activate matrix3d
export PIP_CONSTRAINT=/root/m3d_constraints.txt

WORK=/root/u3d_probe
rm -rf "$WORK"
git clone -q https://github.com/EasternJournalist/utils3d.git "$WORK" || exit 1
cd "$WORK" || exit 1
PARENT=$(git rev-parse 'c7509ba^') || exit 1
echo "pre-rename commit: $PARENT"
git grep -q 'def icosahedron' "$PARENT" || { echo "NO icosahedron at parent — walk further back manually"; exit 1; }

pip install -q --force-reinstall --no-deps "git+https://github.com/EasternJournalist/utils3d.git@$PARENT" || exit 1
python - <<'PY'
import utils3d.numpy as u
assert hasattr(u, "icosahedron"), "icosahedron still missing"
print("UTILS3D_FIX_OK — icosahedron present")
PY
