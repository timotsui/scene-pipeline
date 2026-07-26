"""Provenance trace for a merged object: which detections, from which sweep
frames, built this box — with image evidence crops.

For each member: source frame crop (det box + 25% margin, box drawn), label,
score, truncation/trust flags, its 3D bounds, and which fused faces it is
closest to setting. Face rows show the trusted-bound distribution so the
union-vs-quantile difference is visible per face.

Run:  python trace_object.py --scene bedroom_marble --man robust \
          --obj obj_077 obj_079
Writes out/<scene>/seg_sweep/trace/<man>_<obj>.html (+ crops).
"""
import argparse, json
from pathlib import Path
import numpy as np
from PIL import Image, ImageDraw

import paths

MAN_FILES = {"robust": "scene_manifest_sweep_robust.json",
             "union": "scene_manifest_sweep.json"}
BOUND_NAMES = ["xlo", "xhi", "ylo", "yhi", "zlo", "zhi"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--man", default="robust", choices=list(MAN_FILES))
    ap.add_argument("--obj", nargs="+", required=True)
    ap.add_argument("--job", default="job_high")
    a = ap.parse_args()
    sc = a.scene
    sd = paths.scene_dir(sc)
    seg = sd / "seg_sweep"
    frames_dir = sd / "analyzer" / a.job / "frames"
    man = json.loads((sd / MAN_FILES[a.man]).read_text())
    pool = json.loads((seg / "lift_pool.json").read_text())["pool"]
    tdir = seg / "trace"
    tdir.mkdir(exist_ok=True)

    for oid in a.obj:
        o = next((x for x in man["objects"] if x["id"] == oid), None)
        if o is None:
            print(f"[trace] {oid}: not in {MAN_FILES[a.man]}")
            continue
        if "members" not in o:
            raise SystemExit("manifest lacks 'members' — re-run the merge "
                             "(lift_sweep --remerge-q ...) first")
        mems = [pool[i] for i in o["members"]]
        crops_html = []
        for k, L in enumerate(sorted(mems, key=lambda m: -m["score"])):
            imgf = frames_dir / f"{L['view']}.png"
            b = L["box"]
            im = Image.open(imgf).convert("RGB")
            dr = ImageDraw.Draw(im)
            dr.rectangle([b["xmin"], b["ymin"], b["xmax"], b["ymax"]],
                         outline=(255, 60, 60), width=3)
            mw = (b["xmax"] - b["xmin"]) * 0.25 + 8
            mh = (b["ymax"] - b["ymin"]) * 0.25 + 8
            crop = im.crop((max(0, b["xmin"] - mw), max(0, b["ymin"] - mh),
                            min(im.width, b["xmax"] + mw),
                            min(im.height, b["ymax"] + mh)))
            cf = tdir / f"{a.man}_{oid}_{k:02d}_{L['view']}.png"
            crop.save(cf)
            lo, hi = np.array(L["lo"]), np.array(L["hi"])
            bad = [BOUND_NAMES[2 * ax + s] for ax in range(3)
                   for s in (0, 1) if not L["trust"][2 * ax + s]]
            crops_html.append(
                f'<div class=mem><a href="{cf.name}" target=_blank>'
                f'<img src="{cf.name}"></a><div class=cap>'
                f'#{k} <b>{L["view"]}</b> · score {L["score"]:.2f}'
                f'{" · <span class=tr>CLIPPED: " + ",".join(bad) + "</span>" if bad else " · whole"}'
                f'<br>lo {np.round(lo, 2).tolist()}<br>'
                f'hi {np.round(hi, 2).tolist()}</div></div>')

        # per-face bound distributions
        face_rows = ""
        for ax, axn in enumerate("xyz"):
            for s, side in ((0, "lo"), (1, "hi")):
                vals = sorted(
                    (m["lo"][ax] if s == 0 else m["hi"][ax])
                    for m in mems if m["trust"][2 * ax + s])
                fused = (o["aabb_min"] if s == 0 else o["aabb_max"])[ax]
                w = "weak" if f"lower_bound_{axn}{side}" in str(o["flags"]) else ""
                face_rows += (
                    f'<tr class="{w}"><td>{axn}{side}</td>'
                    f'<td>{fused:+.2f}</td><td>{len(vals)}</td>'
                    f'<td>{" ".join(f"{v:+.2f}" for v in vals[:14])}'
                    f'{" …" if len(vals) > 14 else ""}</td></tr>')

        html = f"""<!doctype html><meta charset="utf-8">
<title>trace {oid} — {a.man}</title>
<style>body{{font:14px system-ui;background:#14161a;color:#dfe3ea;margin:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(220px,1fr));gap:10px}}
.mem img{{width:100%;border:1px solid #333;border-radius:6px}}
.cap{{font-size:12px;color:#9aa3b0}}.tr{{color:#ffb020}}
table{{border-collapse:collapse;margin:10px 0}}
td,th{{border:1px solid #333;padding:3px 8px;font-size:13px}}
tr.weak{{background:#3a2410}}b{{color:#7fd67f}}
.note{{color:#9aa3b0;max-width:100ch}}</style>
<h1>{oid} — {o['label']} <span style="color:#888">({a.man} merge)</span></h1>
<p class=note>fused box: center {o['center']} · size {o['size']} ·
score {o['score']} · {o['n_detections']} detections ({o['n_whole']} whole)
· flags {o['flags'] or '—'} · views {len(o['views'])}</p>
<h2>Fused faces (highlighted = weak: no clean witness)</h2>
<table><tr><th>face</th><th>fused</th><th>#trusted</th>
<th>trusted member values (sorted)</th></tr>{face_rows}</table>
<h2>Member detections ({len(mems)}, best score first)</h2>
<div class=grid>{''.join(crops_html)}</div>"""
        outf = tdir / f"{a.man}_{oid}.html"
        outf.write_text(html, encoding="utf-8")
        print(f"[trace] wrote {outf}  ({len(mems)} members)")


if __name__ == "__main__":
    main()
