"""Asset inspection viewer — orbit any objathor asset referenced by a scene's
shortlists2.json to check its canonical frame (is the mesh axis-aligned inside
its own bounding box, or authored at an oblique angle?).

Sidebar lists every box's candidates (PICK highlighted); clicking one loads
the mesh with world axes (x red, y green, z blue), its axis-aligned bounding
box, and toggles for the fit's perm rotation (thumbs.perm_rotation semantics,
parity sign included) and the measure.py canonical-yaw fix (off = the mesh
exactly as authored). If a robust-extents census entry exists (measure.py
--census), the 99.5%-of-surface-area box is drawn in orange next to the full
AABB in green — daylight between them = outlier geometry inflating the box
(red flag badge when any axis ratio < 0.9). A free uid field loads any
catalog asset. GLBs are converted on demand and cached dataset-level in
<OBJATHOR>/_glb/.

Run:  python asset_viewer.py --scene bedroom_marble --port 8323
"""
import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import trimesh

from assets_thor import load_asset
from comp_paths import MESH_YAW, OBJATHOR, paths
from thumbs import thumb_path

GLB = OBJATHOR / "_glb"


def glb_path(uid, raw=False):
    """Convert uid to GLB once; cached next to the thumbs cache."""
    GLB.mkdir(exist_ok=True)
    f = GLB / (f"{uid}_raw.glb" if raw else f"{uid}.glb")
    if not f.exists():
        trimesh.Scene(load_asset(uid, raw=raw)).export(f)
    return f


