"""Phase C -- MATERIALIZE the carve: ONE proposed node set from the
resolved layer plus EVERY verdict the carve loop produced.

Contract (docs/PLAN_CARVE_DOWNSTREAM.md, Phase C):
  GETS   graph["resolved"] (identity canon) + the carve's SHIPPING boxes
         (scene_manifest_slicevote_preview.json) + the four verdict
         sidecars (J8 graph/multiplicity.json, J8s graph/split_cuts.json,
         J9 graph/same_product.json, graph/carve_doubts.json) + the J1
         SAME verdicts riding on graph["carved_edges"] SAME_CANDIDATE
         edges.
  WRITES one ADDITIVE layer graph["carved"] = {nodes, dropped, conflicts,
         open_questions, counts, provenance per node}. It NEVER touches
         graph[nodes|edges|judged|resolved|carve|carved_edges], the carve
         outputs, or any sidecar -- and it verifies that by diffing every
         other top-level key before/after the write.
  A MISTAKE looks like: a silently recomputed box (boxes are COPIED, never
         derived), a rule quietly overruling another instead of landing in
         `conflicts`, or a dropped piece growing the neighbour it points at.

PRECEDENCE -- the rules are applied in this order and every rule that
fires is recorded on the node's `provenance` list:

  1. GEOMETRY BASE. Each resolved node takes its carve SHIPPING box
     VERBATIM from the preview manifest (aabb_min/aabb_max/center/size
     copied, never recomputed). A resolved node with no manifest entry
     keeps its resolved box and is recorded
     (rule `geometry_base_resolved_fallback`) + listed as an open
     question.
  2. J8 BOX RULING (ONE_BOX cases only).
       ship_vote        -> the carve report's boxes.vote2 for that node
                           (rule `j8_box_swap_vote2`).
       ship_pano|either -> the shipping box stands unchanged
                           (rule `j8_box_ruling_noop`).
     A CARVE-EXEMPT node has neither a vote2 nor a pano box (its report
     entry only carries original/rebox/shipping), so a ruling on it is a
     NO-OP: it is recorded as `j8_ruling_not_applicable` -- never as a
     ruling that applied -- and raised as an open question.
     A ship_pano ruling whose pano box differs from the shipping box is
     a CONFLICT (two claims about which box ships), never silently
     resolved.
     UNCLEAR -> the node ships unchanged (`j8_unclear_ship_unchanged`)
     and the doubt stays open (rule 6).
  3. J8s SPLIT PIECES.
       resolution `split_chain`      -> the case node is REPLACED by its
           final KEPT pieces, ids `<nid>#1`, `<nid>#2`, ... Each piece
           carries its owner, its box (verbatim from the cut record) and
           the round provenance string. A piece owned by `existing:<id>`
           does NOT create a node: it is DROPPED with a note pointing at
           that node, because its content is already represented there.
           CRITICAL (plan rule): a dropped / not-this-object piece NEVER
           grows the named neighbour's box -- the neighbour is only
           ANNOTATED (`represents_dropped_piece`), its geometry untouched.
       resolution `covered_by_existing` -> the node is dropped entirely,
           the owner list recorded, the owners annotated the same way
           (again: no box growth).
  4. J1 SAME MERGES. Every SAME_CANDIDATE edge in graph["carved_edges"]
     with verdict SAME merges its pair: the SMALLER-VOLUME node is
     removed and its id lands on the survivor as `merged_from`. Chains
     resolve transitively (connected components; survivor = the largest
     carved volume in the component, ties broken lexicographically and
     recorded). The survivor's BOX IS NOT UNIONED -- it keeps its carved
     box verbatim; only identity bookkeeping moves.
  5. J9 SAME-PRODUCT. Every group with same_object true annotates each of
     its set members with {product_group, canonical_size}. NO BOX IS
     RESIZED: the canonical size is SHOPPING's input, an annotation only
     (open decision 3 in the plan: per-node boxes stay honest).
  6. UNCLEAR / OPEN DOUBTS. A node whose J8 outcome is UNCLEAR, or which
     still carries unresolved carve doubts, ships UNCHANGED and is listed
     in open_questions. A doubt counts as CLOSED only when the node got a
     J8 verdict other than UNCLEAR and the doubt's kind is one J8 is
     asked about (J8_ADMITTING); `exemption` doubts are provenance, not
     questions; everything else (e.g. slice_fallback) stays open.

CONFLICTS. When two rules make disagreeing claims about the same node
(a merge whose partner a split already removed, a J9 set member that no
longer exists, a piece pointing at a node nothing kept, a node that
represents dropped content and is then merged away, a ship_pano ruling
contradicted by the shipped geometry, or a pair J1 merged as ONE OBJECT
that J9 ruled NOT the same product), BOTH claims land in `conflicts` with
their rules. Nothing is silently resolved.

NOT IN THIS PASS (honest scope): edges are NOT re-derived here. The plan's
Phase C also calls for a mechanical edge rebuild on the materialized
geometry and a targeted appearance pass for the nodes splits created;
this trial builds the NODE SET only, and both are listed as open
questions on the report.

Run:
  python graph/materialize_carve.py --scene living_marble
  python graph/materialize_carve.py --scene living_marble --report-only
  python graph/materialize_carve.py --scene living_marble --apply
"""
import argparse
import html
import json
import re
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import paths          # noqa: E402

CARVED_MANIFEST = "scene_manifest_slicevote_preview.json"
CARVE_REPORT = Path("pool_retake") / "slicevote_report.json"
GEOM_KEYS = ("aabb_min", "aabb_max", "center", "size")
LAYER = "carved"

# doubt kinds J8 is actually asked about -- a non-UNCLEAR J8 verdict
# closes these and only these; `exemption` is provenance, not a question
J8_ADMITTING = ("pano_vs_cluster", "culled_clusters", "low_plan_fill",
                "large_empty_notch", "rebox_rejected_smaller",
                "rebox_truncated")
