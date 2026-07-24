"""
Step 1 -- node-assembly: build the unified semantic scene graph (NODES ONLY).

Writes out/<scene>/scene_graph.json with every node the pipeline knows about
and edges: [] (Step 2 -- graph/build_edges.py -- fills the edges array; rerunning
THIS script resets edges to [] by design, so run Step 2 again after).

USER DECISION (2026-07-22, PLAN_SCENE_GRAPH.md section 2): the node seed is the
ANALYZER box set (analyzer/bridged_boxes.json, 103 boxes ana_000..ana_102), not
the manifest, not a union. Manifest metadata (amodal status, cut status,
retrieval picks, placement poses) attaches to nodes VIA the existing
analyzer<->manifest match mapping in analyzer/match_report.json.

FRAME (the #1 silent-failure class): everything is the RAW gen_raw.ply frame.
Physical up = -y (rot180 convention, see paths.py docstring + scene_manifest
frame block): floor_y (0.029) > ceiling_y (-2.793) NUMERICALLY. The physical
BOTTOM of a box is its MAX y in raw coordinates; physical height h = -y_raw.

---------------------------------------------------------------------------
NODE SCHEMA (this docstring is the contract)
---------------------------------------------------------------------------
Detection nodes (103, ids ana_000..ana_102, source "splat_analyzer job_high"):

  id                    "ana_XXX" (envelope nodes: "arch_floor", "arch_ceiling",
                        "arch_wall_x0" / "arch_wall_x1" / "arch_wall_z0" /
                        "arch_wall_z1")
  label                 detector label as emitted (e.g. "desk lamp")
  canonical_category    label mapped through the synonym map copied from
                        match_report.json (e.g. "desk lamp" -> "lamp");
                        labels not in any group map to themselves
  synonyms              full member list of the synonym group ([label] if none)
  type                  "architecture" for labels {window, door, curtain,
                        air conditioner, ceiling light} and for all
                        envelope-derived nodes; "object" otherwise
  source                "detection" | "envelope"
  geometry              detection nodes: center/size/aabb_min/aabb_max (RAW,
                        meters), yaw: null (HONEST GAP -- the analyzer never
                        estimates orientation), rotation_quat_xyzw (always
                        identity), caveats list (subset of):
                          "surface_bias"      centroid biased toward the
                                              camera-visible surface
                          "fabricated_z_extent"  box depth extent fabricated
                                              as (w+h)/2, never measured
                          "axis_aligned"      identity rotation by tool design
                          "center_outside_envelope"       (bridge sanity flag)
                          "extent_partially_outside_envelope"  (bridge flag)
                        envelope nodes: plane {axis, value_raw, note} + extent
                        (raw-frame intervals), caveats []
  provenance            detection: {detector: "splat_analyzer job_high",
                        votes, peak_score, standpoint_count (distinct camera
                        standpoints among evidence frames, via
                        transforms.json position_idx), matched_manifest_id
                        (or null), match_distance_m (or null),
                        manifest: {...donor metadata: label, score, center,
                        size, aabb, n_points, views, n_detections,
                        amodal_extended} or null}
                        envelope: {detector: "envelope.npz"}
  confidence_tier       "confirmed"  -- has a manifest match (19 nodes; the
                                       matched set's minimum votes is 9)
                        "candidate"  -- no match, votes >= 8 (threshold = the
                                       analyzer's own config-default min_votes;
                                       observed vote distribution over the 103:
                                       min 3 / median 23 / max 56)
                        "weak"       -- no match, votes < 8 (min-vote
                                       survivors, single-standpoint clusters)
                        envelope nodes: "confirmed" (structural, derived from
                        the splat itself, not a detector)
  views                 {evidence_frames: sorted unique frame indices from
                        analyzer job_high interactions.json, best_crop: null
                        (Step 3 -- appearance-pass -- fills)}
  gaussians             {cut: false} for everything except the node matched to
                        obj_004 (= ana_101), which gets {cut: true,
                        source_object, variant, foreground_ply, count,
                        background_ply, stats_json} from cut/obj_004_v2/
  state                 {pick_uid, pick: {category, scale, fit, clip,
                        n_admissible, gate_relaxed} | null, placement_pose:
                        [per-part {part, center, size, perm, scale, mount,
                        yaw?}] | null} -- from package/picks2.json and
                        package/composed_state2.json via the manifest match;
                        nulls when the node has no manifest match or no state

Envelope nodes (6): arch_floor (plane y=floor_y raw -- the NUMERIC MAX y),
arch_ceiling (plane y=ceiling_y raw -- the numeric MIN y), arch_wall_x0/x1/
z0/z1 (vertical planes at the envelope grid's x/z bounds; inward normal
recorded in raw axis terms).

Top level: scene, frame contract (copied semantics), node_seed_decision,
provenance (input file paths + the manifest-based collide export
package/collisions.json recorded FOR PROVENANCE ONLY -- fresh INTERPENETRATES
edges are computed from analyzer boxes by build_edges.py), counts, nodes,
edges: [].

Standalone + idempotent (pure function of its inputs; no timestamps).
Run:  python graph/build_graph.py --scene bedroom_marble
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths     # noqa: E402
import envelope  # noqa: E402

ARCH_LABELS = {"window", "door", "curtain", "air conditioner", "ceiling light"}
CANDIDATE_MIN_VOTES = 8   # = analyzer config-default min_votes; see docstring


def load_inputs(scene):
    sdir = paths.scene_dir(scene)
    p = {
        "bridged_boxes": sdir / "analyzer" / "bridged_boxes.json",
        "match_report": sdir / "analyzer" / "match_report.json",
        "interactions": sdir / "analyzer" / "job_high" / "interactions.json",
        "transforms": sdir / "analyzer" / "job_high" / "transforms.json",
        "manifest": paths.manifest(scene),
        "envelope": paths.envelope_npz(scene),
        "picks": sdir / "package" / "picks2.json",
        "composed_state": sdir / "package" / "composed_state2.json",
        "collisions": sdir / "package" / "collisions.json",   # optional
        "cut_stats": sdir / "cut" / "obj_004_v2" / "stats.json",
    }
    missing = [k for k, f in p.items()
               if not f.exists() and k != "collisions"]
    if missing:
        raise SystemExit(f"[graph] MISSING inputs: {missing}")
    data = {k: (json.loads(f.read_text()) if f.suffix == ".json" and f.exists()
                else None) for k, f in p.items()}
    data["envelope"] = envelope.load(scene)
    return p, data


def synonym_lookup(match):
    groups = match["synonym_groups"]
    label2group = {m: g for g, ms in groups.items() for m in ms}

    def canon(label):
        return label2group.get(label.strip().lower(), label.strip().lower())

    def syns(label):
        g = label2group.get(label.strip().lower())
        return list(groups[g]) if g else [label.strip().lower()]

    return canon, syns


def evidence_and_standpoints(inter, transforms):
    """Per analyzer object (by bridge enumeration order -> ana_XXX):
    sorted unique evidence frame indices + distinct standpoint count."""
    f2sp = {i: fr.get("position_idx")
            for i, fr in enumerate(transforms.get("frames", []))}
    out = {}
    for i, o in enumerate(inter["objects"]):
        frames = sorted({f["frame_idx"] for f in o["frames"]})
        sps = {f2sp.get(fi) for fi in frames} - {None}
        out[f"ana_{i:03d}"] = (frames, len(sps))
    return out


def build_detection_nodes(data, input_paths):
    bridged = data["bridged_boxes"]
    match = data["match_report"]
    canon, syns = synonym_lookup(match)
    ev = evidence_and_standpoints(data["interactions"], data["transforms"])

    # match mapping: ana id -> manifest row
    ana2man = {r["analyzer_id"]: r for r in match["manifest_to_analyzer"]
               if r.get("matched")}
    man_objs = {o["id"]: o for o in data["manifest"]["objects"]}

    # per-manifest-group placement parts from composed_state2
    place_by_group = {}
    for e in data["composed_state"]["objects"]:
        place_by_group.setdefault(e["group"], []).append(e)

    env_flags = bridged.get("envelope_sanity", {})
    centers_out = set(env_flags.get("centers_outside_ids", []))
    extents_out = set(env_flags.get("extents_partially_outside_ids", []))

    cut_stats = data["cut_stats"]
    cut_manifest_id = cut_stats["object"]          # "obj_004"
    cut_dir = input_paths["cut_stats"].parent

    nodes = []
    enrich = {"manifest": 0, "pick": 0, "placement": 0, "cut": 0}
    for o in bridged["objects"]:
        nid = o["id"]
        label = o["label"]
        geom_caveats = ["surface_bias", "fabricated_z_extent", "axis_aligned"]
        if nid in centers_out:
            geom_caveats.append("center_outside_envelope")
        if nid in extents_out:
            geom_caveats.append("extent_partially_outside_envelope")

        row = ana2man.get(nid)
        manifest_meta = None
        state = {"pick_uid": None, "pick": None, "placement_pose": None}
        if row:
            enrich["manifest"] += 1
            mo = man_objs[row["manifest_id"]]
            manifest_meta = {
                "id": mo["id"], "label": mo["label"], "score": mo["score"],
                "center": mo["center"], "size": mo["size"],
                "aabb_min": mo["aabb_min"], "aabb_max": mo["aabb_max"],
                "n_points": mo.get("n_points"), "views": mo.get("views"),
                "n_detections": mo.get("n_detections"),
                "amodal_extended": mo.get("amodal_extended"),
            }
            pick = data["picks"].get(row["manifest_id"])
            if pick:
                enrich["pick"] += 1
                state["pick_uid"] = pick["uid"]
                state["pick"] = {k: pick.get(k) for k in
                                 ("category", "scale", "fit", "clip",
                                  "n_admissible", "gate_relaxed")}
            parts = place_by_group.get(row["manifest_id"])
            if parts:
                enrich["placement"] += 1
                state["placement_pose"] = [
                    {k: e[k] for k in
                     ("part", "center", "size", "perm", "scale", "mount")
                     } | ({"yaw": e["yaw"]} if "yaw" in e else {})
                    for e in parts]

        gaussians = {"cut": False}
        if row and row["manifest_id"] == cut_manifest_id:
            enrich["cut"] += 1
            gaussians = {
                "cut": True,
                "source_object": cut_manifest_id,
                "variant": cut_stats.get("variant"),
                "foreground_ply": str(cut_dir / "foreground.ply"),
                "count": cut_stats["foreground_gaussians"],
                "background_ply": str(cut_dir / "background.ply"),
                "stats_json": str(input_paths["cut_stats"]),
            }

        votes = o["votes"]
        if row:
            tier = "confirmed"
        elif votes >= CANDIDATE_MIN_VOTES:
            tier = "candidate"
        else:
            tier = "weak"

        frames, n_sp = ev[nid]
        nodes.append({
            "id": nid,
            "label": label,
            "canonical_category": canon(label),
            "synonyms": syns(label),
            "type": "architecture" if label in ARCH_LABELS else "object",
            "source": "detection",
            "geometry": {
                "center": o["center"], "size": o["size"],
                "aabb_min": o["aabb_min"], "aabb_max": o["aabb_max"],
                "yaw": None,
                "rotation_quat_xyzw": o["rotation_quat_xyzw"],
                "caveats": geom_caveats,
            },
            "provenance": {
                "detector": "splat_analyzer job_high",
                "votes": votes,
                "peak_score": o["peak_score"],
                "standpoint_count": n_sp,
                "matched_manifest_id": row["manifest_id"] if row else None,
                "match_distance_m": row["distance_m"] if row else None,
                "manifest": manifest_meta,
            },
            "confidence_tier": tier,
            "views": {"evidence_frames": frames, "best_crop": None},
            "gaussians": gaussians,
            "state": state,
        })
    return nodes, enrich


def build_envelope_nodes(env):
    """floor / ceiling / 4 walls as first-class architecture nodes.
    RAW frame: physical up = -y, so the FLOOR is the numeric MAX y plane."""
    x0, z0, cell = float(env["x0"]), float(env["z0"]), float(env["cell"])
    nx, nz = int(env["nx"]), int(env["nz"])
    x1, z1 = x0 + nx * cell, z0 + nz * cell
    floor_y, ceil_y = float(env["floor_y"]), float(env["ceil_y"])

    def node(nid, category, plane, extent):
        return {
            "id": nid, "label": nid.replace("arch_", ""),
            "canonical_category": category,
            "synonyms": [], "type": "architecture", "source": "envelope",
            "geometry": {"plane": plane, "extent": extent, "yaw": None,
                         "caveats": []},
            "provenance": {"detector": "envelope.npz"},
            "confidence_tier": "confirmed",
            "views": {"evidence_frames": [], "best_crop": None},
            "gaussians": {"cut": False},
            "state": {"pick_uid": None, "pick": None, "placement_pose": None},
        }

    fnote = ("RAW frame, physical up = -y: floor is the numeric MAX y plane "
             "(floor_y > ceiling_y numerically)")
    ext_xz = {"x_raw": [round(x0, 3), round(x1, 3)],
              "z_raw": [round(z0, 3), round(z1, 3)]}
    ns = [
        node("arch_floor", "floor",
             {"axis": "y", "value_raw": round(floor_y, 3),
              "inward_normal_raw": [0, -1, 0], "note": fnote},
             ext_xz),
        node("arch_ceiling", "ceiling",
             {"axis": "y", "value_raw": round(ceil_y, 3),
              "inward_normal_raw": [0, 1, 0],
              "note": "numeric MIN y = physical top"},
             ext_xz),
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
    ap.add_argument("--scene", default="bedroom_marble")
    args = ap.parse_args()
    scene = args.scene

    input_paths, data = load_inputs(scene)
    det_nodes, enrich = build_detection_nodes(data, input_paths)
    env_nodes = build_envelope_nodes(data["envelope"])
    nodes = det_nodes + env_nodes

    man_frame = data["manifest"]["frame"]
    coll = data["collisions"]
    coll_prov = None
    if coll is not None:
        coll_prov = {
            "path": str(input_paths["collisions"]),
            "state": coll.get("state"),
            "frame": coll.get("frame"),
            "n_pairs": len(coll.get("pairs", [])),
            "note": ("manifest/composition-based collide export, recorded for "
                     "provenance ONLY (and it is in the RENDER frame, not "
                     "raw); INTERPENETRATES edges in this graph are computed "
                     "fresh from the analyzer boxes by graph/build_edges.py"),
        }

    tiers = {}
    types = {}
    for n in nodes:
        tiers[n["confidence_tier"]] = tiers.get(n["confidence_tier"], 0) + 1
        types[n["type"]] = types.get(n["type"], 0) + 1

    graph = {
        "scene": scene,
        "generated_by": ("graph/build_graph.py (Step 1 -- node-assembly) + "
                         "graph/build_edges.py (Step 2 -- geometric-edges)"),
        "frame": {
            "space": "raw",
            "up": man_frame["up"],
            "floor_y": man_frame["floor_y"],
            "ceiling_y": man_frame["ceiling_y"],
            "note": ("ALL geometry in RAW gen_raw.ply space; physical up = -y "
                     "(rot180), floor_y > ceiling_y numerically; a box's "
                     "physical BOTTOM is its MAX raw y. render space = raw * "
                     "raw_to_render elementwise."),
            "raw_to_render": man_frame.get("raw_to_render"),
        },
        "node_seed_decision": (
            "USER DECISION 2026-07-22: nodes seeded from the analyzer's 103 "
            "bridged boxes (NOT the manifest, NOT a union); manifest/cut/pick/"
            "placement metadata attached via analyzer/match_report.json"),
        "provenance": {
            "inputs": {k: str(v) for k, v in input_paths.items()},
            "collide_export": coll_prov,
        },
        "counts": {
            "nodes": len(nodes),
            "detection_nodes": len(det_nodes),
            "envelope_nodes": len(env_nodes),
            "by_type": types,
            "by_tier": tiers,
            "enrichment": enrich,
        },
        "nodes": nodes,
        "edges": [],
    }

    out = paths.scene_dir(scene) / "scene_graph.json"
    out.write_text(json.dumps(graph, indent=1))

    # ---------------- sanity report ----------------
    print(f"[graph] wrote {out}")
    print(f"[graph] {len(nodes)} nodes = {len(det_nodes)} detection + "
          f"{len(env_nodes)} envelope")
    print(f"[graph] by type: {types}")
    print(f"[graph] by tier: {tiers}  (candidate threshold: votes >= "
          f"{CANDIDATE_MIN_VOTES}, no manifest match)")
    print(f"[graph] enrichment: manifest metadata on {enrich['manifest']} "
          f"nodes, picks on {enrich['pick']}, placement poses on "
          f"{enrich['placement']}, gaussian cut on {enrich['cut']}")
    n_match = len([r for r in data["match_report"]["manifest_to_analyzer"]
                   if r.get("matched")])
    n_only = data["match_report"]["analyzer_only_count"]
    n_near = len(det_nodes) - n_match - n_only
    print(f"[graph] match accounting: {n_match} matched + {n_only} "
          f"analyzer-only + {n_near} unmatched-but-near-a-compatible-manifest-"
          f"object (duplicate clusters within the 0.75 m radius)")
    unattached_state = [g for g in data["picks"]
                        if g.startswith("add_")]
    if unattached_state:
        print(f"[graph] note: composition state groups with NO node to attach "
              f"to (loop additions, no manifest object): {unattached_state}")
    print("[graph] edges: [] (run graph/build_edges.py next)")


if __name__ == "__main__":
    main()
