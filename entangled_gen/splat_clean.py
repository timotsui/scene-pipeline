"""
Floater diagnosis + culling for generated splats.

The gen_bedroom "black holes" are big dark gaussians (LucidDreamer inpaint of
never-observed regions) that occlude sightlines through the room. This tool
reports the suspect population and optionally writes a cleaned ply.

python splat_clean.py --ply out/bedroom/gen_raw.ply                 # report only
python splat_clean.py --ply out/bedroom/gen_raw.ply --out out/bedroom/gen_clean.ply \
    --cull-dark --cull-huge                                          # write cleaned
"""
import argparse
from pathlib import Path
import numpy as np
from splat_place import read_ply, write_ply

C0 = 0.28209479177387814


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ply", required=True)
    ap.add_argument("--out", default="")
    ap.add_argument("--cull-dark", action="store_true",
                    help="cull dark low-detail blobs near the rig (the 'hole fill')")
    ap.add_argument("--cull-huge", action="store_true",
                    help="cull gaussians with max axis > --huge-m")
    ap.add_argument("--huge-m", type=float, default=0.35)
    ap.add_argument("--dark-lum", type=float, default=0.10)
    ap.add_argument("--dark-r", type=float, default=2.5,
                    help="dark culling only within this XZ radius of the rig")
    args = ap.parse_args()

    names, data = read_ply(args.ply)
    ix = {n: i for i, n in enumerate(names)}
    n = len(data)
    xyz = data[:, [ix["x"], ix["y"], ix["z"]]]
    rgb = np.clip(0.5 + C0 * data[:, [ix["f_dc_0"], ix["f_dc_1"], ix["f_dc_2"]]], 0, 1)
    lum = rgb.mean(1)
    alpha = 1 / (1 + np.exp(-data[:, ix["opacity"]]))
    smax = np.exp(data[:, [ix["scale_0"], ix["scale_1"], ix["scale_2"]]]).max(1)
    rxz = np.hypot(xyz[:, 0], xyz[:, 2])

    huge = smax > args.huge_m
    dark = (lum < args.dark_lum) & (alpha > 0.3) & (rxz < args.dark_r)
    print(f"{Path(args.ply).name}: {n:,} gaussians")
    print(f"  scale: median max-axis {np.median(smax)*100:.2f} cm, "
          f"p99 {np.percentile(smax,99)*100:.1f} cm")
    print(f"  HUGE (> {args.huge_m} m): {huge.sum():,} ({huge.mean():.2%}) — "
          f"lum median {np.median(lum[huge]) if huge.any() else float('nan'):.2f}")
    print(f"  DARK near rig (lum<{args.dark_lum}, a>0.3, rxz<{args.dark_r}): "
          f"{dark.sum():,} ({dark.mean():.2%})")
    both = huge & dark
    print(f"  overlap huge&dark: {both.sum():,}")
    # where do the dark ones live?
    if dark.any():
        dy = xyz[dark, 1]
        print(f"  dark y p5..p95: {np.percentile(dy,5):.2f}..{np.percentile(dy,95):.2f} "
              f"(floor region = suspected hole-fill)")

    if args.out:
        cull = np.zeros(n, bool)
        if args.cull_huge:
            cull |= huge
        if args.cull_dark:
            cull |= dark
        keep = ~cull
        write_ply(args.out, names, data[keep])
        print(f"  culled {cull.sum():,} -> wrote {args.out} ({keep.sum():,} kept)")


if __name__ == "__main__":
    main()
