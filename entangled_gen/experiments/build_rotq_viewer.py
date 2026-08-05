"""Build the ROTATION-CHECK REVIEW VIEWER (2026-08-04, pairs edition).

CURRENT CONTENT (user 08-04: "take out the stale results, but keep and show
the reference image and the isolated image"): the SAME-CAMERA PAIRS gate.
Per object with detection evidence: the reference photograph (mirror
corrected) beside the placed object rendered ISOLATED (walls + floor kept,
other objects removed) from THE SAME CAMERA that took the photo, plus the
numeric box self-check (blue rendered box vs yellow detection box). No
model answers are shown -- the two-viewpoint run's answers are superseded
by this stimulus change and stay on disk in compose/rotation_check.json.

Read-only: reads refcam_check.json + the pair PNGs, writes ONE file --
review_shots/index.html -- with relative paths that work off disk.

The page is for the USER's eyes (standing rule: Claude never concludes
from images). The only computed marks are the arithmetic box check
(ok / MISS, center offset, IoU) and the no-reference tag.

  python build_rotq_viewer.py [--scene bedroom_marble]
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
.wrap{max-width:1500px;margin:0 auto;padding:28px 32px 120px}
h1{font-size:26px;margin:0 0 4px}
h2{font-size:19px;margin:40px 0 8px;padding-top:14px;
   border-top:1px solid #2e2e2e}
.sub{color:#9a9a9a;margin:0 0 22px}
.contract{background:#1c1c1c;border-left:3px solid #ffd479;
          padding:14px 18px;margin:18px 0 8px;border-radius:0 4px 4px 0}
.contract b{color:#ffd479}
.note{background:#1c1c1c;border-left:3px solid #4a90d9;
      padding:12px 18px;margin:18px 0;border-radius:0 4px 4px 0;color:#c9c9c9}
.summary{background:#1c1c1c;border:1px solid #2e2e2e;border-radius:6px;
         padding:12px 18px;margin:18px 0;display:flex;gap:34px;flex-wrap:wrap}
.summary b{font-size:22px;display:block}
.summary span{color:#9a9a9a;font-size:12.5px}
img.shot{width:100%;display:block;border-radius:4px;cursor:zoom-in;
         background:#000}
.cap{color:#8a8a8a;font-size:12.5px;margin:7px 0 0}
.tag{display:inline-block;font-size:11px;padding:1px 7px;border-radius:9px;
     margin-left:6px;vertical-align:2px}
.tag.miss{background:#4a2020;color:#ff9d9d;border:1px solid #6d2c2c}
.tag.ok{background:#1c2a1c;color:#9dd89d;border:1px solid #2c5d2c}
.tag.fb{background:#2a2340;color:#c4b5ff;border:1px solid #3d3360}
.meta{color:#8a8a8a;font-size:13px;font-weight:400}
#lb{position:fixed;inset:0;background:#000d;display:none;z-index:99;
    overflow:auto;cursor:zoom-out;padding:20px;text-align:center}
#lb img{max-width:none}
#lb.on{display:block}
.legend{color:#9a9a9a;font-size:13px;margin:6px 0 16px}
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    args = ap.parse_args()

    cdir = DATA / args.scene / "compose"
    sdir = cdir / "review_shots"
    chk = json.loads((cdir / "rotation_check" / "refcam"
                      / "refcam_check.json").read_text(encoding="utf-8"))
    rows = chk["rows"]

    # the same-camera run's answers, if it has landed (one per object)
    rec_p = cdir / "rotation_check.json"
    rec = (json.loads(rec_p.read_text(encoding="utf-8"))
           if rec_p.exists() else None)
    ans_by = ({r["item"]: r for r in rec["runs"]} if rec else {})

    n_ok = sum(1 for r in rows if r.get("status") == "ok")
    n_miss = sum(1 for r in rows if r.get("status") == "MISS")
    n_fb = sum(1 for r in rows if r.get("status") == "no_reference")

    # misses first, then by offset descending -- the eyeball order
    def rank(r):
        if r.get("status") == "MISS":
            return (0, -(r.get("center_off_px") or 0))
        if r.get("status") == "ok":
            return (1, -(r.get("center_off_px") or 0))
        return (2, 0)
    rows = sorted(rows, key=rank)

    P = []
    P.append('<div id="lb"><img alt=""></div><div class="wrap">')
    P.append("<h1>Rotation check &mdash; same-camera pairs "
             "(eyeball gate)</h1>")
    P.append(f'<p class="sub">scene <b>{html.escape(chk["scene"])}</b> '
             f'&middot; {html.escape(str(chk.get("date","")))} &middot; '
             "renders only, NO model calls yet</p>")

    P.append('<div class="contract">'
             "<b>What is under review.</b> The proposed stimulus for the "
             "canon rotation check: the placed object rendered "
             "<b>isolated</b> (walls and floor kept, other objects removed) "
             "from <b>the same camera that took its reference "
             "photograph</b>, so the judge compares two views of the same "
             "room from the same eye. Your call: do the pairs line up well "
             "enough to ask the rotation question on them?</div>")
    P.append('<div class="note">Left of each pair: the detection photograph, '
             "mirror corrected, its box in yellow. Right: the isolated "
             "render from the derived camera; the <b>blue box</b> is the "
             "placed object&rsquo;s own projection and must sit on the "
             "yellow one &mdash; that is the arithmetic self-check "
             "(offset/IoU below each pair), verified against the frame "
             "conversion. The earlier two-viewpoint answers are superseded "
             "by this stimulus change; they stay in "
             "<code>compose\\rotation_check.json</code> but are not shown. "
             "Click to enlarge, Esc to close.</div>")

    sm = ('<div class="summary">'
          f"<div><b>{n_ok}</b><span>pairs aligned (box check ok)"
          "</span></div>"
          f"<div><b>{n_miss}</b><span>MISS &mdash; placed box not where "
          "the photo saw it</span></div>"
          f"<div><b>{n_fb}</b><span>no reference (plausibility fallback, "
          "no pair)</span></div>")
    if rec:
        runs = rec["runs"]
        n_ans = sum(1 for r in runs if r["degrees"] is not None)
        n_nz = sum(1 for r in runs if r["degrees"] not in (None, 0.0))
        tot_s = sum(r.get("model_s") or 0 for r in runs)
        sm += (f"<div><b>{n_ans}/{len(runs)}</b><span>calls answered "
               "(ONE per object)</span></div>"
               f"<div><b>{n_nz}</b><span>non-zero answers</span></div>"
               f'<div><b>{rec.get("wave_s",0)/60:.1f} min</b><span>wave '
               f'wall at {rec.get("jobs","?")} lanes</span></div>'
               f"<div><b>{tot_s/60:.0f} min</b><span>model time paid "
               f'({tot_s/max(rec.get("wave_s",1),1):.1f}&times; '
               "compression)</span></div>")
    P.append(sm + "</div>")

    # ---- the running compass experiment (bed), shown first: its own
    # record file, saved aside so full-scene rebuilds don't clobber it
    comp_p = cdir / "rotation_check_compass_bed.json"
    if comp_p.exists():
        crec = json.loads(comp_p.read_text(encoding="utf-8"))
        for cr in crec["runs"]:
            coid = cr["item"]
            P.append(f'<h2>COMPASS EXPERIMENT &mdash; {html.escape(coid)} '
                     f'{html.escape(cr["name"])} <span class="meta">&middot; '
                     "two-step describe, rose drawn beside the object, turn "
                     "computed from the two facings &middot; "
                     f'{cr.get("model_s",0):.0f} s, '
                     f'{(cr.get("cost") or {}).get("num_turns","?")} turns'
                     "</span></h2>")
            P.append('<p class="legend">real faces '
                     f'<b>{html.escape(str(cr.get("real_faces")))}</b> '
                     "&mdash; &ldquo;"
                     f'{html.escape(str(cr.get("real_desc","")))}'
                     "&rdquo;<br>placed faces "
                     f'<b>{html.escape(str(cr.get("placed_faces")))}</b> '
                     "&mdash; &ldquo;"
                     f'{html.escape(str(cr.get("placed_desc","")))}'
                     "&rdquo;<br>computed turn "
                     f'<b>{cr.get("degrees","?")}&deg;</b> '
                     f'({html.escape(str(cr.get("degrees_source","")))}, '
                     f'confidence {html.escape(str(cr.get("confidence")))})'
                     "</p>")
            for img, lab in ((f"../rotation_check/{coid}_ref.png",
                              "reference photo, mirror corrected, rose "
                              "drawn beside the object"),
                             (f"../rotation_check/{coid}_same/same.png",
                              "isolated same-camera render, the identical "
                              "rose")):
                if (cdir / "rotation_check" / Path(img).relative_to(
                        "../rotation_check")).exists():
                    P.append(f'<img class="shot" loading="lazy" src="{img}" '
                             f'alt="{img}"><p class="cap">{lab} &middot; '
                             f"{img}</p>")

    for r in rows:
        oid, name = r["item"], r["name"]
        st = r.get("status")
        head = f"{html.escape(oid)} &mdash; {html.escape(name)}"
        if r.get("swap_origin"):
            head += (f' <span class="tag fb">swap &mdash; reference is the '
                     f'replaced {html.escape(str(r["swap_origin"]))}</span>')
        if st == "MISS":
            head += ' <span class="tag miss">box check MISS</span>'
        elif st == "ok":
            head += ' <span class="tag ok">aligned</span>'
        elif st == "no_reference":
            head += (' <span class="tag fb">strict add &mdash; no reference, '
                     "keeps the plausibility stimuli</span>")
        if st in ("ok", "MISS"):
            head += (f' <span class="meta">&middot; view '
                     f'{html.escape(str(r.get("view","")))} &middot; offset '
                     f'{r.get("center_off_px","?")} px &middot; IoU '
                     f'{r.get("iou","?")}</span>')
        a = ans_by.get(oid)
        if a and a["degrees"] is not None:
            v = a["degrees"]
            cls = "z" if abs(v) < 1e-6 else "nz"
            head += (f' <span class="meta">&middot; says <b class="{cls}" '
                     f'style="font-size:15px">{v:+.0f}&deg;</b> '
                     f'({html.escape(str(a.get("confidence","?")))}) '
                     f'&middot; {a.get("model_s",0):.0f} s, '
                     f'{(a.get("cost") or {}).get("num_turns","?")} '
                     "turns</span>")
        elif a:
            head += ' <span class="tag miss">NO ANSWER</span>'
        P.append(f"<h2>{head}</h2>")
        if a and a.get("why"):
            P.append(f'<p class="legend" style="margin:2px 0 10px">its '
                     f'stated reason (verbatim): '
                     f'&ldquo;{html.escape(str(a["why"]))}&rdquo;</p>')
        sheetp = cdir / "rotation_check" / "sheets" / f"{oid}.png"
        if a and sheetp.exists():
            sheet = f"../rotation_check/sheets/{oid}.png"
            P.append(f'<img class="shot" loading="lazy" src="{sheet}" '
                     f'alt="{sheet}"><p class="cap">as placed | answer '
                     f"applied &middot; {sheet}</p>")
        pair = f"../rotation_check/refcam/{oid}_pair.png"
        if (cdir / "rotation_check" / "refcam" / f"{oid}_pair.png").exists():
            P.append(f'<img class="shot" loading="lazy" src="{pair}" '
                     f'alt="{pair}"><p class="cap">reference | as placed '
                     f"(the gate pair) &middot; {pair}</p>")

    P.append('<h2>Where this came from</h2><p class="legend">'
             "pairs + check <code>compose\\rotation_check\\refcam\\</code> "
             "&middot; built by <code>experiments/refcam_pairs.py</code> "
             "(camera = detection sidecar via the pano&rarr;raw mirror "
             "mapping pano_lift.py lifts with, then raw&rarr;render) "
             "&middot; page by <code>experiments/build_rotq_viewer.py"
             "</code> &middot; superseded runs: rotation_check.json "
             "(two-viewpoint canon run), rotq/, rotref/, rotref_one/ "
             "(experiments).</p></div>")

    doc = ("<!doctype html><html><head><meta charset='utf-8'>"
           "<title>Rotation check &mdash; same-camera pairs</title>"
           f"<style>{CSS}</style></head><body>"
           + "\n".join(P) +
           f"<script>{JS}</script></body></html>")

    out = sdir / "index.html"
    out.write_text(doc, encoding="utf-8")
    print(f"[viewer] wrote {out}  ({len(doc)/1024:.1f} kB)")


if __name__ == "__main__":
    main()
