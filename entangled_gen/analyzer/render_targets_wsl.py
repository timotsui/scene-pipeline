"""Render aimed retake views with the analyzer's OWN gsplat path (G4).

Runs INSIDE the WSL `splatanalyzer` env (torch 2.4 + gsplat 1.5.3), importing
the tool's ply loader from /root/splat_analyzer — the exact renderer + camera
convention (c2w OpenCV) that produced the G1-verified sweep frames.
splat-transform (shot.py) was tried first and FAILED mechanically (9/18 blank
renders despite the z-buffer model seeing 2-12%% of points; inconsistent
orientation on the rest — see PLAN_SPLAT_RECENTER.md G4 notes).

Invoke from Windows:
  wsl -d Ubuntu-24.04 -- bash -c "cd /root/splat_analyzer && \
    /root/miniconda3/envs/splatanalyzer/bin/python \
    /mnt/d/.../analyzer/render_targets_wsl.py \
    --targets /mnt/d/.../seg_sweep/rc/targets.json \
    --ply /mnt/d/.../gen_raw.ply --out /mnt/d/.../seg_sweep/rc --res 768"
"""
import argparse, json, math, sys
from pathlib import Path

import numpy as np
import torch

sys.path.insert(0, "/root/splat_analyzer")
from render_cameras import _load_ply_arrays          # noqa: E402
from renderers.base import NEAR_PLANE, FAR_PLANE     # noqa: E402
from gsplat import rasterization                     # noqa: E402


def c2w_from_eye_aim(eye, aim, up_w):
    """OpenCV c2w (x right, y down, z forward) from eye/aim + world up."""
    eye = np.asarray(eye, np.float64)
    fwd = np.asarray(aim, np.float64) - eye
    fwd /= np.linalg.norm(fwd)
    up_w = np.asarray(up_w, np.float64)
    right = np.cross(fwd, up_w)
    n = np.linalg.norm(right)
    if n < 1e-6:                       # looking straight along up: pick any
        right = np.cross(fwd, [1.0, 0.0, 0.0])
        n = np.linalg.norm(right)
    right /= n
    down = np.cross(fwd, right)        # right x down = fwd (opencv handed)
    M = np.eye(4)
    M[:3, 0], M[:3, 1], M[:3, 2], M[:3, 3] = right, down, fwd, eye
    return M


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--targets", required=True)
    ap.add_argument("--ply", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--res", type=int, default=768)
    ap.add_argument("--prefix", default="rc_",
                    help="output name prefix (rc_ for retakes, sp_ for the "
                         "pano-rig standpoint views)")
    a = ap.parse_args()
    outd = Path(a.out)
    outd.mkdir(parents=True, exist_ok=True)
    targets = json.loads(Path(a.targets).read_text())
    W = H = a.res

    dev = torch.device("cuda")
    arr = _load_ply_arrays(a.ply)
    g = {
        "means": torch.tensor(arr["means"], device=dev),
        "quats": torch.tensor(arr["quats"], device=dev),
        "scales": torch.exp(torch.tensor(arr["scales"], device=dev)),
        "opacities": torch.sigmoid(torch.tensor(arr["opacities"], device=dev)),
        "sh": torch.tensor(arr["sh_coeffs"], device=dev),
        "sh_degree": int(arr["sh_degree"]),
    }
    print(f"[wslrender] {g['means'].shape[0]:,} gaussians, sh_degree "
          f"{g['sh_degree']}", flush=True)

    from PIL import Image
    for k, t in enumerate(targets):
        name = t.get("name", f"{a.prefix}{k:02d}") + ".png"
        f = outd / name
        if f.exists():
            continue
        fov_x = math.radians(float(t["fov"]))
        fl = W / (2.0 * math.tan(fov_x / 2.0))
        K = torch.tensor([[fl, 0, W / 2.0], [0, fl, H / 2.0], [0, 0, 1]],
                         dtype=torch.float32, device=dev)
        c2w = c2w_from_eye_aim(t["eye"], t["aim"], [0.0, -1.0, 0.0])
        w2c = torch.linalg.inv(
            torch.tensor(c2w, dtype=torch.float32, device=dev)).unsqueeze(0)
        rgb, _, _ = rasterization(
            means=g["means"], quats=g["quats"], scales=g["scales"],
            opacities=g["opacities"], colors=g["sh"],
            viewmats=w2c, Ks=K.unsqueeze(0),
            width=W, height=H, sh_degree=g["sh_degree"],
            near_plane=NEAR_PLANE, far_plane=FAR_PLANE)
        img = (rgb[0].clamp(0, 1).cpu().numpy() * 255).astype(np.uint8)
        Image.fromarray(img).save(f)
        t["file"] = name
        t["c2w"] = c2w.tolist()
        print(f"[wslrender] {name} ({t['label']}, fov {t['fov']})", flush=True)
        import time
        time.sleep(1.0)      # GPU pacing (laptop hard-crash mitigation)
    Path(a.targets).write_text(json.dumps(targets, indent=1))
    print("[wslrender] done", flush=True)


if __name__ == "__main__":
    main()
