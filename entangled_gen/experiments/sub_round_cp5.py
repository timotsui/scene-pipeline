"""SUB ROUNDS — CP5: RAW PLACEMENT ON BOARDS (isolated, obj_043).

USER RULING 2026-08-05C: place RAW first — the PCA cardinal snap (the
obj_032 crooked-in-file lesson) is deliberately OFF this pass so the
user sees what the assets do untreated; a --pca re-run flips it on for
comparison. No jiggle, no declip: this is "books dropped on their
boards", overlaps recorded honestly, resolution deferred.

Reuses the anchors' placement verbatim (compose/fit_preview.py
place_candidate): perm rotation -> [PCA snap when --pca] -> facing
chosen among 4 compass yaws toward the HOST's front (sub facing =
host inheritance canon) -> k tiles filling the box -> bottom on the
box floor = the CP3 board.

Outputs (out/<scene>/compose/sub_experiment/cp5/):
  placements.json    per sub: pose record, per-instance bounds,
                     same-board overlap report
  subs_preview.glb   placed sub meshes, RAW frame (fitted_preview.glb
                     convention) — for the viewer later
  front.png / topdown.png       splat + solid subs + ghost anchor
  composed.png                  subs + anchor solid on dark (no splat)
  index.html         review page (USER GATE)

  python sub_round_cp5.py [--scene bedroom_marble] [--anchor obj_043]
                          [--pca]
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
import fit_preview as fpv                        # noqa: E402
import rotation_check as rc                      # noqa: E402
from place import look_at_pose                   # noqa: E402
from assets_thor import load_asset               # noqa: E402

SHOT = EG / "rendertools" / "shot.py"
RES = 1024          # shot.py blank above 1024 px (CP1 finding)

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


def draw_rect_at_height(dr, pose, fov, res, x0, x1, z0, z1, y, color, w=2):
    ring = [(x0, y, z0), (x1, y, z0), (x1, y, z1), (x0, y, z1), (x0, y, z0)]
    uv = proj(pose, fov, res, ring)
    for a, b in zip(uv, uv[1:]):
        if a and b:
            dr.line([a, b], fill=color, width=w)


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
        a[:, :, 3] = (a[:, :, 3].astype(np.float32) * alpha).astype(np.uint8)
        img = Image.fromarray(a, "RGBA")
    return img


def align_upright(mesh, min_deg=2.0):
    """THE ALIGN TRICK (user 08-05C): snap the asset's oriented
    bounding box axes to the NEAREST world axes — the minimal rotation
    that stands a tilted asset upright. Fixes baked-in roll/pitch AND
    yaw skew in one move (the canon PCA snap is yaw-only and cannot
    straighten a lean). Scene-agnostic: no category assumptions.

    Nearest-cardinal is honest but ambiguous near 45 deg — a hard
    lean can snap to lying-down; the applied angle is returned so the
    record shows exactly what happened. Back-front sign ambiguity is
    deliberately dumped on a HORIZONTAL axis (never up) — the facing
    ladder downstream owns that choice anyway.
    """
    T, _ = trimesh.bounds.oriented_bounds(mesh)
    V = T[:3, :3].T                  # columns = OBB axes in world
    C = np.zeros((3, 3))
    used = []
    for i in sorted(range(3), key=lambda i: -np.abs(V[:, i]).max()):
        scores = [abs(V[k, i]) if k not in used else -1 for k in range(3)]
        j = int(np.argmax(scores))
        used.append(j)
        C[j, i] = np.sign(V[j, i]) or 1.0
    if np.linalg.det(C) < 0:         # proper rotation; flip a horizontal
        for i in range(3):           # column, never the up axis
            if abs(C[1, i]) < 0.5:
                C[:, i] *= -1
                break
    W = C @ V.T
    ang = float(np.degrees(np.arccos(np.clip((np.trace(W) - 1) / 2,
                                             -1, 1))))
    if ang < min_deg:
        return mesh, 0.0
    M = np.eye(4)
    M[:3, :3] = W
    ctr = mesh.bounds.mean(axis=0)
    m = mesh.copy()
    m.apply_translation(-ctr)
    m.apply_transform(M)
    m.apply_translation(ctr)
    return m, round(ang, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--anchor", default="obj_043")
    ap.add_argument("--pca", action="store_true",
                    help="apply the PCA cardinal snap (default RAW)")
    ap.add_argument("--align", action="store_true",
                    help="the align trick: OBB-to-cardinal upright snap "
                         "per asset (implies canon PCA stays ON); output "
                         "goes to cp5_align/ beside the raw pass")
    ap.add_argument("--picks-dir", default="cp4",
                    help="sub_experiment folder holding picks.json "
                         "(cp4_aligned for the aligned-shopping rerun)")
    ap.add_argument("--out", default=None,
                    help="override the output folder name")
    ap.add_argument("--gpu", default="0")
    a = ap.parse_args()

    cdir = paths.compose_dir(a.scene)
    man = {"frame": paths.frame_block(a.scene)}
    r2r = np.asarray(man["frame"].get("raw_to_render", [1, 1, 1]), np.float64)
    floor_r = float(man["frame"]["floor_y"]) * -1.0
    sdir = cdir / "sub_experiment" / a.anchor
    asg = json.loads((sdir / "cp3" / "assignment.json").read_text("utf-8"))
    pk = json.loads((sdir / a.picks_dir / "picks.json").read_text("utf-8"))
    brec = json.loads((sdir / "cp2" / "boards.json").read_text("utf-8"))
    boards = brec["boards"]
    picks = {r["id"]: r for r in pk["subs"]}
    fp = json.loads((cdir / "fitted_preview.json").read_text("utf-8"))
    aplaced = next(p for p in fp["placed"] if p["id"] == a.anchor)

    # RAW MODE: stub the PCA snap out of place_candidate
    # (--align keeps canon PCA on: upright snap + yaw snap compose)
    if not (a.pca or a.align):
        fpv.footprint_cardinal_angle = lambda m: 0.0

    # host front (render xz) — sub facing = host inheritance
    fdr = aplaced.get("front_dir_raw") or [0.0, -1.0]
    fdir = np.array([fdr[0] * r2r[0], fdr[1] * r2r[2]], np.float64)
    n = np.linalg.norm(fdir)
    fdir = fdir / n if n > 1e-6 else np.array([0.0, -1.0])

    placed_meshes, rows = [], []
    for s in asg["subs"]:
        if not s.get("start_box_render"):
            rows.append({"id": s["id"], "name": s["name"],
                         "status": "NO_BOARD"})
            continue
        p = picks.get(s["id"], {}).get("pick")
        if not p:
            rows.append({"id": s["id"], "name": s["name"],
                         "status": "NO_ASSET"})
            continue
        lo = np.asarray(s["start_box_render"]["lo"], np.float64)
        hi = np.asarray(s["start_box_render"]["hi"], np.float64)
        cand = {"uid": p["uid"], "perm": p["perm"], "k": p["k"],
                "scale": 1.0,
                "axis": 0 if (hi[0] - lo[0]) >= (hi[2] - lo[2]) else 2}
        mesh = load_asset(p["uid"])
        align_deg = 0.0
        if a.align:
            mesh, align_deg = align_upright(mesh)
        insts, face_deg, face_dot, pca_deg = fpv.place_candidate(
            mesh, cand, lo, hi, "floor", face_dir=fdir)
        allb = np.vstack([i.bounds for i in insts])
        placed_meshes += insts
        rows.append({
            "id": s["id"], "name": s["name"], "status": "PLACED",
            "board": s["board"], "uid": p["uid"], "perm": p["perm"],
            "k": cand["k"], "tile_axis": cand["axis"],
            "face_deg": face_deg, "face_dot": face_dot,
            "pca_deg": pca_deg, "align_deg": align_deg,
            "bounds_render": {"lo": allb.min(0).round(3).tolist(),
                              "hi": allb.max(0).round(3).tolist()},
            "start_box_render": s["start_box_render"],
        })

    # same-board overlap report (recorded, not resolved — raw pass)
    overlaps = []
    pl = [r for r in rows if r["status"] == "PLACED"]
    for i in range(len(pl)):
        for j in range(i + 1, len(pl)):
            if pl[i]["board"] != pl[j]["board"]:
                continue
            l1 = np.asarray(pl[i]["bounds_render"]["lo"])
            h1 = np.asarray(pl[i]["bounds_render"]["hi"])
            l2 = np.asarray(pl[j]["bounds_render"]["lo"])
            h2 = np.asarray(pl[j]["bounds_render"]["hi"])
            o = np.minimum(h1, h2) - np.maximum(l1, l2)
            if (o > 0).all():
                overlaps.append({"a": pl[i]["id"], "b": pl[j]["id"],
                                 "board": pl[i]["board"],
                                 "overlap_m": o.round(3).tolist()})

    odir = sdir / (a.out or ("cp5_align" if a.align else "cp5"))
    odir.mkdir(parents=True, exist_ok=True)
    rec = {"scene": a.scene, "anchor": a.anchor,
           "anchor_name": brec.get("anchor_name"),
           "picks_dir": a.picks_dir,
           "mode": ("align" if a.align else "pca" if a.pca else "raw"),
           "host_front_render_xz": fdir.round(3).tolist(),
           "n_placed": len(pl), "n_overlap_pairs": len(overlaps),
           "subs": rows, "overlaps": overlaps}
    (odir / "placements.json").write_text(json.dumps(rec, indent=1),
                                          encoding="utf-8")

    if not placed_meshes:
        # clean STALE artifacts from earlier runs — a leftover render
        # here shows things that are no longer placed (the stale-door
        # incident 08-05C)
        for f in ("front.png", "topdown.png", "composed.png",
                  "subs_preview.glb"):
            p = odir / f
            if p.exists():
                p.unlink()
        build_page(odir, rec)
        print(f"[cp5] nothing placeable on {a.anchor} — record + page "
              "written, stale renders removed")
        return

    # GLB in the RAW frame (fitted_preview.glb convention)
    to_raw = np.diag([-1.0, -1.0, 1.0, 1.0])
    out_sc = trimesh.Scene()
    for r, group in zip([r for r in rows if r["status"] == "PLACED"],
                        _group_insts(rows, placed_meshes)):
        for gi, inst in enumerate(group):
            m = inst.copy()
            m.apply_transform(to_raw)
            out_sc.add_geometry(m, node_name=f'{r["id"]}_t{gi}')
    (odir / "subs_preview.glb").write_bytes(
        out_sc.export(file_type="glb"))

    # ---- anchor meshes (render frame) for the ghost/composed views
    to_render = np.diag([-1.0, -1.0, 1.0, 1.0])
    gsc = trimesh.load(cdir / "fitted_preview.glb", force="scene")
    anchor_meshes = []
    for gname, geom in gsc.geometry.items():
        if gname.rsplit("_t", 1)[0] == a.anchor:
            m = geom.copy()
            m.apply_transform(to_render)
            anchor_meshes.append(m)

    # ---- cameras (frame anchor + subs)
    allpts = [np.vstack([m.bounds for m in anchor_meshes])]
    if placed_meshes:
        allpts.append(np.vstack([m.bounds for m in placed_meshes]))
    P = np.vstack(allpts)
    lo_all, hi_all = P.min(0), P.max(0)
    ctr = (lo_all + hi_all) / 2
    span = float(max(hi_all - lo_all))
    ply = paths.ply(a.scene)

    fdir3 = np.array([fdir[0], 0.0, fdir[1]])
    dist = max(2.4, span * 1.1)
    eye_f = ctr + fdir3 * dist
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
                         gpu=a.gpu).convert("RGBA")
        img.alpha_composite(meshes_rgba(anchor_meshes, e, l, u, fv, RES,
                                        alpha=0.30))
        img.alpha_composite(meshes_rgba(placed_meshes, e, l, u, fv, RES))
        img = img.convert("RGB")
        dr = ImageDraw.Draw(img)
        pose = look_at_pose(e, l, u)
        for b in boards:
            c = BOARD_COLORS[b["board"] % len(BOARD_COLORS)]
            draw_rect_at_height(dr, pose, fv, RES, b["x"][0], b["x"][1],
                                b["z"][0], b["z"][1], b["y"], c, 2)
        img.save(odir / f"{name}.png")

    # composed: anchor + subs solid on dark, no splat
    e, l, u, fv = eye_f, ctr.copy(), np.array([0.0, 1.0, 0.0]), fov_f
    img = Image.new("RGBA", (RES, RES), (32, 32, 32, 255))
    img.alpha_composite(meshes_rgba(anchor_meshes, e, l, u, fv, RES))
    img.alpha_composite(meshes_rgba(placed_meshes, e, l, u, fv, RES))
    img.convert("RGB").save(odir / "composed.png")

    build_page(odir, rec)
    print(f"[cp5] {rec['mode']} pass: {rec['n_placed']} placed, "
          f"{rec['n_overlap_pairs']} same-board overlap pairs")
    print(f"[cp5] wrote {odir / 'index.html'}")


def _group_insts(rows, placed_meshes):
    """re-split the flat placed_meshes list back per placed row (k
    instances each, in order)."""
    groups, i = [], 0
    for r in rows:
        if r["status"] != "PLACED":
            continue
        groups.append(placed_meshes[i:i + r["k"]])
        i += r["k"]
    return groups


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
         f'<title>sub rounds CP5 — placement ({rec["mode"]}) — '
         f'{rec["anchor"]}</title>',
         f'<style>{css}</style><div class="wrap">',
         f'<h1>Sub rounds — CP5: placement, {rec["mode"].upper()} pass</h1>',
         f'<p class="sub">{rec["scene"]} · anchor {rec["anchor"]} '
         f'({html.escape(str(rec["anchor_name"]))}) · {rec["n_placed"]} '
         f'placed · {rec["n_overlap_pairs"]} same-board overlap pairs '
         '(recorded, not resolved)</p>',
         '<div class="contract">'
         '<b>What this step gets:</b> CP3 start boxes (board-snapped), '
         'CP4 picks (asset + k copies), the host&rsquo;s front.<br>'
         '<b>What it decides:</b> the actual meshes standing on the '
         'boards — perm rotation, facing inherited from the host, k '
         'tiles filling the row, bottom on the board. RAW pass: the '
         'PCA cardinal snap is OFF (user: see the messy assets first); '
         'no jiggle, no declip.<br>'
         '<b>What a mistake looks like:</b> a book floating or sunk '
         'into a board, a row tiled along the wrong axis, spines '
         'facing the wall, or an overlap silently missing from the '
         'report.</div>']
    if rec["mode"] == "align" and (odir.parent / "cp5"
                                   / "front.png").exists():
        h.append('<div class="imgs">'
                 '<div><img src="../cp5/front.png"><p class="cap">'
                 '<b>RAW pass</b> — before the align trick</p></div>'
                 '<div><img src="front.png"><p class="cap"><b>ALIGN '
                 'pass</b> — OBB-to-cardinal upright snap + canon PCA'
                 '</p></div>'
                 '<div><img src="composed.png"><p class="cap">'
                 '<b>COMPOSED</b></p></div>'
                 '<div><img src="topdown.png"><p class="cap">'
                 '<b>TOP-DOWN</b></p></div></div>')
    else:
        h.append('<div class="imgs">'
                 '<div><img src="front.png"><p class="cap"><b>FRONT</b> — '
                 'placed subs solid, anchor ghosted, over the real splat'
                 '</p></div>'
                 '<div><img src="composed.png"><p class="cap"><b>COMPOSED'
                 '</b> — anchor + subs solid, no splat (what the scene '
                 'model now says)</p></div>'
                 '<div><img src="topdown.png"><p class="cap"><b>TOP-DOWN'
                 '</b></p></div></div>')
    h.append('<table><tr><th>sub</th><th>name</th><th>board</th>'
             '<th>k</th><th>face</th><th>face dot</th><th>pca</th>'
             '<th>align</th></tr>')
    for r in rec["subs"]:
        if r["status"] != "PLACED":
            h.append(f'<tr><td>{r["id"]}</td>'
                     f'<td>{html.escape(r["name"])}</td>'
                     f'<td colspan="6">{r["status"]}</td></tr>')
            continue
        h.append(f'<tr><td>{r["id"]}</td><td>{html.escape(r["name"])}</td>'
                 f'<td class="mono">B{r["board"]}</td>'
                 f'<td class="mono">{r["k"]}</td>'
                 f'<td class="mono">{r["face_deg"]}&deg;</td>'
                 f'<td class="mono">{r["face_dot"]}</td>'
                 f'<td class="mono">{r["pca_deg"]:g}&deg;</td>'
                 f'<td class="mono">{r.get("align_deg", 0):g}&deg;</td>'
                 '</tr>')
    h.append('</table>')
    if rec["overlaps"]:
        h.append('<table><tr><th>overlap pair</th><th>board</th>'
                 '<th>x·y·z overlap m</th></tr>')
        for o in rec["overlaps"]:
            h.append(f'<tr><td class="mono">{o["a"]} × {o["b"]}</td>'
                     f'<td class="mono">B{o["board"]}</td>'
                     f'<td class="mono">{o["overlap_m"]}</td></tr>')
        h.append('</table>')
    h.append('<div class="note"><b>Gate question (one look):</b> in the '
             'front view, do the placed books/basket stand ON their '
             'boards, spines out, roughly where the real ones are? '
             'Tilted/crooked = the raw-asset mess this pass is meant '
             'to expose — the PCA re-run is the next lever, on your '
             'call.</div>')
    h.append('<div id="lb"><img></div>')
    h.append(f'<script>{js}</script></div>')
    (odir / "index.html").write_text("\n".join(h), encoding="utf-8")


if __name__ == "__main__":
    main()
