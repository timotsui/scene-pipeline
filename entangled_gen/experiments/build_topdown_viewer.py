"""Build the TOP-DOWN ROTATION EXPERIMENT REVIEW PAGE (2026-08-05).

Separate page from build_rotq_viewer.py on purpose: that one shows the
CANON perspective pairs gate and is still valid for its own job. Its
layout caters to the two-panel photo|isolated-render stimulus, which this
experiment does not have -- reusing it would mean gutting it.

WHAT THIS SHOWS: for every object, the five images the judge actually saw
-- the top-down splat reference and the four candidate spins -- with the
degree mapping REVEALED (the user is judging the judge, not being tested),
the top-down verdict, and the canon verdict beside it.

Ordering is by usefulness, not by id: the objects where CANON SAYS
NON-ZERO come first, because those are the only ones where a rotation
check earns its keep, and they are where the two formats disagree.

Read-only: reads compose/topdown_check.json + compose/rotation_check.json
and the stimulus PNGs; writes ONE file, review_shots/topdown.html, with
relative paths that work straight off disk.

The page is for the USER's eyes (standing rule: Claude never concludes
from images). The only computed marks are arithmetic -- which candidate
each verdict corresponds to, and whether the two agree.

  python build_topdown_viewer.py [--scene bedroom_marble]
"""
import argparse
import html
import json
from pathlib import Path

DATA = Path(r"D:\T\Documents\GeorgiaTech\Summer2026\CS-8903-OVM\week7"
            r"\entangled_gen\out")

CSS = """
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:#141414;color:#e8e8e8;
     font:15px/1.55 "Segoe UI",system-ui,sans-serif}
.wrap{max-width:1680px;margin:0 auto;padding:28px 32px 120px}
h1{font-size:26px;margin:0 0 4px}
h2{font-size:19px;margin:44px 0 6px;padding-top:14px;
   border-top:1px solid #2e2e2e}
.sub{color:#9a9a9a;margin:0 0 22px}
.contract{background:#1c1c1c;border-left:3px solid #ffd479;
          padding:14px 18px;margin:18px 0 8px;border-radius:0 4px 4px 0}
.contract b{color:#ffd479}
.note{background:#1c1c1c;border-left:3px solid #4a90d9;padding:12px 18px;
      margin:18px 0;border-radius:0 4px 4px 0;color:#c9c9c9}
.summary{background:#1c1c1c;border:1px solid #2e2e2e;border-radius:6px;
         padding:12px 18px;margin:18px 0;display:flex;gap:34px;flex-wrap:wrap}
.summary b{font-size:22px;display:block}
.summary span{color:#9a9a9a;font-size:12.5px}
.card{background:#191919;border:1px solid #2b2b2b;border-radius:7px;
      padding:14px 16px 16px;margin:20px 0}
.card.differ{border-color:#5d3030}
.hd{display:flex;align-items:baseline;gap:12px;flex-wrap:wrap;
    margin-bottom:10px}
.hd .id{font-weight:600;font-size:16px}
.hd .nm{color:#cfcfcf}
.hd .meta{color:#8a8a8a;font-size:12.5px}
.row{display:grid;grid-template-columns:1.25fr 1fr 1fr 1fr 1fr;gap:10px}
.cell{min-width:0}
img.shot{width:100%;display:block;border-radius:4px;cursor:zoom-in;
         background:#000;border:3px solid transparent}
img.shot.td{border-color:#ff9d3d}
img.shot.canon{border-color:#4a90d9}
img.shot.both{border-color:#3fbf6f}
.cap{color:#8a8a8a;font-size:12.5px;margin:6px 0 0}
.cap b{color:#d8d8d8}
.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:9px;
     margin-left:6px;vertical-align:2px}
.tag.td{background:#3a2610;color:#ffc08a;border:1px solid #6d4620}
.tag.canon{background:#16283a;color:#9dc6ff;border:1px solid #2c4a6d}
.tag.both{background:#1c2a1c;color:#9dd89d;border:1px solid #2c5d2c}
.tag.differ{background:#4a2020;color:#ff9d9d;border:1px solid #6d2c2c}
.tag.agree{background:#1c2a1c;color:#9dd89d;border:1px solid #2c5d2c}
.why{color:#a8a8a8;font-size:13px;margin:11px 0 0;font-style:italic}
.legend{color:#9a9a9a;font-size:13px;margin:6px 0 18px}
.key i{font-style:normal;padding:1px 7px;border-radius:3px;margin-right:4px}
#lb{position:fixed;inset:0;background:#000d;display:none;z-index:99;
    overflow:auto;cursor:zoom-out;padding:20px;text-align:center}
#lb img{max-width:none}
#lb.on{display:block}
"""

