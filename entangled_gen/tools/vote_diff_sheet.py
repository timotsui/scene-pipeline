"""Build a side-by-side review sheet comparing two slicevote preview manifests.

WHAT IT GETS   two scene_manifest_slicevote_preview.json files (a BASE and a
               NEW), plus the graph crops folder for object thumbnails.
WHAT IT DECIDES  nothing. It ranks and displays. Every verdict on whether a
               box got better or worse is the reader's.
WHAT A MISTAKE LOOKS LIKE  a row whose numbers don't match the manifests, a
               thumbnail showing the wrong object, or a "changed" row that
               only moved by the carved->voted rename.

Usage:
  python vote_diff_sheet.py --scene living_marble \
      --base out/<scene>/_powertest_backup/scene_manifest_slicevote_preview.json \
      --new  out/<scene>/scene_manifest_slicevote_preview.json \
      --out  out/<scene>/vote_diff_sheet.html
"""

import argparse
import html
import json
import re
from pathlib import Path

# Below this (metres) a box move is noise, not news. Same threshold the
# console diff uses, so the two agree on what counts as "changed".
THRESH = 0.02

AXES = ("x", "y", "z")


def load(p):
    j = json.loads(Path(p).read_text(encoding="utf-8"))
    return j, {o["id"]: o for o in j.get("objects", [])}


def status_of(label):
    """'chair (voted_pano 3v/6)' -> 'voted_pano 3v/6'. The parenthetical is
    the vote status; the bare word before it is the object name."""
    m = re.search(r"\(([^)]*)\)\s*$", label or "")
    return m.group(1) if m else ""


def name_of(label):
    return re.sub(r"\s*\([^)]*\)\s*$", "", label or "").strip()


def canonical_status(s):
    """The 2026-08 rename: 'carved*' became 'voted*'. A row that differs ONLY
    by that word has not actually changed, and must not be reported as if it
    had — the vocabulary moved, the verdict didn't."""
    return s.replace("carved", "voted")


def crops_for(crops_dir, oid, limit=2):
    if not crops_dir.is_dir():
        return []
    return sorted(crops_dir.glob(f"{oid}_*.png"))[:limit]


def rel(frm, to):
    try:
        return to.relative_to(frm).as_posix()
    except ValueError:
        import os
        return Path(os.path.relpath(to, frm)).as_posix()


