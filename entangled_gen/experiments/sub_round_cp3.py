"""SUB ROUNDS — CP3: BOARD ASSIGNMENT + SEED CLAMP (isolated, obj_043).

Marries CP1 to CP2: each sub's seed (CP1, where the search starts) is
assigned to one of the fitted anchor's real boards (CP2) and clamped so
its footprint starts inside that board. Pure geometry, no judge.

Rules:
  1. BOARD = nearest by |seed bottom - board height| (the observed
     bottom already sat ~4 cm above its board on this anchor);
  2. Y SNAP: start bottom ON the board (the fit loop's mesh-flush
     contract, applied to boards);
  3. XZ CLAMP: seed center moved the minimum distance that puts the
     sub's footprint inside the board rect (1 cm inset); footprints
     wider than the board get centered + flagged;
  4. HEADROOM: sub taller than the gap to the next board -> flagged
     (placement may need a different board or a shorter candidate;
     the top surface has no ceiling and never flags).

Flags are RECORDED, not resolved — resolution is CP5's job (user
ruling: the search starts at the seed, with a large margin).

Outputs (out/<scene>/compose/sub_experiment/cp3/):
  assignment.json  per sub: board, y snap, clamp move, flags, start box
  front.png / topdown.png   splat + boards + seed->start moves
  index.html       review page (USER GATE)

  python sub_round_cp3.py [--scene bedroom_marble] [--anchor obj_043]
"""
import argparse
import html
import json
import subprocess
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).parent
EG = HERE.parent
sys.path.insert(0, str(EG))
sys.path.insert(0, str(EG / "compose"))

import paths                                     # noqa: E402
sys.path.insert(0, str(paths.REPO_ROOT / "composition"))
from place import look_at_pose                   # noqa: E402

SHOT = EG / "rendertools" / "shot.py"
RES = 1024          # shot.py blank above 1024 px (CP1 finding)
INSET = 0.01        # m; footprint kept this far inside the board edge

C_SEED = (63, 191, 111)     # CP1 seed — green
C_START = (120, 200, 255)   # clamped start — light blue
C_FLAG = (255, 90, 90)      # flagged start — red
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


def draw_box(dr, pose, fov, res, lo, hi, color, width=3):
    corners = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
               for z in (lo[2], hi[2])]
    uv = proj(pose, fov, res, corners)
    edges = [(0, 1), (0, 2), (1, 3), (2, 3), (4, 5), (4, 6), (5, 7), (6, 7),
             (0, 4), (1, 5), (2, 6), (3, 7)]
    for a, b in edges:
        if uv[a] and uv[b]:
            dr.line([uv[a], uv[b]], fill=color, width=width)


def draw_rect_at_height(dr, pose, fov, res, x0, x1, z0, z1, y, color, w=3):
    ring = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1), (x0, y, z0)]
    uv = proj(pose, fov, res, ring)
    for a, b in zip(uv, uv[1:]):
        if a and b:
            dr.line([a, b], fill=color, width=w)


