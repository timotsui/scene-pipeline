"""
panorama.py — 360-degree filmstrip from a generated (or real) splat.

The scenes are generated from a single camera at the origin (standing height),
so the origin IS the natural panorama capture point. This sweeps N yaws around
that point via week5 shot.py (splat-transform, photoreal) and tiles the frames
left-to-right into one wide strip so you can see the WHOLE room around any single
GPU view — the thing 4 isolated yaw shots don't let you judge.

  python panorama.py --scene playroom
  python panorama.py --all
  python panorama.py --scene bedroom --frames 16 --fov 70

Output: out/<scene>/panorama.png  (+ per-frame webp, kept in out/<scene>/pano_frames/)
Yaw naming matches the existing views: yaw000 looks +Z, yaw090 looks +X.
"""
import argparse, math, subprocess, sys
from pathlib import Path
from PIL import Image, ImageDraw

import paths

HERE = Path(__file__).parent
OUT = HERE / "out"
SHOT = paths.SHOT


def render_strip(scene, frames, fov, res, r):
    ply = paths.ply(scene)
    if not ply.exists():
        print(f"  SKIP {scene}: {ply} missing")
        return None
    fdir = paths.pano_frames(scene)
    fdir.mkdir(parents=True, exist_ok=True)
    tiles = []
    for i in range(frames):
        yaw = 360.0 * i / frames
        # yaw from +Z toward +X (matches yaw000=+Z, yaw090=+X)
        look = f"{r * math.sin(math.radians(yaw)):.4f},0,{r * math.cos(math.radians(yaw)):.4f}"
        outp = fdir / f"yaw{int(round(yaw)):03d}.webp"
        cmd = [sys.executable, str(SHOT), "0,0,0", look,
               "--up", "0,1,0", "--fov", str(fov), "--res", res,
               "--ply", str(ply), "--out", str(outp), "--no-open"]
        print(f"  {scene} yaw {yaw:5.1f} ...", flush=True)
        rc = subprocess.run(cmd, cwd=str(SHOT.parent)).returncode
        if rc != 0 or not outp.exists():
            print(f"    render failed rc={rc}")
            continue
        tiles.append((yaw, outp))
    if not tiles:
        return None

    ims = [Image.open(p).convert("RGB") for _, p in tiles]
    h = min(im.height for im in ims)
    ims = [im.resize((round(im.width * h / im.height), h)) for im in ims]
    label = 22
    strip = Image.new("RGB", (sum(im.width for im in ims), h + label), (20, 20, 20))
    d = ImageDraw.Draw(strip)
    x = 0
    for (yaw, _), im in zip(tiles, ims):
        strip.paste(im, (x, label))
        d.text((x + 6, 4), f"yaw {int(round(yaw)):03d}", fill=(230, 230, 230))
        d.line([(x, label), (x, h + label)], fill=(60, 60, 60))
        x += im.width
    outp = paths.panorama(scene)
    strip.save(outp)
    print(f"  -> {outp}  ({strip.width}x{strip.height}, {len(tiles)} frames)")
    return outp


def stitch_existing(scene):
    """Tile the 4 GPU yaw views already on disk — no rendering, no GPU."""
    vdir = paths.views_dir(scene)
    frames = sorted(vdir.glob("gpu_yaw*.webp"))
    if not frames:
        print(f"  SKIP {scene}: no gpu_yaw*.webp in {vdir}")
        return None
    ims = [Image.open(p).convert("RGB") for p in frames]
    h = min(im.height for im in ims)
    ims = [im.resize((round(im.width * h / im.height), h)) for im in ims]
    label = 22
    strip = Image.new("RGB", (sum(im.width for im in ims), h + label), (20, 20, 20))
    d = ImageDraw.Draw(strip)
    x = 0
    for p, im in zip(frames, ims):
        strip.paste(im, (x, label))
        d.text((x + 6, 4), p.stem.replace("gpu_", ""), fill=(230, 230, 230))
        d.line([(x, label), (x, h + label)], fill=(60, 60, 60))
        x += im.width
    outp = paths.panorama(scene)
    strip.save(outp)
    print(f"  -> {outp}  ({strip.width}x{strip.height}, {len(frames)} existing views)")
    return outp


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--render", action="store_true",
                    help="re-render a denser N-frame sweep on the GPU (smooth, overlapping). "
                         "DEFAULT tiles the 4 yaw views already on disk (free, no GPU)")
    ap.add_argument("--frames", type=int, default=12)
    ap.add_argument("--fov", type=float, default=70)
    ap.add_argument("--res", default="512x512")
    ap.add_argument("--r", type=float, default=3.0, help="look radius from origin")
    a = ap.parse_args()

    if a.all:
        scenes = paths.gen_scenes()
    elif a.scene:
        scenes = [a.scene]
    else:
        ap.error("pass --scene <name> or --all")

    mode = f"render {a.frames}-frame sweep" if a.render else "tile existing views (free)"
    print(f"panorama: {len(scenes)} scene(s), mode = {mode}")
    done = []
    for sc in scenes:
        r = render_strip(sc, a.frames, a.fov, a.res, a.r) if a.render else stitch_existing(sc)
        if r:
            done.append(r)
    print(f"\ndone: {len(done)} strip(s)")


if __name__ == "__main__":
    main()
