"""Phase C -- MATERIALIZE the vote: ONE proposed node set from the
resolved layer plus EVERY verdict the vote loop produced.

Contract (docs/plans/PLAN_VOTEBOX_DOWNSTREAM.md, Phase C):
  GETS   graph["resolved"] (identity canon) + the vote's SHIPPING boxes
         (scene_manifest_slicevote_preview.json) + the four verdict
         sidecars (J8 graph/multiplicity.json, J8s graph/split_cuts.json,
         J9 graph/same_product.json, graph/vote_doubts.json) + the J1
         SAME verdicts riding on graph["voted_edges"] SAME_CANDIDATE
         edges.
  WRITES one ADDITIVE layer graph["grouped"] = {nodes, dropped, conflicts,
         open_questions, counts, provenance per node}. It NEVER touches
         graph[nodes|edges|judged|resolved|vote|voted_edges], the vote
         outputs, or any sidecar -- and it verifies that by diffing every
         other top-level key before/after the write.
  A MISTAKE looks like: a silently recomputed box (boxes are COPIED, never
         derived), a rule quietly overruling another instead of landing in
         `conflicts`, or a dropped piece growing the neighbour it points at.

PRECEDENCE -- the rules are applied in this order and every rule that
fires is recorded on the node's `provenance` list:

  1. GEOMETRY BASE. Each resolved node takes its vote SHIPPING box
     VERBATIM from the preview manifest (aabb_min/aabb_max/center/size
     copied, never recomputed). A resolved node with no manifest entry
     keeps its resolved box and is recorded
     (rule `geometry_base_resolved_fallback`) + listed as an open
     question.
  2. J8 SHIP RULING (ONE_BOX cases only). J8 v2.2 names ONE KEY from that
     case's own candidate-box list ("ship"); the retired enum
     (ship_vote|ship_pano|either) is still accepted on an old sidecar and
     mapped onto the same keys. The NAMED BOX IS APPLIED when it exists,
     copied verbatim from the VOTE's own records -- never from the J8
     sidecar, which is a verdict file, not a geometry source:
       "vote"            -> the vote report's boxes.vote2
       "pano"            -> the vote report's boxes.pano
       "rebox_candidate" -> the face-on measurement the vote recorded on
                            its own doubt: rebox_rejected_smaller's
                            proposed_box, or (2026-08-10, the R-S2-58
                            ballot fix) rebox_truncated's
                            measured_candidate — the raw measurement
                            before priors refilled the clipped sides. On
                            a vote-EXEMPT node this is the judge ADOPTING
                            the MEASURED box over the prior that ships.
       "current"|"either"-> explicit NO-OPs: the shipping box stands
                            (rule `j8_box_ruling_noop`).
     Applying = `j8_box_swap` when the named box differs from the shipping
     box, `j8_box_ruling_noop` when it is already the same geometry.
     A key that names a box THIS NODE DOES NOT HAVE (e.g. "vote" on a
     vote-exempt node, whose report entry only carries
     original/rebox/shipping) is recorded as `j8_ruling_not_applicable` --
     never as a ruling that applied -- and raised as an open question.
     UNCLEAR -> the node ships unchanged (`j8_unclear_ship_unchanged`)
     and the doubt stays open (rule 6).
     NO_GOOD_BOX (J8 v2.3) -> the judge ruled EVERY candidate grossly
     wrong. Handled CONSERVATIVELY: the node KEEPS its current shipping
     geometry (nothing is dropped, no box is invented), records rule
     `j8_no_good_box` with the judge's reason, and lands in
     `open_questions` so it is loud and reviewable rather than silently
     accepted. Its vote doubts also stay open (rule 6): a kill is not
     an answer to the doubt.
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
  4. J1 SAME MERGES. Every SAME_CANDIDATE edge in graph["voted_edges"]
     with verdict SAME merges its pair: the SMALLER-VOLUME node is
     removed and its id lands on the survivor as `merged_from`. Chains
     resolve transitively (connected components; survivor = the largest
     voted volume in the component, ties broken lexicographically and
     recorded). The survivor's BOX IS NOT UNIONED -- it keeps its voted
     box verbatim; only identity bookkeeping moves.
  5. J9 SAME-PRODUCT (USER RULING 2026-08-10: "same product is only a
     relationship — the sizing is already embedded in the scene graph").
     Every group with same_object true is applied as a real EDIT:
       - RELATIONSHIP: pairwise SAME_PRODUCT edges between the set
         members (judge-created, like J0's semantic nominations). No
         size rides on the relationship.
       - SIZE INTO THE NODES: every member's box becomes the determined
         product size, fitted to that member's OWN orientation (boxes
         are room-axis-aligned, so the same door on two perpendicular
         walls swaps width/thickness — the long floor side goes to the
         member's longer floor axis). Anchor = the SUPPORT FACE (user
         ruling): ceiling-mounted keep their top on the ceiling,
         wall-flush keep the wall-side face on the wall, everything
         else keeps its bottom; unanchored axes resize about center.
       - The pre-resize box, the exemplar, the axis fit and the anchors
         all land in provenance. This deliberately repairs a bad member
         through the set's agreement (obj_018's truncation artifact).
     Because boxes now MOVE here, edge re-derivation runs AFTER this
     rule in the full pass (the edges follow the nodes).
  6. UNCLEAR / OPEN DOUBTS. A node whose J8 outcome is UNCLEAR, or which
     still carries unresolved vote doubts, ships UNCHANGED and is listed
     in open_questions. A doubt counts as CLOSED only when the node got a
     J8 verdict other than UNCLEAR and the doubt's kind is one J8 is
     asked about (J8_ADMITTING); `exemption` doubts are provenance, not
     questions; everything else (e.g. slice_fallback) stays open.

CONFLICTS. When two rules make disagreeing claims about the same node
(a merge whose partner a split already removed, a J9 set member that no
longer exists, a piece pointing at a node nothing kept, a node that
represents dropped content and is then merged away, a J8 ship key this
stage has no vocabulary for, or a pair J1 merged as ONE OBJECT that J9
ruled NOT the same product), BOTH claims land in `conflicts` with their
rules. Nothing is silently resolved.

THE EDGES FOLLOW THE NODES (rule 4b, user design rule 2026-08-08: "each
module is an edit on the scene graph, and it has to inherit all the
properties and information ... but overall structure should be the
same"). This layer is a WHOLE graph, not a node set: it carries `edges`,
`nesting` and `edge_meta` alongside the nodes. Geometric edges are
RE-DERIVED on this layer's boxes -- a moved box can form edges with
nodes it never touched (obj_021 grew in a J8 swap and now
INTERPENETRATES the desk, having had one NEAR edge to the floor before),
so checking former neighbours cannot be correct; the full pass is 990
pairs and ~5 ms. What geometry cannot regenerate -- judge status /
triage / verdict and J6's edge re-examination fields -- is INHERITED,
re-pointed through this pass's own node edits, and grafted back onto the
surviving edges. An inherited judge payload with no surviving edge is
recorded, never dropped: `judge_fields_unplaced` (the geometry changed
under it), `judged_edges_consumed_by_a_merge` (both ends became the same
node, i.e. the verdict has already been applied) or
`judged_edges_lost_to_node_removal`.

STILL NOT IN THIS PASS: the targeted appearance pass for nodes the
splits created (a piece inherits its parent's description, which is a
guess) -- listed as an open question on the report.

WRITING IS THE DEFAULT (2026-08-11). The layer used to be written only
when --apply was passed, so a forgotten flag made this stage exit 0
having written nothing while the next stage read the PREVIOUS run's
graph['grouped'] as if it were current. An unattended pass over 100
scenes must not be able to succeed silently that way, so the default is
now "do the work" and --dry-run is the explicit opt-out. --apply is
still accepted and does nothing. --report-only keeps its exact old
meaning: write the html report, not the graph.

Run:
  python graph/materialize_layers.py --scene living_marble
  python graph/materialize_layers.py --scene living_marble --report-only
  python graph/materialize_layers.py --scene living_marble --dry-run
"""
import argparse
import copy
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
import scene_state    # noqa: E402
import edge_carry     # noqa: E402

