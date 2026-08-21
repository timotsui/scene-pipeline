"""Equirect panorama -> pinhole perspective crops + camera sidecars
(WEEK8_OBJECT_ID_PLAN stage 2 substrate).

Detectors degrade on equirect distortion, so detection runs on normal-looking
pinhole views sliced from the pano. Crops are written EXACTLY like the GPU
view renders (webp + gpu_*.json-format sidecar, same Cam convention as
rendertools 03_render.py), so seg_views.py and the lift machinery consume
them unmodified:

  out/<scene>/pano_crops/pano_y{yaw:03d}_p{pitch}{deg:02d}.webp + .json

Default rig: 8 yaws x fov 75 at pitch 0, 8 at pitch -40 (floor objects),
4 at pitch +40 (ceiling), from the pano camera at the origin. At 4608x2304
a 75-degree crop at 960px is ~native pano pixel density — a further zoom
pass adds nothing (the pano resolution is the ceiling).

Pose contract (A2, user-verified 2026-07-07): pano camera = origin, +y up,
image center = +Z, theta grows toward +X, v=0 = up.

  python crop_pano.py --scene bedroom_marble
"""
import argparse, json
from datetime import datetime
from pathlib import Path
import numpy as np
from PIL import Image

import paths

RINGS = [(0, 8), (-40, 8), (40, 4)]   # (pitch deg, n yaws)
FOV = 75.0
RES = 960


def crop_dirs(cam, res):
    """Unit world ray directions for every pixel of a Cam view (same math as
    lift_views.unproject_px / 03_render.unproject)."""
    u, v = np.meshgrid(np.arange(res) + 0.5, np.arange(res) + 0.5)
    x = (u - cam.cx) / cam.f
    y = -(v - cam.cy) / cam.f
    d = np.stack([x, y, np.ones_like(x)], axis=-1).reshape(-1, 3)
    d /= np.linalg.norm(d, axis=1, keepdims=True)
    return d @ cam.R          # cam -> world (R rows are world axes of cam)


