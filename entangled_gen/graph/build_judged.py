"""
Pass 2 -- JUDGE, sub-pass J2: the JUDGED VIEW (deterministic, zero LLM).

Applies the pair verdicts (judge_pairs.py) and floater verdicts
(judge_near.py) to the record and writes the result as graph["judged"]
inside scene_graph.json -- one file, record + verdicts + derived view
(PLAN_SCENE_GRAPH.md 0a.4: two canonical files would drift). The record
nodes/edges are NEVER touched; delete graph["judged"] and this module
rebuilds it identically from record + verdicts.

WHAT IT DOES (all pure code -- merging/renaming were decided by the
judges, materializing them is arithmetic):

  1. Union-find over SAME verdicts on SAME_CANDIDATE edges -> merge
     clusters (transitive: the rug/mat/yoga-mat triple collapses to one
     node). Cluster id = the lowest member id. Merged geometry = union
     AABB; label multiset = union of member multisets; evidence = all
     members' evidence pointers.
  2. DISTINCT -> edge dropped (spatial relations live in the record's
     IN/ON/ATTACHED edges). UNJUDGED SAME_CANDIDATE edges are carried
     over as-is (conservative). PART_OF verdicts RETIRED 08-01 (judge
     v2: fragments are SAME, contents DISTINCT); a stale one aborts the
     build with a re-judge instruction.
  3. Record edges remapped to cluster ids; intra-cluster edges vanish;
     duplicates after remap collapse (ON keeps the smallest |gap| per
     (a, b); a cluster supported by TWO different surfaces keeps both,
     flagged "support_conflict" -- coherence-judge food, not an error).
  4. NEAR edges with a judge_near verdict materialize as their resolved
     relation (ON / IN_WALL / ATTACHED) carrying the verdict provenance;
     unresolved NEAR stays NEAR.
  5. The NAMING QUEUE: every cluster whose members disagree on the label
     (>1 distinct label) -- judge_names.py (J3) consumes it. Until J3
     writes a canonical name, the cluster's name = highest-peak-score
     member label with name_provisional: true (the R9 lamp lesson:
     detector score is NOT trusted as the final word).
  6. Self-checks (exit 1 on failure): every detection cluster holds >= 1
     structural edge (the no-floater invariant survives the merge);
     cluster membership is a partition (each det node in exactly one).

Run:  python graph/build_judged.py --scene bedroom_marble
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402
# the record's own calibrated thresholds -- re-derivation must match them
from build_edges import (TOL_ON_AIR, TOL_ON_PEN, FLOOR_TOL,  # noqa: E402
                         MIN_FOOT_OVERLAP, xz_overlap_area, h)

STRUCT = ("ON", "IN", "IN_WALL", "ATTACHED")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    args = ap.parse_args()
    gpath = paths.scene_dir(args.scene) / "scene_graph.json"
    graph = json.loads(gpath.read_text())
    det = {n["id"]: n for n in graph["nodes"] if n["source"] == "detection"}
    env = [n for n in graph["nodes"] if n["source"] == "envelope"]

    # ---- 1. union-find over SAME verdicts ----
    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    sc_edges = [e for e in graph["edges"] if e["type"] == "SAME_CANDIDATE"]
    applied, dropped, open_pairs = [], [], []
    for e in sc_edges:
        v = e.get("verdict", {})
        verdict = v.get("verdict")
        if verdict == "SAME":
            ra, rb = find(e["a"]), find(e["b"])
            if ra != rb:
                parent[max(ra, rb)] = min(ra, rb)
            applied.append((e["a"], e["b"]))
        elif verdict == "PART_OF":
            # verdict retired 08-01 (judge_pairs v2: fragments are SAME,
            # contents DISTINCT) -- a PART_OF here means stale v1 verdicts:
            # re-run judge_pairs before building the judged layer
            raise SystemExit(
                f"[judged] stale PART_OF verdict on {e['a']}|{e['b']} -- "
                "the verdict menu retired PART_OF (08-01); re-run "
                "graph/judge_pairs.py (prompt v2 re-judges from cache) "
                "and rebuild")
        elif verdict == "DISTINCT":
            dropped.append((e["a"], e["b"]))
        else:
            open_pairs.append(e)      # unjudged -- carried, conservative

    cl = {nid: find(nid) for nid in det}
    members = {}
    for nid, root in cl.items():
        members.setdefault(root, []).append(nid)

    # ---- clusters -> judged nodes ----
    jnodes = {}
    naming_queue = []
    for root, mids in sorted(members.items()):
        mids.sort()
        ns = [det[m] for m in mids]
        amin = [min(n["geometry"]["aabb_min"][k] for n in ns)
                for k in range(3)]
        amax = [max(n["geometry"]["aabb_max"][k] for n in ns)
                for k in range(3)]
        labels = []
        for n in ns:
            labels += n["labels"]
        distinct = sorted({l["label"] for l in labels})
        best = max(ns, key=lambda n: n["provenance"].get("peak_score", 0))
        jn = {"id": root, "members": mids,
              "name": best["label"],
              "name_provisional": len(distinct) > 1,
              "distinct_labels": distinct,
              "geometry": {"aabb_min": [round(v, 3) for v in amin],
                           "aabb_max": [round(v, 3) for v in amax],
                           "center": [round((a + b) / 2, 3)
                                      for a, b in zip(amin, amax)],
                           "size": [round(b - a, 3)
                                    for a, b in zip(amin, amax)]},
              "n_detections": sum(n["evidence"].get("n_detections", 0)
                                  for n in ns),
              "peak_score": best["provenance"].get("peak_score", 0)}
        if len(mids) > 1:
            jn["merged_by"] = "judge_pairs"
        jnodes[root] = jn
        if len(distinct) > 1:
            naming_queue.append(root)

    # ---- edges: remap, dedupe, materialize verdicts ----
    def cid(x):
        return cl.get(x, x)           # envelope ids map to themselves

    jedges = []
    seen = {}                         # (type, a, b) -> index in jedges
    for e in graph["edges"]:
        t = e["type"]
        if t == "SAME_CANDIDATE":
            continue                  # handled below
        a, b = cid(e["a"]), cid(e["b"])
        if a == b:
            continue                  # became internal to a cluster
        ev = dict(e["evidence"])
        caveats = list(e.get("caveats", []))
        extra = {}
        if t == "NEAR":
            v = e.get("verdict")
            if v and v.get("relation") in ("ON", "IN_WALL", "ATTACHED"):
                t = v["relation"]
                b = cid(v["target"])
                # evidence must be the CHOSEN candidate's numbers, not
                # the geometrically-nearest one's (the 07-26 coherence
                # recheck caught the mismatch: "monitor ON desk, gap
                # +0.00" while the true desk gap was 0.185)
                if v["target"] != e["b"]:
                    alt = next((a for a in ev.get("alternatives", [])
                                if a["target"] == v["target"]), None)
                    if alt:
                        ev = {k: val for k, val in alt.items()
                              if k != "target"}
                ev["near_fallback_origin"] = True
                caveats = [c for c in caveats
                           if not c.startswith("fallback_connection")]
                extra = {"resolved_by": "judge_near",
                         "verdict": {k: v[k] for k in
                                     ("box_underreach", "confidence",
                                      "reason", "model", "date")}}
            else:
                extra = {"status": "unresolved"}
        key = (t, a, b)
        if key in seen:
            prev = jedges[seen[key]]
            if (t == "ON" and abs(ev.get("gap_m", 9)) <
                    abs(prev["evidence"].get("gap_m", 9))):
                prev["evidence"] = ev  # keep the tighter contact numbers
            prev.setdefault("merged_from_duplicates", 0)
            prev["merged_from_duplicates"] += 1
            continue
        seen[key] = len(jedges)
        jedges.append({"type": t, "a": a, "b": b, "evidence": ev,
                       "caveats": caveats, **extra})

    for e in open_pairs:              # unjudged pairs stay visible
        jedges.append({"type": "SAME_CANDIDATE", "a": cid(e["a"]),
                       "b": cid(e["b"]), "evidence": dict(e["evidence"]),
                       "caveats": ["unjudged -- carried from the record"],
                       "status": "open"})

    # multiple ON supporters per cluster -> flag, keep both
    on_by_a = {}
    for e in jedges:
        if e["type"] == "ON":
            on_by_a.setdefault(e["a"], []).append(e)
    support_conflicts = []
    for a, es in on_by_a.items():
        if len(es) > 1:
            for e in es:
                e.setdefault("caveats", []).append(
                    "support_conflict -- cluster members rested on "
                    "different surfaces; for the coherence judge")
            support_conflicts.append(
                {"cluster": a, "supporters": [e["b"] for e in es]})

    # ---- re-derive support for clusters the merge left edge-less ----
    # (e.g. the mat triple: every member's ON pointed at a duplicate twin,
    # all internal after the merge). Same thresholds as the record.
    floor_y = next(n for n in env if n["id"] == "arch_floor")[
        "geometry"]["plane"]["value_raw"]
    conn0 = set()
    for e in jedges:
        if e["type"] in STRUCT or e["type"] == "NEAR":
            conn0.add(e["a"])
            conn0.add(e["b"])
    rederived = []
    for r in sorted(jnodes):
        if r in conn0:
            continue
        g = jnodes[r]["geometry"]
        bottom_h = h(g["aabb_max"][1])
        foot = g["size"][0] * g["size"][2]
        best = None
        for r2, jn2 in jnodes.items():
            if r2 == r:
                continue
            gap = bottom_h - h(jn2["geometry"]["aabb_min"][1])
            if not (-TOL_ON_PEN <= gap <= TOL_ON_AIR):
                continue
            frac = (xz_overlap_area(g, jn2["geometry"]) / foot
                    if foot > 0 else 0.0)
            if frac < MIN_FOOT_OVERLAP:
                continue
            cand = (abs(gap), -frac, gap, r2)
            if best is None or cand < best:
                best = cand
        if best is not None:
            _, negfrac, gap, r2 = best
            edge = {"type": "ON", "a": r, "b": r2,
                    "evidence": {"gap_m": round(gap, 3),
                                 "overlap_frac_of_a": round(-negfrac, 3),
                                 "supporter": "object"},
                    "caveats": [], "rederived_after_merge": True}
        else:
            gap_floor = floor_y - g["aabb_max"][1]
            straddle = gap_floor < 0 and h(g["center"][1]) > h(floor_y)
            if gap_floor <= FLOOR_TOL and (gap_floor >= -FLOOR_TOL
                                           or straddle):
                edge = {"type": "ON", "a": r, "b": "arch_floor",
                        "evidence": {"gap_m": round(gap_floor, 3),
                                     "straddles_floor": straddle,
                                     "supporter": "floor"},
                        "caveats": [], "rederived_after_merge": True}
            else:                     # honest fallback, judge/coherence food
                edge = {"type": "NEAR", "a": r, "b": "arch_floor",
                        "evidence": {"relation_hint": "floor",
                                     "gap_m": round(gap_floor, 3)},
                        "caveats": ["fallback after merge re-derivation"],
                        "status": "unresolved",
                        "rederived_after_merge": True}
        jedges.append(edge)
        rederived.append({"cluster": r, "edge": edge["type"],
                          "target": edge["b"],
                          "evidence": edge["evidence"]})

    # ---- self-checks ----
    checks, ok = [], True
    assigned = [m for ms in members.values() for m in ms]
    partition_ok = sorted(assigned) == sorted(det)
    ok &= partition_ok
    checks.append({"rule": "cluster membership is a partition of the "
                           "detection nodes", "passed": partition_ok})
    conn = set()
    for e in jedges:
        if e["type"] in STRUCT or (e["type"] == "NEAR"):
            conn.add(e["a"])
            conn.add(e["b"])
    iso = [r for r in jnodes if r not in conn]
    ok &= not iso
    checks.append({"rule": "no-floater invariant survives the merge",
                   "isolated": iso, "passed": not iso})

    counts = {}
    for e in jedges:
        counts[e["type"]] = counts.get(e["type"], 0) + 1

    graph["judged"] = {
        "built": date.today().isoformat(),
        "built_from": {"pair_verdicts": len(applied)
                       + len(dropped), "near_verdicts":
                       sum(1 for e in graph["edges"] if e["type"] == "NEAR"
                           and "verdict" in e)},
        "nodes": [jnodes[r] for r in sorted(jnodes)],
        "arch_nodes": [n["id"] for n in env],
        "edges": jedges,
        "merge_clusters": [{"id": r, "members": m, "labels":
                            jnodes[r]["distinct_labels"]}
                           for r, m in sorted(members.items())
                           if len(m) > 1],
        "naming_queue": naming_queue,
        "support_conflicts": support_conflicts,
        "rederived_after_merge": rederived,
        "edge_counts": counts,
        "self_check": {"passed": bool(ok), "details": checks},
    }
    gpath.write_text(json.dumps(graph, indent=1))

    print(f"[judged] wrote graph['judged'] in {gpath}")
    print(f"[judged] {len(det)} detection nodes -> {len(jnodes)} clusters "
          f"({len(graph['judged']['merge_clusters'])} merged, "
          f"{len(dropped)} distinct, "
          f"{len(open_pairs)} unjudged carried)")
    for c in graph["judged"]["merge_clusters"]:
        print(f"           {c['id']} <= {'+'.join(c['members'])} "
              f"{c['labels']}")
    print(f"[judged] edge counts: {counts}")
    print(f"[judged] naming queue ({len(naming_queue)}): "
          f"{[(r, jnodes[r]['distinct_labels']) for r in naming_queue]}")
    if support_conflicts:
        print(f"[judged] support conflicts: {support_conflicts}")
    if rederived:
        print(f"[judged] support re-derived after merge: {rederived}")
    print(f"[judged] SELF-CHECK: {'PASS' if ok else '*** FAIL ***'}")
    for c in checks:
        print(f"           {c}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
