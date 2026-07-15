# WorldMirror 2.0 harness (Exp 4 local leg)

Feed-forward multi-view recon (tencent/HY-World-2.0, `HY-WorldMirror-2.0`
subfolder, ~5 GB weights ≈ 2.5B params — fits the 12 GB card, unlike the 17B
WorldStereo pano stage which stays rental-territory).

Adaptation: WorldMirror takes PERSPECTIVE images, not equirect panos, so we
feed it a crop rig of our own pano (zero-baseline caveat — depth must come
from monocular priors, not parallax; this IS the experiment).

Chain (bedroom, one-scene-per-pipeline):
1. Windows python: `python make_crops.py OUT/bedroom_hw1/panorama.png OUT/bedroom_hw1/crops`
2. WSL: `bash setup_env.sh` (conda env `worldmirror`; see header for the
   dependency findings — requirements_git.txt is training-only, SKIPPED)
3. WSL: `bash download_weights.sh` (5 GB, HF cache)
4. Guarded (clock lock + deadman): `bash run_worldmirror.sh bedroom_hw1 bedroom_hw2`
   → `OUT/bedroom_hw2/gen_raw.ply` → standard eval kit.

Sequencing rule (2026-07-07): steps 2-4 must NOT run while another heavy job
owns the WSL RAM cap (a concurrent cgroup OOM would kill the wrong process).
