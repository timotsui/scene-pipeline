"""SUB ROUNDS — CP7: HOST-AWARE WALK-DOWNS + CROSS-LEVEL PHYSICS
(experiment, one anchor — the obj_022 cross-level-clipping ask).

v2 (user: "this is not jiggling with the host object itself"): the
host mesh joins the physics. Until now subs saw only their board
RECTANGLE — the host's vertical dividers, side panels, back panel
and closed DOORS were invisible (v1's re-triage spilled baskets into
obj_022's closed-door compartment). Now:

  FREE SPACE  per standing board, host-mesh occupancy is measured on
              fit_check's 2 cm voxel lattice between the board and
              its ceiling -> free INTERVALS along the board's long
              axis. A divider splits a board into two intervals; a
              doored compartment has none (ENCLOSED).
  PSEUDO-BOARDS  each free interval becomes a board for SR9/SR8:
              triage capacity = free length, spill targets = real
              open space only, enclosed boards evict their squatters,
              the jiggle sweep runs inside intervals.
  HOST CLIPS  item-AABB vs host-voxel overlap counted before/after
              (> 4 cells = clip, fit_check's contact rule).

Carried from v1:
  1. cross-level accounting (cp6 counted same-board pairs only) +
     per-item CEILING PROTRUSION (item top vs next surface above);
  2. plank UNDERSIDES admitted as boards by flipped normals (sparse
     small-area board 44-48 mm below a full one) are detected, kept
     as compartment CEILINGS, their squatters re-seated up;
  3. WALK: a too-tall item trial-places its recorded cp4 runners
     (native size, align trick, same k) and takes the first that
     fits under the ceiling; none fit -> TOO_TALL_DRY, kept, the
     library-gap complaint.

Order: re-seat -> walk -> interval assignment -> SR9 triage ->
SR8 jiggle -> report.  Reads <anchor>/cp6 + cp4_aligned + cp2 + cp3.
Writes <anchor>/cp7/ — placements_walked.json, subs_walked.glb,
front.png, index.html (USER GATE).

  python sub_round_cp7.py [--scene bedroom_marble] [--anchor obj_022]
"""
import argparse
import html
import json
import sys
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).parent
EG = HERE.parent
sys.path.insert(0, str(EG))
sys.path.insert(0, str(EG / "compose"))
sys.path.insert(0, str(HERE))

import paths                                     # noqa: E402
sys.path.insert(0, str(paths.REPO_ROOT / "composition"))
import fit_preview as fpv                        # noqa: E402
from assets_thor import load_asset               # noqa: E402
from sub_round_cp5 import align_upright          # noqa: E402
import sub_round_cp6 as cp6                      # noqa: E402

RES = 1024
SLACK = 0.005       # m; required clearance below the ceiling
PLANK_MAX = 0.06    # m; max top-to-underside gap read as one plank
PHANTOM_AREA_FRAC = 0.3   # underside face area << the top face's
PITCH = 0.02        # m; fit_check's clip lattice
CONTACT_CELLS = 4   # fit_check: overlap cells <= this = contact
Y_PAD = 0.03        # m; skip plank-underside cells at the ceiling
Y_BLOCK_MIN = 0.10  # m; host cells below this height over the board
                    # are surface RELIEF (mattress folds, lips), not
                    # obstacles — the obj_008 pillow-vs-duvet lesson
MIN_RUN = 0.06      # m; shortest usable free interval
CURTAIN = (0.03, 0.08)   # m; access probe inward/outward of the edge
COVER_ENCLOSED = 0.6     # front-face coverage above this = doors


# ---------------------------------------------------------------- boards
def classify_boards(boards):
    """-> (standing_boards, phantom_of, ceiling_y_of_board).

    A board P is the UNDERSIDE of the plank whose top is board R when
    R sits 0..PLANK_MAX above P with much larger face area (flipped
    normals let the bottom face through the up-facing filter). P is
    not a standing surface; it IS the ceiling of the compartment
    below R."""
    phantom_of = {}
    for p in boards:
        for r in boards:
            if (0.0 < r["y"] - p["y"] <= PLANK_MAX
                    and p["area_m2"] < PHANTOM_AREA_FRAC * r["area_m2"]):
                phantom_of[p["board"]] = r["board"]
                break
    standing = [b for b in boards if b["board"] not in phantom_of]
    ceiling = {}
    for b in standing:
        above = [c["y"] for c in boards if c["y"] > b["y"] + 1e-6]
        ceiling[b["board"]] = min(above) if above else None
    return standing, phantom_of, ceiling


def headroom_of(b, ceiling):
    c = ceiling.get(b["board"])
    return None if c is None else c - b["y"]


# ------------------------------------------------------- host free space
def host_points(anchor_meshes):
    """Surface-voxel cell centers of the host on the 2 cm lattice
    (fit_check's cell_keys idiom, coordinates kept)."""
    pts = []
    for m in anchor_meshes:
        vg = m.voxelized(pitch=PITCH)
        pts.append(np.asarray(vg.points, np.float64))
    return np.vstack(pts)


