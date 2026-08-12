"""
FIT DECLIP (2026-08-04, user design: "jiggle it until it doesn't clip
-- like in a 3D game things bounce away from each other", with the
rule "the wall/floor/ceiling is STATIC"): deterministic position-based
penetration resolution over the placed preview meshes.

Per relaxation round, every clipping pair (real-mesh voxel overlap on
the 2 cm lattice, â‰¤4 shared cells = contact) generates a push-apart
along the horizontal axis of least penetration, split between the two
items PROPORTIONAL TO THEIR REMAINING BUDGET; out-of-bounds items get
pushed back inside by the static shell. Constraints, all hard:

  - shell is immovable: pushes from walls/floor/ceiling only point in
  - PLANE CONSTRAINTS (user 08-04): floor/ceiling items move in the
    FLOOR PLANE only (x/z); wall-mounted items move in their WALL
    PLANE only (along the wall AND vertically, between floor and
    ceiling) -- flush to the wall stays canon (normal axis locked)
  - items MAY leave their fit box (user 08-04: "the jiggle can move
    outside the box") -- the budget is the ROOM: a mesh may travel
    until it meets a wall. Push shares stay minimal (half the
    penetration), so displacement is only what de-clipping demands;
    `declip_move_m` + `out_of_box_mm` record how far each item ended
    from its box for the loop/judge to weigh
  - WALL-ADJACENCY LOCK (user 08-04: "a shelf on the floor backing the
    north wall should not migrate to the middle of the room"): a floor
    item starting within HUG_M of a wall KEEPS that wall -- its motion
    on the wall's normal axis is locked for the whole solve; sliding
    along the wall stays free; corner items lock both axes (pinned).
    TUCKED-ITEM EXEMPTION (the obj_000 desk-chair catch, user-spotted):
    the lock holds only when the witness's OBSERVED facing agrees the
    item BACKS the wall (front into the room, or no observation) -- an
    item observed facing TOWARD the wall (a chair at its desk) is
    tucked furniture, not wall-backed, and stays free to jiggle
  - FLAT items (height < FLAT_H, e.g. rug / yoga mat) are exempt as
    clip participants: things standing through a rug's pile is correct

ROTATION (2026-08-09) is tried BEFORE a push-apart and wins when it
clears the clip with ZERO translation -- see the rule below.

Moves are quantized to the voxel lattice so a translation is an integer
key-shift (no re-voxelization inside the loop); the final state is
verified by a normal fit_check pass afterwards, never by the solver
itself. Applies the result IN PLACE to fitted_preview.glb (+ per-item
`declip_move_m` in fitted_preview.json). Stage order:
fit_preview -> fit_declip -> fit_check.

Run:  python compose/fit_declip.py --scene bedroom_marble
Out:  updated fitted_preview.glb/.json + compose/fit_declip.json
"""
import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

import numpy as np
import trimesh

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402
from fit_check import (load_placed, cell_keys, PITCH,  # noqa: E402
                       CONTACT_CELLS, ALLOW_CELLS, ALLOW_L)
# ALLOW_CELLS (R-S2-117): the user's allowed clipping margin. The solver
# leaves any overlap at/below it alone â€” those are acceptable touches
# (asset junk slivers included, by ruling), and authority is spent on
# the overlaps a viewer would actually notice.
# scene_state lives in the sibling graph/ package, not beside us, so its
# directory has to go on the path too (same two-step the other compose
# modules use, e.g. uniform_instances.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "graph"))
import scene_state  # noqa: E402

TOL_M = 0.02      # slack around the fit box a mesh may use
FLAT_H = 0.06     # items shorter than this never participate in clips
HUG_M = 0.30      # floor item starting this close to a wall keeps it
                  # (same constant as the facing ladder's wall-hug)
HUG_DRIFT_M = 0.30  # how far a hugging item may be dragged OFF its wall
#                     to de-clip. USER-SET, twice (2026-08-11C, R-S2-119b):
#                     first 0.2 — eyeballed on the PRE-normalization room —
#                     then corrected to 0.3 once the scene proved to be at
#                     0.66 scale ("now i know that the scene is actually
#                     miniature. i think 0.3 is reasonable"). Eye-calibrated
#                     value in TRUE meters; moves on their say-so only,
#                     like fit_check.ALLOW_L.
MAX_ROUNDS = 60

KX, KY, KZ = 1 << 42, 1 << 21, 1
KSHIFT = {0: KX, 1: KY, 2: KZ}

