"""
SHOPPING (compose lane, after propose_edits; replaces the dissolved
screening stage -- see docs/PLAN_SHOPPING.md for the rulings).

Produces ORDERED ASSET CANDIDATES from the objathor library for each
ANCHOR-tier object box in the scene state (real detections + accepted
adds + swap-ins). The fit loop (NEXT module, not built here) walks each
candidate list until one fits; sub-objects are listed but DEFERRED --
they get shopped per anchor after that anchor's real mesh is settled
(user: "limit the search tree").

The library-match step IS the filter: an item whose name matches no
catalog category is not bought (status NO_MATCH -- e.g. a door handle
when the library has no such category; the door asset covers it).
Nothing is checked against the original scene pixels (sandbox ruling).

Reuses composition/retrieve2.py: tiered category match, orientation-
aware size-fit shortlist (aspect residual + |log scale| + upright
penalty + tiling), mount filter, and ONE batched label-mapper call for
names with no lexical category match (--no-llm skips it: those items
become NO_MATCH honestly).

Output: out/<scene>/compose/shopping.json (candidates ordered best
first, boxes verbatim from the scene state).

Run:
  python compose/shopping.py --scene bedroom_marble
  python compose/shopping.py --scene bedroom_marble --no-llm
"""
import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

sys.path.insert(0, str(paths.REPO_ROOT / "composition"))
import retrieve2  # noqa: E402

TOP_N = 24
WALLISH = ("mounted_on", "hangs_from", "embedded_in")
ARCH_CLASS_WORDS = ("door", "window", "curtain")


def mount_of_support(supporter, how):
    if supporter == "arch_ceiling":
        return "ceiling"
    if supporter.startswith("arch_wall") or (how or "") in WALLISH:
        return "wall"
    return "floor"


