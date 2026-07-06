"""
Convert a 3DGS ply to the live viewer's point payload: positions f32 + rgb u8.
Subsamples to --max-pts (default 1.5M). Writes viewer/data/<scene>.bin + .json meta.

Run:  python viewer/prep_scene.py --scene bedroom
      python viewer/prep_scene.py --scene composed --ply out/composed_bedroom_desk.ply
"""
import argparse, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import paths  # noqa: E402
from splat_place import read_ply  # noqa: E402

C0 = 0.28209479177387814


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--ply", default="")
    ap.add_argument("--max-pts", type=int, default=1500000)
    ap.add_argument("--opacity-min", type=float, default=0.3)
    args = ap.parse_args()

    ply = Path(args.ply) if args.ply else paths.ply(args.scene)
    names, data = read_ply(ply)
    ix = {n: i for i, n in enumerate(names)}
    alpha = 1 / (1 + np.exp(-data[:, ix["opacity"]]))
    m = alpha > args.opacity_min
    data = data[m]
    if len(data) > args.max_pts:
        sel = np.random.default_rng(0).choice(len(data), args.max_pts, replace=False)
        data = data[sel]
    xyz = data[:, [ix["x"], ix["y"], ix["z"]]].astype("<f4")
    rgb = np.clip(0.5 + C0 * data[:, [ix["f_dc_0"], ix["f_dc_1"], ix["f_dc_2"]]], 0, 1)
    rgb8 = (rgb * 255).astype(np.uint8)

    out = HERE / "data"
    out.mkdir(exist_ok=True)
    payload = out / f"{args.scene}.bin"
    with open(payload, "wb") as f:
        xyz.tofile(f)
        rgb8.tofile(f)
    lo, hi = np.percentile(xyz, 1, axis=0), np.percentile(xyz, 99, axis=0)
    meta = {"count": int(len(xyz)), "extent_p1": lo.tolist(), "extent_p99": hi.tolist(),
            "source_ply": str(ply)}
    (out / f"{args.scene}.json").write_text(json.dumps(meta))
    print(f"[prep] {payload}: {len(xyz):,} pts "
          f"({payload.stat().st_size/1e6:.1f} MB)", flush=True)


if __name__ == "__main__":
    main()