INFORMATIONAL_DOUBTS = ("exemption",)


# --------------------------------------------------------------------------
# small geometry helpers -- COPY boxes, never recompute a carve number
# --------------------------------------------------------------------------

def geom_from_lohi(lo, hi, ndigits=3):
    """A node geometry block from a report/cut box. lo/hi are copied
    verbatim; center/size are the two derived conveniences every other
    layer carries (rounded like the manifest's own)."""
    lo, hi = list(lo), list(hi)
    return {"aabb_min": lo, "aabb_max": hi,
            "center": [round((lo[i] + hi[i]) / 2, ndigits) for i in range(3)],
            "size": [round(hi[i] - lo[i], ndigits) for i in range(3)]}


def volume(g):
    return max(0.0, (g["aabb_max"][0] - g["aabb_min"][0])
               * (g["aabb_max"][1] - g["aabb_min"][1])
               * (g["aabb_max"][2] - g["aabb_min"][2]))


def same_box(g, lo, hi, tol=1e-6):
    return all(abs(g["aabb_min"][i] - lo[i]) <= tol
               and abs(g["aabb_max"][i] - hi[i]) <= tol for i in range(3))


def size_str(g):
    return "x".join(f"{v:.2f}" for v in g["size"])


# --------------------------------------------------------------------------
# inputs
# --------------------------------------------------------------------------

def load_json(p, what, required=True):
    if not p.exists():
        if required:
            raise SystemExit(f"[materialize] missing {what}: {p}")
        return None
    return json.loads(p.read_text(encoding="utf-8"))


def carve_report_boxes(sdir, graph):
    """{id: {box_name: {lo,hi}}} from the carve's own report (the only
    place vote2 lives). Preferred location is the scene's pool_retake/;
    the carve block's recorded absolute built_from is the fallback."""
    p = sdir / CARVE_REPORT
    if not p.exists():
        rec = (graph.get("carve") or {}).get("built_from")
        if rec and Path(rec).exists():
            p = Path(rec)
    rep = load_json(p, "carve report (slicevote_report.json)")
    return ({r["id"]: (r.get("boxes") or {}) for r in rep["results"]},
            str(p))


def same_verdict_pairs(graph):
    """SAME_CANDIDATE edges of graph['carved_edges'] whose J1 verdict is
    SAME. Returns [(a, b, verdict)]."""
    layer = graph.get("carved_edges") or {}
    out = []
    for e in layer.get("edges", []):
        if e.get("type") != "SAME_CANDIDATE":
            continue
        v = e.get("verdict") or {}
        if str(v.get("verdict", "")).upper() == "SAME":
            out.append((e["a"], e["b"], v))
    return out


def doubts_by_node(sdir, graph):
    """{id: [doubt]} -- the carve's typed doubts. carve_doubts.json is
    the sidecar; graph['carve']['nodes'] is the same content folded in."""
    p = sdir / "graph" / "carve_doubts.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        return {n["id"]: n.get("doubts") or [] for n in d.get("nodes", [])}
    return {i: n.get("doubts") or []
            for i, n in ((graph.get("carve") or {}).get("nodes") or {}).items()}


# --------------------------------------------------------------------------
# the pass
# --------------------------------------------------------------------------

