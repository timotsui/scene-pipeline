"""
Pass 1 -- RECORD, step 2: geometric edges + the SAME_CANDIDATE queue.

Reads the node-only record written by graph/build_graph.py and rewrites the
SAME file with the edges array filled + an edge_summary block. Standalone +
idempotent (pure function of the node geometry; rerunning reproduces the
same edges). Still RECORD: threshold arithmetic on boxes, zero model calls,
every edge carries its numbers. NEXT-TO / adjacency is deliberately ABSENT
(a judge-side v2 pass). Reworked 2026-07-26 for the pano-track record
(analyzer-era z_fabricated caveats retired -- pano boxes are measured by
z-buffer lift + robust merge, not fabricated).

FRAME: RAW gen_raw.ply space, physical up = -y (rot180). Physical height
h = -y_raw. A box's physical BOTTOM face is its MAX raw y (aabb_max[1]);
its physical TOP face is its MIN raw y. The floor plane is the numeric MAX
y plane. Getting this sign wrong inverts every ON edge -- a generic numeric
self-check below verifies that at least one bed/rug-labeled node (when one
exists) is ON arch_floor and that NOTHING is ON arch_ceiling; exits 1 on
failure.

---------------------------------------------------------------------------
EDGE TYPES + THRESHOLDS (documented choices; every edge carries numeric
evidence -- auditable, not vibes)
---------------------------------------------------------------------------
Every edge: {type, a, b, evidence: {numbers}, caveats: []}.

ON (a supported-by b):
  contact test between a's physical bottom and b's physical top:
      gap_m = bottom_h(a) - top_h(b)      (+ = air between, - = penetration)
  accepted when -0.15 <= gap_m <= +0.08 AND the horizontal (xz) overlap
  covers >= 30% of a's footprint. Thresholds carried over from v1 where
  they were calibrated; the penetration side stays wide because merged
  boxes still over-reach (robust-merge unions + recenter refinements).
  Single best supporter = smallest |gap_m| (tie: larger overlap). Pairs
  already holding an IN edge are excluded (containment wins over support).
  Fallback: floor test, gap_floor_m = floor_y - aabb_max[1]; ON arch_floor
  when gap_floor_m <= +0.15 AND (>= -0.15 OR the box STRADDLES the floor:
  bottom below the plane, center physically above). The +-0.15 band is the
  v1 calibration; pano-track floor gaps measure far tighter (min +0.012),
  revisit after the record review.

IN (containment; smaller-volume box IN larger):
  overlap_volume / volume(smaller) >= 0.6. Detection-node pairs only.

IN_WALL / ATTACHED (ceiling) -- ALL detection nodes vs envelope planes
  (label-blind by design: windows/doors are ordinary object nodes since
  07-26; whether a node hugs a wall is a geometric FACT the judge uses,
  not a typing decision):
  IN_WALL: node box within 0.10 m of the nearest envelope wall plane.
  ATTACHED: node box within 0.10 m of the ceiling plane.
  (v1's curtain->window label rule DROPPED: label-conditioned semantics
  belong to the judge, not the record.)

SAME_CANDIDATE (the open "same object or part?" questions -- computed HERE
  from geometry since the 07-26-late amendment: NO pre-merge dedup stage,
  the record keeps both objects of every suspect pair):
  detection-node pairs with IoU >= 0.40 AND (IoU >= 0.60 OR containment
  >= 0.90). Evidence: iou, containment, zone ("confident" = IoU >= 0.60,
  two boxes sharing most of their volume -- almost certainly one object
  detected twice; "gray" = IoU .40-.60 + containment >= .90 -- same-vs-
  part genuinely ambiguous), center height difference, both labels.
  status: "open" -- the judge pass resolves EVERY pair (confident zone
  included) to SAME / DISTINCT (v2 08-01; PART_OF retired -- fragments
  are SAME, contents DISTINCT); merging is a judge VERDICT,
  never a record operation. These pairs are excluded from IN and
  INTERPENETRATES (already represented). High-containment LOW-IoU nesting
  (book in shelf, IoU < 0.40) stays plain IN -- unchanged.

NESTING (record fact, user ruling 08-01 -- "if future runs always add
this, it's permissible"): every detection pair with containment >=
SC_CONTAIN (0.90) writes a `nesting` entry onto the SMALLER node:
{host, host_label, containment, iou, same_candidate} -- the box-inside-
box facts the SAME_CANDIDATE IoU floor deliberately excludes (shelf
board fully inside its bookshelf scores containment 1.0 but IoU 0.29
and is never nominated; the R5b shelf-nest reconstruction had to
recompute these by hand). Deterministic, produced identically every
run, sorted (containment desc, host id). Consumers: viewer object card,
the planned semantic-dedup nomination.

INTERPENETRATES (unordered; a < b by id):
  detection-node pairs with box overlap volume > 0.001 m3 that hold NO
  other edge. Evidence: overlap volume + fraction of the smaller box.

NEAR (fallback — the "no standing floaters" invariant, user 2026-07-26:
  with a measured shell, every object must connect to SOMETHING):
  any detection node with NO structural edge (ON / IN / IN_WALL /
  ATTACHED) gets ONE NEAR edge to its geometrically best candidate —
  nearest supporter top (xz overlap >= 0.2), floor, ceiling, or wall
  plane INCLUDING the wall's recorded parallel surfaces (a picture can
  hang on the visible wall face 0.2 m inside the structural plane).
  Explicitly caveated fallback_connection, status "unresolved" — the
  judge confirms or retypes it; the record never silently widens the
  real thresholds. Floor is always a candidate, so the invariant cannot
  fail.

Sanity lists (edge_summary + stdout; nothing invented):
  floating          detection nodes with no ON and no IN
  isolated_resolved nodes that needed a NEAR fallback (audit list)
  wall_attached     detection nodes holding IN_WALL / ATTACHED (fact list)
  underground       nodes whose center sits physically below the floor

Run:  python graph/build_edges.py --scene bedroom_marble
"""
import argparse
import json
import sys
from collections import namedtuple
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

