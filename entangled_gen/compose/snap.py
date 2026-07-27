"""
STEP 3 COMPOSE+LOOP, 3.2 PHYSICAL / PH1 v0 -- SNAP ANALYZER.

Deterministic, ZERO LLM (standing rule: code interprets the numbers).
v0 runs on the graph's OWN boxes as proxy geometry -- no cast list
needed: for every object it computes the pose correction that would make
its TOP supported_by option physically exact (floor contact, wall flush,
parent-top contact). The correction DELTAS are the product: a large
delta = the box and its own support verdict disagree = suspect-box /
re-attribution EVIDENCE for the semantic loop (user 07-27: the physical
stage is deterministic and feeds back into the semantic loop -- a loop
within a loop). When real assets arrive (S4 shopping), the same snap
math poses meshes; this analyzer's contract does not change.

Snap rules by the top option's `how`:
  rests_on arch_floor        bottom -> measured floor plane
  rests_on/leans_on object   bottom -> the SUPPORTER'S SNAPPED top --
                             but ONLY if the observed bottom is already
                             near that top (<= TOP_TOL). If the bottom
                             sits INSIDE the supporter's vertical span,
                             the real support is an interior board the
                             box model doesn't carry -> INTERNAL_SURFACE,
                             no move (the observed height IS the shelf).
  mounted_on/hangs_from wall nearest face -> flush to the wall plane
                             (horizontal move only; mounting height is
                             observed truth)
  mounted_on/hangs_from ceil top -> measured ceiling plane
  inside / embedded_in       no move (container interior / architecture)

Ordering guarantee: supporters snap BEFORE what rests on them (support-
chain depth), so a dependent lands on its parent's corrected top.

Output out/<scene>/compose/snap.json -- ANALYZER LAYER ONLY: the graph
and its boxes stay verbatim; snapped boxes exist only here.

Run:
  python compose/snap.py --scene bedroom_marble
"""
import argparse
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

LARGE_CORRECTION = 0.10   # m -- flag threshold: box vs verdict disagree
TOP_TOL = 0.35            # m -- "near the supporter's top" window (matches
                          # the beneath-scan generosity: occlusion-
                          # truncated boxes)
CHAIN_MAX = 12

WALL_AXIS = {"x": 0, "z": 2}