class Materialize:
    def __init__(self, scene):
        self.scene = scene
        self.sdir = paths.scene_dir(scene)
        gp = self.sdir / "scene_graph.json"
        self.gpath = gp
        self.graph = load_json(gp, "scene_graph.json")
        if not (self.graph.get("resolved") or {}).get("nodes"):
            raise SystemExit("[materialize] no resolved layer")
        man = load_json(self.sdir / CARVED_MANIFEST, "carve preview manifest")
        self.manifest = {o["id"]: o for o in man["objects"]}
        self.report, self.report_path = carve_report_boxes(self.sdir,
                                                           self.graph)
        gdir = self.sdir / "graph"
        self.mult = load_json(gdir / "multiplicity.json", "J8 verdicts")
        self.cuts = load_json(gdir / "split_cuts.json", "J8s split cuts")
        self.sameprod = load_json(gdir / "same_product.json", "J9 verdicts")
        self.doubts = doubts_by_node(self.sdir, self.graph)

        self.nodes = {}          # id -> proposed node (insertion ordered)
        self.merge_pairs = []
        self.dropped = []
        self.conflicts = []
        self.opens = []
        self.stats = {}

    # -- recording -------------------------------------------------------
    def prov(self, nid, rule, **kw):
        self.nodes[nid]["provenance"].append({"rule": rule, **kw})

    def conflict(self, nid, why, claim_a, claim_b, **kw):
        self.conflicts.append({"node": nid, "why": why,
                               "claim_a": claim_a, "claim_b": claim_b, **kw})

    def open_q(self, nid, kind, text, **kw):
        self.opens.append({"node": nid, "kind": kind, "text": text, **kw})

    def drop(self, nid, rule, why, **kw):
        n = self.nodes.pop(nid)
        self.dropped.append({"id": nid, "name": n["name"], "rule": rule,
                             "why": why,
                             "geometry_was": n["geometry"], **kw})
        return n

    # -- rule 1 ----------------------------------------------------------
    def base_geometry(self):
        fallbacks = 0
        for rn in sorted(self.graph["resolved"]["nodes"], key=lambda n: n["id"]):
            nid = rn["id"]
            mo = self.manifest.get(nid)
            self.nodes[nid] = {
                "id": nid, "name": rn["name"],
                "geometry": None,
                "members": list(rn.get("members") or []),
                "from": "resolved",
                "provenance": [],
            }
            if mo:
                self.nodes[nid]["geometry"] = {k: mo[k] for k in GEOM_KEYS}
                self.prov(nid, "geometry_base_carved",
                          source=CARVED_MANIFEST,
                          carve_status=(mo.get("flags") or [None])[0],
                          note="carve SHIPPING box copied VERBATIM")
            else:
                self.nodes[nid]["geometry"] = dict(rn["geometry"])
                self.prov(nid, "geometry_base_resolved_fallback",
                          note="no entry in the carve preview manifest -- "
                               "the resolved (pre-carve) box stands")
                self.open_q(nid, "uncarved",
                            "node has no carved box; it ships its "
                            "pre-carve resolved geometry")
                fallbacks += 1
        self.stats["base_carved"] = len(self.nodes) - fallbacks
        self.stats["base_resolved_fallback"] = fallbacks

    # -- rule 2 ----------------------------------------------------------
    def box_rulings(self):
        swapped = noop = na = unclear = 0
        for case in (self.mult or {}).get("cases", []):
            nid = case["id"]
            v = case.get("verdict") or {}
            outcome = v.get("outcome")
            if nid not in self.nodes:
                self.conflict(nid, "J8 verdict references a node that is "
                                   "not in the resolved set",
                              {"rule": "j8", "claim": outcome},
                              {"rule": "resolved_layer",
                               "claim": "node absent"})
                continue
            if outcome == "UNCLEAR":
                self.prov(nid, "j8_unclear_ship_unchanged",
                          confidence=v.get("confidence"),
                          reason=v.get("reason"))
                self.open_q(nid, "j8_unclear",
                            "J8 could not decide; shipping default stands",
                            confidence=v.get("confidence"))
                unclear += 1
                continue
            if outcome != "ONE_BOX":
                continue                      # SPLIT -> rule 3
            ruling = v.get("box_ruling")
            boxes = self.report.get(nid) or {}
            if ruling == "ship_vote":
                b = boxes.get("vote2")
                if b:
                    old = self.nodes[nid]["geometry"]
                    new = geom_from_lohi(b["lo"], b["hi"])
                    self.nodes[nid]["geometry"] = new
                    self.prov(nid, "j8_box_swap_vote2",
                              source=str(CARVE_REPORT).replace("\\", "/"),
                              was={"aabb_min": old["aabb_min"],
                                   "aabb_max": old["aabb_max"]},
                              now={"aabb_min": new["aabb_min"],
                                   "aabb_max": new["aabb_max"]},
                              confidence=v.get("confidence"))
                    swapped += 1
                else:
                    self.prov(nid, "j8_ruling_not_applicable",
                              ruling=ruling,
                              available_boxes=sorted(boxes),
                              note="this node has no vote2/pano box (carve"
                                   "-exempt: the carve never sliced it), so "
                                   "the ruling is a NO-OP -- the shipping "
                                   "box stands unchanged")
                    self.open_q(nid, "ruling_not_applicable",
                                f"J8 ruled {ruling} but the carve produced "
                                f"no vote box for this node "
                                f"({', '.join(sorted(boxes)) or 'no boxes'})"
                                f" -- the ruling could not be executed")
                    na += 1
            elif ruling in ("ship_pano", "either"):
                pano = boxes.get("pano")
                if pano is None:
                    self.prov(nid, "j8_ruling_not_applicable", ruling=ruling,
                              available_boxes=sorted(boxes),
                              note="no pano box on record -- NO-OP")
                    self.open_q(nid, "ruling_not_applicable",
                                f"J8 ruled {ruling} but no pano box exists "
                                f"for this node")
                    na += 1
                    continue
                g = self.nodes[nid]["geometry"]
                if not same_box(g, pano["lo"], pano["hi"]):
                    self.conflict(
                        nid, "J8 ruled ship_pano but the shipped carve box "
                             "is not the pano box",
                        {"rule": "j8_box_ruling", "claim": "pano box ships",
                         "box": {"lo": pano["lo"], "hi": pano["hi"]}},
                        {"rule": "geometry_base_carved",
                         "claim": "manifest shipping box",
                         "box": {"lo": g["aabb_min"], "hi": g["aabb_max"]}})
                self.prov(nid, "j8_box_ruling_noop", ruling=ruling,
                          confidence=v.get("confidence"),
                          note="shipping box already IS the ruled box")
                noop += 1
            else:
                self.conflict(nid, "unknown J8 box ruling",
                              {"rule": "j8_box_ruling", "claim": ruling},
                              {"rule": "materialize",
                               "claim": "vocabulary is "
                                        "ship_vote|ship_pano|either"})
        self.stats.update(j8_box_swapped=swapped, j8_box_noop=noop,
                          j8_ruling_not_applicable=na, j8_unclear=unclear)

    # -- rule 3 ----------------------------------------------------------
    def annotate_owner(self, owner_id, src_node, piece_id, kind):
        """A dropped piece / covered case points at an existing node. The
        node is ANNOTATED only -- its box is NEVER grown (plan rule)."""
        if owner_id not in self.nodes:
            self.conflict(owner_id,
                          "a split piece names an owner that is not in the "
                          "proposed node set",
                          {"rule": kind, "claim": f"owns content of "
                                                  f"{src_node} {piece_id}"},
                          {"rule": "materialize",
                           "claim": "owner node dropped or never existed"})
            return
        self.nodes[owner_id].setdefault("represents_dropped_pieces", []).append(
            {"from_node": src_node, "piece": piece_id, "rule": kind})
        self.prov(owner_id, "represents_dropped_piece",
                  from_node=src_node, piece=piece_id, via=kind,
                  note="ANNOTATION ONLY -- this node's box is NOT grown "
                       "(plan rule: a dropped piece never grows the named "
                       "neighbour's box)")

    def splits(self):
        made = dropped_pieces = covered = replaced = discarded = 0
        for case in (self.cuts or {}).get("cases", []):
            nid = case["id"]
            res = case.get("resolution")
            if nid not in self.nodes:
                self.conflict(nid, "J8s case references a node that is not "
                                   "in the proposed set",
                              {"rule": "j8s", "claim": res},
                              {"rule": "materialize", "claim": "node absent"})
                continue
            prior = [p["rule"] for p in self.nodes[nid]["provenance"]]
            if "j8_box_swap_vote2" in prior:
                self.conflict(nid, "node carries both a J8 ONE_BOX box swap "
                                   "and a J8s split",
                              {"rule": "j8_box_swap_vote2",
                               "claim": "one box, vote2 ships"},
                              {"rule": f"j8s_{res}",
                               "claim": "the node is replaced by pieces"})
            if res == "covered_by_existing":
                owners = case.get("owners") or []
                self.drop(nid, "j8s_covered_by_existing",
                          "J8 ruled SPLIT/distinct and every part maps to an "
                          "existing node whose carved box already covers it",
                          owners=owners, coverage=case.get("coverage"))
                for o in owners:
                    self.annotate_owner(o, nid, "(whole node)",
                                        "covered_by_existing")
                covered += 1
                continue
            if res != "split_chain":
                self.conflict(nid, "unknown J8s resolution",
                              {"rule": "j8s", "claim": res},
                              {"rule": "materialize",
                               "claim": "vocabulary is split_chain|"
                                        "covered_by_existing"})
                continue

            parent = self.nodes[nid]
            new_ids, k = [], 0
            for p in case.get("pieces") or []:
                owner = p.get("owner")
                if owner == "this_node":
                    k += 1
                    pid = f"{nid}#{k}"
                    g = geom_from_lohi(p["box"]["lo"], p["box"]["hi"])
                    self.nodes[pid] = {
                        "id": pid, "name": parent["name"], "geometry": g,
                        "members": list(parent["members"]),
                        "from": "split_piece", "split_from": nid,
                        "provenance": [{
                            "rule": "inherited_from_parent", "parent": nid,
                            "parent_rules": [q["rule"]
                                             for q in parent["provenance"]],
                            "note": "the parent's rules are recorded for "
                                    "audit; this piece's BOX comes from the "
                                    "J8s cut record, not from the parent"}],
                    }
                    self.prov(pid, "j8s_split_piece", parent=nid,
                              piece=p.get("id"), owner=owner,
                              cut_provenance=p.get("provenance"),
                              identity=(case.get("j8_verdict") or {}).get(
                                  "identity"),
                              note="box VERBATIM from the J8s cut record")
                    if p.get("doubts"):
                        self.nodes[pid]["open_doubts"] = [
                            {"kind": d, "source": "j8s_piece"}
                            for d in p["doubts"]]
                        for d in p["doubts"]:
                            self.open_q(pid, d,
                                        "doubt recorded on the split piece",
                                        source="split_cuts.json")
                    new_ids.append(pid)
                    made += 1
                elif isinstance(owner, str) and owner.startswith("existing:"):
                    tgt = owner.split(":", 1)[1]
                    self.dropped.append({
                        "id": f"{nid}:{p.get('id')}", "name": parent["name"],
                        "rule": "j8s_piece_owned_by_existing",
                        "why": f"the piece's content is already represented "
                               f"by {tgt} -- no node is created and "
                               f"{tgt}'s box is NOT grown",
                        "owner": tgt, "geometry_was": geom_from_lohi(
                            p["box"]["lo"], p["box"]["hi"])})
                    self.annotate_owner(tgt, nid, p.get("id"),
                                        "j8s_piece_owned_by_existing")
                    dropped_pieces += 1
                else:
                    self.conflict(nid, "split piece has an owner materialize "
                                       "cannot execute",
                                  {"rule": "j8s_split_piece",
                                   "claim": f"owner={owner}"},
                                  {"rule": "materialize",
                                   "claim": "vocabulary is this_node|"
                                            "existing:<id>"},
                                  piece=p.get("id"))
                    self.open_q(nid, "unhandled_piece_owner",
                                f"piece {p.get('id')} owner {owner!r} is not "
                                f"materializable -- the piece was NOT "
                                f"created")
            # the chain's DISCARDED sides never become nodes (J8s contract:
            # discards live in the rounds, not in final pieces). They are
            # recorded here anyway, because they are what shrank the node --
            # and, like every drop, they grow NOTHING.
            disc = [p for rd in case.get("rounds") or []
                    for p in rd.get("pieces") or []
                    if p.get("action") == "discard"]
            for p in disc:
                rc = p.get("residue_check") or {}
                self.dropped.append({
                    "id": f"{nid}:{p.get('id')}", "name": parent["name"],
                    "rule": "j8s_side_discarded",
                    "why": p.get("note"),
                    "geometry_was": geom_from_lohi(p["box"]["lo"],
                                                   p["box"]["hi"]),
                    "residue": rc.get("residue"),
                    "eligible_boxes": rc.get("eligible_boxes"),
                    "residue_stands": rc.get("stands")})
                discarded += 1
            self.drop(nid, "j8s_split_replaced",
                      (f"replaced by {len(new_ids)} piece node(s); "
                       f"{len(disc)} side(s) discarded; the node's box was "
                       f"{size_str(parent['geometry'])} m"
                       if new_ids else
                       "the split chain kept no piece owned by this node"),
                      pieces=new_ids, sides_discarded=len(disc),
                      calls=case.get("calls"),
                      identity=(case.get("j8_verdict") or {}).get("identity"))
            if not new_ids:
                self.open_q(nid, "split_left_no_node",
                            "the J8s chain produced no piece owned by this "
                            "node -- the node disappears from the scene")
            replaced += 1
        self.stats.update(j8s_cases=replaced, j8s_pieces_made=made,
                          j8s_pieces_dropped=dropped_pieces,
                          j8s_sides_discarded=discarded,
                          j8s_covered_by_existing=covered)

    # -- rule 4 ----------------------------------------------------------
    def same_merges(self):
        pairs = same_verdict_pairs(self.graph)
        live = []
        for a, b, v in pairs:
            miss = [x for x in (a, b) if x not in self.nodes]
            if miss:
                self.conflict(miss[0], "J1 ruled SAME but an endpoint is no "
                                       "longer in the proposed set",
                              {"rule": "j1_same", "claim": f"{a} SAME {b}",
                               "confidence": v.get("confidence")},
                              {"rule": "materialize",
                               "claim": f"missing: {', '.join(miss)} "
                                        f"(split or covered)"})
                self.open_q(miss[0], "merge_endpoint_missing",
                            f"the SAME merge {a}<->{b} could not be applied")
                continue
            live.append((a, b, v))
        self.merge_pairs = live

        parent = {}

        def find(x):
            parent.setdefault(x, x)
            while parent[x] != x:
                parent[x] = parent[parent[x]]
                x = parent[x]
            return x

        for a, b, _ in live:
            ra, rb = find(a), find(b)
            if ra != rb:
                parent[rb] = ra
        comps = {}
        for x in list(parent):
            comps.setdefault(find(x), set()).add(x)

        removed = 0
        for members in comps.values():
            if len(members) < 2:
                continue
            ranked = sorted(members,
                            key=lambda i: (-volume(self.nodes[i]["geometry"]),
                                           i))
            survivor, losers = ranked[0], ranked[1:]
            vols = {i: round(volume(self.nodes[i]["geometry"]), 5)
                    for i in ranked}
            tie = len({vols[i] for i in ranked}) < len(ranked)
            ev = [{"a": a, "b": b, "confidence": v.get("confidence"),
                   "reason": v.get("reason")}
                  for a, b, v in live if a in members and b in members]
            self.nodes[survivor]["merged_from"] = losers
            self.nodes[survivor].setdefault("merged_members", [])
            for lid in losers:
                self.nodes[survivor]["merged_members"] += \
                    self.nodes[lid]["members"]
            self.prov(survivor, "j1_same_merge_survivor",
                      merged_from=losers, volumes_m3=vols,
                      tie_break="lexicographic" if tie else None,
                      verdicts=ev,
                      note="identity only -- the survivor's box is NOT "
                           "unioned with the merged node's box")
            for lid in losers:
                # a node that a dropped piece points at must not vanish
                # unnoticed -- the pointer would dangle
                for r in self.nodes[lid].get("represents_dropped_pieces") or []:
                    self.conflict(
                        lid, "a node that represents dropped split content "
                             "is itself merged away",
                        {"rule": r["rule"],
                         "claim": f"represents {r['from_node']} "
                                  f"{r['piece']}"},
                        {"rule": "j1_same_merge_removed",
                         "claim": f"merged into {survivor}"})
                    self.open_q(lid, "representation_pointer_dangling",
                                f"{r['from_node']} {r['piece']} was dropped "
                                f"because {lid} represented it, but {lid} "
                                f"then merged into {survivor}")
                self.drop(lid, "j1_same_merge_removed",
                          f"J1 ruled SAME; the smaller-volume node merges "
                          f"into {survivor}",
                          survivor=survivor, volumes_m3=vols, verdicts=ev)
                removed += 1
        self.stats.update(j1_same_pairs=len(pairs),
                          j1_merged_away=removed)

    # -- rule 5 ----------------------------------------------------------
    def same_product(self):
        annotated = groups_true = 0
        for gi, grp in enumerate((self.sameprod or {}).get("groups", []), 1):
            if not grp.get("same_object"):
                continue
            groups_true += 1
            label = f"g{gi}_{re.sub('[^a-z0-9]+', '_', grp['name'].lower())}"
            size = grp.get("canonical_size")
            for mid in grp.get("set_members") or []:
                if mid in self.nodes:
                    self.nodes[mid]["product_group"] = label
                    self.nodes[mid]["canonical_size"] = size
                    self.prov(mid, "j9_same_product_annotation",
                              product_group=label, canonical_size=size,
                              members=grp.get("set_members"),
                              note="ANNOTATION ONLY -- no box resized; the "
                                   "canonical size is shopping's input, not "
                                   "geometry")
                    annotated += 1
                    continue
                gone = next((d for d in self.dropped if d["id"] == mid), None)
                self.conflict(mid, "J9 named a set member that the node set "
                                   "no longer contains",
                              {"rule": "j9_same_product",
                               "claim": f"member of {label}",
                               "canonical_size": size},
                              {"rule": gone["rule"] if gone else "unknown",
                               "claim": gone["why"] if gone
                               else "node not present"})
                self.open_q(mid, "product_member_missing",
                            f"J9 set member of {label} is not in the "
                            f"proposed node set -- the group annotation "
                            f"could not be placed")
        self.stats.update(j9_groups_same=groups_true,
                          j9_annotated=annotated)

    # -- cross-verdict consistency ---------------------------------------
    def cross_checks(self):
        """Two verdicts can disagree about the same nodes without either
        rule "hitting" the same field. The one that materializes silently
        wins unless it is written down: J1 ruling a pair SAME OBJECT while
        J9 ruled the same pair NOT the same product is exactly that -- the
        merge lands, J9's `false` has no materialized effect."""
        for gi, grp in enumerate((self.sameprod or {}).get("groups", []), 1):
            if grp.get("same_object"):
                continue
            mem = {m["id"] for m in grp.get("members") or []}
            label = f"g{gi}_{re.sub('[^a-z0-9]+', '_', grp['name'].lower())}"
            for a, b, v in getattr(self, "merge_pairs", []):
                if a in mem and b in mem:
                    self.conflict(
                        a, "J1 merged a pair that J9 ruled NOT the same "
                           "product",
                        {"rule": "j1_same_merge", "claim": f"{a} and {b} "
                                                           f"are ONE object",
                         "confidence": v.get("confidence"),
                         "reason": v.get("reason")},
                        {"rule": "j9_same_product",
                         "claim": f"{label}: same_object=false",
                         "reason": grp.get("reason")},
                        applied="the J1 merge (J9's false verdict has no "
                                "materialized effect) -- recorded, not "
                                "resolved")
                    self.open_q(a, "j1_j9_disagreement",
                                f"J1 merged {a}+{b}; J9 ruled {label} not "
                                f"the same product")

    # -- rule 6 ----------------------------------------------------------
    def open_doubts(self):
        j8_by = {c["id"]: (c.get("verdict") or {})
                 for c in (self.mult or {}).get("cases", [])}
        n_open = 0
        for nid, n in self.nodes.items():
            src = n.get("split_from") or nid
            j8 = j8_by.get(src) or {}
            decided = j8.get("outcome") in ("ONE_BOX", "SPLIT")
            opens = list(n.get("open_doubts") or [])
            for d in self.doubts.get(src, []):
                kind = d.get("kind")
                if kind in INFORMATIONAL_DOUBTS:
                    continue
                if decided and kind in J8_ADMITTING:
                    continue                       # J8 answered this doubt
                opens.append({"kind": kind, "text": d.get("text"),
                              "source": "carve_doubts"})
            if opens:
                n["open_doubts"] = opens
                n_open += 1
                for d in opens:
                    if d.get("source") == "carve_doubts":
                        self.open_q(nid, d["kind"], d.get("text"),
                                    source="carve_doubts")
        self.stats["nodes_with_open_doubts"] = n_open

    # -- drive -----------------------------------------------------------
    def run(self):
        self.base_geometry()
        self.box_rulings()
        self.splits()
        self.same_merges()
        self.same_product()
        self.cross_checks()
        self.open_doubts()
        self.stats.update(
            resolved_in=len(self.graph["resolved"]["nodes"]),
            nodes_out=len(self.nodes),
            dropped=len(self.dropped),
            conflicts=len(self.conflicts),
            open_questions=len(self.opens))
        return self

    # -- fate table (report + printout) ----------------------------------
    def fates(self):
        """One row per RESOLVED node (the input set), in id order, plus the
        piece nodes under their parent."""
        drop_by = {d["id"]: d for d in self.dropped}
        rows = []
        for rn in sorted(self.graph["resolved"]["nodes"], key=lambda n: n["id"]):
            nid = rn["id"]
            node = self.nodes.get(nid)
            d = drop_by.get(nid)
            if node:
                rules = [p["rule"] for p in node["provenance"]]
                if "j8_box_swap_vote2" in rules:
                    fate, rule = "box-swapped (vote2)", "j8_box_swap_vote2"
                else:
                    fate, rule = "kept", rules[0] if rules else "-"
                    if "j1_same_merge_survivor" in rules:
                        fate = ("kept · absorbed "
                                + ", ".join(node.get("merged_from") or []))
                        rule = "j1_same_merge_survivor"
                rows.append(self.row(nid, rn["name"], fate, rule, node))
            elif d and d["rule"] == "j8s_split_replaced":
                kids = [self.nodes[i] for i in d.get("pieces") or []]
                nd = d.get("sides_discarded") or 0
                rows.append(self.row(
                    nid, rn["name"],
                    (f"split into {len(kids)}"
                     + (f" (+{nd} side discarded)" if nd else ""))
                    if kids else "dropped (split kept nothing)",
                    d["rule"], None, note=d["why"]))
                for kd in kids:
                    rows.append(self.row(kd["id"], kd["name"],
                                         "NEW piece node", "j8s_split_piece",
                                         kd, indent=True))
                for pd in [x for x in self.dropped
                           if x["rule"] in ("j8s_piece_owned_by_existing",
                                            "j8s_side_discarded")
                           and x["id"].startswith(nid + ":")]:
                    cov = ", ".join(pd.get("eligible_boxes") or []) \
                        or "nothing"
                    lbl = (f"piece dropped -> {pd.get('owner')}"
                           if pd["rule"] == "j8s_piece_owned_by_existing"
                           else f"side DISCARDED (residue "
                                f"{pd.get('residue')}, covered by {cov})")
                    rows.append(self.row(
                        pd["id"], pd["name"], lbl, pd["rule"], None,
                        indent=True, note=pd["why"],
                        size=size_str(pd["geometry_was"])))
            elif d and d["rule"] == "j1_same_merge_removed":
                rows.append(self.row(nid, rn["name"],
                                     f"dropped · merged into {d['survivor']}",
                                     d["rule"], None, note=d["why"]))
            elif d and d["rule"] == "j8s_covered_by_existing":
                rows.append(self.row(
                    nid, rn["name"],
                    "dropped · covered by " + ", ".join(d.get("owners") or []),
                    d["rule"], None, note=d["why"]))
            elif d:
                rows.append(self.row(nid, rn["name"], "dropped", d["rule"],
                                     None, note=d["why"]))
            else:
                rows.append(self.row(nid, rn["name"], "?? vanished",
                                     "materialize_bug", None))
        return rows

    def row(self, nid, name, fate, rule, node, indent=False, note="",
            size=None):
        ann = []
        if node:
            if node.get("product_group"):
                ann.append(f"{node['product_group']} · canonical "
                           f"{node.get('canonical_size')}")
            for r in node.get("represents_dropped_pieces") or []:
                ann.append(f"represents {r['from_node']} {r['piece']}")
        opens = [o for o in self.opens if o["node"] == nid]
        confs = [c for c in self.conflicts if c["node"] == nid]
        return {"id": nid, "name": name, "fate": fate, "rule": rule,
                "size": size or (size_str(node["geometry"]) if node else "-"),
                "annotations": ann, "note": note,
                "open": [f"{o['kind']}: {(o['text'] or '')[:120]}"
                         for o in opens],
                "conflicts": [c["why"] for c in confs],
                "indent": indent}

    # -- outputs ---------------------------------------------------------
    def layer(self):
        return {
            "built": date.today().isoformat(),
            "built_from": "resolved nodes + carve SHIPPING boxes + J8/J8s/"
                          "J1/J9 verdicts (Phase C materialize)",
            "status": "UNTESTED-TRIAL",
            "note": "ADDITIVE layer: record/judged/resolved/carve/"
                    "carved_edges are untouched. Boxes are COPIES (carve "
                    "manifest, carve report vote2, J8s cut record) -- "
                    "nothing recomputed. Merges and dropped pieces move "
                    "IDENTITY only: no box is ever grown. Edges are NOT "
                    "re-derived in this pass (open question).",
            "precedence": [
                "1 geometry base = carve shipping box verbatim",
                "2 J8 box ruling (ship_vote -> vote2; ship_pano/either -> "
                "unchanged; exempt node -> ruling_not_applicable)",
                "3 J8s split pieces (<nid>#k; existing:<id> piece dropped "
                "with a pointer, never grows that node)",
                "4 J1 SAME merges (smaller volume removed, transitive)",
                "5 J9 same-product annotation (canonical_size, NO resize)",
                "6 UNCLEAR / open doubts ship unchanged",
            ],
            "sources": {
                "geometry": CARVED_MANIFEST,
                "vote_boxes": self.report_path,
                "j8": "graph/multiplicity.json",
                "j8s": "graph/split_cuts.json",
                "j9": "graph/same_product.json",
                "doubts": "graph/carve_doubts.json",
                "j1_same": "graph['carved_edges'] SAME_CANDIDATE verdicts",
            },
            "nodes": list(self.nodes.values()),
            "dropped": self.dropped,
            "conflicts": self.conflicts,
            "open_questions": self.opens,
            "counts": self.stats,
        }

    def print_report(self):
        s = self.stats
        print(f"[materialize] {self.scene}: {s['resolved_in']} resolved -> "
              f"{s['nodes_out']} proposed nodes "
              f"({s['dropped']} dropped, {s['j8s_pieces_made']} new pieces)")
        print(f"[materialize] rules fired: base carved {s['base_carved']}"
              f" / resolved-fallback {s['base_resolved_fallback']} · "
              f"J8 swap {s['j8_box_swapped']}, noop {s['j8_box_noop']}, "
              f"not-applicable {s['j8_ruling_not_applicable']}, "
              f"UNCLEAR {s['j8_unclear']} · "
              f"J8s cases {s['j8s_cases']} (pieces {s['j8s_pieces_made']}, "
              f"pieces dropped {s['j8s_pieces_dropped']}, sides discarded "
              f"{s['j8s_sides_discarded']}, covered "
              f"{s['j8s_covered_by_existing']}) · "
              f"J1 SAME pairs {s['j1_same_pairs']} -> merged away "
              f"{s['j1_merged_away']} · "
              f"J9 groups {s['j9_groups_same']} -> annotated "
              f"{s['j9_annotated']}")
        print(f"[materialize] conflicts: {s['conflicts']} · open questions: "
              f"{s['open_questions']} · nodes carrying open doubts: "
              f"{s['nodes_with_open_doubts']}")
        print("\n--- CHANGED NODES ---")
        for r in self.fates():
            if (r["fate"] == "kept" and not r["annotations"]
                    and not r["conflicts"]):
                continue
            pad = "    " if r["indent"] else ""
            print(f'{pad}{r["id"]:<14} {r["name"]:<14} {r["fate"]:<34} '
                  f'[{r["rule"]}] {r["size"]}'
                  + (f' | {"; ".join(r["annotations"])}'
                     if r["annotations"] else ""))
            if r["note"]:
                print(f'{pad}    note: {r["note"]}')
        if self.conflicts:
            print("\n--- CONFLICTS (never silently resolved) ---")
            for c in self.conflicts:
                print(f'  {c["node"]}: {c["why"]}')
                print(f'      A [{c["claim_a"].get("rule")}] '
                      f'{c["claim_a"].get("claim")}')
                print(f'      B [{c["claim_b"].get("rule")}] '
                      f'{c["claim_b"].get("claim")}')
        else:
            print("\n--- CONFLICTS: none ---")
        print("\n--- OPEN QUESTIONS ---")
        for o in self.opens:
            print(f'  {o["node"]:<14} {o["kind"]:<26} '
                  f'{(o["text"] or "")[:110]}')
        if not self.opens:
            print("  none")


