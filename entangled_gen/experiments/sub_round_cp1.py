"""SUB ROUNDS — CP1: SEED TRANSFORM (isolated experiment, obj_043).

USER RULING 2026-08-05C (PLAN_SUB_ROUNDS.md): each deferred sub's search
STARTS at the same relative anchor->sub offset it had in the observation,
re-expressed on the anchor's FITTED pose (jiggle/walk translation + any
applied spin). This checkpoint computes those seeds and shows them to the
user over the real splat — no placement, no retrieval, no pipeline files
touched.

Math: delta = fitted anchor box center - observed anchor box center
(render frame); yaw delta = rotcheck_applied_deg (obj_043: 0). A non-zero
yaw rotates the offsets about the anchor center. An extent-swap sanity
flag fires if the fitted box's footprint looks 90-degree-turned vs the
observation (would mean the yaw bookkeeping missed a spin).

Outputs (out/<scene>/compose/sub_experiment/cp1/):
  seeds.json    per-sub: observed box, anchor-relative offset, seed box
  topdown.png   splat from above, boxes overlaid
  front.png     splat from the shelf's front, boxes overlaid
  index.html    the review page (USER GATE — Claude never concludes
                from images)

  python sub_round_cp1.py [--scene bedroom_marble] [--anchor obj_043]
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
# shot.py silently renders EMPTY above 1024px (measured this session:
# 1024 fine, 1050+ ~10KB blank webp — a renderer tile/block ceiling).
RES = 1024

# overlay palette (house colors from the review pages)
C_FIT = (74, 144, 217)     # fitted anchor box — blue
C_OBS = (154, 154, 154)    # observed anchor box — gray
C_SUB = (255, 157, 61)     # sub observed box — orange
C_SEED = (63, 191, 111)    # sub seed box — green


def vec(a):
    return ",".join(f"{(v if v != 0 else 0.0):.4f}" for v in a)


def box_raw(b):
    """aabb dict -> (lo, hi), raw frame, order fixed.

    FRAME NOTE (measured this session): fitted_preview.json fit_box is
    in the RAW frame, same as shopping.json boxes — obj_043's fit_box
    x/z are byte-identical to its observed box, only y floor-snapped.
    ALL seed math therefore stays raw; boxes convert to the render
    frame (via r2r) only for cameras and overlay drawing.
    """
    lo = np.asarray(b["aabb_min"], np.float64)
    hi = np.asarray(b["aabb_max"], np.float64)
    return np.minimum(lo, hi), np.maximum(lo, hi)


def to_render(lo, hi, r2r):
    return np.minimum(lo * r2r, hi * r2r), np.maximum(lo * r2r, hi * r2r)


def proj(pose, fov_deg, res, pts):
    """project(); but aligned — None for points behind the camera."""
    inv = np.linalg.inv(pose)
    f = 1.0 / np.tan(np.radians(fov_deg) / 2.0)
    uv = []
    for p in pts:
        pc = (inv @ np.append(np.asarray(p, float), 1.0))[:3]
        z = -pc[2]
        if z <= 1e-6:
            uv.append(None)
            continue
        uv.append((((pc[0] / z) * f + 1.0) / 2.0 * res,
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


def draw_arrow(dr, pose, fov, res, p0, p1, color, width=2):
    uv = proj(pose, fov, res, [p0, p1])
    if uv[0] and uv[1]:
        dr.line([uv[0], uv[1]], fill=color, width=width)
        dr.ellipse([uv[1][0] - 4, uv[1][1] - 4, uv[1][0] + 4, uv[1][1] + 4],
                   fill=color)


def splat_shot(out_png, eye, look, up, fov, clip, ply, gpu="0", res=RES):
    tmp = out_png.with_suffix(".webp")
    cmd = [sys.executable, str(SHOT), vec(eye), vec(look), f"--up={vec(up)}",
           f"--fov={fov:.3f}", f"--box={clip}", f"--res={res}x{res}",
           f"--ply={ply}", f"--gpu={gpu}", f"--out={tmp}", "--no-open"]
    subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL)
    if tmp.stat().st_size < 30_000:            # blank-render guard
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
    man = json.loads(paths.manifest(a.scene).read_text(encoding="utf-8"))
    r2r = np.asarray(man["frame"].get("raw_to_render", [1, 1, 1]), np.float64)
    floor_r = float(man["frame"]["floor_y"]) * -1.0
    sl = json.loads((cdir / "shopping.json").read_text(encoding="utf-8"))
    fp = json.loads((cdir / "fitted_preview.json").read_text(encoding="utf-8"))

    anchor_obs = next(it for it in sl["items"] if it["id"] == a.anchor)
    subs = [s for s in sl["subs_deferred"] if s.get("anchor") == a.anchor]
    placed = next(p for p in fp["placed"] if p["id"] == a.anchor)

    # SR0 HOSTS BEFORE RIDERS: a sub whose host is itself an unfitted
    # sub belongs to the NEXT level — defer it, never seed it onto the
    # anchor directly (plant obj_003 rides basket obj_012, not the
    # shelf). Level-1 = host is the anchor (or a fitted item).
    sub_ids = {s["id"] for s in sl["subs_deferred"]}
    level2 = [s for s in subs if s.get("host") in sub_ids]
    subs = [s for s in subs if s.get("host") not in sub_ids]

    obs_lo, obs_hi = box_raw(anchor_obs["box"])          # raw frame
    fit_lo, fit_hi = box_raw(placed["fit_box"])          # raw frame too
    # declip_move_m is RENDER frame (verified vs the GLB: obj_043's mesh
    # sits at fit_box + declip * r2r); the GLB is the placed truth.
    declip_raw = (np.asarray(placed.get("declip_move_m") or [0, 0, 0],
                             np.float64) * r2r)
    fit_lo, fit_hi = fit_lo + declip_raw, fit_hi + declip_raw
    obs_c, fit_c = (obs_lo + obs_hi) / 2, (fit_lo + fit_hi) / 2
    delta = fit_c - obs_c
    # applied spins are about render +y; raw = render mirrored by
    # diag(-1,-1,1) (proper), so the same spin is -deg about raw y.
    yaw = float(placed.get("rotcheck_applied_deg") or 0.0)
    yaw_raw = -yaw

    # extent-swap sanity: does the fitted footprint look 90-deg-turned?
    obs_sz, fit_sz = obs_hi - obs_lo, fit_hi - fit_lo
    straight = abs(fit_sz[0] - obs_sz[0]) + abs(fit_sz[2] - obs_sz[2])
    swapped = abs(fit_sz[0] - obs_sz[2]) + abs(fit_sz[2] - obs_sz[0])
    swap_flag = bool(swapped + 0.05 < straight)

    rad = np.radians(yaw_raw)
    rot = np.array([[np.cos(rad), 0, np.sin(rad)],
                    [0, 1, 0],
                    [-np.sin(rad), 0, np.cos(rad)]])

    floor_raw = float(man["frame"]["floor_y"])
    rows = []
    for s in subs:
        slo, shi = box_raw(s["box"])
        sc, ssz = (slo + shi) / 2, shi - slo
        off = sc - obs_c                      # anchor-relative, observed
        seed_c = fit_c + rot @ off            # re-expressed on fitted pose
        # raw up = -y: the sub's bottom is its raw-y MAX
        h_obs = floor_raw - float(shi[1])
        rows.append({
            "id": s["id"], "name": s["name"], "host": s.get("host"),
            "obs_box": {"lo": slo.round(3).tolist(),
                        "hi": shi.round(3).tolist()},
            "size": ssz.round(3).tolist(),
            "offset_obs": off.round(3).tolist(),
            "seed_center": seed_c.round(3).tolist(),
            "seed_box": {"lo": (seed_c - ssz / 2).round(3).tolist(),
                         "hi": (seed_c + ssz / 2).round(3).tolist()},
            "height_above_floor_obs": round(h_obs, 3),
        })

    odir = cdir / "sub_experiment" / a.anchor / "cp1"
    odir.mkdir(parents=True, exist_ok=True)
    rec = {
        "scene": a.scene, "anchor": a.anchor,
        "anchor_name": anchor_obs.get("name"),
        "level2_deferred": [{"id": s["id"], "name": s["name"],
                             "host": s.get("host")} for s in level2],
        "obs_box": {"lo": obs_lo.round(3).tolist(),
                    "hi": obs_hi.round(3).tolist()},
        "fit_box": {"lo": fit_lo.round(3).tolist(),
                    "hi": fit_hi.round(3).tolist()},
        "delta_m": delta.round(3).tolist(),
        "yaw_applied_deg": yaw,
        "extent_swap_flag": swap_flag,
        "floor_render_y": floor_r,
        "n_subs": len(rows), "subs": rows,
    }
    (odir / "seeds.json").write_text(json.dumps(rec, indent=1),
                                     encoding="utf-8")

    # ---- render-frame copies for cameras + drawing
    rb = {}   # label -> (lo, hi) render frame
    rb["obs"] = to_render(obs_lo, obs_hi, r2r)
    rb["fit"] = to_render(fit_lo, fit_hi, r2r)
    for r in rows:
        rb[r["id"] + ":o"] = to_render(np.asarray(r["obs_box"]["lo"]),
                                       np.asarray(r["obs_box"]["hi"]), r2r)
        rb[r["id"] + ":s"] = to_render(np.asarray(r["seed_box"]["lo"]),
                                       np.asarray(r["seed_box"]["hi"]), r2r)

    # frame everything that matters
    pts = []
    for lo, hi in rb.values():
        pts += [lo, hi]
    P = np.vstack(pts)
    lo_all, hi_all = P.min(0), P.max(0)
    ctr = (lo_all + hi_all) / 2

    ply = paths.ply(a.scene)
    clip = (f"{lo_all[0]-1.2:.3f},{floor_r-0.25:.3f},{lo_all[2]-1.2:.3f},"
            f"{hi_all[0]+1.2:.3f},{floor_r+2.45:.3f},{hi_all[2]+1.2:.3f}")

    shots = {}

    # top-down: eye high enough that the fov stays sane; clip keeps the
    # whole shelf (cut just above the tallest box, not at furniture height)
    half = max(hi_all[0] - lo_all[0], hi_all[2] - lo_all[2]) / 2 * 1.5
    eye_y = hi_all[1] + max(1.5, half / np.tan(np.radians(27.5)))
    eye = np.array([ctr[0], eye_y, ctr[2]])
    look = np.array([ctr[0], floor_r, ctr[2]])
    up = np.array([0.0, 0.0, 1.0])
    fov = float(np.clip(np.degrees(2 * np.arctan2(half, eye_y - ctr[1])),
                        25, 100))
    shots["topdown"] = (eye, look, up, fov,
                        (f"{lo_all[0]-1.2:.3f},{floor_r-0.25:.3f},"
                         f"{lo_all[2]-1.2:.3f},{hi_all[0]+1.2:.3f},"
                         f"{hi_all[1]+0.15:.3f},{hi_all[2]+1.2:.3f}"))

    # front elevation: from the shelf's own front direction
    fdr = placed.get("front_dir_raw") or [0.0, -1.0]
    fdir = np.array([fdr[0] * r2r[0], 0.0, fdr[1] * r2r[2]])
    n = np.linalg.norm(fdir)
    fdir = fdir / n if n > 1e-6 else np.array([0.0, 0.0, -1.0])
    span = max(hi_all[0] - lo_all[0], hi_all[1] - lo_all[1],
               hi_all[2] - lo_all[2])
    dist = max(2.4, span * 1.1)
    eye_f = ctr + fdir * dist
    eye_f[1] = ctr[1] + 0.15
    shots["front"] = (eye_f, ctr.copy(), np.array([0.0, 1.0, 0.0]),
                      float(np.clip(np.degrees(
                          2 * np.arctan2(span * 0.62, dist)), 25, 95)),
                      clip)

    for name, (e, l, u, fv, cl) in shots.items():
        img = splat_shot(odir / f"{name}.png", e, l, u, fv, cl, ply,
                         gpu=a.gpu)
        dr = ImageDraw.Draw(img)
        pose = look_at_pose(e, l, u)
        draw_box(dr, pose, fv, RES, *rb["obs"], C_OBS, 2)
        draw_box(dr, pose, fv, RES, *rb["fit"], C_FIT, 3)
        for r in rows:
            olo, ohi = rb[r["id"] + ":o"]
            slo2, shi2 = rb[r["id"] + ":s"]
            draw_box(dr, pose, fv, RES, olo, ohi, C_SUB, 2)
            draw_box(dr, pose, fv, RES, slo2, shi2, C_SEED, 3)
            draw_arrow(dr, pose, fv, RES, (olo + ohi) / 2,
                       (slo2 + shi2) / 2, C_SEED, 2)
        img.save(odir / f"{name}.png")

    build_page(odir, rec)
    print(f"[cp1] delta {rec['delta_m']} yaw {yaw} swap_flag {swap_flag}")
    print(f"[cp1] wrote {odir / 'index.html'}")


def build_page(odir, rec):
    def fmt(v):
        return f"[{', '.join(f'{x:+.3f}' for x in v)}]"

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
.warn{border-left-color:#d9774a}
table{border-collapse:collapse;margin:16px 0;font-size:13.5px}
th,td{border:1px solid #2e2e2e;padding:5px 10px;text-align:left}
th{background:#1c1c1c;color:#cfcfcf}
td.mono{font-family:Consolas,monospace;font-size:12.5px}
.imgs{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin:18px 0}
.imgs img{width:100%;display:block;border-radius:4px;cursor:zoom-in;
          background:#000}
.cap{color:#8a8a8a;font-size:12.5px;margin:6px 0 0}
.key i{font-style:normal;padding:1px 8px;border-radius:3px;margin-right:6px;
       font-size:12.5px}
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
         f'<title>sub rounds CP1 — seeds — {rec["anchor"]}</title>',
         f'<style>{css}</style><div class="wrap">',
         '<h1>Sub rounds — CP1: seed transform</h1>',
         f'<p class="sub">{rec["scene"]} · anchor {rec["anchor"]} '
         f'({html.escape(str(rec["anchor_name"]))}) · {rec["n_subs"]} subs · '
         'isolated experiment, no pipeline files touched</p>',
         '<div class="contract">'
         '<b>What this step gets:</b> the anchor&rsquo;s observed box, its '
         'fitted box (after jiggle/declip/walk + applied spins), and the '
         'observed boxes of its deferred subs.<br>'
         '<b>What it decides:</b> where each sub&rsquo;s placement search '
         'STARTS &mdash; the observed anchor&rarr;sub offset re-expressed '
         'on the fitted pose (user ruling: same relative position, '
         'large margin comes later).<br>'
         '<b>What a mistake looks like:</b> seeds landing off the shelf, at '
         'the wrong end (a missed spin), or at the wrong height &mdash; the '
         'later board search would then start from nonsense.</div>',
         f'<div class="note"><b>Transform:</b> delta {fmt(rec["delta_m"])} m '
         f'&middot; yaw applied {rec["yaw_applied_deg"]:g}&deg; &middot; '
         f'extent-swap flag {"FIRED" if rec["extent_swap_flag"] else "clear"}'
         '<br>Seed = fitted center + R(yaw) &middot; (sub center &minus; '
         'observed anchor center); the sub keeps its observed size.</div>']
    if rec["extent_swap_flag"]:
        h.append('<div class="note warn"><b>&#9888; extent-swap flag:</b> '
                 'the fitted footprint looks 90&deg;-turned vs the observed '
                 'box but no spin was recorded — the yaw bookkeeping may '
                 'have missed one. Judge the top-down carefully.</div>')
    h.append('<p class="key"><i style="background:#16283a;color:#9dc6ff">'
             'fitted anchor</i><i style="background:#2a2a2a;color:#c0c0c0">'
             'observed anchor</i><i style="background:#3a2610;color:#ffc08a">'
             'sub observed</i><i style="background:#1c2a1c;color:#9dd89d">'
             'sub SEED</i> · dot = seed center · click to zoom</p>')
    h.append('<div class="imgs">'
             '<div><img src="topdown.png"><p class="cap"><b>TOP-DOWN</b> — '
             'splat, ceiling clipped; orange&rarr;green arrow = observed '
             '&rarr; seed</p></div>'
             '<div><img src="front.png"><p class="cap"><b>FRONT</b> — from '
             'the shelf&rsquo;s front direction; heights readable here</p>'
             '</div></div>')
    h.append('<table><tr><th>sub</th><th>name</th><th>size m</th>'
             '<th>offset vs anchor (obs)</th><th>seed center</th>'
             '<th>obs height above floor</th></tr>')
    for r in rec["subs"]:
        h.append(f'<tr><td>{r["id"]}</td><td>{html.escape(r["name"])}</td>'
                 f'<td class="mono">{fmt(r["size"])}</td>'
                 f'<td class="mono">{fmt(r["offset_obs"])}</td>'
                 f'<td class="mono">{fmt(r["seed_center"])}</td>'
                 f'<td class="mono">{r["height_above_floor_obs"]:+.3f}</td>'
                 '</tr>')
    h.append('</table>')
    h.append('<div class="note"><b>Gate question (one look):</b> do the '
             'green seed boxes sit on/inside the real shelf in both views, '
             'at the same spots the orange observations occupy? For this '
             'anchor the move was small, so near-overlap = PASS; the '
             'machinery, not the distance, is under test.</div>')
    h.append('<div id="lb"><img></div>')
    h.append(f'<script>{js}</script></div>')
    (odir / "index.html").write_text("\n".join(h), encoding="utf-8")


if __name__ == "__main__":
    main()