PAGE = """<!doctype html><meta charset="utf-8"><title>asset inspection</title>
<style>
 body{background:#15171c;color:#dcdfe6;font:14px/1.4 system-ui,sans-serif;
      margin:0;display:flex;height:100vh;overflow:hidden}
 #side{flex:0 0 300px;overflow-y:auto;background:#1c1f27;
       border-right:1px solid #333;padding:10px}
 #side h1{font-size:15px;margin:2px 0 8px}
 #uidform{display:flex;gap:6px;margin-bottom:10px}
 #uidform input{flex:1;background:#10131a;color:#dcdfe6;border:1px solid #444;
       border-radius:4px;padding:4px 6px;font-size:12px}
 .boxhdr{color:#9aa0ad;font-size:12px;margin:10px 0 4px;position:sticky;
       top:0;background:#1c1f27;padding:2px 0}
 .boxhdr b{color:#dcdfe6}
 .cards{display:flex;flex-wrap:wrap;gap:6px}
 .card{width:64px;cursor:pointer;border:2px solid #333;border-radius:5px;
       background:#fff;position:relative}
 .card img{width:60px;height:60px;display:block;border-radius:3px}
 .card.picked{border-color:#59c2ff}
 .card.sel{outline:2px solid #e8b04b;outline-offset:1px}
 .pickbadge{position:absolute;top:1px;right:1px;background:#59c2ff;
   color:#081018;font-weight:700;font-size:9px;padding:0 4px;border-radius:7px}
 .yawbadge{position:absolute;bottom:1px;left:1px;background:#e8b04b;
   color:#1c1207;font-weight:700;font-size:9px;padding:0 3px;border-radius:7px}
 .robbadge{position:absolute;bottom:1px;right:1px;background:#e05555;
   color:#fff;font-weight:700;font-size:9px;padding:0 3px;border-radius:7px}
 #main{flex:1;display:flex;flex-direction:column;min-width:0}
 #bar{background:#1c1f27;border-bottom:1px solid #333;padding:8px 14px;
      display:flex;gap:16px;align-items:center;flex-wrap:wrap;font-size:12.5px}
 #bar b{color:#e8b04b}
 #bar label{color:#9aa0ad;cursor:pointer;user-select:none}
 #canvaswrap{flex:1;position:relative;min-height:0}
 canvas{display:block}
 #hint{position:absolute;bottom:8px;left:12px;color:#667;font-size:11.5px}
</style>
<div id="side">
 <h1>asset inspection</h1>
 <form id="uidform"><input id="uidin" placeholder="any uid, Enter to load">
 </form>
 <div id="list"></div>
</div>
<div id="main">
 <div id="bar">
  <span id="info">click a candidate</span>
  <label><input type="checkbox" id="yawchk" checked> yaw fix
    (<span id="yawlab">—</span>)</label>
  <label><input type="checkbox" id="permchk"> apply fit perm
    (<span id="permlab">xyz</span>)</label>
  <label><input type="checkbox" id="boxchk" checked> bounding box</label>
  <label><input type="checkbox" id="gridchk" checked> grid</label>
 </div>
 <div id="canvaswrap"><div id="hint">drag orbit &middot; wheel zoom &middot;
  axes: x red, y green (up), z blue &middot; bbox recomputed after perm</div>
 </div>
</div>
<script type="importmap">
{ "imports": {
    "three": "https://unpkg.com/three@0.160.0/build/three.module.js",
    "three/addons/": "https://unpkg.com/three@0.160.0/examples/jsm/"
} }
</script>
<script type="module">
import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { GLTFLoader } from 'three/addons/loaders/GLTFLoader.js';

const wrap = document.getElementById('canvaswrap');
const renderer = new THREE.WebGLRenderer({antialias:true});
renderer.setPixelRatio(devicePixelRatio);
wrap.appendChild(renderer.domElement);
const scene = new THREE.Scene();
scene.background = new THREE.Color(0x15171c);
const camera = new THREE.PerspectiveCamera(45, 1, 0.001, 100);
const controls = new OrbitControls(camera, renderer.domElement);
scene.add(new THREE.AmbientLight(0xffffff, 1.1));
const dir = new THREE.DirectionalLight(0xffffff, 2.2);
scene.add(dir);
const grid = new THREE.GridHelper(4, 40, 0x3a4050, 0x262b36);
scene.add(grid);

function resize(){
  const w = wrap.clientWidth, h = wrap.clientHeight;
  renderer.setSize(w, h);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe(wrap);

const AX = {x:0, y:1, z:2};
function permMatrix(perm){
  // mirror of thumbs.perm_rotation: signed permutation, row-0 flip on odd
  // parity so it is a PROPER rotation, never a mirror
  const R = [[0,0,0],[0,0,0],[0,0,0]];
  [...perm].forEach((c,i)=>{ R[i][AX[c]] = 1; });
  const det = R[0][0]*(R[1][1]*R[2][2]-R[1][2]*R[2][1])
            - R[0][1]*(R[1][0]*R[2][2]-R[1][2]*R[2][0])
            + R[0][2]*(R[1][0]*R[2][1]-R[1][1]*R[2][0]);
  if (det < 0) R[0] = R[0].map(v=>-v);
  return new THREE.Matrix4().set(
    R[0][0],R[0][1],R[0][2],0, R[1][0],R[1][1],R[1][2],0,
    R[2][0],R[2][1],R[2][2],0, 0,0,0,1);
}

let group = null, boxHelper = null, robHelper = null, axes = null;
let cur = {uid:null, perm:'xyz', label:'', category:''};
let YAWS = {}, ROBUST = {};

function refit(){
  if (!group) return;
  group.matrix.identity();
  group.matrixAutoUpdate = false;
  if (document.getElementById('permchk').checked)
    group.matrix.copy(permMatrix(cur.perm));
  group.updateMatrixWorld(true);
  const bb = new THREE.Box3().setFromObject(group);
  if (boxHelper) scene.remove(boxHelper);
  boxHelper = new THREE.Box3Helper(bb, 0x3fd06a);
  boxHelper.visible = document.getElementById('boxchk').checked;
  scene.add(boxHelper);
  if (robHelper){ scene.remove(robHelper); robHelper = null; }
  const rob = ROBUST[cur.uid];
  // robust box is measured in the yaw-fixed frame — only valid with fix on
  if (rob && document.getElementById('yawchk').checked){
    const rb = new THREE.Box3();
    for (const x of [rob.lo[0], rob.hi[0]])
      for (const y of [rob.lo[1], rob.hi[1]])
        for (const z of [rob.lo[2], rob.hi[2]])
          rb.expandByPoint(new THREE.Vector3(x, y, z)
            .applyMatrix4(group.matrix));
    robHelper = new THREE.Box3Helper(rb, 0xe8963c);
    robHelper.visible = document.getElementById('boxchk').checked;
    scene.add(robHelper);
  }
  const size = bb.getSize(new THREE.Vector3());
  const c = bb.getCenter(new THREE.Vector3());
  const r = size.length() / 2;
  if (axes) scene.remove(axes);
  axes = new THREE.AxesHelper(r * 1.4);
  axes.position.copy(c);
  scene.add(axes);
  const cm = v => (v*100).toFixed(1);
  const rr = rob ? ` &middot; robust ratio x${rob.ratio[0].toFixed(2)}` +
    ` y${rob.ratio[1].toFixed(2)} z${rob.ratio[2].toFixed(2)}` +
    (Math.min(...rob.ratio) < 0.9 ? ' <b style="color:#e05555">FLAG</b>' : '')
    : '';
  document.getElementById('info').innerHTML =
    `<b>${cur.label||cur.uid}</b> ${cur.category||''} &middot; ` +
    `aabb x${cm(size.x)} y${cm(size.y)} z${cm(size.z)} cm${rr}`;
  return {c, r};
}

async function load(uid, perm, label, category){
  cur = {uid, perm: perm||'xyz', label, category};
  document.getElementById('permlab').textContent = cur.perm;
  const yaw = YAWS[uid] || 0;
  document.getElementById('yawlab').textContent =
    yaw ? yaw.toFixed(1) + '\\u00b0' : 'none';
  document.querySelectorAll('.card').forEach(el=>
    el.classList.toggle('sel', el.dataset.uid===uid));
  if (group) scene.remove(group);
  const raw = !document.getElementById('yawchk').checked;
  const gltf = await new GLTFLoader().loadAsync(   // t= busts browser cache
    'glb/' + uid + '?' + (raw ? 'raw=1&' : '') + 't=' + Date.now());
  group = gltf.scene;
  scene.add(group);
  const fit = refit();
  const eye = fit.c.clone().add(
    new THREE.Vector3(0.72, 0.45, 0.72).multiplyScalar(fit.r * 2.6));
  camera.position.copy(eye);
  camera.near = fit.r / 100; camera.far = fit.r * 100;
  camera.updateProjectionMatrix();
  controls.target.copy(fit.c);
  controls.update();
}

for (const id of ['permchk','boxchk','gridchk'])
  document.getElementById(id).addEventListener('change', ()=>{
    grid.visible = document.getElementById('gridchk').checked;
    refit();
  });
document.getElementById('yawchk').addEventListener('change', ()=>{
  if (cur.uid) load(cur.uid, cur.perm, cur.label, cur.category);
});

document.getElementById('uidform').addEventListener('submit', e=>{
  e.preventDefault();
  const uid = document.getElementById('uidin').value.trim();
  if (uid) load(uid, 'xyz', uid, '');
});

async function main(){
  const DATA = await (await fetch('data')).json();
  YAWS = DATA.yaws || {};
  ROBUST = DATA.robust || {};
  document.title = 'asset inspection — ' + DATA.scene;
  const list = document.getElementById('list');
  for (const b of DATA.boxes){
    const hdr = document.createElement('div');
    hdr.className = 'boxhdr';
    hdr.innerHTML = `<b>${b.id}</b> ${b.label} · ${b.mount}`;
    list.appendChild(hdr);
    const cards = document.createElement('div');
    cards.className = 'cards';
    const pk = (DATA.picks||{})[b.id] || {};
    for (const c of b.candidates){
      const el = document.createElement('div');
      const perm = c.perm || 'xyz';
      const stem = perm === 'xyz' ? c.uid : `${c.uid}_${perm}`;
      const yaw = YAWS[c.uid] || 0;
      const rob = ROBUST[c.uid];
      const flagged = rob && Math.min(...rob.ratio) < 0.9;
      el.className = 'card' + (pk.uid===c.uid ? ' picked' : '');
      el.dataset.uid = c.uid;
      el.title = `${c.category} · perm ${perm}` +
        (yaw ? ` · yaw fix ${yaw.toFixed(1)}\\u00b0` : '') +
        (flagged ? ` · outlier geometry (ratio ${rob.ratio.join('/')})` : '');
      el.innerHTML = (pk.uid===c.uid ? '<span class="pickbadge">P</span>' : '')
        + (yaw ? '<span class="yawbadge">\\u2220</span>' : '')
        + (flagged ? '<span class="robbadge">\\u2691</span>' : '')
        + `<img loading="lazy" src="thumb/${stem}"
             onerror="this.onerror=null;this.src='thumb/${c.uid}'">`;
      el.onclick = ()=>load(c.uid, perm, b.id+' '+b.label, c.category);
      cards.appendChild(el);
    }
    list.appendChild(cards);
  }
}
main();

(function anim(){
  requestAnimationFrame(anim);
  dir.position.copy(camera.position);
  renderer.render(scene, camera);
})();
</script>"""


