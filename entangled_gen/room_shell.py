"""
Room shell — measured world architecture (walls · ceiling · floor).

W1 (default mode) — MEASURED SHELL -> out/<scene>/room_shell.json.
Assumptions (user 2026-07-26, "clean and workable"):
  - VERTICAL-PRISM WALLS: a plan cell is a wall candidate only if its
    splat reaches within TOP_TOL of the measured ceiling (kills beds and
    low furniture; verified on bedroom_marble: the x_low "wall" at -2.05
    was furniture, the true wall at -2.427 = the collider's plane).
  - v1 fits ONE outer segment per axis side (4 sides) but the schema is a
    LIST of wall segments — non-box rooms (N segments, boundary tracing)
    are a schema-compatible v2, not a rewrite.
  - Per side, ALL parallel candidate planes are recorded (curtain planes,
    wardrobe fronts, visible wall surfaces) with evidence; the STRUCTURAL
    plane = the outermost strong candidate. Record-then-judge: nothing
    discarded, consumers choose.
Floor/ceiling: y-histogram peaks (measured, not inherited). Collider
planes (Marble bundles) corroborate wherever present; never required.
Consumers: graph/build_graph.py (architecture nodes) + envelope.py
(rewired: reads the shell instead of the legacy manifest).

W0 (--audit; PLAN_ROOM_SHELL.md): REPORT ONLY.
The scene-graph record's wall planes are unverified placeholders (splat
p1/p99 extent). This audit answers, with numbers, "where are the REAL
walls?" three independent ways before anything is fitted:

  1. splat density: 1 cm histograms of wall-band points (0.3 m above
     floor .. 0.1 m below ceiling) perpendicular to each current bound —
     a real wall is a sharp density peak; report peak position vs the
     p1/p99 placeholder, sharpness (peak/interior median) and width;
  2. y histogram (2 cm): measured floor and ceiling peaks vs the frame's
     floor_y / ceiling_y;
  3. collider cross-check (Marble bundles only, absent elsewhere):
     collider_registered.glb planar patches via face-normal clustering —
     every patch >= 0.5 m^2 with its plane offset, so the mesh the user
     already trusts votes on the same question.

Plus a top-down occupancy image of the wall band — non-box room shapes
(alcoves, L-rooms) show up here; the W1 fitter must handle N wall
segments, not assume 4 (user rule 07-26).

Out: out/<scene>/room_shell_audit.json + room_shell_audit.png
Run: python room_shell.py --scene bedroom_marble --audit
Frames: all math upright (raw * raw_to_render, elementwise +-1,
self-inverse); reported positions are given in BOTH upright and raw.
raw_to_render is read from the legacy manifest for now (W1 carries it
into room_shell.json so the legacy read dies there).
"""
import argparse
import json
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
import sys
sys.path.insert(0, str(HERE))
import paths                      # noqa: E402
from splat_place import read_ply  # noqa: E402

WALL_BAND_LO = 0.30    # m above floor: skip baseboards/rug/furniture feet
WALL_BAND_HI = 0.10    # m below ceiling: skip cornice/ceiling points
BIN_WALL = 0.01        # m, histogram bin perpendicular to walls
BIN_Y = 0.02           # m, vertical histogram bin
SEARCH = 0.45          # m, wall peak searched within bound +- this
MIN_PATCH_AREA = 0.5   # m^2, collider planar patch report floor
NORMAL_ROUND = 0.05    # collider face-normal clustering grid


def load_upright_points(scene, fr):
    ply = paths.ply(scene)
    names, data = read_ply(ply)
    ix = {n: i for i, n in enumerate(names)}
    alpha = 1 / (1 + np.exp(-data[:, ix["opacity"]]))
    xyz = data[alpha > 0.3][:, [ix["x"], ix["y"], ix["z"]]]
    r2r = np.array(fr["raw_to_render"], dtype=np.float64)
    return xyz * r2r, r2r


