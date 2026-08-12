"""
SHOPPING (compose lane, after propose_edits; replaces the dissolved
screening stage -- see docs/plans/PLAN_SHOPPING.md for the rulings).

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

FIT = NATIVE SIZE ONLY (user rulings 08-03B): no rescale -- a product
is judged at the size it really is. Configs tried: the two rotations
about the VERTICAL axis (nothing gets tipped over) x 1..3 side-by-side
copies along the box's long horizontal axis. Deviation per axis =
|native/box - 1| on normal axes, SYMMETRIC (too big is NOT assumed
worse); FLAT axes (box under 15 cm) measure ABSOLUTELY with a 15 cm
allowance (R-S2-125 -- a 2 cm detection slab must not veto a 4 cm
door). The fit metric = the WORST axis. Boxes are known-loose: <= 15%
on every axis earns the strict "fits" mark, but nothing is ruled out
for missing it -- the whole list ranks most-fit to least-fit.
DOWNSTREAM BAR (R-S2-124): fit_preview places NOTHING whose best
candidate exceeds DRY 0.65 -- better absent than wrong-sized; the
R-S2-127 substitute-category walk (meaning-nominated, sequential,
<= 3 aisles) runs first for hopeless items.

Reuses composition/retrieve2.py for the catalog + tiered category
match + mount filter + the ONE batched label-mapper call for names
with no lexical category match (--no-llm skips it: those items become
NO_MATCH honestly).

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

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'graph'))
import scene_state  # noqa: E402

sys.path.insert(0, str(paths.REPO_ROOT / "composition"))
import retrieve2  # noqa: E402

TOP_N = 24
WALLISH = ("mounted_on", "hangs_from", "embedded_in")
ARCH_CLASS_WORDS = ("door", "window", "curtain")
FIT_TOL = 0.15               # strict "fits" mark, NOT a cutoff
YAW_PERMS = ("xyz", "zyx")   # rotation about the vertical axis ONLY
MAX_TILES = 3
ROWABLE_CATS = ("book", "books")
# ^ categories allowed to tile k>1. The k-row convention (fill the
#   observed span with side-by-side copies) reads RIGHT for books and
#   FABRICATES objects everywhere else — one detected desk lamp became
#   3 tiled lamps, one monitor became twins (user 08-07, obj_039).
#   Grows into a catalog "rowable" tag when more row classes appear.


def mount_of_support(supporter, how):
    if supporter == "arch_ceiling":
        return "ceiling"
    if supporter.startswith("arch_wall") or (how or "") in WALLISH:
        return "wall"
    return "floor"


#: FLAT AXES MEASURE IN METERS, NOT PERCENT (user ruling 2026-08-12,
#: R-S2-125: "percentage only doesn't seem to be a reasonable metric...
#: anything less than 15cm is considered flat, and we can be slightly
#: generous with that number"). A door detected as a 2 cm slab made
#: every real 4 cm door read "100% wrong" on the axis that matters
#: least, and the worst-axis rule then vetoed doors, panels, rugs and
#: ceiling discs wholesale (the fresh04 thin-item massacre). On a flat
#: axis a miss within FLAT_TOL_M is FREE; beyond it, the excess counts
#: in units of FLAT_AXIS_M so it stays comparable to the ratio scale.
FLAT_AXIS_M = 0.15
FLAT_TOL_M = 0.15


def native_fit(box_size, size_cm, rowable=True):
    """NO RESCALE (user ruling 08-03B): the product is judged at its
    natural size. Configs = the two vertical-axis rotations x 1..3
    side-by-side copies along the box's long horizontal axis
    (rowable=False pins k=1: singular categories place ONE copy —
    the unfilled span is an honest fit deviation, not a reason to
    fabricate duplicates).
    Per-axis deviation: |native/box - 1| on normal axes, SYMMETRIC —
    shopping holds no too-big-is-worse assumption. On FLAT axes (box
    under FLAT_AXIS_M) the deviation is ABSOLUTE: free within
    FLAT_TOL_M, then the excess in units of FLAT_AXIS_M (R-S2-125).
    The fit metric = the WORST axis (lower = better, ties prefer fewer
    tiles). fits = every axis within FIT_TOL."""
    b0 = np.asarray(box_size, np.float64)
    a0 = np.asarray(size_cm, np.float64) / 100.0
    if b0.shape != (3,) or (b0 <= 0).any() or (a0 <= 0).any():
        return None
    best = None
    for k in range(1, (MAX_TILES if rowable else 1) + 1):
        s = b0.copy()
        axis = 0 if s[0] >= s[2] else 2
        s[axis] = s[axis] / k
        for perm in YAW_PERMS:
            a = a0[[retrieve2._AX[c] for c in perm]]
            ratio = np.abs(a / s - 1.0)
            absd = (np.maximum(np.abs(a - s) - FLAT_TOL_M, 0.0)
                    / FLAT_AXIS_M)
            dev = float(np.max(np.where(s < FLAT_AXIS_M, absd, ratio)))
            if best is None or (dev, k) < (best[0], best[1]):
                best = (dev, k, axis, perm)
    dev, k, axis, perm = best
    return {"score": round(dev, 3), "k": k, "axis": axis,
            "perm": perm, "scale": 1.0, "fits": dev <= FIT_TOL}


def shortlist(name, box_size, mount, cats):
    rows = []
    for cat in cats:
        pool = retrieve2.by_category()[cat]
        if mount == "ceiling":
            # _mount_ok knows onWall/onFloor only; prefer onCeiling if
            # the catalog carries the flag, else the whole pool
            pool = [a for a in pool if a.get("onCeiling")] or pool
        else:
            pool = [a for a in pool if retrieve2._mount_ok(a, mount)]
        for a in pool:
            cfg = native_fit(box_size, a["size_yup_cm"],
                             rowable=cat in ROWABLE_CATS)
            if cfg is None:
                continue
            rows.append({"uid": a["uid"], "category": a["category"],
                         "description": a["description"],
                         "size_cm": a["size_yup_cm"], **cfg})
    rows.sort(key=lambda r: (r["score"], r["k"]))
    return rows[:TOP_N]


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

    # THE CURRENT STATE OF THE SCENE, not a hand-named layer (user rule
    # 2026-08-09). Reading "resolved" here meant shopping sized every
    # asset from PRE-VOTE boxes — 43 of 46 disagreed with the elected
    # one, the glass door by 300x on an axis.
    nodes = {n["id"]: n for n in scene_state.nodes(graph)}
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

    # FIT WALK-BACK (canon rule 9): dry-list verdicts from the fit
    # stage override proposal feasibility -- a rejected swap's
    # out-items come back into the fit set, rejected adds vanish
    fb_p = cdir / "fit_feedback.json"
    fb = (json.loads(fb_p.read_text(encoding="utf-8"))
          if fb_p.exists() else {})
    # STALE-METRIC GUARD (R-S2-128b): a rejection is a judgment under a
    # scoring canon. If this shopping run's constants differ from the
    # stamp on the verdicts, they describe a world that no longer
    # exists — ignored loudly, never obeyed. Unstamped files (pre-guard)
    # count as stale for the same reason.
    from fit_feedback import DRY_SCORE as _DRY
    cur_fp = (f"dry{_DRY}|flat{FLAT_AXIS_M}"
              f"|ftol{FLAT_TOL_M}|fit{FIT_TOL}")
    if fb and fb.get("metric_fp") != cur_fp:
        print(f"[shopping] IGNORING stale-metric fit_feedback "
              f"(stamp {fb.get('metric_fp')!r} != current {cur_fp!r}) "
              f"— verdicts from a different scoring canon")
        fb = {}
    rej_swaps = set(fb.get("rejected_swaps", {}))
    rej_adds = set(fb.get("rejected_adds", {}))
    if rej_swaps or rej_adds:
        print(f"[shopping] fit walk-back: {sorted(rej_swaps)} reverted,"
              f" {sorted(rej_adds)} dropped")

    swapped_out = {o for s in ep["swaps"]
                   if s.get("feasible") and s["id"] not in rej_swaps
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
        if not a.get("box") or a["id"] in rej_adds:
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
        if not s.get("feasible") or s["id"] in rej_swaps:
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

    # ---- SYNONYM ESCALATION, hopeless items only (user ruling
    # 2026-08-12, R-S2-126: "only escalate the empty item, search
    # synonyms, if nothing fits then we abandon"). The lexical match
    # ends the search the moment a word hits an aisle — a small
    # end-of-bed bench never sees ottoman/footstool/bedside aisles
    # because "bench" spelled an aisle name. Items whose best candidate
    # is past the DRY bar (= about to be not_placed, R-S2-124) get ONE
    # batched mapper call carrying name + the judge's description;
    # sibling-aisle candidates merge in. Still nothing under the bar ->
    # abandoned exactly as before, now with "we looked everywhere"
    # honestly true.
    # ---- SUBSTITUTE-TERM ESCALATION, USER DESIGN 2026-08-12
    # (R-S2-127, replacing the withdrawn 126b/c size-nominated version
    # whose first run offered a BED for a console table and a MIRROR
    # for a headboard). The user's flow, verbatim: "bench -> other
    # possible categories by function or by synonym, like stool etc,
    # ordered by closeness, then we search those category using our
    # normal routine... if not then we go down to the next term, maybe
    # up to like 3 terms? then if nothing we kill it."
    # WHY THIS SHAPE IS SAFE where 126b was not: MEANING nominates the
    # aisles (no size in the question), the walk is SEQUENTIAL nearest-
    # first (a far term is only consulted after a near one FAILED), and
    # each attempt runs the normal one-aisle routine — so the style
    # judge can never cross-shop a pretty wrong-class thing. Same DRY
    # bar per aisle; three terms, then honestly absent.
    from fit_feedback import DRY_SCORE
    hopeless = [r for r in items
                if r["categories"]
                and (not r["candidates"]
                     or r["candidates"][0]["score"] > DRY_SCORE)]
    if hopeless and not args.no_llm:
        enriched = {}
        for r in hopeless:
            d = ((nodes.get(r["id"]) or {}).get("appearance") or {}) \
                .get("description") or ""
            enriched[r["id"]] = (f"{r['name']} — {d[:100]}" if d
                                 else r["name"])
        entries = {enriched[r["id"]]: r["categories"] for r in hopeless}
        try:
            got = retrieve2.map_substitute_terms(entries,
                                                 model=args.model)
        except Exception as ex:   # honest degrade: the bar stands
            print(f"[shopping] substitute-term call failed: {ex}")
            got = {}
        n_esc = 0
        for r in hopeless:
            trail = []
            for cat in (got.get(enriched[r["id"]]) or [])[:3]:
                cat = str(cat).lower()
                if cat in r["categories"]:
                    continue
                # ONE aisle per attempt, nearest first — the normal
                # routine on that aisle, same bar; the style judge
                # later sees only the aisle that WON.
                cands = shortlist(r["name"], r["box"]["size"],
                                  r["mount"], [cat])
                best = cands[0]["score"] if cands else None
                if cands and best <= DRY_SCORE:
                    r["candidates"] = cands[:TOP_N]
                    r["substituted_as"] = cat
                    r["status"] = "CANDIDATES"
                    trail.append({"category": cat, "best": best,
                                  "verdict": "TAKEN"})
                    n_esc += 1
                    break
                trail.append({"category": cat, "best": best,
                              "verdict": "over bar" if cands
                              else "empty aisle"})
            r["escalation_trail"] = trail
        print(f"[shopping] substitute categories: {len(hopeless)} "
              f"hopeless item(s), {n_esc} found a stand-in aisle")

    layer = {
        "scene": args.scene, "built": str(date.today()),
        "elapsed_s": round(time.time() - t0, 1),
        "generated_by": "compose/shopping.py",
        "graph_fingerprint": paths.graph_fingerprint(args.scene),
        "tier": "anchors",
        "note": ("ordered candidates per ANCHOR box, NATIVE SIZE ONLY "
                 "(no rescale, user 08-03B): score = worst-axis "
                 "|native/box - 1| over vertical-axis rotations x "
                 "tiling; fits = every axis within 15% (strict mark, "
                 "not a cutoff). The fit loop (next module) walks each "
                 "list until fit. Subs deferred per anchor. NO_MATCH = "
                 "not bought, host asset covers it. Boxes verbatim "
                 "from graph/edit_proposals."),
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
        nf = sum(1 for c in r["candidates"] if c.get("fits"))
        print(head + f' -> {len(r["candidates"])} candidates, '
                     f'{nf} within {FIT_TOL:.0%}')
        for c in r["candidates"][:3]:
            print(f'        dev {c["score"]:6.3f}'
                  f'{" FITS" if c.get("fits") else "     "}'
                  f' x{c["k"]} {c["category"]:<20.20s}'
                  f' {c["description"][:60]}')
    for r in subs[:200]:
        print(f'    SUB {r["id"]} "{r["name"]}" on {r["host"]} '
              f'(anchor {r["anchor"]}) -- deferred')


if __name__ == "__main__":
    main()
