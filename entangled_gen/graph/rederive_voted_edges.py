"""Phase B2 -- LOOP-BACK: re-derive the geometric edges on the VOTED boxes.

The record's edges (graph/build_edges.py) were derived from the LIFTED
boxes. Then the judges resolved duplicates (graph[resolved]) and the
vote stage measured tighter, slice-voted boxes for those resolved
objects. Nothing ever re-asked the geometry question with the better
boxes: a table whose lifted box over-reached may have held an
INTERPENETRATES edge that the voted box dissolves, and a lamp whose
voted box finally touches the floor may only NOW be ON it.

This module closes that loop. Same derivation (build_edges.derive_edges
-- identical thresholds, identical code), different geometry:

    nodes     graph["resolved"]["nodes"]      (the judged object set)
    boxes     scene_manifest_slicevote_preview.json  VERBATIM
              (Phase C rule: voted boxes are COPIED, never recomputed;
               a resolved node with no voted box keeps its resolved
               geometry and is listed in unvoted_ids)
    planes    the record's envelope nodes, unchanged

WRITES NOTHING WITHOUT --apply. The default run prints the Gate-B2 DIFF
(what appeared / what dissolved, per edge type, vs the resolved edges)
for the user gate. With --apply the result lands ADDITIVELY under
graph["voted_edges"] -- the record layer, the judged layer and the
resolved layer are untouched, so this is a new layer, not a rewrite.

The judges can be pointed at that layer with
    python graph/triage_pairs.py --scene S --edges-from voted_edges
    python graph/judge_pairs.py  --scene S --edges-from voted_edges

Run:
  python graph/rederive_voted_edges.py --scene living_marble
  python graph/rederive_voted_edges.py --scene living_marble --apply
"""
import argparse
import copy
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import paths          # noqa: E402
from build_edges import SC_CONTAIN, derive_edges   # noqa: E402

VOTED_MANIFEST = "scene_manifest_slicevote_preview.json"
GEOM_KEYS = ("aabb_min", "aabb_max", "center", "size")
EDGE_TYPES = ("SAME_CANDIDATE", "IN", "IN_WALL", "ATTACHED", "ON",
              "INTERPENETRATES", "NEAR")


def voted_boxes(sdir, fname=VOTED_MANIFEST):
    """{id: geometry} straight out of the vote manifest -- VERBATIM."""
    p = sdir / fname
    if not p.exists():
        raise SystemExit(f"[rederive] no voted manifest: {p}")
    man = json.loads(p.read_text(encoding="utf-8"))
    return {o["id"]: {k: o[k] for k in GEOM_KEYS} for o in man["objects"]}


# --------------------------------------------------------------------------
# judge-side helpers: run J0/J1 against the voted layer instead of the record
# --------------------------------------------------------------------------

def layer_of(graph, edges_from):
    """The voted_edges layer dict, or None for the record layer."""
    if edges_from == "record":
        return None
    layer = graph.get("voted_edges")
    if not layer:
        raise SystemExit("[voted_edges] no graph['voted_edges'] -- run "
                         "graph/rederive_voted_edges.py --apply first")
    return layer


def overlay_voted_geometry(nodes_by_id, sdir, layer):
    """Copies of the record nodes carrying the layer's voted boxes, so a
    judge prompt quotes the geometry its edges were derived from. Nodes
    with no voted box (unvoted_ids, arch planes) pass through."""
    boxes = voted_boxes(sdir, layer.get("source_geometry", VOTED_MANIFEST))
    return {i: ({**n, "geometry": boxes[i]} if i in boxes else n)
            for i, n in nodes_by_id.items()}


def voted_nodes(graph, boxes):
    """Adapt graph[resolved][nodes] to the derivation's node contract:
    source/label/geometry/evidence.members. Members are the record
    members of each resolved cluster, concatenated (NEAR truncation
    facts read them). Returns (nodes, unvoted_ids)."""
    rec = {n["id"]: n for n in graph["nodes"]}
    nodes, unvoted = [], []
    for rn in graph["resolved"]["nodes"]:
        members = []
        for mid in rn.get("members") or []:
            m = rec.get(mid)
            if not m:
                continue
            members += ((m.get("evidence") or {}).get("members") or [])
        g = boxes.get(rn["id"])
        if g is None:
            unvoted.append(rn["id"])
            g = rn["geometry"]
        nodes.append({"id": rn["id"], "source": "detection",
                      "label": rn["name"], "geometry": copy.deepcopy(g),
                      "evidence": {"members": members}})
    return nodes, unvoted


def pairs_by_type(edges):
    """{type: {frozenset({a,b}): edge}} -- the resolved layer's edges are
    bare {a,b,type} triples, so the pair IS the comparable unit."""
    out = {}
    for e in edges:
        out.setdefault(e["type"], {})[frozenset((e["a"], e["b"]))] = e
    return out


def nesting_pairs(nesting):
    """{frozenset({small, host}): fact} for containment >= SC_CONTAIN."""
    out = {}
    for small, ents in (nesting or {}).items():
        for ent in ents:
            out[frozenset((small, ent["host"]))] = {
                "small": small, "host": ent["host"],
                "containment": ent["containment"], "iou": ent["iou"]}
    return out


