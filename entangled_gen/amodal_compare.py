"""Photoreal comparison artifact for the amodal box methods.

Reads out/<scene>/amodal_boxes.json (amodal_boxes.py) and draws, per method,
the CHANGED boxes into the real RGB views: raw truncated box in light grey,
the method's extended box in the method color (same palette as the viewer
toggles). Unchanged boxes are faint context. Output:

  out/<scene>/amodal_comparison/<method>_<view>.png
  out/<scene>/amodal_comparison/COMPARISON.html   (numeric table + image grid)

Run: python amodal_compare.py --scene bedroom_marble
"""
import argparse
import json

import numpy as np
from PIL import Image, ImageDraw

import paths

r3 = paths.load_r3()

COLORS = {"splat": (48, 213, 200), "collider": (255, 165, 0),
          "prior": (255, 90, 210)}
RAW = (230, 230, 230)
FAINT = (110, 110, 110)


def draw_box(dr, cam, lo, hi, r2r, color, width, label=None):
    a = np.asarray(lo, np.float32) * r2r
    b = np.asarray(hi, np.float32) * r2r
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    corners = np.array([[x, y, z] for x in (lo[0], hi[0])
                        for y in (lo[1], hi[1]) for z in (lo[2], hi[2])], np.float32)
    u, v, z = cam.project(corners)
    if np.median(z) < 0.2:
        return
    ok = z > 0.2
    for i in range(8):
        for j in range(i + 1, 8):
            if bin(i ^ j).count("1") == 1 and ok[i] and ok[j]:
                dr.line([(u[i], v[i]), (u[j], v[j])], fill=color, width=width)
    if label and ok.any():
        dr.text((float(np.clip(u[ok].min(), 2, cam.w - 120)),
                 float(np.clip(v[ok].min() - 14, 2, cam.h - 14))),
                label, fill=color)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()
    sc = args.scene
    sd = paths.scene_dir(sc)
    am = json.loads((sd / "amodal_boxes.json").read_text())
    man = json.loads(paths.manifest(sc).read_text())
    r2r = np.array(man["frame"].get("raw_to_render", [1, 1, 1]), np.float32)
    raw_by_id = {o["id"]: o for o in man["objects"]}
    outdir = sd / "amodal_comparison"
    outdir.mkdir(exist_ok=True)

    views = []
    for metaf in sorted(paths.views_dir(sc).glob("gpu_yaw*.json")):
        meta = json.loads(metaf.read_text())
        imgf = paths.views_dir(sc) / meta["file"]
        if not imgf.exists():
            continue
        w, h = (int(t) for t in meta["res"].split("x"))
        cam = r3.Cam([float(t) for t in meta["cam"].split(",")],
                     [float(t) for t in meta["look"].split(",")],
                     [float(t) for t in meta["up"].split(",")],
                     float(meta["fov"]), w, h)
        views.append((metaf.stem, cam, imgf))

    grid = {}
    for meth, boxes in am["methods"].items():
        col = COLORS.get(meth, (255, 255, 255))
        changed = {b["id"]: b for b in boxes if b["changed"]}
        for stem, cam, imgf in views:
            im = Image.open(imgf).convert("RGB")
            dr = ImageDraw.Draw(im)
            for o in man["objects"]:
                if o["id"] not in changed:
                    draw_box(dr, cam, o["aabb_min"], o["aabb_max"], r2r, FAINT, 1)
            for oid, b in changed.items():
                o = raw_by_id[oid]
                draw_box(dr, cam, o["aabb_min"], o["aabb_max"], r2r, RAW, 2)
                draw_box(dr, cam, b["aabb_min"], b["aabb_max"], r2r, col, 3,
                         f'{oid} {b["label"]}')
            f = outdir / f"{meth}_{stem}.png"
            im.save(f)
            grid.setdefault(meth, []).append(f.name)
            print(f"[compare] wrote {f}", flush=True)

    # ---- numeric table + page ----
    sy, fy = am["sy"], am["floor_y"]
    meths = list(am["methods"])
    rows = []
    for o in man["objects"]:
        b0 = min(sy * (o["aabb_min"][1] - fy), sy * (o["aabb_max"][1] - fy))
        cells = ""
        for m in meths:
            e = next(x for x in am["methods"][m] if x["id"] == o["id"])
            cells += (f'<td class="chg">{e["bottom_e"]:.2f}</td>' if e["changed"]
                      else "<td>—</td>")
        rows.append(f'<tr><td>{o["id"]}</td><td>{o["label"]}</td>'
                    f'<td>{b0:.2f}</td>{cells}</tr>')
    imgs = ""
    for stem, _, _ in views:
        imgs += f"<h3>{stem}</h3><div class='row'>"
        for m in meths:
            imgs += (f"<figure><img src='{m}_{stem}.png'>"
                     f"<figcaption style='color:rgb{COLORS.get(m,(255,255,255))}'>"
                     f"{m}</figcaption></figure>")
        imgs += "</div>"
    warn = ("" if am.get("collider_iou", 1) >= 0.5 else
            f"<p class='warn'>⚠ collider registration IoU {am['collider_iou']}"
            " — collider boxes are UNRELIABLE until scale registration is solved.</p>")
    html = f"""<!doctype html><meta charset="utf-8"><title>amodal box comparison — {sc}</title>
<style>
 body{{background:#15171c;color:#dcdfe6;font:14px/1.5 system-ui;margin:20px}}
 table{{border-collapse:collapse;margin:12px 0}} td,th{{border:1px solid #333;padding:3px 10px}}
 .chg{{color:#8fd18f;font-weight:600}} .warn{{color:#e8b04b}}
 .row{{display:flex;gap:8px;overflow-x:auto}} figure{{margin:0}}
 figure img{{width:420px;display:block}} figcaption{{font-size:12px;text-align:center}}
</style>
<h1>amodal box methods — {sc}</h1>
<p>bottom elevation (m above floor): raw vs per-method (— = unchanged).
Grey box in images = raw truncated box; colored = method-extended.</p>{warn}
<table><tr><th>box</th><th>label</th><th>raw</th>{"".join(f"<th>{m}</th>" for m in meths)}</tr>
{"".join(rows)}</table>
{imgs}"""
    page = outdir / "COMPARISON.html"
    page.write_text(html, encoding="utf-8")
    print(f"[compare] wrote {page}", flush=True)


if __name__ == "__main__":
    main()
