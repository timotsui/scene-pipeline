"""
Habitable-envelope / clearance map from a splat.

Tonight's placement failures (2026-07-05) were all "manifest says free, reality
says curtain/wardrobe/eave". Object footprints aren't enough: composition needs,
per floor cell, (a) is there actual floor here, and (b) how much vertical
clearance exists above it. Both are computable straight from the gaussian means.

compute(scene | ply) -> writes out/<scene>/envelope.npz + envelope_heatmap.png +
viewer/data/<scene>_clearance.json (coarse grid for the live viewer).

check_placement(env, center, size, margin) -> (ok, reasons) — shared by the
probe CLI, render_proposal, and the viewer server.
"""
import argparse, json, sys
from pathlib import Path
import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402
from splat_place import read_ply  # noqa: E402

CELL = 0.05          # xz cell size (m)
YBIN = 0.05          # vertical bin (m)
OCC_MIN_PTS = 3      # points in a (cell, ybin) to count as solid
FLOOR_BAND = 0.07    # floor presence = points within this of floor_y
HEAD_MAX = 2.2       # don't care about clearance beyond this


FLOOR_SEARCH = 0.45   # local floor searched within floor_y +/- this (gen floors WARP)
SKIRT = 0.12          # ignore this much above local floor (baseboards, rug pile)


def compute(ply, floor_y, ceil_y, x0, x1, z0, z1):
    """First bedroom run (global flat-floor band) found floor under <5% of the
    room: generated floors are bowl-warped by tens of cm. So estimate a LOCAL
    floor height per cell and measure clearance above that; the local floor map
    itself (floor_dev) doubles as the spatial-warp metric."""
    names, data = read_ply(ply)
    ix = {n: i for i, n in enumerate(names)}
    alpha = 1 / (1 + np.exp(-data[:, ix["opacity"]]))
    m = alpha > 0.3
    xyz = data[m][:, [ix["x"], ix["y"], ix["z"]]]

    nx = max(8, int(np.ceil((x1 - x0) / CELL)))
    nz = max(8, int(np.ceil((z1 - z0) / CELL)))
    ylo = floor_y - FLOOR_SEARCH
    ny = int(np.ceil((min(floor_y + HEAD_MAX, ceil_y + 0.3) - ylo) / YBIN))

    inb = (xyz[:, 0] >= x0) & (xyz[:, 0] < x1) & (xyz[:, 2] >= z0) & (xyz[:, 2] < z1) \
        & (xyz[:, 1] >= ylo) & (xyz[:, 1] < ylo + ny * YBIN)
    p = xyz[inb]
    ci = ((p[:, 0] - x0) / CELL).astype(np.int32).clip(0, nx - 1)
    cz = ((p[:, 2] - z0) / CELL).astype(np.int32).clip(0, nz - 1)
    by = ((p[:, 1] - ylo) / YBIN).astype(np.int32).clip(0, ny - 1)
    occ = np.zeros((ny, nz, nx), np.int16)
    np.add.at(occ, (by, cz, ci), 1)
    solid = occ >= OCC_MIN_PTS                          # (ny, nz, nx)

    # local floor = lowest solid bin within the floor search band
    nfb = int((2 * FLOOR_SEARCH) / YBIN)                # bins covering +/-FLOOR_SEARCH
    band = solid[:nfb]
    has_floor = band.any(axis=0)
    floor_bin = np.argmax(band, axis=0)                 # first solid bin from below
    floor_h = ylo + (floor_bin + 0.5) * YBIN            # local floor y
    floor_dev = np.where(has_floor, floor_h - floor_y, np.nan).astype(np.float32)

    # clearance = gap from local floor (+skirt) to next solid bin above
    start = floor_bin + int(np.ceil(SKIRT / YBIN))
    ybins = np.arange(ny)[:, None, None]
    above_mask = solid & (ybins >= start[None, :, :])
    any_above = above_mask.any(axis=0)
    first_above = np.argmax(above_mask, axis=0)
    clearance = np.where(
        any_above,
        (first_above - floor_bin) * YBIN,
        HEAD_MAX).astype(np.float32)
    clearance = np.where(has_floor, np.minimum(clearance, HEAD_MAX), 0.0)
    return {"clearance": clearance, "has_floor": has_floor, "floor_dev": floor_dev,
            "x0": x0, "z0": z0, "cell": CELL, "nx": nx, "nz": nz,
            "floor_y": floor_y, "ceil_y": ceil_y}


