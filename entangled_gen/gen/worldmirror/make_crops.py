"""make_crops.py — equirect pano -> perspective crop rig for WorldMirror 2.0.

Standalone (cv2 + numpy only; runs on the Windows python). Deliberately NOT
importing hy3dworld (its __init__ eagerly imports the whole scenegen chain)
and their Perspective class maps the wrong direction anyway.

Rig: 8 yaws at pitch 0 + 4 yaws at pitch -30 (floor coverage) + 2 at
pitch +30 (ceiling) = 14 views, fov 85, 1036x1036 (multiple of 14, near the
model's 952 target). Zero-baseline rotation-only rig — the known caveat of
the pano-crop adaptation (plan doc 4.1): WorldMirror's monocular priors must
supply the depth scale.

Usage: python make_crops.py <pano.png> <out_dir>
"""
import sys
import cv2
import numpy as np


def equirect_to_perspective(pano, fov_deg, yaw_deg, pitch_deg, out_w, out_h):
    ph, pw = pano.shape[:2]
    f = 0.5 * out_w / np.tan(np.radians(fov_deg) / 2.0)
    cx, cy = (out_w - 1) / 2.0, (out_h - 1) / 2.0
    xs, ys = np.meshgrid(np.arange(out_w, dtype=np.float32),
                         np.arange(out_h, dtype=np.float32))
    # camera rays (x right, y down, z forward)
    dirs = np.stack([(xs - cx) / f, (ys - cy) / f, np.ones_like(xs)], axis=-1)
    dirs /= np.linalg.norm(dirs, axis=-1, keepdims=True)
    yaw, pitch = np.radians(yaw_deg), np.radians(pitch_deg)
    # pitch about x, then yaw about y
    Rx = np.array([[1, 0, 0],
                   [0, np.cos(pitch), -np.sin(pitch)],
                   [0, np.sin(pitch), np.cos(pitch)]], dtype=np.float32)
    Ry = np.array([[np.cos(yaw), 0, np.sin(yaw)],
                   [0, 1, 0],
                   [-np.sin(yaw), 0, np.cos(yaw)]], dtype=np.float32)
    d = dirs @ (Ry @ Rx).T
    lon = np.arctan2(d[..., 0], d[..., 2])          # -pi..pi
    lat = np.arcsin(np.clip(d[..., 1], -1, 1))      # -pi/2..pi/2 (down +)
    map_x = ((lon / np.pi + 1) * 0.5 * (pw - 1)).astype(np.float32)
    map_y = ((lat / (np.pi / 2) + 1) * 0.5 * (ph - 1)).astype(np.float32)
    return cv2.remap(pano, map_x, map_y, cv2.INTER_LINEAR,
                     borderMode=cv2.BORDER_WRAP)


def main():
    pano_path, out_dir = sys.argv[1], sys.argv[2]
    import os
    os.makedirs(out_dir, exist_ok=True)
    pano = cv2.imread(pano_path, cv2.IMREAD_COLOR)
    assert pano is not None, f"cannot read {pano_path}"
    views = [(y, 0) for y in range(0, 360, 45)]
    views += [(y, -30) for y in range(0, 360, 90)]
    views += [(y, 30) for y in (45, 225)]
    for i, (yaw, pitch) in enumerate(views):
        img = equirect_to_perspective(pano, 85.0, yaw, pitch, 1036, 1036)
        name = f"view_{i:02d}_y{yaw:03d}_p{pitch:+03d}.png"
        cv2.imwrite(f"{out_dir}/{name}", img)
        print(name)
    print(f"OK {len(views)} crops -> {out_dir}")


if __name__ == "__main__":
    main()