# ROTATION AS A DE-CLIPPING MOVE (user design 2026-08-09: "if there is a
# rotation that can solve collision with minimal translation, we might
# prefer that" -> "rotation might even be preferred if it can minimize
# translation").
# 
# THE RULE, and it has no weight to tune: MINIMISE TRANSLATION. A bounded
# yaw is FREE in that ranking, so it wins whenever it can do the job.
# Position is measured evidence -- sliding an item moves it away from
# where it was actually seen -- while a small yaw leaves it where the
# evidence put it. Concretely, before a clipping pair is pushed apart we
# ask whether a bounded yaw on either item clears the overlap with ZERO
# translation; zero beats any positive translation, so that rotation is
# taken. Anything a rotation cannot clear falls through to the existing
# push-apart, unchanged.
# 
# WHAT BOUNDS THE YAW (not a knob): the placement stage already snapped
# each item to a CARDINAL facing, and rotation_check spent a model call
# per object per camera agreeing that facing against the reference
# photograph. So the yaw may not change which cardinal direction the item
# faces -- |yaw| < 45 deg -- and when a witness observed the item, the
# rotated front must stay within 45 deg of the OBSERVED direction too.
# That is the same evidence the tucked-item exemption reads.
# 
# WHO MAY ROTATE: floor-mounted, non-flat items. A wall item's yaw is
# what holds it flat against its wall, and a ceiling item's likewise, so
# neither is eligible.
# 
# COST: a translation is an integer key shift on the 2 cm lattice, but a
# rotation is not -- it needs the mesh re-voxelised. So each (item, yaw)
# is voxelised AT MOST ONCE and cached; the item's live cells are always
# that cached set plus its accumulated integer translation. Candidate
# yaws are a coarse-to-fine ladder, not a continuous search.

YAW_LADDER = (5, -5, 10, -10, 15, -15, 20, -20, 30, -30, 40, -40)
YAW_MAX = 45.0        # a larger yaw would change the CARDINAL facing the
#                       placement stage snapped to and rotation_check
#                       confirmed -- that is a decision, not slack
FACE_TOL_DEG = 45.0   # rotated front must stay this close to the facing a
#                       witness observed, when one did


def _yaw_cells(mesh, deg, pitch, cell_keys):
    """Cells of `mesh` yawed `deg` about its own vertical axis, through
    its footprint centre, at its ORIGINAL position. Absolute lattice
    keys, so the caller adds the accumulated translation shift."""
    import numpy as np
    m = mesh.copy()
    c = m.bounds.mean(axis=0)
    t = np.radians(deg)
    co, si = np.cos(t), np.sin(t)
    R = np.eye(4)
    R[0, 0], R[0, 2] = co, si          # yaw about +y (render frame up)
    R[2, 0], R[2, 2] = -si, co
    m.apply_translation(-c)
    m.apply_transform(R)
    m.apply_translation(c)
    return cell_keys(m), np.array(m.bounds)



