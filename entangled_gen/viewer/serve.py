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
    """Method-organized box sets (2026-07-25 reorg; 2026-07-26 grouped):
    one entry per detection/lift METHOD. group='current' = the canonical
    lane; group='archive' = superseded/reference methods, rendered in the
    HUD's collapsed archive section (files stay on disk — nothing deleted).
    Registry order = HUD order. Only entries whose file exists are served.

    2026-08-01 (user: latest-and-greatest only): registry EMPTIED — the
    resolved scene model is the one current view; every box-source layer
    below is superseded audit. Entries kept commented for one-line
    re-enable; all files remain on disk."""
    sd = paths.scene_dir(sc)
    # (2026-08-06: the temporary directional-prior A/B pair lived here for
    # the user eyeball — RULED same day, prior promoted, entries removed.)
    # 2026-08-06 TEMPORARY streak-surgery previews (R-S2-22 gate): remove
    # both when ruled.
    return [
        ("parallax_carved", "parallax retake · carved (preview)", "current",
         sd / "scene_manifest_parallax_preview.json", "#65ff8f",
         "PREVIEW — experiments/parallax_retake.py: per-node side view "
         "from a second standpoint; original ray axis carved, then the "
         "original masks' points refiltered through the established depth "
         "slab (all axes re-derived). Uncarved nodes keep the record box "
         "(flagged) and are absent from this layer"),
        ("set_a", "set A · standpoint center", "current",
         sd / "scene_manifest_pano2c.json", "#ffd24d",
         "TWO-STANDPOINT EXPERIMENT — set A: the canonical rig at the "
         "center eye (rig_sp0), lift stage, ungated merge"),
        ("set_b", "set B · standpoint +1.1x", "current",
         sd / "scene_manifest_pano2_sp1.json", "#7fd4ff",
         "TWO-STANDPOINT EXPERIMENT — set B: the SAME chain re-run from "
         "a standpoint 1.1 m along +x (rig_sp1; bubble verified empty). "
         "Each set streaks along its own rays; matched-pair intersection "
         "= the carve; in-one-set-only = phantom-or-occlusion signal"),
        # ("support_clipped", ...) removed from HUD — wiring premature
        # until support judgment runs on carved geometry (R-S2-22 note)
    ]
    #     # ---- current: the pano-track funnel, upstream -> downstream ----
    #     # stage 1 (recentered full set) -> stage 2 (f30 score filter) ->
    #     # stage 3 = geometry dedup + GRAPH RECORD (the "graph record"
    #     # toggle in the main checkbox row — richer view than a box layer)
    #     ("pano_track", "pano · stage 1 · recentered full set", "current",
    #      sd / "scene_manifest_pano2c_rc.json", "#ffd24d",
    #      "STAGE 1 — the most UPSTREAM full manifest (input to stage 2): "
    #      "detection chain output after the recenter round. Self-rendered "
    #      "pano at (0,0)+1.6m -> 20-crop rig -> batched-vocab detect thr "
    #      "0.20 -> z-buffer lift -> robust merge q.05 -> RECENTER as the "
    #      "real filter (42 phantoms refuted by aimed close-ups, no "
    #      "arithmetic gate). 108 objects; floor-gap min +0.012"),
    #     ("pano_track_f30", "pano · stage 2 · f30 score filter", "current",
    #      sd / "scene_manifest_pano2c_rc_f30.json", "#7fd4ff",
    #      "STAGE 2 — stage 1 after the hard 0.30 score filter "
    #      "(manifest_filter.py; no reruns, pure post-processing): 102 "
    #      "objects, 6 dropped (3 toy, 2 book, 1 conditioner; 3 of the 6 "
    #      "were retake-confirmed — the filter overrules the verifier "
    #      "there; drops preserved in filtered_out). INPUT to stage 3 = the "
    #      "scene-graph RECORD (same 102 objects as nodes, duplicate pairs "
    #      "as SAME_CANDIDATE edges — no dedup stage, merging is a judge "
    #      "verdict; toggle 'graph record' above)"),
    #     # Δ pre-recenter audit layer REMOVED from the HUD (user, 07-26
    #     # late, "for simplicity"); the file stays on disk
    #     # (scene_manifest_pano_rcdelta.json — 42 refuted + 26 pre-
    #     # refinement boxes) and pano_track_diffs.py can regenerate it.
    #     # ---- archive / reference: superseded by decisions on record ----
    #     # REMOVED from the HUD entirely (user, 07-26 late): f30+dedup
    #     # geometry-only (redundant view — the 'graph record' layer draws
    #     # the same 93 boxes with the full card; the FILE stays the record
    #     # builder's input), f30+dedup LLM version (retired method), and
    #     # Δ gate kills (audit of the dropped 0.40 gate). Files untouched
    #     # on disk: scene_manifest_pano2c_rc_f30_dd.json / _dd_llm.json /
    #     # scene_manifest_pano_gatekills.json.
    #     # sweep-lane entries (G3/robust/gated/G4) RETIRED from the HUD
    #     # 2026-07-26 — superseded by the canonical pano track; manifests
    #     # stay on disk (scene_manifest_sweep*.json) for the record.
    #     # fuse · 3h2 pool entry REMOVED 2026-07-26 — never built; the
    #     # multiview-vote idea lives on the map's parked-ideas card.
    #     ("recenter_C1", "pano 1.0 · recenter C1 (superseded)",
    #      "archive", sd / "recenter_experiment" / "manifest_C1_raw.json",
    #      "#f0a028",
    #      "Marble-pano lane, superseded by the canonical PANO TRACK "
    #      "(carries the +6.5cm registration pedestal); kept for comparison"),
    #     ("analyzer_hybrid", "analyzer + OUR lift (hybrid · closed)",
    #      "archive", sd / "scene_manifest_analyzer_hybrid.json", "#00c89a",
    #      "REFERENCE (experiment closed 07-26): analyzer's OWLv2 detections "
    #      "AND clustering kept 1:1, geometry replaced by our SAM + z-buffer "
    #      "lift + robust per-axis fusion. Verdict: their clustering shreds "
    #      "(8x bed); the pano track won the FIND comparison"),
    #     ("analyzer", "analyzer · OWLv2 vote (reference)",
    #      "archive", sd / "analyzer" / "bridged_boxes.json", "#00ffff",
    #      "REFERENCE (analyzer demoted to side tool 07-26): bridged "
    #      "clusters — surface-biased centers, fabricated depth extent "
    #      "(w+h)/2; kept runnable as an independent second opinion"),
    #     ("legacy_v1", "yaw4 mask-lift +amodal (retired)",
    #      "archive", paths.manifest(sc), "#8899aa",
    #      "ARCHIVED: the old default scene_manifest.json: 4 gpu_yaw renders "
    #      "-> GroundingDINO+SAM -> per-pixel z-buffer mask lift -> "
    #      "label+IoU merge (lift_views.py), then splat-amodal box extension "
    #      "(amodal_apply.py, 2026-07-15). 4-yaw observation retired 07-24"),


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

    # which graph SLICES each layer actually consumes -- a layer is
    # stale only when a slice it depends on changed (08-02C redesign:
    # the old whole-graph mtime gate staled EVERYTHING on any graph
    # write, e.g. the additive facing field)
    FP_NEED = {"supported_by.json": ("geometry", "testimony"),
               "consistency.json": ("geometry", "testimony"),
               "snap.json": ("geometry",),
               "edit_proposals.json": ("geometry",),
               "shopping.json": ("geometry",),
               "fitted_preview.json": ("geometry",),
               "fit_check.json": ("geometry",)}
    _fp_cache = {}   # scene -> (graph mtime, fingerprint)

    def _graph_fp(self, sc):
        p = paths.scene_dir(sc) / "scene_graph.json"
        if not p.exists():
            return None
        mt = p.stat().st_mtime
        ent = self._fp_cache.get(sc)
        if ent and ent[0] == mt:
            return ent[1]
        fp = paths.graph_fingerprint(sc)
        self._fp_cache[sc] = (mt, fp)
        return fp

    def _compose_json(self, sc, name, run_hint):
        """Serve a compose/ layer with a CONTENT-FINGERPRINT freshness
        check: the layer's stamped graph_fingerprint is compared against
        the current graph's, per the slices this layer consumes
        (FP_NEED). Stale layers are served IN FULL with stale:true +
        stale_hint added -- the viewer badges them instead of hiding
        them (debugging must still see the data). Unstamped legacy
        files fall back to the old mtime comparison."""
        f = paths.compose_dir(sc) / name
        if not f.exists():
            return self._send(404, b"no compose/" + name.encode() + b"; run "
                              + run_hint.encode() + b" --scene " + sc.encode())
        raw = f.read_bytes()
        cur = self._graph_fp(sc)
        why = None
        try:
            layer = json.loads(raw)
        except ValueError:
            layer = None
        if layer is not None and cur:
            need = self.FP_NEED.get(name, ("geometry",))
            stamped = layer.get("graph_fingerprint")
            if stamped:
                changed = [k for k in need
                           if stamped.get(k) != cur.get(k)]
                if changed:
                    why = "graph " + "+".join(changed) + " changed"
            else:
                graph = paths.scene_dir(sc) / "scene_graph.json"
                if graph.exists() \
                        and f.stat().st_mtime < graph.stat().st_mtime:
                    why = "unstamped layer older than the graph"
            if why:
                layer["stale"] = True
                layer["stale_hint"] = (f"{why}; re-run {run_hint} "
                                       f"--scene {sc}")
                return self._send(200, json.dumps(layer).encode(),
                                  "application/json")
        self._send(200, raw, "application/json")

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
            boot = paths.scene_dir(sc) / "frame_bootstrap.json"
            if manf.exists():
                man = json.loads(manf.read_text())
                meta["floor_y"] = man["frame"]["floor_y"]
                meta["ceiling_y"] = man["frame"]["ceiling_y"]
            elif boot.exists():
                # pre-lift scenes: the intake module's frame record (same
                # convention — bundle frame, y-down — since 2026-08-06)
                fb = json.loads(boot.read_text())
                meta["floor_y"] = fb["floor_y"]
                meta["ceiling_y"] = fb["ceiling_y"]
            # (gpu_yaw photo-pose harvesting removed 2026-07-25 — yaw track
            # retired; startup pose is now derived from floor_y client-side)
            self._send(200, json.dumps(meta).encode(), "application/json")
        elif p == "/raw":
            # ground-truth page: the Marble bundle exactly as shipped
            self._send(200, (HERE / "raw.html").read_bytes(), "text/html")
        elif p in ("/bundle_splats.spz", "/bundle_collider.glb"):
            # stream RAW BUNDLE FILES (no conversion, no copy) for raw.html
            bp = paths.scene_dir(sc) / "bundle_path.txt"
            if not bp.exists():
                return self._send(404, b"no bundle_path.txt for this scene")
            bundle = Path(bp.read_text().strip())
            pat = "*.spz" if p.endswith(".spz") else "*collider*.glb"
            hits = sorted(bundle.glob(pat))
            if not hits:
                return self._send(404, f"no {pat} in bundle".encode())
            ctype = ("application/octet-stream" if p.endswith(".spz")
                     else "model/gltf-binary")
            self._send(200, hits[0].read_bytes(), ctype)
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
            out = [{"key": k, "label": lb, "group": gp, "color": c, "note": nt}
                   for k, lb, gp, f, c, nt in box_sources(sc) if f.exists()]
            self._send(200, json.dumps({"sources": out}).encode(),
                       "application/json")
        elif p == "/boxes.json":
            # one method box set, by registry key (?src=<key>)
            src = (q.get("src") or [""])[0]
            f = next((f for k, _, _, f, _, _ in box_sources(sc) if k == src), None)
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
        elif p == "/supported_by.json":
            # compose/supported_by.py output (STEP 3 module 1): per object
            # the superseding supported_by options; RAW frame ids only (no
            # geometry of its own). Feeds the scene-graph row's support
            # arrows + semantic anchor tint. sc sanitized by _scene().
            # Freshness-gated vs scene_graph.json (see _compose_json).
            self._compose_json(sc, "supported_by.json",
                               "compose/supported_by.py")
        elif p == "/consistency.json":
            # compose/consistency.py output (STEP 3 module 2): per-edge
            # KEEP/DROP verdicts vs the supported_by layer (R2 gate).
            # Feeds the scene-graph row's consistency review colors.
            self._compose_json(sc, "consistency.json",
                               "compose/consistency.py")
        elif p == "/snap.json":
            # compose/snap.py output (PH1 analyzer): per-object deterministic
            # correction making the top supported_by option physically exact
            # (R4 gate). Feeds the scene-graph row's snap ghosts + colors.
            self._compose_json(sc, "snap.json", "compose/snap.py")
        elif p == "/edit_proposals.json":
            # compose/propose_edits.py output (isolated add/delete
            # proposer): DELETE verdicts per doubt-flagged object + ADD
            # proposals with declared support. Feeds the scene-graph
            # row's edits review mode.
            self._compose_json(sc, "edit_proposals.json",
                               "compose/propose_edits.py")
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
        elif p.startswith("/graph_crops_ctx/"):
            # CONTEXT crops (padded 35%/35%/75% + red outline) — the exact
            # views the appearance-v3 describe pass saw; shown in the judged
            # card alongside tight crops so review sees the pipeline's real
            # evidence. Same names as graph/crops/, same sanitize+resolve.
            base = (paths.scene_dir(sc) / "graph" / "crops_ctx").resolve()
            name = p[len("/graph_crops_ctx/"):].lstrip("/")
            name = "".join(ch for ch in name if ch.isalnum() or ch in "_-.")
            f = (base / name).resolve() if name else base
            if name and f.is_file() and base in f.parents:
                self._send(200, f.read_bytes(), "image/png", cache=True)
            else:
                self._send(404, b"no such graph ctx crop")
        elif p == "/composed.glb":
            # composition C6 output (RENDER frame; browser flips via
            # frame.raw_to_render, self-inverse)
            f = paths.package_dir(sc) / "composed_scene2.glb"
            if f.exists():
                self._send(200, f.read_bytes(), "model/gltf-binary")
            else:
                self._send(404, b"no composed_scene2.glb; run composition/place2.py")
        elif p == "/fitted_preview.json":
            # compose/fit_preview.py record: what was placed + the
            # DECIDED front per item (front_dir_raw) -- feeds the fit
            # view's bright arrows
            self._compose_json(sc, "fitted_preview.json",
                               "compose/fit_preview.py")
        elif p == "/fit_check.json":
            # compose/fit_check.py output (deterministic bounds+clip
            # report over the placed preview) -- feeds the scene-model
            # row's fit-check view (red OOB / orange clips + overlap
            # region wireframes)
            self._compose_json(sc, "fit_check.json",
                               "compose/fit_check.py")
        elif p == "/shopping.json":
            # compose/shopping.py output (anchor candidates + deferred
            # subs): the FIT SET -- feeds the scene-model row's fit view
            self._compose_json(sc, "shopping.json", "compose/shopping.py")
        elif p == "/fitted_preview.glb":
            # compose/fit_preview.py output: the shopping module's #1
            # candidates naively placed (RAW frame baked in, no
            # browser-side flip) -- the "fitted preview" HUD layer
            f = paths.compose_dir(sc) / "fitted_preview.glb"
            if f.exists():
                self._send(200, f.read_bytes(), "model/gltf-binary")
            else:
                self._send(404, b"no fitted_preview.glb; run "
                                b"compose/fit_preview.py --scene "
                           + sc.encode())
        elif p == "/subs_preview.glb":
            # sub rounds: every anchor's best sub GLB merged (cp7
            # host-aware > cp6 jiggled > cp5 raw; RAW frame like
            # fitted_preview.glb — no browser-side flip). Built by
            # experiments/build_subs_preview.py.
            f = paths.compose_dir(sc) / "subs_preview.glb"
            if f.exists():
                self._send(200, f.read_bytes(), "model/gltf-binary")
            else:
                self._send(404, b"no subs_preview.glb; run "
                                b"experiments/build_subs_preview.py "
                                b"--scene " + sc.encode())
        elif p == "/collider.glb":
            # Marble bundle collider, ICP-registered into the RAW frame
            # (collider_register.py) — already raw, so NO browser-side flip.
            f = paths.scene_dir(sc) / "collider_registered.glb"
            if f.exists():
                self._send(200, f.read_bytes(), "model/gltf-binary")
            else:
                self._send(404, b"no collider_registered.glb; run "
                                b"collider_register.py --scene " + sc.encode())
        elif p == "/human.glb":
            # stock reference human for scale eyeballing (CesiumMan,
            # Khronos glTF sample assets, CC-BY 4.0 Cesium), BAKED to a
            # static y-up mesh: exactly 1.75 m tall, feet at y=0 (the
            # raw skinned+Z_UP original defeated browser-side bbox
            # scaling -- wall-sized legs, 08-02). Scene-independent.
            f = HERE / "assets" / "human_static.glb"
            if f.exists():
                self._send(200, f.read_bytes(), "model/gltf-binary",
                           cache=True)
            else:
                self._send(404, b"no viewer/assets/human.glb")
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