def build(base_p, new_p, out_p, crops_dir):
    bmeta, bmap = load(base_p)
    nmeta, nmap = load(new_p)
    out_p = Path(out_p)
    outdir = out_p.parent

    rows = []
    for oid in sorted(set(bmap) & set(nmap)):
        b, n = bmap[oid], nmap[oid]
        dsize = [round(n["size"][i] - b["size"][i], 3) for i in range(3)]
        dctr = [round(n["center"][i] - b["center"][i], 3) for i in range(3)]
        mx = max(max(abs(v) for v in dsize), max(abs(v) for v in dctr))
        volb = b["size"][0] * b["size"][1] * b["size"][2]
        voln = n["size"][0] * n["size"][1] * n["size"][2]
        sb, sn = status_of(b["label"]), status_of(n["label"])
        rows.append({
            "id": oid,
            "name": name_of(n["label"]),
            "sb": sb, "sn": sn,
            # a rename-only status change is NOT a real change
            "status_real": canonical_status(sb) != canonical_status(sn),
            "status_renamed": sb != sn and canonical_status(sb) == canonical_status(sn),
            "dsize": dsize, "dctr": dctr, "max": round(mx, 3),
            "sizeb": b["size"], "sizen": n["size"],
            "volpct": round(100.0 * (voln - volb) / volb, 1) if volb > 0 else 0.0,
            "prov_b": (b.get("prov") or {}).get("run_id", "?"),
            "prov_n": (n.get("prov") or {}).get("run_id", "?"),
            "crops": [rel(outdir, c) for c in crops_for(crops_dir, oid)],
        })

    moved = [r for r in rows if r["max"] >= THRESH or r["status_real"]]
    still = [r for r in rows if r not in moved]
    moved.sort(key=lambda r: -r["max"])
    still.sort(key=lambda r: r["id"])
    renamed = sum(1 for r in rows if r["status_renamed"])

    only_b = sorted(set(bmap) - set(nmap))
    only_n = sorted(set(nmap) - set(bmap))

    def meta_card(title, m, path):
        return f"""<div class="card">
  <h3>{html.escape(title)}</h3>
  <table class="meta">
    <tr><td>run_id</td><td><code>{html.escape(str(m.get('run_id')))}</code></td></tr>
    <tr><td>run_kind</td><td><code>{html.escape(str(m.get('run_kind')))}</code></td></tr>
    <tr><td>mixed_provenance</td><td><code>{html.escape(str(m.get('mixed_provenance')))}</code></td></tr>
    <tr><td>canon_eligible</td><td><code>{html.escape(str(m.get('canon_eligible')))}</code></td></tr>
    <tr><td>params_hash</td><td><code>{html.escape(str(m.get('params_hash')))}</code></td></tr>
    <tr><td>source_sha</td><td><code>{html.escape(str(m.get('source_sha')))}</code></td></tr>
    <tr><td>objects</td><td><code>{m.get('n_objects')}</code></td></tr>
  </table>
  <p class="path">{html.escape(str(path))}</p>
</div>"""

    def dcell(v):
        if abs(v) < 0.001:
            return '<td class="d zero">0</td>'
        cls = "up" if v > 0 else "dn"
        return f'<td class="d {cls}">{v:+.3f}</td>'

    def row_html(r):
        thumbs = "".join(
            f'<img src="{html.escape(c)}" loading="lazy" alt="{r["id"]}">'
            for c in r["crops"]) or '<span class="nocrop">no crop</span>'
        sizeb = " &times; ".join(f"{v:.3f}" for v in r["sizeb"])
        sizen = " &times; ".join(f"{v:.3f}" for v in r["sizen"])
        stat = (f'<span class="ren">{html.escape(r["sb"])} &rarr; {html.escape(r["sn"])} '
                f'<em>(rename only)</em></span>' if r["status_renamed"]
                else (f'<span class="chg">{html.escape(r["sb"])} &rarr; {html.escape(r["sn"])}</span>'
                      if r["status_real"] else html.escape(r["sn"])))
        vol = r["volpct"]
        volcls = "big" if abs(vol) >= 25 else ""
        return f"""<tr>
  <td class="thumb">{thumbs}</td>
  <td class="id"><b>{r['id']}</b><br><span class="nm">{html.escape(r['name'])}</span></td>
  <td class="status">{stat}<br><span class="prov">base run: <code>{html.escape(r['prov_b'])}</code></span></td>
  <td class="sz"><span class="old">{sizeb}</span><br><span class="new">{sizen}</span></td>
  {dcell(r['dsize'][0])}{dcell(r['dsize'][1])}{dcell(r['dsize'][2])}
  {dcell(r['dctr'][0])}{dcell(r['dctr'][1])}{dcell(r['dctr'][2])}
  <td class="max">{r['max']:.3f}</td>
  <td class="vol {volcls}">{vol:+.1f}%</td>
</tr>"""

    head = """<tr>
  <th>crops</th><th>object</th><th>vote status</th>
  <th>size old<br>size new</th>
  <th colspan="3">&Delta; size (x,y,z) m</th>
  <th colspan="3">&Delta; center (x,y,z) m</th>
  <th>max</th><th>volume</th>
</tr>"""

    doc = f"""<!doctype html>
<meta charset="utf-8">
<title>Vote run diff &mdash; {html.escape(str(nmeta.get('scene', '')))}</title>
<style>
 :root {{ --bg:#f7f7f8; --fg:#1a1a1a; --mut:#666; --line:#ddd; --card:#fff;
          --up:#0a7d32; --dn:#b3261e; --warn:#8a6d00; }}
 @media (prefers-color-scheme: dark) {{
   :root {{ --bg:#151517; --fg:#e8e8ea; --mut:#9a9aa2; --line:#333;
            --card:#1e1e21; --up:#4ade80; --dn:#f87171; --warn:#d4b106; }}
 }}
 body {{ background:var(--bg); color:var(--fg); margin:0; padding:24px;
        font:14px/1.5 -apple-system,Segoe UI,Roboto,sans-serif; }}
 h1 {{ font-size:20px; margin:0 0 4px; }}
 .sub {{ color:var(--mut); margin:0 0 20px; }}
 .cards {{ display:flex; gap:16px; flex-wrap:wrap; margin-bottom:20px; }}
 .card {{ background:var(--card); border:1px solid var(--line); border-radius:8px;
         padding:12px 16px; min-width:280px; }}
 .card h3 {{ margin:0 0 8px; font-size:13px; text-transform:uppercase;
            letter-spacing:.05em; color:var(--mut); }}
 table.meta td {{ padding:1px 8px 1px 0; font-size:12px; }}
 table.meta td:first-child {{ color:var(--mut); }}
 .path {{ font-size:11px; color:var(--mut); word-break:break-all; margin:8px 0 0; }}
 .note {{ background:var(--card); border-left:3px solid var(--warn);
         padding:10px 14px; border-radius:4px; margin:0 0 20px; }}
 .wrap {{ overflow-x:auto; }}
 table.diff {{ border-collapse:collapse; width:100%; background:var(--card);
              border:1px solid var(--line); border-radius:8px; }}
 table.diff th {{ text-align:left; font-size:11px; text-transform:uppercase;
                 letter-spacing:.04em; color:var(--mut); padding:8px;
                 border-bottom:1px solid var(--line); white-space:nowrap; }}
 table.diff td {{ padding:8px; border-bottom:1px solid var(--line);
                 vertical-align:top; }}
 .thumb img {{ height:56px; border-radius:4px; margin-right:4px;
              border:1px solid var(--line); }}
 .nocrop {{ color:var(--mut); font-size:11px; }}
 .id b {{ font-family:ui-monospace,Consolas,monospace; }}
 .nm {{ color:var(--mut); font-size:12px; }}
 .sz {{ font-family:ui-monospace,Consolas,monospace; font-size:12px;
       white-space:nowrap; }}
 .sz .old {{ color:var(--mut); }}
 td.d {{ font-family:ui-monospace,Consolas,monospace; text-align:right;
        white-space:nowrap; }}
 .d.up {{ color:var(--up); }} .d.dn {{ color:var(--dn); }}
 .d.zero {{ color:var(--mut); }}
 .max {{ font-family:ui-monospace,Consolas,monospace; text-align:right;
        font-weight:600; }}
 .vol {{ font-family:ui-monospace,Consolas,monospace; text-align:right; }}
 .vol.big {{ font-weight:700; color:var(--warn); }}
 .prov {{ font-size:11px; color:var(--mut); }}
 .ren {{ color:var(--mut); }} .ren em {{ font-style:normal; }}
 .chg {{ color:var(--warn); font-weight:600; }}
 h2 {{ font-size:15px; margin:28px 0 10px; }}
</style>
<h1>Vote run diff &mdash; {html.escape(str(nmeta.get('scene', '')))}</h1>
<p class="sub">Both sides are output of the same module (<code>slicevote.py</code>).
Nothing downstream (J8 / J8s / J9 / materialize) writes this file &mdash; they read it.</p>

<div class="cards">
{meta_card('BASE (old run)', bmeta, base_p)}
{meta_card('NEW (this run)', nmeta, new_p)}
</div>

<div class="note">
<b>Read the status column carefully.</b> {renamed} of the rows show a status change
that is <em>only</em> the <code>carved&nbsp;&rarr;&nbsp;voted</code> vocabulary rename.
Those are marked <em>(rename only)</em> and are not counted as changed.
A row counts as changed when a box moved by &ge;&nbsp;{THRESH}&nbsp;m on any axis,
or its status changed for a real reason.
<br><br>
<b>Crops identify the object, not the box.</b> They are cut from detector
rectangles and may not frame the current box &mdash; use them to see <em>what</em>
the row is, not to judge extents.
</div>

<p><b>{len(rows)}</b> objects compared &middot;
<b>{len(moved)}</b> changed &middot;
<b>{len(still)}</b> unchanged &middot;
<b>{renamed}</b> rename-only status changes
{('&middot; <b>only in base:</b> ' + ', '.join(only_b)) if only_b else ''}
{('&middot; <b>only in new:</b> ' + ', '.join(only_n)) if only_n else ''}
</p>

<h2>Changed &mdash; largest movement first</h2>
<div class="wrap"><table class="diff">{head}
{''.join(row_html(r) for r in moved)}
</table></div>

<h2>Unchanged ({len(still)})</h2>
<div class="wrap"><table class="diff">{head}
{''.join(row_html(r) for r in still)}
</table></div>
"""
    out_p.write_text(doc, encoding="utf-8")
    return out_p, len(rows), len(moved), len(still), renamed


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--new", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--crops", required=True)
    a = ap.parse_args()
    p, n, m, s, r = build(a.base, a.new, a.out, Path(a.crops))
    print(f"[votediff] wrote {p}")
    print(f"[votediff] {n} compared / {m} changed / {s} unchanged / {r} rename-only")