# --------------------------------------------------------------------------
# report
# --------------------------------------------------------------------------

CSS = """body{font-family:system-ui,sans-serif;margin:22px;background:#111;
color:#eee}h1{font-size:19px;margin:0 0 4px}h2{font-size:14px;
margin:22px 0 6px;color:#ffd27a}.meta{font-size:12px;color:#bbb}
table{border-collapse:collapse;font-size:12px;width:100%}
td,th{border:1px solid #444;padding:4px 8px;vertical-align:top}
th{background:#1b1b1b;text-align:left}
tr.piece td:first-child{padding-left:26px;color:#9fd39f}
.kept{color:#9a9a9a}.chg{color:#ffd27a}.drop{color:#ff9d9d}
.new{color:#9fd39f}.warn{color:#ff9d9d}
code{color:#8ec7ff}ul{margin:4px 0 4px 18px;padding:0}
.count{display:inline-block;border:1px solid #444;background:#1b1b1b;
padding:6px 10px;margin:0 8px 8px 0;font-size:12px}
.count b{font-size:16px;color:#ffd27a;display:block}"""


def esc(x):
    return html.escape(str(x)) if x is not None else ""


def fate_class(f):
    if f.startswith("kept ·"):
        return "chg"
    if f.startswith("kept"):
        return "kept"
    if f.startswith("NEW"):
        return "new"
    if "dropped" in f or "DISCARD" in f:
        return "drop"
    return "chg"


