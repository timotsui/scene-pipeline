"""Register the Marble bundle's collider mesh into the scene's RAW frame.

The bundle collider ships in its own frame: measured on bedroom_marble it is
the raw frame scaled ~0.95 and shifted ~1.23 m along y, with NO rotation.
The old in-line search in amodal_boxes.py tried the 8 SIGN FLIPS and nothing
else — a sign flip mirrors about the origin, so with the frames' origins 1.23 m
apart no element of that search space could register, and its best bbox IoU of
0.37 was coincidental overlap (2026-07-15).

Method here:
  coarse   all 48 signed axis permutations x {no scale, uniform scale from
           robust extents}; translation matches p2/p98 bbox centers; scored by
           VOXEL OCCUPANCY IoU (10 cm). Bbox IoU cannot see rotation about y
           and cannot tell a flip from a no-flip — voxels can, and do: on
           bedroom_marble identity scores 0.511 vs the y-flip's 0.325.
  refine   trimesh ICP (scale free) onto the splat points.

Writes out/<scene>/collider_registration.json (THE CONTRACT):
  {scene, collider, T: 4x4 row-major collider->RAW, scale, metrics:{...}}
Consumers (amodal_boxes.py) read T from here and never re-search.

The metrics are deliberately ASYMMETRIC. Voxel IoU is the wrong objective for
an amodal source: a collider that carried the occluded floor under the bed
SHOULD have voxels the splat lacks, and IoU punishes exactly that. So:
  coverage  splat voxels explained by the collider   -> alignment quality
  extra     collider voxels with no splat voxel      -> the amodal payload
  dist_p50/p90  splat point -> collider surface (m)  -> alignment quality

Measured on bedroom_marble (2026-07-15): coverage 0.705, dist p50 0.014 m —
a real lock. But extra FELL from 0.196 to 0.042 as alignment improved, and a
per-box check found the collider holds strictly LESS geometry under every
occluded box than the splat already has (and none at all under the lamp and
planter, where the splat is nearly empty too). The collider is a mesh derived
FROM the splat: it cannot carry what the splat lacks, so it is NOT an amodal
source. Registering it correctly is what proves that — see docs.

Run: python collider_register.py --scene bedroom_marble
"""
import argparse
import itertools
import json
from pathlib import Path

import numpy as np
import trimesh

import paths

VOX = 0.10          # scoring voxel (m)
NS = 300_000        # surface samples / splat subsample
ICP_SRC = 60_000    # ICP source points (full NS is slow, gains nothing)


def _robust(p):
    return np.percentile(p, 2, axis=0), np.percentile(p, 98, axis=0)


def _keys(p, size=VOX):
    return set(map(tuple, np.unique(np.floor(p / size).astype(np.int64), axis=0)))


def _signed_perms():
    """All 48 signed axis permutations (24 rotations + 24 mirrors)."""
    for perm in itertools.permutations(range(3)):
        for sx, sy, sz in itertools.product((1, -1), repeat=3):
            M = np.zeros((3, 3))
            for i, p in enumerate(perm):
                M[i, p] = (sx, sy, sz)[i]
            yield M


def collider_path(sc):
    bp = paths.scene_dir(sc) / "bundle_path.txt"
    if not bp.exists():
        return None
    bundle = Path(bp.read_text().strip())
    g = (list(bundle.glob("*_collider.glb"))
         + list(bundle.glob("*collider*.glb")))
    return g[0] if g else None


def metrics(cpts, splat):
    """Asymmetric scores — see module docstring for why not plain IoU."""
    from scipy.spatial import cKDTree
    a, b = _keys(cpts), _keys(splat)
    inter = len(a & b)
    d, _ = cKDTree(cpts).query(splat[:20_000], k=1)
    return {"voxel_iou": round(inter / max(1, len(a | b)), 4),
            "coverage": round(inter / max(1, len(b)), 4),
            "extra": round((len(a) - inter) / max(1, len(a)), 4),
            "dist_p50": round(float(np.percentile(d, 50)), 4),
            "dist_p90": round(float(np.percentile(d, 90)), 4)}


def register(sc, verbose=True):
    glb = collider_path(sc)
    if glb is None:
        print("[reg] no collider in bundle (or no bundle_path.txt)", flush=True)
        return None
    r3 = paths.load_r3()
    xyz, *_ = r3.load_splat(str(paths.ply(sc)))
    splat = np.asarray(xyz, np.float64)
    rng = np.random.default_rng(0)
    if splat.shape[0] > NS:
        splat = splat[rng.choice(splat.shape[0], NS, replace=False)]
    s_lo, s_hi = _robust(splat)
    s_c, s_e = (s_lo + s_hi) / 2, (s_hi - s_lo)

    mesh = trimesh.load(glb, force="mesh")
    cp = np.asarray(mesh.sample(NS), np.float64)
    sk = _keys(splat)

    best = None
    for M in _signed_perms():
        for scaled in (False, True):
            q = cp @ M.T
            s = 1.0
            if scaled:
                q_lo, q_hi = _robust(q)
                s = float(np.exp(np.mean(np.log(
                    s_e / np.maximum(q_hi - q_lo, 1e-9)))))
                q = q * s
            q_lo, q_hi = _robust(q)
            t = s_c - (q_lo + q_hi) / 2
            iou = len(_keys(q + t) & sk) / max(1, len(_keys(q + t) | sk))
            if best is None or iou > best[0]:
                best = (iou, M, s, t)
    iou0, M, s0, t0 = best
    T0 = np.eye(4)
    T0[:3, :3], T0[:3, 3] = M * s0, t0
    if verbose:
        print(f"[reg] coarse: voxel IoU {iou0:.3f}  scale {s0:.4f}  "
              f"t {t0.round(3)}  det {np.linalg.det(M):+.0f}", flush=True)

    T, _, cost = trimesh.registration.icp(
        np.asarray(mesh.sample(ICP_SRC), np.float64), splat,
        initial=T0, scale=True, max_iterations=60)
    m1 = mesh.copy()
    m1.apply_transform(T)
    mt = metrics(np.asarray(m1.sample(NS)), splat)
    scale = float(np.cbrt(abs(np.linalg.det(T[:3, :3]))))
    if verbose:
        print(f"[reg] icp:    cost {cost:.5f}  scale {scale:.4f}  "
              f"t {T[:3,3].round(3)}", flush=True)
        print(f"[reg] metrics {mt}", flush=True)
        if mt["dist_p50"] > 0.05:
            print("[reg] WARNING p50 > 5cm — registration SUSPECT", flush=True)

    out = {"scene": sc, "collider": glb.name, "method": "coarse48+icp",
           "vox": VOX, "T": [list(map(float, r)) for r in T],
           "scale": round(scale, 5), "icp_cost": round(float(cost), 6),
           "metrics": mt}
    outf = paths.scene_dir(sc) / "collider_registration.json"
    outf.write_text(json.dumps(out, indent=1))
    print(f"[reg] wrote {outf}", flush=True)

    # viewer payload: registered mesh baked into the RAW frame (the viewer's
    # worldGroup is RAW, so unlike composed_scene2.glb it needs no flip)
    gout = paths.scene_dir(sc) / "collider_registered.glb"
    m1.export(gout)
    print(f"[reg] wrote {gout}", flush=True)
    return out


def load_T(sc):
    """4x4 collider->RAW, or None if the scene was never registered."""
    f = paths.scene_dir(sc) / "collider_registration.json"
    if not f.exists():
        return None
    return np.asarray(json.loads(f.read_text())["T"], np.float64)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    register(ap.parse_args().scene)
