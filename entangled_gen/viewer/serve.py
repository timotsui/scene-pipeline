"""
Live placement viewer server (multi-scene).

Any scene with viewer/data/<scene>.bin is servable; the browser picks via
?scene=X (dropdown in the HUD). Per-scene live placement files:
out/<scene>/live_placement.json — edit one and the browser updates in 0.5 s.
POST /capture saves canvas views to out/viewer_caps/ for LLM feedback.

Run:  python viewer/serve.py --scene bedroom --port 8321   (--scene = default only)
"""
import argparse, base64, json, sys, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

HERE = Path(__file__).parent
ROOT = HERE.parent
sys.path.insert(0, str(ROOT))
import paths  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--scene", default="bedroom", help="default scene for /")
ap.add_argument("--port", type=int, default=8321)
args = ap.parse_args()

CAPS = paths.OUT / "viewer_caps"   # shared data root (local_paths.json), not the repo tree
CAPS.mkdir(parents=True, exist_ok=True)


def placement_file(sc):
    return paths.live_placement(sc)


class H(BaseHTTPRequestHandler):
    def _send(self, code, body, ctype="text/plain", cache=False):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        if not cache:
            self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _scene(self, q):
        sc = (q.get("scene") or [args.scene])[0]
        return "".join(ch for ch in sc if ch.isalnum() or ch in "_-") or args.scene

    def do_GET(self):
        u = urlparse(self.path)
        p, q = u.path, parse_qs(u.query)
        sc = self._scene(q)
        if p == "/":
            self._send(200, (HERE / "index.html").read_bytes(), "text/html")
        elif p == "/scenes.json":
            scenes = sorted(f.stem for f in (HERE / "data").glob("*.bin"))
            actf = HERE / "data" / "_active.json"
            try:
                active = json.loads(actf.read_text()).get("active", [])
            except Exception:
                active = []
            active = [s for s in active if s in scenes] or [args.scene]
            self._send(200, json.dumps({"scenes": scenes, "active": active,
                                        "default": args.scene}).encode(),
                       "application/json")
        elif p == "/scene.bin":
            f = HERE / "data" / f"{sc}.bin"
            if f.exists():
                self._send(200, f.read_bytes(), "application/octet-stream", cache=True)
            else:
                self._send(404, b"no point payload; run viewer/prep_scene.py")
        elif p == "/meta.json":
            f = HERE / "data" / f"{sc}.json"
            if not f.exists():
                return self._send(404, b"no meta")
            meta = json.loads(f.read_text())
            meta["scene"] = sc
            manf = paths.manifest(sc)
            if manf.exists():
                man = json.loads(manf.read_text())
                meta["floor_y"] = man["frame"]["floor_y"]
                meta["ceiling_y"] = man["frame"]["ceiling_y"]
            # exact rig cameras from the shot.py sidecars, so the viewer's
            # photo-pose buttons match the webps even when the rig is not at
            # the origin (e.g. marble scenes: floor-origin, eye at +1.6)
            poses = {}
            for vj in sorted((paths.OUT / sc / "views").glob("gpu_yaw*.json")):
                try:
                    d = json.loads(vj.read_text())
                    poses[vj.stem] = {"cam": d["cam"], "look": d["look"],
                                      "fov": d.get("fov", 75)}
                except Exception:
                    pass
            meta["poses"] = poses
            self._send(200, json.dumps(meta).encode(), "application/json")
        elif p == "/manifest.json":
            # ?man=<variant> serves scene_manifest_<variant>.json (e.g. the
            # week8 pano-lift manifests) without touching the default one
            man = (q.get("man") or [""])[0]
            if man and man.replace("_", "").isalnum():
                f = paths.scene_dir(sc) / f"scene_manifest_{man}.json"
            else:
                f = paths.manifest(sc)
            if f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no manifest")
        elif p == "/clearance.json":
            f = HERE / "data" / f"{sc}_clearance.json"
            if f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no envelope computed for this scene")
        elif p == "/placement.json":
            f = placement_file(sc)
            body = f.read_bytes() if f.exists() else b'{"placements":[]}'
            self._send(200, body, "application/json")
        elif p == "/amodal.json":
            # amodal_boxes.py comparison output (extraction experiment)
            f = paths.scene_dir(sc) / "amodal_boxes.json"
            if f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no amodal_boxes.json; run amodal_boxes.py")
        elif p == "/glts.glb":
            # GLTS baseline scene (newest glts_comparison* package in OUT)
            cands = sorted(paths.OUT.glob("glts_comparison*/glts_scene.glb"))
            if cands:
                self._send(200, cands[-1].read_bytes(), "model/gltf-binary")
            else:
                self._send(404, b"no glts_comparison*/glts_scene.glb in OUT")
        elif p == "/composed.glb":
            # composition C6 output (RENDER frame; browser flips via
            # frame.raw_to_render, self-inverse)
            f = paths.package_dir(sc) / "composed_scene2.glb"
            if f.exists():
                self._send(200, f.read_bytes(), "model/gltf-binary")
            else:
                self._send(404, b"no composed_scene2.glb; run composition/place2.py")
        elif p == "/splat.ply":
            # full-quality splat for the hi-fi renderer (GaussianSplats3D).
            # Streamed in chunks: gen_raw.ply can be 100-800 MB.
            f = paths.OUT / sc / "gen_raw.ply"
            if not f.exists():
                return self._send(404, b"no gen_raw.ply for this scene")
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(f.stat().st_size))
            self.send_header("Cache-Control", "max-age=300")
            self.end_headers()
            with f.open("rb") as fh:
                while True:
                    chunk = fh.read(1 << 20)
                    if not chunk:
                        break
                    self.wfile.write(chunk)
        else:
            self._send(404, b"not found")

    def do_POST(self):
        u = urlparse(self.path)
        q = parse_qs(u.query)
        sc = self._scene(q)
        n = int(self.headers["Content-Length"])
        req = json.loads(self.rfile.read(n))
        if u.path == "/capture":
            png = base64.b64decode(req["image"].split(",", 1)[1])
            ts = time.strftime("%H%M%S")
            f = CAPS / f"cap_{sc}_{ts}.png"
            f.write_bytes(png)
            (CAPS / "latest.png").write_bytes(png)
            meta = {"scene": sc, **req.get("camera", {})}
            (CAPS / f"cap_{sc}_{ts}.json").write_text(json.dumps(meta))
            (CAPS / "latest.json").write_text(json.dumps(meta))
            self._send(200, f"saved {f.name}".encode())
        elif u.path == "/placement":
            req["scene"] = sc
            req.setdefault("note", "edited via live viewer")
            f = placement_file(sc)
            tmp = f.with_suffix(".tmp")
            tmp.write_text(json.dumps(req, indent=2))
            tmp.replace(f)
            self._send(200, b"placement saved")
        elif u.path == "/bookmark":
            cam = req.get("camera", {})
            pos = cam.get("pos", [0, 0, 0]); tgt = cam.get("target", [0, 0, 0])
            shot = (f"python rendertools/shot.py {pos[0]:.2f},{pos[1]:.2f},{pos[2]:.2f} "
                    f"{tgt[0]:.2f},{tgt[1]:.2f},{tgt[2]:.2f} --fov {cam.get('fov', 65):.0f} "
                    f"--up 0,1,0 --ply out/{sc}/gen_raw.ply --out <out.webp> --no-open")
            bmf = CAPS / "bookmarks.json"
            bms = json.loads(bmf.read_text()) if bmf.exists() else []
            bms.append({"time": time.strftime("%H:%M:%S"), "scene": sc,
                        "camera": cam, "shot_cmd": shot})
            bmf.write_text(json.dumps(bms, indent=2))
            self._send(200, f"bookmark #{len(bms)} saved".encode())
        else:
            self._send(404, b"not found")

    def log_message(self, *a):
        pass


print(f"[viewer] default scene={args.scene} http://localhost:{args.port} "
      f"(?scene=<name> to switch; live files: out/<scene>/live_placement.json)",
      flush=True)
ThreadingHTTPServer(("127.0.0.1", args.port), H).serve_forever()
