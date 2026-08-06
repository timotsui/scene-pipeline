"""SUB ROUNDS — CP6: SUB-JIGGLE (fit_declip at depth 1; canon SR8).

The fit loop's PH2·2 re-entering one support level down, same rules
re-bound (PLAN_FIT_LOOP rule 8 → boards):
  - static shell = the sub's BOARD rect (1 cm inset) — x/z clamped
    inside it, y LOCKED to the board (verticality is scene data);
  - bounce-apart: overlapping same-board siblings split the
    separation half/half along the axis of least overlap, moves
    quantized to the 5 mm lattice; a sibling pinned at the board edge
    hands its share to the partner;
  - boxes are seeds not cages: the applied move per sub is RECORDED
    (jiggle_move_m), residual overlaps reported honestly;
  - a sub wider than its board (footprint_wider flags) stays centered
    and exempt (the rug rule's cousin) — recorded, not resolved.

Reads cp5_final placements + subs_preview.glb; whole k-tile groups
move rigidly. Writes cp6/ — placements_jiggled.json, jiggled glb,
before/after renders, review page (USER GATE).

  python sub_round_cp6.py [--scene bedroom_marble] [--anchor obj_043]
"""
import argparse
import html
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw

HERE = Path(__file__).parent
EG = HERE.parent
sys.path.insert(0, str(EG))
sys.path.insert(0, str(EG / "compose"))

import paths                                     # noqa: E402
sys.path.insert(0, str(paths.REPO_ROOT / "composition"))
from place import look_at_pose                   # noqa: E402
import rotation_check as rc                      # noqa: E402

SHOT = EG / "rendertools" / "shot.py"
RES = 1024          # shot.py blank above 1024 px (CP1 finding)
INSET = 0.01        # m; board-edge inset (the CP3 constant)
LATTICE = 0.005     # m; move quantum (declip's lattice, halved scale)
GAP = 0.005         # m; separation added beyond touching
MAX_IT = 120

BOARD_COLORS = [(63, 191, 111), (255, 157, 61), (74, 144, 217),
                (217, 119, 74), (191, 63, 127), (170, 170, 60),
                (120, 200, 200), (200, 120, 200)]


def vec(a):
    return ",".join(f"{(v if v != 0 else 0.0):.4f}" for v in a)


def proj(pose, fov_deg, res, pts):
    inv = np.linalg.inv(pose)
    f = 1.0 / np.tan(np.radians(fov_deg) / 2.0)
    uv = []
    for p in pts:
        pc = (inv @ np.append(np.asarray(p, float), 1.0))[:3]
        z = -pc[2]
        uv.append(None if z <= 1e-6 else
                  (((pc[0] / z) * f + 1.0) / 2.0 * res,
                   (1.0 - (pc[1] / z) * f) / 2.0 * res))
    return uv


def splat_shot(out_png, eye, look, up, fov, clip, ply, gpu="0", res=RES):
    tmp = out_png.with_suffix(".webp")
    subprocess.run(
        [sys.executable, str(SHOT), vec(eye), vec(look), f"--up={vec(up)}",
         f"--fov={fov:.3f}", f"--box={clip}", f"--res={res}x{res}",
         f"--ply={ply}", f"--gpu={gpu}", f"--out={tmp}", "--no-open"],
        check=True, stdout=subprocess.DEVNULL)
    if tmp.stat().st_size < 30_000:
        raise RuntimeError(f"suspiciously small splat render: {tmp}")
    img = Image.open(tmp).convert("RGB")
    tmp.unlink()
    return img


def meshes_rgba(meshes, eye, look, up, fov, res, alpha=1.0):
    orig = rc.look_at_pose

    def patched(e, t, _u):
        return orig(np.asarray(e, float), np.asarray(t, float),
                    np.asarray(up, float))
    rc.look_at_pose = patched
    try:
        img = rc.render_object_rgba(meshes, eye, look, fov, res)
    finally:
        rc.look_at_pose = orig
    if alpha < 1.0:
        a = np.asarray(img, np.uint8).copy()
        a[:, :, 3] = (a[:, :, 3].astype(np.float32) * alpha).astype(
            np.uint8)
        img = Image.fromarray(a, "RGBA")
    return img