def check_placement(env, center, size, margin=0.05):
    """AABB placement legality against the envelope. Returns (ok, [reasons])."""
    cl, hf = env["clearance"], env["has_floor"]
    x0, z0, cell = env["x0"], env["z0"], env["cell"]
    nz, nx = cl.shape
    reasons = []
    lo = [center[0] - size[0] / 2 - margin, center[2] - size[2] / 2 - margin]
    hi = [center[0] + size[0] / 2 + margin, center[2] + size[2] / 2 + margin]
    c0, c1 = int((lo[0] - x0) / cell), int(np.ceil((hi[0] - x0) / cell))
    r0, r1 = int((lo[1] - z0) / cell), int(np.ceil((hi[1] - z0) / cell))
    if c0 < 0 or r0 < 0 or c1 > nx or r1 > nz:
        return False, ["outside envelope grid"]
    patch_cl = cl[r0:r1, c0:c1]
    patch_hf = hf[r0:r1, c0:c1]
    if patch_hf.mean() < 0.6:
        reasons.append(f"floor present under only {patch_hf.mean():.0%} of footprint "
                       "(hole / eave / outside room)")
    need = size[1] + 0.02
    frac_clear = float((patch_cl >= need).mean())
    if frac_clear < 0.95:
        reasons.append(f"only {frac_clear:.0%} of footprint has clearance >= {need:.2f} m "
                       f"(min clearance in patch: {float(patch_cl.min()):.2f} m — "
                       "something solid occupies this volume)")
    return (not reasons), reasons


def save(env, scene):
    out = paths.envelope_npz(scene)
    np.savez_compressed(out, **{k: v for k, v in env.items()})
    # coarse grid for the viewer (10 cm cells, clearance in cm as uint8)
    cl, hf = env["clearance"], env["has_floor"]
    f = 2  # 5 cm -> 10 cm
    nz, nx = cl.shape
    czs, cxs = nz // f, nx // f
    coarse = cl[:czs * f, :cxs * f].reshape(czs, f, cxs, f).min(axis=(1, 3))
    floorc = hf[:czs * f, :cxs * f].reshape(czs, f, cxs, f).mean(axis=(1, 3)) >= 0.5
    fdc = env["floor_dev"][:czs * f, :cxs * f].reshape(czs, f, cxs, f)
    with np.errstate(all="ignore"):
        fdev = np.nanmedian(fdc, axis=(1, 3))
    fdev_cm = np.where(np.isfinite(fdev), np.clip(fdev * 100, -120, 120), 127)
    vj = {"x0": float(env["x0"]), "z0": float(env["z0"]), "cell": CELL * f,
          "nx": cxs, "nz": czs, "floor_y": float(env["floor_y"]),
          "clearance_cm": (np.minimum(coarse, 2.55) * 100).astype(np.uint8).ravel().tolist(),
          "floor_dev_cm": fdev_cm.astype(np.int16).ravel().tolist(),
          "has_floor": floorc.astype(np.uint8).ravel().tolist()}
    vd = HERE / "viewer" / "data"
    vd.mkdir(exist_ok=True)
    (vd / f"{scene}_clearance.json").write_text(json.dumps(vj))

    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ext = [env["x0"], env["x0"] + cl.shape[1] * CELL,
           env["z0"] + cl.shape[0] * CELL, env["z0"]]
    fig, axes = plt.subplots(1, 2, figsize=(15, 8))
    im0 = axes[0].imshow(np.where(hf, cl, np.nan), origin="upper", cmap="RdYlGn",
                         vmin=0, vmax=2.0, extent=ext)
    axes[0].set_title("clearance above LOCAL floor (white = no floor found)")
    fig.colorbar(im0, ax=axes[0], label="m", shrink=0.8)
    fd = env["floor_dev"]
    im1 = axes[1].imshow(fd, origin="upper", cmap="coolwarm", vmin=-0.4, vmax=0.4,
                         extent=ext)
    axes[1].set_title("floor height deviation from global floor_y (WARP map)")
    fig.colorbar(im1, ax=axes[1], label="m", shrink=0.8)
    for ax in axes:
        ax.plot(0, 0, "k*", markersize=12)
        ax.set_xlabel("x"); ax.set_ylabel("z")
    fig.suptitle(f"{scene} habitable envelope  (star = rig)")
    heat = paths.envelope_heatmap(scene)
    fig.tight_layout(); fig.savefig(heat, dpi=110)
    valid = fd[np.isfinite(fd)]
    if len(valid):
        print(f"[envelope] floor coverage {np.isfinite(fd).mean():.0%}, "
              f"warp p5..p95: {np.percentile(valid,5):+.2f}..{np.percentile(valid,95):+.2f} m",
              flush=True)
    print(f"[envelope] wrote {out}, {heat}, viewer clearance json", flush=True)


def load(scene):
    z = np.load(paths.envelope_npz(scene))
    return {k: z[k] for k in z.files}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--ply", default="")
    args = ap.parse_args()
    ply = Path(args.ply) if args.ply else paths.ply(args.scene)
    man = json.loads(paths.manifest(args.scene).read_text())
    fr = man["frame"]
    (x0, _, z0), (x1, _, z1) = fr["extent_p1"], fr["extent_p99"]
    env = compute(ply, fr["floor_y"], fr["ceiling_y"], x0, x1, z0, z1)
    save(env, args.scene)


if __name__ == "__main__":
    main()