def free_intervals(b, ceil_y, hpts):
    """-> list of [lo, hi] free runs along the board's long axis.

    A 2 cm bin is BLOCKED when any host voxel sits over the board's
    footprint in that bin between board+Y_PAD and ceiling-Y_PAD (the
    pads exclude the board's own surface cells and the plank above).
    No ceiling (top board) probes a 0.5 m band instead."""
    ax = 0 if (b["x"][1] - b["x"][0]) >= (b["z"][1] - b["z"][0]) else 2
    key, key2 = ("x", "z") if ax == 0 else ("z", "x")
    ax2 = 2 if ax == 0 else 0
    lo_e, hi_e = b[key][0] + cp6.INSET, b[key][1] - cp6.INSET
    y_top = (ceil_y - Y_PAD) if ceil_y is not None else b["y"] + 0.5
    sel = hpts[(hpts[:, 1] > b["y"] + Y_BLOCK_MIN) & (hpts[:, 1] < y_top)
               & (hpts[:, ax2] > b[key2][0]) & (hpts[:, ax2] < b[key2][1])
               & (hpts[:, ax] >= lo_e) & (hpts[:, ax] <= hi_e)]
    nbin = max(1, int(np.ceil((hi_e - lo_e) / PITCH)))
    blocked = np.zeros(nbin, bool)
    if len(sel):
        bi = np.clip(((sel[:, ax] - lo_e) / PITCH).astype(int), 0,
                     nbin - 1)
        blocked[bi] = True
    runs, start = [], None
    for i in range(nbin + 1):
        free = i < nbin and not blocked[i]
        if free and start is None:
            start = i
        elif not free and start is not None:
            lo, hi = lo_e + start * PITCH, lo_e + i * PITCH
            if hi - lo >= MIN_RUN:
                runs.append([round(lo, 3), round(min(hi, hi_e), 3)])
            start = None
    return ax, runs


def front_coverage(b, ceil_y, hpts, fdir):
    """ACCESS test (the closed-door lesson: the door panel sits just
    OUTSIDE the board's upward-face footprint, invisible to the
    column probe). Fraction of the compartment's FRONT face — a
    voxel curtain at the rect edge facing the host's front — covered
    by host geometry. ~1.0 = doors; ~0.0 = open shelf."""
    ax = 0 if (b["x"][1] - b["x"][0]) >= (b["z"][1] - b["z"][0]) else 2
    key, key2 = ("x", "z") if ax == 0 else ("z", "x")
    ax2 = 2 if ax == 0 else 0
    lo_e, hi_e = b[key][0] + cp6.INSET, b[key][1] - cp6.INSET
    y_top = (ceil_y - Y_PAD) if ceil_y is not None else b["y"] + 0.5
    f = fdir[0] if ax2 == 0 else fdir[1]
    edge = b[key2][1] if f > 0 else b[key2][0]
    s_lo = edge - (CURTAIN[0] if f > 0 else CURTAIN[1])
    s_hi = edge + (CURTAIN[1] if f > 0 else CURTAIN[0])
    sel = hpts[(hpts[:, 1] > b["y"] + Y_BLOCK_MIN) & (hpts[:, 1] < y_top)
               & (hpts[:, ax2] >= s_lo) & (hpts[:, ax2] <= s_hi)
               & (hpts[:, ax] >= lo_e) & (hpts[:, ax] <= hi_e)]
    nbin = max(1, int(np.ceil((hi_e - lo_e) / PITCH)))
    covered = np.zeros(nbin, bool)
    if len(sel):
        bi = np.clip(((sel[:, ax] - lo_e) / PITCH).astype(int), 0,
                     nbin - 1)
        covered[bi] = True
    return float(covered.mean())


def pseudo_boards(standing, ceiling, hpts, fdir):
    """-> (pseudo list for SR9/SR8, per-board interval record).

    Pseudo id = board*100 + interval index; rect = the interval along
    the long axis, full board depth across. An enclosed board (no
    free run, or front face covered by doors per the access test)
    contributes a single DEGENERATE pseudo (zero span): triage can
    never fit anything there, so its squatters are evicted and it is
    never a spill target."""
    plist, recs = [], []
    for b in standing:
        ax, runs = free_intervals(b, ceiling.get(b["board"]), hpts)
        cover = front_coverage(b, ceiling.get(b["board"]), hpts, fdir)
        if cover > COVER_ENCLOSED:
            runs = []
        key = "x" if ax == 0 else "z"
        span = b[key][1] - b[key][0] - 2 * cp6.INSET
        recs.append({"board": b["board"], "long_axis": key,
                     "free": runs, "enclosed": not runs,
                     "front_cover": round(cover, 2),
                     "free_frac": round(sum(r[1] - r[0]
                                            for r in runs) / span, 2)})
        if not runs:
            pb = dict(b)
            pb["board"] = b["board"] * 100
            pb[key] = [b[key][0], b[key][0]]        # zero usable span
            pb["force_ax"] = ax
            plist.append(pb)
            continue
        for i, (rlo, rhi) in enumerate(runs):
            pb = dict(b)
            pb["board"] = b["board"] * 100 + i
            pb[key] = [rlo, rhi]
            pb["force_ax"] = ax     # a short interval must NOT flip
            plist.append(pb)        # its long axis to the board depth
    return plist, recs


def _ax_of(b):
    """Long axis of a (pseudo-)board — pinned by force_ax when set
    (an interval shorter than the board depth would otherwise read
    the DEPTH as its long axis: the obj_030 wrong-interval bug)."""
    if "force_ax" in b:
        return b["force_ax"]
    return 0 if (b["x"][1] - b["x"][0]) >= (b["z"][1] - b["z"][0]) else 2