def serve(sc, port):
    pkg = paths.package_dir(sc)
    sl = json.loads((pkg / "shortlists2.json").read_text())

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
                yaws = (json.loads(MESH_YAW.read_text())
                        if MESH_YAW.exists() else {})
                from measure import load_robust
                self._send(json.dumps({"scene": sc, "boxes": sl["boxes"],
                                       "picks": picks, "yaws": yaws,
                                       "robust": load_robust()}).encode())
            elif p.startswith("/glb/"):
                try:
                    raw = "raw=1" in (self.path.split("?") + [""])[1]
                    self._send(glb_path(p.split("/")[-1], raw).read_bytes(),
                               "model/gltf-binary")
                except Exception as e:
                    print(f"[assets] glb FAIL {p}: {e}", flush=True)
                    self.send_error(500)
            elif p.startswith("/thumb/"):
                f = thumb_path(p.split("/")[-1])
                self._send(f.read_bytes(), "image/png") if f.exists() \
                    else self.send_error(404)
            else:
                self.send_error(404)

        def log_message(self, *a):
            pass

    n = sum(len(b["candidates"]) for b in sl["boxes"])
    print(f"[assets] http://localhost:{port}  ({len(sl['boxes'])} boxes, "
          f"{n} candidates)", flush=True)
    ThreadingHTTPServer(("127.0.0.1", port), H).serve_forever()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--port", type=int, default=8323)
    args = ap.parse_args()
    serve(args.scene, args.port)
