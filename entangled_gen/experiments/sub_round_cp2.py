"""SUB ROUNDS — CP2: BOARD EXTRACTION (isolated experiment, obj_043).

Finds the REAL support surfaces of the fitted anchor mesh — the shelf
boards the deferred subs will stand on (the reason they were deferred:
box-level placement had no boards, only the anchor's outer box).

Method (pure geometry, no judge):
  1. the anchor's placed meshes from fitted_preview.glb (the placed
     truth, CP1 finding), converted raw->render by diag(-1,-1,1);
  2. upward-facing triangles (render +y up, face normal_y > 0.65);
  3. area-weighted height clustering (gap > 35 mm starts a new board);
  4. per cluster: projected XZ footprint (rect + area), clearance to
     the next board above (books need headroom);
  5. small patches dropped (< 0.02 m^2 projected — trim edges, lips).

Outputs (out/<scene>/compose/sub_experiment/cp2/):
  boards.json   per board: height, footprint rect, area, clearance
  front.png     splat front view, board rectangles overlaid + labels
  topdown.png   splat top-down, footprints overlaid
  index.html    review page (USER GATE: do the drawn boards line up
                with the real shelf's boards?)

  python sub_round_cp2.py [--scene bedroom_marble] [--anchor obj_043]
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
import rotation_check as rc                      # noqa: E402  (mesh renderer)

SHOT = EG / "rendertools" / "shot.py"
RES = 1024          # shot.py blank above 1024 px (CP1 finding)
UP_DOT = 0.65       # min normal_y for "upward-facing"
GAP = 0.035         # m; height gap starting a new cluster
MIN_AREA = 0.02     # m^2; drop smaller patches
MIN_SPAN = 0.12     # m; drop clusters narrower than this in x AND z

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


def draw_rect_at_height(dr, pose, fov, res, x0, x1, z0, z1, y, color, w=4):
    ring = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1), (x0, y, z0)]
    uv = proj(pose, fov, res, ring)
    for a, b in zip(uv, uv[1:]):
        if a and b:
            dr.line([a, b], fill=color, width=w)


def asset_rgba(meshes, eye, look, up, fov, res, alpha=0.62):
    """The fitted asset rendered from the same camera, semi-transparent.

    rotation_check.render_object_rgba hardwires up=[0,1,0] via
    look_at_pose — patch it (the topdown_choice_test trick) so the
    straight-down camera works too."""
    orig = rc.look_at_pose

    def patched(e, t, _u):
        return orig(np.asarray(e, float), np.asarray(t, float),
                    np.asarray(up, float))
    rc.look_at_pose = patched
    try:
        img = rc.render_object_rgba(meshes, eye, look, fov, res)
    finally:
        rc.look_at_pose = orig
    a = np.asarray(img, np.uint8).copy()
    a[:, :, 3] = (a[:, :, 3].astype(np.float32) * alpha).astype(np.uint8)
    return Image.fromarray(a, "RGBA")


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


def extract_boards(meshes):
    """meshes: render-frame trimesh list -> board dicts, low to high."""
    tris = []      # (y_center, area_xz, tri_pts)
    for m in meshes:
        n = m.face_normals
        up_idx = np.where(n[:, 1] > UP_DOT)[0]
        if not len(up_idx):
            continue
        v = m.vertices
        for fi in up_idx:
            p = v[m.faces[fi]]
            # projected XZ area of the triangle
            a = 0.5 * abs((p[1][0] - p[0][0]) * (p[2][2] - p[0][2])
                          - (p[2][0] - p[0][0]) * (p[1][2] - p[0][2]))
            tris.append((float(p[:, 1].mean()), a, p))
    tris.sort(key=lambda t: t[0])
    if not tris:
        return []

    clusters, cur = [], [tris[0]]
    for t in tris[1:]:
        if t[0] - cur[-1][0] > GAP:
            clusters.append(cur)
            cur = [t]
        else:
            cur.append(t)
    clusters.append(cur)

    boards = []
    for cl in clusters:
        area = sum(t[1] for t in cl)
        P = np.vstack([t[2] for t in cl])
        y = float(np.average([t[0] for t in cl],
                             weights=[max(t[1], 1e-9) for t in cl]))
        x0, x1 = float(P[:, 0].min()), float(P[:, 0].max())
        z0, z1 = float(P[:, 2].min()), float(P[:, 2].max())
        if area < MIN_AREA or max(x1 - x0, z1 - z0) < MIN_SPAN:
            continue
        boards.append({"y": round(y, 4), "area_m2": round(float(area), 4),
                       "x": [round(x0, 3), round(x1, 3)],
                       "z": [round(z0, 3), round(z1, 3)]})
    for i, b in enumerate(boards):
        b["board"] = i
        b["clearance_m"] = (round(boards[i + 1]["y"] - b["y"], 3)
                            if i + 1 < len(boards) else None)
    return boards


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--anchor", default="obj_043")
    ap.add_argument("--gpu", default="0")
    a = ap.parse_args()

    cdir = paths.compose_dir(a.scene)
    man = json.loads(paths.manifest(a.scene).read_text(encoding="utf-8"))
    floor_r = float(man["frame"]["floor_y"]) * -1.0
    fp = json.loads((cdir / "fitted_preview.json").read_text(encoding="utf-8"))
    placed = next(p for p in fp["placed"] if p["id"] == a.anchor)

    to_render = np.diag([-1.0, -1.0, 1.0, 1.0])
    sc = trimesh.load(cdir / "fitted_preview.glb", force="scene")
    meshes = []
    for gname, geom in sc.geometry.items():
        if gname.rsplit("_t", 1)[0] == a.anchor:
            m = geom.copy()
            m.apply_transform(to_render)
            meshes.append(m)
    if not meshes:
        raise SystemExit(f"no meshes for {a.anchor} in fitted_preview.glb")

    boards = extract_boards(meshes)
    allb = np.vstack([m.bounds for m in meshes])
    mlo, mhi = allb.min(0), allb.max(0)

    odir = cdir / "sub_experiment" / a.anchor / "cp2"
    odir.mkdir(parents=True, exist_ok=True)
    rec = {"scene": a.scene, "anchor": a.anchor,
           "anchor_name": placed.get("name"),
           "mesh_bounds": {"lo": mlo.round(3).tolist(),
                           "hi": mhi.round(3).tolist()},
           "floor_render_y": floor_r,
           "params": {"up_dot": UP_DOT, "gap_m": GAP,
                      "min_area_m2": MIN_AREA, "min_span_m": MIN_SPAN},
           "n_boards": len(boards), "boards": boards}
    for b in boards:
        b["height_above_floor"] = round(b["y"] - floor_r, 3)
    (odir / "boards.json").write_text(json.dumps(rec, indent=1),
                                      encoding="utf-8")

    # ---- cameras (CP1 framing, on the mesh bounds)
    ply = paths.ply(a.scene)
    ctr = (mlo + mhi) / 2
    span = float(max(mhi - mlo))
    clip = (f"{mlo[0]-1.2:.3f},{floor_r-0.25:.3f},{mlo[2]-1.2:.3f},"
            f"{mhi[0]+1.2:.3f},{mhi[1]+0.5:.3f},{mhi[2]+1.2:.3f}")

    fdr = placed.get("front_dir_raw") or [0.0, -1.0]
    r2r = np.asarray(man["frame"].get("raw_to_render", [1, 1, 1]), np.float64)
    fdir = np.array([fdr[0] * r2r[0], 0.0, fdr[1] * r2r[2]])
    n = np.linalg.norm(fdir)
    fdir = fdir / n if n > 1e-6 else np.array([0.0, 0.0, -1.0])
    dist = max(2.4, span * 1.1)
    eye_f = ctr + fdir * dist
    eye_f[1] = ctr[1] + 0.15
    fov_f = float(np.clip(np.degrees(2 * np.arctan2(span * 0.62, dist)),
                          25, 95))

    half = max(mhi[0] - mlo[0], mhi[2] - mlo[2]) / 2 * 1.5
    eye_y = mhi[1] + max(1.5, half / np.tan(np.radians(27.5)))
    fov_t = float(np.clip(np.degrees(2 * np.arctan2(half, eye_y - ctr[1])),
                          25, 100))
    clip_t = (f"{mlo[0]-1.2:.3f},{floor_r-0.25:.3f},{mlo[2]-1.2:.3f},"
              f"{mhi[0]+1.2:.3f},{mhi[1]+0.15:.3f},{mhi[2]+1.2:.3f}")

    shots = {
        "front": (eye_f, ctr.copy(), np.array([0.0, 1.0, 0.0]), fov_f, clip),
        "topdown": (np.array([ctr[0], eye_y, ctr[2]]),
                    np.array([ctr[0], floor_r, ctr[2]]),
                    np.array([0.0, 0.0, 1.0]), fov_t, clip_t),
    }
    for name, (e, l, u, fv, cl) in shots.items():
        base = splat_shot(odir / f"{name}.png", e, l, u, fv, cl, ply,
                          gpu=a.gpu)
        pose = look_at_pose(e, l, u)
        overlay = asset_rgba(meshes, e, l, u, fv, RES)
        solid = asset_rgba(meshes, e, l, u, fv, RES, alpha=1.0)
        for variant in ("", "_asset", "_solid"):
            if variant == "_solid":
                img = Image.new("RGBA", solid.size, (32, 32, 32, 255))
                img.alpha_composite(solid)
                img = img.convert("RGB")
            else:
                img = base.copy()
            if variant == "_asset":
                img = img.convert("RGBA")
                img.alpha_composite(overlay)
                img = img.convert("RGB")
            dr = ImageDraw.Draw(img)
            for b in boards:
                c = BOARD_COLORS[b["board"] % len(BOARD_COLORS)]
                draw_rect_at_height(dr, pose, fv, RES, b["x"][0], b["x"][1],
                                    b["z"][0], b["z"][1], b["y"], c)
                uv = proj(pose, fv, RES,
                          [(b["x"][0], b["y"], (b["z"][0] + b["z"][1]) / 2)])
                if uv[0]:
                    dr.text((uv[0][0] - 26, uv[0][1] - 8), f"B{b['board']}",
                            fill=c)
            img.save(odir / f"{name}{variant}.png")

    build_page(odir, rec)
    print(f"[cp2] {len(boards)} boards @ "
          + ", ".join(f"{b['height_above_floor']:.2f}" for b in boards)
          + " m above floor")
    print(f"[cp2] wrote {odir / 'index.html'}")


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
.sw{display:inline-block;width:12px;height:12px;border-radius:2px;
    margin-right:7px;vertical-align:-1px}
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
         f'<title>sub rounds CP2 — boards — {rec["anchor"]}</title>',
         f'<style>{css}</style><div class="wrap">',
         '<h1>Sub rounds — CP2: board extraction</h1>',
         f'<p class="sub">{rec["scene"]} · anchor {rec["anchor"]} '
         f'({html.escape(str(rec["anchor_name"]))}) · {rec["n_boards"]} '
         'boards found · pure geometry, no judge</p>',
         '<div class="contract">'
         '<b>What this step gets:</b> the anchor&rsquo;s placed meshes '
         'from fitted_preview.glb (the placed truth).<br>'
         '<b>What it decides:</b> the anchor&rsquo;s REAL support '
         'surfaces &mdash; each board&rsquo;s height, footprint and '
         'headroom &mdash; the shelves the subs will stand on.<br>'
         '<b>What a mistake looks like:</b> a real board missed (its '
         'books will have nowhere to go), a phantom board (books float '
         'mid-air), or a footprint spilling outside the shelf.</div>',
         '<div class="note"><b>Method:</b> upward-facing triangles '
         f'(normal_y &gt; {rec["params"]["up_dot"]}), height-clustered '
         f'(gap &gt; {rec["params"]["gap_m"]*1000:.0f} mm), patches '
         f'&lt; {rec["params"]["min_area_m2"]} m&sup2; dropped. Colors '
         'match the table; the rectangle is drawn AT the board&rsquo;s '
         'height.</div>']
    h.append('<div class="imgs">'
             '<div><img src="front.png"><p class="cap"><b>FRONT</b> — real '
             'splat + board rectangles</p></div>'
             '<div><img src="front_solid.png"><p class="cap"><b>THE ASSET '
             'WE GOT</b> — the fitted stand-in isolated, same camera; the '
             'rectangles should sit ON its planks</p></div>'
             '<div><img src="front_asset.png"><p class="cap"><b>FRONT + '
             'ASSET</b> — stand-in ghosted over the splat (position '
             'check)</p></div>'
             '<div><img src="topdown.png"><p class="cap"><b>TOP-DOWN</b> '
             '— footprints; the top board dominates this view</p></div>'
             '<div><img src="topdown_asset.png"><p class="cap"><b>TOP-DOWN '
             '+ ASSET</b> — same, stand-in ghosted</p></div>'
             '</div>')
    h.append('<table><tr><th>board</th><th>height above floor</th>'
             '<th>headroom to next</th><th>footprint x</th>'
             '<th>footprint z</th><th>area</th></tr>')
    for b in rec["boards"]:
        c = BOARD_COLORS[b["board"] % len(BOARD_COLORS)]
        sw = (f'<i class="sw" style="background:rgb{c}"></i>')
        clr = (f'{b["clearance_m"]:.3f} m' if b["clearance_m"] is not None
               else "&mdash; (top)")
        h.append(f'<tr><td>{sw}B{b["board"]}</td>'
                 f'<td class="mono">{b["height_above_floor"]:.3f} m</td>'
                 f'<td class="mono">{clr}</td>'
                 f'<td class="mono">{b["x"][0]:.2f} .. {b["x"][1]:.2f}</td>'
                 f'<td class="mono">{b["z"][0]:.2f} .. {b["z"][1]:.2f}</td>'
                 f'<td class="mono">{b["area_m2"]:.3f} m&sup2;</td></tr>')
    h.append('</table>')
    h.append('<div class="note"><b>Gate question (one look):</b> the '
             'rectangles are the FITTED STAND-IN&rsquo;s boards — the '
             'surfaces the books will actually be placed on. Are they '
             'sensible shelf boards (count, spacing, inside the shelf), '
             'with none missed and none phantom? Where a rectangle sits '
             'off a real board line, that is the stand-in&rsquo;s '
             'geometry differing from the real shelf — judge whether '
             'that gap is acceptable for placing books, not the '
             'extractor.</div>')
    h.append('<div id="lb"><img></div>')
    h.append(f'<script>{js}</script></div>')
    (odir / "index.html").write_text("\n".join(h), encoding="utf-8")


if __name__ == "__main__":
    main()