def assign_pseudo(items, plist):
    """Each item joins the interval of ITS board containing (or
    nearest to) its long-axis center."""
    by_real = {}
    for pb in plist:
        by_real.setdefault(pb["board"] // 100, []).append(pb)
    for it in items:
        cands = by_real.get(it["board"])
        if not cands:
            continue
        ax = _ax_of(cands[0])
        key = "x" if ax == 0 else "z"
        c = it["c"][ax]

        def dist(pb):
            lo, hi = pb[key]
            return 0.0 if lo <= c <= hi else min(abs(c - lo),
                                                 abs(c - hi))
        it["board"] = min(cands, key=dist)["board"]


# ---- SR9 triage + SR8 jiggle, force_ax-aware (donor: sub_round_cp6;
# only the long-axis reads changed — cp6's versions recompute the
# axis from the rect, which flips on short intervals)
def triage_fa(items, boards, asg):
    brect = {b["board"]: b for b in boards}

    def usable(b):
        k = "x" if _ax_of(b) == 0 else "z"
        return (b[k][1] - b[k][0]) - 2 * cp6.INSET

    def demand(group, ax):
        return (sum(g["sz"][ax] for g in group)
                + cp6.GAP * max(0, len(group) - 1))

    obs_h = {r["id"]: r.get("seed_bottom_y") for r in asg}
    spills, kills = [], []
    by_board = {}
    for it in items:
        by_board.setdefault(it["board"], []).append(it)

    tile_drops = []
    for bid in sorted(by_board, key=lambda b: -len(by_board[b])):
        b = brect[bid]
        ax = _ax_of(b)
        group = by_board[bid]
        while demand(group, ax) > usable(b):
            rows_k = [g for g in group
                      if g["k"] - g["tiles_dropped"] > 1
                      and g["tile_axis"] == ax]
            if not rows_k:
                break
            g = max(rows_k, key=lambda g: g["sz"][ax]
                    / (g["k"] - g["tiles_dropped"]))
            step = g["sz"][ax] / (g["k"] - g["tiles_dropped"])
            g["tiles_dropped"] += 1
            g["sz"][ax] -= step
            g["hi"][ax] -= step
            g["c"][ax] -= step / 2
            tile_drops.append({"id": g["id"], "board": bid,
                               "freed_m": round(float(step), 3)})
        while group and demand(group, ax) > usable(b):
            movable = [g for g in group if not g["exempt"]]
            if not movable:
                break
            ev = max(movable,
                     key=lambda g: abs((obs_h.get(g["id"]) or b["y"])
                                       - b["y"]))
            group.remove(ev)
            tgt = None
            for cb in sorted(boards,
                             key=lambda c: abs(c["y"] - (obs_h.get(
                                 ev["id"]) or c["y"]))):
                if cb["board"] == bid:
                    continue
                cg = by_board.setdefault(cb["board"], [])
                axc = _ax_of(cb)
                if (demand(cg + [ev], axc) <= usable(cb)
                        and ev["sz"][0] <= (cb["x"][1] - cb["x"][0])
                        and ev["sz"][2] <= (cb["z"][1] - cb["z"][0])):
                    tgt = cb
                    break
            if tgt is None:
                kills.append({"id": ev["id"], "from_board": bid,
                              "why": "no board has room"})
                ev["killed"] = True
                continue
            dy = tgt["y"] - ev["lo"][1]
            cp6._shift(ev, 1, dy)
            for axi, key in ((0, "x"), (2, "z")):
                half = ev["sz"][axi] / 2
                lo_e, hi_e = (tgt[key][0] + cp6.INSET,
                              tgt[key][1] - cp6.INSET)
                if hi_e - lo_e < ev["sz"][axi]:
                    continue
                dv = float(np.clip(ev["c"][axi], lo_e + half,
                                   hi_e - half) - ev["c"][axi])
                cp6._shift(ev, axi, cp6.q(dv))
            ev["board"] = tgt["board"]
            by_board[tgt["board"]].append(ev)
            spills.append({"id": ev["id"], "from_board": bid,
                           "to_board": tgt["board"],
                           "dy_m": round(float(dy), 3)})
    items[:] = [g for g in items if not g.get("killed")]
    return tile_drops, spills, kills


def jiggle_fa(items, boards):
    brect = {b["board"]: b for b in boards}
    over_capacity = []
    done = 0
    by_board = {}
    for it in items:
        by_board.setdefault(it["board"], []).append(it)

    for bid, group in by_board.items():
        b = brect[bid]
        ax = _ax_of(b)
        key = "x" if ax == 0 else "z"
        lo_e, hi_e = b[key][0] + cp6.INSET, b[key][1] - cp6.INSET
        need = sum(g["sz"][ax] for g in group) \
            + cp6.GAP * max(0, len(group) - 1)
        if need > (hi_e - lo_e):
            over_capacity.append({"board": bid,
                                  "need_m": round(float(need), 3),
                                  "span_m": round(float(hi_e - lo_e),
                                                  3),
                                  "items": [g["id"] for g in group]})
            continue
        group.sort(key=lambda g: g["c"][ax])
        prev_end = lo_e
        for g in group:
            half = g["sz"][ax] / 2
            tgt = max(g["c"][ax], prev_end + half)
            cp6._move(g, ax, cp6.q(tgt - g["c"][ax]))
            prev_end = g["c"][ax] + half + cp6.GAP
        next_start = hi_e
        for g in reversed(group):
            half = g["sz"][ax] / 2
            tgt = min(g["c"][ax], next_start - half)
            cp6._move(g, ax, cp6.q(tgt - g["c"][ax]))
            next_start = g["c"][ax] - half - cp6.GAP
        ax2 = 2 if ax == 0 else 0
        key2 = "x" if ax2 == 0 else "z"
        lo2, hi2 = b[key2][0] + cp6.INSET, b[key2][1] - cp6.INSET
        for g in group:
            half = g["sz"][ax2] / 2
            if hi2 - lo2 < g["sz"][ax2]:
                continue
            tgt = np.clip(g["c"][ax2], lo2 + half, hi2 - half)
            cp6._move(g, ax2, cp6.q(tgt - g["c"][ax2]))
        done += 1
    return done, over_capacity


# ------------------------------------------------------------- reporting
def cross_report(items, boards, ceiling):
    """All-pairs overlaps (any board) + per-item ceiling protrusion."""
    by = {b["board"]: b for b in boards}
    pairs = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            o = np.minimum(a["hi"], b["hi"]) - np.maximum(a["lo"], b["lo"])
            if (o > 0).all():
                pairs.append({"a": a["id"], "b": b["id"],
                              "boards": [a["board"], b["board"]],
                              "cross_level": a["board"] != b["board"],
                              "overlap_m": o.round(3).tolist()})
    prot = []
    for it in items:
        c = ceiling.get(it["board"])
        if c is None or it["board"] not in by:
            continue
        over = float(it["hi"][1] - c)
        if over > 1e-4:
            prot.append({"id": it["id"], "board": it["board"],
                         "through_ceiling_m": round(over, 3),
                         "height_m": round(float(it["sz"][1]), 3),
                         "headroom_m": round(c - by[it["board"]]["y"], 3)})
    return pairs, prot


def host_clips(items, hpts):
    """Items whose AABB swallows host voxels beyond contact (> 4
    cells, fit_check's rule). The AABB is shaved half a pitch on the
    sides and a full pitch at the bottom so standing-on-the-board and
    flush-against-a-panel read as contact, not clip."""
    out = []
    for it in items:
        lo, hi = it["lo"], it["hi"]
        m = ((hpts[:, 0] > lo[0] + PITCH / 2)
             & (hpts[:, 0] < hi[0] - PITCH / 2)
             & (hpts[:, 1] > lo[1] + PITCH)
             & (hpts[:, 1] < hi[1])
             & (hpts[:, 2] > lo[2] + PITCH / 2)
             & (hpts[:, 2] < hi[2] - PITCH / 2))
        n = int(m.sum())
        if n > CONTACT_CELLS:
            out.append({"id": it["id"], "board": it["board"],
                        "host_cells": n})
    return out


# ---------------------------------------------------------------- walking
def trial_place(uid, cand, lo, hi, fdir):
    """place_candidate a runner into the box -> (insts, group bounds)."""
    mesh = load_asset(uid)
    mesh, align_deg = align_upright(mesh)
    insts, face_deg, face_dot, pca_deg = fpv.place_candidate(
        mesh, cand, lo, hi, "floor", face_dir=fdir)
    allb = np.vstack([i.bounds for i in insts])
    return insts, allb.min(0), allb.max(0), align_deg, face_deg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--anchor", default="obj_022")
    ap.add_argument("--gpu", default="0")
    a = ap.parse_args()

    cdir = paths.compose_dir(a.scene)
    man = json.loads(paths.manifest(a.scene).read_text(encoding="utf-8"))
    floor_r = float(man["frame"]["floor_y"]) * -1.0
    r2r = np.asarray(man["frame"].get("raw_to_render", [1, 1, 1]),
                     np.float64)
    sdir = cdir / "sub_experiment" / a.anchor
    odir = sdir / "cp7"
    jig_p = sdir / "cp6" / "placements_jiggled.json"
    jig = json.loads(jig_p.read_text("utf-8")) if jig_p.exists() else {}
    if not jig.get("subs"):
        odir.mkdir(parents=True, exist_ok=True)
        (odir / "placements_walked.json").write_text(json.dumps(
            {"scene": a.scene, "anchor": a.anchor, "n_items": 0,
             "note": "nothing jiggled at cp6 — cp7 idle"}, indent=1),
            encoding="utf-8")
        (odir / "index.html").write_text(
            "<!doctype html><meta charset='utf-8'><body style="
            "'background:#141414;color:#e8e8e8;font:15px system-ui'>"
            f"<p>{a.anchor}: nothing jiggled at cp6 — cp7 idle.</p>",
            encoding="utf-8")
        print(f"[cp7] {a.anchor}: nothing to walk, idle")
        return
    brec = json.loads((sdir / "cp2" / "boards.json").read_text("utf-8"))
    boards = brec["boards"]
    picks = {r["id"]: r for r in json.loads(
        (sdir / "cp4_aligned" / "picks.json").read_text("utf-8"))["subs"]}
    asg = json.loads((sdir / "cp3" / "assignment.json")
                     .read_text("utf-8"))["subs"]
    flags_of = {r["id"]: (r.get("flags") or []) for r in asg}
    fp = json.loads((cdir / "fitted_preview.json").read_text("utf-8"))
    aplaced = next(p for p in fp["placed"] if p["id"] == a.anchor)
    fdr = aplaced.get("front_dir_raw") or [0.0, -1.0]
    fdir = np.array([fdr[0] * r2r[0], fdr[1] * r2r[2]], np.float64)
    n = np.linalg.norm(fdir)
    fdir = fdir / n if n > 1e-6 else np.array([0.0, -1.0])

    # host meshes first — they are the new physics
    to_render = np.diag([-1.0, -1.0, 1.0, 1.0])
    fsc = trimesh.load(cdir / "fitted_preview.glb", force="scene")
    anchor_meshes = []
    for gname, geom in fsc.geometry.items():
        if gname.rsplit("_t", 1)[0] == a.anchor:
            m = geom.copy()
            m.apply_transform(to_render)
            anchor_meshes.append(m)
    hpts = host_points(anchor_meshes)

    standing, phantom_of, ceiling = classify_boards(boards)
    brect = {b["board"]: b for b in boards}
    plist, interval_recs = pseudo_boards(standing, ceiling, hpts, fdir)

    # ---- items from the cp6 state (k-group boxes)
    items = []
    for r in jig["subs"]:
        lo = np.asarray(r["bounds_render"]["lo"], np.float64)
        hi = np.asarray(r["bounds_render"]["hi"], np.float64)
        wide = any(f.startswith("footprint_wider")
                   for f in flags_of.get(r["id"], []))
        items.append({"id": r["id"], "board": r["board"],
                      "lo": lo, "hi": hi, "c": (lo + hi) / 2,
                      "sz": hi - lo, "move": [0.0, 0.0, 0.0],
                      "k": (picks.get(r["id"], {}).get("pick") or
                            {}).get("k", 1),
                      "k_eff": ((picks.get(r["id"], {}).get("pick") or
                                 {}).get("k", 1) - r["tiles_dropped"]),
                      "tiles_dropped": r["tiles_dropped"],
                      "tile_axis": 0 if (hi[0] - lo[0]) >= (hi[2] - lo[2])
                      else 2,
                      "exempt": r["exempt_wide"] or wide,
                      "swapped": None})
    pairs_before, prot_before = cross_report(items, boards, ceiling)
    clips_before = host_clips(items, hpts)

    # ---- step 1: RE-SEAT items standing on a phantom (underside)
    # board — up onto the real plank top it belongs to
    reseats = []
    for it in items:
        if it["board"] in phantom_of:
            real = phantom_of[it["board"]]
            dy = brect[real]["y"] - brect[it["board"]]["y"]
            cp6._shift(it, 1, dy)
            reseats.append({"id": it["id"], "from_board": it["board"],
                            "to_board": real, "dy_m": round(dy, 3)})
            it["board"] = real

    # ---- step 2: WALK-DOWNS for items over their headroom
    swaps, dry = [], []
    new_meshes = {}          # id -> render-frame instance meshes
    for it in items:
        if it["board"] not in brect:
            continue
        hr = headroom_of(brect[it["board"]], ceiling)
        if hr is None or it["sz"][1] <= hr - SLACK:
            continue
        pkr = picks.get(it["id"])
        if not pkr:
            dry.append({"id": it["id"], "why": "no pick record"})
            continue
        runners = pkr.get("runners") or []
        box_lo = it["lo"].copy()
        box_hi = it["hi"].copy()
        board_y = brect[it["board"]]["y"]
        box_lo[1] = board_y
        box_hi[1] = board_y + hr
        done = False
        for rank, rn in enumerate(runners, start=1):
            cand = {"uid": rn["uid"], "perm": rn["perm"],
                    "k": it["k_eff"], "scale": 1.0,
                    "axis": it["tile_axis"]}
            try:
                insts, glo, ghi, adeg, fdeg = trial_place(
                    rn["uid"], cand, box_lo, box_hi, fdir)
            except Exception as e:      # unreadable asset = skip runner
                dry.append({"id": it["id"],
                            "why": f"runner {rn['uid'][:8]} failed: {e}"})
                continue
            if ghi[1] - glo[1] <= hr - SLACK:
                swaps.append({"id": it["id"], "board": it["board"],
                              "from_uid": pkr["pick"]["uid"],
                              "to_uid": rn["uid"], "runner_rank": rank,
                              "height_before": round(float(it["sz"][1]),
                                                     3),
                              "height_after": round(float(ghi[1] -
                                                          glo[1]), 3),
                              "headroom_m": round(hr, 3),
                              "align_deg": adeg, "face_deg": fdeg})
                it["lo"], it["hi"] = glo, ghi
                it["c"] = (glo + ghi) / 2
                it["sz"] = ghi - glo
                new_meshes[it["id"]] = insts
                done = True
                break
        if not done:
            dry.append({"id": it["id"], "board": it["board"],
                        "why": "TOO_TALL_DRY — no runner fits under "
                               f"{hr:.3f} m headroom",
                        "height_m": round(float(it["sz"][1]), 3)})

    # ---- step 3: intervals become the boards; SR9 triage + SR8
    # jiggle run on free space only
    assign_pseudo(items, plist)
    asg_seed = [{"id": r["id"], "seed_bottom_y": r.get("seed_bottom_y")}
                for r in asg]
    tile_drops, spills, kills = triage_fa(items, plist, asg_seed)
    iters, over_cap = jiggle_fa(items, plist)
    for it in items:                       # pseudo -> real board ids
        it["interval"] = it["board"] % 100
        it["board"] = it["board"] // 100
    for s in spills:
        s["from_board"], s["to_board"] = (s["from_board"] // 100,
                                          s["to_board"] // 100)
    for t in tile_drops:
        t["board"] //= 100
    for k in kills:
        k["from_board"] //= 100
    for o in over_cap:
        o["board"] //= 100
    pairs_after, prot_after = cross_report(items, boards, ceiling)
    clips_after = host_clips(items, hpts)

    rows = []
    for it in items:
        rows.append({"id": it["id"], "board": it["board"],
                     "interval": it["interval"],
                     "walk_move_m": [round(v, 3) for v in it["move"]],
                     "swapped_to": next((s["to_uid"] for s in swaps
                                         if s["id"] == it["id"]), None),
                     "bounds_render": {"lo": it["lo"].round(3).tolist(),
                                       "hi": it["hi"].round(3).tolist()}})
    rec = {"scene": a.scene, "anchor": a.anchor,
           "anchor_name": brec.get("anchor_name"),
           "n_items": len(items),
           "phantom_boards": [{"board": p, "underside_of": r,
                               "gap_m": round(brect[r]["y"]
                                              - brect[p]["y"], 3)}
                              for p, r in sorted(phantom_of.items())],
           "free_space": interval_recs,
           "reseats": reseats, "swaps": swaps, "dry": dry,
           "tile_drops": tile_drops, "spills": spills, "kills": kills,
           "over_capacity_boards": over_cap,
           "host_clips_before": clips_before,
           "host_clips_after": clips_after,
           "cross_level_pairs_before": [p for p in pairs_before
                                        if p["cross_level"]],
           "cross_level_pairs_after": [p for p in pairs_after
                                       if p["cross_level"]],
           "same_board_pairs_before": len([p for p in pairs_before
                                           if not p["cross_level"]]),
           "same_board_pairs_after": len([p for p in pairs_after
                                          if not p["cross_level"]]),
           "protrusions_before": prot_before,
           "protrusions_after": prot_after,
           "subs": rows}
    odir = sdir / "cp7"
    odir.mkdir(parents=True, exist_ok=True)
    (odir / "placements_walked.json").write_text(
        json.dumps(rec, indent=1), encoding="utf-8")

    # ---- meshes: cp6 glb minus swapped ids, plus the new instances,
    # plus this pass's moves (reseat dy rides in move[] too)
    move_of = {it["id"]: it["move"] for it in items}
    gsc = trimesh.load(sdir / "cp6" / "subs_jiggled.glb", force="scene")
    sub_meshes = []
    out_sc = trimesh.Scene()
    for node in gsc.graph.nodes_geometry:
        T, gname = gsc.graph[node]
        sid = node.rsplit("_t", 1)[0]
        if sid in new_meshes or sid not in move_of:
            continue
        m = gsc.geometry[gname].copy()
        if T is not None:
            m.apply_transform(T)
        m.apply_transform(to_render)
        m.apply_translation(move_of[sid])
        sub_meshes.append((sid, m))
    for sid, insts in new_meshes.items():
        if sid not in move_of:
            continue                  # walked, then killed at triage
        for m0 in insts:
            m = m0.copy()
            m.apply_translation(move_of[sid])
            sub_meshes.append((sid, m))
    for gi, (sid, m) in enumerate(sub_meshes):
        mr = m.copy()
        mr.apply_transform(to_render)
        out_sc.add_geometry(mr, node_name=f"{sid}_t{gi}")
    meshes_only = [m for _, m in sub_meshes]
    if not meshes_only:
        # everything killed/dropped — record + page stand, stale
        # artifacts go (the cp5 stale-door lesson)
        for f in ("subs_walked.glb", "front.png"):
            p = odir / f
            if p.exists():
                p.unlink()
        build_page(odir, rec)
        print(f"[cp7] {a.anchor}: nothing left to render "
              f"({len(kills)} kills) — record + page written")
        return
    (odir / "subs_walked.glb").write_bytes(
        out_sc.export(file_type="glb"))

    # ---- front render, cp6 framing verbatim
    P = np.vstack([np.vstack([m.bounds for m in anchor_meshes]),
                   np.vstack([m.bounds for m in meshes_only])])
    lo_all, hi_all = P.min(0), P.max(0)
    ctr = (lo_all + hi_all) / 2
    span = float(max(hi_all - lo_all))
    fdir3 = np.array([fdir[0], 0.0, fdir[1]])
    dist = max(2.4, span * 1.1)
    eye = ctr + fdir3 * dist
    eye[1] = ctr[1] + 0.15
    fov = float(np.clip(np.degrees(2 * np.arctan2(span * 0.62, dist)),
                        25, 95))
    clip = (f"{lo_all[0]-1.2:.3f},{floor_r-0.25:.3f},{lo_all[2]-1.2:.3f},"
            f"{hi_all[0]+1.2:.3f},{hi_all[1]+0.5:.3f},{hi_all[2]+1.2:.3f}")
    img = cp6.splat_shot(odir / "front.png", eye, ctr,
                         np.array([0., 1., 0.]), fov, clip,
                         paths.ply(a.scene), gpu=a.gpu).convert("RGBA")
    img.alpha_composite(cp6.meshes_rgba(anchor_meshes, eye, ctr,
                                        np.array([0., 1., 0.]), fov, RES,
                                        alpha=0.30))
    if meshes_only:
        img.alpha_composite(cp6.meshes_rgba(meshes_only, eye, ctr,
                                            np.array([0., 1., 0.]), fov,
                                            RES))
    img.convert("RGB").save(odir / "front.png")

    build_page(odir, rec)
    print(f"[cp7] {a.anchor}: {len(reseats)} re-seated, "
          f"{len(swaps)} walked down, {len(dry)} dry; cross-level "
          f"pairs {len(rec['cross_level_pairs_before'])} -> "
          f"{len(rec['cross_level_pairs_after'])}; protrusions "
          f"{len(prot_before)} -> {len(prot_after)}; host clips "
          f"{len(clips_before)} -> {len(clips_after)}")
    print(f"[cp7] wrote {odir / 'index.html'}")


def build_page(odir, rec):
    css = """
:root{color-scheme:dark}*{box-sizing:border-box}
body{margin:0;background:#141414;color:#e8e8e8;
     font:15px/1.55 "Segoe UI",system-ui,sans-serif}
.wrap{max-width:1500px;margin:0 auto;padding:28px 32px 120px}
h1{font-size:24px;margin:0 0 4px}
.sub{color:#9a9a9a;margin:0 0 20px}
.contract{background:#1c1c1c;border-left:3px solid #ffd479;
          padding:14px 18px;margin:18px 0;border-radius:0 4px 4px 0}
.contract b{color:#ffd479}
.note{background:#1c1c1c;border-left:3px solid #4a90d9;padding:12px 18px;
      margin:18px 0;border-radius:0 4px 4px 0;color:#c9c9c9}
table{border-collapse:collapse;margin:16px 0;font-size:13.5px}
th,td{border:1px solid #2e2e2e;padding:5px 10px;text-align:left}
th{background:#1c1c1c;color:#cfcfcf}
td.mono{font-family:Consolas,monospace;font-size:12.5px}
.imgs{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:18px 0}
.imgs img{width:100%;display:block;border-radius:4px;cursor:zoom-in;
          background:#000}
.cap{color:#8a8a8a;font-size:12.5px;margin:6px 0 0}
#lb{position:fixed;inset:0;background:#000d;display:none;z-index:99;
    overflow:auto;cursor:zoom-out;padding:20px;text-align:center}
#lb img{max-width:none}#lb.on{display:block}
"""
    js = """
const lb=document.getElementById('lb'),lbi=lb.querySelector('img');
document.addEventListener('click',e=>{const im=e.target.closest('.imgs img');
 if(im){lbi.src=im.src;lb.classList.add('on');window.scrollTo(0,0);}});
lb.addEventListener('click',()=>lb.classList.remove('on'));
document.addEventListener('keydown',e=>{
 if(e.key==='Escape')lb.classList.remove('on');});
"""
    clb = len(rec["cross_level_pairs_before"])
    cla = len(rec["cross_level_pairs_after"])
    h = ['<!doctype html><meta charset="utf-8">',
         f'<title>sub rounds CP7 — walk-downs — {rec["anchor"]}</title>',
         f'<style>{css}</style><div class="wrap">',
         '<h1>Sub rounds — CP7: host-aware walk-downs + cross-level '
         'physics</h1>',
         f'<p class="sub">{rec["scene"]} · anchor {rec["anchor"]} '
         f'({html.escape(str(rec["anchor_name"]))}) · '
         f'{len(rec["reseats"])} re-seated off underside-boards · '
         f'{len(rec["swaps"])} walked down · {len(rec["dry"])} dry · '
         f'cross-level pairs {clb} &rarr; {cla} · ceiling protrusions '
         f'{len(rec["protrusions_before"])} &rarr; '
         f'{len(rec["protrusions_after"])} · host clips '
         f'{len(rec["host_clips_before"])} &rarr; '
         f'{len(rec["host_clips_after"])}</p>',
         '<div class="contract">'
         '<b>What this step gets:</b> the cp6 jiggled state, each '
         'sub&rsquo;s recorded cp4 runners, the cp2 boards, and the '
         'HOST MESH itself (2 cm voxel occupancy — new).<br>'
         '<b>What it decides:</b> which boards are real standing '
         'surfaces vs plank UNDERSIDES (undersides become ceilings, '
         'their squatters re-seated); the FREE INTERVALS of each '
         'board once dividers/panels/doors are subtracted — triage '
         'and jiggle then run on free space only, so an enclosed '
         'compartment can never receive a spill; which too-tall '
         'items walk down their runner list to fit under the '
         'ceiling.<br>'
         '<b>What a mistake looks like:</b> an item inside a divider '
         'or door not flagged as a host clip, a free interval drawn '
         'through solid geometry, a walk on an item that already '
         'fit, or a real board misread as an underside.</div>']
    h.append('<div class="imgs">'
             '<div><img src="../cp6/front.png"><p class="cap">'
             '<b>BEFORE</b> — cp6 jiggled</p></div>'
             '<div><img src="front.png"><p class="cap"><b>AFTER</b> — '
             're-seated + walked + host-aware re-jiggle</p></div></div>')
    if rec["phantom_boards"]:
        h.append('<div class="note"><b>Underside-boards detected '
                 '(kept as ceilings, not standing surfaces):</b> '
                 + " · ".join(
                     f'B{p["board"]} = underside of B{p["underside_of"]}'
                     f' (plank {p["gap_m"]} m)'
                     for p in rec["phantom_boards"]) + '</div>')
    h.append('<p><b>Host free space per standing board</b> (measured '
             'from the mesh; ENCLOSED = no usable run, e.g. behind '
             'doors):</p>')
    h.append('<table><tr><th>board</th><th>free intervals (long axis)'
             '</th><th>free fraction</th><th>front coverage '
             '(doors test)</th></tr>')
    for fr in rec["free_space"]:
        iv = ("<b>ENCLOSED</b>" if fr["enclosed"] else " · ".join(
            f'[{r[0]} .. {r[1]}]' for r in fr["free"]))
        h.append(f'<tr><td class="mono">B{fr["board"]}</td>'
                 f'<td class="mono">{iv}</td>'
                 f'<td class="mono">{fr["free_frac"]}</td>'
                 f'<td class="mono">{fr.get("front_cover", "—")}'
                 '</td></tr>')
    h.append('</table>')
    if rec["reseats"]:
        h.append('<div class="note"><b>Re-seated (were standing on an '
                 'underside, i.e. sunk inside a plank):</b> '
                 + " · ".join(
                     f'{r["id"]} B{r["from_board"]}&rarr;'
                     f'B{r["to_board"]} (+{r["dy_m"]} m)'
                     for r in rec["reseats"]) + '</div>')
    if rec["swaps"]:
        h.append('<table><tr><th>walked item</th><th>board</th>'
                 '<th>runner</th><th>height before</th>'
                 '<th>height after</th><th>headroom</th></tr>')
        for s in rec["swaps"]:
            h.append(f'<tr><td>{s["id"]}</td>'
                     f'<td class="mono">B{s["board"]}</td>'
                     f'<td class="mono">#{s["runner_rank"]} '
                     f'{s["to_uid"][:8]}</td>'
                     f'<td class="mono">{s["height_before"]} m</td>'
                     f'<td class="mono">{s["height_after"]} m</td>'
                     f'<td class="mono">{s["headroom_m"]} m</td></tr>')
        h.append('</table>')
    if rec["dry"]:
        h.append('<div class="note"><b>Dry (no runner fits — recorded, '
                 'kept; library-gap material):</b><br>' + "<br>".join(
                     f'{d["id"]}: {html.escape(d["why"])}'
                     for d in rec["dry"]) + '</div>')
    for title, key in (("Host clips BEFORE (item box swallows host "
                        "geometry beyond contact)", "host_clips_before"),
                       ("Host clips AFTER", "host_clips_after")):
        rowsc = rec[key]
        h.append(f'<p><b>{title}:</b> {len(rowsc) or "none"}</p>')
        if rowsc:
            h.append('<table><tr><th>item</th><th>board</th>'
                     '<th>host cells in box</th></tr>')
            for c in rowsc:
                h.append(f'<tr><td>{c["id"]}</td>'
                         f'<td class="mono">B{c["board"]}</td>'
                         f'<td class="mono">{c["host_cells"]}</td></tr>')
            h.append('</table>')
    for title, key in (("Ceiling protrusions BEFORE (pokes through the "
                        "plank above)", "protrusions_before"),
                       ("Ceiling protrusions AFTER", "protrusions_after")):
        rowsp = rec[key]
        h.append(f'<p><b>{title}:</b> {len(rowsp) or "none"}</p>')
        if rowsp:
            h.append('<table><tr><th>item</th><th>board</th>'
                     '<th>through ceiling</th><th>item height</th>'
                     '<th>headroom</th></tr>')
            for p in rowsp:
                h.append(f'<tr><td>{p["id"]}</td>'
                         f'<td class="mono">B{p["board"]}</td>'
                         f'<td class="mono">{p["through_ceiling_m"]} m'
                         '</td>'
                         f'<td class="mono">{p["height_m"]} m</td>'
                         f'<td class="mono">{p["headroom_m"]} m</td>'
                         '</tr>')
            h.append('</table>')
    if rec["cross_level_pairs_after"]:
        h.append('<table><tr><th>residual cross-level pair</th>'
                 '<th>boards</th><th>overlap m</th></tr>')
        for p in rec["cross_level_pairs_after"]:
            h.append(f'<tr><td class="mono">{p["a"]} × {p["b"]}</td>'
                     f'<td class="mono">B{p["boards"][0]} × '
                     f'B{p["boards"][1]}</td>'
                     f'<td class="mono">{p["overlap_m"]}</td></tr>')
        h.append('</table>')
    h.append(f'<p>Same-board overlap pairs: '
             f'{rec["same_board_pairs_before"]} &rarr; '
             f'{rec["same_board_pairs_after"]}.</p>')
    if rec.get("spills") or rec.get("tile_drops") or rec.get("kills"):
        bits = []
        if rec["tile_drops"]:
            bits.append(f'{len(rec["tile_drops"])} tile drops')
        if rec["spills"]:
            bits.append(", ".join(
                f'{s["id"]} B{s["from_board"]}&rarr;B{s["to_board"]}'
                for s in rec["spills"]) + " spilled")
        if rec["kills"]:
            bits.append(", ".join(k["id"] for k in rec["kills"])
                        + " KILLED")
        h.append('<div class="note"><b>Re-triage after the walks '
                 '(free intervals as boards — spills can only land in '
                 'measured open space):</b> ' + " · ".join(bits)
                 + '</div>')
    h.append('<div class="note"><b>Gate question (one look):</b> does '
             'nothing poke through a plank, a divider or the doors '
             'any more, are the walked replacements sane stand-ins, '
             'and did anything move that should not have?</div>')
    h.append('<div id="lb"><img></div>')
    h.append(f'<script>{js}</script></div>')
    (odir / "index.html").write_text("\n".join(h), encoding="utf-8")


if __name__ == "__main__":
    main()
