"""
Find legal placement spots from the habitable envelope: every position where a
W x H x D box fits on real floor with enough clearance (both orientations),
NMS-deduped and ranked. The inverse of splat_probe: not "why did this fail"
but "where would it succeed".

python suggest_spots.py --scene bedroom --size 1.2x0.75x0.6 --top 6
  [--write-live]   also append top spots as ghost placements to
                   out/<scene>/live_placement.json so they show in the viewer

Outputs: console table + out/<scene>/spots.png (spots on the clearance map).
"""
import argparse, json
from pathlib import Path
import numpy as np
import envelope
import paths

HERE = Path(__file__).parent


def window_ok(ok, wc, dc):
    """Boolean map: full wc x dc window of ok-cells anchored at each cell (top-left)."""
    ii = np.zeros((ok.shape[0] + 1, ok.shape[1] + 1), np.int32)
    ii[1:, 1:] = np.cumsum(np.cumsum(ok.astype(np.int32), 0), 1)
    nz, nx = ok.shape
    out = np.zeros_like(ok)
    if dc > nz or wc > nx:
        return out
    s = (ii[dc:, wc:] - ii[:-dc, wc:] - ii[dc:, :-wc] + ii[:-dc, :-wc])
    out[:nz - dc + 1, :nx - wc + 1] = (s == wc * dc)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--size", required=True, help="WxHxD in meters")
    ap.add_argument("--top", type=int, default=6)
    ap.add_argument("--margin", type=float, default=0.05)
    ap.add_argument("--write-live", action="store_true")
    args = ap.parse_args()

    W, H, D = (float(t) for t in args.size.split("x"))
    env = envelope.load(args.scene)
    cl, hf, fd = env["clearance"], env["has_floor"], env["floor_dev"]
    cell = float(env["cell"]); x0 = float(env["x0"]); z0 = float(env["z0"])
    floor_y = float(env["floor_y"])
    ok = hf & (cl >= H + 0.02)

    cands = []  # (score, cx, cz, yaw, wc, dc)
    for yaw, (w, d) in ((0, (W, D)), (90, (D, W))):
        wc = int(np.ceil((w + 2 * args.margin) / cell))
        dc = int(np.ceil((d + 2 * args.margin) / cell))
        fit = window_ok(ok, wc, dc)
        rr, cc = np.nonzero(fit)
        if not len(rr):
            continue
        # score: mean clearance margin over the window center region
        for r, c in zip(rr[::3], cc[::3]):     # stride-3 subsample, NMS later
            patch = cl[r:r + dc, c:c + wc]
            score = float(patch.mean() - H)
            cx = x0 + (c + wc / 2) * cell
            cz = z0 + (r + dc / 2) * cell
            cands.append((score, cx, cz, yaw, w, d, r, c, wc, dc))

    if not cands:
        print(f"NO legal spot for {W}x{H}x{D} in {args.scene} "
              f"(envelope: floor {hf.mean():.0%}, need clearance {H + 0.02:.2f})")
        return

    # NMS by center distance
    cands.sort(key=lambda t: -t[0])
    picked = []
    min_sep = max(W, D) * 0.8
    for cd in cands:
        if all(np.hypot(cd[1] - p[1], cd[2] - p[2]) > min_sep for p in picked):
            picked.append(cd)
        if len(picked) >= args.top:
            break

    print(f"{args.scene}: top {len(picked)} spots for {W}x{H}x{D} m:")
    spots = []
    for k, (score, cx, cz, yaw, w, d, r, c, wc, dc) in enumerate(picked):
        patch_fd = fd[r:r + dc, c:c + wc]
        dev = float(np.nanmedian(patch_fd)) if np.isfinite(patch_fd).any() else 0.0
        y = floor_y + dev + H / 2
        print(f"  #{k+1} center=({cx:+.2f}, {y:+.2f}, {cz:+.2f}) yaw={yaw:3d} "
              f"clearance-margin={score:+.2f} m floor-dev={dev:+.2f} m")
        spots.append({"label": f"spot#{k+1}", "center": [round(cx, 3), round(y, 3),
                      round(cz, 3)], "size": [W, H, D], "yaw_deg": yaw,
                      "reason": f"suggest_spots: clearance margin {score:+.2f} m"})

    # plot
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    nz, nx = cl.shape
    ext = [x0, x0 + nx * cell, z0 + nz * cell, z0]
    fig, ax = plt.subplots(figsize=(8, 8))
    ax.imshow(np.where(hf, cl, np.nan), origin="upper", cmap="RdYlGn",
              vmin=0, vmax=2, extent=ext)
    for k, s in enumerate(spots):
        w, d = (s["size"][0], s["size"][2]) if s["yaw_deg"] == 0 else \
               (s["size"][2], s["size"][0])
        ax.add_patch(Rectangle((s["center"][0] - w/2, s["center"][2] - d/2), w, d,
                     fill=False, edgecolor="blue", linewidth=2))
        ax.text(s["center"][0], s["center"][2], f'#{k+1}', color="blue",
                ha="center", va="center", fontsize=11, weight="bold")
    ax.plot(0, 0, "k*", markersize=13)
    ax.set_title(f"{args.scene}: legal spots for {W}x{H}x{D} m (blue)")
    outp = paths.spots(args.scene)
    fig.tight_layout(); fig.savefig(outp, dpi=110)
    print(f"wrote {outp}")

    if args.write_live:
        lp = paths.live_placement(args.scene)
        cur = json.loads(lp.read_text()) if lp.exists() else {"placements": []}
        cur["placements"] = [p for p in cur.get("placements", [])
                             if not p["label"].startswith("spot#")] + spots
        lp.write_text(json.dumps(cur, indent=2))
        print(f"appended {len(spots)} ghost spots to {lp.name} (visible in viewer)")


if __name__ == "__main__":
    main()