def draw_arrow(dr, pose, fov, res, p0, p1, color, width=2):
    uv = proj(pose, fov, res, [p0, p1])
    if uv[0] and uv[1]:
        dr.line([uv[0], uv[1]], fill=color, width=width)
        dr.ellipse([uv[1][0] - 4, uv[1][1] - 4, uv[1][0] + 4, uv[1][1] + 4],
                   fill=color)


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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--anchor", default="obj_043")
    ap.add_argument("--gpu", default="0")
    a = ap.parse_args()

    cdir = paths.compose_dir(a.scene)
    man = {"frame": paths.frame_block(a.scene)}
    r2r = np.asarray(man["frame"].get("raw_to_render", [1, 1, 1]), np.float64)
    floor_r = float(man["frame"]["floor_y"]) * -1.0
    sdir = cdir / "sub_experiment" / a.anchor
    seeds = json.loads((sdir / "cp1" / "seeds.json").read_text("utf-8"))
    brec = json.loads((sdir / "cp2" / "boards.json").read_text("utf-8"))
    boards = brec["boards"]
    # SR10 at the source (user 08-07): an underside board is a plank
    # CEILING, never an assignment target — its rider would sit inside
    # the plank's thickness. clearance_m still reads off the full list,
    # so headroom stays measured to the true ceiling.
    standing = [b for b in boards if "underside_of" not in b]
    if seeds["anchor"] != a.anchor or brec["anchor"] != a.anchor:
        raise SystemExit("cp1/cp2 records are for a different anchor")

    # SR3b — ATTACHMENT-CLASS GATE (08-05C, the window-on-curtain-fold
    # case): a sub whose own observed box sits IN A WALL (thin axis =
    # the wall normal, center within the wall slab) is ARCH-CLASS, not
    # a board rider — it belongs to the wall channel (its observed box
    # IS the correct placement, the relation router put it there).
    # Route recorded, board placement skipped. Wall channel = unwired.
    graph = json.loads((paths.scene_dir(a.scene) / "scene_graph.json")
                       .read_text("utf-8"))
    # canon-drift fix 2026-08-13 (probe on fresh08): the v1 wall ids
    # (arch_wall_x_low..) died with the W5 polygon shell — read the
    # outer planes the way every compose module does (arch_walls).
    sys.path.insert(0, str(EG / "compose"))
    from arch_walls import wall_axis_planes
    xs_raw, zs_raw, _fl, _ce = wall_axis_planes(graph["nodes"])
    wx = sorted((xs_raw[0] * r2r[0], xs_raw[-1] * r2r[0]))
    wz = sorted((zs_raw[0] * r2r[2], zs_raw[-1] * r2r[2]))

    def in_wall(slo, shi):
        c, sz = (slo + shi) / 2, shi - slo
        if sz[0] < 0.2 and min(abs(c[0] - wx[0]), abs(c[0] - wx[1])) < 0.12:
            return "x"
        if sz[2] < 0.2 and min(abs(c[2] - wz[0]), abs(c[2] - wz[1])) < 0.12:
            return "z"
        return None

    rows = []
    for s in seeds["subs"]:
        # Attachment class is a property of the OBSERVATION — the
        # anchor's fitting moves must not drag an embedded item out of
        # its wall (the curtain's -0.13 z wall-flush pulled the seeded
        # window 1 cm past the threshold). Test the OBSERVED box; the
        # seed box is the fallback evidence.
        wall_ax = None
        for key in ("obs_box", "seed_box"):
            rlo = np.asarray(s[key]["lo"], np.float64)
            rhi = np.asarray(s[key]["hi"], np.float64)
            slo_r = np.minimum(rlo * r2r, rhi * r2r)
            shi_r = np.maximum(rlo * r2r, rhi * r2r)
            wall_ax = in_wall(slo_r, shi_r)
            if wall_ax:
                break
        if wall_ax:
            rows.append({"id": s["id"], "name": s["name"],
                         "board": None,
                         "flags": ["NOT_A_BOARD_RIDER"],
                         "route": {"channel": "wall",
                                   "wall_axis": wall_ax,
                                   "box_render":
                                       {"lo": slo_r.round(3).tolist(),
                                        "hi": shi_r.round(3).tolist()}}})
            continue
        if not standing:
            # SR2 honesty: no usable surface on this anchor — record,
            # never force (door/picture anchors land here)
            rows.append({"id": s["id"], "name": s["name"],
                         "board": None, "flags": ["NO_BOARD"]})
            continue
        # CP1 seed boxes are RAW frame (CP1 finding) -> render
        lo = np.asarray(s["seed_box"]["lo"], np.float64)
        hi = np.asarray(s["seed_box"]["hi"], np.float64)
        slo = np.minimum(lo * r2r, hi * r2r)
        shi = np.maximum(lo * r2r, hi * r2r)
        sz = shi - slo

        b = min(standing, key=lambda b: abs(slo[1] - b["y"]))
        # y snap: bottom ON the board
        dy = b["y"] - slo[1]
        # xz clamp into the board rect (footprint-aware)
        flags = []
        c = (slo + shi) / 2
        start_c = c.copy()
        for ax, key in ((0, "x"), (2, "z")):
            lo_e, hi_e = b[key][0] + INSET, b[key][1] - INSET
            half = sz[ax] / 2
            if hi_e - lo_e < sz[ax]:
                start_c[ax] = (lo_e + hi_e) / 2
                flags.append(f"footprint_wider_{key}")
            else:
                start_c[ax] = min(max(c[ax], lo_e + half), hi_e - half)
        clamp_move = float(np.hypot(start_c[0] - c[0], start_c[2] - c[2]))
        # headroom
        if b["clearance_m"] is not None and sz[1] > b["clearance_m"]:
            flags.append("too_tall_for_board")

        start_lo = np.array([start_c[0] - sz[0] / 2, b["y"],
                             start_c[2] - sz[2] / 2])
        start_hi = start_lo + sz
        rows.append({
            "id": s["id"], "name": s["name"], "board": b["board"],
            "board_y": b["y"],
            "seed_bottom_y": round(float(slo[1]), 3),
            "y_snap_m": round(float(dy), 3),
            "clamp_move_m": round(clamp_move, 3),
            "flags": flags,
            "seed_box_render": {"lo": slo.round(3).tolist(),
                                "hi": shi.round(3).tolist()},
            "start_box_render": {"lo": start_lo.round(3).tolist(),
                                 "hi": start_hi.round(3).tolist()},
        })

    odir = sdir / "cp3"
    odir.mkdir(parents=True, exist_ok=True)
    rec = {"scene": a.scene, "anchor": a.anchor,
           "anchor_name": brec.get("anchor_name"),
           "inset_m": INSET, "n_subs": len(rows),
           "n_flagged": sum(1 for r in rows if r["flags"]),
           "boards_used": sorted(b for b in {r["board"] for r in rows}
                                 if b is not None),
           "subs": rows}
    (odir / "assignment.json").write_text(json.dumps(rec, indent=1),
                                          encoding="utf-8")

    rows_ok = [r for r in rows if r.get("start_box_render")]
    if not rows_ok:
        build_page(odir, rec)
        print(f"[cp3] no placeable subs (boards: {len(boards)}) — "
              "record written, renders skipped")
        print(f"[cp3] wrote {odir / 'index.html'}")
        return

    # ---- render views (frame boards + all boxes)
    pts = []
    for b in boards:
        pts += [np.array([b["x"][0], b["y"], b["z"][0]]),
                np.array([b["x"][1], b["y"], b["z"][1]])]
    for r in rows_ok:
        pts += [np.asarray(r["seed_box_render"]["lo"]),
                np.asarray(r["seed_box_render"]["hi"]),
                np.asarray(r["start_box_render"]["lo"]),
                np.asarray(r["start_box_render"]["hi"])]
    P = np.vstack(pts)
    lo_all, hi_all = P.min(0), P.max(0)
    ctr = (lo_all + hi_all) / 2
    span = float(max(hi_all - lo_all))
    ply = paths.ply(a.scene)

    fdr = None
    fp = json.loads((cdir / "fitted_preview.json").read_text("utf-8"))
    for p in fp["placed"]:
        if p["id"] == a.anchor:
            fdr = p.get("front_dir_raw")
    fdir = np.array([(fdr or [0, -1])[0] * r2r[0], 0.0,
                     (fdr or [0, -1])[1] * r2r[2]])
    n = np.linalg.norm(fdir)
    fdir = fdir / n if n > 1e-6 else np.array([0.0, 0.0, -1.0])
    dist = max(2.4, span * 1.1)
    eye_f = ctr + fdir * dist
    eye_f[1] = ctr[1] + 0.15
    fov_f = float(np.clip(np.degrees(2 * np.arctan2(span * 0.62, dist)),
                          25, 95))
    clip = (f"{lo_all[0]-1.2:.3f},{floor_r-0.25:.3f},{lo_all[2]-1.2:.3f},"
            f"{hi_all[0]+1.2:.3f},{hi_all[1]+0.5:.3f},{hi_all[2]+1.2:.3f}")

    half = max(hi_all[0] - lo_all[0], hi_all[2] - lo_all[2]) / 2 * 1.5
    eye_y = hi_all[1] + max(1.5, half / np.tan(np.radians(27.5)))
    fov_t = float(np.clip(np.degrees(2 * np.arctan2(half, eye_y - ctr[1])),
                          25, 100))
    clip_t = (f"{lo_all[0]-1.2:.3f},{floor_r-0.25:.3f},{lo_all[2]-1.2:.3f},"
              f"{hi_all[0]+1.2:.3f},{hi_all[1]+0.15:.3f},{hi_all[2]+1.2:.3f}")

    shots = {
        "front": (eye_f, ctr.copy(), np.array([0.0, 1.0, 0.0]), fov_f, clip),
        "topdown": (np.array([ctr[0], eye_y, ctr[2]]),
                    np.array([ctr[0], floor_r, ctr[2]]),
                    np.array([0.0, 0.0, 1.0]), fov_t, clip_t),
    }
    for name, (e, l, u, fv, cl) in shots.items():
        img = splat_shot(odir / f"{name}.png", e, l, u, fv, cl, ply,
                         gpu=a.gpu)
        dr = ImageDraw.Draw(img)
        pose = look_at_pose(e, l, u)
        for b in boards:
            c = BOARD_COLORS[b["board"] % len(BOARD_COLORS)]
            draw_rect_at_height(dr, pose, fv, RES, b["x"][0], b["x"][1],
                                b["z"][0], b["z"][1], b["y"], c, 2)
        for r in rows_ok:
            slo = np.asarray(r["seed_box_render"]["lo"])
            shi = np.asarray(r["seed_box_render"]["hi"])
            tlo = np.asarray(r["start_box_render"]["lo"])
            thi = np.asarray(r["start_box_render"]["hi"])
            cc = C_FLAG if r["flags"] else C_START
            draw_box(dr, pose, fv, RES, slo, shi, C_SEED, 1)
            draw_box(dr, pose, fv, RES, tlo, thi, cc, 3)
            draw_arrow(dr, pose, fv, RES, (slo + shi) / 2, (tlo + thi) / 2,
                       cc, 2)
        img.save(odir / f"{name}.png")

    build_page(odir, rec)
    print(f"[cp3] {len(rows)} subs -> boards {rec['boards_used']}, "
          f"{rec['n_flagged']} flagged")
    print(f"[cp3] wrote {odir / 'index.html'}")


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
tr.flag td{background:#2a1717}
.key i{font-style:normal;padding:1px 8px;border-radius:3px;margin-right:6px;
       font-size:12.5px}
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
         f'<title>sub rounds CP3 — assignment — {rec["anchor"]}</title>',
         f'<style>{css}</style><div class="wrap">',
         '<h1>Sub rounds — CP3: board assignment + seed clamp</h1>',
         f'<p class="sub">{rec["scene"]} · anchor {rec["anchor"]} '
         f'({html.escape(str(rec["anchor_name"]))}) · {rec["n_subs"]} subs '
         f'· boards used {rec["boards_used"]} · {rec["n_flagged"]} flagged '
         '· pure geometry, no judge</p>',
         '<div class="contract">'
         '<b>What this step gets:</b> CP1&rsquo;s seeds (where each '
         'sub&rsquo;s search starts) and CP2&rsquo;s boards (the real '
         'surfaces of the fitted stand-in).<br>'
         '<b>What it decides:</b> WHICH board each sub starts on, with '
         'its bottom snapped to the board and its footprint clamped '
         'inside it. Flags (too tall / too wide) are recorded, not '
         'resolved — that is the placement round&rsquo;s job.<br>'
         '<b>What a mistake looks like:</b> a book assigned to the board '
         'above/below its real one, a start box hanging over the board '
         'edge, or a silent flag that should have been raised.</div>',
         '<p class="key"><i style="background:#1c2a1c;color:#9dd89d">CP1 '
         'seed (thin)</i><i style="background:#16283a;color:#9dc6ff">'
         'clamped start</i><i style="background:#3a1c1c;color:#ff9d9d">'
         'flagged start</i> · thin colored rings = boards · click to '
         'zoom</p>']
    h.append('<div class="imgs">'
             '<div><img src="front.png"><p class="cap"><b>FRONT</b> — every '
             'start box should sit bottom-on a board</p></div>'
             '<div><img src="topdown.png"><p class="cap"><b>TOP-DOWN</b> — '
             'no start box outside its board rect</p></div></div>')
    h.append('<table><tr><th>sub</th><th>name</th><th>board</th>'
             '<th>seed bottom</th><th>y snap</th><th>xz clamp</th>'
             '<th>flags</th></tr>')
    for r in rec["subs"]:
        cls = ' class="flag"' if r["flags"] else ""
        if r.get("board") is None:
            why = ("in-wall box → wall channel (SR3b: not a board "
                   "rider; observed box kept as the placement)"
                   if "NOT_A_BOARD_RIDER" in r["flags"] else
                   "no usable surface on this anchor (SR2: recorded, "
                   "never forced)")
            h.append(f'<tr{cls}><td>{r["id"]}</td>'
                     f'<td>{html.escape(r["name"])}</td>'
                     f'<td colspan="4">{why}</td>'
                     f'<td>{", ".join(r["flags"])}</td></tr>')
            continue
        h.append(f'<tr{cls}><td>{r["id"]}</td>'
                 f'<td>{html.escape(r["name"])}</td>'
                 f'<td class="mono">B{r["board"]}</td>'
                 f'<td class="mono">{r["seed_bottom_y"]:+.3f}</td>'
                 f'<td class="mono">{r["y_snap_m"]:+.3f} m</td>'
                 f'<td class="mono">{r["clamp_move_m"]:.3f} m</td>'
                 f'<td>{", ".join(r["flags"]) or "—"}</td></tr>')
    h.append('</table>')
    h.append('<div class="note"><b>Gate question (one look):</b> in the '
             'front view, does every light-blue box stand ON a board '
             '(no floating, no wrong level)? Red boxes are flagged — '
             'check the table row to see why.</div>')
    h.append('<div id="lb"><img></div>')
    h.append(f'<script>{js}</script></div>')
    (odir / "index.html").write_text("\n".join(h), encoding="utf-8")


if __name__ == "__main__":
    main()