JS = """
const lb=document.getElementById('lb'),lbi=lb.querySelector('img');
document.addEventListener('click',function(e){
  const im=e.target.closest('img.shot');
  if(im){lbi.src=im.src;lb.classList.add('on');window.scrollTo(0,0);}});
lb.addEventListener('click',function(){lb.classList.remove('on');});
document.addEventListener('keydown',function(e){
  if(e.key==='Escape')lb.classList.remove('on');});
"""


def card(r):
    oid = r["item"]
    mapping = {k: v for k, v in (r.get("mapping") or {}).items()}
    td_pick = r.get("pick")
    # which letter does canon's verdict correspond to?
    cdeg = r.get("canon_degrees")
    canon_pick = None
    if cdeg is not None:
        for le, dg in mapping.items():
            if abs(float(dg) - float(cdeg)) < 1e-6:
                canon_pick = le
    agree = r.get("agrees_with_canon")
    klass = "card" + ("" if agree else " differ")
    tag = ('<span class="tag agree">agree</span>' if agree
           else '<span class="tag differ">differ</span>')
    applied = r.get("rotcheck_applied_deg") or 0.0
    app_txt = (f" &middot; preview already carries {applied:g}&deg;"
               if applied else "")
    fp = r.get("footprint_m") or []
    h = [f'<div class="{klass}">',
         '<div class="hd">',
         f'<span class="id">{html.escape(oid)}</span>',
         f'<span class="nm">{html.escape(str(r.get("name") or ""))}</span>',
         f'<span class="meta">{html.escape(str(r.get("mount") or "?"))}'
         + (f" &middot; {fp[0]}&times;{fp[1]} m" if len(fp) == 2 else "")
         + app_txt + '</span>',
         f'<span class="tag td">top-down {r.get("degrees")}&deg; '
         f'({html.escape(str(r.get("confidence") or "?"))})</span>',
         f'<span class="tag canon">canon {cdeg}&deg; '
         f'({html.escape(str(r.get("canon_confidence") or "?"))})</span>',
         tag, '</div>', '<div class="row">']
    base = f"../topdown_check/{oid}_td"
    h.append('<div class="cell">'
             f'<img class="shot" src="{base}/reference.png">'
             '<p class="cap"><b>REAL</b> &mdash; splat from above, '
             'ceiling clipped</p></div>')
    for le in sorted(mapping):
        cls = "shot"
        marks = []
        if le == td_pick and le == canon_pick:
            cls += " both"; marks = ["top-down", "canon"]
        elif le == td_pick:
            cls += " td"; marks = ["top-down"]
        elif le == canon_pick:
            cls += " canon"; marks = ["canon"]
        m = (" &larr; " + " + ".join(marks)) if marks else ""
        h.append(f'<div class="cell"><img class="{cls}" '
                 f'src="{base}/candidate_{le}.png">'
                 f'<p class="cap"><b>{mapping[le]}&deg;</b>{m}</p></div>')
    h.append('</div>')
    if r.get("why"):
        h.append('<p class="why">top-down said: &ldquo;'
                 + html.escape(str(r["why"])) + '&rdquo;</p>')
    h.append('</div>')
    return "\n".join(h)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    a = ap.parse_args()
    cdir = DATA / a.scene / "compose"
    rec = json.loads((cdir / "topdown_check.json").read_text(encoding="utf-8"))
    runs = rec["runs"]
    sdir = cdir / "review_shots"
    sdir.mkdir(exist_ok=True)

    ans = [r for r in runs if r.get("degrees") is not None]
    agree = [r for r in ans if r.get("agrees_with_canon")]
    nz = [r for r in runs if r.get("canon_degrees") not in (0.0, None)]
    nz_ag = [r for r in nz if r.get("agrees_with_canon")]
    zz = [r for r in runs if r.get("canon_degrees") == 0.0]
    zz_ag = [r for r in zz if r.get("agrees_with_canon")]

    def pct(n, d):
        return f"{100*n/max(d,1):.0f}%"

    h = ['<!doctype html><meta charset="utf-8">',
         f'<title>top-down rotation experiment &mdash; {a.scene}</title>',
         f"<style>{CSS}</style>", '<div class="wrap">',
         '<h1>Top-down rotation experiment</h1>',
         f'<p class="sub">{html.escape(a.scene)} &middot; '
         f'{html.escape(str(rec.get("date")))} &middot; model '
         f'{html.escape(str(rec.get("model")))} &middot; one call per object '
         f'&middot; renders {rec.get("render_s")}s, wave '
         f'{rec.get("wave_s")}s</p>',
         '<div class="contract">'
         '<b>What this module gets:</b> one object already placed in the '
         'reconstruction, plus the splat of the real room.<br>'
         '<b>What it decides:</b> how far that object must turn about its '
         'vertical axis to match the real one &mdash; chosen from four '
         'candidates (0/90/180/270) by picking the matching picture, never '
         'by naming a facing.<br>'
         '<b>What a mistake looks like:</b> a confident 0&deg; on an object '
         'that is actually backwards &mdash; the fit loop then leaves it '
         'wrong and nothing downstream re-opens it.</div>',
         '<div class="note"><b>What changed vs canon:</b> only the camera. '
         'Canon judges from a real photograph and renders the candidates '
         'from that photograph&rsquo;s own camera. Here both sides are '
         'top-down: the reference is the splat rendered from above with the '
         'ceiling clipped, and the candidates use that same overhead camera. '
         'Same 4-candidate choice, same model, same one-call-per-object '
         'protocol.</div>',
         '<div class="note"><b>Reading the numbers:</b> verdicts are '
         'DELTAS on the current preview &mdash; objects that already carry a '
         'correction are marked, and 0&deg; is the right answer for them. '
         'Canon is <i>not</i> ground truth; it is the other format&rsquo;s '
         'answer. Where the two differ, someone has to look &mdash; that is '
         'what this page is for.</div>',
         '<div class="summary">',
         f'<div><b>{len(ans)}/{len(runs)}</b><span>answered</span></div>',
         f'<div><b>{len(agree)}/{len(ans)}</b>'
         f'<span>agree with canon ({pct(len(agree),len(ans))})</span></div>',
         f'<div><b>{len(nz_ag)}/{len(nz)}</b><span>agree where canon says '
         f'NON-ZERO ({pct(len(nz_ag),len(nz))})</span></div>',
         f'<div><b>{len(zz_ag)}/{len(zz)}</b><span>agree where canon says '
         f'0 ({pct(len(zz_ag),len(zz))})</span></div>',
         '</div>',
         '<p class="legend key">Border marks which candidate a verdict '
         'chose: <i style="background:#3a2610;color:#ffc08a">top-down</i>'
         '<i style="background:#16283a;color:#9dc6ff">canon</i>'
         '<i style="background:#1c2a1c;color:#9dd89d">both</i> '
         '&middot; click any image to zoom.</p>']

    h.append('<h2>1 &mdash; Canon says a real rotation is needed '
             f'({len(nz)} objects)</h2>')
    h.append('<p class="legend">The only objects where a rotation check '
             'earns its keep. If the two formats disagree here, one of them '
             'is leaving furniture backwards.</p>')
    for r in sorted(nz, key=lambda r: r["item"]):
        h.append(card(r))

    h.append(f'<h2>2 &mdash; Canon says leave it ({len(zz)} objects)</h2>')
    h.append('<p class="legend">Agreement here is cheap: a stage that '
             'answered 0&deg; to everything would score full marks in this '
             'section and be worth nothing.</p>')
    for r in sorted(zz, key=lambda r: r["item"]):
        h.append(card(r))

    rest = [r for r in runs if r.get("canon_degrees") is None]
    if rest:
        h.append(f'<h2>3 &mdash; No canon verdict ({len(rest)})</h2>')
        for r in sorted(rest, key=lambda r: r["item"]):
            h.append(card(r))

    h.append('<div id="lb"><img></div>')
    h.append(f"<script>{JS}</script></div>")
    out = sdir / "topdown.html"
    out.write_text("\n".join(h), encoding="utf-8")
    print(f"[view] wrote {out}")
    print(f"[view] {len(agree)}/{len(ans)} agree; non-zero "
          f"{len(nz_ag)}/{len(nz)}; zero {len(zz_ag)}/{len(zz)}")


if __name__ == "__main__":
    main()