def phys_h(y_raw):
    """Physical height (m, up positive) of a raw y (up = -y frame)."""
    return -y_raw


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()

    gpath = paths.scene_dir(args.scene) / "scene_graph.json"
    graph = json.loads(gpath.read_text(encoding="utf-8"))
    res = graph["resolved"]
    boxes = {n["id"]: {"mn": list(n["geometry"]["aabb_min"]),
                       "mx": list(n["geometry"]["aabb_max"])}
             for n in res["nodes"]}
    names = {n["id"]: n["name"] for n in res["nodes"]}
    planes = {n["id"]: n["geometry"]["plane"] for n in graph["nodes"]
              if n["id"].startswith("arch_")}
    floor_h = phys_h(planes["arch_floor"]["value_raw"])
    ceil_h = phys_h(planes["arch_ceiling"]["value_raw"])

    cdir = paths.compose_dir(args.scene)
    sbp = cdir / "supported_by.json"
    if not sbp.exists():
        raise SystemExit("[snap] no supported_by.json -- run "
                         "compose/supported_by.py first")
    sbL = json.loads(sbp.read_text(encoding="utf-8"))
    top = {}
    for o in sbL["objects"]:
        sb = o.get("supported_by")
        if sb:
            top[o["id"]] = sb[0]

    # support-chain depth: arch = 0; supporters snap before dependents
    def depth(oid, seen=None):
        seen = seen or set()
        if oid.startswith("arch_"):
            return 0
        if oid in seen or len(seen) > CHAIN_MAX:
            return 99                      # cycle guard (audit says none)
        t = top.get(oid)
        if not t:
            return 1
        return 1 + depth(t["supporter"], seen | {oid})

    order = sorted(boxes, key=lambda oid: (depth(oid), oid))

    snapped = {oid: {"mn": list(b["mn"]), "mx": list(b["mx"])}
               for oid, b in boxes.items()}
    records = []
    for oid in order:
        b = snapped[oid]
        t = top.get(oid)
        rec = {"id": oid, "name": names[oid],
               "how": t["how"] if t else None,
               "supporter": t["supporter"] if t else None,
               "delta_raw": [0.0, 0.0, 0.0], "magnitude_m": 0.0,
               "disposition": None}

        def shift(axis, d):
            b["mn"][axis] += d
            b["mx"][axis] += d
            rec["delta_raw"][axis] = round(d, 4)

        if t is None:
            rec["disposition"] = "UNRESOLVED"
        else:
            how, sup = t["how"], t["supporter"]
            if how in ("inside", "embedded_in"):
                rec["disposition"] = ("INSIDE_CONTAINER"
                                      if how == "inside" else "EMBEDDED")
            elif sup == "arch_floor":
                # bottom (max raw y) -> floor plane
                d = (-floor_h) - b["mx"][1]
                shift(1, d)
                rec["disposition"] = "SNAPPED_FLOOR"
            elif sup == "arch_ceiling":
                # top (min raw y) -> ceiling plane
                d = (-ceil_h) - b["mn"][1]
                shift(1, d)
                rec["disposition"] = "SNAPPED_CEILING"
            elif sup.startswith("arch_wall"):
                pl = planes[sup]
                ax = WALL_AXIS[pl["axis"]]
                inward = pl["inward_normal_raw"][ax]
                v = pl["value_raw"]
                d = (v - b["mn"][ax]) if inward > 0 else (v - b["mx"][ax])
                shift(ax, d)
                rec["disposition"] = "SNAPPED_WALL_FLUSH"
            else:
                # object supporter (rests_on / leans_on): supporter is
                # already snapped (ordering) -- its top in phys h
                sb2 = snapped.get(sup)
                if sb2 is None:
                    rec["disposition"] = "SUPPORTER_MISSING"
                else:
                    sup_top_h = phys_h(sb2["mn"][1])
                    bottom_h = phys_h(b["mx"][1])
                    if bottom_h < sup_top_h - TOP_TOL:
                        # bottom deep inside the supporter's span: the
                        # real surface is an interior board (bookshelf
                        # shelves) the box model doesn't carry
                        rec["disposition"] = "INTERNAL_SURFACE"
                    else:
                        d = (-sup_top_h) - b["mx"][1]
                        shift(1, d)
                        rec["disposition"] = "SNAPPED_ON_OBJECT"

        rec["magnitude_m"] = round(sum(x * x for x in
                                       rec["delta_raw"]) ** 0.5, 4)
        if rec["magnitude_m"] > LARGE_CORRECTION:
            rec["flag"] = "LARGE_CORRECTION"
        rec["snapped_aabb"] = {"mn": [round(x, 4) for x in b["mn"]],
                               "mx": [round(x, 4) for x in b["mx"]]}
        records.append(rec)

    from collections import Counter
    disp = Counter(r["disposition"] for r in records)
    large = sorted((r for r in records if r.get("flag")),
                   key=lambda r: -r["magnitude_m"])
    layer = {
        "scene": args.scene, "built": str(date.today()),
        "generated_by": "compose/snap.py",
        "note": ("PH1 v0 ANALYZER on the graph's own boxes: corrections "
                 "that would make each TOP supported_by option exact. "
                 "Graph/boxes verbatim -- snapped boxes live only here. "
                 "LARGE_CORRECTION = box and verdict disagree -> semantic-"
                 "loop evidence (suspect box / wrong support). Same snap "
                 "math will pose real meshes after S4 shopping."),
        "params": {"large_correction_m": LARGE_CORRECTION,
                   "top_tol_m": TOP_TOL},
        "counts": {"objects": len(records), **disp,
                   "large_corrections": len(large)},
        "objects": records,
    }
    opath = cdir / "snap.json"
    opath.write_text(json.dumps(layer, indent=1), encoding="utf-8")
    print(f"[snap] wrote {opath}")
    print(f"[snap] dispositions: {json.dumps(dict(disp))}")
    print(f"[snap] LARGE corrections (> {LARGE_CORRECTION} m): "
          f"{len(large)}")
    for r in large:
        print(f"    {r['id']} ({r['name']}) {r['how']} -> "
              f"{r['supporter']}: {r['magnitude_m']} m "
              f"[{r['disposition']}]")


if __name__ == "__main__":
    main()
