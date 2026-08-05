"""
FIT DECLIP (2026-08-04, user design: "jiggle it until it doesn't clip
-- like in a 3D game things bounce away from each other", with the
rule "the wall/floor/ceiling is STATIC"): deterministic position-based
penetration resolution over the placed preview meshes.

Per relaxation round, every clipping pair (real-mesh voxel overlap on
the 2 cm lattice, ≤4 shared cells = contact) generates a push-apart
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
                       CONTACT_CELLS)

TOL_M = 0.02      # slack around the fit box a mesh may use
FLAT_H = 0.06     # items shorter than this never participate in clips
HUG_M = 0.30      # floor item starting this close to a wall keeps it
                  # (same constant as the facing ladder's wall-hug)
MAX_ROUNDS = 60

KX, KY, KZ = 1 << 42, 1 << 21, 1
KSHIFT = {0: KX, 1: KY, 2: KZ}


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
    observed = {}
    for jn in graph.get("judged", {}).get("nodes", []):
        wd = ((jn.get("appearance") or {}).get("facing") or {})\
            .get("world_dir")
        if wd:
            observed[jn["id"]] = (wd[0] * float(r2r[0]),
                                  wd[1] * float(r2r[2]))

    ids = sorted(by_item)
    cells = {i: cell_keys(by_item[i]).copy() for i in ids}
    aabb = {i: np.array(by_item[i].bounds) for i in ids}
    moved = {i: np.zeros(3) for i in ids}          # metres, (x, y, z)
    flat = {i for i in ids
            if (aabb[i][1][1] - aabb[i][0][1]) < FLAT_H}

    # per-item allowed interval per horizontal axis (box +- TOL_M);
    # wall items locked on their wall-normal axis
    lock = {i: set() for i in ids}
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
        # wall-adjacency lock: starting-pose mesh edge within HUG_M of
        # a wall -> that wall's normal axis is frozen for this item
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
                    lock[i].add(axis)

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
        return d

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
                if len(inter) <= CONTACT_CELLS:
                    continue
                clips.append((len(inter), a, b, inter))
        clips.sort(key=lambda c: (-c[0], c[1], c[2]))
        for _, a, b, inter in clips:
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
                           "moved_m": round(any_move, 3)})
        if not clips or any_move < PITCH / 2:
            break

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
            if n > CONTACT_CELLS:
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
        if mv is None or not mv.any():
            continue
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
                   "verify with compose/fit_check.py",
           "params": {"tol_m": TOL_M, "flat_h": FLAT_H,
                      "pitch_m": PITCH, "max_rounds": MAX_ROUNDS},
           "rounds": log_rounds,
           "moves": {i: [round(float(v), 3) for v in m]
                     for i, m in sorted(moved.items()) if m.any()},
           "flat_exempt": sorted(flat),
           "residual_clips": residual,
           "elapsed_s": round(time.time() - t0, 1)}
    (cdir / "fit_declip.json").write_text(json.dumps(out, indent=1),
                                          encoding="utf-8")
    print(f"[declip] {len(log_rounds)} rounds, {n_moved} items moved, "
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