def shortlist(name, box_size, mount, cats):
    if mount == "ceiling":
        # _mount_ok knows onWall/onFloor only; prefer onCeiling if the
        # catalog carries the flag, else rank the whole category pool
        rows = []
        for cat in cats:
            pool = retrieve2.by_category()[cat]
            pool = [a for a in pool if a.get("onCeiling")] or pool
            for a in pool:
                sc, k, axis, perm, scale, resid, ls = \
                    retrieve2.best_fit_config(box_size, a)
                rows.append({"uid": a["uid"], "category": a["category"],
                             "description": a["description"],
                             "size_cm": a["size_yup_cm"],
                             "score": round(sc, 3), "k": k, "axis": axis,
                             "perm": perm, "scale": round(scale, 3),
                             "aspect_resid": round(resid, 3),
                             "log_scale": round(ls, 3)})
        rows.sort(key=lambda r: r["score"])
        return rows[:TOP_N]
    return retrieve2.shortlist_box({"size": box_size}, mount, cats,
                                   n=TOP_N)


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--no-llm", action="store_true",
                    help="skip the unmatched-label mapper call")
    ap.add_argument("--model", default="sonnet")
    args = ap.parse_args()

    cdir = paths.compose_dir(args.scene)
    graph = json.loads((paths.scene_dir(args.scene) / "scene_graph.json")
                       .read_text(encoding="utf-8"))
    sbL = json.loads((cdir / "supported_by.json")
                     .read_text(encoding="utf-8"))
    ep = json.loads((cdir / "edit_proposals.json")
                    .read_text(encoding="utf-8"))

    nodes = {n["id"]: n for n in graph["resolved"]["nodes"]}
    top_sup = {}
    for o in sbL["objects"]:
        t = (o.get("supported_by") or [{}])[0]
        if t.get("supporter"):
            top_sup[o["id"]] = (t["supporter"], t.get("how", ""))

    def anchor_root(oid, depth=0):
        """The anchor a sub ultimately rests under (or oid if anchor)."""
        sup = top_sup.get(oid)
        if sup is None or sup[0].startswith("arch_") or depth > 4:
            return oid
        return anchor_root(sup[0], depth + 1)

    swapped_out = {o for s in ep["swaps"] if s.get("feasible")
                   for o in s["out"]}

    # ---- collect items: (id, name, box, tier, mount/host, source) ----
    items, subs = [], []
    for oid, n in sorted(nodes.items()):
        if oid in swapped_out:
            continue
        sup, how = top_sup.get(oid, ("arch_floor", ""))
        rec = {"id": oid, "name": n["name"], "source": "detected",
               "box": n["geometry"]}
        if sup.startswith("arch_"):
            rec["mount"] = mount_of_support(sup, how)
            items.append(rec)
        else:
            rec["host"] = sup
            rec["anchor"] = anchor_root(oid)
            subs.append(rec)

    for a in ep["adds"]:
        if not a.get("box"):
            continue
        rec = {"id": a["id"], "name": a["name"], "source": "add",
               "box": a["box"]}
        if a["support"] in ("floor", "wall", "ceiling"):
            rec["mount"] = ("wall" if a["support"] == "wall" else
                            a["support"])
            items.append(rec)
        else:
            rec["host"] = a["anchor"]
            rec["anchor"] = anchor_root(a["anchor"])
            subs.append(rec)

    for s in ep["swaps"]:
        if not s.get("feasible"):
            continue
        first_out = s["out"][0]
        sup, how = top_sup.get(first_out, ("arch_floor", ""))
        first_in = None
        for i, ir in enumerate(s["in"]):
            if not ir.get("box"):
                continue
            rec = {"id": ir["id"], "name": ir["name"],
                   "source": "swap_in", "box": ir["box"],
                   "replaces": s["out"]}
            if i == 0:
                first_in = ir["id"]
                if sup.startswith("arch_"):
                    rec["mount"] = mount_of_support(sup, how)
                    items.append(rec)
                else:
                    rec["host"] = sup
                    rec["anchor"] = anchor_root(first_out)
                    subs.append(rec)
            else:   # later in-items sit on the first (shelf -> vase)
                rec["host"] = first_in
                rec["anchor"] = first_in
                subs.append(rec)
        # children of the outs re-hang on the first in-item
        for kid in s.get("out_children", []):
            for r in subs:
                if r["id"] == kid:
                    r["host"] = first_in
                    r["anchor"] = first_in

    # ---- category match (code tiers, then ONE call for the rest) ----
    for r in items:
        tier, cats = retrieve2.match_categories(r["name"])
        r["match_tier"], r["categories"] = tier, cats
    unmatched = sorted({r["name"] for r in items if not r["categories"]})
    if unmatched and not args.no_llm:
        try:
            got = retrieve2.map_labels_agent(unmatched, model=args.model)
            for r in items:
                if not r["categories"] and r["name"] in got:
                    r["categories"] = got[r["name"]]
                    r["match_tier"] = "agent"
        except Exception as ex:   # honest degrade: NO_MATCH stands
            print(f"[shopping] label mapper failed: {ex}")

    # ---- shortlists ----
    for r in items:
        r["arch_class"] = any(w in r["name"] for w in ARCH_CLASS_WORDS)
        if not r["categories"]:
            r["status"], r["candidates"] = "NO_MATCH", []
            continue
        box_size = r["box"]["size"]
        r["candidates"] = shortlist(r["name"], box_size, r["mount"],
                                    r["categories"])
        r["status"] = "CANDIDATES" if r["candidates"] else "NO_MATCH"

    layer = {
        "scene": args.scene, "built": str(date.today()),
        "elapsed_s": round(time.time() - t0, 1),
        "generated_by": "compose/shopping.py",
        "graph_fingerprint": paths.graph_fingerprint(args.scene),
        "tier": "anchors",
        "note": ("ordered candidates per ANCHOR box; the fit loop (next "
                 "module) walks each list until fit. Subs deferred per "
                 "anchor. NO_MATCH = not bought, host asset covers it. "
                 "Boxes verbatim from graph/edit_proposals."),
        "counts": {
            "anchors": len(items),
            "with_candidates": sum(1 for r in items
                                   if r["status"] == "CANDIDATES"),
            "no_match": sum(1 for r in items
                            if r["status"] == "NO_MATCH"),
            "subs_deferred": len(subs),
            "swapped_out": sorted(swapped_out)},
        "items": items,
        "subs_deferred": subs,
    }
    opath = cdir / "shopping.json"
    opath.write_text(json.dumps(layer, indent=1), encoding="utf-8")
    print(f"[shopping] wrote {opath} ({time.time() - t0:.0f}s)")
    print(f"[shopping] counts: {json.dumps(layer['counts'], indent=1)}")
    for r in items:
        head = (f'    {r["id"]} "{r["name"]}" [{r["mount"]}'
                + (", arch" if r["arch_class"] else "")
                + f'] tier={r["match_tier"]}')
        if r["status"] == "NO_MATCH":
            print(head + " -> NO MATCH (not bought)")
            continue
        print(head + f' -> {len(r["candidates"])} candidates')
        for c in r["candidates"][:3]:
            print(f'        {c["score"]:6.3f} x{c["k"]} {c["category"]:<20.20s}'
                  f' {c["description"][:60]}')
    for r in subs[:200]:
        print(f'    SUB {r["id"]} "{r["name"]}" on {r["host"]} '
              f'(anchor {r["anchor"]}) -- deferred')


if __name__ == "__main__":
    main()