VOTED_MANIFEST = "scene_manifest_slicevote_preview.json"
VOTE_REPORT = Path("vote") / "slicevote_report.json"
GEOM_KEYS = ("aabb_min", "aabb_max", "center", "size")
LAYER = "grouped"

# doubt kinds J8 is actually asked about -- a non-UNCLEAR J8 verdict
# closes these and only these; `exemption` is provenance, not a question
J8_ADMITTING = ("pano_vs_cluster", "culled_clusters", "low_plan_fill",
                "large_empty_notch", "rebox_rejected_smaller",
                "rebox_truncated")
INFORMATIONAL_DOUBTS = ("exemption",)

# J8 v2.2 ship vocabulary. SHIP_KEYS name a box that must be looked up and
# applied; NOOP_KEYS name the box that already ships. The retired enum is
# accepted on an OLD sidecar only, mapped onto the same keys.
SHIP_KEYS = ("vote", "pano", "rebox_candidate")
NOOP_KEYS = ("current", "either")
LEGACY_SHIP = {"ship_vote": "vote", "ship_pano": "pano", "either": "either"}


# --------------------------------------------------------------------------
# small geometry helpers -- COPY boxes, never recompute a vote number
# --------------------------------------------------------------------------


def supersede(node, geom, stage, why):
    """Push the box a node is about to lose onto its geometry_superseded
    HISTORY, oldest first.

    It is a LIST, not a single slot: a node can lose its box more than
    once (the vote elects one, then J8 swaps it), and a single slot meant
    the second edit erased the first — obj_021 ended up advertising its
    PRE-VOTE box as "superseded" while the box the vote actually elected
    had vanished without trace. Kept for reference, never canon.
    """
    if not geom:
        return
    hist = node.get("geometry_superseded")
    if isinstance(hist, dict):          # the one-slot form written earlier
        hist = [hist]
    elif not isinstance(hist, list):
        hist = []
    hist.append({"stage": stage, "source": stage, "note": why,
                 **{k: geom[k] for k in GEOM_KEYS if k in geom}})
    node["geometry_superseded"] = hist


def geom_from_lohi(lo, hi, ndigits=3):
    """A node geometry block from a report/cut box. lo/hi are copied
    verbatim; center/size are the two derived conveniences every other
    layer carries (rounded like the manifest's own)."""
    lo, hi = list(lo), list(hi)
    return {"aabb_min": lo, "aabb_max": hi,
            "center": [round((lo[i] + hi[i]) / 2, ndigits) for i in range(3)],
            "size": [round(hi[i] - lo[i], ndigits) for i in range(3)]}


def fit_size_to_member(size, member_size):
    """Express a product size [w,h,d] in ONE member's own orientation.

    Boxes are room-axis-aligned, so the same product standing on two
    perpendicular walls swaps its two floor dimensions: the product's
    long floor side goes on the member's own longer floor axis. Height
    (y in this y-down frame) never moves. Returns (fitted_size,
    axis_map). SHARED with the J9 box view -- one rule, so the picture
    and the graph can never disagree about which way a size lies."""
    p_h = size[1]
    p_long, p_short = sorted((size[0], size[2]), reverse=True)
    if member_size[0] >= member_size[2]:
        return [p_long, p_h, p_short], "x=long"
    return [p_short, p_h, p_long], "z=long"


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


def vote_report_boxes(sdir, graph):
    """{id: {box_name: {lo,hi}}} from the vote's own report (the only
    place vote2 lives). Preferred location is the scene's vote/; the
    `voted` layer's recorded built_from is the fallback for a scene whose
    report has been moved. (That fallback read graph['vote']['built_from']
    until 2026-08-11, when the block was retired; build_voted records the
    same provenance on the layer.)"""
    p = sdir / VOTE_REPORT
    if not p.exists():
        rec = (graph.get("voted") or {}).get("built_from") or ""
        # the layer states its sources in one sentence; pull the report
        # out of it rather than trusting the whole string as a path
        for tok in str(rec).split():
            if tok.endswith("slicevote_report.json") and Path(tok).exists():
                p = Path(tok)
                break
    rep = load_json(p, "vote report (slicevote_report.json)")
    return ({r["id"]: (r.get("boxes") or {}) for r in rep["results"]},
            str(p))