def overlaps_of(items):
    out = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, b = items[i], items[j]
            if a["board"] != b["board"]:
                continue
            o = np.minimum(a["hi"], b["hi"]) - np.maximum(a["lo"], b["lo"])
            if (o > 0).all():
                out.append((i, j, o))
    return out


def q(v):
    return round(round(v / LATTICE) * LATTICE, 4)


def triage(items, boards, asg):
    """SR9 — CAPACITY TRIAGE before any jiggle (user: 'if something's
    total length simply isn't possible, kill or walk the objects').

    Deterministic, no cycles possible afterwards:
      1. per board: excess = items + gaps - span;
      2. while excess: EVICT the item whose OBSERVED height is
         furthest from this board (the height-collapse victim — it
         least belongs here); wide-exempt items are never evicted;
      3. SPILL target = the board with spare room nearest the
         evictee's observed height (bottom re-snapped, y recorded);
      4. no board has room -> KILL: adds drop silently, detections
         drop with the anchor-level complaint ('stand-in
         under-capacity') — the future anchor-walk feedback.
    Returns (spills, kills); killed items are removed from `items`.
    """
    brect = {b["board"]: b for b in boards}

    def long_ax(b):
        return 0 if (b["x"][1] - b["x"][0]) >= (b["z"][1] - b["z"][0]) \
            else 2

    def usable(b):
        k = "x" if long_ax(b) == 0 else "z"
        return (b[k][1] - b[k][0]) - 2 * INSET

    def demand(group, ax):
        return (sum(g["sz"][ax] for g in group)
                + GAP * max(0, len(group) - 1))

    obs_h = {r["id"]: r.get("seed_bottom_y") for r in asg}
    spills, kills = [], []
    by_board = {}
    for it in items:
        by_board.setdefault(it["board"], []).append(it)

    tile_drops = []
    for bid in sorted(by_board, key=lambda b: -len(by_board[b])):
        b = brect[bid]
        ax = long_ax(b)
        group = by_board[bid]
        # PASS 0 — TILE REDUCTION (user: "multi sub fills one box —
        # we don't have to kill the entire box"): a k-tiled row
        # sheds copies one at a time (from the high end), never
        # below 1. Frees the most length per decision, loses the
        # least content.
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
            # spill target: nearest-height board with room for it
            tgt = None
            for cb in sorted(boards,
                             key=lambda c: abs(c["y"] - (obs_h.get(
                                 ev["id"]) or c["y"]))):
                if cb["board"] == bid:
                    continue
                cg = by_board.setdefault(cb["board"], [])
                axc = long_ax(cb)
                if (demand(cg + [ev], axc) <= usable(cb)
                        and ev["sz"][0] <= (cb["x"][1] - cb["x"][0])
                        and ev["sz"][2] <= (cb["z"][1] - cb["z"][0])):
                    tgt = cb
                    break
            if tgt is None:
                kills.append({"id": ev["id"],
                              "from_board": bid,
                              "why": "no board has room"})
                ev["killed"] = True
                continue
            dy = tgt["y"] - ev["lo"][1]
            _shift(ev, 1, dy)
            # xz: keep seed, clamp into the target rect
            for axi, key in ((0, "x"), (2, "z")):
                half = ev["sz"][axi] / 2
                lo_e, hi_e = tgt[key][0] + INSET, tgt[key][1] - INSET
                dv = float(np.clip(ev["c"][axi], lo_e + half,
                                   hi_e - half) - ev["c"][axi])
                _shift(ev, axi, q(dv))
            ev["board"] = tgt["board"]
            by_board[tgt["board"]].append(ev)
            spills.append({"id": ev["id"], "from_board": bid,
                           "to_board": tgt["board"],
                           "dy_m": round(float(dy), 3)})
    items[:] = [g for g in items if not g.get("killed")]
    return tile_drops, spills, kills


def _shift(g, ax, dv):
    if not dv:
        return
    g["c"][ax] += dv
    g["lo"][ax] += dv
    g["hi"][ax] += dv
    g["move"][ax] += dv


