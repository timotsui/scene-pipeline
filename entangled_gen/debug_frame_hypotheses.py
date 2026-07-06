"""
4-hypothesis frame calibration (SESSION_2026-07-05B_HANDOFF.md, step 2).

For each view render (webp + camera sidecar), z-buffer-paint the splat means
under 4 axis-sign hypotheses and correlate against the actual webp, exactly
the way lift_views.detect_st_mirror does for its 2 hypotheses:

    identity  (+x, +y, +z)
    mirX      (-x, +y, +z)   det=-1   <- current detect_st_mirror winner
    mirY      (+x, -y, +z)   det=-1
    rot180    (-x, -y, +z)   det=+1   <- "gen plys are Y-down" hypothesis

Prints numbers only; draws no conclusions.

Run:  python debug_frame_hypotheses.py --scene bedroom_s1
      python debug_frame_hypotheses.py --scene realplayroom
          --views-dir ../../week5/splat_to_placement/package/views
"""
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image

import paths

r3 = paths.load_r3()

HYPS = [("identity", np.array([1.0, 1.0, 1.0], np.float32)),
        ("mirX",     np.array([-1.0, 1.0, 1.0], np.float32)),
        ("mirY",     np.array([1.0, -1.0, 1.0], np.float32)),
        ("rot180",   np.array([-1.0, -1.0, 1.0], np.float32))]


def view_corrs(xyz, rgb, views_dir, view, size=192):
    """Correlation of point-paint vs actual webp for each hypothesis."""
    meta = json.loads((views_dir / f"{view}.json").read_text())
    cam = r3.Cam([float(t) for t in meta["cam"].split(",")],
                 [float(t) for t in meta["look"].split(",")],
                 [float(t) for t in meta["up"].split(",")],
                 float(meta["fov"]), size, size)
    ref = Image.open(views_dir / f"{view}.webp").convert("L").resize((size, size))
    ref = np.asarray(ref, np.float32)
    ref = (ref - ref.mean()) / (ref.std() + 1e-6)

    out = []
    for _name, sgn in HYPS:
        u, v, z = cam.project(xyz * sgn)
        ok = (z > 0.2) & np.isfinite(u) & np.isfinite(v)
        ui = np.round(u[ok]).astype(np.int64)
        vi = np.round(v[ok]).astype(np.int64)
        order = np.argsort(-z[ok])           # painter: near overwrites far
        img = np.zeros((size, size), np.float32)
        uu, vv = ui[order], vi[order]
        inb = (uu >= 0) & (uu < size) & (vv >= 0) & (vv < size)
        img[vv[inb], uu[inb]] = rgb[ok][order][inb].mean(axis=1)
        img = (img - img.mean()) / (img.std() + 1e-6)
        out.append(float((img * ref).mean()))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--views-dir", default="")
    ap.add_argument("--ply", default="")
    args = ap.parse_args()

    sc = args.scene
    views_dir = Path(args.views_dir) if args.views_dir else paths.views_dir(sc)
    ply = Path(args.ply) if args.ply else paths.ply(sc)

    views = sorted(p.stem for p in views_dir.glob("*.json")
                   if (views_dir / f"{p.stem}.webp").exists())
    if not views:
        raise SystemExit(f"no webp+json view pairs in {views_dir}")

    print(f"[hyp] scene={sc}  ply={ply.name}  views_dir={views_dir}", flush=True)
    xyz, rgb, _a, _r = r3.load_splat(str(ply), opacity_min=0.3)
    print(f"[hyp] {len(xyz):,} gaussians (opacity>=0.3)", flush=True)

    names = [h[0] for h in HYPS]
    header = f'{"view":<14}' + "".join(f"{n:>10}" for n in names) + "   winner"
    print(header)
    print("-" * len(header))
    sums = np.zeros(len(HYPS))
    for view in views:
        cs = view_corrs(xyz, rgb, views_dir, view)
        sums += cs
        win = names[int(np.argmax(cs))]
        print(f"{view:<14}" + "".join(f"{c:>10.3f}" for c in cs) + f"   {win}",
              flush=True)
    means = sums / len(views)
    win = names[int(np.argmax(means))]
    print("-" * len(header))
    print(f'{"MEAN":<14}' + "".join(f"{c:>10.3f}" for c in means) + f"   {win}")


if __name__ == "__main__":
    main()
