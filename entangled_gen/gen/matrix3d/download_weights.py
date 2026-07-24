"""Selective Matrix-3D checkpoint download (~35-40 GB vs ~140 GB full set).

Run with the HunyuanWorld env's python (has huggingface_hub); writes into the
Matrix-3D repo's ./checkpoints layout (repo location derived from
local_paths.json's data root: <out>/../repos/Matrix-3D). Skips: pano_lrm
(80 GB VRAM path), 480p/720p 14B LoRAs + Wan2.1-14B bases, text2panoimage
LoRA (we bring our own panos). Also creates the wan-lora/wan_lora
hyphen/underscore twin the repo needs (see README).
"""
import os
import sys

from huggingface_hub import hf_hub_download, snapshot_download

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
import paths  # noqa: E402  (entangled_gen/paths.py — OUT from local_paths.json)


def _wsl(p):
    """Windows drive path -> /mnt form (this script runs under WSL)."""
    s = str(p).replace("\\", "/")
    return f"/mnt/{s[0].lower()}{s[2:]}" if len(s) > 1 and s[1] == ":" else s


REPO = _wsl(paths.OUT.parent / "repos" / "Matrix-3D")
CK = os.path.join(REPO, "checkpoints")


def main():
    # 1) Wan2.2-TI2V-5B base (T5 + 5B DiT + VAE) — the big one (~25 GB)
    snapshot_download("Wan-AI/Wan2.2-TI2V-5B",
                      local_dir=os.path.join(CK, "Wan-AI", "Wan2.2-TI2V-5B"))

    # 2) pano video LoRA for the 5B model
    for d in ("wan_lora", "wan-lora"):
        os.makedirs(os.path.join(CK, "Wan-AI", d), exist_ok=True)
    p = hf_hub_download("Skywork/Matrix-3D",
                        "checkpoints/pano_video_gen_720p_5b.safetensors",
                        local_dir=os.path.join(CK, "Wan-AI", "wan_lora"))
    twin = os.path.join(CK, "Wan-AI", "wan-lora", "pano_video_gen_720p_5b.safetensors")
    if not os.path.exists(twin):
        try:
            os.link(p, twin)
        except OSError:
            import shutil
            shutil.copy2(p, twin)

    # 3) MoGe depth (recon)
    hf_hub_download("Ruicheng/moge-vitl", "model.pt",
                    local_dir=os.path.join(CK, "moge"))

    # 4) StableSR + VEnhancer (video SR used in the recon path)
    hf_hub_download("Iceclear/StableSR", "stablesr_turbo.ckpt",
                    local_dir=os.path.join(CK, "StableSR"))
    hf_hub_download("Iceclear/StableSR", "vqgan_cfw_00011.ckpt",
                    local_dir=os.path.join(CK, "StableSR"))
    hf_hub_download("jwhejwhe/VEnhancer", "venhancer_v2.pt",
                    local_dir=os.path.join(REPO, "code", "VideoSR", "checkpoints"))

    print("M3D_WEIGHTS_OK")


if __name__ == "__main__":
    main()
