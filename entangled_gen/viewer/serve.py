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

# set in main(); class H reads these module globals at request time
args = None
CAPS = None


def placement_file(sc):
    return paths.live_placement(sc)


def box_sources(sc):
    """Method-organized box sets (2026-07-25 reorg): one entry per
    detection/lift METHOD, so competing methods are compared side by side.
    Registry order = HUD order. Only entries whose file exists are served."""
    sd = paths.scene_dir(sc)
    return [
        ("pano_track", "PANO TRACK (canonical · thr 0.2)",
         sd / "scene_manifest_pano2c_rc.json", "#ffd24d",
         "THE pano track (user-canonical 2026-07-26), 20%% floor "
         "everywhere (user: drop the 0.40 gate): self-rendered pano at "
         "(0,0)+1.6m -> 20-crop rig -> BATCHED-vocab detect thr 0.20 -> "
         "z-buffer lift -> robust merge q.05 -> RECENTER round as the "
         "real filter (20 refined, 15 marginal singletons refuted by "
         "close-up, 8 confirmed). 135 objects; floor-gap min +0.012"),
        ("pano_track_rcdelta", "pano track · Δ before recenter (thr 0.2)",
         sd / "scene_manifest_pano_rcdelta.json", "#ff5a5a",
         "the BEFORE-state of everything the recenter round changed: the "
         "refuted objects (since deleted, with close-up evidence) + the "
         "pre-refinement boxes of objects whose bounds moved. Canonical = "
         "the full scene after recenter; toggle both to see before vs "
         "after"),
        ("pano_track_gatekills", "pano track · Δ gate kills",
         sd / "scene_manifest_pano_gatekills.json", "#b06aff",
         "DELTA layer: only the 33 objects the confidence gate killed "
         "(best detection < 0.40) — the gate's audit trail; real objects "
         "found here are candidates for recenter-verification rescue"),
        # sweep-lane entries (G3/robust/gated/G4) RETIRED from the HUD
        # 2026-07-26 — superseded by the canonical pano track; manifests
        # stay on disk (scene_manifest_sweep*.json) for the record
        ("recenter_C1", "pano 1.0 · recenter C1 (superseded)",
         sd / "recenter_experiment" / "manifest_C1_raw.json", "#f0a028",
         "Marble-pano lane, superseded by the canonical PANO TRACK "
         "(carries the +6.5cm registration pedestal); kept for comparison"),
        ("analyzer_hybrid", "analyzer + OUR lift (hybrid)",
         sd / "scene_manifest_analyzer_hybrid.json", "#00c89a",
         "the 3h2 hybrid: analyzer's OWLv2 detections AND clustering kept "
         "1:1, geometry replaced by our SAM + z-buffer lift + robust "
         "per-axis fusion. Floor-ish gap median +0.53 -> +0.11, boxes "
         "touch the floor; volumes measured not fabricated (median 2.2x "
         "theirs)"),
        ("analyzer", "analyzer · OWLv2 vote (their lift)",
         sd / "analyzer" / "bridged_boxes.json", "#00ffff",
         "splat_analyzer bridged clusters: surface-biased centers, "
         "fabricated depth extent (w+h)/2 — toggle against the hybrid to "
         "see the lift swap alone"),
        ("fuse", "fuse · 3h2 pool",
         sd / "scene_manifest_fuse.json", "#33ee66",
         "unified lift pool + ported vote (SPEC_3H2_FUSE) — appears once built"),
        ("legacy_v1", "yaw4 mask-lift +amodal (old manifest)",
         paths.manifest(sc), "#8899aa",
         "the old default scene_manifest.json: 4 gpu_yaw renders -> "
         "GroundingDINO+SAM -> per-pixel z-buffer mask lift -> label+IoU "
         "merge (lift_views.py), then splat-amodal box extension "
         "(amodal_apply.py, 2026-07-15). 4-yaw observation retired 07-24 — "
         "kept for method comparison"),
    ]


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
            # (gpu_yaw photo-pose harvesting removed 2026-07-25 — yaw track
            # retired; startup pose is now derived from floor_y client-side)
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
        elif p == "/box_sources.json":
            # method-box registry: which competing box sets exist for sc
            out = [{"key": k, "label": lb, "color": c, "note": nt}
                   for k, lb, f, c, nt in box_sources(sc) if f.exists()]
            self._send(200, json.dumps({"sources": out}).encode(),
                       "application/json")
        elif p == "/boxes.json":
            # one method box set, by registry key (?src=<key>)
            src = (q.get("src") or [""])[0]
            f = next((f for k, _, f, _, _ in box_sources(sc) if k == src), None)
            if f is not None and f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"unknown or missing box source; see /box_sources.json")
        elif p == "/collisions.json":
            # collide.py --export output: mesh-overlap pairs + RENDER-frame
            # overlap boxes for the viewer's collision layer
            f = paths.package_dir(sc) / "collisions.json"
            if f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no collisions.json; run composition/"
                                b"collide.py --scene " + sc.encode()
                                + b" --export")
        elif p == "/analyzer_boxes.json":
            # bridge_boxes.py output (Step 6 -- format-bridge): splat_analyzer
            # clusters as manifest-style boxes, RAW frame (same as
            # scene_manifest.json). sc is sanitized by _scene() (alnum/_-),
            # so the path cannot traverse.
            f = paths.scene_dir(sc) / "analyzer" / "bridged_boxes.json"
            if f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no analyzer/bridged_boxes.json; run "
                                b"analyzer/bridge_boxes.py --scene "
                                + sc.encode())
        elif p == "/analyzer_cameras.json":
            # splat_analyzer job cameras (transforms.json verbatim): sampled
            # standpoints + per-frame OpenCV c2w poses, RAW frame (the tool
            # never transforms its input). ?job=<name> picks a job dir;
            # default = newest analyzer/job_*/ that has a transforms.json.
            # job is sanitized like sc, so the path cannot traverse.
            job = (q.get("job") or [""])[0]
            job = "".join(ch for ch in job if ch.isalnum() or ch in "_-")
            base = paths.scene_dir(sc) / "analyzer"
            if job:
                cands = [base / job / "transforms.json"]
            else:
                cands = sorted(base.glob("job_*/transforms.json"),
                               key=lambda f: f.stat().st_mtime, reverse=True)
            f = next((c for c in cands if c.exists()), None)
            if f is not None:
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no analyzer job transforms.json; drop a "
                                b"splat_analyzer job dir into analyzer/")
        elif p == "/scene_graph.json":
            # graph/build_graph.py + build_edges.py + describe_nodes.py output
            # (Steps 1-3 -- scene graph): nodes + typed edges + appearance,
            # RAW frame. Feeds the "graph nodes" layer. sc is sanitized by
            # _scene() (alnum/_-), so the path cannot traverse.
            f = paths.scene_dir(sc) / "scene_graph.json"
            if f.exists():
                self._send(200, f.read_bytes(), "application/json")
            else:
                self._send(404, b"no scene_graph.json; run "
                                b"graph/build_graph.py --scene " + sc.encode())
        elif p.startswith("/graph_crops/"):
            # per-node evidence crops (graph/describe_nodes.py output) for the
            # graph layer's click card. Filename sanitized to alnum/_-. and
            # resolve+parents-checked like /vendor/ -- blocks ../ traversal.
            base = (paths.scene_dir(sc) / "graph" / "crops").resolve()
            name = p[len("/graph_crops/"):].lstrip("/")
            name = "".join(ch for ch in name if ch.isalnum() or ch in "_-.")
            f = (base / name).resolve() if name else base
            if name and f.is_file() and base in f.parents:
                self._send(200, f.read_bytes(), "image/png", cache=True)
            else:
                self._send(404, b"no such graph crop")
        elif p == "/composed.glb":
            # composition C6 output (RENDER frame; browser flips via
            # frame.raw_to_render, self-inverse)
            f = paths.package_dir(sc) / "composed_scene2.glb"
            if f.exists():
                self._send(200, f.read_bytes(), "model/gltf-binary")
            else:
                self._send(404, b"no composed_scene2.glb; run composition/place2.py")
        elif p == "/collider.glb":
            # Marble bundle collider, ICP-registered into the RAW frame
            # (collider_register.py) — already raw, so NO browser-side flip.
            f = paths.scene_dir(sc) / "collider_registered.glb"
            if f.exists():
                self._send(200, f.read_bytes(), "model/gltf-binary")
            else:
                self._send(404, b"no collider_registered.glb; run "
                                b"collider_register.py --scene " + sc.encode())
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
        elif p.startswith("/vendor/"):
            # locally-vendored JS modules (three, OrbitControls, GLTFLoader,
            # gaussian-splats-3d) so the viewer works with NO internet. Served
            # with a JS mime type — ES-module <script type=module> imports are
            # rejected by the browser unless the response is a JS content-type.
            base = (HERE / "vendor").resolve()
            f = (base / p[len("/vendor/"):].lstrip("/")).resolve()
            if f.is_file() and base in f.parents:      # blocks ../ traversal
                ctype = "text/javascript" if f.suffix == ".js" else "application/octet-stream"
                self._send(200, f.read_bytes(), ctype, cache=True)
            else:
                self._send(404, b"no such vendor file")
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


def main():
    global args, CAPS
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom", help="default scene for /")
    ap.add_argument("--port", type=int, default=8321)
    args = ap.parse_args()

    CAPS = paths.OUT / "viewer_caps"   # shared data root (local_paths.json), not the repo tree
    CAPS.mkdir(parents=True, exist_ok=True)

    print(f"[viewer] default scene={args.scene} http://localhost:{args.port} "
          f"(?scene=<name> to switch; live files: out/<scene>/live_placement.json)",
          flush=True)
    ThreadingHTTPServer(("127.0.0.1", args.port), H).serve_forever()


if __name__ == "__main__":
    main()
