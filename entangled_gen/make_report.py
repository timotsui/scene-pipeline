"""
Build out/report.html — one page comparing all generated scenes:
prompt, photoreal views, lift plan, envelope heatmap, and the spatial-correctness
metrics (floor coverage, warp, object count). Open directly in a browser.

python make_report.py
"""
import html, json, re
from pathlib import Path
import numpy as np

import paths

HERE = Path(__file__).parent
OUT = HERE / "out"

KNOWN_PROMPTS = {
    "playroom": "a cozy playroom with a rug and shelves (seed 0)",
    "bedroom": "a bedroom with a bed, a nightstand and a wardrobe (seed 0)",
    "livingroom": "a living room with a sofa, a coffee table and a television (seed 0)",
    "kitchen": "a kitchen with a dining table and chairs (seed 0)",
}


def prompts_from_logs():
    out = dict(KNOWN_PROMPTS)
    for qlog in (OUT / "logs" / "queue.log", OUT / "logs" / "queue2.log"):
        if not qlog.exists():
            continue
        for m in re.finditer(r"launching (\w+) \(seed (\d+)\): (.+)", qlog.read_text(encoding="utf-8", errors="replace")):
            out[m.group(1)] = f"{m.group(3).strip()} (seed {m.group(2)})"
    return out


def img_cell(path, w=260):
    if path and path.exists():
        rel = path.relative_to(OUT).as_posix()
        return f'<a href="{rel}"><img src="{rel}" width="{w}"></a>'
    return '<span class="miss">—</span>'


def main():
    prompts = prompts_from_logs()
    scenes = paths.gen_scenes()
    rows = []
    for sc in scenes:
        views = paths.views_dir(sc)
        seg = paths.seg_dir(sc)
        manf = paths.manifest(sc)
        envf = paths.envelope_npz(sc)
        metrics = []
        if envf.exists():
            z = np.load(envf)
            fd = z["floor_dev"]
            cov = float(np.isfinite(fd).mean())
            good = fd[np.isfinite(fd)]
            warp = (f"{np.percentile(good, 5):+.2f}..{np.percentile(good, 95):+.2f} m"
                    if len(good) else "n/a")
            metrics.append(f"floor coverage <b>{cov:.0%}</b>")
            metrics.append(f"floor warp p5..p95 <b>{warp}</b>")
        if manf.exists():
            man = json.loads(manf.read_text())
            metrics.append(f"objects lifted <b>{len(man['objects'])}</b>")
            fr = man["frame"]
            metrics.append(f"floor y {fr['floor_y']} · ceil y {fr['ceiling_y']}")
        rows.append(f"""
<tr>
 <td class="sc"><b>{sc}</b><div class="prompt">{html.escape(prompts.get(sc, '?'))}</div>
     <div class="metrics">{'<br>'.join(metrics) or '—'}</div></td>
 <td>{img_cell(views / 'gpu_yaw000.webp')}</td>
 <td>{img_cell(views / 'gpu_yaw270.webp')}</td>
 <td>{img_cell(seg / f'manifest_plan_{sc}.png')}</td>
 <td>{img_cell(paths.envelope_heatmap(sc), 380)}</td>
</tr>""")

    doc = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>entangled_gen scene report</title>
<style>
 body {{ font: 13px monospace; background: #16161c; color: #ccc; margin: 16px; }}
 table {{ border-collapse: collapse; }}
 td, th {{ border: 1px solid #333; padding: 8px; vertical-align: top; }}
 th {{ background: #22222c; }}
 .sc {{ min-width: 230px; }}
 .prompt {{ color: #9ab; margin: 6px 0; max-width: 240px; }}
 .metrics {{ color: #cda; line-height: 1.6; }}
 .miss {{ color: #555; }}
 img {{ border: 1px solid #444; }}
 h1 {{ font-size: 16px; color: #7fd67f; }}
</style></head><body>
<h1>entangled_gen — generated scenes ({len(scenes)})</h1>
<p>Spatial-correctness read: floor coverage = % of room area with detectable floor
(the rest is holes/eaves); warp = local floor height spread (flat real room ≈ 0).
Click images for full size. Regenerate with <code>python make_report.py</code>.</p>
<table>
<tr><th>scene / prompt / metrics</th><th>view yaw000</th><th>view yaw270</th>
<th>lift plan</th><th>habitable envelope</th></tr>
{''.join(rows)}
</table></body></html>"""
    f = OUT / "report.html"
    f.write_text(doc, encoding="utf-8")
    print(f"wrote {f} ({len(scenes)} scenes)")


if __name__ == "__main__":
    main()