TOL_ON_AIR = 0.08          # m, max air gap bottom(a) above top(b)
TOL_ON_PEN = 0.15          # m, max penetration of a's bottom into b
FLOOR_TOL = 0.15           # m, |gap| band around the floor plane
MIN_FOOT_OVERLAP = 0.30    # fraction of a's xz footprint over b
IN_FRAC = 0.60             # overlap volume / smaller volume
WALL_TOL = 0.10            # m, box-to-plane distance for IN_WALL / ceiling
INTERP_MIN_VOL = 0.001     # m3
SC_IOU_CONF = 0.60         # SAME_CANDIDATE confident zone: IoU >= this
SC_IOU_MIN = 0.40          # SAME_CANDIDATE floor: IoU >= this
SC_CONTAIN = 0.90          # gray zone also needs containment >= this


def h(y_raw):
    """Physical height from raw y (physical up = -y)."""
    return -y_raw


def overlap_1d(lo1, hi1, lo2, hi2):
    return max(0.0, min(hi1, hi2) - max(lo1, lo2))


def box_overlap_vol(a, b):
    v = 1.0
    for k in range(3):
        v *= overlap_1d(a["aabb_min"][k], a["aabb_max"][k],
                        b["aabb_min"][k], b["aabb_max"][k])
    return v


def xz_overlap_area(a, b):
    return (overlap_1d(a["aabb_min"][0], a["aabb_max"][0],
                       b["aabb_min"][0], b["aabb_max"][0])
            * overlap_1d(a["aabb_min"][2], a["aabb_max"][2],
                         b["aabb_min"][2], b["aabb_max"][2]))


def vol(g):
    s = g["size"]
    return s[0] * s[1] * s[2]


