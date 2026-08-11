"""THE VOTE-BOX LAYER — graph["voted"]: the scene graph AFTER the boxes
were elected.

NAMING (user, 2026-08-08): this stage does not vote anything. It renders
views of a node, lets the detections in them VOTE, and elects a box. The
result is a NEW box, not a trimmed one. So: the vote stage, and the
boxes it produces are VOTED boxes. The old `vote*` names survive in file
names and stored keys and are being retired separately.

WHY THIS LAYER EXISTS (user, 2026-08-08): "after vote box we should
update the whole scene graph, as the new vote box will supersede the old
box — that's the whole point. All info from the vote stage should
also be written into canon graph. We can keep the stale boxes for
reference purposes, but we need to make sure it's explicitly known."

Before this module the vote stage wrote NOTHING into the graph. It
dropped a manifest and a report beside it, `resolved` kept its pre-vote
geometry, and every later module had to know on its own to override that
geometry from the manifest. 43 of 46 resolved boxes disagreed with the
elected one — the glass door was 6.04 m in `resolved` and 0.02 m after
the vote — and nothing anywhere said which was current. That is how a
stale box propagates: not by being wrong, but by being unmarked.

WHAT THIS MODULE DOES — one edit, on the whole graph:

  GETS   graph["resolved"] (the last full layer), the elected boxes
         (scene_manifest_slicevote_preview.json), the vote record
         (vote/slicevote_report.json) and the typed doubts
         (graph/vote_doubts.json).
  WRITES one ADDITIVE layer graph["voted"] = {nodes, edges, nesting,
         edge_meta, run, counts, open_questions} — a WHOLE graph, the
         thing the next stage edits.
  KEEPS  every node property `resolved` had, plus:
           geometry            THE ELECTED BOX (canon from here on)
           geometry_superseded the pre-vote box, kept ON PURPOSE and
                               labelled, so it is reference rather than a
                               second opinion
           vote                the whole vote record for that node —
                               status, tiers, the slice note, how many
                               views voted and how many were needed, the
                               plan-fill numbers, every candidate box
                               (original / strict / vote2 / pano /
                               shipping) and the top-view choice trail
           doubts              the typed open questions, verbatim
           provenance          what this stage did, per node
  NEVER  invents geometry. The elected box is COPIED from the manifest.
         A resolved node the vote never reached keeps its box and is
         listed in `open_questions` as not-voted — never silently passed
         off as elected.

  A MISTAKE looks like: a node silently keeping its pre-vote box while
  the layer claims to be post-vote, an edge left pointing at pre-vote
  geometry, or vote information left behind in a sidecar so a later
  stage has to go looking for it.

Run:  python graph/build_voted.py --scene living_marble          (dry)
      python graph/build_voted.py --scene living_marble --apply
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import paths            # noqa: E402
import edge_carry       # noqa: E402
import scene_state      # noqa: E402

LAYER = "voted"
MANIFEST = "scene_manifest_slicevote_preview.json"
REPORT = Path("vote") / "slicevote_report.json"
GEOM_KEYS = ("aabb_min", "aabb_max", "center", "size")

# the vote record's own fields, lifted onto the node so nothing downstream
# has to open the report to know how the box was decided
VOTE_RULE_KEYS = ("need_votes", "flag", "pano_flag", "outlier", "tiers",
                  "culled_clusters", "shell_ineligible_dots", "plan_fill",
                  "plan_fill2", "slice", "top_frame", "top_shots",
                  "top_choice", "top_choice_overruled_score")
STATUSES = ("voted", "voted_pano", "kept", "kept_wall", "kept_ceiling",
            "kept_outlier")


def load(p, what):
    try:
        return json.loads(Path(p).read_text(encoding="utf-8"))
    except Exception as e:                                  # noqa: BLE001
        raise SystemExit(f"[voted] cannot read {what}: {p}\n    {e}")


def build(scene):
    sd = paths.scene_dir(scene)
    graph = load(sd / "scene_graph.json", "the scene graph")
    if not (graph.get("resolved") or {}).get("nodes"):
        raise SystemExit("[voted] no resolved layer to edit")

    man = load(sd / MANIFEST, "the elected boxes")
    boxes = {o["id"]: o for o in man.get("objects") or []}
    rep = load(sd / REPORT, "the vote record")
    results = rep.get("results") or []
    rec = {r["id"]: r for r in results} if isinstance(results, list) \
        else dict(results)
    # APPEARANCE COMES FORWARD TOO (2026-08-09). J6 described every node
    # -- colours, material, style, a one-line description, what it rests
    # on, which way it faces -- and `resolved` dropped it, so compose's
    # FIRST stage (compose/supported_by.py) had to reach back past the
    # current layer into graph['judged'] to find it. That works only for
    # ids `judged` still has: a split piece the judges CREATED is not
    # there at all, and a merged-away node is gone, so the lookup
    # silently returned {} for exactly the nodes this pipeline changed --
    # and S1 weighs support on that testimony.
    app = {}
    for jn in (graph.get("judged") or {}).get("nodes") or []:
        if jn.get("appearance"):
            app[jn["id"]] = jn["appearance"]
    apf = sd / "graph" / "appearance_cache_v2.json"
    if apf.exists():                      # fallback: J6's own cache
        for nid, ent in (load(apf, "the appearance cache").get("nodes")
                         or {}).items():
            if isinstance(ent, dict) and ent.get("appearance"):
                app.setdefault(nid, ent["appearance"])

    doubts = {}
    dp = sd / "graph" / "vote_doubts.json"
    if dp.exists():
        for nd in load(dp, "the doubts").get("nodes") or []:
            doubts[nd["id"]] = nd.get("doubts") or []

    nodes, opens, stats = [], [], {"voted": 0, "not_voted": 0,
                                   "with_appearance": 0}
    by_status = {}
    for rn in graph["resolved"]["nodes"]:
        nid = rn["id"]
        n = dict(rn)                       # INHERIT everything resolved had
        b = boxes.get(nid)
        r = rec.get(nid) or {}
        rule = r.get("rule") or {}
        status = next((f for f in (b or {}).get("flags") or []
                       if f in STATUSES), None)

        if b is None:
            # the vote never reached this node: it keeps its box, and that
            # is stated rather than implied
            n["provenance"] = [{
                "rule": "not_voted",
                "note": "the vote stage produced no box for this node "
                        "— its PRE-VOTE geometry stands unchanged"}]
            opens.append({"node": nid, "kind": "not_voted",
                          "text": "no elected box; this node's geometry is "
                                  "still the pre-vote one"})
            stats["not_voted"] += 1
            nodes.append(n)
            continue

        # a LIST from the start: a node can lose its box more than once
        # down the chain (elected here, swapped later by J8), and a single
        # slot meant the second edit erased the first
        n["geometry_superseded"] = [{
            "stage": "resolved", "source": "resolved",
            "note": "PRE-VOTE box, kept for reference only. The elected "
                    "box in `geometry` supersedes it — do not read this "
                    "as a second opinion.",
            **{k: rn["geometry"][k] for k in GEOM_KEYS
               if k in rn["geometry"]}}]
        n["geometry"] = {k: b[k] for k in GEOM_KEYS if k in b}
        n["vote"] = {
            "status": status,
            "n_views_voted": r.get("nviews_vote"),
            "candidates": r.get("boxes") or {},
            **{k: rule[k] for k in VOTE_RULE_KEYS if k in rule},
        }
        if doubts.get(nid):
            n["doubts"] = doubts[nid]
        seen = app.get(nid) or next(
            (app[m] for m in (rn.get("members") or []) if m in app), None)
        if seen:
            n["appearance"] = seen
        n["provenance"] = [{
            "rule": "geometry_from_vote",
            "status": status,
            "note": "elected box COPIED VERBATIM from the vote manifest; "
                    "the pre-vote box is kept on the node as "
                    "geometry_superseded"}]
        by_status[status] = by_status.get(status, 0) + 1
        stats["voted"] += 1
        nodes.append(n)

    for nid, ds in doubts.items():
        if nid in {n["id"] for n in nodes}:
            for d in ds:
                if d.get("kind") != "exemption":
                    opens.append({"node": nid, "kind": d.get("kind"),
                                  "text": d.get("text")})

    # the edges follow the nodes. No node was removed or created here, so
    # the remap is empty — but the BOXES all moved, which is exactly the
    # case that needs a re-derive rather than a carried-over edge list.
    edges, nesting, emeta = edge_carry.carry(
        nodes, graph, remap={},
        inherit_from=("judged", "resolved", "voted_edges"),
        diff_against="resolved")   # this layer supersedes resolved

    stats["with_appearance"] = sum(1 for n in nodes
                                   if n.get("appearance"))
    stats.update(nodes=len(nodes), edges=len(edges),
                 by_status=by_status,
                 boxes_changed=sum(
                     1 for n in nodes if n.get("geometry_superseded")
                     and any(abs(a - b) > 0.005 for a, b in zip(
                         n["geometry"]["size"],
                         n["geometry_superseded"][0]["size"]))))
    layer = {
        "built": date.today().isoformat(),
        "built_from": f"graph['resolved'] + {MANIFEST} + {REPORT} + "
                      "graph/vote_doubts.json",
        "supersedes": "resolved",
        "note": "THE SCENE GRAPH AFTER THE BOXES WERE ELECTED. This is a "
                "WHOLE layer, not a sidecar: nodes carry every property "
                "`resolved` had plus the elected box, the vote record and "
                "the typed doubts, and the edges are re-derived on the new "
                "boxes. Each node's PRE-VOTE box is kept as "
                "`geometry_superseded` — reference, explicitly not canon. "
                "graph['resolved'] is unchanged and is now SUPERSEDED for "
                "geometry.",
        "run": (man.get("run_id") and {
            "run_id": man.get("run_id"), "run_at": man.get("run_at"),
            "params_hash": man.get("params_hash"),
            "source_sha": man.get("source_sha"),
            "canon_eligible": man.get("canon_eligible")}) or {},
        "nodes": nodes,
        "edges": edges,
        "nesting": nesting,
        "edge_meta": emeta,
        "open_questions": opens,
        "counts": stats,
    }
    return graph, layer, sd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="write graph['voted'] (ADDITIVE); without it "
                         "NOTHING is written")
    a = ap.parse_args()
    graph, layer, sd = build(a.scene)
    c, em = layer["counts"], layer["edge_meta"]

    print(f"[voted] {a.scene}: {c['nodes']} nodes "
          f"({c['voted']} elected, {c['not_voted']} not voted), "
          f"{c['boxes_changed']} boxes changed vs pre-vote")
    print(f"[voted] statuses: {c['by_status']}")
    print(f"[voted] nodes carrying a J6 appearance: "
          f"{c['with_appearance']}/{c['nodes']}")
    print(f"[voted] edges: {em.get('n_out')} "
          f"(+{len(em.get('appeared') or [])} / "
          f"-{len(em.get('dissolved') or [])}), judge fields grafted "
          f"{em.get('judge_fields_grafted')}, unplaced "
          f"{len(em.get('judge_fields_unplaced') or [])}, consumed "
          f"{len(em.get('judged_edges_consumed_by_a_merge') or [])}, lost "
          f"{len(em.get('judged_edges_lost_to_node_removal') or [])}")
    sc = em.get("self_check") or {}
    print(f"[voted] self-check: {'PASS' if sc.get('passed') else 'FAIL'}")
    for d in sc.get("details") or []:
        print(f"           {d['rule']} -> {d['passed']}")
    print(f"[voted] open questions: {len(layer['open_questions'])}")

    if not a.apply:
        print("[voted] DRY -- nothing written (rerun with --apply)")
        return
    before = {k: v for k, v in graph.items() if k != LAYER}
    graph[LAYER] = layer
    scene_state.stamp(graph, LAYER)   # declare it IN THE FILE
    p = sd / "scene_graph.json"
    p.write_text(json.dumps(graph, indent=1), encoding="utf-8")
    after = json.loads(p.read_text(encoding="utf-8"))
    changed = [k for k in set(before) | (set(after) - {LAYER})
               if k != "layer"
               if json.dumps(before.get(k), sort_keys=True)
               != json.dumps(after.get(k), sort_keys=True)]
    print(f"[voted] wrote graph['{LAYER}'] into {p}")
    print(f"[voted] additive check: "
          f"{'PASS' if not changed else 'FAIL ' + str(changed)} -- "
          f"{len(before)} other top-level blocks compared")


if __name__ == "__main__":
    main()