def jiggle(items, boards):
    """per-board 1D LEGALIZATION -> (n_boards_done, over_capacity).

    The bounce-apart form oscillated (pairwise feasibility ignored
    the third object: separating basket×row shoved the row into its
    neighbor). This is the deterministic version: per board, sort by
    center along the board's LONG axis and sweep twice (left-to-right
    pushing right, then right-to-left pulling back inside the edge) —
    minimal-ish moves, order preserved, converges by construction.
    The short axis just clamps each item into the board depth.

    A board whose items + gaps EXCEED its span is OVER_CAPACITY as a
    whole: recorded untouched — that is walk-class work (relocate /
    re-shop), not jiggle work. obj_043's B5 (basket + 2 book rows =
    1.80 m on 1.53 m, a short-stand-in artifact) lands there."""
    brect = {b["board"]: b for b in boards}
    over_capacity = []
    done = 0
    by_board = {}
    for idx, it in enumerate(items):
        by_board.setdefault(it["board"], []).append(it)

    for bid, group in by_board.items():
        b = brect[bid]
        ax = 0 if (b["x"][1] - b["x"][0]) >= (b["z"][1] - b["z"][0]) \
            else 2
        key = "x" if ax == 0 else "z"
        lo_e, hi_e = b[key][0] + INSET, b[key][1] - INSET
        need = sum(g["sz"][ax] for g in group) \
            + GAP * max(0, len(group) - 1)
        if need > (hi_e - lo_e):
            over_capacity.append({"board": bid,
                                  "need_m": round(float(need), 3),
                                  "span_m": round(float(hi_e - lo_e),
                                                  3),
                                  "items": [g["id"] for g in group]})
            continue
        group.sort(key=lambda g: g["c"][ax])
        # pass 1: left -> right, push right so nothing overlaps
        prev_end = lo_e
        for g in group:
            half = g["sz"][ax] / 2
            tgt = max(g["c"][ax], prev_end + half)
            _move(g, ax, q(tgt - g["c"][ax]))
            prev_end = g["c"][ax] + half + GAP
        # pass 2: right -> left, pull back inside the far edge
        next_start = hi_e
        for g in reversed(group):
            half = g["sz"][ax] / 2
            tgt = min(g["c"][ax], next_start - half)
            _move(g, ax, q(tgt - g["c"][ax]))
            next_start = g["c"][ax] - half - GAP
        # short axis: independent clamp into the board depth
        ax2 = 2 if ax == 0 else 0
        key2 = "x" if ax2 == 0 else "z"
        lo2, hi2 = b[key2][0] + INSET, b[key2][1] - INSET
        for g in group:
            half = g["sz"][ax2] / 2
            if hi2 - lo2 < g["sz"][ax2]:
                continue                     # deeper than the board:
            tgt = np.clip(g["c"][ax2], lo2 + half, hi2 - half)
            _move(g, ax2, q(tgt - g["c"][ax2]))
        done += 1
    return done, over_capacity