def interval_plane_dist(lo, hi, value):
    if lo <= value <= hi:
        return 0.0
    return min(abs(value - lo), abs(value - hi))


Derived = namedtuple(
    "Derived",
    # edges           the edge list, in emission order
    # nesting         {smaller node id: [nesting facts]} (already sorted);
    #                 the caller writes these onto the nodes
    # sc_pairs        the open_questions["same_candidate_pairs"] payload
    # edge_summary    the graph["edge_summary"] block (carries self_check)
    # counts_partial  the graph["counts"] keys this stage owns
    # self_check      {"passed": bool, "details": [...]} -- the SAME dict
    #                 object edge_summary["self_check"] holds; the caller
    #                 decides what a failure means (build_edges exits 1)
    "edges nesting sc_pairs edge_summary counts_partial self_check")


def derive_edges(det, env, floor_y, ceil_y, walls):
    """Derive every edge from box geometry alone. PURE: reads the node
    dicts, mutates nothing (the nesting facts are RETURNED, not written
    onto the nodes) and touches no file.

    det    detection nodes  [{id, label, geometry{aabb_min,aabb_max,
           center,size}, evidence{members}}]  -- iteration order is the
           edge order, so callers must pass a stable list
    env    envelope nodes keyed by id (arch_floor / arch_ceiling /
           arch_wall*), each with geometry.plane + evidence
    floor_y / ceil_y   raw-y plane values
    walls  {wall id: plane dict} for the x/z wall planes

    Extracted from main() 2026-08-07 for the Phase-B2 loop-back
    re-derive (graph/rederive_voted_edges.py), which runs the same
    derivation over the resolved nodes carrying voted boxes. Pure
    refactor: identical thresholds, iteration order, rounding and
    self-check.
    """
    label = {n["id"]: n["label"] for n in det}

    edges = []
    paired = set()          # frozenset({a,b}) for every emitted edge

    def add(etype, a, b, evidence, caveats, **extra):
        edges.append({"type": etype, "a": a, "b": b,
                      "evidence": evidence, "caveats": caveats, **extra})
        paired.add(frozenset((a, b)))

    # ---------------- SAME_CANDIDATE (computed from geometry) --------------
    # No pre-merge dedup stage (amendment 07-26 late): both objects of every
    # probable-duplicate pair are nodes; the pair itself is this open edge.
    sc_pairs = []
    nesting = {}            # smaller-node id -> [nesting facts]
    for i in range(len(det)):
        for j in range(i + 1, len(det)):
            ga, gb = det[i]["geometry"], det[j]["geometry"]
            ov = box_overlap_vol(ga, gb)
            if ov <= 0:
                continue
            va, vb = vol(ga), vol(gb)
            iou = ov / (va + vb - ov)
            contain = ov / min(va, vb)
            if contain >= SC_CONTAIN:
                small, big = ((det[i], det[j]) if va <= vb
                              else (det[j], det[i]))
                nesting.setdefault(small["id"], []).append({
                    "host": big["id"], "host_label": big["label"],
                    "containment": round(contain, 3),
                    "iou": round(iou, 3),
                    "same_candidate": iou >= SC_IOU_MIN})
            if iou >= SC_IOU_CONF:
                zone = "confident"
            elif iou >= SC_IOU_MIN and contain >= SC_CONTAIN:
                zone = "gray"
            else:
                continue
            hdiff = abs(h(ga["center"][1]) - h(gb["center"][1]))
            a, b = det[i]["id"], det[j]["id"]
            add("SAME_CANDIDATE", a, b,
                {"iou": round(iou, 3), "containment": round(contain, 3),
                 "zone": zone, "center_height_diff_m": round(hdiff, 3),
                 "labels": [det[i]["label"], det[j]["label"]]},
                [], status="open")
            sc_pairs.append({"a": a, "a_label": det[i]["label"],
                             "b": b, "b_label": det[j]["label"],
                             "iou": round(iou, 3),
                             "containment": round(contain, 3),
                             "zone": zone})
    # ---------------- nesting facts (sorted here; written by the caller) --
    for ents in nesting.values():
        ents.sort(key=lambda e: (-e["containment"], e["host"]))
    counts_partial = {"same_candidate_pairs": len(sc_pairs),
                      "nested_nodes": len(nesting)}

    # ---------------- IN (containment) ----------------
    in_pairs = set()
    for i in range(len(det)):
        for j in range(i + 1, len(det)):
            a, b = det[i], det[j]
            if frozenset((a["id"], b["id"])) in paired:
                continue          # SAME_CANDIDATE already represents it
            ov = box_overlap_vol(a["geometry"], b["geometry"])
            if ov <= 0:
                continue
            va, vb = vol(a["geometry"]), vol(b["geometry"])
            small, big = (a, b) if va <= vb else (b, a)
            frac = ov / min(va, vb)
            if frac >= IN_FRAC:
                add("IN", small["id"], big["id"],
                    {"overlap_vol_m3": round(ov, 5),
                     "frac_of_smaller": round(frac, 3),
                     "vol_small_m3": round(min(va, vb), 5),
                     "vol_big_m3": round(max(va, vb), 5)}, [])
                in_pairs.add(frozenset((a["id"], b["id"])))

    # ---------------- IN_WALL + ATTACHED (all nodes vs planes) -------------
    for n in det:
        g = n["geometry"]
        best = None
        for wid, plane in walls.items():
            k = 0 if plane["axis"] == "x" else 2
            d = interval_plane_dist(g["aabb_min"][k], g["aabb_max"][k],
                                    plane["value_raw"])
            if best is None or d < best[1]:
                best = (wid, d, plane)
        if best and best[1] <= WALL_TOL:
            wid, d, plane = best
            # on-wall footprint: the node's box projected onto the wall —
            # tangent (horizontal along the wall) + vertical intervals, RAW.
            tcol = 2 if plane["axis"] == "x" else 0
            add("IN_WALL", n["id"], wid,
                {"wall_distance_m": round(d, 3), "wall_axis": plane["axis"],
                 "wall_value_raw": plane["value_raw"],
                 "on_wall_tangent_raw": [round(g["aabb_min"][tcol], 3),
                                         round(g["aabb_max"][tcol], 3)],
                 "on_wall_y_raw": [round(g["aabb_min"][1], 3),
                                   round(g["aabb_max"][1], 3)]}, [])
        dc = interval_plane_dist(g["aabb_min"][1], g["aabb_max"][1], ceil_y)
        if dc <= WALL_TOL:
            add("ATTACHED", n["id"], "arch_ceiling",
                {"ceiling_distance_m": round(dc, 3), "rule": "ceiling_plane"},
                [])

    # ---------------- ON (support) ----------------
    supported = {}
    for a in det:
        ga = a["geometry"]
        bottom_h = h(ga["aabb_max"][1])
        foot_a = ga["size"][0] * ga["size"][2]
        best = None
        for b in det:
            if b["id"] == a["id"]:
                continue
            if frozenset((a["id"], b["id"])) in in_pairs:
                continue          # containment wins over support
            gb = b["geometry"]
            top_h = h(gb["aabb_min"][1])
            gap = bottom_h - top_h
            if not (-TOL_ON_PEN <= gap <= TOL_ON_AIR):
                continue
            frac = xz_overlap_area(ga, gb) / foot_a if foot_a > 0 else 0.0
            if frac < MIN_FOOT_OVERLAP:
                continue
            cand = (abs(gap), -frac, gap, b["id"])
            if best is None or cand < best:
                best = cand
        if best is not None:
            _, negfrac, gap, bid = best
            add("ON", a["id"], bid,
                {"gap_m": round(gap, 3),
                 "overlap_frac_of_a": round(-negfrac, 3),
                 "supporter": "object"}, [])
            supported[a["id"]] = bid
            continue
        # floor fallback
        gap_floor = floor_y - ga["aabb_max"][1]     # = floor_h - bottom_h
        center_above = h(ga["center"][1]) > h(floor_y)
        straddle = gap_floor < 0 and center_above
        if gap_floor <= FLOOR_TOL and (gap_floor >= -FLOOR_TOL or straddle):
            add("ON", a["id"], "arch_floor",
                {"gap_m": round(gap_floor, 3),
                 "straddles_floor": straddle,
                 "supporter": "floor"}, [])
            supported[a["id"]] = "arch_floor"

    # ---------------- INTERPENETRATES ----------------
    interp = []
    for i in range(len(det)):
        for j in range(i + 1, len(det)):
            a, b = det[i], det[j]
            if frozenset((a["id"], b["id"])) in paired:
                continue
            ov = box_overlap_vol(a["geometry"], b["geometry"])
            if ov <= INTERP_MIN_VOL:
                continue
            frac = ov / min(vol(a["geometry"]), vol(b["geometry"]))
            interp.append((ov, a["id"], b["id"], frac))
    interp.sort(reverse=True)
    for ov, aid, bid, frac in interp:
        add("INTERPENETRATES", aid, bid,
            {"overlap_vol_m3": round(ov, 5),
             "frac_of_smaller": round(frac, 3)}, [])

    # ---------------- NEAR fallback: no standing floaters ------------------
    STRUCT = ("ON", "IN", "IN_WALL", "ATTACHED")
    connected = set()
    for e in edges:
        if e["type"] in STRUCT:
            connected.add(e["a"])
            connected.add(e["b"])
    isolated = [n for n in det if n["id"] not in connected]
    for n in isolated:
        g = n["geometry"]
        bottom_h = h(g["aabb_max"][1])
        foot_a = g["size"][0] * g["size"][2]
        cands = []
        for b in det:
            if b["id"] == n["id"]:
                continue
            gb = b["geometry"]
            frac = xz_overlap_area(g, gb) / foot_a if foot_a > 0 else 0.0
            if frac < 0.2:
                continue
            gap = bottom_h - h(gb["aabb_min"][1])
            cands.append((abs(gap), "support", b["id"],
                          {"gap_m": round(gap, 3),
                           "overlap_frac_of_a": round(frac, 3)}))
        gapf = floor_y - g["aabb_max"][1]
        cands.append((abs(gapf), "floor", "arch_floor",
                      {"gap_m": round(gapf, 3)}))
        dc = interval_plane_dist(g["aabb_min"][1], g["aabb_max"][1], ceil_y)
        cands.append((dc, "ceiling", "arch_ceiling",
                      {"distance_m": round(dc, 3)}))
        for wid, plane in walls.items():
            k = 0 if plane["axis"] == "x" else 2
            d = interval_plane_dist(g["aabb_min"][k], g["aabb_max"][k],
                                    plane["value_raw"])
            cands.append((d, "wall", wid, {"distance_m": round(d, 3)}))
            for ps in (env[wid]["evidence"].get("parallel_surfaces") or []):
                d2 = interval_plane_dist(g["aabb_min"][k], g["aabb_max"][k],
                                         ps["value_raw"])
                cands.append((d2, "wall", wid,
                              {"distance_m": round(d2, 3),
                               "via_parallel_surface_raw": ps["value_raw"]}))
        cands.sort(key=lambda c: c[0])
        _, hint, target, ev = cands[0]
        # truncation facts (J0, user 07-26): a box whose members were cut
        # off at view edges may under-reach its real extent (occluded plant
        # base) — evidence the judge weighs, not a conclusion
        members = n.get("evidence", {}).get("members", [])
        n_trunc = sum(1 for m in members if m.get("truncated"))
        # runners-up recorded too — a straddled parallel surface scores
        # distance 0 even when "on the floor, gap 0.19" is the truer
        # story; one candidate per (relation, target), judge decides
        alts, seen = [], {(hint, target)}
        for _, h2, t2, e2 in cands[1:]:
            if (h2, t2) in seen:
                continue
            seen.add((h2, t2))
            alts.append({"relation_hint": h2, "target": t2, **e2})
            if len(alts) == 3:
                break
        add("NEAR", n["id"], target,
            {"relation_hint": hint, **ev, "alternatives": alts,
             "members_truncated": [n_trunc, len(members)]},
            ["fallback_connection — outside normal thresholds; for the "
             "judge"], status="unresolved")
    isolated_resolved = [{"id": n["id"], "label": n["label"]}
                         for n in isolated]

    # ---------------- sanity lists ----------------
    contained = {e["a"] for e in edges if e["type"] == "IN"}
    floating = []
    for a in det:
        if a["id"] in supported or a["id"] in contained:
            continue
        gap_floor = floor_y - a["geometry"]["aabb_max"][1]
        floating.append({"id": a["id"], "label": a["label"],
                         "floor_gap_m": round(gap_floor, 3)})
    floating.sort(key=lambda f: f["floor_gap_m"])
    wall_attached = sorted({e["a"] for e in edges
                            if e["type"] in ("IN_WALL", "ATTACHED")})
    underground = [{"id": n["id"], "label": n["label"],
                    "center_below_floor_m":
                        round(h(floor_y) - h(n["geometry"]["center"][1]), 3)}
                   for n in det if h(n["geometry"]["center"][1]) < h(floor_y)]

    # ---------------- self-check (frame sign, generic) ----------------
    on_floor = {e["a"] for e in edges
                if e["type"] == "ON" and e["b"] == "arch_floor"}
    on_ceiling = [e for e in edges
                  if e["type"] == "ON" and e["b"] == "arch_ceiling"]
    anchor_labels = [n["id"] for n in det
                     if any(w in n["label"] for w in ("bed", "rug"))]
    checks = []
    ok = True
    if anchor_labels:
        hit = sorted(set(anchor_labels) & on_floor)
        passed = bool(hit)
        ok &= passed
        checks.append({"rule": "some bed/rug node ON floor",
                       "candidates": anchor_labels, "on_floor": hit,
                       "passed": passed})
    ok &= not on_ceiling
    checks.append({"rule": "nothing ON ceiling",
                   "passed": not on_ceiling})
    # invariant: every detection node connected (structural or NEAR)
    conn2 = set()
    for e in edges:
        if e["type"] in STRUCT + ("NEAR",):
            conn2.add(e["a"])
            conn2.add(e["b"])
    still_iso = [n["id"] for n in det if n["id"] not in conn2]
    ok &= not still_iso
    checks.append({"rule": "no standing floaters (every object connected)",
                   "isolated": still_iso, "passed": not still_iso})

    counts = {}
    for e in edges:
        counts[e["type"]] = counts.get(e["type"], 0) + 1

    self_check = {"passed": bool(ok), "details": checks}
    edge_summary = {
        "thresholds": {
            "on_air_gap_max_m": TOL_ON_AIR,
            "on_penetration_max_m": TOL_ON_PEN,
            "floor_band_m": FLOOR_TOL,
            "floor_straddle_rule": ("bottom below floor plane accepted when "
                                    "the box center is physically above it"),
            "min_footprint_overlap": MIN_FOOT_OVERLAP,
            "in_containment_frac": IN_FRAC,
            "wall_plane_dist_m": WALL_TOL,
            "interpenetrates_min_vol_m3": INTERP_MIN_VOL,
        },
        "edge_counts": counts,
        "floating": floating,
        "isolated_resolved_by_near": isolated_resolved,
        "wall_attached": wall_attached,
        "underground": underground,
        "top_interpenetrates": [
            {"a": aid, "b": bid, "labels": [label[aid], label[bid]],
             "overlap_vol_m3": round(ov, 5), "frac_of_smaller": round(fr, 3)}
            for ov, aid, bid, fr in interp[:10]],
        "self_check": self_check,
    }
    return Derived(edges, nesting, sc_pairs, edge_summary, counts_partial,
                   self_check)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    args = ap.parse_args()
    gpath = paths.scene_dir(args.scene) / "scene_graph.json"
    graph = json.loads(gpath.read_text())

    det = [n for n in graph["nodes"] if n["source"] == "detection"]

    env = {n["id"]: n for n in graph["nodes"] if n["source"] == "envelope"}
    floor_y = env["arch_floor"]["geometry"]["plane"]["value_raw"]
    ceil_y = env["arch_ceiling"]["geometry"]["plane"]["value_raw"]
    # any wall node (measured room_shell segments OR legacy grid-bound
    # placeholders) — id-agnostic so N-segment shells just work
    walls = {nid: n["geometry"]["plane"] for nid, n in env.items()
             if nid.startswith("arch_wall") and
             n["geometry"].get("plane", {}).get("axis") in ("x", "z")}

    d = derive_edges(det, env, floor_y, ceil_y, walls)
    edges, nesting = d.edges, d.nesting
    edge_summary, checks = d.edge_summary, d.self_check["details"]
    ok = d.self_check["passed"]
    counts = edge_summary["edge_counts"]
    floating = edge_summary["floating"]
    wall_attached = edge_summary["wall_attached"]
    underground = edge_summary["underground"]

    # ---------------- write (same key order as before the refactor) -------
    graph.setdefault("open_questions", {})["same_candidate_pairs"] = d.sc_pairs
    graph.setdefault("counts", {})["same_candidate_pairs"] = \
        d.counts_partial["same_candidate_pairs"]
    for n in det:                     # nesting facts onto nodes (idempotent)
        ents = nesting.get(n["id"])
        if ents:
            n["nesting"] = ents
        else:
            n.pop("nesting", None)
    graph["counts"]["nested_nodes"] = d.counts_partial["nested_nodes"]
    graph["edges"] = edges
    graph["edge_summary"] = edge_summary
    gpath.write_text(json.dumps(graph, indent=1))

    # ---------------- report ----------------
    print(f"[edges] wrote {gpath}")
    print(f"[edges] counts by type: {counts}")
    print(f"[edges] nesting facts: {sum(len(v) for v in nesting.values())} "
          f"entries on {len(nesting)} nodes (containment >= {SC_CONTAIN})")
    sc_edges = [e for e in edges if e["type"] == "SAME_CANDIDATE"]
    for e in sc_edges:
        print(f"           ? SAME_CANDIDATE [{e['evidence']['zone']:9s}] "
              f"{e['a']} <-> {e['b']} {e['evidence']['labels']} "
              f"iou {e['evidence']['iou']} "
              f"contain {e['evidence']['containment']}")
    print(f"[edges] floating objects ({len(floating)}; no support edge "
          f"invented):")
    for f in floating:
        print(f"           {f['id']} {f['label']:<18} floor_gap "
              f"{f['floor_gap_m']:+.3f} m")
    print(f"[edges] wall/ceiling-attached nodes: {len(wall_attached)}")
    ne = [e for e in edges if e["type"] == "NEAR"]
    print(f"[edges] NEAR fallbacks (no-floater invariant): {len(ne)}")
    for e in ne:
        print(f"           ~ {e['a']} → {e['b']} "
              f"[{e['evidence']['relation_hint']}] {e['evidence']}")
    if underground:
        print(f"[edges] underground centers: {underground}")
    print("[edges] top INTERPENETRATES by overlap volume:")
    for t in edge_summary["top_interpenetrates"]:
        la, lb = t["labels"]
        print(f"           {t['a']} ({la}) x {t['b']} ({lb}): "
              f"{t['overlap_vol_m3']:.4f} m3, "
              f"{t['frac_of_smaller']:.0%} of smaller")
    print(f"[edges] SELF-CHECK (frame sign): "
          f"{'PASS' if ok else '*** FAIL ***'}")
    for c in checks:
        print(f"           {c}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
