"""
Step 2 -- geometric-edges: fill the edges array of out/<scene>/scene_graph.json.

Reads the node-only graph written by graph/build_graph.py (Step 1) and rewrites
the SAME file with the edges array filled + an edge_summary block. Standalone +
idempotent (pure function of the node geometry; rerunning reproduces the same
edges). NEXT-TO / adjacency is deliberately ABSENT (deferred to the v2 VLM
pass per PLAN_SCENE_GRAPH.md section 2).

FRAME: RAW gen_raw.ply space, physical up = -y (rot180). Physical height
h = -y_raw. A box's physical BOTTOM face is its MAX raw y (aabb_max[1]); its
physical TOP face is its MIN raw y (aabb_min[1]). The floor plane is the
numeric MAX y plane (floor_y = +0.029 > ceiling_y = -2.793). Getting this sign
wrong inverts every ON edge -- a numeric self-check below verifies the
manifest-confirmed floor-standing objects (rug obj_006/ana_063, rug obj_018/
ana_065, bed obj_001/ana_072) end up ON arch_floor, and that NOTHING is ON
arch_ceiling; the script exits 1 if that check fails.

---------------------------------------------------------------------------
EDGE TYPES + THRESHOLDS (all documented choices; every edge carries numeric
evidence -- auditable, not vibes)
---------------------------------------------------------------------------
Every edge: {type, a, b, evidence: {numbers}, caveats: []}.

ON (a supported-by b; a = object-typed detection node):
  contact test between a's physical bottom and b's physical top:
      gap_m = bottom_h(a) - top_h(b)      (+ = air between, - = penetration)
  accepted when -0.15 <= gap_m <= +0.08 AND the horizontal (xz) overlap area
  covers >= 30% of a's footprint. The air side (+0.08) is inside the 3-8 cm
  spec range; the penetration side is widened to 0.15 m because the analyzer
  FABRICATES each box's depth extent as (w+h)/2 (bridged_boxes.json caveats):
  supporter tops are inflated physically UPWARD, so a truly-supported object's
  bottom systematically lands BELOW the inflated top (measured here: desk lamp
  ana_101 on desk ana_094 gap -0.139, monitor ana_100 on desk gap -0.103).
  Resolution: the SINGLE best supporter = smallest |gap_m| (tie: larger
  overlap fraction). Supporter candidates are object-typed detection nodes
  only; pairs already holding an IN edge are excluded (containment wins over
  support). Fallback: nodes with no object supporter are tested against the
  floor plane:
      gap_floor_m = floor_h - bottom_h(a) ... i.e. (floor_y - aabb_max[1])
  ON arch_floor when gap_floor_m <= +0.15 AND (gap_floor_m >= -0.15 OR the
  box STRADDLES the floor: bottom below the floor plane but center physically
  above it -- the fabricated-extent signature; rug ana_063 overshoots 0.274 m
  BELOW the floor while its center sits above). The +-0.15 floor band exceeds
  the 3-8 cm spec range DELIBERATELY, calibrated on the manifest-confirmed
  floor-standing set: bed ana_072 bottom sits 0.142 m above the floor plane
  (surface-bias / under-reach), planter ana_016 0.142, desk ana_094 0.112 --
  an 8 cm band would false-float all of them. The next cohort up starts at
  0.152 (duplicate shelf clusters), so 0.15 is the largest confirmed floor-
  stander + epsilon; anything beyond lands in the floating list instead of
  getting an invented edge.

IN (containment; smaller-volume box IN larger):
  overlap_volume / volume(smaller box) >= 0.6 (documented threshold; target
  case = books inside shelves). Detection-node pairs only. Carries caveat
  "z_fabricated" (overlap volumes are inflated by fabricated extents).

IN_WALL (architecture-typed DETECTION node -> envelope wall arch_wall_*):
  distance from the node's box (interval on the wall axis) to the nearest
  envelope wall plane <= 0.10 m (0 when the box straddles the plane).
  Nearest wall only.

ATTACHED:
  (a) architecture-typed detection node -> arch_ceiling when its box lies
      within 0.10 m of the ceiling plane (same rule as IN_WALL; gives ceiling
      lights their anchor -- documented extension of the wall rule);
  (b) curtain -> window when their boxes overlap in 3D, or their xz
      projections overlap with a vertical gap <= 0.10 m.

INTERPENETRATES (unordered; a < b by id):
  detection-node pairs with box overlap volume > 0.001 m3 that hold NO other
  edge (ON / IN / ATTACHED) between them. Evidence: overlap volume +
  normalized value (volume / smaller box volume). ALWAYS carries caveat
  "z_fabricated" -- fabricated depth extents inflate every overlap; the
  review page dims these.

Sanity lists (edge_summary block + stdout; nothing invented):
  floating              object-typed detection nodes with no ON and no IN
  unattached_architecture  architecture-typed detection nodes with no
                           IN_WALL / ATTACHED
  underground           nodes whose center sits physically below the floor

Run:  python graph/build_edges.py --scene bedroom_marble
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

TOL_ON_AIR = 0.08          # m, max air gap bottom(a) above top(b)
TOL_ON_PEN = 0.15          # m, max penetration of a's bottom into b
FLOOR_TOL = 0.15           # m, |gap| band around the floor plane (see docstring)
MIN_FOOT_OVERLAP = 0.30    # fraction of a's xz footprint over b
IN_FRAC = 0.60             # overlap volume / smaller volume
WALL_TOL = 0.10            # m, box-to-plane distance for IN_WALL / ceiling
CURTAIN_VGAP = 0.10        # m, vertical adjacency for curtain->window
INTERP_MIN_VOL = 0.001     # m3


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


def vol(n):
    s = n["size"]
    return s[0] * s[1] * s[2]


def interval_plane_dist(lo, hi, value):
    if lo <= value <= hi:
        return 0.0
    return min(abs(value - lo), abs(value - hi))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    args = ap.parse_args()
    gpath = paths.scene_dir(args.scene) / "scene_graph.json"
    graph = json.loads(gpath.read_text())

    det = [n for n in graph["nodes"] if n["source"] == "detection"]
    geom = {n["id"]: n["geometry"] for n in det}
    label = {n["id"]: n["label"] for n in det}
    objects = [n for n in det if n["type"] == "object"]
    arch_det = [n for n in det if n["type"] == "architecture"]

    env = {n["id"]: n for n in graph["nodes"] if n["source"] == "envelope"}
    floor_y = env["arch_floor"]["geometry"]["plane"]["value_raw"]
    ceil_y = env["arch_ceiling"]["geometry"]["plane"]["value_raw"]
    walls = {nid: env[nid]["geometry"]["plane"]
             for nid in ("arch_wall_x0", "arch_wall_x1",
                         "arch_wall_z0", "arch_wall_z1")}

    edges = []
    paired = set()          # frozenset({a,b}) for every emitted edge

    def add(etype, a, b, evidence, caveats):
        edges.append({"type": etype, "a": a, "b": b,
                      "evidence": evidence, "caveats": caveats})
        paired.add(frozenset((a, b)))

    # ---------------- IN (containment) ----------------
    in_pairs = set()
    for i in range(len(det)):
        for j in range(i + 1, len(det)):
            a, b = det[i], det[j]
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
                     "vol_big_m3": round(max(va, vb), 5)},
                    ["z_fabricated"])
                in_pairs.add(frozenset((a["id"], b["id"])))

    # ---------------- IN_WALL + ATTACHED (architecture) ----------------
    for n in arch_det:
        g = n["geometry"]
        # nearest wall plane
        best = None
        for wid, plane in walls.items():
            k = 0 if plane["axis"] == "x" else 2
            d = interval_plane_dist(g["aabb_min"][k], g["aabb_max"][k],
                                    plane["value_raw"])
            if best is None or d < best[1]:
                best = (wid, d, plane)
        if best and best[1] <= WALL_TOL:
            wid, d, plane = best
            add("IN_WALL", n["id"], wid,
                {"wall_distance_m": round(d, 3), "wall_axis": plane["axis"],
                 "wall_value_raw": plane["value_raw"]}, [])
        # ceiling attachment (same proximity rule against the ceiling plane)
        dc = interval_plane_dist(g["aabb_min"][1], g["aabb_max"][1], ceil_y)
        if dc <= WALL_TOL:
            add("ATTACHED", n["id"], "arch_ceiling",
                {"ceiling_distance_m": round(dc, 3), "rule": "ceiling_plane"},
                [])

    # curtain -> window
    curtains = [n for n in arch_det if n["label"] == "curtain"]
    windows = [n for n in arch_det if n["label"] == "window"]
    for c in curtains:
        for w in windows:
            gc, gw = c["geometry"], w["geometry"]
            ov = box_overlap_vol(gc, gw)
            xz = xz_overlap_area(gc, gw)
            # vertical gap between the y intervals (0 if they overlap)
            vgap = max(0.0, max(gc["aabb_min"][1], gw["aabb_min"][1])
                       - min(gc["aabb_max"][1], gw["aabb_max"][1]))
            if ov > 0 or (xz > 0 and vgap <= CURTAIN_VGAP):
                add("ATTACHED", c["id"], w["id"],
                    {"overlap_vol_m3": round(ov, 5),
                     "xz_overlap_m2": round(xz, 4),
                     "vertical_gap_m": round(vgap, 3),
                     "rule": "curtain_window"}, ["z_fabricated"])

    # ---------------- ON (support) ----------------
    supported = {}
    for a in objects:
        ga = a["geometry"]
        bottom_h = h(ga["aabb_max"][1])
        foot_a = ga["size"][0] * ga["size"][2]
        best = None
        for b in objects:
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
                 "supporter": "object"},
                ["z_fabricated"])
            supported[a["id"]] = bid
            continue
        # floor fallback
        gap_floor = floor_y - ga["aabb_max"][1]     # = floor_h - bottom_h
        center_above = h(ga["center"][1]) > h(floor_y)
        straddle = gap_floor < 0 and center_above
        if gap_floor <= FLOOR_TOL and (gap_floor >= -FLOOR_TOL or straddle):
            cav = [] if -TOL_ON_AIR <= gap_floor <= TOL_ON_AIR \
                else ["z_fabricated"]
            add("ON", a["id"], "arch_floor",
                {"gap_m": round(gap_floor, 3),
                 "straddles_floor": straddle,
                 "supporter": "floor"}, cav)
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
             "frac_of_smaller": round(frac, 3)}, ["z_fabricated"])

    # ---------------- sanity lists ----------------
    contained = {e["a"] for e in edges if e["type"] == "IN"}
    floating = []
    for a in objects:
        if a["id"] in supported or a["id"] in contained:
            continue
        gap_floor = floor_y - a["geometry"]["aabb_max"][1]
        floating.append({"id": a["id"], "label": a["label"],
                         "floor_gap_m": round(gap_floor, 3),
                         "tier": a["confidence_tier"]})
    floating.sort(key=lambda f: f["floor_gap_m"])
    anchored = {e["a"] for e in edges if e["type"] in ("IN_WALL", "ATTACHED")}
    unattached_arch = [{"id": n["id"], "label": n["label"],
                        "tier": n["confidence_tier"]}
                       for n in arch_det if n["id"] not in anchored]
    underground = [{"id": n["id"], "label": n["label"],
                    "center_below_floor_m":
                        round(h(floor_y) - h(n["geometry"]["center"][1]), 3)}
                   for n in det if h(n["geometry"]["center"][1]) < h(floor_y)]

    # ---------------- self-check (frame sign) ----------------
    # manifest-confirmed floor-standing objects must be ON arch_floor
    must_floor = {"obj_006": None, "obj_018": None, "obj_001": None}
    for n in det:
        mid = n["provenance"].get("matched_manifest_id")
        if mid in must_floor:
            must_floor[mid] = n["id"]
    on_floor = {e["a"]: e for e in edges
                if e["type"] == "ON" and e["b"] == "arch_floor"}
    on_ceiling = [e for e in edges
                  if e["type"] == "ON" and e["b"] == "arch_ceiling"]
    checks = []
    ok = True
    for mid, nid in must_floor.items():
        e = on_floor.get(nid)
        passed = e is not None
        ok &= passed
        checks.append({"manifest_id": mid, "node": nid,
                       "on_floor": passed,
                       "gap_m": e["evidence"]["gap_m"] if e else None})
    ok &= not on_ceiling
    checks.append({"nothing_on_ceiling": not on_ceiling})

    counts = {}
    for e in edges:
        counts[e["type"]] = counts.get(e["type"], 0) + 1

    graph["edges"] = edges
    graph["edge_summary"] = {
        "thresholds": {
            "on_air_gap_max_m": TOL_ON_AIR,
            "on_penetration_max_m": TOL_ON_PEN,
            "floor_band_m": FLOOR_TOL,
            "floor_straddle_rule": ("bottom below floor plane accepted when "
                                    "the box center is physically above it "
                                    "(fabricated-extent overshoot)"),
            "min_footprint_overlap": MIN_FOOT_OVERLAP,
            "in_containment_frac": IN_FRAC,
            "wall_plane_dist_m": WALL_TOL,
            "curtain_window_vertical_gap_m": CURTAIN_VGAP,
            "interpenetrates_min_vol_m3": INTERP_MIN_VOL,
        },
        "edge_counts": counts,
        "floating": floating,
        "unattached_architecture": unattached_arch,
        "underground": underground,
        "top_interpenetrates": [
            {"a": aid, "b": bid, "labels": [label[aid], label[bid]],
             "overlap_vol_m3": round(ov, 5), "frac_of_smaller": round(fr, 3)}
            for ov, aid, bid, fr in interp[:10]],
        "self_check": {"passed": bool(ok), "details": checks},
    }
    gpath.write_text(json.dumps(graph, indent=1))

    # ---------------- report ----------------
    print(f"[edges] wrote {gpath}")
    print(f"[edges] counts by type: {counts}")
    print(f"[edges] floating objects ({len(floating)}; no support edge "
          f"invented):")
    for f in floating:
        print(f"           {f['id']} {f['label']:<18} floor_gap "
              f"{f['floor_gap_m']:+.3f} m  [{f['tier']}]")
    print(f"[edges] unattached architecture ({len(unattached_arch)}):")
    for u in unattached_arch:
        print(f"           {u['id']} {u['label']} [{u['tier']}]")
    if underground:
        print(f"[edges] underground centers: {underground}")
    print("[edges] top INTERPENETRATES by overlap volume:")
    for ov, aid, bid, fr in interp[:10]:
        print(f"           {aid} ({label[aid]}) x {bid} ({label[bid]}): "
              f"{ov:.4f} m3, {fr:.0%} of smaller")
    print(f"[edges] SELF-CHECK (frame sign): "
          f"{'PASS' if ok else '*** FAIL ***'}")
    for c in checks:
        print(f"           {c}")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