def same_verdict_pairs(graph):
    """SAME_CANDIDATE edges whose J1 verdict is SAME. [(a, b, verdict)].

    `voted` IS THE PLACE, and since 2026-08-11 it is the only one.

    THE BUG THIS FUNCTION WAS BORN FROM, kept because the shape recurs.
    It used to read `(graph["voted"] or graph["voted_edges"])` — the
    docstring said `voted_edges`, the code took `voted` whenever it
    existed, which was always. But J1's post-vote re-judgement wrote into
    `voted_edges`, so a SAME_CANDIDATE pair re-judged after the vote had
    no effect at all: the answer went somewhere this function never
    looked. That matters because the vote MOVES BOXES and can create
    duplicate pairs no judge saw before it (the two chairs at 96%
    containment). Re-judging them is the intended repair, and it silently
    did nothing. Two places to write one fact is what made it possible.

    The half-layer is now retired and `judge_pairs --edges-from voted`
    writes into the voted LAYER's own edges — the same list this reads
    first. `voted_edges` is still swept, and swept SECOND, purely for
    scenes on disk that were judged before the change; a fresh scene
    never has the block. Verdicts are keyed by pair, so no edge is
    applied twice."""
    seen = {}
    for block in ("voted", "voted_edges"):
        for e in (graph.get(block) or {}).get("edges", []):
            if e.get("type") != "SAME_CANDIDATE":
                continue
            v = e.get("verdict") or {}
            if str(v.get("verdict", "")).upper() != "SAME":
                continue
            seen[tuple(sorted((e["a"], e["b"])))] = (e["a"], e["b"], v)
    return list(seen.values())