def write_report(m, out):
    s, rows = m.stats, m.fates()
    counts = [("resolved in", s["resolved_in"]),
              ("proposed nodes", s["nodes_out"]),
              ("new split pieces", s["j8s_pieces_made"]),
              ("dropped", s["dropped"]),
              ("box swaps", s["j8_box_swapped"]),
              ("merged away", s["j1_merged_away"]),
              ("product annotations", s["j9_annotated"]),
              ("conflicts", s["conflicts"]),
              ("open questions", s["open_questions"])]
    head = "".join(f"<span class='count'><b>{v}</b>{esc(k)}</span>"
                   for k, v in counts)
    trs = []
    for r in rows:
        cls = fate_class(r["fate"])
        extra = ""
        if r["note"]:
            extra += f"<div class='meta'>{esc(r['note'])}</div>"
        if r["conflicts"]:
            extra += "".join(f"<div class='warn'>CONFLICT: {esc(c)}</div>"
                             for c in r["conflicts"])
        if r["open"]:
            extra += "<ul>" + "".join(f"<li class='meta'>{esc(o)}</li>"
                                      for o in r["open"]) + "</ul>"
        trs.append(
            f"<tr class='{'piece' if r['indent'] else ''}'>"
            f"<td><code>{esc(r['id'])}</code></td><td>{esc(r['name'])}</td>"
            f"<td class='{cls}'>{esc(r['fate'])}</td>"
            f"<td><code>{esc(r['rule'])}</code></td>"
            f"<td>{esc(r['size'])}</td>"
            f"<td>{'<br>'.join(esc(a) for a in r['annotations'])}{extra}</td>"
            f"</tr>")
    conf = "".join(
        f"<tr><td><code>{esc(c['node'])}</code></td><td>{esc(c['why'])}</td>"
        f"<td>[{esc(c['claim_a'].get('rule'))}] "
        f"{esc(c['claim_a'].get('claim'))}</td>"
        f"<td>[{esc(c['claim_b'].get('rule'))}] "
        f"{esc(c['claim_b'].get('claim'))}</td></tr>"
        for c in m.conflicts) or \
        "<tr><td colspan='4' class='meta'>none</td></tr>"
    opens = "".join(
        f"<tr><td><code>{esc(o['node'])}</code></td>"
        f"<td>{esc(o['kind'])}</td><td>{esc(o.get('text'))}</td></tr>"
        for o in m.opens) or \
        "<tr><td colspan='3' class='meta'>none</td></tr>"
    doc = f"""<!doctype html><meta charset='utf-8'>
<title>Phase C materialize - {esc(m.scene)}</title><style>{CSS}</style>
<h1>PHASE C &middot; MATERIALIZE THE CARVE &mdash; {esc(m.scene)}</h1>
<p class='meta'>{esc(m.layer()['built'])} &middot; TRIAL (non-destructive:
the layer is additive, nothing else in scene_graph.json is touched)
&middot; precedence: geometry base &rarr; J8 box ruling &rarr; J8s split
&rarr; J1 SAME merge &rarr; J9 same-product &rarr; open doubts.
Boxes are COPIES, never recomputed; merges and dropped pieces move
identity only &mdash; no box is ever grown. Edges are NOT re-derived in
this pass.</p>
<p>{head}</p>
<h2>EVERY RESOLVED NODE &rarr; ITS FATE</h2>
<table><tr><th>node</th><th>name</th><th>fate</th><th>deciding rule</th>
<th>size m</th><th>annotations / notes / open questions</th></tr>
{''.join(trs)}</table>
<h2>CONFLICTS (both claims recorded, nothing silently resolved)</h2>
<table><tr><th>node</th><th>why</th><th>claim A</th><th>claim B</th></tr>
{conf}</table>
<h2>OPEN QUESTIONS</h2>
<table><tr><th>node</th><th>kind</th><th>text</th></tr>{opens}</table>
"""
    out.write_text(doc, encoding="utf-8")
    return out


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="write graph['carved'] (ADDITIVE) + the report")
    ap.add_argument("--report-only", action="store_true",
                    help="write graph/materialize_report.html but NOT the "
                         "graph")
    a = ap.parse_args()

    m = Materialize(a.scene).run()
    m.print_report()

    rpath = m.sdir / "graph" / "materialize_report.html"
    if not (a.apply or a.report_only):
        print("\n[materialize] DRY -- nothing written "
              "(--report-only for the html, --apply for the layer)")
        return
    write_report(m, rpath)
    print(f"\n[materialize] wrote {rpath}")
    if not a.apply:
        print("[materialize] --report-only: graph NOT written")
        return

    before = {k: v for k, v in m.graph.items() if k != LAYER}
    m.graph[LAYER] = m.layer()
    m.gpath.write_text(json.dumps(m.graph, indent=1), encoding="utf-8")

    after = json.loads(m.gpath.read_text(encoding="utf-8"))
    changed = [k for k in set(before) | (set(after) - {LAYER})
               if json.dumps(before.get(k), sort_keys=True)
               != json.dumps(after.get(k), sort_keys=True)]
    print(f"[materialize] wrote graph['{LAYER}'] into {m.gpath} "
          f"({len(m.nodes)} nodes)")
    print(f"[materialize] additive check: "
          f"{'PASS' if not changed else '*** FAIL: ' + str(changed) + ' ***'}"
          f" -- {len(before)} other top-level blocks compared "
          f"({', '.join(sorted(before))})")


if __name__ == "__main__":
    main()