def peak_report(pts_axis, bound, side):
    """Density peak near one bound. side=+1: bound is the LOW end (wall
    material extends below the peak); side=-1: HIGH end."""
    lo, hi = bound - SEARCH, bound + SEARCH
    sel = pts_axis[(pts_axis >= lo) & (pts_axis <= hi)]
    if len(sel) < 100:
        return {"bound": round(bound, 3), "peak": None,
                "note": f"only {len(sel)} points near bound"}
    nb = int(np.ceil((hi - lo) / BIN_WALL))
    cnt, edges = np.histogram(sel, bins=nb, range=(lo, hi))
    k = int(np.argmax(cnt))
    peak = (edges[k] + edges[k + 1]) / 2
    # sharpness vs interior density: median count over the interior third
    interior = cnt[nb // 3: 2 * nb // 3] if side > 0 else \
        cnt[nb // 3: 2 * nb // 3]
    med = float(np.median(interior)) or 1.0
    half = cnt[k] / 2
    w = np.where(cnt >= half)[0]
    width = (w.max() - w.min() + 1) * BIN_WALL if len(w) else None
    return {"bound": round(bound, 3),
            "peak": round(float(peak), 3),
            "peak_minus_bound_m": round(float(peak - bound), 3),
            "peak_count": int(cnt[k]),
            "sharpness_x_interior": round(cnt[k] / med, 1),
            "halfmax_width_m": round(float(width), 3) if width else None}


def collider_patches(scene, r2r):
    """Per-axis, area-weighted offset histogram of near-axis-aligned faces
    (peaks = the mesh's dominant planes), plus how much face area is
    OBLIQUE (>= 25 deg off every axis) — the non-box-room signal. All
    positions reported UPRIGHT. Exact per-normal clustering fragmented
    the walls (triangulated meshes wobble normals), hence histograms."""
    f = paths.scene_dir(scene) / "collider_registered.glb"
    if not f.exists():
        return None
    import trimesh
    m = trimesh.load(str(f), force="mesh")
    n = m.face_normals * np.asarray(r2r)          # upright normals
    c = m.triangles_center * np.asarray(r2r)      # upright centers
    a = m.area_faces
    out = {"total_area_m2": round(float(a.sum()), 2), "planes": [],
           "oblique_area_m2": 0.0}
    axis_names = ["x", "y", "z"]
    aligned = np.zeros(len(a), dtype=bool)
    for ax in range(3):
        sel = np.abs(n[:, ax]) > 0.9
        aligned |= sel
        if not sel.any():
            continue
        pos = c[sel, ax]
        w = a[sel]
        nb = max(8, int((pos.max() - pos.min()) / 0.02))
        cnt, edges = np.histogram(pos, bins=nb, weights=w)
        mid = (edges[:-1] + edges[1:]) / 2
        # peaks: bins over MIN_PATCH_AREA, merged when adjacent (<6 cm)
        order = np.argsort(cnt)[::-1]
        used = np.zeros(nb, dtype=bool)
        for k in order:
            if cnt[k] < MIN_PATCH_AREA / 2 or used[max(0, k - 3):k + 4].any():
                continue
            lo, hi = max(0, k - 3), min(nb, k + 4)
            area = float(cnt[lo:hi].sum())
            if area < MIN_PATCH_AREA:
                continue
            used[lo:hi] = True
            out["planes"].append({"axis": axis_names[ax],
                                  "offset_upright_m": round(float(mid[k]), 3),
                                  "area_m2": round(area, 2)})
    out["oblique_area_m2"] = round(float(a[~aligned].sum()), 2)
    out["planes"].sort(key=lambda p: -p["area_m2"])
    return out


CELL = 0.05        # m, plan cell for the top-height map
TOP_TOL = 0.20     # m, cell top must reach ceiling - this to be wall-like
MIN_CELL_PTS = 5   # points for a cell to count at all
PEAK_KEEP = 0.30   # candidate plane = histogram peak >= this * max peak
PEAK_MERGE = 0.06  # m, peaks closer than this merge into one candidate
COLL_MATCH = 0.06  # m, collider plane corroborates a candidate within this


def measure_floor_ceiling(pts):
    ys = pts[:, 1]
    nb = int(np.ceil((ys.max() - ys.min()) / BIN_Y))
    cnt, edges = np.histogram(ys, bins=nb)
    mid = (edges[:-1] + edges[1:]) / 2
    half = (ys.min() + ys.max()) / 2
    lo = cnt.copy(); lo[mid > half] = 0
    hi = cnt.copy(); hi[mid <= half] = 0
    return float(mid[int(np.argmax(lo))]), float(mid[int(np.argmax(hi))])


def side_candidates(vals, lo, hi, outer_is_low):
    """Candidate parallel planes along one axis from wall-cell point
    positions: histogram peaks >= PEAK_KEEP * max, merged within
    PEAK_MERGE; structural = the outermost candidate."""
    nb = max(8, int((hi - lo) / BIN_WALL))
    cnt, edges = np.histogram(vals, bins=nb, range=(lo, hi))
    mid = (edges[:-1] + edges[1:]) / 2
    if cnt.max() == 0:
        return []
    keep = np.where(cnt >= PEAK_KEEP * cnt.max())[0]
    cands = []                      # [position, weight]
    for k in keep:
        # local maxima only
        if (k > 0 and cnt[k - 1] > cnt[k]) or \
           (k < nb - 1 and cnt[k + 1] > cnt[k]):
            continue
        p = float(mid[k])
        for c in cands:
            if abs(c[0] - p) < PEAK_MERGE:
                if cnt[k] > c[1]:
                    c[0], c[1] = p, int(cnt[k])
                break
        else:
            cands.append([p, int(cnt[k])])
    cands.sort(key=lambda c: c[0], reverse=not outer_is_low)
    return [{"position": round(c[0], 3), "point_count": c[1]} for c in cands]


def fit_shell(scene, fr, pts, r2r):
    # Clip to the frame's robust extents (+SEARCH margin) before ANY
    # histogramming. Generated splats leak floater gaussians through
    # openings (living_marble 08-06: sky/ground points 10+ m outside the
    # room dragged the floor/ceiling midpoint split to -9.5 — the fitter
    # called the real floor "ceiling" and a floater cluster "floor").
    # The audit path already clips this way; the extents come from the
    # frame block, no new estimation. Closed rooms (bedroom) are a no-op.
    r2r_a = np.asarray(r2r, dtype=np.float64)
    ext_lo = np.minimum(np.array(fr["extent_p1"]) * r2r_a,
                        np.array(fr["extent_p99"]) * r2r_a) - SEARCH
    ext_hi = np.maximum(np.array(fr["extent_p1"]) * r2r_a,
                        np.array(fr["extent_p99"]) * r2r_a) + SEARCH
    n_all = len(pts)
    pts = pts[np.all((pts >= ext_lo) & (pts <= ext_hi), axis=1)]
    if n_all - len(pts):
        print(f"[shell] extent clip: {n_all - len(pts):,} of {n_all:,} "
              f"points outside robust extents dropped", flush=True)
    floor_m, ceil_m = measure_floor_ceiling(pts)
    # top-height map over plan cells
    x, y, z = pts[:, 0], pts[:, 1], pts[:, 2]
    x0, x1 = float(x.min()), float(x.max())
    z0, z1 = float(z.min()), float(z.max())
    nx = int(np.ceil((x1 - x0) / CELL)); nz = int(np.ceil((z1 - z0) / CELL))
    ci = ((x - x0) / CELL).astype(np.int32).clip(0, nx - 1)
    cz = ((z - z0) / CELL).astype(np.int32).clip(0, nz - 1)
    flat = ci * nz + cz
    top = np.full(nx * nz, -np.inf)
    np.maximum.at(top, flat, y)
    npts = np.bincount(flat, minlength=nx * nz)
    wall_cell = (top >= ceil_m - TOP_TOL) & (npts >= MIN_CELL_PTS)
    in_wall_cell = wall_cell[flat]
    wp = pts[in_wall_cell]                       # wall-candidate points

    coll = collider_patches(scene, r2r)

    def coll_near(axis, pos):
        if not coll:
            return None
        best = None
        for p in coll["planes"]:
            if p["axis"] != axis:
                continue
            d = abs(p["offset_upright_m"] - pos)
            if d <= COLL_MATCH and (best is None or d < best[1]):
                best = (p, d)
        return None if best is None else \
            {"collider_offset_m": best[0]["offset_upright_m"],
             "collider_area_m2": best[0]["area_m2"],
             "delta_m": round(best[1], 3)}

    walls = []
    sides = [("x", 0, 2, True), ("x", 0, 2, False),
             ("z", 2, 0, True), ("z", 2, 0, False)]
    for axis, col, tcol, outer_is_low in sides:
        vals = wp[:, col]
        mid = (vals.min() + vals.max()) / 2
        sel = vals < mid if outer_is_low else vals >= mid
        sv = wp[sel]
        if len(sv) < 200:
            continue
        cands = side_candidates(sv[:, col], sv[:, col].min() - 0.02,
                                sv[:, col].max() + 0.02, outer_is_low)
        if not cands:
            continue
        for c in cands:
            c["collider"] = coll_near(axis, c["position"])
        structural = cands[0]
        # parallel surfaces: only within 0.6 m of the structural plane
        # (curtain planes, visible wall faces, wardrobe fronts) and the
        # strongest 5 — the far-interior tall-furniture peaks are not
        # "surfaces of this wall"
        parallels = [c for c in cands[1:]
                     if abs(c["position"] - structural["position"]) <= 0.6]
        parallels.sort(key=lambda c: -c["point_count"])
        parallels = parallels[:5]
        near = sv[np.abs(sv[:, col] - structural["position"]) <= 0.05]
        tan_lo = float(near[:, tcol].min()) if len(near) else None
        tan_hi = float(near[:, tcol].max()) if len(near) else None
        side_name = f"{axis}_{'low' if outer_is_low else 'high'}"
        inward = [0.0, 0.0, 0.0]
        inward[col] = 1.0 if outer_is_low else -1.0
        walls.append({
            "id": f"wall_{side_name}",
            "axis": axis,
            "plane_upright_m": structural["position"],
            "inward_normal_upright": inward,
            "extent_tangent_observed_m": [round(tan_lo, 3), round(tan_hi, 3)]
                if tan_lo is not None else None,
            "extent_tangent_span_m": None,   # filled below (room rectangle)
            "extent_y_upright_m": [round(floor_m, 3), round(ceil_m, 3)],
            "evidence": {"point_count": structural["point_count"],
                         "collider": structural["collider"],
                         "n_wall_cells_side": int(len(sv))},
            "parallel_surfaces": parallels,
        })
    # span each wall to the PERPENDICULAR structural planes (the room
    # rectangle): the observed extent covers only where splat sits ON the
    # plane (27-45% on bedroom_marble — the rest hides behind curtains /
    # furniture / openings); observed stays as evidence + coverage metric
    for w in walls:
        perp = sorted(v["plane_upright_m"] for v in walls
                      if v["axis"] != w["axis"])
        if len(perp) >= 2:
            span = [perp[0], perp[-1]]
            w["extent_tangent_span_m"] = [round(span[0], 3),
                                          round(span[1], 3)]
            obs = w["extent_tangent_observed_m"]
            if obs:
                w["evidence"]["observed_coverage"] = round(
                    (obs[1] - obs[0]) / (span[1] - span[0]), 2)
    return {"floor_upright_m": round(floor_m, 3),
            "ceiling_upright_m": round(ceil_m, 3),
            "walls": walls, "collider": coll,
            "n_wall_cells": int(wall_cell.sum())}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--audit", action="store_true")
    a = ap.parse_args()
    if not a.audit:
        sd = paths.scene_dir(a.scene)
        fr = paths.frame_block(a.scene)
        pts, r2r = load_upright_points(a.scene, fr)
        shell = fit_shell(a.scene, fr, pts, r2r)
        sy = r2r[1]
        out = {
            "scene": a.scene,
            "generated_by": "room_shell.py (W1 — PLAN_ROOM_SHELL.md)",
            "assumptions": ["vertical_prism_walls_floor_to_ceiling",
                            "v1_one_outer_segment_per_axis_side",
                            "all_parallel_candidates_recorded"],
            "frame": {"raw_to_render": list(map(float, r2r)),
                      "note": ("*_upright values are raw*r2r; raw value = "
                               "upright * the same component (r2r is "
                               "self-inverse)")},
            "floor_y_raw": round(shell["floor_upright_m"] * sy, 3),
            "ceiling_y_raw": round(shell["ceiling_upright_m"] * sy, 3),
            **shell,
        }
        f = sd / "room_shell.json"
        f.write_text(json.dumps(out, indent=1))
        print(f"[shell] wrote {f}")
        print(f"[shell] floor {shell['floor_upright_m']:+.3f}  ceiling "
              f"{shell['ceiling_upright_m']:+.3f}  (upright; "
              f"{shell['n_wall_cells']} wall cells)")
        for w in shell["walls"]:
            cb = w["evidence"]["collider"]
            print(f"  {w['id']:11s} plane {w['plane_upright_m']:+7.3f}  "
                  f"pts {w['evidence']['point_count']:>6}  collider "
                  f"{'agree d=' + str(cb['delta_m']) if cb else '—'}  "
                  f"parallels {len(w['parallel_surfaces'])}")
        return
    sd = paths.scene_dir(a.scene)
    fr = paths.frame_block(a.scene)
    pts, r2r = load_upright_points(a.scene, fr)

    floor_u = fr["floor_y"] * r2r[1]
    ceil_u = fr["ceiling_y"] * r2r[1]
    lo_u = np.minimum(np.array(fr["extent_p1"]) * r2r,
                      np.array(fr["extent_p99"]) * r2r)
    hi_u = np.maximum(np.array(fr["extent_p1"]) * r2r,
                      np.array(fr["extent_p99"]) * r2r)

    band = pts[(pts[:, 1] >= floor_u + WALL_BAND_LO)
               & (pts[:, 1] <= ceil_u - WALL_BAND_HI)]
    inplan = pts[(pts[:, 0] >= lo_u[0] - SEARCH) & (pts[:, 0] <= hi_u[0] + SEARCH)
                 & (pts[:, 2] >= lo_u[2] - SEARCH) & (pts[:, 2] <= hi_u[2] + SEARCH)]

    walls = {
        "x_low": peak_report(band[:, 0], lo_u[0], +1),
        "x_high": peak_report(band[:, 0], hi_u[0], -1),
        "z_low": peak_report(band[:, 2], lo_u[2], +1),
        "z_high": peak_report(band[:, 2], hi_u[2], -1),
    }

    # floor + ceiling peaks from the y histogram
    ys = inplan[:, 1]
    nb = int(np.ceil((ys.max() - ys.min()) / BIN_Y))
    cnt, edges = np.histogram(ys, bins=nb)
    mid = (edges[:-1] + edges[1:]) / 2
    lo_half = cnt.copy(); lo_half[mid > (floor_u + ceil_u) / 2] = 0
    hi_half = cnt.copy(); hi_half[mid <= (floor_u + ceil_u) / 2] = 0
    fpk = float(mid[int(np.argmax(lo_half))])
    cpk = float(mid[int(np.argmax(hi_half))])
    yrep = {"floor_frame": round(floor_u, 3), "floor_peak": round(fpk, 3),
            "floor_delta_m": round(fpk - floor_u, 3),
            "ceil_frame": round(ceil_u, 3), "ceil_peak": round(cpk, 3),
            "ceil_delta_m": round(cpk - ceil_u, 3)}

    patches = collider_patches(a.scene, r2r)

    # ---- top-down occupancy image (non-box shapes show here) ----
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axes = plt.subplots(1, 3, figsize=(16, 5.2))
    H, xe, ze = np.histogram2d(band[:, 0], band[:, 2], bins=[
        int((hi_u[0] - lo_u[0] + 2 * SEARCH) / 0.02),
        int((hi_u[2] - lo_u[2] + 2 * SEARCH) / 0.02)],
        range=[[lo_u[0] - SEARCH, hi_u[0] + SEARCH],
               [lo_u[2] - SEARCH, hi_u[2] + SEARCH]])
    axes[0].imshow(np.log1p(H.T), origin="lower", cmap="magma",
                   extent=[xe[0], xe[-1], ze[0], ze[-1]], aspect="equal")
    from matplotlib.patches import Rectangle
    axes[0].add_patch(Rectangle((lo_u[0], lo_u[2]), hi_u[0] - lo_u[0],
                                hi_u[2] - lo_u[2], fill=False, ec="cyan",
                                lw=1.2, ls="--"))
    axes[0].set_title("wall-band occupancy (log) · cyan = p1/p99 placeholder")
    for ax_i, (axname, col) in enumerate([("x", 0), ("z", 2)]):
        ax = axes[1 + ax_i]
        v = band[:, col]
        nb2 = int((v.max() - v.min()) / BIN_WALL)
        ax.hist(v, bins=nb2, color="#446", log=True)
        for side in ([lo_u[col], hi_u[col]]):
            ax.axvline(side, color="cyan", ls="--", lw=1)
        for key in (f"{axname}_low", f"{axname}_high"):
            pk = walls[key].get("peak")
            if pk is not None:
                ax.axvline(pk, color="red", lw=1)
        ax.set_title(f"density along {axname} · cyan placeholder / red peak")
    fig.tight_layout()
    png = sd / "room_shell_audit.png"
    fig.savefig(png, dpi=110)

    rep = {"scene": a.scene,
           "frame_note": "positions UPRIGHT (raw*r2r); r2r " + str(list(r2r)),
           "wall_band_m": [WALL_BAND_LO, WALL_BAND_HI],
           "walls_vs_placeholder": walls,
           "floor_ceiling": yrep,
           "collider_patches": patches,
           "n_points_wall_band": int(len(band))}
    out = sd / "room_shell_audit.json"
    out.write_text(json.dumps(rep, indent=1))

    print(f"[shell-audit] {out}")
    print(f"[shell-audit] wall band points: {len(band):,}")
    for k, w in walls.items():
        print(f"  {k:7s} bound {w['bound']:+7.3f}  peak "
              f"{w.get('peak')}  d {w.get('peak_minus_bound_m')}  "
              f"sharp x{w.get('sharpness_x_interior')}  "
              f"width {w.get('halfmax_width_m')}")
    print(f"  floor  frame {yrep['floor_frame']:+.3f} peak "
          f"{yrep['floor_peak']:+.3f} (d {yrep['floor_delta_m']:+.3f})")
    print(f"  ceil   frame {yrep['ceil_frame']:+.3f} peak "
          f"{yrep['ceil_peak']:+.3f} (d {yrep['ceil_delta_m']:+.3f})")
    if patches is None:
        print("  collider: none for this scene (cross-check skipped)")
    else:
        print(f"  collider: total area {patches['total_area_m2']} m^2, "
              f"oblique (non-axis) {patches['oblique_area_m2']} m^2")
        for p in patches["planes"][:14]:
            print(f"    plane {p['axis']}={p['offset_upright_m']:+7.3f}  "
                  f"area {p['area_m2']}")
    print(f"[shell-audit] plots: {png}")


if __name__ == "__main__":
    main()