def doubts_by_node(sdir, graph):
    """{id: [doubt]} -- the vote's typed doubts.

    graph/vote_doubts.json is THE source (record_vote_doubts.py writes
    it). The `voted` layer's nodes carry the same doubts, folded in by
    build_voted, and are the fallback for a scene whose sidecar has been
    moved. graph['vote'] was a third copy and was retired 2026-08-11."""
    p = sdir / "graph" / "vote_doubts.json"
    if p.exists():
        d = json.loads(p.read_text(encoding="utf-8"))
        return {n["id"]: n.get("doubts") or [] for n in d.get("nodes", [])}
    return {n["id"]: n.get("doubts") or []
            for n in (graph.get("voted") or {}).get("nodes") or []}


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
        man = load_json(self.sdir / VOTED_MANIFEST, "vote preview manifest")
        self.manifest = {o["id"]: o for o in man["objects"]}
        self.report, self.report_path = vote_report_boxes(self.sdir,
                                                           self.graph)
        gdir = self.sdir / "graph"
        self.mult = load_json(gdir / "multiplicity.json", "J8 verdicts")
        self.cuts = load_json(gdir / "split_cuts.json", "J8s split cuts")
        # J9's VERDICTS ARE OPTIONAL HERE, AND ON A FRESH SCENE THEY MUST
        # BE (fixed 2026-08-11, found on the first genuinely new scene).
        # This module runs TWICE: `--settle-only` writes the geometry
        # layer BEFORE J9 has been asked anything, and the full pass adds
        # J9's grouping afterwards. Requiring same_product.json in the
        # constructor made the FIRST pass depend on the output of a stage
        # that has not run yet — so `--settle-only` could never succeed on
        # a scene that had not already been through the chain once. It
        # went unnoticed because the scenes it was developed on all had a
        # stale same_product.json lying around from an earlier session.
        #
        # Absent is now simply "no grouping yet". The full pass still
        # refuses without it — see run(), where it is actually needed.
        self.sameprod = load_json(gdir / "same_product.json", "J9 verdicts",
                                  required=False)
        self.doubts = doubts_by_node(self.sdir, self.graph)

        self.nodes = {}          # id -> proposed node (insertion ordered)
        self.edge_list = []      # rule 4b: the edges, following the nodes
        self.edge_meta = {}
        self.nesting = {}
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
        """START FROM THE NEWEST WHOLE LAYER, inheriting all of it.

        USER DESIGN RULE (2026-08-08): a module edits the scene graph and
        inherits the rest. This used to rebuild each node from scratch —
        id / name / geometry / members / from — which quietly dropped
        everything the vote stage had recorded (the elected box's own
        provenance, the superseded pre-vote box, the vote record, the
        typed doubts) and forced every later reader to go find it in a
        sidecar. Now graph['voted'] is copied forward WHOLE and this pass
        only edits what its own rules touch.

        Fallback, announced: no voted layer -> the old resolved + manifest
        path, so a scene that has not been re-run still materializes.
        """
        voted = (self.graph.get("voted") or {}).get("nodes")
        if voted:
            for vn in sorted(voted, key=lambda n: n["id"]):
                n = copy.deepcopy(vn)
                n["from"] = "voted"
                n.setdefault("provenance", [])
                self.nodes[n["id"]] = n
            self.stats["base_voted"] = len(self.nodes)
            self.stats["base_resolved_fallback"] = 0
            self.base_layer = "voted"
            return

        self.base_layer = "resolved+manifest"
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
                self.prov(nid, "geometry_base_voted",
                          source=VOTED_MANIFEST,
                          vote_status=(mo.get("flags") or [None])[0],
                          note="vote SHIPPING box copied VERBATIM")
            else:
                self.nodes[nid]["geometry"] = dict(rn["geometry"])
                self.prov(nid, "geometry_base_resolved_fallback",
                          note="no entry in the vote preview manifest -- "
                               "the resolved (pre-vote) box stands")
                self.open_q(nid, "unvoted",
                            "node has no voted box; it ships its "
                            "pre-vote resolved geometry")
                fallbacks += 1
        self.stats["base_voted"] = len(self.nodes) - fallbacks
        self.stats["base_resolved_fallback"] = fallbacks

    # -- rule 2 ----------------------------------------------------------
    def named_box(self, nid, key):
        """The box a J8 ship key names, from the VOTE's own records.
        Returns (box|None, source). `None` means this node does not have
        that box -- the ruling is then not-applicable, never guessed."""
        boxes = self.report.get(nid) or {}
        if key == "vote":
            return boxes.get("vote2"), str(VOTE_REPORT).replace("\\", "/")
        if key == "pano":
            return boxes.get("pano"), str(VOTE_REPORT).replace("\\", "/")
        if key == "rebox_candidate":
            for d in self.doubts.get(nid, []):
                if d.get("kind") == "rebox_rejected_smaller" \
                        and d.get("proposed_box"):
                    return d["proposed_box"], ("graph/vote_doubts.json "
                                               "rebox_rejected_smaller."
                                               "proposed_box")
                if d.get("kind") == "rebox_truncated" \
                        and d.get("measured_candidate"):
                    return d["measured_candidate"], (
                        "graph/vote_doubts.json rebox_truncated."
                        "measured_candidate")
            return None, "graph/vote_doubts.json"
        return None, ""

    def available_keys(self, nid):
        """The ship keys this node COULD honour -- for the not-applicable
        record, so the open question says what was actually on hand."""
        boxes = sorted(self.report.get(nid) or {})
        got = [k for k, b in (("vote", "vote2"), ("pano", "pano"))
               if b in boxes]
        if self.named_box(nid, "rebox_candidate")[0]:
            got.append("rebox_candidate")
        return got + ["current", "either"]

    def box_rulings(self):
        swapped = noop = na = unclear = no_good = 0
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
            if outcome == "NO_GOOD_BOX":
                # J8 v2.3 kill: every candidate box was grossly wrong.
                # CONSERVATIVE by rule -- the node keeps whatever geometry
                # it already ships (no drop, no invented box) and the case
                # is raised loudly instead of being silently accepted.
                why = (v.get("reason") or "").strip() or "(no reason given)"
                self.prov(nid, "j8_no_good_box",
                          confidence=v.get("confidence"), reason=why,
                          note="J8 ruled NO candidate box usable. The "
                               "current shipping geometry STANDS UNCHANGED "
                               "-- the node is not dropped and no box is "
                               "invented; the case is an open question")
                self.open_q(nid, "j8_no_good_box",
                            f"J8 ruled NO_GOOD_BOX (every candidate box is "
                            f"grossly wrong): {why} -- the node ships its "
                            f"current geometry unchanged and NEEDS a new box",
                            confidence=v.get("confidence"))
                no_good += 1
                continue
            if outcome != "ONE_BOX":
                continue                      # SPLIT -> rule 3
            # v2.2 vocabulary; a legacy sidecar's box_ruling maps onto it
            ruling = v.get("ship") or LEGACY_SHIP.get(v.get("box_ruling"))
            if ruling in ("current", "either"):
                self.prov(nid, "j8_box_ruling_noop", ship=ruling,
                          confidence=v.get("confidence"),
                          note="the ruling names the box that already "
                               "ships -- nothing to apply")
                noop += 1
            elif ruling in SHIP_KEYS:
                b, src = self.named_box(nid, ruling)
                if b is None:
                    self.prov(nid, "j8_ruling_not_applicable", ship=ruling,
                              available=self.available_keys(nid),
                              note=f"this node has no {ruling!r} box on "
                                   "record, so the ruling is a NO-OP -- the "
                                   "shipping box stands unchanged")
                    self.open_q(nid, "ruling_not_applicable",
                                f"J8 ruled ship={ruling} but no such box "
                                f"exists for this node (available: "
                                f"{', '.join(self.available_keys(nid))}) -- "
                                f"the ruling could not be executed")
                    na += 1
                elif same_box(self.nodes[nid]["geometry"], b["lo"], b["hi"]):
                    self.prov(nid, "j8_box_ruling_noop", ship=ruling,
                              source=src, confidence=v.get("confidence"),
                              note="shipping box already IS the ruled box")
                    noop += 1
                else:
                    old = self.nodes[nid]["geometry"]
                    new = geom_from_lohi(b["lo"], b["hi"])
                    # NOTHING IS OVERWRITTEN WITHOUT A RECORD (user design
                    # rule): the box this swap replaces is the one the VOTE
                    # elected, and it was being silently dropped -- the
                    # node's geometry_superseded still named the pre-vote
                    # box, so "what did the vote decide for obj_021" became
                    # unanswerable after J8 touched it.
                    supersede(self.nodes[nid], old, "voted",
                              "the ELECTED box, replaced by J8's ship "
                              "ruling on this node")
                    self.nodes[nid]["geometry"] = new
                    self.prov(nid, "j8_box_swap", ship=ruling, source=src,
                              was={"aabb_min": old["aabb_min"],
                                   "aabb_max": old["aabb_max"]},
                              now={"aabb_min": new["aabb_min"],
                                   "aabb_max": new["aabb_max"]},
                              confidence=v.get("confidence"),
                              note="box COPIED verbatim from the vote's own "
                                   "record -- never from the J8 sidecar")
                    swapped += 1
            else:
                self.conflict(nid, "unknown J8 ship ruling",
                              {"rule": "j8_box_ruling", "claim": ruling},
                              {"rule": "materialize",
                               "claim": "vocabulary is "
                                        + "|".join(SHIP_KEYS + NOOP_KEYS)})
        self.stats.update(j8_box_swapped=swapped, j8_box_noop=noop,
                          j8_ruling_not_applicable=na, j8_unclear=unclear,
                          j8_no_good_box=no_good)

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
            if "j8_box_swap" in prior:
                self.conflict(nid, "node carries both a J8 ONE_BOX box swap "
                                   "and a J8s split",
                              {"rule": "j8_box_swap",
                               "claim": "one box, the J8-named box ships"},
                              {"rule": f"j8s_{res}",
                               "claim": "the node is replaced by pieces"})
            if res == "covered_by_existing":
                owners = case.get("owners") or []
                self.drop(nid, "j8s_covered_by_existing",
                          "J8 ruled SPLIT/distinct and every part maps to an "
                          "existing node whose voted box already covers it",
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
                    # A NEW NODE INHERITS ITS PARENT'S INFORMATION
                    # (user design rule): a piece used to be born with
                    # id/name/geometry/members only, so it carried no vote
                    # record and no doubts -- and a doubt-free node is
                    # eligible to become a size exemplar. Everything the
                    # parent held comes across, with the parent's own box
                    # recorded as superseded for this piece, and the
                    # inherited vote marked as the PARENT's measurement so
                    # it is never read as this piece's own.
                    self.nodes[pid] = {
                        **{k: copy.deepcopy(v) for k, v in parent.items()
                           if k not in ("id", "geometry", "provenance",
                                        "merged_from", "merged_members")},
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
                    if self.nodes[pid].get("appearance"):
                        # a description of the PARENT is a guess about the
                        # piece: same treatment as the inherited vote, so
                        # nothing downstream reads it as first-hand
                        self.nodes[pid]["appearance"] = {
                            **self.nodes[pid]["appearance"],
                            "describes": nid,
                            "note": "INHERITED from the parent node — J6 "
                                    "described the whole object, not this "
                                    "piece. A targeted appearance pass "
                                    "for judge-created nodes is still an "
                                    "open question."}
                    if self.nodes[pid].get("vote"):
                        self.nodes[pid]["vote"] = {
                            **self.nodes[pid]["vote"],
                            "measured_on": nid,
                            "note": "INHERITED from the parent node — this "
                                    "vote elected the parent's box, NOT "
                                    "this piece's; the piece's box comes "
                                    "from the J8s cut"}
                    supersede(self.nodes[pid], parent["geometry"], "voted",
                              f"the parent {nid}'s box, which this piece "
                              f"was cut out of")
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

    # -- rule 4b: THE EDGES FOLLOW THE NODES ------------------------------
    # USER DESIGN RULE (2026-08-08): "each module is an edit on the scene
    # graph, and it has to inherit all the properties and information.
    # only modify, add, edit, delete etc. but overall structure should be
    # the same." This layer used to hand on nodes with NO edges while
    # graph['voted_edges'] held edges with no nodes -- two half-layers,
    # neither of them a scene graph. On living run 17 that left 15 edges
    # pointing at nodes this pass had deleted, the split piece obj_011#1
    # with none at all, and all 9 pillows' only relation aimed at a node
    # that no longer existed.
    #
    # INHERIT WHAT ONLY INHERITANCE CAN KEEP, RE-DERIVE WHAT ONLY GEOMETRY
    # CAN DECIDE (user: "if it inherits but its wrong then its not right").
    # Every edge type here is derived from boxes, so once a box moves the
    # old edge is a claim about geometry that no longer exists -- and a
    # moved box can form edges with nodes it NEVER touched before (obj_021
    # grew 0.42 -> 0.61 in the J8 swap and now INTERPENETRATES the desk,
    # having previously had a single NEAR edge to the floor). Checking
    # "what used to be near it" cannot find those, so the geometric pass
    # is a full re-derivation: 45 nodes, 990 pairs, ~5 ms, no model calls.
    #
    # What re-derivation CANNOT regenerate is what a judge wrote onto an
    # edge -- status / triage / verdict (J0 nominations, J1 SAME rulings)
    # and J6's edge re-examination fields. Those are grafted back onto the
    # surviving edges, and any that do NOT survive are recorded with their
    # payload intact rather than vanishing.
    JUDGE_FIELDS = ("status", "verdict", "nominated_by", "triage",
                    "confidence", "was", "true_arrangement", "suspect_box",
                    "source")

    def edges(self):
        """THE EDGES FOLLOW THE NODES — delegated to graph/edge_carry.py.

        This method used to hold its own copy of the logic. Two copies is
        one too many, and it showed: the shared module later learned to
        carry edges a JUDGE CREATED (J0 nominates pairs below the
        geometric SAME_CANDIDATE gate and adds its own zone=semantic
        edge) and this copy never did, so a surviving nomination would be
        silently deleted at the settle step. Caught 2026-08-09 by an
        audit asking whether the layer J9 consumes is complete.
        """
        remap = {}
        for d in self.dropped:
            nid, rule = d["id"], d.get("rule") or ""
            if rule.startswith("j1_same_merge") and d.get("survivor"):
                remap[nid] = [d["survivor"]]
            elif rule.startswith("j8s_split") and d.get("pieces"):
                remap[nid] = [q for q in d["pieces"] if q in self.nodes]
            else:
                remap[nid] = []
        self.edge_list, self.nesting, self.edge_meta = edge_carry.carry(
            list(self.nodes.values()), self.graph, remap,
            inherit_from=("judged", "resolved", "voted_edges", "voted"),
            diff_against="voted")
        self.stats.update(
            edges_out=len(self.edge_list),
            edges_appeared=len(self.edge_meta.get("appeared") or []),
            edges_dissolved=len(self.edge_meta.get("dissolved") or []),
            edges_judge_grafted=self.edge_meta.get(
                "judge_fields_grafted", 0),
            edges_judge_consumed=len(self.edge_meta.get(
                "judged_edges_consumed_by_a_merge") or []),
            edges_judge_lost=len(self.edge_meta.get(
                "judged_edges_lost_to_node_removal") or []))

    # -- rule 5 ----------------------------------------------------------
    def _support_anchors(self):
        """What each node rests on, read off the SETTLED layer's edges —
        the layer J9 judged. Returns (ceiling_ids, wall_by_id) where
        wall_by_id[nid] = (axis, wall_value_raw) of its claimed wall."""
        ceiling, wall = set(), {}
        s_edges = (self.graph.get("settled") or {}).get("edges") or []
        s_nodes = {n["id"]: n for n in
                   (self.graph.get("settled") or {}).get("nodes") or []}
        for e in s_edges:
            if e.get("type") == "ATTACHED" and e.get("b") == "arch_ceiling":
                ceiling.add(e.get("a"))
            if e.get("type") == "IN_WALL" and e.get("a") not in wall:
                ev = e.get("evidence") or {}
                ax = ev.get("wall_axis")
                val = ev.get("wall_value_raw")
                if ax is None or val is None:
                    plane = ((s_nodes.get(e.get("b")) or {})
                             .get("geometry") or {}).get("plane") or {}
                    ax = ax or plane.get("axis")
                    val = val if val is not None else plane.get("value_raw")
                if ax in ("x", "z") and val is not None:
                    wall[e.get("a")] = (ax, float(val))
        return ceiling, wall

    def same_product(self):
        """USER RULING 2026-08-10: same product = a RELATIONSHIP; the size
        goes INTO the member nodes, fitted to each member's orientation,
        anchored at its support face. See the module docstring, rule 5."""
        resized = groups_true = 0
        self.product_edges = []
        ceiling, wall = self._support_anchors()
        AX = {"x": 0, "y": 1, "z": 2}
        for gi, grp in enumerate((self.sameprod or {}).get("groups", []), 1):
            if not grp.get("same_object"):
                continue
            groups_true += 1
            label = f"g{gi}_{re.sub('[^a-z0-9]+', '_', grp['name'].lower())}"
            size = grp.get("canonical_size")
            exemplar = grp.get("canonical_size_from")
            present = []
            for mid in grp.get("set_members") or []:
                if mid not in self.nodes:
                    gone = next((d for d in self.dropped
                                 if d["id"] == mid), None)
                    self.conflict(
                        mid, "J9 named a set member that the node set "
                             "no longer contains",
                        {"rule": "j9_same_product",
                         "claim": f"member of {label}",
                         "canonical_size": size},
                        {"rule": gone["rule"] if gone else "unknown",
                         "claim": gone["why"] if gone
                         else "node not present"})
                    self.open_q(mid, "product_member_missing",
                                f"J9 set member of {label} is not in the "
                                f"proposed node set -- the size could not "
                                f"be applied")
                    continue
                present.append(mid)
                if not size:
                    continue
                # PARTIAL members (user ruling 2026-08-12, R-S2-122): a
                # piece of a larger unit — one door face of a fitted
                # wardrobe wall — matches the product's LOOK but is not
                # another whole one. It keeps the SAME_PRODUCT
                # relationship and its OWN measured box; writing the
                # product size into it is how fresh04's real 85 cm-deep
                # wardrobe got flattened into its ghosts' 6 cm slab.
                if mid in (grp.get("partial_members") or []):
                    self.nodes[mid]["product_group"] = label
                    self.prov(mid, "j9_same_product_size",
                              product_group=label, size_from=exemplar,
                              note="PARTIAL member — matches the "
                                   "product's look but is a piece of a "
                                   "larger unit; measured box kept, "
                                   "product size NOT written (user "
                                   "ruling 2026-08-12)")
                    continue
                g = self.nodes[mid]["geometry"]
                old_size = list(g["size"])
                lo, hi = list(g["aabb_min"]), list(g["aabb_max"])
                # fit the product size to THIS member's orientation:
                # long floor side -> the member's longer floor axis
                # (fit_size_to_member -- the one shared rule, also drawn
                # by the J9 box view)
                new, axis_map = fit_size_to_member(size, old_size)
                # anchors, per axis (y-down frame: floor = MAX y, so the
                # bottom face is aabb_max[1] and the top is aabb_min[1])
                anchors = []
                for ax_name, ns in (("x", new[0]), ("y", new[1]),
                                    ("z", new[2])):
                    i = AX[ax_name]
                    if ax_name == "y":
                        if mid in ceiling:
                            hi[i] = lo[i] + ns          # top stays put
                            anchors.append("y:top(ceiling)")
                        else:
                            lo[i] = hi[i] - ns          # bottom stays put
                            anchors.append("y:bottom")
                    elif mid in wall and wall[mid][0] == ax_name:
                        w = wall[mid][1]
                        if abs(lo[i] - w) <= abs(hi[i] - w):
                            hi[i] = lo[i] + ns          # wall face = lo
                        else:
                            lo[i] = hi[i] - ns          # wall face = hi
                        anchors.append(f"{ax_name}:wall")
                    else:
                        c = (lo[i] + hi[i]) / 2
                        lo[i], hi[i] = c - ns / 2, c + ns / 2
                        anchors.append(f"{ax_name}:center")
                g["aabb_min"] = [round(v, 3) for v in lo]
                g["aabb_max"] = [round(v, 3) for v in hi]
                g["size"] = [round(h - l, 3)
                             for l, h in zip(g["aabb_min"], g["aabb_max"])]
                g["center"] = [round((l + h) / 2, 4)
                               for l, h in zip(g["aabb_min"], g["aabb_max"])]
                self.nodes[mid]["product_group"] = label
                changed = g["size"] != [round(v, 3) for v in old_size]
                self.prov(mid, "j9_same_product_size",
                          product_group=label, size_from=exemplar,
                          box_was={"size": old_size},
                          axis_fit=axis_map, anchors=anchors,
                          note=("product size written into the node in its "
                                "own orientation (USER RULING 2026-08-10); "
                                "the relationship itself is the "
                                "SAME_PRODUCT edges")
                          if changed else
                          "exemplar (or already at product size) -- "
                          "no geometric change")
                if changed:
                    resized += 1
            for i, a in enumerate(present):
                for b in present[i + 1:]:
                    self.product_edges.append({
                        "type": "SAME_PRODUCT", "a": a, "b": b,
                        "zone": "judged",
                        "evidence": {"set": label, "size_from": exemplar},
                        "caveats": [],
                        "source": "judge_same_product"})
        self.stats.update(j9_groups_same=groups_true,
                          j9_resized=resized,
                          j9_product_edges=len(self.product_edges))

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
                              "source": "vote_doubts"})
            if opens:
                n["open_doubts"] = opens
                n_open += 1
                for d in opens:
                    if d.get("source") == "vote_doubts":
                        self.open_q(nid, d["kind"], d.get("text"),
                                    source="vote_doubts")
        self.stats["nodes_with_open_doubts"] = n_open

    # -- drive -----------------------------------------------------------
    def run(self, settle_only=False):
        """TWO PHASES (user ruling 2026-08-08). SETTLE first, ANNOTATE
        after.

        J9 used to read the raw vote manifest while running AFTER J8/J8s/
        J1 in the chain — so it judged boxes those verdicts had already
        superseded. On living run 17 that was 3 of the 11 members in its
        sets: obj_011 was still the UNCUT 2.80 m L (J8s had split it),
        obj_020 no longer existed (J1 merged it into obj_068) and was the
        chair set's EXEMPLAR, and obj_021's box had been swapped. The two
        conflicts this pass kept filing were the symptom.

        `settle_only` runs rules 1-4 — the ones that decide GEOMETRY and
        the NODE SET — and stops. J9 then judges that layer, and a second
        full pass folds its annotations in. Rule order is unchanged; only
        what J9 is handed changed.
        """
        self.base_geometry()
        self.box_rulings()
        self.splits()
        self.same_merges()
        if settle_only:
            self.edges()
            self.open_doubts()
            self.stats.update(
                resolved_in=len(self.graph["resolved"]["nodes"]),
                nodes_out=len(self.nodes), dropped=len(self.dropped),
                conflicts=len(self.conflicts),
                open_questions=len(self.opens), phase="settle_only")
            return self
        # THE FULL PASS IS THE ONE THAT ACTUALLY NEEDS J9. The constructor
        # loads same_product.json optionally, because `--settle-only`
        # legitimately runs before J9 exists; the requirement belongs
        # here, where the verdicts are about to be applied. Without this
        # the full pass would quietly write `grouped` with no grouping in
        # it and call that a finished scene.
        if self.sameprod is None:
            raise SystemExit(
                "[materialize] no graph/same_product.json — J9 has not "
                "run for this scene, so there is no grouping to apply. "
                "Run graph/judge_same_product.py first, or use "
                "--settle-only if you only meant to write the geometry "
                "layer.")
        # rule 5 RESIZES boxes since 2026-08-10, so the geometric edge
        # re-derivation must run AFTER it — the edges follow the nodes
        self.same_product()
        self.edges()
        self.edge_list += getattr(self, "product_edges", [])
        self.inherit_shown()
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
                if "j8_box_swap" in rules:
                    sw = next(p for p in node["provenance"]
                              if p["rule"] == "j8_box_swap")
                    fate = f"box-swapped ({sw.get('ship')})"
                    rule = "j8_box_swap"
                else:
                    fate, rule = "kept", rules[0] if rules else "-"
                    if "j1_same_merge_survivor" in rules:
                        fate = ("kept · absorbed "
                                + ", ".join(node.get("merged_from") or []))
                        rule = "j1_same_merge_survivor"
                    if "j8_no_good_box" in rules:
                        # never let a kill hide in the "kept" rows
                        fate += " · NO GOOD BOX (j8)"
                        rule = "j8_no_good_box"
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
                ann.append(f"{node['product_group']} · product size "
                           f"applied to the box")
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
    def inherit_shown(self):
        """Carry each node's PICTURE decision from `shown` into `grouped`.

        THE DEFECT THIS CLOSES (found in the stage table's own note, fixed
        2026-08-11B on the user's ruling that it is "a core function").
        This pass does not read `shown` — it starts again from `voted` and
        re-applies the geometry rules, then adds J9's grouping. So the
        `shown` block, which records WHICH PICTURE each node is actually
        seen as, existed on all 28 nodes of `shown` and on ZERO nodes of
        `grouped`. `grouped` is the final layer and the one compose reads,
        so the pipeline decided each object's picture and then dropped the
        answer on the last step.

        That contradicts the project's own layer rule (user, 2026-08-08):
        "each module is an edit on the scene graph, and it has to inherit
        all the properties and information."

        MATCHED BY ID, AND MISSES ARE COUNTED, NOT ASSUMED AWAY. `shown`
        is built from `settled`, and this pass rebuilds the same node set
        from the same rules, so the ids line up — but a node that gained
        an id here (a J8s split piece) legitimately has no picture yet,
        and that is reported rather than hidden."""
        shown = (self.graph.get("shown") or {}).get("nodes") or []
        if not shown:
            self.stats["shown_inherited"] = 0
            self.stats["shown_missing"] = len(self.nodes)
            return
        book = {n["id"]: n["shown"] for n in shown if n.get("shown")}
        got = 0
        for nid, n in self.nodes.items():
            if nid in book:
                n["shown"] = book[nid]
                got += 1
        self.stats["shown_inherited"] = got
        self.stats["shown_missing"] = len(self.nodes) - got

    def layer(self):
        return {
            "built": date.today().isoformat(),
            "built_from": "resolved nodes + vote SHIPPING boxes + J8/J8s/"
                          "J1/J9 verdicts (Phase C materialize)",
            "status": "UNTESTED-TRIAL",
            "note": "ADDITIVE layer: record/judged/resolved/vote/"
                    "voted_edges are untouched. Boxes are COPIES (vote "
                    "manifest, vote report vote2, J8s cut record) -- "
                    "nothing recomputed. Merges and dropped pieces move "
                    "IDENTITY only: no box is ever grown. THE EDGES "
                    "FOLLOW THE NODES (user design rule 2026-08-08: a "
                    "module edits the graph and inherits the rest, so "
                    "this layer is a WHOLE graph, not a node set): "
                    "geometric edges re-derived on these boxes, judge "
                    "fields inherited and grafted back -- see edge_meta.",
            "precedence": [
                "1 geometry base = vote shipping box verbatim",
                "2 J8 ship ruling (the named candidate box is APPLIED from "
                "the vote's own record: vote -> boxes.vote2, pano -> "
                "boxes.pano, rebox_candidate -> the rejected face-on "
                "re-box; current/either -> unchanged; a key this node has "
                "no box for -> ruling_not_applicable; NO_GOOD_BOX -> the "
                "current shipping geometry stands unchanged and the node "
                "is raised in open_questions)",
                "3 J8s split pieces (<nid>#k; existing:<id> piece dropped "
                "with a pointer, never grows that node)",
                "4 J1 SAME merges (smaller volume removed, transitive)",
                "4b EDGES follow the nodes: re-derived geometrically on "
                "this layer's boxes (a moved box can form edges with "
                "nodes it never touched, so neighbours-only is not "
                "enough), with judge status/verdict/triage inherited and "
                "grafted back because geometry cannot regenerate them",
                "5 J9 same-product: SAME_PRODUCT edges + product size "
                "written into member boxes (user ruling 2026-08-10)",
                "6 UNCLEAR / open doubts ship unchanged",
            ],
            "sources": {
                "geometry": VOTED_MANIFEST,
                "vote_boxes": self.report_path,
                "j8": "graph/multiplicity.json",
                "j8s": "graph/split_cuts.json",
                "j9": "graph/same_product.json",
                "doubts": "graph/vote_doubts.json",
                "j1_same": "graph['voted_edges'] SAME_CANDIDATE verdicts",
            },
            "nodes": list(self.nodes.values()),
            "edges": self.edge_list,
            "edge_meta": self.edge_meta,
            "nesting": self.nesting,
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
        base = (f"base voted {s['base_voted']}" if 'base_voted' in s
                else f"base voted {s.get('base_voted', 0)}"
                     f" / resolved-fallback "
                     f"{s.get('base_resolved_fallback', 0)}")
        print(f"[materialize] rules fired: {base} · "
              f"J8 swap {s['j8_box_swapped']}, noop {s['j8_box_noop']}, "
              f"not-applicable {s['j8_ruling_not_applicable']}, "
              f"UNCLEAR {s['j8_unclear']}, "
              f"NO_GOOD_BOX {s['j8_no_good_box']} · "
              f"J8s cases {s['j8s_cases']} (pieces {s['j8s_pieces_made']}, "
              f"pieces dropped {s['j8s_pieces_dropped']}, sides discarded "
              f"{s['j8s_sides_discarded']}, covered "
              f"{s['j8s_covered_by_existing']}) · "
              f"J1 SAME pairs {s['j1_same_pairs']} -> merged away "
              f"{s['j1_merged_away']} · "
              + (f"J9 groups {s['j9_groups_same']} -> resized "
                 f"{s['j9_resized']}, SAME_PRODUCT edges "
                 f"{s['j9_product_edges']}" if "j9_groups_same" in s
                 else "J9 NOT APPLIED (--settle-only)"))
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
    # .get, not [] — PHASE 1 (--settle-only) legitimately has no J9 stats,
    # and a KeyError here killed the run AFTER every rule had fired but
    # BEFORE the layer was written, so graph['settled'] was never created.
    # It was invisible too: the caller piped stdout to grep, so `set -e`
    # saw grep's exit status and the step merely looked quiet. A REPORT
    # MUST NEVER BE ABLE TO STOP A STAGE FROM WRITING ITS RESULT.
    counts = [("resolved in", s.get("resolved_in", 0)),
              ("proposed nodes", s.get("nodes_out", 0)),
              ("new split pieces", s.get("j8s_pieces_made", 0)),
              ("dropped", s.get("dropped", 0)),
              ("box swaps", s.get("j8_box_swapped", 0)),
              ("merged away", s.get("j1_merged_away", 0)),
              ("product annotations", s.get("j9_annotated", 0)),
              ("edges", s.get("edges_out", 0)),
              ("conflicts", s.get("conflicts", 0)),
              ("open questions", s.get("open_questions", 0))]
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
<h1>PHASE C &middot; MATERIALIZE THE VOTE &mdash; {esc(m.scene)}</h1>
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
                    help="accepted for backward compatibility; writing is "
                         "now the default (use --dry-run to opt out)")
    ap.add_argument("--dry-run", action="store_true",
                    help="report what would happen and write nothing")
    ap.add_argument("--report-only", action="store_true",
                    help="write graph/materialize_report.html but NOT the "
                         "graph")
    ap.add_argument("--settle-only", action="store_true",
                    help="PHASE 1: settle geometry + the node set (J8 box "
                         "rulings, J8s splits, J1 merges) and stop, so J9 "
                         "can judge the settled layer instead of the raw "
                         "vote manifest. Run again without this flag "
                         "afterwards to fold J9's annotations in.")
    a = ap.parse_args()

    m = Materialize(a.scene).run(settle_only=a.settle_only)
    if a.settle_only:
        print("\n[materialize] PHASE 1 (settle only) -- J9 annotations NOT "
              "applied; run graph/judge_same_product.py next, then this "
              "again without --settle-only")
    m.print_report()

    rpath = m.sdir / "graph" / "materialize_report.html"
    if a.dry_run:
        print("\n[materialize] DRY -- nothing written "
              "(this is --dry-run; omit it to write)")
        return
    try:
        write_report(m, rpath)
        print(f"\n[materialize] wrote {rpath}")
    except Exception as e:                              # noqa: BLE001
        print(f"\n[materialize] REPORT FAILED ({type(e).__name__}: "
              f"{str(e)[:160]}) -- continuing; the layer is still written")
    if a.report_only:
        print("[materialize] --report-only: graph NOT written")
        return

    # PHASE 1 writes its OWN layer: resolved -> voted -> settled -> voted.
    # Each stage's output is a whole graph named for the stage that made
    # it, so "the newest layer" is always unambiguous.
    out_layer = "settled" if a.settle_only else LAYER
    before = {k: v for k, v in m.graph.items() if k != out_layer}
    m.graph[out_layer] = m.layer()
    scene_state.stamp(m.graph, out_layer)   # declare it IN THE FILE
    # This pass runs straight after two GPU stages, which is exactly when
    # the machine is most likely to cut out (docs/POWER_CRASHES.md), so
    # the graph is written beside itself and renamed rather than
    # truncated and re-streamed. See paths.write_atomic.
    paths.write_atomic(m.gpath, json.dumps(m.graph, indent=1))

    after = json.loads(m.gpath.read_text(encoding="utf-8"))
    changed = [k for k in set(before) | (set(after) - {out_layer})
               if k != "layer"
               if json.dumps(before.get(k), sort_keys=True)
               != json.dumps(after.get(k), sort_keys=True)]
    print(f"[materialize] wrote graph['{out_layer}'] into {m.gpath} "
          f"({len(m.nodes)} nodes)")
    print(f"[materialize] additive check: "
          f"{'PASS' if not changed else '*** FAIL: ' + str(changed) + ' ***'}"
          f" -- {len(before)} other top-level blocks compared "
          f"({', '.join(sorted(before))})")


if __name__ == "__main__":
    main()
