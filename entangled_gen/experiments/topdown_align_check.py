"""DIAGNOSTIC 2026-08-05: does the top-down SPLAT render agree with the
placement at all? (user: "where did you render the topdown splat from? it
dont seem aligned... might be the flipped version")

The bed-framed stimulus can't answer that -- a crop shows too little to
tell a wrong camera from a wrong placement. So: ONE whole-room top-down of
the splat, ceiling clipped, with EVERY placed object's footprint drawn on
it, plus the room shell rectangle. That is the overlay pairing
render_proposal.py already trusts (r3.Cam boxes on a shot.py/splat-transform
image), so if the boxes land, the camera is right and the stimulus camera
is right with it.

Also renders the same top-down with the up vector REVERSED, to test the
"flipped version" reading head-on: whichever of the two has boxes on the
furniture is the correct convention.

  python topdown_align_check.py [--scene bedroom_marble] [--height 4.0]
"""
import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).parent
EG = HERE.parent
sys.path.insert(0, str(EG))
sys.path.insert(0, str(EG / "compose"))

import paths                                     # noqa: E402
from rotation_check import load_scene            # noqa: E402

_s = importlib.util.spec_from_file_location("r3", EG / "rendertools" /
                                            "03_render.py")
r3 = importlib.util.module_from_spec(_s)
_s.loader.exec_module(r3)

R2R = np.array([-1.0, -1.0, 1.0])
SHOT = EG / "rendertools" / "shot.py"


def vec(a):
    return ",".join(f"{(v if v != 0 else 0.0):.4f}" for v in a)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--height", type=float, default=4.0)
    ap.add_argument("--cut", type=float, default=1.8)
    ap.add_argument("--res", type=int, default=1000)
    ap.add_argument("--gpu", default="0")
    args = ap.parse_args()

    cdir, nodes, by_item, shell, wx, wz, room_c = load_scene(args.scene)
    man = json.loads(paths.manifest(args.scene).read_text(encoding="utf-8"))
    floor_raw = float(man["frame"]["floor_y"])
    ceil_raw = float(man["frame"]["ceiling_y"])
    up_sign = -1.0 if floor_raw > ceil_raw else 1.0
    floor_r = floor_raw * R2R[1]

    out = cdir / "topdown_test"
    out.mkdir(exist_ok=True)

    eye = np.array([room_c[0], floor_r + args.height, room_c[2]])
    look = np.array([room_c[0], floor_r, room_c[2]])
    half = max(wx[1] - wx[0], wz[1] - wz[0]) / 2 * 1.15
    fov = float(np.clip(np.degrees(2 * np.arctan2(half, args.height)),
                        30, 110))

    # RENDER frame throughout: splat-transform applies diag(-1,-1,1) on load
    # (measured 2026-08-05, zero-error fit over 4 box observations), so its
    # camera and clip box speak the same coords as fitted_preview.
    ylo, yhi = floor_r - 0.25, floor_r + args.cut
    box = (f"{wx[0]-0.3:.3f},{ylo:.3f},{wz[0]-0.3:.3f},"
           f"{wx[1]+0.3:.3f},{yhi:.3f},{wz[1]+0.3:.3f}")

    placed = json.loads((cdir / "fitted_preview.json")
                        .read_text(encoding="utf-8"))["placed"]
    names = {p["id"]: p["name"] for p in placed}

    for tag, up in (("upz", np.array([0.0, 0.0, 1.0])),
                    ("upnegz", np.array([0.0, 0.0, -1.0]))):
        img_p = out / f"room_topdown_{tag}.webp"
        cmd = [sys.executable, str(SHOT), vec(eye), vec(look),
               f"--up={vec(up)}", f"--fov={fov:.3f}", f"--box={box}",
               f"--res={args.res}x{args.res}",
               f"--ply={paths.ply(args.scene)}", f"--gpu={args.gpu}",
               f"--out={img_p}", "--no-open"]
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)

        cam = r3.Cam(eye, look, up, fov, args.res, args.res)
        im = Image.open(img_p).convert("RGB")
        d = ImageDraw.Draw(im)
        # room shell rectangle (blue) — must frame the walls in the splat
        cor = [np.array([x, floor_r, z]) for x in wx for z in wz]
        u, v, z = cam.project(np.array(cor, np.float32))
        for i, j in ((0, 1), (1, 3), (3, 2), (2, 0)):
            d.line([(u[i], v[i]), (u[j], v[j])], fill=(60, 140, 255), width=3)
        # every placed footprint (yellow; bed in green)
        for oid, meshes in by_item.items():
            b = np.vstack([m.bounds for m in meshes])
            lo, hi = b.min(0), b.max(0)
            pts = np.array([[x, (lo[1] + hi[1]) / 2, zz]
                            for x in (lo[0], hi[0]) for zz in (lo[2], hi[2])],
                           np.float32)
            u, v, _ = cam.project(pts)
            col = (40, 230, 90) if oid == "obj_008" else (255, 210, 0)
            w = 4 if oid == "obj_008" else 2
            for i, j in ((0, 1), (1, 3), (3, 2), (2, 0)):
                d.line([(u[i], v[i]), (u[j], v[j])], fill=col, width=w)
            d.text((u.min(), max(0, v.min() - 12)),
                   f"{oid} {names.get(oid, '')}", fill=col)
        p_out = out / f"room_topdown_{tag}_boxes.png"
        im.save(p_out)
        print(f"[align] {tag}: {p_out}")

    print(f"[align] camera render-frame eye {eye.round(2).tolist()} "
          f"fov {fov:.1f}  clip {box}")


if __name__ == "__main__":
    main()
