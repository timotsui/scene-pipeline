"""
Splat surgery v0: cut an object's gaussians out of a source scene by AABB and
rigid-place them into a target scene (translate + uniform scale, yaw=0).

This is the "take an asset and place it" step: the asset is not from a library,
it's extracted from another splat by the same lift pipeline that found it.

Property handling: output uses the TARGET ply's property list; asset rows fill
missing props with 0 (f_rest_* zeros = view-independent color) and drop extras.
Uniform scale s: xyz *= s and scale_0..2 += ln(s) (3DGS stores log-scales).

Run:
python splat_place.py --src <src.ply> --dst <dst.ply> --out <out.ply> \
  --cut xmin,ymin,zmin,xmax,ymax,zmax  --target-center x,y,z --target-height H \
  [--bottom-align]
"""
import argparse
from pathlib import Path
import numpy as np


def read_ply(path):
    f = open(path, "rb")
    magic = f.readline()
    fmt = f.readline()
    names, n = [], None
    while True:
        l = f.readline().strip()
        if l.startswith(b"element vertex"):
            n = int(l.split()[-1])
        elif l.startswith(b"property"):
            parts = l.split()
            if parts[1] != b"float":
                raise SystemExit(f"non-float property {l!r} unsupported")
            names.append(parts[2].decode())
        elif l == b"end_header":
            break
    data = np.fromfile(f, dtype="<f4", count=n * len(names)).reshape(n, len(names))
    f.close()
    return names, data


def write_ply(path, names, data):
    with open(path, "wb") as f:
        f.write(b"ply\nformat binary_little_endian 1.0\n")
        f.write(f"element vertex {len(data)}\n".encode())
        for nm in names:
            f.write(f"property float {nm}\n".encode())
        f.write(b"end_header\n")
        data.astype("<f4").tofile(f)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--dst", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--cut", required=True, help="xmin,ymin,zmin,xmax,ymax,zmax in src frame")
    ap.add_argument("--target-center", required=True, help="x,y,z in dst frame")
    ap.add_argument("--target-height", type=float, required=True,
                    help="desired asset height in dst units")
    ap.add_argument("--bottom-align", action="store_true",
                    help="target-center y is the FLOOR y; asset bottom sits on it")
    ap.add_argument("--fatten", type=float, default=1.0,
                    help="extra multiplier on gaussian scales (visibility: hi-detail "
                         "sub-mm source gaussians go sub-pixel after downscaling and "
                         "AA attenuates them to invisible)")
    ap.add_argument("--yaw", type=float, default=0.0,
                    help="rotate asset about +Y by this many degrees (positions AND "
                         "gaussian quaternions; f_rest SH left unrotated — minor "
                         "view-dependent tint artifact)")
    ap.add_argument("--strip-sh", action="store_true",
                    help="zero the asset's f_rest_* bands (matte diffuse color; kills "
                         "the specular shimmer from unrotated view-dependent SH)")
    args = ap.parse_args()

    cut = np.array([float(t) for t in args.cut.split(",")], np.float32)
    lo, hi = cut[:3], cut[3:]
    tc = np.array([float(t) for t in args.target_center.split(",")], np.float32)

    print(f"[place] reading src {args.src}", flush=True)
    s_names, s_data = read_ply(args.src)
    sx = {nm: i for i, nm in enumerate(s_names)}
    xyz = s_data[:, [sx["x"], sx["y"], sx["z"]]]
    m = np.all((xyz >= lo) & (xyz <= hi), axis=1)
    asset = s_data[m].copy()
    if len(asset) == 0:
        raise SystemExit("cut box selected 0 gaussians")
    axyz = asset[:, [sx["x"], sx["y"], sx["z"]]]
    alo, ahi = np.percentile(axyz, 1, axis=0), np.percentile(axyz, 99, axis=0)
    print(f"[place] cut {len(asset):,} gaussians; asset bbox size {np.round(ahi-alo,3)}",
          flush=True)

    s = args.target_height / float(ahi[1] - alo[1])
    center = (alo + ahi) / 2
    axyz = (axyz - center) * s
    if args.yaw != 0.0:
        th = np.radians(args.yaw)
        c, sn = np.cos(th), np.sin(th)
        rx = axyz[:, 0] * c + axyz[:, 2] * sn
        rz = -axyz[:, 0] * sn + axyz[:, 2] * c
        axyz = np.stack([rx, axyz[:, 1], rz], axis=1)
        # rotate gaussian orientations: q' = q_yaw (w,0,y,0) HAMILTON q
        w1, y1 = np.cos(th / 2), np.sin(th / 2)
        qw = asset[:, sx["rot_0"]].copy(); qx = asset[:, sx["rot_1"]].copy()
        qy = asset[:, sx["rot_2"]].copy(); qz = asset[:, sx["rot_3"]].copy()
        asset[:, sx["rot_0"]] = w1 * qw - y1 * qy
        asset[:, sx["rot_1"]] = w1 * qx + y1 * qz
        asset[:, sx["rot_2"]] = w1 * qy + y1 * qw
        asset[:, sx["rot_3"]] = w1 * qz - y1 * qx
    if args.bottom_align:
        # after scaling, bottom of asset is at -(height)/2 relative to its center
        shift_y = tc[1] + (center[1] - alo[1]) * s
        new = axyz + np.array([tc[0], shift_y, tc[2]], np.float32)
    else:
        new = axyz + tc
    asset[:, sx["x"]], asset[:, sx["y"]], asset[:, sx["z"]] = new[:, 0], new[:, 1], new[:, 2]
    for k in ("scale_0", "scale_1", "scale_2"):
        asset[:, sx[k]] += np.log(s * args.fatten)
    print(f"[place] scale {s:.3f}; placed at {tc} (bottom_align={args.bottom_align})",
          flush=True)

    print(f"[place] reading dst {args.dst}", flush=True)
    d_names, d_data = read_ply(args.dst)
    # map asset columns into the dst property layout
    out_asset = np.zeros((len(asset), len(d_names)), np.float32)
    missing = []
    for j, nm in enumerate(d_names):
        if nm in sx and not (args.strip_sh and nm.startswith("f_rest_")):
            out_asset[:, j] = asset[:, sx[nm]]
        elif nm not in sx:
            missing.append(nm)
    if missing:
        print(f"[place] asset lacks {len(missing)} dst props (zero-filled): "
              f"{missing[:6]}{'...' if len(missing) > 6 else ''}", flush=True)
    merged = np.vstack([d_data, out_asset])
    write_ply(args.out, d_names, merged)
    print(f"[place] wrote {args.out}: {len(d_data):,} + {len(out_asset):,} "
          f"= {len(merged):,} gaussians", flush=True)


if __name__ == "__main__":
    main()