def sample_equirect(pano, dirs, W, H):
    """Bilinear equirect lookup, u wraps, v clamps. dirs: (N,3) unit, +y up,
    center=+Z, theta toward +X."""
    theta = np.arctan2(dirs[:, 0], dirs[:, 2])
    phi = np.arcsin(np.clip(dirs[:, 1], -1, 1))
    uf = (theta / (2 * np.pi) + 0.5) * W - 0.5
    vf = (0.5 - phi / np.pi) * H - 0.5
    u0 = np.floor(uf).astype(np.int64); v0 = np.floor(vf).astype(np.int64)
    du = (uf - u0)[:, None]; dv = (vf - v0)[:, None]
    u1 = (u0 + 1) % W; u0 = u0 % W
    v0 = np.clip(v0, 0, H - 1); v1 = np.clip(v0 + 1, 0, H - 1)
    p = pano
    out = (p[v0, u0] * (1 - du) * (1 - dv) + p[v0, u1] * du * (1 - dv)
           + p[v1, u0] * (1 - du) * dv + p[v1, u1] * du * dv)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--pano", default="", help="equirect png (default: bundle *_pano.png)")
    ap.add_argument("--res", type=int, default=RES)
    ap.add_argument("--fov", type=float, default=FOV)
    ap.add_argument("--out-dir", default="",
                    help="override output dir (default pano_crops/ — pass "
                         "this for self-rendered panos so the Marble crops "
                         "are not clobbered)")
    ap.add_argument("--name-prefix", default="",
                    help="prefix crop stems when combining multiple standpoints")
    ap.add_argument("--eye-raw", default="",
                    help="exact RAW/world pano eye x,y,z; writes exact OpenCV c2w sidecars")
    ap.add_argument("--pano-to-raw-signs", default="1,-1,1")
    a = ap.parse_args()

    if a.pano:
        panof = Path(a.pano)
    else:
        # THE CANONICAL FUNNEL ALWAYS PASSES --pano (the self-rendered
        # equirect from pano_stitch.py), so this branch is the bundle
        # fallback only. It used to be a bare next() on "*_pano.png",
        # which matches the deprecated 07-07 manual downloads and NONE of
        # the 300-plus harvest bundles — those carry pano_rgb_0.png. On a
        # real bundle it raised StopIteration with no message at all.
        # vocab_build.find_pano was fixed for exactly this on 08-06; this
        # is the same rule, and it says what went wrong.
        from vocab_build import find_pano
        panof = find_pano(a.scene)
        if panof is None:
            raise SystemExit(
                f"[crop] no equirect pano for scene '{a.scene}'. Pass "
                f"--pano (the funnel passes rig_sp0/pano_selfrender.png "
                f"from pano_stitch.py), or put a *pano*.png / *pano*.jpg "
                f"in the bundle that out/{a.scene}/bundle_path.txt "
                f"points at.")

    Image.MAX_IMAGE_PIXELS = None
    pano = np.asarray(Image.open(panof).convert("RGB"), np.float32)
    H, W = pano.shape[:2]
    print(f"pano {W}x{H}  {panof.name}")

    r3 = paths.load_r3()
    outd = Path(a.out_dir) if a.out_dir else paths.pano_crops_dir(a.scene)
    outd.mkdir(parents=True, exist_ok=True)
    eye_raw = None
    signs = None
    if a.eye_raw:
        eye_raw = np.asarray([float(t) for t in a.eye_raw.split(",")], float)
        signs = np.asarray([float(t) for t in a.pano_to_raw_signs.split(",")], float)
        if eye_raw.shape != (3,) or signs.shape != (3,):
            ap.error("--eye-raw and --pano-to-raw-signs require x,y,z")

    n_out = 0
    for pitch, nyaw in RINGS:
        for i in range(nyaw):
            yaw = 360.0 * i / nyaw
            ry, rp = np.radians(yaw), np.radians(pitch)
            fwd = np.array([np.cos(rp) * np.sin(ry), np.sin(rp), np.cos(rp) * np.cos(ry)])
            cam = r3.Cam([0, 0, 0], fwd, [0, 1, 0], a.fov, a.res, a.res)
            img = sample_equirect(pano, crop_dirs(cam, a.res), W, H).reshape(a.res, a.res, 3)
            img = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).convert("RGB")
            tag = (f"{a.name_prefix}pano_y{int(round(yaw)):03d}_"
                   f"p{'m' if pitch < 0 else 'p'}{abs(pitch):02d}")
            img.save(outd / f"{tag}.webp", quality=92)
            side = {"file": f"{tag}.webp",
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "preset": "", "cam": "0,0,0",
                    "look": ",".join(f"{v:.6f}" for v in fwd),
                    "up": "0,1,0", "fov": a.fov, "near": 0.2,
                    "box": "", "sphere": "", "res": f"{a.res}x{a.res}",
                    "ply": str(panof)}
            if eye_raw is not None:
                R_raw = cam.R * signs[None, :]
                c2w_cv = np.eye(4, dtype=float)
                c2w_cv[:3, 0] = R_raw[0]
                c2w_cv[:3, 1] = -R_raw[1]
                c2w_cv[:3, 2] = R_raw[2]
                c2w_cv[:3, 3] = eye_raw
                side.update({"format": "exact-c2w-opencv-v1",
                             "transform_matrix": c2w_cv.tolist(),
                             "fl_x": float(cam.f), "fl_y": float(cam.f),
                             "cx": float(cam.cx), "cy": float(cam.cy),
                             "w": int(a.res), "h": int(a.res),
                             "eye_raw": eye_raw.tolist(),
                             "pano_to_raw_signs": signs.tolist()})
            (outd / f"{tag}.json").write_text(json.dumps(side, indent=2))
            n_out += 1
            print(f"  {tag}  yaw {yaw:5.1f} pitch {pitch:+3d}")
    print(f"wrote {n_out} crops -> {outd}")


if __name__ == "__main__":
    main()
