"""Realization funnel — measured boxes -> placed assets, with reasons.

EVAL_PLAN metric 8, user: "be very clear that our thing is mostly
limited by the asset library". Per scene, from receipts that already
exist (no re-runs):

  measured   objects in the shipped graph layer (comparison.json
             D_grounding.ours_object_count — the evidence-backed boxes)
  shopped    anchor-tier items sent to retrieval (compose/shopping.json
             items; subs_deferred counted separately)
  placed     assets standing in the final GLB: fitted_preview.json
             placed (anchors + swap-ins) + merge_subs.json n_added
  unrealized not_placed with its recorded 'why' (verbatim, bucketed),
             plus deferred subs that never merged

The point (stated in the paper text): the measured side is rich; the
furnishing ceiling is the RETRIEVAL LIBRARY, which is swappable and
out of scope (user ruling 2026-08-11B kept re-shop unbuilt). Unlike
GLTS — which silently loses 1–11 of its own retrievals per scene —
every unrealized box here carries its box, its evidence and its
reason.

Run:  python eval_funnel.py
"""
import json
import re
from pathlib import Path

import paths

SCENES = ["natural_living", "sunlit_office", "blue_living", "panel_bedroom",
          "arch_bedroom", "plaster_bedroom",
          "bedroom_marble", "living_marble", "fresh04", "fresh06"]


def _load(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def bucket(why):
    w = (why or "").lower()
    if "candidate" in w or "retriev" in w or "shortlist" in w or "match" in w:
        return "no acceptable asset match"
    if "size" in w or "score" in w or "fit" in w:
        return "size/fit bar"
    if "wall" in w or "outside" in w or "polygon" in w:
        return "placement geometry"
    return f"other: {w[:60]}"


def main():
    comp = _load(paths.OUT / "comparison.json") or {}
    measured_by = {r["scene"]: (r.get("D_grounding") or {})
                   .get("ours_object_count")
                   for r in comp.get("scenes", [])}

    table = {}
    for sc in SCENES:
        cdir = paths.scene_dir(sc) / "compose"
        fp = _load(cdir / "fitted_preview.json")
        sh = _load(cdir / "shopping.json")
        ms = _load(cdir / "merge_subs.json")
        if fp is None or sh is None:
            table[sc] = {"available": False,
                         "why": "no current-era compose receipts"}
            print(f"[funnel] {sc:18s} — no current-era compose receipts")
            continue
        placed = fp.get("placed") or []
        not_placed = fp.get("not_placed") or []
        failed = fp.get("failed") or []
        anchors = sh.get("items") or []
        subs_def = sh.get("subs_deferred") or []
        n_subs_merged = (ms or {}).get("n_added", 0)
        reasons = {}
        for e in not_placed + failed:
            b = bucket(e.get("why") or e.get("reason"))
            reasons.setdefault(b, []).append(
                f"{e.get('id')}:{e.get('name')}")
        n_placed_anchor = sum(1 for e in placed
                              if re.match(r"obj_", str(e.get("id", ""))))
        n_placed_swap = len(placed) - n_placed_anchor
        rec = {
            "available": True,
            "measured": measured_by.get(sc),
            "shopped_anchors": len(anchors),
            "subs_deferred": len(subs_def),
            "placed_total": len(placed) + n_subs_merged,
            "placed_anchors": n_placed_anchor,
            "placed_swaps": n_placed_swap,
            "subs_merged": n_subs_merged,
            "unrealized": {b: v for b, v in reasons.items()},
            "n_unrealized": len(not_placed) + len(failed),
        }
        m = rec["measured"]
        rate = (round(100.0 * rec["placed_total"] / m) if m else None)
        rec["realization_pct_of_measured"] = rate
        table[sc] = rec
        print(f"[funnel] {sc:18s} measured {m or '?':>3} -> shopped "
              f"{len(anchors):3d} (+{len(subs_def)} subs) -> placed "
              f"{rec['placed_total']:3d} ({rate or '?'}%)  unrealized "
              f"{rec['n_unrealized']}: "
              + "; ".join(f"{b} x{len(v)}" for b, v in reasons.items()))

    out = paths.OUT / "eval_renders" / "realization_funnel.json"
    out.write_text(json.dumps({"scenes": table}, indent=1), encoding="utf-8")
    print(f"[funnel] -> {out}")


if __name__ == "__main__":
    main()