def _move(g, ax, dv):
    if not dv or g["exempt"]:
        return
    g["c"][ax] += dv
    g["lo"][ax] += dv
    g["hi"][ax] += dv
    g["move"][ax] += dv


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--anchor", default="obj_043")
    ap.add_argument("--gpu", default="0")
    a = ap.parse_args()

    cdir = paths.compose_dir(a.scene)
    man = json.loads(paths.manifest(a.scene).read_text(encoding="utf-8"))
    floor_r = float(man["frame"]["floor_y"]) * -1.0
    sdir = cdir / "sub_experiment" / a.anchor
    pl = json.loads((sdir / "cp5_final" / "placements.json")
                    .read_text("utf-8"))
    brec = json.loads((sdir / "cp2" / "boards.json").read_text("utf-8"))
    # SR10 at the source (user 08-07): underside boards are plank
    # CEILINGS — never triage/spill targets (cp6 was re-introducing
    # riders onto them after cp3 stopped seeding there)
    boards = [b for b in brec["boards"] if "underside_of" not in b]
    placed = [r for r in pl["subs"] if r["status"] == "PLACED"]

    odir = sdir / "cp6"
    odir.mkdir(parents=True, exist_ok=True)

    if not placed:
        rec = {"scene": a.scene, "anchor": a.anchor, "n_placed": 0,
               "note": "nothing placed at cp5 — jiggle idle"}
        (odir / "placements_jiggled.json").write_text(
            json.dumps(rec, indent=1), encoding="utf-8")
        for f in ("front.png", "before.png", "topdown.png"):
            p = odir / f
            if p.exists():
                p.unlink()
        (odir / "index.html").write_text(
            "<!doctype html><meta charset='utf-8'><body style="
            "'background:#141414;color:#e8e8e8;font:15px system-ui'>"
            f"<p>{a.anchor}: nothing placed at cp5 — jiggle idle.</p>",
            encoding="utf-8")
        print(f"[cp6] {a.anchor}: nothing placed, idle")
        return

    # cp3 wider-than-board exemptions
    asg = {r["id"]: r for r in json.loads(
        (sdir / "cp3" / "assignment.json").read_text("utf-8"))["subs"]}

    items = []
    for r in placed:
        lo = np.asarray(r["bounds_render"]["lo"], np.float64)
        hi = np.asarray(r["bounds_render"]["hi"], np.float64)
        wide = any(f.startswith("footprint_wider")
                   for f in (asg.get(r["id"], {}).get("flags") or []))
        items.append({"id": r["id"], "board": r["board"],
                      "lo": lo, "hi": hi, "c": (lo + hi) / 2,
                      "sz": hi - lo, "move": [0.0, 0.0, 0.0],
                      "k": r.get("k", 1),
                      "tile_axis": r.get("tile_axis", 0),
                      "tiles_dropped": 0,
                      "exempt": wide})
    before = len(overlaps_of(items))
    tile_drops, spills, kills = triage(
        items, boards,
        json.loads((sdir / "cp3" / "assignment.json")
                   .read_text("utf-8"))["subs"])
    iters, over_cap = jiggle(items, boards)
    after_ovl = overlaps_of(items)

    rows = []
    for it in items:
        rows.append({"id": it["id"], "board": it["board"],
                     "jiggle_move_m": [round(v, 3)
                                       for v in it["move"]],
                     "tiles_dropped": it["tiles_dropped"],
                     "exempt_wide": it["exempt"],
                     "bounds_render": {"lo": it["lo"].round(3).tolist(),
                                       "hi": it["hi"].round(3).tolist()}})
    rec = {"scene": a.scene, "anchor": a.anchor,
           "n_placed": len(items), "boards_legalized": iters,
           "overlap_pairs_before": before,
           "overlap_pairs_after": len(after_ovl),
           "tile_drops": tile_drops, "spills": spills, "kills": kills,
           "over_capacity_boards": over_cap,
           "residual": [{"a": items[i]["id"], "b": items[j]["id"],
                         "overlap_m": o.round(3).tolist()}
                        for i, j, o in after_ovl],
           "subs": rows}
    (odir / "placements_jiggled.json").write_text(
        json.dumps(rec, indent=1), encoding="utf-8")

    # ---- apply deltas to the cp5 meshes (whole k-groups, rigid);
    # killed subs and dropped tiles (highest indices) are omitted
    to_render = np.diag([-1.0, -1.0, 1.0, 1.0])
    move_of = {it["id"]: it["move"] for it in items}
    keep_k = {it["id"]: it["k"] - it["tiles_dropped"] for it in items}
    gsc = trimesh.load(sdir / "cp5_final" / "subs_preview.glb",
                       force="scene")
    sub_meshes = []
    out_sc = trimesh.Scene()
    # geometry dict keys are NOT our node names (trimesh renames) —
    # walk the scene graph, where the cp5 node names survive
    for node in gsc.graph.nodes_geometry:
        T, gname = gsc.graph[node]
        base = node.rsplit("_t", 1)
        sid = base[0]
        ti = int(base[1]) if len(base) == 2 and base[1].isdigit() else 0
        if sid not in move_of:
            continue                          # killed at triage
        if ti >= keep_k.get(sid, 99):
            continue                          # dropped tile
        m = gsc.geometry[gname].copy()
        if T is not None:
            m.apply_transform(T)
        m.apply_transform(to_render)          # raw -> render
        mv = move_of[sid]
        m.apply_translation([mv[0], mv[1], mv[2]])
        sub_meshes.append(m)
        mr = m.copy()
        mr.apply_transform(to_render)         # render -> raw (self-inv)
        out_sc.add_geometry(mr, node_name=node)
    (odir / "subs_jiggled.glb").write_bytes(
        out_sc.export(file_type="glb"))

    # anchor meshes for the ghost
    fsc = trimesh.load(cdir / "fitted_preview.glb", force="scene")
    anchor_meshes = []
    for gname, geom in fsc.geometry.items():
        if gname.rsplit("_t", 1)[0] == a.anchor:
            m = geom.copy()
            m.apply_transform(to_render)
            anchor_meshes.append(m)

    # ---- front render (same framing as cp5)
    allb = [np.vstack([m.bounds for m in anchor_meshes])]
    allb.append(np.vstack([m.bounds for m in sub_meshes]))
    P = np.vstack(allb)
    lo_all, hi_all = P.min(0), P.max(0)
    ctr = (lo_all + hi_all) / 2
    span = float(max(hi_all - lo_all))
    fp = json.loads((cdir / "fitted_preview.json").read_text("utf-8"))
    fdr = next((p.get("front_dir_raw") for p in fp["placed"]
                if p["id"] == a.anchor), None) or [0.0, -1.0]
    r2r = np.asarray(man["frame"].get("raw_to_render", [1, 1, 1]),
                     np.float64)
    fdir = np.array([fdr[0] * r2r[0], 0.0, fdr[1] * r2r[2]])
    n = np.linalg.norm(fdir)
    fdir = fdir / n if n > 1e-6 else np.array([0.0, 0.0, -1.0])
    dist = max(2.4, span * 1.1)
    eye = ctr + fdir * dist
    eye[1] = ctr[1] + 0.15
    fov = float(np.clip(np.degrees(2 * np.arctan2(span * 0.62, dist)),
                        25, 95))
    clip = (f"{lo_all[0]-1.2:.3f},{floor_r-0.25:.3f},{lo_all[2]-1.2:.3f},"
            f"{hi_all[0]+1.2:.3f},{hi_all[1]+0.5:.3f},{hi_all[2]+1.2:.3f}")
    img = splat_shot(odir / "front.png", eye, ctr, np.array([0., 1., 0.]),
                     fov, clip, paths.ply(a.scene), gpu=a.gpu
                     ).convert("RGBA")
    img.alpha_composite(meshes_rgba(anchor_meshes, eye, ctr,
                                    np.array([0., 1., 0.]), fov, RES,
                                    alpha=0.30))
    if sub_meshes:
        img.alpha_composite(meshes_rgba(sub_meshes, eye, ctr,
                                        np.array([0., 1., 0.]), fov,
                                        RES))
    img.convert("RGB").save(odir / "front.png")

    build_page(odir, rec)
    print(f"[cp6] {a.anchor}: {before} -> {len(after_ovl)} overlap "
          f"pairs in {iters} iterations")
    print(f"[cp6] wrote {odir / 'index.html'}")


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
    h = ['<!doctype html><meta charset="utf-8">',
         f'<title>sub rounds CP6 — jiggle — {rec["anchor"]}</title>',
         f'<style>{css}</style><div class="wrap">',
         '<h1>Sub rounds — CP6: sub-jiggle (declip at depth 1)</h1>',
         f'<p class="sub">{rec["scene"]} · anchor {rec["anchor"]} · '
         f'{rec["n_placed"]} placed · {rec["overlap_pairs_before"]} '
         f'&rarr; {rec["overlap_pairs_after"]} overlap pairs · '
         f'{rec["boards_legalized"]} boards legalized</p>',
         '<div class="contract">'
         '<b>What this step gets:</b> the cp5 placements (whole k-tile '
         'groups) and their boards.<br>'
         '<b>What it decides:</b> minimal on-board slides that separate '
         'same-board siblings — bounce-apart half/half along the axis '
         'of least overlap, y locked, clamped inside the board, moves '
         'on the 5 mm lattice, all recorded.<br>'
         '<b>What a mistake looks like:</b> a book pushed off its '
         'board, an unresolved overlap not in the residual table, or '
         'a wide-exempt item moved.</div>']
    h.append('<div class="imgs">'
             '<div><img src="../cp5_final/front.png"><p class="cap">'
             '<b>BEFORE</b> — cp5 as placed</p></div>'
             '<div><img src="front.png"><p class="cap"><b>AFTER</b> — '
             'jiggled</p></div></div>')
    h.append('<table><tr><th>sub</th><th>board</th>'
             '<th>move x·y·z m</th><th>tiles dropped</th>'
             '<th>exempt</th></tr>')
    for r in rec["subs"]:
        mv = r["jiggle_move_m"]
        h.append(f'<tr><td>{r["id"]}</td>'
                 f'<td class="mono">B{r["board"]}</td>'
                 f'<td class="mono">{mv[0]:+.3f} · {mv[1]:+.3f} · '
                 f'{mv[2]:+.3f}</td>'
                 f'<td class="mono">{r["tiles_dropped"] or "—"}</td>'
                 f'<td>{"wide" if r["exempt_wide"] else "—"}</td></tr>')
    h.append('</table>')
    if rec.get("tile_drops"):
        h.append('<div class="note"><b>Tile reduction (SR9 pass 0 — '
                 'a k-tiled row sheds copies, never the whole box):'
                 '</b> ' + " · ".join(
                     f'{t["id"]} −1 tile ({t["freed_m"]} m) on '
                     f'B{t["board"]}' for t in rec["tile_drops"])
                 + '</div>')
    if rec.get("spills"):
        h.append('<div class="note"><b>Spills (evicted to the '
                 'nearest-height board with room):</b> ' + " · ".join(
                     f'{s["id"]} B{s["from_board"]}→B{s["to_board"]} '
                     f'(dy {s["dy_m"]:+.2f})' for s in rec["spills"])
                 + '</div>')
    if rec.get("kills"):
        h.append('<div class="note"><b>Kills (no board has room — '
                 'the anchor-walk complaint):</b> ' + " · ".join(
                     f'{k["id"]} (was B{k["from_board"]})'
                     for k in rec["kills"]) + '</div>')
    if rec.get("over_capacity_boards"):
        h.append('<div class="note"><b>OVER CAPACITY (not a jiggle '
                 'problem):</b> these boards hold more than they can '
                 'fit — usually the stand-in being smaller than the '
                 'real shelf. Left untouched; resolution = walk-class '
                 '(relocate to a board with room / re-shop), '
                 'queued.</div>')
        h.append('<table><tr><th>board</th><th>need</th><th>span</th>'
                 '<th>items</th></tr>')
        for o in rec["over_capacity_boards"]:
            h.append(f'<tr><td class="mono">B{o["board"]}</td>'
                     f'<td class="mono">{o["need_m"]} m</td>'
                     f'<td class="mono">{o["span_m"]} m</td>'
                     f'<td class="mono">{", ".join(o["items"])}</td>'
                     '</tr>')
        h.append('</table>')
    if rec["residual"]:
        h.append('<table><tr><th>residual pair</th>'
                 '<th>overlap m</th></tr>')
        for o in rec["residual"]:
            h.append(f'<tr><td class="mono">{o["a"]} × {o["b"]}</td>'
                     f'<td class="mono">{o["overlap_m"]}</td></tr>')
        h.append('</table>')
    h.append('<div class="note"><b>Gate question (one look):</b> same '
             'books, same boards, no more interpenetration — and '
             'nothing shoved off an edge?</div>')
    h.append('<div id="lb"><img></div>')
    h.append(f'<script>{js}</script></div>')
    (odir / "index.html").write_text("\n".join(h), encoding="utf-8")


if __name__ == "__main__":
    main()
