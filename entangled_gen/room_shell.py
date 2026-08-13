"""
Room shell â€” measured world architecture (walls Â· ceiling Â· floor).

W1 (default mode) â€” MEASURED SHELL -> out/<scene>/room_shell.json.
Assumptions (user 2026-07-26, "clean and workable"):
  - VERTICAL-PRISM WALLS: a plan cell is a wall candidate only if its
    splat reaches within TOP_TOL of the measured ceiling (kills beds and
    low furniture; verified on bedroom_marble: the x_low "wall" at -2.05
    was furniture, the true wall at -2.427 = the collider's plane).
  - v1 fits ONE outer segment per axis side (4 sides) but the schema is a
    LIST of wall segments â€” non-box rooms (N segments, boundary tracing)
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
     floor .. 0.1 m below ceiling) perpendicular to each current bound â€”
     a real wall is a sharp density peak; report peak position vs the
     p1/p99 placeholder, sharpness (peak/interior median) and width;
  2. y histogram (2 cm): measured floor and ceiling peaks vs the frame's
     floor_y / ceiling_y;
  3. collider cross-check (Marble bundles only, absent elsewhere):
     collider_registered.glb planar patches via face-normal clustering â€”
     every patch >= 0.5 m^2 with its plane offset, so the mesh the user
     already trusts votes on the same question.

Plus a top-down occupancy image of the wall band â€” non-box room shapes
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
    OBLIQUE (>= 25 deg off every axis) â€” the non-box-room signal. All
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
    # room dragged the floor/ceiling midpoint split to -9.5 â€” the fitter
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
        # strongest 5 â€” the far-interior tall-furniture peaks are not
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
    # plane (27-45% on bedroom_marble â€” the rest hides behind curtains /
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


# ---- W4 polygonal shell v2: TRACE -> CLOSE -> MERGE (--poly) ----------
# User design 2026-08-09 (PLAN_ROOM_SHELL.md Â§3-W4). REVIEW ARTIFACTS
# ONLY: writes room_shell_poly.json + room_shell_poly.png next to the v1
# shell; nothing downstream reads them until the W4 gate passes.
# 1. TRACE the interior boundary of the wall-material map wherever it is
#    dense enough (never invent where you could measure);
# 2. CLOSE the polygon â€” every un-traceable stretch becomes a segment
#    MARKED inferred, never passed off as measured;
# 3. MERGE similar planes â€” cardinal snap is a special case of the
#    merge, position re-measured from the density spike; what cannot
#    snap survives as a connector at its traced angle, and connector /
#    closure pieces absorb the error so walls never move.
POLY_MARGIN = 1.5   # m beyond p1/p99 kept for the trace â€” the v1 clip
                    # (SEARCH 0.45) amputates the pocket beyond an
                    # opening (obj_001); floater columns past this are
                    # killed by the floor-to-ceiling rule, not the clip
POLY_DP_M = 0.12    # m, trace simplification tolerance
POLY_SNAP_DEG = 12  # deg, segment within this of an axis snaps cardinal
POLY_MERGE_M = 0.15 # m, same-axis neighbours within this merge
POLY_INK_M = 0.15   # m, wall material within this of a segment = traced
POLY_MEAS_FRAC = 0.5  # >= this fraction inked => measured, else inferred
POLY_GROUP_M = 0.35   # m, same-axis planes within this = one wall group
POLY_MAJ_M = 0.08     # m, positions within this vote for one plane
POLY_MIN_SEG_M = 0.30  # m, clean polygon swallows pieces shorter than this
POLY_CONN_KEEP_M = 0.50  # m, connectors at least this long keep their
                         # traced angle; shorter jogs become square steps
POLY_WALL_MIN_M = 2.0    # m, a cardinal GROUP below this total traced
                         # length is not architecture (user ruling
                         # 2026-08-09: wall_04 was a shelf at the
                         # corner) â€” its pieces are dropped and the
                         # neighbouring planes close straight across.
                         # Judged per group, not per segment, so a short
                         # fragment of a long wall survives. Furniture
                         # longer than this bar still defeats it, same
                         # honesty note as the height rule
POLY_TALL_M = 1.4   # m above the floor a solid cell's band material
                    # must reach â€” walls/curtains/glass doors do,
                    # sofas/tables/dressers do not (the furniture-dent
                    # guard; replaces v1's reaches-the-ceiling rule,
                    # which a dense Marble ceiling defeats)
POLY_REACH_M = 3.0  # m, a traced pocket may extend at most this far
                    # (geodesic, through free space) beyond the frame's
                    # robust box. Without the cap the flood escapes an
                    # unbounded opening and wraps around the OUTSIDE of
                    # the walls (living_marble: the east wall traced
                    # twice, once per face). First value, uncalibrated â€”
                    # it bounds pocket DEPTH, not which scenes work


def _dp(pts, tol):
    """Douglas-Peucker on an open polyline (list of [x, z])."""
    if len(pts) < 3:
        return pts
    a, b = np.asarray(pts[0]), np.asarray(pts[-1])
    mid = np.asarray(pts[1:-1])
    ab = b - a
    L = float(np.hypot(*ab))
    if L < 1e-9:            # degenerate chord (closed loop handed in
                            # whole): distance from the endpoint instead
        d = np.hypot(*(mid - a).T)
    else:
        d = np.abs(ab[0] * (a[1] - mid[:, 1])
                   - ab[1] * (a[0] - mid[:, 0])) / L
    k = int(np.argmax(d))
    if d[k] <= tol:
        return [pts[0], pts[-1]]
    left = _dp(pts[:k + 2], tol)
    return left[:-1] + _dp(pts[k + 1:], tol)


def _dp_loop(loop, tol):
    """Simplify a CLOSED loop: split at the point farthest from the
    start (a degenerate chord defeats plain DP), DP each half."""
    p0 = np.asarray(loop[0])
    k = int(np.argmax(np.hypot(*(np.asarray(loop) - p0).T)))
    if k < 2 or k > len(loop) - 3:
        return _dp(loop, tol)
    left = _dp(loop[:k + 1], tol)
    return left[:-1] + _dp(loop[k:], tol)


_MOORE = [(-1, 0), (-1, 1), (0, 1), (1, 1),
          (1, 0), (1, -1), (0, -1), (-1, -1)]


def _trace_boundary(mask):
    """Moore-neighbour trace of the OUTER boundary of the largest True
    region: one ordered CLOSED loop of cell indices. (plt.contour
    fragments a jagged mask into open pieces â€” this never does.)"""
    xs, zs = np.nonzero(mask)
    k = int(np.argmin(xs * mask.shape[1] + zs))   # scan order first
    start = (int(xs[k]), int(zs[k]))
    loop = [start]
    prev_dir = 6                                  # came from the left
    cur = start
    H, W = mask.shape
    for _ in range(8 * mask.size):
        found = False
        for j in range(8):
            d = (prev_dir + 1 + j) % 8            # clockwise sweep from
            dy, dx = _MOORE[d]                    # the backtrack side
            ny, nz2 = cur[0] + dy, cur[1] + dx
            if 0 <= ny < H and 0 <= nz2 < W and mask[ny, nz2]:
                cur = (ny, nz2)
                prev_dir = (d + 4) % 8
                found = True
                break
        if not found:                             # isolated cell
            break
        if cur == start:
            break
        loop.append(cur)
    return loop


def _rectilinearize_verts(verts):
    """A polyline -> a staircase of axis-aligned legs (R-S2-149): each
    maximal run of same-dominant-axis edges becomes one cardinal at the
    length-weighted mean plane. Shared by the live chain conversion in
    run_poly and the pre-snap review panel, so the panel can never
    drift from the pipeline."""
    runs = []
    for a, b in zip(verts[:-1], verts[1:]):
        a = np.asarray(a, float)
        b = np.asarray(b, float)
        d = b - a
        L = float(np.hypot(*d))
        if L < 1e-9:
            continue
        ax = "z" if abs(d[0]) >= abs(d[1]) else "x"  # along x = z-wall
        if runs and runs[-1][0] == ax:
            runs[-1][1].append((a, b, L))
        else:
            runs.append((ax, [(a, b, L)]))
    out = []
    for ax, edges in runs:
        Ls = [w for _, _, w in edges]
        if ax == "z":
            pos = float(np.average(
                [(a[1] + b[1]) / 2 for a, b, _ in edges], weights=Ls))
            p = np.array([edges[0][0][0], pos])
            q = np.array([edges[-1][1][0], pos])
            ln = abs(q[0] - p[0])
        else:
            pos = float(np.average(
                [(a[0] + b[0]) / 2 for a, b, _ in edges], weights=Ls))
            p = np.array([pos, edges[0][0][1]])
            q = np.array([pos, edges[-1][1][1]])
            ln = abs(q[1] - p[1])
        if ln < 1e-6:
            continue          # a switchback run with no net movement
        out.append({"kind": "cardinal", "axis": ax, "plane": pos,
                    "p": p, "q": q, "len": float(ln)})
    return out


def _render_steps(sd, scene, st, out_segs, clean_segs):
    """--steps-sheet: every stage of the W4 trace as its own panel, in
    the order the code runs them, so a wrong outline can be blamed on
    the exact step that wronged it (user ask 2026-08-12: 'break these
    down step by step, give me visual of each step'). REVIEW ARTIFACT
    ONLY â€” writes room_shell_steps.png and nothing else."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    x0, z0, nx, nz = st["grid"]
    ex = [x0, x0 + nx * CELL, z0, z0 + nz * CELL]

    def density(ax):
        b = st["band"]
        H, xe, ze = np.histogram2d(
            b[:, 0], b[:, 2],
            bins=[max(2, int((ex[1] - ex[0]) / 0.02)),
                  max(2, int((ex[3] - ex[2]) / 0.02))],
            range=[[ex[0], ex[1]], [ex[2], ex[3]]])
        ax.imshow(np.log1p(H.T), origin="lower", cmap="gray_r",
                  extent=ex, aspect="equal")

    def mask(ax, m, rgba):
        img = np.zeros((*m.T.shape, 4))
        img[m.T] = rgba
        ax.imshow(img, origin="lower", extent=ex, aspect="equal")

    kind_col = {"cardinal": "#1db954", "connector": "#ff9f1c",
                "step": "#9b5de5"}
    fig, axes = plt.subplots(3, 3, figsize=(24, 17))
    axs = list(axes.ravel())

    ax = axs[0]
    density(ax)
    ax.set_title("1. all splat material between floor and ceiling,\n"
                 "seen from above (dark = dense)")

    ax = axs[1]
    density(ax)
    mask(ax, st["solid"], (0.86, 0.2, 0.27, 0.8))
    ax.set_title("2. 'solid' squares (red): dense AND reaching 1.4 m up\n"
                 "â€” walls, but also shelves and curtains")

    ax = axs[2]
    density(ax)
    mask(ax, st["floor_ok"], (0.2, 0.6, 0.3, 0.45))
    bx = st["box"]
    ax.add_patch(Rectangle((bx[0], bx[1]), bx[2] - bx[0], bx[3] - bx[1],
                           fill=False, ec="#1f6feb", lw=2, ls=":"))
    ax.set_title("3. floor evidence (green) + the rough box (blue).\n"
                 "Open space must be in the box OR stand on floor")

    ax = axs[3]
    mask(ax, st["free"], (0.72, 0.72, 0.72, 0.6))
    mask(ax, st["interior_precap"], (0.99, 0.75, 0.18, 0.85))
    ax.set_title("4. open-space regions (gray);\nthe one picked as THE "
                 "ROOM (orange)")

    ax = axs[4]
    mask(ax, st["interior_precap"], (0.82, 0.82, 0.82, 0.6))
    mask(ax, st["interior"], (0.95, 0.55, 0.1, 0.9))
    ax.set_title("5. leash + floor union: 3 m leash for floorless space,\n"
                 "NO cap through seen floor (orange kept, gray cut off)")

    ax = axs[5]
    density(ax)
    lp = np.asarray(st["loop"] + [st["loop"][0]])
    ax.plot(lp[:, 0], lp[:, 1], "-", color="#e63946", lw=1.5)
    ax.set_title("6. the walk: march around the room's edge\n"
                 "(red = the raw trace)")

    ax = axs[6]
    density(ax)
    for s in out_segs:
        (px, pz), (qx, qz) = s["endpoints_upright"]
        ax.plot([px, qx], [pz, qz], "-",
                color=kind_col.get(s["kind"], "#333"), lw=2.2)
    ax.set_title("7. straighten + label the pieces; near-axis pieces\n"
                 "re-measure onto the nearest dense band\n"
                 "(green = wall-like, orange = angled, purple = step)")

    ax = axs[7]
    density(ax)
    for ax_w, plane, (pp, qq) in st.get("cards_pre", []):
        if ax_w == "z":                      # constant-z wall, runs along x
            xs2 = sorted((pp[0], qq[0]))
            ax.plot(xs2, [plane, plane], "-", color="#1db954", lw=2.6)
        else:                                # constant-x wall, runs along z
            zs2 = sorted((pp[1], qq[1]))
            ax.plot([plane, plane], zs2, "-", color="#1db954", lw=2.6)
    for poly in st.get("chain_polylines", []):
        for leg in _rectilinearize_verts([np.asarray(v, float)
                                          for v in poly]):
            ax.plot([leg["p"][0], leg["q"][0]], [leg["p"][1], leg["q"][1]],
                    "-", color="#12b5cb", lw=2.2)
    ax.set_title("7b. everything as CARDINALS at their OWN traced planes\n"
                 "(green = walls at spike positions, teal = staircase legs\n"
                 "from angled runs) — BEFORE the group snap moves anything")

    ax = axs[8]
    density(ax)
    for s in out_segs:
        (px, pz), (qx, qz) = s["endpoints_upright"]
        ax.plot([px, qx], [pz, qz], "-", color="#b8b8d8", lw=1.0)
    for s in clean_segs:
        (px, pz), (qx, qz) = s["endpoints_upright"]
        ax.plot([px, qx], [pz, qz],
                "-" if s["status"] == "measured" else "--",
                color=kind_col[s["kind"]], lw=3.0)
    v1f = sd / "room_shell.json"
    if v1f.exists():
        w4 = {w["id"]: w["plane_upright_m"]
              for w in json.loads(v1f.read_text())["walls"]}
        if len(w4) == 4:
            ax.add_patch(Rectangle(
                (w4["wall_x_low"], w4["wall_z_low"]),
                w4["wall_x_high"] - w4["wall_x_low"],
                w4["wall_z_high"] - w4["wall_z_low"],
                fill=False, ec="cyan", lw=1.4, ls=":"))
    ax.set_title("8. cleanup: group + snap + merge + delete-short\n"
                 "(bold; dashed = inferred) over the raw trace (faint);\n"
                 "dotted cyan = old v1 box")

    for row in axes:
        for a2 in row:
            a2.set_xlim(ex[0], ex[1])
            a2.set_ylim(ex[2], ex[3])
    fig.suptitle(f"{scene} â€” how the wall outline is made, step by step",
                 fontsize=15)
    outp = sd / "room_shell_steps.png"
    fig.tight_layout()
    fig.savefig(outp, dpi=110)
    plt.close(fig)
    print(f"[shell-poly] steps sheet -> {outp} (sheet mode: nothing "
          f"else written)", flush=True)


def run_poly(scene, sheet=False):
    from scipy import ndimage
    sd = paths.scene_dir(scene)
    fr = paths.frame_block(scene)
    pts, r2r = load_upright_points(scene, fr)
    r2r_a = np.asarray(r2r, dtype=np.float64)
    ext_lo = np.minimum(np.array(fr["extent_p1"]) * r2r_a,
                        np.array(fr["extent_p99"]) * r2r_a) - POLY_MARGIN
    ext_hi = np.maximum(np.array(fr["extent_p1"]) * r2r_a,
                        np.array(fr["extent_p99"]) * r2r_a) + POLY_MARGIN
    pts = pts[np.all((pts >= ext_lo) & (pts <= ext_hi), axis=1)]
    floor_m, ceil_m = measure_floor_ceiling(pts)

    # wall-material ink: plan cells with dense WALL-BAND splat (points
    # between floor and ceiling margins â€” the same material the audit
    # image draws). NOT the v1 reaches-the-ceiling rule: living_marble's
    # ceiling splat is dense, which made every open-floor cell "reach
    # the ceiling" and the whole room read as solid. Furniture also
    # inks, but it forms holes INSIDE the interior â€” the outer boundary
    # walk never sees it, and the majority-plane merge absorbs a bulge
    # where furniture touches a wall.
    x, z = pts[:, 0], pts[:, 2]
    x0, z0 = float(x.min()), float(z.min())
    nx = int(np.ceil((x.max() - x0) / CELL)) + 1
    nz = int(np.ceil((z.max() - z0) / CELL)) + 1
    ci = ((x - x0) / CELL).astype(np.int32).clip(0, nx - 1)
    cz = ((z - z0) / CELL).astype(np.int32).clip(0, nz - 1)
    flat = ci * nz + cz
    # THE HEAD LINE IS A FRACTION OF THE MEASURED ROOM, not an absolute
    # (2026-08-12, the fresh05 lesson): POLY_TALL_M = 1.4 assumes a
    # metric scene, but the shell must also behave on a not-yet-
    # normalized one (fresh05 at raw 0.64x: "1.4 m" landed 0.23 below
    # its ceiling and every vertical test warped). Same cure as the
    # stitch eye (R-S2-134): 1.4-in-a-2.8-standard-room, re-expressed
    # against THIS room's measured height. Identical on metric scenes.
    head_line = floor_m + (POLY_TALL_M / 2.8) * (ceil_m - floor_m)
    in_band = ((pts[:, 1] >= floor_m + WALL_BAND_LO)
               & (pts[:, 1] <= ceil_m - WALL_BAND_HI))
    band_cnt = np.bincount(flat[in_band],
                           minlength=nx * nz).reshape(nx, nz)
    # TALL rule: the cell's band material must reach above furniture
    # height, else the sofa welds to the wall band and dents the trace
    # (first band-only run: a 2 m bite around the sofa). Walls,
    # curtains and glass doors reach; sofas, tables, chairs do not.
    band_top = np.full(nx * nz, -np.inf)
    np.maximum.at(band_top, flat[in_band], pts[in_band, 1])
    tall = (band_top >= head_line).reshape(nx, nz)
    # A BARRIER MUST OCCUPY THE WALKING ZONE (user diagnosis 2026-08-12:
    # "some drop ceiling remain and confused the open space analysis" â€”
    # measured: 65% of fresh06's solid cells, 38% of fresh09's, 19% of
    # fresh05's had their LOWEST band point above head height â€” ceiling
    # remnants and soffits hanging in the band, walling off open room).
    # Walls, wardrobes and floor-length curtains all CROSS the head
    # line; hanging material does not. Same constant, no new threshold.
    band_bot = np.full(nx * nz, np.inf)
    np.minimum.at(band_bot, flat[in_band], pts[in_band, 1])
    reaches_down = (band_bot <= head_line).reshape(nx, nz)
    solid = (band_cnt >= MIN_CELL_PTS) & tall & reaches_down
    ink = ndimage.binary_dilation(solid, iterations=2)
    st = {"grid": (x0, z0, nx, nz), "solid": solid.copy()} if sheet else None

    # interior = the free-space blob around the room centre.
    # FLOOR RULE: interior cells must stand on floor-level splat â€” the
    # room (and any walk-in pocket) has floor at floor_m; the area seen
    # THROUGH a window does not, so it can never join the interior even
    # where the wall has no floor-to-ceiling material (living_marble:
    # the band past the curtain wall out-sized the room itself and a
    # geodesic cap alone could not exclude it)
    floor_cnt = np.bincount(
        flat[np.abs(pts[:, 1] - floor_m) < 0.15],
        minlength=nx * nz).reshape(nx, nz)
    floor_ok = ndimage.binary_dilation(floor_cnt >= 3, iterations=4)
    # A ROOM IS COVERED SPACE (2026-08-12, the fresh09 leak review):
    # after the walking-zone rule dissolved hanging wall remnants, the
    # rough box's floor-free permission let exterior pockets flood in
    # through the breaches (6.6 of 7.5 added m2 were in-box exterior),
    # and exterior GROUND reads as "floor" so floor evidence cannot
    # tell a garden from a room. A ceiling can: every open cell must be
    # UNDER A ROOF â€” material near ceiling height above it, mirrored
    # from the floor test (same >= 3 pts, same 4-cell dilation).
    # Measured: fresh09 38.5 -> 29.4 m2 (exterior gone), fresh05
    # 20.3 -> 15.1 (its traced footprint is 14.9), fresh06 unaffected.
    # "roofed" = ANYTHING overhead above the head line (2026-08-12,
    # second round: the near-main-ceiling form cut the space UNDER a
    # false ceiling â€” the true ceiling is hidden above it, so the test
    # failed exactly where the user pointed. A drop ceiling IS a roof;
    # the outdoors has nothing overhead at all.)
    ceil_ok = ndimage.binary_dilation(
        np.bincount(flat[pts[:, 1] > head_line],
                    minlength=nx * nz).reshape(nx, nz) >= 3, iterations=4)
    # the floor requirement applies OUTSIDE the frame's robust box only:
    # inside it, furniture shadows the floor and would dig fake dents;
    # outside it, floor evidence is exactly what separates a walk-in
    # pocket from the view through a window
    boxm = np.zeros((nx, nz), bool)
    bx0 = int((ext_lo[0] + POLY_MARGIN - x0) / CELL)
    bz0 = int((ext_lo[2] + POLY_MARGIN - z0) / CELL)
    bx1 = int((ext_hi[0] - POLY_MARGIN - x0) / CELL)
    bz1 = int((ext_hi[2] - POLY_MARGIN - z0) / CELL)
    boxm[bx0:bx1, bz0:bz1] = True
    if st is not None:
        st["floor_ok"] = floor_ok.copy()
        st["box"] = (x0 + bx0 * CELL, z0 + bz0 * CELL,
                     x0 + bx1 * CELL, z0 + bz1 * CELL)
    # FLOOR DEFEATS THE RING (the decisive half of the user's 08-12
    # union ruling â€” measured first: relaxing only the leash changed
    # NOTHING (15.9/14.0/8.7 m2 identical), because the lost area dies
    # HERE: the dilated ring around solid cells â€” fog blobs and tall
    # furniture standing on visibly-open floor â€” was excluding room the
    # capture plainly saw. Seen floor at a spot means open room at that
    # spot; only a cell that is ITSELF solid (a wall) may override it.
    # fresh09 15.9 -> 31.0 m2, fresh05 14.0 -> 20.2, fresh06 8.7 -> 9.2.
    near_solid = ndimage.binary_dilation(solid, iterations=1)
    free = ((~near_solid & (boxm | floor_ok))
            | (floor_ok & ~solid)) & ceil_ok
    lab, _n = ndimage.label(free)
    # the room = the free component with the most area inside the
    # frame's robust box (a centre seed lands under furniture)
    bx0 = int((ext_lo[0] + POLY_MARGIN - x0) / CELL)
    bz0 = int((ext_lo[2] + POLY_MARGIN - z0) / CELL)
    bx1 = int((ext_hi[0] - POLY_MARGIN - x0) / CELL)
    bz1 = int((ext_hi[2] - POLY_MARGIN - z0) / CELL)
    inbox = np.bincount(lab[bx0:bx1, bz0:bz1].ravel(),
                        minlength=_n + 1)
    inbox[0] = 0
    interior = lab == int(np.argmax(inbox))
    if st is not None:
        st["free"] = free.copy()
        st["interior_precap"] = interior.copy()
    # REACH CAP + FLOOR-EVIDENCE UNION (user ruling 2026-08-12, from the
    # step-4 review: "a union of the floor evidence and openspace walk
    # seems to be the best"). Two-phase growth from the in-box core:
    #   phase 1 â€” the old leash: anything reachable within POLY_REACH_M
    #             stays, floor or no floor (furniture shadows the floor
    #             inside the room, so the box core must not need it);
    #   phase 2 â€” MEASURED floor is the room: growth continues without
    #             a cap, but only through floor-evidenced open cells.
    # A hallway whose floor was seen joins fully (fresh09's arm died at
    # the 3 m leash); the view through a window still cannot join â€” its
    # cells are not CONNECTED through open space (the wall/glass band is
    # solid), and a floorless leak past a wall end still hits the leash.
    boxmask = np.zeros_like(interior)
    boxmask[bx0:bx1, bz0:bz1] = True
    grown = interior & boxmask
    for _ in range(int(POLY_REACH_M / CELL)):
        grown = ndimage.binary_dilation(grown) & interior
    ext = grown
    for _ in range(nx + nz):                 # geodesic, bounded
        new = ndimage.binary_dilation(ext) & interior & (floor_ok | grown)
        if bool(np.array_equal(new, ext)):
            break
        ext = new
    interior = ext

    # TRACE: the interior's boundary as an ordered loop (Moore trace â€”
    # one closed loop by construction)
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    # keep the largest connected piece only (the cap can strand slivers)
    ilab, in_ = ndimage.label(interior)
    if in_ > 1:
        interior = ilab == int(np.argmax(np.bincount(
            ilab.ravel())[1:]) + 1)
    cells = _trace_boundary(interior)
    loop = [[x0 + c[0] * CELL, z0 + c[1] * CELL] for c in cells]
    verts = _dp_loop(loop, POLY_DP_M)
    if np.allclose(verts[0], verts[-1]):
        verts = verts[:-1]
    if st is not None:
        st["interior"] = interior.copy()
        st["loop"] = [list(p) for p in loop]

    # classify + MERGE. Each edge of the simplified loop becomes a
    # segment; cardinal snap is a merge special case (position from the
    # density spike); same-axis neighbours within POLY_MERGE_M merge.
    band = pts[(pts[:, 1] >= floor_m + WALL_BAND_LO)
               & (pts[:, 1] <= ceil_m - WALL_BAND_HI)]
    if st is not None:
        st["band"] = band

    def spike(axis_col, pos, t_lo, t_hi, t_col):
        sel = band[(np.abs(band[:, axis_col] - pos) <= 0.35)
                   & (band[:, t_col] >= t_lo) & (band[:, t_col] <= t_hi)]
        if len(sel) < 200:
            return None
        v = sel[:, axis_col]
        nb = max(8, int(0.7 / BIN_WALL))
        cnt, edges = np.histogram(v, bins=nb, range=(pos - 0.35, pos + 0.35))
        k = int(np.argmax(cnt))
        return {"position": float((edges[k] + edges[k + 1]) / 2),
                "point_count": int(cnt[k:k + 1].sum()),
                "n_band_points": int(len(sel))}

    segs = []
    nv = len(verts)
    for i in range(nv):
        p, q = np.asarray(verts[i]), np.asarray(verts[(i + 1) % nv])
        d = q - p
        L = float(np.hypot(*d))
        if L < 1e-6:
            continue
        ang = float(np.degrees(np.arctan2(d[1], d[0]))) % 180.0
        seg = {"p": p, "q": q, "len": L}
        if min(ang, 180 - ang) <= POLY_SNAP_DEG:        # runs along x
            seg["kind"] = "cardinal"; seg["axis"] = "z"  # constant-z wall
            pos = float((p[1] + q[1]) / 2)
            sp = spike(2, pos, min(p[0], q[0]), max(p[0], q[0]), 0)
            seg["position"] = sp["position"] if sp else pos
            seg["spike"] = sp
        elif abs(ang - 90) <= POLY_SNAP_DEG:            # runs along z
            seg["kind"] = "cardinal"; seg["axis"] = "x"  # constant-x wall
            pos = float((p[0] + q[0]) / 2)
            sp = spike(0, pos, min(p[1], q[1]), max(p[1], q[1]), 2)
            seg["position"] = sp["position"] if sp else pos
            seg["spike"] = sp
        else:
            seg["kind"] = "connector"; seg["angle_deg"] = round(ang, 1)
        segs.append(seg)
    merged = True
    while merged and len(segs) > 2:
        merged = False
        for i in range(len(segs)):
            a_, b_ = segs[i], segs[(i + 1) % len(segs)]
            same_card = (a_["kind"] == b_["kind"] == "cardinal"
                         and a_["axis"] == b_["axis"]
                         and abs(a_["position"] - b_["position"])
                         <= POLY_MERGE_M)
            same_conn = (a_["kind"] == b_["kind"] == "connector"
                         and abs(a_["angle_deg"] - b_["angle_deg"]) <= 8)
            if same_card or same_conn:
                w = a_["len"] + b_["len"]
                if same_card:
                    a_["position"] = (a_["position"] * a_["len"]
                                      + b_["position"] * b_["len"]) / w
                else:
                    a_["angle_deg"] = round(
                        (a_["angle_deg"] * a_["len"]
                         + b_["angle_deg"] * b_["len"]) / w, 1)
                a_["q"] = b_["q"]; a_["len"] = w
                del segs[(i + 1) % len(segs)]
                merged = True
                break

    # CLOSE: consecutive lines meet at a vertex. Different orientations
    # intersect; same-orientation neighbours get an explicit closure
    # connector. Cardinal walls never move â€” joints absorb the error.
    def line_of(s):
        if s["kind"] == "cardinal" and s["axis"] == "x":
            return ("x", s["position"])
        if s["kind"] == "cardinal":
            return ("z", s["position"])
        return ("free", (s["p"], s["q"]))

    def meet(s1, s2):
        l1, l2 = line_of(s1), line_of(s2)
        if l1[0] == "x" and l2[0] == "z":
            return np.array([l1[1], l2[1]])
        if l1[0] == "z" and l2[0] == "x":
            return np.array([l2[1], l1[1]])
        if "free" in (l1[0], l2[0]):
            fs, os_ = (s1, s2) if l1[0] == "free" else (s2, s1)
            p, q = fs["p"], fs["q"]; d = q - p
            ol = line_of(os_)
            if ol[0] == "free":
                return None
            ax_i = 0 if ol[0] == "x" else 1
            if abs(d[ax_i]) < 1e-9:
                return None
            t = (ol[1] - p[ax_i]) / d[ax_i]
            return p + t * d
        return None

    final = []
    for i, s in enumerate(segs):
        nxt = segs[(i + 1) % len(segs)]
        v = meet(s, nxt)
        joint_gap = float(np.hypot(*(nxt["p"] - s["q"])))
        if v is not None and np.hypot(*(v - s["q"])) < 1.0:
            s["q2"] = v; nxt["p2"] = v
        else:                                   # parallel / far: bridge
            s["q2"] = s.get("q2", s["q"]); nxt["p2"] = nxt["p"]
            if joint_gap > CELL:
                final.append({"kind": "closure", "p": s["q"],
                              "q": nxt["p"], "len": joint_gap})
        final.append(s)

    # measured vs inferred: how much of each segment has ink beside it
    ink_r = int(round(POLY_INK_M / CELL))
    inkd = ndimage.binary_dilation(ink, iterations=ink_r)
    out_segs = []
    for k, s in enumerate(final):
        p = np.asarray(s.get("p2", s["p"]), float)
        q = np.asarray(s.get("q2", s["q"]), float)
        L = float(np.hypot(*(q - p)))
        n = max(2, int(L / CELL))
        ts = np.linspace(0, 1, n)[:, None]
        sample = p[None, :] * (1 - ts) + q[None, :] * ts
        si = ((sample[:, 0] - x0) / CELL).astype(int).clip(0, nx - 1)
        sz = ((sample[:, 1] - z0) / CELL).astype(int).clip(0, nz - 1)
        frac = float(inkd[si, sz].mean())
        status = "measured" if frac >= POLY_MEAS_FRAC else "inferred"
        rec = {"id": f"seg_{k:02d}", "kind": s["kind"],
               "status": status,
               "traced_ink_fraction": round(frac, 2),
               "endpoints_upright": [[round(float(p[0]), 3),
                                      round(float(p[1]), 3)],
                                     [round(float(q[0]), 3),
                                      round(float(q[1]), 3)]],
               "length_m": round(L, 3)}
        if s["kind"] == "cardinal":
            rec["axis"] = s["axis"]
            rec["plane_upright_m"] = round(float(s["position"]), 3)
            rec["evidence"] = s.get("spike")
        elif s["kind"] == "connector":
            rec["angle_deg"] = s["angle_deg"]
        if rec["length_m"] < 1e-3:
            continue    # a rounded-to-zero sliver is not wall evidence
        out_segs.append(rec)

    if st is not None:
        # panel 7b: every line as a cardinal at its OWN traced plane,
        # BEFORE the group snap moves anything
        st["cards_pre"] = [
            (s["axis"], s["plane_upright_m"], s["endpoints_upright"])
            for s in out_segs if s["kind"] == "cardinal"]
        chains, cur = [], []
        for s in out_segs:
            if s["kind"] == "connector":
                cur.append(s)
            else:
                if cur:
                    chains.append(cur)
                cur = []
        if cur:
            chains.append(cur)
        st["chain_polylines"] = [
            [c[0]["endpoints_upright"][0]]
            + [x["endpoints_upright"][1] for x in c]
            for c in chains]

    # MERGE ACROSS THE LOOP (user ruling 2026-08-09b): group same-axis
    # planes, snap each group to its MAJORITY plane (weighted by traced
    # length), swallow slivers, and emit ONE CLEAN CLOSED POLYGON.
    # Square steps join parallel planes; connectors >= POLY_CONN_KEEP_M
    # keep their traced angle (seg_15's pocket ramp is real geometry).
    def ink_frac(p, q):
        p = np.asarray(p, float); q = np.asarray(q, float)
        L = float(np.hypot(*(q - p)))
        n = max(2, int(L / CELL))
        ts = np.linspace(0, 1, n)[:, None]
        sm = p[None, :] * (1 - ts) + q[None, :] * ts
        si = ((sm[:, 0] - x0) / CELL).astype(int).clip(0, nx - 1)
        sz = ((sm[:, 1] - z0) / CELL).astype(int).clip(0, nz - 1)
        return float(inkd[si, sz].mean())

    groups = {"x": [], "z": []}
    for s in out_segs:
        if s["kind"] != "cardinal":
            continue
        if s["length_m"] < 1e-3:
            continue    # a rounded-to-zero sliver is not wall evidence
        g = next((g for g in groups[s["axis"]]
                  if abs(g["pos"] - s["plane_upright_m"]) <= POLY_GROUP_M),
                 None)
        if g is None:
            g = {"pos": s["plane_upright_m"], "members": []}
            groups[s["axis"]].append(g)
        g["members"].append(s)
        tot = sum(m["length_m"] for m in g["members"])
        if tot > 1e-9:      # zero-length members must not poison the mean
            g["pos"] = (sum(m["plane_upright_m"] * m["length_m"]
                            for m in g["members"]) / tot)
    group_recs = []
    for ax_name in ("x", "z"):
        for g in groups[ax_name]:
            mem = sorted(g["members"], key=lambda s: s["plane_upright_m"])
            clusters = []
            for s in mem:
                p, L = s["plane_upright_m"], s["length_m"]
                if clusters and p - clusters[-1]["hi"] <= POLY_MAJ_M:
                    c = clusters[-1]
                    c["hi"] = p; c["wsum"] += p * L; c["len"] += L
                else:
                    clusters.append({"hi": p, "wsum": p * L, "len": L})
            best = max(clusters, key=lambda c: c["len"])
            g["plane"] = best["wsum"] / best["len"]
            for s in g["members"]:
                s["group_plane"] = g["plane"]
            group_recs.append(
                {"axis": ax_name,
                 "majority_plane_upright_m": round(g["plane"], 3),
                 "members": [s["id"] for s in mem],
                 "member_planes": [s["plane_upright_m"] for s in mem],
                 "majority_length_m": round(best["len"], 2)})

    group_len = {}
    for s in out_segs:
        if s["kind"] == "cardinal":
            key = (s["axis"], s["group_plane"])
            group_len[key] = group_len.get(key, 0.0) + s["length_m"]
    for g, rec in zip(groups["x"] + groups["z"], group_recs):
        tot = group_len.get((rec["axis"], g["plane"]), 0.0)
        rec["total_length_m"] = round(tot, 2)
        rec["is_wall"] = tot >= POLY_WALL_MIN_M

    seq = []
    for s in out_segs:
        if (s["kind"] == "cardinal"
                and group_len[(s["axis"], s["group_plane"])]
                < POLY_WALL_MIN_M):
            continue                    # furniture face, not a wall
        e = {"kind": "cardinal" if s["kind"] == "cardinal" else "connector",
             "len": s["length_m"],
             "p": s["endpoints_upright"][0], "q": s["endpoints_upright"][1]}
        if s["kind"] == "cardinal":
            e["axis"] = s["axis"]; e["plane"] = s["group_plane"]
        seq.append(e)

    def merge_seq(seq):
        out = []
        for e in seq:
            if (out and e["kind"] == out[-1]["kind"] == "cardinal"
                    and e["axis"] == out[-1]["axis"]
                    and abs(e["plane"] - out[-1]["plane"]) < 1e-9):
                out[-1]["q"] = e["q"]; out[-1]["len"] += e["len"]
            else:
                out.append(dict(e))
        if (len(out) > 1 and out[0]["kind"] == out[-1]["kind"] == "cardinal"
                and out[0]["axis"] == out[-1]["axis"]
                and abs(out[0]["plane"] - out[-1]["plane"]) < 1e-9):
            out[0]["p"] = out[-1]["p"]; out[0]["len"] += out[-1]["len"]
            out.pop()
        return out

    seq = merge_seq(seq)

    # RECTILINEARIZE THE CHAINS (user ruling 2026-08-12, superseding the
    # 08-09 delete-or-flatten pair: "make each full orange line one poly
    # line and then approximate it with cardinal lines"). An angled run
    # is neither dropped nor collapsed to a diagonal: its FULL polyline
    # becomes a staircase of axis-aligned legs â€” each maximal run of
    # same-dominant-axis edges is one cardinal at the length-weighted
    # mean plane. The corner/step joint machinery below already knows
    # how to join alternating cardinals; micro-legs die at the existing
    # POLY_MIN_SEG_M bar right after. POLY_CONN_KEEP_M and the 2 m chain
    # bar are retired by this ruling (no connectors survive to need
    # them); connector handling in consumers stays for old shells.
    def rectilinearize(chain):
        verts = [np.asarray(chain[0]["p"], float)]
        for e in chain:
            verts.append(np.asarray(e["q"], float))
        return _rectilinearize_verts(verts)

    while seq and seq[0]["kind"] == "connector":     # chains must not
        seq.append(seq.pop(0))                       # wrap the list end
    i = 0
    while i < len(seq):
        if seq[i]["kind"] != "connector":
            i += 1
            continue
        j = i
        while j < len(seq) and seq[j]["kind"] == "connector":
            j += 1
        legs = rectilinearize(seq[i:j])
        seq[i:j] = legs
        i += max(1, len(legs))
    seq = merge_seq(seq)

    changed = True
    while changed and len(seq) > 3:
        changed = False
        for i, e in enumerate(seq):
            need = (POLY_CONN_KEEP_M if e["kind"] == "connector"
                    else POLY_MIN_SEG_M)
            if e["len"] < need:
                del seq[i]
                seq = merge_seq(seq)
                changed = True
                break

    def isect(p, q, axis, pos):
        p = np.asarray(p, float); d = np.asarray(q, float) - p
        i = 0 if axis == "x" else 1
        if abs(d[i]) < 1e-9:
            return [float(p[0]), float(p[1])]
        t = (pos - p[i]) / d[i]
        v = p + t * d
        return [float(v[0]), float(v[1])]

    m = len(seq)
    joints = []                 # joints[i]: 1 or 2 points between i, i+1
    for i in range(m):
        e, f = seq[i], seq[(i + 1) % m]
        if e["kind"] == f["kind"] == "cardinal":
            if e["axis"] != f["axis"]:
                xp = e["plane"] if e["axis"] == "x" else f["plane"]
                zp = e["plane"] if e["axis"] == "z" else f["plane"]
                joints.append([[xp, zp]])
            else:                       # parallel planes: square step
                tc = 1 if e["axis"] == "x" else 0
                t = (e["q"][tc] + f["p"][tc]) / 2
                if e["axis"] == "x":
                    joints.append([[e["plane"], t], [f["plane"], t]])
                else:
                    joints.append([[t, e["plane"]], [t, f["plane"]]])
        elif e["kind"] == "connector" and f["kind"] == "cardinal":
            joints.append([isect(e["p"], e["q"], f["axis"], f["plane"])])
        elif e["kind"] == "cardinal" and f["kind"] == "connector":
            joints.append([isect(f["p"], f["q"], e["axis"], e["plane"])])
        else:
            joints.append([list(map(float, f["p"]))])

    clean_segs = []
    verts_clean = []
    for i in range(m):
        e = seq[i]
        start = joints[i - 1][-1]
        end = joints[i][0]
        if np.hypot(end[0] - start[0], end[1] - start[1]) < 0.02:
            continue                        # joint re-anchoring ate it
        frac = ink_frac(start, end)
        rec = {"id": f"wall_{i:02d}", "kind": e["kind"],
               "status": ("measured" if frac >= POLY_MEAS_FRAC
                          else "inferred"),
               "traced_ink_fraction": round(frac, 2),
               "endpoints_upright": [[round(start[0], 3), round(start[1], 3)],
                                     [round(end[0], 3), round(end[1], 3)]],
               "length_m": round(float(np.hypot(end[0] - start[0],
                                                end[1] - start[1])), 3)}
        if e["kind"] == "cardinal":
            rec["axis"] = e["axis"]
            rec["plane_upright_m"] = round(e["plane"], 3)
        clean_segs.append(rec)
        verts_clean.append([round(start[0], 3), round(start[1], 3)])
        if len(joints[i]) == 2:         # the square step is a segment too
            a, b = joints[i]
            frac = ink_frac(a, b)
            step_ax = "z" if e["axis"] == "x" else "x"
            clean_segs.append(
                {"id": f"wall_{i:02d}s", "kind": "step",
                 "status": ("measured" if frac >= POLY_MEAS_FRAC
                            else "inferred"),
                 "traced_ink_fraction": round(frac, 2),
                 "axis": step_ax,
                 "plane_upright_m": round(a[1] if step_ax == "z"
                                          else a[0], 3),
                 "endpoints_upright": [[round(a[0], 3), round(a[1], 3)],
                                       [round(b[0], 3), round(b[1], 3)]],
                 "length_m": round(float(np.hypot(b[0] - a[0],
                                                  b[1] - a[1])), 3)})
            verts_clean.append([round(a[0], 3), round(a[1], 3)])

    if sheet:
        # sheet mode is strictly read-only on scene state: render the
        # step panels and stop before ANY of the writes below
        _render_steps(sd, scene, st, out_segs, clean_segs)
        return

    # overlay for review: raw trace faint, clean polygon bold
    fig, ax = plt.subplots(figsize=(9, 9))
    H, xe, ze = np.histogram2d(band[:, 0], band[:, 2],
                               bins=[int((ext_hi[0] - ext_lo[0]) / 0.02),
                                     int((ext_hi[2] - ext_lo[2]) / 0.02)],
                               range=[[ext_lo[0], ext_hi[0]],
                                      [ext_lo[2], ext_hi[2]]])
    ax.imshow(np.log1p(H.T), origin="lower", cmap="gray_r",
              extent=[xe[0], xe[-1], ze[0], ze[-1]], aspect="equal")
    v1 = sd / "room_shell.json"
    if v1.exists():
        w4 = {w["id"]: w["plane_upright_m"]
              for w in json.loads(v1.read_text())["walls"]}
        if len(w4) == 4:
            from matplotlib.patches import Rectangle
            ax.add_patch(Rectangle(
                (w4["wall_x_low"], w4["wall_z_low"]),
                w4["wall_x_high"] - w4["wall_x_low"],
                w4["wall_z_high"] - w4["wall_z_low"],
                fill=False, ec="cyan", lw=1.2, ls=":",
                label="v1 4-wall shell"))
    for s in out_segs:                       # raw trace, faint
        (px, pz), (qx, qz) = s["endpoints_upright"]
        ax.plot([px, qx], [pz, qz], "-", color="#b8b8d8", lw=1.0)
    colors = {"cardinal": "#1db954", "connector": "#ff9f1c",
              "step": "#9b5de5"}
    seen = set()
    for s in clean_segs:
        (px, pz), (qx, qz) = s["endpoints_upright"]
        ls = "-" if s["status"] == "measured" else "--"
        ax.plot([px, qx], [pz, qz], ls, color=colors[s["kind"]],
                lw=3.0, label=(f"{s['kind']} (dashed = inferred)"
                               if s["kind"] not in seen else None))
        seen.add(s["kind"])
        ax.annotate(s["id"].replace("wall_", ""),
                    ((px + qx) / 2, (pz + qz) / 2), color="#333",
                    fontsize=8, ha="center")
    ax.legend(loc="upper right", fontsize=8)
    ax.set_title(f"{scene} â€” W4 clean polygon over the raw trace "
                 f"(review artifact; nothing consumes this)")
    png = sd / "room_shell_poly.png"
    fig.tight_layout(); fig.savefig(png, dpi=130); plt.close(fig)

    rep = {"scene": scene,
           "generated_by": "room_shell.py --poly (W4 â€” TRACE->CLOSE->MERGE,"
                           " review artifact, no consumers)",
           "frame": {"raw_to_render": list(map(float, r2r))},
           "floor_upright_m": round(floor_m, 3),
           "ceiling_upright_m": round(ceil_m, 3),
           "params": {"cell_m": CELL, "margin_m": POLY_MARGIN,
                      "dp_tol_m": POLY_DP_M, "snap_deg": POLY_SNAP_DEG,
                      "merge_m": POLY_MERGE_M, "ink_m": POLY_INK_M,
                      "measured_min_frac": POLY_MEAS_FRAC,
                      "group_m": POLY_GROUP_M, "majority_m": POLY_MAJ_M,
                      "min_seg_m": POLY_MIN_SEG_M,
                      "conn_keep_m": POLY_CONN_KEEP_M},
           "wall_groups": group_recs,
           "clean_polygon": {"vertices_upright": verts_clean,
                             "segments": clean_segs},
           "raw_trace_segments": out_segs}
    outf = sd / "room_shell_poly.json"
    outf.write_text(json.dumps(rep, indent=1))
    fold_polygon_into_shell(sd, rep)
    n_meas = sum(1 for s in clean_segs if s["status"] == "measured")
    print(f"[shell-poly] raw trace {len(out_segs)} segments -> "
          f"{len(group_recs)} wall groups -> clean polygon "
          f"{len(clean_segs)} segments "
          f"({n_meas} measured / {len(clean_segs) - n_meas} inferred):",
          flush=True)
    for s in clean_segs:
        print(f"  {s['id']:9s} {s['kind']:9s} "
              + (f"{s['axis']}={s['plane_upright_m']:+7.3f}  "
                 if s.get("axis") else " " * 12)
              + f"len {s['length_m']:6.3f} m  {s['status']}"
              f"  ink {s['traced_ink_fraction']}", flush=True)
    print(f"[shell-poly] wrote {outf}")
    print(f"[shell-poly] overlay: {png}")


def fold_polygon_into_shell(sd, rep):
    """W5 (D3 ruling 2026-08-09): ONE shell contract file. The clean
    polygon is folded into room_shell.json as a "polygon" block â€”
    consumers read the contract, never the review artifact. Everything
    is precomputed here in BOTH frames (upright and raw) so consumers
    that live in the raw frame (slicevote) do no geometry derivation of
    their own: per cardinal/step segment the raw plane + which side of
    it is room interior; per connector the inward unit normal. No
    room_shell.json on disk -> nothing to fold (v1 must run first)."""
    shell_f = sd / "room_shell.json"
    if not shell_f.exists():
        print("[shell-poly] no room_shell.json â€” polygon block NOT "
              "folded (run the default v1 mode first)", flush=True)
        return
    # ACCEPTANCE (2026-08-12, R-S2-133): a trace that "succeeds"
    # numerically can still be geometric nonsense â€” fresh06 produced 3
    # segments, two of them 70 m, ONE cardinal wall per axis, and folded
    # it silently; the first reader that counts planes (arch_walls,
    # >= 2 per axis) crashed 26 stages later in compose. A closed
    # box-ish room always yields >= 2 axis-bearing walls per axis, so a
    # polygon that cannot is a FAILED FIT: raising here routes it into
    # main()'s existing degrade path (v1 4-plane shell + polygon_error
    # recorded). Structural test only â€” no length threshold invented.
    n_x = sum(1 for s in rep["clean_polygon"]["segments"]
              if s.get("axis") == "x")
    n_z = sum(1 for s in rep["clean_polygon"]["segments"]
              if s.get("axis") == "z")
    if n_x < 2 or n_z < 2:
        raise ValueError(
            f"clean polygon carries {n_x} x-wall / {n_z} z-wall "
            f"segments â€” a closed room needs >= 2 per axis; refusing "
            f"to fold a degenerate fit (arch_walls.wall_axis_planes "
            f"enforces the same bound downstream)")
    from matplotlib.path import Path as MplPath
    r2r = rep["frame"]["raw_to_render"]
    verts_up = rep["clean_polygon"]["vertices_upright"]
    verts_raw = [[round(x * r2r[0], 3), round(z * r2r[2], 3)]
                 for x, z in verts_up]
    poly_raw = MplPath(np.asarray(verts_raw, float))

    def inside_raw(x, z):
        return bool(poly_raw.contains_point((x, z)))

    segs = []
    for s in rep["clean_polygon"]["segments"]:
        (px, pz), (qx, qz) = s["endpoints_upright"]
        p_raw = [round(px * r2r[0], 3), round(pz * r2r[2], 3)]
        q_raw = [round(qx * r2r[0], 3), round(qz * r2r[2], 3)]
        rec = dict(s, endpoints_raw=[p_raw, q_raw])
        mx, mz = (p_raw[0] + q_raw[0]) / 2, (p_raw[1] + q_raw[1]) / 2
        if s["kind"] in ("cardinal", "step"):
            comp = 0 if s["axis"] == "x" else 2
            plane_raw = round(s["plane_upright_m"] * r2r[comp], 3)
            rec["plane_raw_m"] = plane_raw
            # WALLS-table convention: +1 = interior lies BELOW the plane
            eps = 0.05
            probe = (mx - eps, mz) if s["axis"] == "x" else (mx, mz - eps)
            rec["interior_side_raw"] = 1 if inside_raw(*probe) else -1
        else:                                            # connector
            d = np.array([q_raw[0] - p_raw[0], q_raw[1] - p_raw[1]])
            n = np.array([-d[1], d[0]])
            n = n / np.linalg.norm(n)
            if not inside_raw(mx + 0.05 * n[0], mz + 0.05 * n[1]):
                n = -n
            rec["inward_normal_raw"] = [round(float(n[0]), 4),
                                        round(float(n[1]), 4)]
            rec["plane_offset_raw"] = round(
                float(n[0] * p_raw[0] + n[1] * p_raw[1]), 4)
        segs.append(rec)

    shell = json.loads(shell_f.read_text())
    shell["polygon"] = {
        "generated_by": "room_shell.py --poly (W4 recipe: trace -> "
                        "close -> merge; folded by W5/D3)",
        "params": rep["params"],
        "vertices_upright": verts_up,
        "vertices_raw": verts_raw,
        "segments": segs,
        "note": ("raw = upright * frame.raw_to_render componentwise "
                 "(x,z components); interior_side_raw follows the "
                 "WALLS convention (+1 = room interior below the "
                 "plane value); connector inward_normal_raw points "
                 "into the room, plane_offset_raw = n . p"),
    }
    shell_f.write_text(json.dumps(shell, indent=1))
    print(f"[shell-poly] polygon block ({len(segs)} segments) folded "
          f"into {shell_f}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--poly", action="store_true",
                    help="W4 trace->close->merge review artifacts")
    ap.add_argument("--steps-sheet", action="store_true",
                    help="render room_shell_steps.png â€” every trace "
                         "stage as its own panel; writes NOTHING else")
    a = ap.parse_args()
    if a.steps_sheet:
        run_poly(a.scene, sheet=True)
        return
    if a.poly:
        run_poly(a.scene)
        return
    if not a.audit:
        sd = paths.scene_dir(a.scene)
        fr = paths.frame_block(a.scene)
        pts, r2r = load_upright_points(a.scene, fr)
        shell = fit_shell(a.scene, fr, pts, r2r)
        sy = r2r[1]
        out = {
            "scene": a.scene,
            "generated_by": "room_shell.py (W1 â€” PLAN_ROOM_SHELL.md)",
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
                  f"{'agree d=' + str(cb['delta_m']) if cb else 'â€”'}  "
                  f"parallels {len(w['parallel_surfaces'])}")
        # W5 AUTOMATION RULE (2026-08-09): the default mode produces the
        # COMPLETE contract in one command â€” the polygon fit runs here,
        # unconditionally, so an unattended per-scene run can never end
        # up with a v1-only shell by ordering accident. If the fit fails
        # on a scene, the shell DEGRADES to the 4-plane v1 behaviour
        # (consumers take the POLY-is-None path) and the failure is
        # recorded in the contract file itself â€” never a silent skip.
        try:
            run_poly(a.scene)
        except Exception as e:                               # noqa: BLE001
            print(f"[shell] polygon fit FAILED ({e}) â€” shell stays v1 "
                  "4-plane (degraded; recorded in room_shell.json)",
                  flush=True)
            cur = json.loads(f.read_text())
            cur.pop("polygon", None)
            cur["polygon_error"] = str(e)
            f.write_text(json.dumps(cur, indent=1))
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
    axes[0].set_title("wall-band occupancy (log) Â· cyan = p1/p99 placeholder")
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
        ax.set_title(f"density along {axname} Â· cyan placeholder / red peak")
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

