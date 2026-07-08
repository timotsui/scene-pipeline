"""Convert the week8 pano-frame manifest into the RAW splat frame for the
viewer (module-3 utility). The pano<->raw relation for marble bundles is
still under A2b verification, so BOTH candidate transforms are emitted; the
user picks the one whose boxes hug the splat in the viewer:

  scene_manifest_panoraw_a.json   A: pure translation
        p_raw = p_pano + (0, H, 0)              (raw y-up, eye at +H)
  scene_manifest_panoraw_b.json   B: rot180Z + shift
        p_raw = (-x_pano, -y_pano - H, z_pano)  (raw up = -y, eye at -H)

View:  python viewer/serve.py --scene bedroom_marble   then
  http://localhost:8000/?scene=bedroom_marble&man=panoraw_a   (and _b)

  python manifest_pano_to_raw.py --scene bedroom_marble --eye-h 1.6
"""
import argparse, json
import numpy as np

import paths


def convert(objects, f):
    out = []
    for o in objects:
        lo = np.array(o["aabb_min"], float)
        hi = np.array(o["aabb_max"], float)
        clo, chi = f(lo), f(hi)
        nlo, nhi = np.minimum(clo, chi), np.maximum(clo, chi)
        n = dict(o)
        n["aabb_min"] = [round(float(v), 3) for v in nlo]
        n["aabb_max"] = [round(float(v), 3) for v in nhi]
        n["center"] = [round(float(v), 3) for v in (nlo + nhi) / 2]
        n["size"] = [round(float(v), 3) for v in nhi - nlo]
        out.append(n)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--eye-h", type=float, default=0.0,
                    help="pano camera height above floor; default 0 = derive "
                         "from the manifest's mesh floor_y (PER-SCENE value — "
                         "bedroom_marble measured 1.31/1.34)")
    a = ap.parse_args()
    src = paths.scene_dir(a.scene) / "scene_manifest_pano.json"
    man = json.loads(src.read_text())
    # H is per-scene: splat is floor-origin, pano/mesh are camera-origin, so
    # H = camera height above floor = -floor_y of the mesh in the pano frame
    H = a.eye_h if a.eye_h else round(-man["frame"]["floor_y"], 3)
    print(f"eye height H = {H} ({'flag' if a.eye_h else 'derived from mesh floor_y'})")

    variants = {
        "panoraw_a": (lambda p: p + np.array([0, H, 0]),
                      f"raw = pano + (0,{H},0) [translation, raw y-up]"),
        "panoraw_b": (lambda p: np.array([-p[0], -p[1] - H, p[2]]),
                      f"raw = (-x, -y-{H}, z) [rot180Z + shift, raw up=-y]"),
        # user verdict on B (2026-07-07): aligned except mirrored in x ->
        # compose with x-flip = mirror-y + shift. Matches the glb relation
        # (collider was also mirror-y of pano): splat and collider share a
        # frame; the PANO is the mirrored export.
        "panoraw_c": (lambda p: np.array([p[0], -p[1] - H, p[2]]),
                      f"raw = (x, -y-{H}, z) [mirror-y + shift, raw up=-y]"),
    }
    for name, (f, desc) in variants.items():
        m = dict(man)
        m["objects"] = convert(man["objects"], f)
        fl, ce = man["frame"]["floor_y"], man["frame"]["ceiling_y"]
        pf, pc = f(np.array([0.0, fl, 0.0]))[1], f(np.array([0.0, ce, 0.0]))[1]
        m["frame"] = dict(man["frame"], space="raw-candidate", transform=desc,
                          floor_y=round(float(pf), 3), ceiling_y=round(float(pc), 3))
        outf = paths.scene_dir(a.scene) / f"scene_manifest_{name}.json"
        outf.write_text(json.dumps(m, indent=2))
        print(f"wrote {outf}  ({desc})")


if __name__ == "__main__":
    main()
