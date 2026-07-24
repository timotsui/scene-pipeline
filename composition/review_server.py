"""Retrieval inspection viewer — checkpoint 1 of the stage-by-stage rework.

LOOK-ONLY (no picking; asset selection will be automated later): one row per
manifest box — the box cropped out of the real RGB views (3D AABB projected
with the frame-verified raw->render transform, green box edges drawn for
context) next to the shortlist2 candidates as thumbnail cards sorted by fit
score. Candidates whose native size fits INSIDE the box (after the fit's yaw
and tiling sub-box split) get a highlight frame.

Run:  python review_server.py --scene bedroom_marble --port 8322
Crops are written to package/review_crops/ at startup (--recrop to redo).
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from comp_paths import paths
from crops import make_crops
from thumbs import thumb_path


PAGE = """<!doctype html><meta charset="utf-8"><title>retrieval inspection</title>
<style>
 body{background:#15171c;color:#dcdfe6;font:14px/1.4 system-ui,sans-serif;margin:0}
 header{position:sticky;top:0;background:#1c1f27;padding:10px 18px;z-index:5;
        border-bottom:1px solid #333;display:flex;gap:18px;align-items:baseline}
 h1{font-size:16px;margin:0} #prog{color:#8fd18f}
 .box{display:flex;gap:14px;padding:14px 18px;border-bottom:1px solid #2a2d36}
 .left{flex:0 0 340px}
 .left img{max-width:330px;max-height:280px;border:1px solid #444;border-radius:4px}
 .meta{margin-top:6px;color:#9aa0ad;font-size:12.5px}
 .meta b{color:#dcdfe6;font-size:14px}
 .flag{color:#e8b04b}
 .strips{flex:1;min-width:0}
 .striplabel{color:#7f87a0;font-size:11px;text-transform:uppercase;
             letter-spacing:.08em;margin:2px 0 4px}
 .cards{display:flex;gap:10px;overflow-x:auto;padding-bottom:6px}
 .card{flex:0 0 150px;background:#1c1f27;border:2px solid #333;border-radius:6px;
       padding:6px;font-size:11.5px;color:#aab;position:relative}
 .card img{width:136px;height:136px;border-radius:3px;background:#fff}
 .card .sc{color:#8fd18f} .card .rot{color:#e8b04b} .card .reup{color:#d98fd9}
 .card .desc{height:3.6em;overflow:hidden;margin-top:3px}
 .card.picked{outline:2px solid #59c2ff;outline-offset:2px}
 .card.alt{outline:2px dashed #59c2ff66;outline-offset:2px}
 .pickbadge{position:absolute;top:10px;right:10px;background:#59c2ff;
   color:#081018;font-weight:700;font-size:10.5px;padding:1px 7px;
   border-radius:9px}
 .altbadge{position:absolute;top:10px;right:10px;background:#2a3f52;
   color:#9fd0f5;font-weight:700;font-size:10.5px;padding:1px 7px;
   border-radius:9px}
 .card.fits{border:2px solid transparent;
   background:linear-gradient(#1e2b22,#1e2b22) padding-box,
              linear-gradient(135deg,#3fd06a,#59c2ff) border-box;
   box-shadow:0 0 14px rgba(63,208,106,.35)}
 .fitbadge{position:absolute;top:10px;left:10px;background:#3fd06a;color:#0c1410;
   font-weight:700;font-size:10.5px;padding:1px 7px;border-radius:9px}
</style>
<header><h1 id="title"></h1><span id="prog"></span>
<span style="color:#667">inspection only &middot; sizes = extents along x y z
in cm (y = up) &middot; ↻90° about y = quarter-turn around the vertical axis
&middot; ⟳ re-upped = mis-authored mesh stood upright (thumb shows corrected
orientation) &middot; ×N = uniform rescale &middot; clip/txt = crop-vs-thumb /
crop-vs-description similarity &middot; glowing frame = fits INSIDE the box at
native size &middot; blue PICK = the automated C5 choice, #n = finalist rank
(top-N)</span>
</header><div id="rows"></div>
<script>
const AX = {x:0, y:1, z:2};
function fitsInside(c, boxM){
  // native size vs the (possibly tiled) sub-box, fit orientation applied
  const a = [...(c.perm||'xyz')].map(ch=>c.size_cm[AX[ch]]);
  const sub = boxM.map(v=>v*100);
  sub[c.axis] /= c.k;
  return a[0]<=sub[0] && a[1]<=sub[1] && a[2]<=sub[2];
}
async function main(){
  const DATA = await (await fetch('data')).json();
  document.getElementById('title').textContent = 'retrieval inspection — ' + DATA.scene;
  const rows = document.getElementById('rows');
  let nFit = 0;
  for (const b of DATA.boxes){
    const div = document.createElement('div'); div.className='box'; div.id=b.id;
    const [bx,by,bz] = b.size.map(v=>(v*100).toFixed(0));
    const dims = `x${bx} y${by} z${bz}`;
    const flag = b.match_tier===3 ? ' <span class="flag">UNMATCHED</span>'
               : b.match_tier==='agent' ? ' <span class="flag">agent-mapped</span>' : '';
    const pk = (DATA.picks||{})[b.id];
    const card = (c, badge)=>{
      const tile = c.k>1 ? ` ×${c.k}` : '';
      const [ax,ay,az] = c.size_cm;
      const perm = c.perm || 'xyz';
      const rot = perm==='xyz' ? '' :
        perm==='zyx' ? ' <span class="rot">↻90° about y</span>' :
        ` <span class="reup">⟳ re-upped: asset ${perm[1]} → up</span>`;
      const fits = fitsInside(c, b.size);
      const clip = c.clip!=null ? ` · clip ${c.clip.toFixed(3)}` : '';
      const ctxt = c.clip_txt!=null ? ` · txt ${c.clip_txt.toFixed(3)}` : '';
      const stem = perm==='xyz' ? c.uid : `${c.uid}_${perm}`;
      const picked = pk && pk.uid===c.uid;
      let altRank = null;
      if (pk && !picked && pk.alternates){
        const ai = pk.alternates.findIndex(a=>a.uid===c.uid);
        if (ai >= 0) altRank = ai + 2;
      }
      return `<div class="card${fits ? ' fits' : ''}${picked ? ' picked' : ''}${altRank ? ' alt' : ''}"
        title="fit score ${c.score.toFixed(3)} (lower = better)">
        ${fits ? '<span class="fitbadge">FITS</span>' : ''}
        ${picked ? '<span class="pickbadge">PICK</span>' : ''}
        ${altRank ? `<span class="altbadge">#${altRank}</span>` : ''}
        <img loading="lazy" src="thumb/${stem}">
        <div><span class="sc">${badge}</span> ${c.category}${tile}</div>
        <div>x${ax} y${ay} z${az} cm${rot} · ×${c.scale.toFixed(2)}${clip}${ctxt}</div>
        <div class="desc">${c.description}</div></div>`;
    };
    b.candidates.forEach(c=>{ if (fitsInside(c, b.size)) nFit++; });
    const dimCards = b.candidates.map((c,i)=>card(c, `fit #${i+1}`)).join('');
    const hasClip = b.candidates.some(c=>c.clip!=null);
    let strips = `<div class="striplabel">dimension fit</div>
                  <div class="cards">${dimCards}</div>`;
    if (hasClip){
      const byClip = b.candidates.slice()
        .sort((p,q)=>(q.clip??-9)-(p.clip??-9));
      strips += `<div class="striplabel">relevance (CLIP vs crop)</div>
        <div class="cards">${byClip.map((c,i)=>card(c, `rel #${i+1}`)).join('')}</div>`;
    }
    div.innerHTML = `<div class="left"><img src="crop/${b.id}" onerror="this.style.display='none'">
      <div class="meta"><b>${b.id} — ${b.label}</b>${flag}<br>
      box ${dims} cm · ${b.mount} · conf ${b.conf.toFixed(2)}<br>
      cats: ${b.categories.join(', ')||'—'}</div></div>
      <div class="strips">${strips}</div>`;
    rows.appendChild(div);
  }
  document.getElementById('prog').textContent =
    DATA.boxes.length + ' boxes · ' + nFit + ' in-bounds candidates';
}
main();
</script>"""


def serve(sc, port):
    pkg = paths.package_dir(sc)
    sl = json.loads((pkg / "shortlists2.json").read_text())
    cdir = pkg / "review_crops"

    class H(BaseHTTPRequestHandler):
        def _send(self, body, ctype="application/json"):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            p = self.path.split("?")[0]
            if p == "/":
                self._send(PAGE.encode(), "text/html; charset=utf-8")
            elif p == "/data":
                pf = pkg / "picks2.json"
                picks = json.loads(pf.read_text()) if pf.exists() else {}
                self._send(json.dumps({"scene": sc, "boxes": sl["boxes"],
                                       "picks": picks}).encode())
            elif p.startswith("/thumb/"):
                f = thumb_path(p.split("/")[-1])
                self._send(f.read_bytes(), "image/png") if f.exists() \
                    else self.send_error(404)
            elif p.startswith("/crop/"):
                f = cdir / f'{p.split("/")[-1]}.png'
                self._send(f.read_bytes(), "image/png") if f.exists() \
                    else self.send_error(404)
            else:
                self.send_error(404)

        def log_message(self, *a):
            pass

    print(f"[review] http://localhost:{port}  ({len(sl['boxes'])} boxes)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--port", type=int, default=8322)
    ap.add_argument("--recrop", action="store_true")
    args = ap.parse_args()
    sl = json.loads((paths.package_dir(args.scene) / "shortlists2.json").read_text())
    make_crops(args.scene, sl["boxes"], force=args.recrop)
    serve(args.scene, args.port)
