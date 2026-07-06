"""
Phase 1 - load + look. Parse an INRIA-format 3DGS .ply with numpy (no deps
beyond numpy/matplotlib), report geometry/color stats, and dump 3 orthographic
projections so we can pick the top-down (floor-plan) axis.
"""
import sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path

PLY = Path(__file__).parent / "data" / "raw" / "room.ply"
OUT = Path(__file__).parent / "outputs"; OUT.mkdir(exist_ok=True)
C0 = 0.28209479177387814  # SH DC band constant

def load_ply(path):
    with open(path, "rb") as f:
        assert f.readline().strip() == b"ply"
        fmt = f.readline().strip()
        assert b"binary_little_endian" in fmt, fmt
        props, n = [], None
        while True:
            line = f.readline().strip()
            if line.startswith(b"element vertex"):
                n = int(line.split()[-1])
            elif line.startswith(b"property"):
                parts = line.split()
                props.append((parts[1].decode(), parts[2].decode()))
            elif line == b"end_header":
                break
        assert all(t == "float" for t, _ in props), "expected all float32 props"
        names = [name for _, name in props]
        data = np.frombuffer(f.read(n * len(names) * 4), dtype="<f4").reshape(n, len(names))
    return names, data

def col(names, data, key):
    return data[:, names.index(key)]

def main():
    names, data = load_ply(PLY)
    n = data.shape[0]
    xyz = np.stack([col(names, data, k) for k in ("x", "y", "z")], 1)
    print(f"file        : {PLY.name}")
    print(f"gaussians   : {n:,}")
    print(f"properties  : {len(names)}  -> {', '.join(names[:12])}{' ...' if len(names)>12 else ''}")

    lo, hi = xyz.min(0), xyz.max(0)
    ext = hi - lo
    print(f"bbox min    : {np.round(lo,3)}")
    print(f"bbox max    : {np.round(hi,3)}")
    print(f"extent (xyz): {np.round(ext,3)}   (3DGS units ~ metres if COLMAP metric-scaled)")
    # robust extent (1-99 pct) to ignore floaters
    p1, p99 = np.percentile(xyz, [1, 99], axis=0)
    print(f"extent 1-99%: {np.round(p99-p1,3)}   <- ignore far floaters")

    if "opacity" in names:
        op = col(names, data, "opacity")
        alpha = 1/(1+np.exp(-op))
        print(f"opacity     : raw[{op.min():.2f},{op.max():.2f}]  alpha mean {alpha.mean():.3f}  frac>0.5: {(alpha>0.5).mean():.2%}")
    else:
        alpha = np.ones(n)

    # base color from SH DC
    fdc = np.stack([col(names, data, f"f_dc_{i}") for i in range(3)], 1)
    rgb = np.clip(0.5 + C0 * fdc, 0, 1)
    print(f"rgb (SH DC) : mean {np.round(rgb.mean(0),3)}")

    # subsample for plotting; bias toward opaque gaussians
    keep = alpha > 0.3
    idx = np.where(keep)[0]
    if idx.size > 120_000:
        idx = np.random.default_rng(0).choice(idx, 120_000, replace=False)
    P, Crgb = xyz[idx], rgb[idx]

    fig, axes = plt.subplots(1, 3, figsize=(18, 6))
    for ax, (a, b, lbl) in zip(axes, [(0,2,"X-Z (top-down?)"),(0,1,"X-Y (front?)"),(2,1,"Z-Y (side?)")]):
        ax.scatter(P[:, a], P[:, b], c=Crgb, s=0.4, linewidths=0)
        ax.set_title(lbl); ax.set_aspect("equal"); ax.invert_yaxis()
        ax.set_xlabel("axis %d"%a); ax.set_ylabel("axis %d"%b)
    fig.suptitle(f"room.ply  -  {n:,} gaussians  (opaque subset {idx.size:,})")
    fig.tight_layout()
    out = OUT / "01_projections.png"
    fig.savefig(out, dpi=110); print("saved       :", out)

if __name__ == "__main__":
    main()
