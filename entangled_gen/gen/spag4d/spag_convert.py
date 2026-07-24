"""Direct SPAG4D core-API converter — bypasses the repo's broken CLI glue
(cli.py at HEAD passes sharp_refine/... kwargs core.SPAG4D doesn't accept).

Usage (spag4d env):
  python spag_convert.py <pano> <out_ply> [--depth-model da360|dap] [--stride N]
Also writes depth preview png + npy next to the ply (useful eval artifacts).
"""
import argparse
import os

from spag4d.core import SPAG4D

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pano")
    ap.add_argument("out_ply")
    ap.add_argument("--depth-model", default="dap", choices=["dap", "da360"])
    ap.add_argument("--stride", type=int, default=1)
    args = ap.parse_args()

    base = os.path.splitext(args.out_ply)[0]
    conv = SPAG4D(device="cuda", depth_model=args.depth_model,
                  generator=args.depth_model)
    result = conv.convert(
        input_path=args.pano,
        output_path=args.out_ply,
        stride=args.stride,
        depth_preview_path=base + "_depth.png",
        depth_npy_path=base + "_depth.npy",
    )
    print(f"SPAG_CONVERT_OK {args.out_ply} ({result})")


if __name__ == "__main__":
    main()
