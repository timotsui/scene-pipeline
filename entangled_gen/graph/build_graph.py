"""
Pass 1 -- the RECORD builder (record-then-judge, PLAN_SCENE_GRAPH.md 0a).

Rebuilt 2026-07-26 on the PANO TRACK (the analyzer-seeded v1 is archived as
scene_graph_v1.json / graph/crops_v1). Writes out/<scene>/scene_graph.json
with the RECORD layer only: nodes + evidence + open questions, edges: []
(graph/build_edges.py fills geometric edges + the SAME_CANDIDATE queue;
rerunning THIS script resets edges by design, so run edges again after).

THE RECORD COMMITS TO NOTHING. It writes down everything extraction already
knows, deterministically (zero model calls, byte-reproducible):
  - NO MERGING ANYWHERE IN PASS 1 (user amendment 2026-07-26 late: "record
    both objects and indicate their relationship faithfully") -- every f30
    manifest object = one node, duplicates included; probable-duplicate
    pairs are recorded as SAME_CANDIDATE edges by build_edges.py (zone
    "confident" IoU>=0.6 / "gray" IoU .40-.60 + containment>=.90) and
    MERGING IS A JUDGE VERDICT, reversible by rerunning one cached pass.
    The former manifest_dedup.py stage is RETIRED;
  - every candidate LABEL from every member detection, with scores -- the
    full multiset; label_provisional wherever more than one distinct label
    exists (canonical naming = the judge pass, NOT here);
  - evidence as pointers: member detections (2D box, view, score), plus a
    deterministically CUT crop image per member (graph/crops/) so the record
    is reviewable by eye and the judge pass reads them;
  - downstream state (retrieval picks, placement, cut status) is NOT here
    (v1 reversal): those are consumers of the graph, not evidence.

FRAME (the #1 silent-failure class): everything is the RAW gen_raw.ply
frame. Physical up = -y (rot180 convention): floor_y > ceiling_y
NUMERICALLY; a box's physical BOTTOM is its MAX raw y.

---------------------------------------------------------------------------
RECORD NODE SCHEMA (this docstring is the contract)
---------------------------------------------------------------------------
Detection nodes (ids = manifest obj_XXX -- identity is preserved):
  id, source: "detection", type: "object"
      (windows/doors/curtains stay ordinary object nodes -- USER DECISION
       07-26: no label-based architecture typing; geometry edges + the
       judge settle typing later)
  label               primary label (manifest), a PLACEHOLDER not a verdict
  label_provisional   true iff the node's label multiset has >1 distinct
                      label (incl. dedup alt_labels)
  labels              the full multiset: [{label, score, view, member}]
                      sorted by score desc, one entry per member detection
  geometry            center/size/aabb_min/aabb_max (RAW, meters),
                      yaw: null (honest gap), amodal: null (honest gap --
                      amodal completion was never computed for the pano
                      track; the old amodal_boxes.json belongs to the
                      retired legacy manifest's ids)
  evidence            {views, n_detections, n_whole, members: [{member
                      (index into the lift pool), view, label, score,
                      box_2d [xmin,ymin,xmax,ymax] in that view's 960px
                      crop image, truncated, crop (graph/crops/<file> or
                      null)}]}
  provenance          {manifest (file this node came from), peak_score,
                      flags (recenter_refined / retake_confirmed / ...)}
  open_questions      subset of ["naming"] -- naming iff label_provisional
                      (same-vs-part questions live on SAME_CANDIDATE edges,
                      filled by build_edges.py)

Envelope nodes (6, source "envelope", type "architecture"): arch_floor
(plane y=floor_y raw -- the NUMERIC MAX y), arch_ceiling, arch_wall_x0/x1/
z0/z1 -- same plane/extent geometry as v1 (unchanged machinery).

Top level: scene, layer: {record: true, judged: false} (the judge pass
adds verdict fields later, REFERENCING these nodes, never overwriting),
frame contract, lineage (manifest chain + pool + seg dir + pano meta +
bundle prompt.txt text -- the generation prompt is evidence), counts,
open_questions {same_candidate_pairs (from the manifest's
deferred_semantic), naming_nodes}, nodes, edges: [].

Standalone + idempotent (pure function of its inputs; no timestamps).
Run:  python graph/build_graph.py --scene bedroom_marble
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths     # noqa: E402
import envelope  # noqa: E402

CROP_PAD = 0.10      # fractional padding around the 2D box when cutting crops
MANIFEST_DEFAULT = "scene_manifest_pano2c_rc_f30.json"
POOL_DEFAULT = "rig_sp0/lift_poolc.json"
CROPSRC_DEFAULT = "rig_sp0/crops"


def load_inputs(scene, a):
    sdir = paths.scene_dir(scene)
    p = {
        "manifest": sdir / a.manifest,
        "pool": sdir / a.pool,
        "crop_src": sdir / a.crop_src,
        "envelope": paths.envelope_npz(scene),
        "bundle_path": sdir / "bundle_path.txt",       # optional
        "pano_meta": sdir / "rig_sp0" / "pano_selfrender_meta.json",
    }
    # ⚠ `envelope` IS ONLY REQUIRED ON THE FALLBACK PATH, and demanding it
    # here unconditionally was stale. It is read at ONE site — the else
    # branch below that builds PLACEHOLDER architecture nodes from the
    # envelope grid when there is no room_shell.json. room_shell.py
    # superseded that on 07-26 ("architecture measurement moved to
    # room_shell.py"), envelope.py was PARKED the same day, and
    # pipeline_map.html has drawn it with no outgoing arrow ever since.
    #
    # So the funnel does not run it, correctly — and this line then
    # crashed the first genuinely fresh scene at the first stage after
    # the funnel, having passed all eleven intake stages
    # (`[record] MISSING inputs: ['envelope']`, 2026-08-11B). Every dev
    # scene had a stale envelope.npz from the era when it did run, which
    # is why nothing caught it before.
    optional = ("bundle_path",)
    if (sdir / "room_shell.json").exists():
        optional += ("envelope",)
    missing = [k for k, f in p.items() if not f.exists()
               and k not in optional]
    if missing:
        raise SystemExit(f"[record] MISSING inputs: {missing}")
    man = json.loads(p["manifest"].read_text())
    pool = json.loads(p["pool"].read_text())["pool"]
    prompt_text = None
    if p["bundle_path"].exists():
        pf = Path(p["bundle_path"].read_text().strip()) / "prompt.txt"
        if pf.exists():
            prompt_text = pf.read_text(encoding="utf-8",
                                       errors="replace").strip()
    return p, man, pool, prompt_text


def cut_crops(nodes, pool, crop_src, crop_dir, sdir=None):
    """Deterministic crop per member detection: pad the 2D box by CROP_PAD,
    clamp to the view image, save PNG.

    THE FOLDER IS WIPED AND REBUILT EVERY RUN (2026-08-10). It used to be
    topped up ("skip existing files — content is a pure function of view
    image x box"). That assumption is false ACROSS scene re-runs: node and
    member NUMBERS are handed out fresh, a leftover file from the old
    numbering can share a name with a new crop, and skipping serves the
    dead object's picture (living 08-06 re-run: 9 crops showed other
    objects; the shelf carried the old coffee table's photo, and J6/J9
    described what they were shown). A stage owns its output folder:
    rebuilding means replacing, never topping up. Cutting all crops takes
    seconds, so the shortcut bought nothing.
    A member may state its own image path ("img", scene-relative — inline
    retake members do, their shots live outside crop_src)."""
    from PIL import Image
    if crop_dir.exists():
        shutil.rmtree(crop_dir)
    crop_dir.mkdir(parents=True, exist_ok=True)
    cache = {}
    n_cut = n_missing = 0
    for n in nodes:
        for m in n["evidence"]["members"]:
            src = (sdir / m["img"] if m.get("img") and sdir
                   else crop_src / f"{m['view']}.webp")
            if not src.exists():
                m["crop"] = None
                n_missing += 1
                continue
            out = crop_dir / f"{n['id']}_m{m['member']:03d}.png"
            m["crop"] = out.name
            if m["view"] not in cache:
                cache[m["view"]] = Image.open(src).convert("RGB")
            im = cache[m["view"]]
            x0, y0, x1, y1 = m["box_2d"]
            px, py = (x1 - x0) * CROP_PAD, (y1 - y0) * CROP_PAD
            box = (max(0, int(x0 - px)), max(0, int(y0 - py)),
                   min(im.width, int(x1 + px)), min(im.height, int(y1 + py)))
            if box[2] <= box[0] or box[3] <= box[1]:
                m["crop"] = None
                n_missing += 1
                continue
            im.crop(box).save(out)
            n_cut += 1
    return n_cut, n_missing


def build_detection_nodes(man, pool):
    nodes = []
    for o in man["objects"]:
        members = []
        for idx in o.get("members", []):
            L = pool[idx]
            b = L["box"]
            members.append({
                "member": idx,
                "view": L["view"],
                "label": L["label"],
                "score": round(L["score"], 3),
                "box_2d": [round(b["xmin"], 1), round(b["ymin"], 1),
                           round(b["xmax"], 1), round(b["ymax"], 1)],
                "truncated": bool(L.get("trunc")),
                "crop": None,          # cut_crops() fills
            })
        # INLINE members (2026-08-10): SP4's enrichment children are found
        # on RETAKE views whose detections never enter the pool, so they
        # carry their evidence inline — view + 2D rect + the image path
        # (retake shots live outside crop_src). Without this the child is
        # born photo-less: no crop, no J6 description, a NO PHOTO row at
        # J9. Member numbers count within the node (pool indexes are
        # meaningless here); crop filenames stay unique via the node id.
        for j, im in enumerate(o.get("members_inline") or []):
            members.append({
                "member": j,
                "view": im["view"],
                "label": im["label"],
                "score": im["score"],
                "box_2d": im["box_2d"],
                "truncated": bool(im.get("truncated")),
                "img": im.get("img"),
                "crop": None,
            })
        members.sort(key=lambda m: -m["score"])
        distinct = sorted({m["label"] for m in members} | {o["label"]})
        provisional = len(distinct) > 1
        nodes.append({
            "id": o["id"],
            "source": "detection",
            "type": "object",
            "label": o["label"],
            "label_provisional": provisional,
            "labels": members and [
                {"label": m["label"], "score": m["score"],
                 "view": m["view"], "member": m["member"]}
                for m in members] or [],
            "distinct_labels": distinct,
            "geometry": {
                "center": o["center"], "size": o["size"],
                "aabb_min": o["aabb_min"], "aabb_max": o["aabb_max"],
                "yaw": None,
                "amodal": None,
            },
            "evidence": {
                "views": o.get("views", []),
                "n_detections": o.get("n_detections"),
                "n_whole": o.get("n_whole"),
                "members": members,
            },
            "provenance": {
                "manifest": None,          # filled by main() (file name)
                "peak_score": o["score"],
                "flags": [f for f in o.get("flags", [])],
            },
            "open_questions": (["naming"] if provisional else []),
        })
    return nodes


def build_shell_nodes(shell):
    """Architecture nodes from the MEASURED room shell (room_shell.py W1,
    PLAN_ROOM_SHELL.md): wall segments with fitted planes + evidence +
    parallel candidate surfaces, measured floor/ceiling. All values RAW
    (shell stores upright; raw = upright * r2r componentwise)."""
    r2r = shell["frame"]["raw_to_render"]
    sy = r2r[1]
    floor_raw = shell["floor_y_raw"]
    ceil_raw = shell["ceiling_y_raw"]

    def node(nid, category, plane, extent, evidence):
        return {
            "id": nid, "source": "envelope", "type": "architecture",
            "label": nid.replace("arch_", "").replace("_", " "),
            "label_provisional": False,
            "labels": [], "distinct_labels": [category],
            "geometry": {"plane": plane, "extent": extent, "yaw": None,
                         "amodal": None},
            "evidence": {"views": [], "n_detections": 0, "n_whole": 0,
                         "members": [], **(evidence or {})},
            "provenance": {"manifest": None, "peak_score": None,
                           "flags": [], "detector": "room_shell.py (W1)"},
            "open_questions": [],
        }

    fnote = ("RAW frame, physical up = -y: floor is the numeric MAX y "
             "plane (floor_y > ceiling_y numerically); MEASURED from the "
             "splat y-histogram peak (room_shell.py)")
    ns = [
        node("arch_floor", "floor",
             {"axis": "y", "value_raw": floor_raw,
              "inward_normal_raw": [0, -1, 0], "note": fnote}, None,
             {"measured": True}),
        node("arch_ceiling", "ceiling",
             {"axis": "y", "value_raw": ceil_raw,
              "inward_normal_raw": [0, 1, 0],
              "note": "numeric MIN y = physical top; MEASURED"}, None,
             {"measured": True,
              "collider_planes": [p for p in
                                  (shell.get("collider") or {}).get(
                                      "planes", []) if p["axis"] == "y"]}),
    ]
    # W5 (2026-08-10, unattended-run audit): a shell carrying the POLYGON
    # block builds its wall nodes from the polygon SEGMENTS — one node
    # per segment (cardinal planes + connectors), ids arch_wall_00..NN,
    # raw-frame values precomputed by room_shell.py. A shell without the
    # block (polygon fit failed / old scene) falls through to the v1
    # one-wall-per-axis-side loop below unchanged.
    poly = shell.get("polygon")
    if poly:
        for s in poly["segments"]:
            ev = {"measured": s["status"] == "measured",
                  "traced_ink_fraction": s["traced_ink_fraction"],
                  "length_m": s["length_m"],
                  **({"fit": s["evidence"]} if s.get("evidence") else {})}
            y_ext = sorted([round(floor_raw, 3), round(ceil_raw, 3)])
            if s["kind"] != "connector":
                axc = 0 if s["axis"] == "x" else 2
                normal = [0.0, 0.0, 0.0]
                normal[axc] = float(-s["interior_side_raw"])
                tc = 1 if s["axis"] == "x" else 0
                p, q = s["endpoints_raw"]
                t0, t1 = sorted((p[tc], q[tc]))
                ns.append(node(
                    "arch_" + s["id"], "wall",
                    {"axis": s["axis"], "value_raw": s["plane_raw_m"],
                     "inward_normal_raw": normal,
                     "note": "polygon shell segment (W4 trace->close->"
                             "merge; majority plane)"},
                    {("z_raw" if s["axis"] == "x" else "x_raw"): [t0, t1],
                     "y_raw": y_ext}, ev))
            else:
                n2 = s["inward_normal_raw"]
                ns.append(node(
                    "arch_" + s["id"], "wall",
                    {"axis": None, "kind": "connector",
                     "inward_normal_raw": [n2[0], 0.0, n2[1]],
                     "offset_raw": s["plane_offset_raw"],
                     "note": "polygon connector segment — angled outline "
                             "piece; defines interior only (no "
                             "axis-aligned plane)"},
                    {"endpoints_raw": s["endpoints_raw"], "y_raw": y_ext},
                    ev))
        return ns
    for w in shell["walls"]:
        col = 0 if w["axis"] == "x" else 2
        tcol = 2 if w["axis"] == "x" else 0
        s_ax, s_t = r2r[col], r2r[tcol]
        val_raw = round(w["plane_upright_m"] * s_ax, 3)
        normal_raw = [0.0, 0.0, 0.0]
        normal_raw[col] = w["inward_normal_upright"][col] * s_ax
        ext = None
        span = w.get("extent_tangent_span_m") or w.get(
            "extent_tangent_observed_m")
        if span:
            t = sorted(v * s_t for v in span)
            ext = {("z_raw" if w["axis"] == "x" else "x_raw"):
                   [round(t[0], 3), round(t[1], 3)],
                   "y_raw": sorted([round(floor_raw, 3),
                                    round(ceil_raw, 3)])}
        observed = None
        if w.get("extent_tangent_observed_m"):
            o = sorted(v * s_t for v in w["extent_tangent_observed_m"])
            observed = [round(o[0], 3), round(o[1], 3)]
        parallels = [{"value_raw": round(p["position"] * s_ax, 3),
                      "point_count": p["point_count"],
                      "collider": p.get("collider")}
                     for p in w.get("parallel_surfaces", [])]
        ns.append(node(
            "arch_" + w["id"], "wall",
            {"axis": w["axis"], "value_raw": val_raw,
             "inward_normal_raw": normal_raw,
             "note": "MEASURED structural plane (outermost strong "
                     "candidate; vertical-prism wall-cell fit)"},
            ext,
            {"measured": True,
             "point_count": w["evidence"]["point_count"],
             "collider": w["evidence"]["collider"],
             "observed_tangent_raw": observed,
             "observed_coverage": w["evidence"].get("observed_coverage"),
             "parallel_surfaces": parallels}))
    return ns


def build_envelope_nodes(env):
    """FALLBACK when no room_shell.json exists: floor / ceiling / 4 walls
    from the envelope grid bounds (splat p1..p99 extent — placeholders,
    W0 audit measured them off by up to 0.4 m; run room_shell.py).
    RAW frame: physical up = -y, so the FLOOR is the numeric MAX y plane.
    (Unchanged v1 machinery, reshaped to the record schema.)"""
    x0, z0, cell = float(env["x0"]), float(env["z0"]), float(env["cell"])
    nx, nz = int(env["nx"]), int(env["nz"])
    x1, z1 = x0 + nx * cell, z0 + nz * cell
    floor_y, ceil_y = float(env["floor_y"]), float(env["ceil_y"])

    def node(nid, category, plane, extent):
        return {
            "id": nid, "source": "envelope", "type": "architecture",
            "label": nid.replace("arch_", ""),
            "label_provisional": False,
            "labels": [], "distinct_labels": [category],
            "geometry": {"plane": plane, "extent": extent, "yaw": None,
                         "amodal": None},
            "evidence": {"views": [], "n_detections": 0, "n_whole": 0,
                         "members": []},
            "provenance": {"manifest": None, "peak_score": None,
                           "flags": [], "detector": "envelope.npz"},
            "open_questions": [],
        }

    fnote = ("RAW frame, physical up = -y: floor is the numeric MAX y plane "
             "(floor_y > ceiling_y numerically)")
    ext_xz = {"x_raw": [round(x0, 3), round(x1, 3)],
              "z_raw": [round(z0, 3), round(z1, 3)]}
    ns = [
        node("arch_floor", "floor",
             {"axis": "y", "value_raw": round(floor_y, 3),
              "inward_normal_raw": [0, -1, 0], "note": fnote}, ext_xz),
        node("arch_ceiling", "ceiling",
             {"axis": "y", "value_raw": round(ceil_y, 3),
              "inward_normal_raw": [0, 1, 0],
              "note": "numeric MIN y = physical top"}, ext_xz),
    ]
    ext_y = {"y_raw": [round(ceil_y, 3), round(floor_y, 3)]}
    walls = [("arch_wall_x0", "x", x0, [1, 0, 0],
              {"z_raw": ext_xz["z_raw"], **ext_y}),
             ("arch_wall_x1", "x", x1, [-1, 0, 0],
              {"z_raw": ext_xz["z_raw"], **ext_y}),
             ("arch_wall_z0", "z", z0, [0, 0, 1],
              {"x_raw": ext_xz["x_raw"], **ext_y}),
             ("arch_wall_z1", "z", z1, [0, 0, -1],
              {"x_raw": ext_xz["x_raw"], **ext_y})]
    for nid, ax, val, normal, ext in walls:
        ns.append(node(nid, "wall",
                       {"axis": ax, "value_raw": round(val, 3),
                        "inward_normal_raw": normal,
                        "note": "envelope grid bound (splat p1..p99 extent)"},
                       ext))
    return ns


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--manifest", default=MANIFEST_DEFAULT)
    ap.add_argument("--pool", default=POOL_DEFAULT)
    ap.add_argument("--crop-src", default=CROPSRC_DEFAULT)
    ap.add_argument("--no-crops", action="store_true",
                    help="skip crop cutting (crop refs stay null)")
    # --recrop is GONE (2026-08-10): the crops folder is now wiped and
    # rebuilt on every run, so there is nothing to opt into.
    a = ap.parse_args()
    scene = a.scene
    sdir = paths.scene_dir(scene)

    input_paths, man, pool, prompt_text = load_inputs(scene, a)
    det_nodes = build_detection_nodes(man, pool)
    for n in det_nodes:
        n["provenance"]["manifest"] = a.manifest
    shell_f = sdir / "room_shell.json"
    if shell_f.exists():
        env_nodes = build_shell_nodes(json.loads(shell_f.read_text()))
        arch_src = f"room_shell.json (measured, {len(env_nodes) - 2} walls)"
    else:
        # THE PLACEHOLDER PATH. envelope.py is PARKED (map, 07-26) and the
        # funnel does not run it, so on a scene built the current way this
        # branch is unreachable — room_shell always exists. It is kept for
        # old scenes that have an envelope.npz and no shell. Say plainly
        # what is missing rather than dying inside numpy.
        if not paths.envelope_npz(scene).exists():
            raise SystemExit(
                "[record] no room_shell.json AND no envelope.npz — there "
                "is nothing to build the room's architecture from. Run "
                "room_shell.py --scene <s> (the funnel's `shell` stage); "
                "envelope.py is parked and is not the way to fix this.")
        env_nodes = build_envelope_nodes(envelope.load(scene))
        arch_src = "envelope grid bounds (PLACEHOLDER — run room_shell.py)"
    nodes = det_nodes + env_nodes

    n_cut = n_missing = 0
    if not a.no_crops:
        n_cut, n_missing = cut_crops(
            det_nodes, pool, input_paths["crop_src"],
            sdir / "graph" / "crops", sdir=sdir)
    # a node with ZERO crops is invisible to every crop-fed judge (J1, J6
    # describe, J9) for the rest of the pipeline — on an unattended run
    # that must be loud, counted from the data, never silent
    photoless = [n["id"] for n in det_nodes
                 if not any(m.get("crop")
                            for m in n["evidence"]["members"])]
    if photoless and not a.no_crops:
        print(f"[record] WARNING {len(photoless)} node(s) with NO crop — "
              f"blind to J1/J6/J9: {', '.join(photoless)}")

    naming_nodes = [n["id"] for n in det_nodes if n["label_provisional"]]

    man_frame = man["frame"]
    graph = {
        "scene": scene,
        "generated_by": ("graph/build_graph.py (pass 1 -- RECORD: nodes + "
                         "evidence) + graph/build_edges.py (pass 1 -- RECORD:"
                         " geometric edges + SAME_CANDIDATE queue)"),
        "layer": {"record": True, "judged": False,
                  "note": ("record-then-judge (PLAN_SCENE_GRAPH.md 0a): "
                           "this file currently holds the RECORD only; the "
                           "judge passes add verdict fields referencing "
                           "these nodes, never overwriting them")},
        "frame": {
            "space": "raw",
            "up": man_frame["up"],
            "floor_y": man_frame["floor_y"],
            "note": ("ALL geometry in RAW gen_raw.ply space; physical up = "
                     "-y (rot180), floor_y > ceiling_y numerically; a box's "
                     "physical BOTTOM is its MAX raw y."),
        },
        "lineage": {
            "manifest": str(input_paths["manifest"]),
            "lift_pool": str(input_paths["pool"]),
            "crop_source": str(input_paths["crop_src"]),
            "pano_meta": str(input_paths["pano_meta"]),
            "architecture_source": arch_src,
            "generation_prompt": prompt_text,
        },
        "counts": {
            "nodes": len(nodes),
            "detection_nodes": len(det_nodes),
            "envelope_nodes": len(env_nodes),
            "label_provisional_nodes": len(naming_nodes),
            "same_candidate_pairs": 0,     # build_edges.py fills
            "crops": {"cut": n_cut, "missing": n_missing},
        },
        "open_questions": {
            # SAME_CANDIDATE pairs are computed from geometry by
            # build_edges.py (no pre-merged dedup stage anymore)
            "same_candidate_pairs": [],
            "naming_nodes": naming_nodes,
        },
        "nodes": nodes,
        "edges": [],
    }

    out = sdir / "scene_graph.json"
    out.write_text(json.dumps(graph, indent=1))

    print(f"[record] wrote {out}")
    print(f"[record] {len(nodes)} nodes = {len(det_nodes)} detection + "
          f"{len(env_nodes)} architecture ({arch_src})")
    print(f"[record] label multisets: {len(naming_nodes)} nodes provisional "
          f"(open naming question): {naming_nodes}")
    print("[record] same-candidate pairs: computed from geometry by "
          "build_edges.py (no pre-merge dedup stage)")
    print(f"[record] crops: folder rebuilt, {n_cut} cut, "
          f"{n_missing} missing/degenerate")
    print(f"[record] generation prompt: "
          f"{'attached (' + str(len(prompt_text)) + ' chars)' if prompt_text else 'NOT FOUND (lineage.generation_prompt = null)'}")
    print("[record] edges: [] (run graph/build_edges.py next)")


if __name__ == "__main__":
    main()
