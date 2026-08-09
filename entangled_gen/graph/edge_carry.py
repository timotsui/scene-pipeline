"""THE EDGES FOLLOW THE NODES — one definition, shared by every stage
that edits the scene graph.

USER DESIGN RULE (2026-08-08): "each module is an edit on the scene
graph, and it has to inherit all the properties and information. only
modify, add, edit, delete etc. but overall structure should be the
same." A stage therefore hands on a WHOLE graph, and its edges have to
survive whatever it did to the nodes.

THE SPLIT, and why it is not a compromise:

  RE-DERIVE the geometry.  Every edge type this pipeline has (IN, ON,
  NEAR, IN_WALL, ATTACHED, INTERPENETRATES, SAME_CANDIDATE) is a claim
  about boxes. Once a box moves, the old claim is about geometry that no
  longer exists — "if it inherits but its wrong then its not right"
  (user). And a moved box can form edges with nodes it NEVER touched, so
  re-checking only its former neighbours cannot be correct: obj_021 grew
  0.42 -> 0.61 m in a J8 swap and now INTERPENETRATES the desk, having
  previously had a single NEAR edge to the floor. The full pass is 45
  nodes = 990 pairs = ~5 ms and no model calls, so there is nothing to
  optimise for.

  INHERIT the judgements.  What geometry can never regenerate is what a
  judge wrote ONTO an edge: J0's nomination (`nominated_by`, `triage`),
  J1's ruling (`status`, `verdict`) and J6's edge re-examination
  (`confidence`, `was`, `true_arrangement`, `suspect_box`, `source`).
  Those are carried across, re-pointed through the caller's own node
  edits, and grafted back onto the surviving edges.

  RECORD what cannot land.  Three ways a judgement can fail to reattach,
  none of them silent: `unplaced` (the geometry moved out from under it),
  `consumed` (both endpoints re-point to the same node — what a J1 SAME
  verdict looks like AFTER its own merge has been applied; skipping this
  case silently discarded the verdict that deleted the node, found
  2026-08-08) and `lost` (an endpoint was removed with no replacement).

INHERIT FROM EVERY PREVIOUS EDGE SET, not just the newest one. J6's edge
fields live on `resolved.edges`; `voted_edges` was derived later and had
already dropped them, so inheriting only from the newest layer lost 5
fields on 2 edges. Sources are unioned, earlier ones filling gaps the
later ones do not have.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from build_edges import derive_edges  # noqa: E402

# what a judge writes onto an edge — geometry cannot regenerate any of it
JUDGE_FIELDS = ("status", "verdict", "nominated_by", "triage",
                "confidence", "was", "true_arrangement", "suspect_box",
                "source")



def _overlap_facts(ga, gb):
    """iou / containment on the CURRENT boxes, so a carried judge edge
    never keeps stale numbers. Empty when either box is missing."""
    if not ga or not gb:
        return {}
    lo_a, hi_a = ga.get("aabb_min"), ga.get("aabb_max")
    lo_b, hi_b = gb.get("aabb_min"), gb.get("aabb_max")
    if not (lo_a and hi_a and lo_b and hi_b):
        return {}
    ov = 1.0
    for k in range(3):
        ov *= max(0.0, min(hi_a[k], hi_b[k]) - max(lo_a[k], lo_b[k]))
    va = 1.0
    vb = 1.0
    for k in range(3):
        va *= max(0.0, hi_a[k] - lo_a[k])
        vb *= max(0.0, hi_b[k] - lo_b[k])
    if va <= 0 or vb <= 0:
        return {}
    den = va + vb - ov
    return {"iou": round(ov / den, 3) if den > 0 else 0.0,
            "containment": round(ov / min(va, vb), 3),
            "refreshed_on": "this layer's boxes"}


def carry(nodes, graph, remap, inherit_from=("resolved", "voted_edges"),
          diff_against=None):
    """Re-derive this node set's edges and re-attach the judgements.

    nodes        the stage's OUTPUT nodes: [{id, name, geometry, members}]
    graph        the whole scene graph (envelope nodes + the edge sets to
                 inherit from live here)
    remap        {removed id: [live ids that replace it]} — the caller's
                 own node edits, so a merge survivor or a split piece
                 keeps what pointed at its predecessor
    inherit_from graph block names holding edge lists, oldest first

    Returns (edges, nesting, meta). Never raises on a scene with no
    envelope: it returns empty edges and says so in meta.
    """
    live = {n["id"] for n in nodes} | {
        n["id"] for n in graph.get("nodes") or []
        if n.get("source") == "envelope"}

    def resolve(i):
        if i in live:
            return [i]
        seen, out, stack = set(), [], [i]
        while stack:                       # merges can chain
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            for nxt in remap.get(cur, []):
                (out if nxt in live else stack).append(nxt)
        return out

    # ---- inherit the judgements, re-pointed ---------------------------
    carried, lost, consumed, sources = {}, [], [], []
    for block in inherit_from:
        edges = (graph.get(block) or {}).get("edges") or []
        if not edges:
            continue
        sources.append({"block": block, "n_edges": len(edges)})
        for e in edges:
            payload = {k: e[k] for k in JUDGE_FIELDS if e.get(k)}
            if not payload:
                continue
            aa, bb = resolve(e["a"]), resolve(e["b"])
            if not aa or not bb:
                lost.append({**e, "from_block": block,
                             "why": "an endpoint was removed and has no "
                                    "live replacement"})
                continue
            for a2 in aa:
                for b2 in bb:
                    if a2 == b2:
                        consumed.append({**e, "from_block": block,
                                         "became": a2,
                                         "why": "both endpoints are now "
                                                "the same node — this "
                                                "verdict has already been "
                                                "applied"})
                        continue
                    # earlier sources fill gaps, never overwrite newer
                    slot = carried.setdefault((e["type"], a2, b2), {})
                    for k, v in payload.items():
                        slot.setdefault(k, v)

    # ---- re-derive the geometry ---------------------------------------
    env = {n["id"]: n for n in (graph.get("nodes") or [])
           if n.get("source") == "envelope"}
    if "arch_floor" not in env or "arch_ceiling" not in env:
        return [], {}, {"status": "NOT DERIVED — the scene has no "
                                  "arch_floor / arch_ceiling envelope "
                                  "nodes"}
    rec = {n["id"]: n for n in (graph.get("nodes") or [])}
    res_src = {n["id"]: (n.get("members") or [n["id"]])
               for n in (graph.get("resolved") or {}).get("nodes") or []}
    det = []
    for n in nodes:
        if not n.get("geometry"):
            continue
        # NEAR reads detection-level truncation facts, so walk down to the
        # RECORD nodes: a node's members are resolved ids, a resolved
        # node's are record ids. One hop is not enough for a split piece.
        members = []
        for rid in (n.get("members") or [n["id"]]):
            for sid in res_src.get(rid, [rid]):
                m = rec.get(sid)
                if m:
                    members += ((m.get("evidence") or {})
                                .get("members") or [])
        det.append({"id": n["id"], "source": "detection",
                    "label": n.get("name") or "",
                    "geometry": n["geometry"],
                    "evidence": {"members": members}})

    walls = {i: n["geometry"]["plane"] for i, n in env.items()
             if i.startswith("arch_wall")
             and n["geometry"].get("plane", {}).get("axis") in ("x", "z")}
    d = derive_edges(det, env,
                     env["arch_floor"]["geometry"]["plane"]["value_raw"],
                     env["arch_ceiling"]["geometry"]["plane"]["value_raw"],
                     walls)

    # ---- graft the judgements back on ---------------------------------
    out, grafted = [], 0
    for e in d.edges:
        key = (e["type"], e["a"], e["b"])
        if key in carried:
            e = {**e, **carried[key]}
            grafted += 1
        out.append(e)

    # ---- edges a JUDGE CREATED, which no re-derivation can produce ----
    # J0 (graph/triage_pairs.py) nominates pairs whose IoU sits BELOW the
    # geometric SAME_CANDIDATE gate and adds its own edge, marked
    # zone="semantic" and nominated_by="triage". Re-deriving geometry
    # cannot regenerate those — the whole point is that geometry did not
    # ask for them — so they must be carried across as WHOLE EDGES, not
    # merely as fields grafted onto an edge that will not exist. Dropping
    # one silently loses J1's merge input: the obj_068/obj_020 chair
    # duplicate rides on exactly such an edge (iou 0.387, gate 0.40).
    # The test is provenance, not a type list: `nominated_by` means a
    # module put this edge here.
    geo = {(e["type"], e["a"], e["b"]) for e in out}
    boxes = {n["id"]: n.get("geometry") for n in nodes}
    boxes.update({n["id"]: n.get("geometry")
                  for n in (graph.get("nodes") or [])
                  if n.get("source") == "envelope"})
    judge_made = []
    for block in inherit_from:
        for e in (graph.get(block) or {}).get("edges") or []:
            if not e.get("nominated_by"):
                continue
            for a2 in resolve(e["a"]):
                for b2 in resolve(e["b"]):
                    if a2 == b2 or (e["type"], a2, b2) in geo:
                        continue
                    ne = {**e, "a": a2, "b": b2}
                    ev = dict(ne.get("evidence") or {})
                    ev.update(_overlap_facts(boxes.get(a2), boxes.get(b2)))
                    ne["evidence"] = ev
                    ne["carried"] = {
                        "from_block": block,
                        "why": "created by a judge, not by geometry — "
                               "re-derivation cannot produce it, so the "
                               "edge is carried whole and its overlap "
                               "numbers refreshed on the new boxes"}
                    out.append(ne)
                    geo.add((e["type"], a2, b2))
                    judge_made.append([e["type"], a2, b2])
    # The diff is against the ONE layer this edit supersedes — not the
    # union of everything inherited from. Unioning made "appeared" read 0
    # and "dissolved" 47 on a layer that barely changed, because the union
    # of three older edge sets is naturally a superset (caught 2026-08-08).
    base = diff_against or (inherit_from[-1] if inherit_from else None)
    before = {(e["type"], e["a"], e["b"])
              for e in ((graph.get(base) or {}).get("edges") or [])}
    after = {(e["type"], e["a"], e["b"]) for e in out}
    meta = {
        "inherited_from": sources,
        "diff_against": base,
        "note": "GEOMETRIC edges re-derived on THIS layer's boxes "
                "(build_edges.derive_edges — identical thresholds); judge "
                "fields (" + ", ".join(JUDGE_FIELDS) + ") inherited and "
                "grafted back, because geometry cannot regenerate them.",
        "n_out": len(out),
        "appeared": [list(k) for k in sorted(after - before)],
        "dissolved": [list(k) for k in sorted(before - after)],
        "judge_fields_grafted": grafted,
        "judge_fields_unplaced": [{"edge": list(k), **v}
                                  for k, v in carried.items()
                                  if k not in after],
        "judged_edges_consumed_by_a_merge": consumed,
        "judged_edges_lost_to_node_removal": lost,
        "judge_created_edges_carried": judge_made,
        "summary": d.edge_summary,
        "self_check": d.self_check,
    }
    return out, d.nesting, meta
