"""
"Why can't I place here?" probe.

python splat_probe.py --scene bedroom --at -1.9,-1.9
python splat_probe.py --scene bedroom --box "-1.9,-1.9,1.2,0.75,0.6"   # center x,z + size WxHxD

Reports, at that spot: local floor height + deviation, clearance, floor presence,
nearby manifest objects, and (for --box) the full check_placement verdict.
"""
import argparse, json
from pathlib import Path
import numpy as np
import envelope
import paths

HERE = Path(__file__).parent


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--at", default="", help="x,z")
    ap.add_argument("--box", default="", help="cx,cz,W,H,D")
    args = ap.parse_args()

    env = envelope.load(args.scene)
    man = json.loads(paths.manifest(args.scene).read_text())
    cl, hf, fd = env["clearance"], env["has_floor"], env["floor_dev"]
    x0, z0, cell = float(env["x0"]), float(env["z0"]), float(env["cell"])
    floor_y = float(env["floor_y"])

    def cellat(x, z):
        c = int((x - x0) / cell); r = int((z - z0) / cell)
        if 0 <= r < cl.shape[0] and 0 <= c < cl.shape[1]:
            return r, c
        return None

    def report_point(x, z):
        rc = cellat(x, z)
        if rc is None:
            print(f"({x:.2f},{z:.2f}): outside envelope grid")
            return
        r, c = rc
        # 15 cm neighborhood for robustness
        k = max(1, int(0.15 / cell))
        pc = cl[max(0, r-k):r+k+1, max(0, c-k):c+k+1]
        ph = hf[max(0, r-k):r+k+1, max(0, c-k):c+k+1]
        pf = fd[max(0, r-k):r+k+1, max(0, c-k):c+k+1]
        print(f"probe ({x:.2f},{z:.2f}):")
        print(f"  floor present: {ph.mean():.0%} of nearby cells")
        good = pf[np.isfinite(pf)]
        if len(good):
            print(f"  local floor y: {floor_y + np.median(good):+.2f} "
                  f"(dev {np.median(good):+.2f} m from global {floor_y})")
        print(f"  clearance: median {np.median(pc):.2f} m, min {pc.min():.2f} m")
        near = []
        for o in man["objects"]:
            lo, hi = o["aabb_min"], o["aabb_max"]
            dx = max(lo[0] - x, 0, x - hi[0])
            dz = max(lo[2] - z, 0, z - hi[2])
            d = float(np.hypot(dx, dz))
            if d < 0.8:
                near.append((d, o))
        for d, o in sorted(near)[:5]:
            print(f"  {d:.2f} m away: {o['id']} {o['label']} (h {o['size'][1]:.2f})")

    if args.at:
        x, z = (float(t) for t in args.at.split(","))
        report_point(x, z)
    if args.box:
        cx, cz, W, H, D = (float(t) for t in args.box.split(","))
        report_point(cx, cz)
        ok, reasons = envelope.check_placement(
            env, [cx, floor_y + H / 2, cz], [W, H, D])
        print(f"  placement {W}x{H}x{D} here: {'OK' if ok else 'REJECT'}")
        for r in reasons:
            print(f"    - {r}")


if __name__ == "__main__":
    main()