def build_diff(old_edges, new_edges, old_nesting, new_nesting, names):
    """Gate-B2 diff. Numbers only exist on the NEW side (the resolved
    edges carry none), so appeared pairs ship their evidence and
    dissolved pairs ship the pair alone."""
    old_by, new_by = pairs_by_type(old_edges), pairs_by_type(new_edges)
    by_type, tot_a, tot_d = {}, 0, 0
    for t in list(EDGE_TYPES) + sorted((set(old_by) | set(new_by))
                                       - set(EDGE_TYPES)):
        if t in by_type:
            continue
        o, n = old_by.get(t, {}), new_by.get(t, {})
        app = [{"a": n[p]["a"], "b": n[p]["b"],
                "labels": [names.get(n[p]["a"]), names.get(n[p]["b"])],
                "evidence": n[p].get("evidence")}
               for p in n if p not in o]
        dis = [{"a": o[p]["a"], "b": o[p]["b"],
                "labels": [names.get(o[p]["a"]), names.get(o[p]["b"])]}
               for p in o if p not in n]
        if not (o or n):
            continue
        by_type[t] = {"resolved": len(o), "voted": len(n),
                      "appeared": app, "dissolved": dis}
        tot_a += len(app)
        tot_d += len(dis)

    onest, nnest = nesting_pairs(old_nesting), nesting_pairs(new_nesting)
    nest = {"resolved_layer_source": "record nodes' nesting facts",
            "note": ("the old side spans the RECORD nodes, the new side the "
                     "RESOLVED nodes -- a pair whose node was merged away by "
                     "the judges shows up as dissolved for that reason "
                     "alone, not because the voted box changed"),
            "old": len(onest), "new": len(nnest),
            "appeared": [nnest[p] for p in nnest if p not in onest],
            "dissolved": [onest[p] for p in onest if p not in nnest]}
    return {"containment_threshold": SC_CONTAIN,
            "totals": {"appeared": tot_a, "dissolved": tot_d},
            "by_type": by_type, "nesting": nest}


def print_diff(diff, unvoted, n_nodes, summary):
    print(f"[rederive] nodes: {n_nodes} resolved "
          f"({n_nodes - len(unvoted)} voted boxes, "
          f"{len(unvoted)} keeping resolved geometry: "
          f"{unvoted or 'none'})")
    print(f"[rederive] edge counts (voted): {summary['edge_counts']}")
    print(f"[rederive] self-check: "
          f"{'PASS' if summary['self_check']['passed'] else '*** FAIL ***'}")
    for c in summary["self_check"]["details"]:
        print(f"           {c}")
    t = diff["totals"]
    print(f"[rederive] GATE-B2 DIFF vs resolved edges: "
          f"{t['appeared']} appeared, {t['dissolved']} dissolved")
    for etype, d in diff["by_type"].items():
        print(f"  {etype}: resolved {d['resolved']} -> voted {d['voted']} "
              f"(+{len(d['appeared'])} / -{len(d['dissolved'])})")
        for e in d["appeared"]:
            print(f"      + {e['a']} -> {e['b']} {e['labels']} "
                  f"{json.dumps(e['evidence'])}")
        for e in d["dissolved"]:
            print(f"      - {e['a']} -> {e['b']} {e['labels']}")
    n = diff["nesting"]
    print(f"  NESTING (containment >= {diff['containment_threshold']}): "
          f"record {n['old']} -> voted {n['new']} "
          f"(+{len(n['appeared'])} / -{len(n['dissolved'])})")
    for e in n["appeared"]:
        print(f"      + {e['small']} in {e['host']} "
              f"contain {e['containment']} iou {e['iou']}")
    for e in n["dissolved"]:
        print(f"      - {e['small']} in {e['host']} "
              f"contain {e['containment']} iou {e['iou']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="write graph['voted_edges'] (additive); "
                         "without it NOTHING is written")
    ap.add_argument("--date", default=None,
                    help="date stamped into the layer header "
                         "(default: today)")
    args = ap.parse_args()

    sdir = paths.scene_dir(args.scene)
    gpath = sdir / "scene_graph.json"
    graph = json.loads(gpath.read_text(encoding="utf-8"))
    if not graph.get("resolved", {}).get("nodes"):
        raise SystemExit("[rederive] no resolved layer -- run the judges "
                         "and graph/materialize_verdicts.py first")

    boxes = voted_boxes(sdir)
    det, unvoted = voted_nodes(graph, boxes)
    env = {n["id"]: n for n in graph["nodes"] if n["source"] == "envelope"}
    floor_y = env["arch_floor"]["geometry"]["plane"]["value_raw"]
    ceil_y = env["arch_ceiling"]["geometry"]["plane"]["value_raw"]
    # W5: full geometry (plane + extent) — see build_edges.wall_claim_dist
    walls = {nid: n["geometry"] for nid, n in env.items()
             if nid.startswith("arch_wall")}

    d = derive_edges(det, env, floor_y, ceil_y, walls)

    names = {n["id"]: n["label"] for n in det}
    old_nesting = {n["id"]: n["nesting"] for n in graph["nodes"]
                   if n.get("nesting")}
    diff = build_diff(graph["resolved"]["edges"], d.edges,
                      old_nesting, d.nesting, names)
    print_diff(diff, unvoted, len(det), d.edge_summary)

    if not args.apply:
        print("[rederive] DRY -- nothing written (rerun with --apply after "
              "the gate)")
        return

    graph["voted_edges"] = {
        "built": args.date or str(date.today()),
        "built_from": "resolved nodes + voted boxes (loop-back B2)",
        "source_geometry": VOTED_MANIFEST,
        "unvoted_ids": unvoted,
        "edges": d.edges,
        "nesting": d.nesting,
        "edge_summary": d.edge_summary,
        "diff_vs_resolved": diff,
    }
    gpath.write_text(json.dumps(graph, indent=1), encoding="utf-8")
    print(f"[rederive] wrote graph['voted_edges'] into {gpath} "
          f"({len(d.edges)} edges) -- every other block untouched")


if __name__ == "__main__":
    main()
