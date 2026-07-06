"""
Verify a compose_proposal.json: check the hard constraints from GUIDE.md
numerically, then draw proposed boxes (green, solid) next to existing manifest
boxes (grey) in the photoreal views + a plan view.

Run:  python render_proposal.py --scene playroom
Reads  out/<scene>/package/compose_proposal.json
Writes out/<scene>/package/proposal_check.txt + proposal_view_*.png + proposal_plan.png
"""
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

import paths
HERE = Path(__file__).parent
r3 = paths.load_r3()


def aabb(p):
    c, s = np.array(p["center"], np.float32), np.array(p["size"], np.float32)
    return c - s / 2, c + s / 2


def overlap(lo1, hi1, lo2, hi2):
    return bool(np.all(np.maximum(lo1, lo2) < np.minimum(hi1, hi2)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="playroom")
    args = ap.parse_args()
    sc = args.scene

    pkg = paths.package_dir(sc)
    views_dir = paths.views_dir(sc)
    man = json.loads((pkg / "scene_manifest.json").read_text())
    prop = json.loads((pkg / "compose_proposal.json").read_text())
    fr = man["frame"]
    floor_y = fr["floor_y"]

    # ---- constraint check ----
    lines, ok_all = [], True
    exist = [(o["id"], np.array(o["aabb_min"], np.float32),
              np.array(o["aabb_max"], np.float32)) for o in man["objects"]]
    placed = []
    for p in prop["placements"]:
        lo, hi = aabb(p)
        errs = []
        want_y = floor_y + p["size"][1] / 2
        if abs(p["center"][1] - want_y) > 0.02:
            errs.append(f"not on floor (center_y {p['center'][1]} != {want_y:.3f})")
        if "extent_p1" in fr:
            (x0, _, z0), (x1, _, z1) = fr["extent_p1"], fr["extent_p99"]
            if lo[0] < x0 or hi[0] > x1 or lo[2] < z0 or hi[2] > z1:
                errs.append("outside room extent")
        for oid, elo, ehi in exist:
            if overlap(lo, hi, elo, ehi):
                errs.append(f"intersects {oid}")
        for q, (qlo, qhi) in placed:
            if overlap(lo, hi, qlo, qhi):
                errs.append(f"intersects placement '{q}'")
        # corridor: keep the closest point of the AABB >= 0.5 m from origin (xz)
        nearest = np.clip(0, lo, hi)
        d = float(np.hypot(nearest[0], nearest[2]))
        if d < 0.5:
            errs.append(f"blocks rig corridor (d={d:.2f})")
        placed.append((p["label"], (lo, hi)))
        status = "OK " if not errs else "FAIL"
        ok_all &= not errs
        lines.append(f'{status} {p["label"]:14s} center={p["center"]} size={p["size"]}'
                     + ("" if not errs else "  <- " + "; ".join(errs)))
    report = "\n".join(lines) + f"\n\nALL CONSTRAINTS {'PASS' if ok_all else 'FAIL'}\n"
    (pkg / "proposal_check.txt").write_text(report)
    print(report, flush=True)

    # ---- draw: existing grey, proposed green ----
    # manifest/proposal boxes are in RAW ply space; the webp render space may be
    # x-mirrored relative to it (frame.st_mirror_x, calibrated by lift_views).
    st_mirror = bool(fr.get("st_mirror_x", False))

    def draw_box(dr, cam, lo, hi, color, width, label=None):
        if st_mirror:
            lo, hi = np.array([-hi[0], lo[1], lo[2]]), np.array([-lo[0], hi[1], hi[2]])
        corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                            for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], np.float32)
        u, v, z = cam.project(corners)
        if np.median(z) < 0.2:
            return
        ok = z > 0.2
        for a in range(8):
            for b in range(a + 1, 8):
                if bin(a ^ b).count("1") == 1 and ok[a] and ok[b]:
                    dr.line([(u[a], v[a]), (u[b], v[b])], fill=color, width=width)
        if label and ok.any():
            dr.text((float(np.clip(u[ok].min(), 2, cam.w - 140)),
                     float(np.clip(v[ok].min() - 14, 2, cam.h - 14))), label, fill=color)

    for metaf in sorted(views_dir.glob("gpu_yaw*.json")):
        meta = json.loads(metaf.read_text())
        imgf = views_dir / meta["file"]
        if not imgf.exists():
            continue
        w, h = (int(t) for t in meta["res"].split("x"))
        cam = r3.Cam([float(t) for t in meta["cam"].split(",")],
                     [float(t) for t in meta["look"].split(",")],
                     [float(t) for t in meta["up"].split(",")],
                     float(meta["fov"]), w, h)
        im = Image.open(imgf).convert("RGB")
        dr = ImageDraw.Draw(im)
        for _oid, elo, ehi in exist:
            draw_box(dr, cam, elo, ehi, (150, 150, 150), 1)
        for p in prop["placements"]:
            lo, hi = aabb(p)
            draw_box(dr, cam, lo, hi, (40, 230, 90), 3, f'+ {p["label"]}')
        outf = pkg / f"proposal_view_{metaf.stem}.png"
        im.save(outf)
        print("[proposal] wrote", outf, flush=True)

    # ---- plan ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    fig, ax = plt.subplots(figsize=(8, 8))
    for oid, elo, ehi in exist:
        ax.add_patch(Rectangle((elo[0], elo[2]), ehi[0] - elo[0], ehi[2] - elo[2],
                               fill=False, edgecolor="grey", linewidth=1))
    for p in prop["placements"]:
        lo, hi = aabb(p)
        ax.add_patch(Rectangle((lo[0], lo[2]), hi[0] - lo[0], hi[2] - lo[2],
                               fill=True, facecolor=(0.2, 0.85, 0.4, 0.5),
                               edgecolor="green", linewidth=2))
        ax.text(lo[0], lo[2] - 0.06, f'+ {p["label"]}', color="green", fontsize=9)
    if "extent_p1" in fr:
        (x0, _, z0), (x1, _, z1) = fr["extent_p1"], fr["extent_p99"]
        ax.add_patch(Rectangle((x0, z0), x1 - x0, z1 - z0, fill=False,
                               edgecolor="black", linestyle="--", linewidth=1))
        ax.set_xlim(x0 - 0.4, x1 + 0.4); ax.set_ylim(z1 + 0.4, z0 - 0.4)
    ax.plot(0, 0, "r*", markersize=14)
    ax.set_aspect("equal"); ax.set_xlabel("x"); ax.set_ylabel("z")
    ax.set_title(f"{sc}: proposed placements (green) vs existing (grey)")
    fig.tight_layout(); fig.savefig(pkg / "proposal_plan.png", dpi=110)
    print("[proposal] wrote", pkg / "proposal_plan.png", flush=True)


if __name__ == "__main__":
    main()