def decode(keys):
    ix = keys >> 42
    iy = (keys >> 21) & ((1 << 21) - 1)
    iz = keys & ((1 << 21) - 1)
    return ix, iy, iz


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()

    cdir, by_item, wx, wz, fy, cy, r2r = load_placed(args.scene)
    fpj = json.loads((cdir / "fitted_preview.json").read_text(
        encoding="utf-8"))
    place = {p["id"]: p for p in fpj["placed"]}
    # observed witness facing (render frame xz) for the tucked-item
    # exemption on the hug lock
    graph = json.loads((paths.scene_dir(args.scene) / "scene_graph.json")
                       .read_text(encoding="utf-8"))
    # THE CURRENT LAYER carries this testimony, with `judged` kept only as
    # a fallback for older graphs that have no layer. Reading `judged`
    # alone returned nothing for exactly the nodes the pipeline changed: a
    # piece the judges SPLIT off never existed in `judged`, and a node
    # merged away is still in it â€” so the tucked-item exemption below never
    # fired for them.
    app_src = {n["id"]: (n.get("appearance") or {})
               for n in scene_state.nodes(graph)}
    for jn in graph.get("judged", {}).get("nodes", []):
        app_src.setdefault(jn["id"], jn.get("appearance") or {})
    observed = {}
    for nid, app in app_src.items():
        wd = (app.get("facing") or {}).get("world_dir")
        if wd:
            observed[nid] = (wd[0] * float(r2r[0]),
                             wd[1] * float(r2r[2]))

    ids = sorted(by_item)
    cells = {i: cell_keys(by_item[i]).copy() for i in ids}
    aabb = {i: np.array(by_item[i].bounds) for i in ids}
    moved = {i: np.zeros(3) for i in ids}          # metres, (x, y, z)
    ncell = {i: np.zeros(3, np.int64) for i in ids}  # the SAME move
    #   as integer lattice cells, so a re-voxelised rotation can be
    #   composed with the translation already applied
    yaw = {i: 0.0 for i in ids}                   # applied yaw, deg
    yaw_cache = {}                                # (id, deg) -> cells
    flat = {i for i in ids
            if (aabb[i][1][1] - aabb[i][0][1]) < FLAT_H}

    # per-item allowed interval per horizontal axis (box +- TOL_M);
    # wall items locked on their wall-normal axis
    lock = {i: set() for i in ids}
    #: DIRECTIONAL hug (R-S2-116): {item: {axis: allowed sign}}. The
    #: sign points AT the hugged wall â€” moving that way is allowed
    #: (shell-bounded), the opposite way is the drift the hug forbids.
    hug = {}
    box_iv = {}
    for i in ids:
        pl = place[i]
        blo = np.asarray(pl["fit_box"]["aabb_min"], np.float32) * r2r
        bhi = np.asarray(pl["fit_box"]["aabb_max"], np.float32) * r2r
        blo, bhi = np.minimum(blo, bhi), np.maximum(blo, bhi)
        box_iv[i] = (blo, bhi)
        fd = pl.get("front_dir_raw")
        if pl["mount"] == "wall" and fd:
            fdir = (fd[0] * float(r2r[0]), fd[1] * float(r2r[2]))
            lock[i].add(0 if abs(fdir[0]) >= abs(fdir[1]) else 2)
            # dual attachment (door rule): wall item standing on the
            # floor never jiggles vertically
            if "floor" in (pl.get("attachment") or []):
                lock[i].add(1)
        if pl["mount"] == "ceiling":
            pass   # ceiling items still slide horizontally if pushed
        # wall-adjacency HUG: starting-pose mesh edge within HUG_M of a
        # wall. âš  DIRECTIONAL since 2026-08-11C (R-S2-116). It used to
        # freeze the whole axis, which also banned sliding CLOSER to the
        # hugged wall â€” and that froze a wardrobe out of 18 cm of free
        # space the user could see with the naked eye (fresh04). "Don't
        # leave your wall" never meant "don't tighten against it": the
        # allowed sign points AT the hugged wall, the forbidden sign
        # away from it, and the shell bound is what stops the item at
        # the wall itself.
        if pl["mount"] == "floor":
            lo, hi = by_item[i].bounds if not isinstance(
                by_item[i], list) else (None, None)
            if lo is not None:
                obs = observed.get(i)
                for axis, gaps, normals in (
                        (0, (lo[0] - wx[0], wx[1] - hi[0]),
                         ((1.0, 0.0), (-1.0, 0.0))),
                        (2, (lo[2] - wz[0], wz[1] - hi[2]),
                         ((0.0, 1.0), (0.0, -1.0)))):
                    k = 0 if gaps[0] <= gaps[1] else 1
                    if gaps[k] >= HUG_M:
                        continue
                    n = normals[k]   # wall's inward normal
                    # tucked exemption: observed facing TOWARD the wall
                    if obs and (obs[0] * n[0] + obs[1] * n[1]) < -0.3:
                        continue
                    hug.setdefault(i, {})[axis] = -1 if k == 0 else +1

    def budget(i, axis, sgn, shell=False):
        """Metres item i may still move along +-axis before meeting a
        STATIC shell surface. Plane constraints: y is available ONLY
        to wall-mounted items (their wall plane); the wall-normal
        axis is locked for them; floor/ceiling items keep x/z.
        Shell push-back BYPASSES a floor item's hug lock: the lock
        means 'don't leave the wall', not 'stay embedded in it'."""
        if axis in lock[i] and not (shell
                                    and place[i]["mount"] == "floor"):
            return 0.0
        # directional hug: toward the hugged wall is free (the shell
        # bound below stops the item AT the wall). Away from it: a
        # BOUNDED allowance (user ruling 2026-08-11C, R-S2-119: "we can
        # allow the bed to be dragged off the wall a bit" — the bed's
        # headboard vs the window's protruding frame). The item may
        # drift off its wall as far as de-clipping demands but must
        # still END within HUG_DRIFT_M of it — hugging is preserved,
        # only "flush" stopped being mandatory.
        if not shell:
            hd = hug.get(i, {}).get(axis)
            if hd is not None and sgn != hd:
                lo_h, hi_h = aabb[i]
                low_w, high_w = (wx if axis == 0 else wz)
                gap = ((lo_h[axis] - low_w) if hd < 0
                       else (high_w - hi_h[axis]))
                return max(0.0, HUG_DRIFT_M - gap)
        lo, hi = aabb[i]
        if axis == 1:
            if place[i]["mount"] != "wall":
                return 0.0
            return (max(0.0, cy - hi[1]) if sgn > 0
                    else max(0.0, lo[1] - fy))
        low, high = (wx if axis == 0 else wz)
        if sgn > 0:
            return max(0.0, high - hi[axis])
        return max(0.0, lo[axis] - low)

    def shift(i, axis, metres):
        """Quantized move; updates cells (integer key shift), aabb,
        moved. Returns the metres actually moved."""
        n = int(round(metres / PITCH))
        if n == 0:
            return 0.0
        d = n * PITCH
        cells[i] = cells[i] + (n * KSHIFT[axis])
        aabb[i][:, axis] += d
        moved[i][axis] += d
        ncell[i][axis] += n
        return d

    def may_rotate(i):
        """Floor-mounted, non-flat, NOT wall-backed. A wall or ceiling
        item's yaw is what holds it flat against its surface — and the
        same is true of a floor item HUGGING a wall (R-S2-118, the
        15°-yawed wardrobe the user caught on fresh04): its back is
        flat against the wall, and any yaw digs a corner in. Tucked
        items (observed facing the wall, e.g. a desk chair) carry no
        hug entry and keep their rotation freedom."""
        return (place[i]["mount"] == "floor" and i not in flat
                and i not in hug)

    def cells_at(i, deg):
        """Item i's cells if it were yawed `deg`, at its CURRENT
        position: the cached voxelisation of the yawed mesh plus the
        integer translation applied so far."""
        key = (i, deg)
        if key not in yaw_cache:
            yaw_cache[key] = _yaw_cells(by_item[i], deg, PITCH, cell_keys)
        base, bb = yaw_cache[key]
        sh = int(ncell[i][0]) * KX + int(ncell[i][1]) * KY             + int(ncell[i][2]) * KZ
        return base + sh, bb + (ncell[i] * PITCH)

    def facing_ok(i, deg):
        """The yaw may not change the CARDINAL facing the placement stage
        snapped to, nor drift from what a witness observed."""
        if abs(yaw[i] + deg) >= YAW_MAX:
            return False
        obs = observed.get(i)
        fd = place[i].get("front_dir_raw")
        if not obs or not fd:
            return True
        f = np.array([fd[0] * float(r2r[0]), fd[1] * float(r2r[2])])
        t = np.radians(yaw[i] + deg)
        co, si = np.cos(t), np.sin(t)
        rot = np.array([co * f[0] + si * f[1], -si * f[0] + co * f[1]])
        o = np.array(obs, float)
        no, nr = np.linalg.norm(o), np.linalg.norm(rot)
        if no == 0 or nr == 0:
            return True
        cosang = float(np.dot(rot, o) / (nr * no))
        return cosang >= np.cos(np.radians(FACE_TOL_DEG))

    def try_rotate(a, b):
        """Can a bounded yaw on a or b clear this clip with ZERO
        translation? Zero beats any positive translation, so if one can,
        it is taken. Returns the id rotated, or None."""
        for i, other in ((a, b), (b, a)):
            if not may_rotate(i):
                continue
            for deg in YAW_LADDER:
                if not facing_ok(i, deg):
                    continue
                cand, bb = cells_at(i, yaw[i] + deg)
                ov = (np.minimum(bb[1], aabb[other][1])
                      - np.maximum(bb[0], aabb[other][0]))
                if (ov <= 0).any():
                    n_int = 0
                else:
                    n_int = len(np.intersect1d(cand, cells[other]))
                if n_int > ALLOW_CELLS:
                    continue
                # it clears. Take it, and make sure it did not simply
                # move the problem onto a third item.
                worse = False
                for k in ids:
                    if k in (i, other) or k in flat:
                        continue
                    ov2 = (np.minimum(bb[1], aabb[k][1])
                           - np.maximum(bb[0], aabb[k][0]))
                    if (ov2 <= 0).any():
                        continue
                    before = len(np.intersect1d(cells[i], cells[k]))
                    after = len(np.intersect1d(cand, cells[k]))
                    if after > ALLOW_CELLS and after > before:
                        worse = True
                        break
                if worse:
                    continue
                cells[i] = cand
                aabb[i] = bb
                yaw[i] += deg
                return i
        return None

    rotated = set()
    log_rounds = []
    for rnd in range(MAX_ROUNDS):
        any_move = 0.0
        # ---- shell pass (static shell pushes items back inside) ----
        for i in ids:
            lo, hi = aabb[i]
            planes = [(0, wx[0], wx[1]), (2, wz[0], wz[1])]
            if place[i]["mount"] == "wall":
                planes.append((1, fy, cy))   # wall plane includes y
            for axis, low, high in planes:
                pen_lo = low - lo[axis]
                pen_hi = hi[axis] - high
                if pen_lo > TOL_M:
                    any_move += abs(shift(
                        i, axis,
                        min(pen_lo, budget(i, axis, +1, shell=True))))
                elif pen_hi > TOL_M:
                    any_move += abs(shift(
                        i, axis,
                        -min(pen_hi, budget(i, axis, -1, shell=True))))
        # ---- pair pass ----
        clips = []
        for ai in range(len(ids)):
            a = ids[ai]
            if a in flat:
                continue
            for b in ids[ai + 1:]:
                if b in flat:
                    continue
                ov = (np.minimum(aabb[a][1], aabb[b][1])
                      - np.maximum(aabb[a][0], aabb[b][0]))
                if (ov <= 0).any():
                    continue
                inter = np.intersect1d(cells[a], cells[b],
                                       assume_unique=True)
                if len(inter) <= ALLOW_CELLS:
                    continue
                clips.append((len(inter), a, b, inter))
        clips.sort(key=lambda c: (-c[0], c[1], c[2]))
        n_rot_round = 0
        for _, a, b, inter in clips:
            # ROTATION FIRST (user rule 2026-08-09): minimise translation,
            # and a bounded yaw is free in that ranking. If a yaw clears
            # the clip with ZERO translation it wins outright, because
            # zero beats any positive push.
            r = try_rotate(a, b)
            if r is not None:
                rotated.add(r)
                n_rot_round += 1
                any_move += PITCH        # progress, so the loop continues
                continue
            ix, iy, iz = decode(inter)
            ext = {0: (int(np.ptp(ix)) + 1) * PITCH,
                   2: (int(np.ptp(iz)) + 1) * PITCH}
            if "wall" in (place[a]["mount"], place[b]["mount"]):
                ext[1] = (int(np.ptp(iy)) + 1) * PITCH
            # least-penetration axis first, next axis when no budget
            for axis in sorted(ext, key=lambda k: ext[k]):
                pen = ext[axis]
                ca = (aabb[a][0][axis] + aabb[a][1][axis]) / 2
                cb = (aabb[b][0][axis] + aabb[b][1][axis]) / 2
                sa = 1 if ca >= cb else -1      # a moves away from b
                ba, bb = budget(a, axis, sa), budget(b, axis, -sa)
                if ba + bb <= 0:
                    continue
                share = pen / 2.0
                ma = min(share * (2 if bb == 0 else 1), ba)
                mb = min(share * (2 if ba == 0 else 1), bb)
                any_move += abs(shift(a, axis, sa * ma))
                any_move += abs(shift(b, axis, -sa * mb))
                break
        log_rounds.append({"round": rnd, "clips": len(clips),
                           "moved_m": round(any_move, 3),
                           "rotated": n_rot_round})
        if not clips or any_move < PITCH / 2:
            break

    # ---- MINIMAL-CLIP PASS (user ruling 2026-08-11C, R-S2-115) --------
    # "Clipping is allowed, but it must be MINIMAL â€” and not because a
    # pair is layered on purpose; even paired meshes clip minimally."
    # The loop above stops at EQUILIBRIUM: in a crowded wall row the
    # pen/2 pushes cancel and a clip survives at whatever depth the
    # stall left it. This pass takes every surviving clip, deepest
    # first, and grinds it down by single 2 cm lattice steps of either
    # item along its UNLOCKED axes â€” a step is kept only when it
    # STRICTLY shrinks this pair's intersection and deepens no other
    # pair beyond where it already is (the try_rotate third-party
    # guard, cell-exact). Strictly decreasing and step-capped, so it
    # terminates; what remains after it is the lock-constrained
    # minimum, not a stall.
    MC_STEPS = 40       # cap per pair per sweep: 40 cells = 0.8 m slide
    MC_TOTAL_CAP = 600  # cap on accepted steps overall â€” a runaway stop,
    #                     far above what a room's wall rows need
    MC_SWEEPS = 8       # a sweep re-ranks the pairs so a hand-off (door
    #                     pushed the window) gets its own turn to move on

    def pair_n(i, k):
        ov = (np.minimum(aabb[i][1], aabb[k][1])
              - np.maximum(aabb[i][0], aabb[k][0]))
        if (ov <= 0).any():
            return 0
        return len(np.intersect1d(cells[i], cells[k]))

    def mover_total(i):
        """Total intersection cells of every clip involving i. Only i
        moves in a trial, so the GLOBAL clip total changes by exactly
        this number's change â€” net acceptance needs nothing else."""
        return sum(pair_n(i, k) for k in ids
                   if k != i and k not in flat)

    mc_log = {}
    mc_total = 0
    for _sweep in range(MC_SWEEPS):
        improved = False
        mc_pairs = sorted(((pair_n(a, b), a, b)
                           for ai in range(len(ids))
                           for a in [ids[ai]] if a not in flat
                           for b in ids[ai + 1:] if b not in flat),
                          key=lambda t: -t[0])
        for n0, a, b in mc_pairs:
            if n0 <= ALLOW_CELLS:
                continue
            steps = 0
            while (pair_n(a, b) > ALLOW_CELLS and steps < MC_STEPS
                   and mc_total < MC_TOTAL_CAP):
                # NET-TOTAL acceptance (the crowded-row lesson): a step
                # may deepen a neighbour's clip â€” the door hands its
                # overlap to the panel â€” as long as the mover's TOTAL
                # strictly falls. A strict no-worsening guard froze
                # whole wall rows solid; net descent lets the row
                # shuffle along and still terminates (the total is a
                # non-negative integer and every step decreases it).
                best = None                  # (delta, i, axis, sgn)
                for i in (a, b):
                    before = mover_total(i)
                    for axis in (0, 2, 1):
                        for sgn in (+1, -1):
                            if budget(i, axis, sgn) < PITCH:
                                continue
                            if shift(i, axis, sgn * PITCH) == 0.0:
                                continue
                            delta = mover_total(i) - before
                            shift(i, axis, -sgn * PITCH)   # revert trial
                            if delta < 0 and (best is None
                                              or delta < best[0]):
                                best = (delta, i, axis, sgn)
                if best is None:
                    break                    # lock-constrained minimum
                _, i, axis, sgn = best
                shift(i, axis, sgn * PITCH)
                improved = True
                steps += 1
                mc_total += 1
                key = f"{a}~{b}"
                e = mc_log.setdefault(key, {"a": a, "b": b,
                                            "cells_before": int(n0),
                                            "cells_after": None,
                                            "steps": 0})
                e["steps"] += 1
        if not improved:
            break
    for e in mc_log.values():
        e["cells_after"] = int(pair_n(e["a"], e["b"]))
    mc_log = sorted(mc_log.values(), key=lambda e: -e["cells_before"])

    # residual clips after the loop (still on the lattice model)
    residual = []
    for ai in range(len(ids)):
        a = ids[ai]
        for b in ids[ai + 1:]:
            if a in flat or b in flat:
                continue
            ov = (np.minimum(aabb[a][1], aabb[b][1])
                  - np.maximum(aabb[a][0], aabb[b][0]))
            if (ov <= 0).any():
                continue
            n = len(np.intersect1d(cells[a], cells[b],
                                   assume_unique=True))
            if n > ALLOW_CELLS:
                residual.append({"a": a, "b": b,
                                 "overlap_l": round(
                                     n * PITCH ** 3 * 1000, 2)})

    # ---- apply to the GLB (render-frame moves -> raw frame) ----
    gpath = cdir / "fitted_preview.glb"
    sc = trimesh.load(gpath, force="scene")
    n_applied = 0
    for gname, geom in sc.geometry.items():
        oid = gname.rsplit("_t", 1)[0]
        mv = moved.get(oid)
        if mv is None or (not mv.any() and not yaw.get(oid, 0.0)):
            continue
        dy = yaw.get(oid, 0.0)
        if dy:
            # yaw about the item's own vertical axis, in the RAW frame the
            # glb lives in, so it spins in place rather than orbiting
            c = geom.bounds.mean(axis=0)
            t = np.radians(dy) * float(r2r[0]) * float(r2r[2])
            co, si = np.cos(t), np.sin(t)
            R = np.eye(4)
            R[0, 0], R[0, 2] = co, si
            R[2, 0], R[2, 2] = -si, co
            geom.apply_translation(-c)
            geom.apply_transform(R)
            geom.apply_translation(c)
        geom.apply_translation([mv[0] * float(r2r[0]),
                                mv[1] * float(r2r[1]),
                                mv[2] * float(r2r[2])])
        n_applied += 1
    gpath.write_bytes(sc.export(file_type="glb"))
    for p in fpj["placed"]:
        mv = moved.get(p["id"])
        p["declip_move_m"] = ([round(float(v), 3) for v in mv]
                              if mv is not None and mv.any() else None)
        if p["id"] in aabb:
            blo, bhi = box_iv[p["id"]]
            lo, hi = aabb[p["id"]]
            oob = max(max(0.0, blo[a] - lo[a], hi[a] - bhi[a])
                      for a in (0, 1, 2))
            p["out_of_box_mm"] = round(float(oob) * 1000, 0)
        p["declip_yaw_deg"] = (round(float(yaw[p["id"]]), 1)
                               if yaw.get(p["id"]) else None)
    fpj["note"] = fpj.get("note", "") + "; declip applied " + str(
        date.today())
    (cdir / "fitted_preview.json").write_text(
        json.dumps(fpj, indent=1), encoding="utf-8")

    n_moved = sum(1 for m in moved.values() if m.any())
    out = {"scene": args.scene, "built": str(date.today()),
           "generated_by": "compose/fit_declip.py",
           "graph_fingerprint": paths.graph_fingerprint(args.scene),
           "note": "position-based declip; static shell; moves "
                   "quantized to the 2 cm lattice; flat items exempt; "
                   "minimal-clip pass grinds every surviving clip to its "
                   "lock-constrained minimum (user ruling 2026-08-11C: "
                   "clipping allowed but MINIMAL, paired or not); "
                   "verify with compose/fit_check.py",
           "params": {"tol_m": TOL_M, "flat_h": FLAT_H,
                      "pitch_m": PITCH, "max_rounds": MAX_ROUNDS,
                      "mc_steps": MC_STEPS},
           "rounds": log_rounds,
           "minimal_clip": mc_log,
           "moves": {i: [round(float(v), 3) for v in m]
                     for i, m in sorted(moved.items()) if m.any()},
           "flat_exempt": sorted(flat),
           "yaws_deg": {i: round(float(v), 1)
                        for i, v in sorted(yaw.items()) if v},
           "rotation_rule": "minimise translation; a bounded yaw is free "
                            "in that ranking, so it is taken whenever it "
                            "clears a clip with ZERO translation. Bounds: "
                            f"|yaw| < {YAW_MAX} deg (a larger yaw would "
                            "change the cardinal facing the placement "
                            "stage snapped to) and, where a witness "
                            f"observed the item, within {FACE_TOL_DEG} "
                            "deg of that. Floor-mounted, non-flat only.",
           "residual_clips": residual,
           "elapsed_s": round(time.time() - t0, 1)}
    (cdir / "fit_declip.json").write_text(json.dumps(out, indent=1),
                                          encoding="utf-8")
    n_rot = sum(1 for v in yaw.values() if v)
    print(f"[declip] {len(log_rounds)} rounds, {n_moved} items moved, "
          f"{n_rot} rotated, "
          f"{len(residual)} residual clips, {len(flat)} flat-exempt "
          f"({time.time() - t0:.0f}s)")
    for i, m in sorted(moved.items()):
        if m.any():
            print(f"  MOVE {i:14s} {str(place[i]['name']):22s} "
                  f"x {m[0] * 1000:+5.0f}mm  y {m[1] * 1000:+5.0f}mm  "
                  f"z {m[2] * 1000:+5.0f}mm")
    for r in residual:
        print(f"  STUCK {r['a']} x {r['b']}  {r['overlap_l']} L")


if __name__ == "__main__":
    main()
