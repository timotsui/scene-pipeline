"""RECORD CARVE DOUBTS — typed open questions from the slice-vote carve
(USER RULING 2026-08-06 late: the carve's doubt flags are RECORDED, never
decided on; judges consume them. USER GO 2026-08-07: record-proper
integration — the description-making pass — is no longer gated; --apply
folds the doubts into scene_graph.json as the additive `carve` block).

Two outputs:
1. SIDECAR graph/carve_doubts.json (always) — the typed doubt list.
2. --apply: scene_graph.json gains a top-level additive `carve` block
   (record-then-judge pattern, same as triage_meta etc.: nodes are NEVER
   mutated; the block references them by id). Per node: carve status,
   escalation tiers, slice provenance, typed doubts each with a
   mechanical plain-English sentence (no LLM — judges do the judging).
   Consumers: multiplicity judge + same-product judge + viewer cards.

Doubt kinds (per node, from pool_retake/slicevote_report.json + the
preview manifest's status flags):
- pano_vs_cluster: pano-filtered box < 50% of the vote-cluster volume
  (possible multi-node structure — multiplicity-judge territory).
  Pano masks = the node's founding masks from the original pano-funnel
  views (rig_sp0 crops). Formerly "arm_vs_cluster" — run-5 and earlier
  records carry the old name and are still read.
- culled_clusters: N vote clusters culled by anchoring (possible second
  instance — multiplicity evidence)
- slice_fallback: slice came from the original-box wedge fallback (no
  top detection) — lower-confidence geometry
- low_plan_fill: elected dots cover < 65% of the vote box's footprint
  (user rule 3, 2026-08-07; census break 0.58|0.73) — non-box shape
  (L-sectional) or sparse giant; split-cell territory
- large_empty_notch: largest contiguous empty axis-aligned rectangle in
  the object's own plan footprint >= 0.50 m2 (user rule, 2026-08-07
  late; run-6 census: sofa 1.52 m2 vs next 0.18 m2) — the notch where a
  missing/other limb would park; multiplicity-judge territory
- exemption: box kept verbatim, never carved (kept_wall / kept_ceiling
  / kept_floor / kept_outlier / kept) — recorded so judges know which
  geometry the carve never touched

RULE #1 (no human in the loop): the docket is AUTO-DOUBTS ONLY. A
user_routed channel existed for ~an hour on 2026-08-07 (hardcoded
obj_011) and was REMOVED the same day as a Rule-1 violation — the
pipeline must raise its own questions scene-agnostically; dev-time
review findings go to REVIEW_LOG/eval notes, never into pipeline
source. If the auto rules miss a real case, that is an honest miss for
downstream/eval to reveal, or a scene-agnostic rule-design decision
taken with the user at a gate.

Run:  python graph/record_carve_doubts.py --scene living_marble [--apply]
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402

# large_empty_notch thresholds (user rule, 2026-08-07 late). Run-6
# scene-wide census: the sofa's largest contiguous empty footprint
# rectangle is 1.52 m2 vs 0.18 m2 for the next object — open water.
# Plan-fill v2 GLOBAL thresholds were tried and REFUTED (small round
# objects underfill more than the L; the sofa sat mid-pack among
# pillows), so the rule is the NOTCH, not overall fill.
NOTCH_K = 2      # a plan cell counts as OCCUPIED only with >= K dots
NOTCH_M2 = 0.50  # doubt when the largest empty rectangle >= this area


def largest_empty_rect(pc):
    """Largest contiguous EMPTY axis-aligned rectangle in a plan_cells
    grid ({"cell_m", "nx", "nz", "counts": [[ix, iz, count], ...]}).
    Empty = cell with < NOTCH_K dots (cells absent from counts are 0
    dots = empty). Histogram-of-heights + monotonic stack per z-row.
    Returns (area_m2, (x0, z0, x1, z1)) — cell bounds
    inclusive-exclusive."""
    nx, nz = pc["nx"], pc["nz"]
    occ = np.zeros((nx, nz), dtype=bool)
    for ix, iz, cnt in pc["counts"]:
        if cnt >= NOTCH_K:
            occ[ix, iz] = True
    best_cells, best_rect = 0, (0, 0, 0, 0)
    heights = np.zeros(nx, dtype=int)   # empty-run height ending at row z
    for z in range(nz):
        for x in range(nx):
            heights[x] = 0 if occ[x, z] else heights[x] + 1
        stack = []   # (start_x, height), heights strictly increasing
        for x in range(nx + 1):
            h = int(heights[x]) if x < nx else 0
            start = x
            while stack and stack[-1][1] >= h:
                sx, sh = stack.pop()
                if sh * (x - sx) > best_cells:
                    best_cells = sh * (x - sx)
                    best_rect = (sx, z - sh + 1, x, z + 1)
                start = sx
            if h > 0:
                stack.append((start, h))
    return best_cells * pc["cell_m"] ** 2, best_rect


def pano_box(boxes):
    """The pano-filtered box, under either name (pre-rename reports and
    run-5 data call it "arm")."""
    return boxes.get("pano") or boxes.get("arm")


def doubt_text(d):
    k = d["kind"]
    if k in ("pano_vs_cluster", "arm_vs_cluster"):   # old name still read
        return (f"pano-filtered box is {d['ratio']:.0%} of the vote-cluster "
                "volume — possibly a multi-object structure "
                "(multiplicity-judge territory)")
    if k == "culled_clusters":
        return (f"{d['n']} vote cluster(s) culled by anchoring — possible "
                "second instance (multiplicity evidence)")
    if k == "slice_fallback":
        return ("slice came from the original-box wedge fallback (no top "
                "detection) — lower-confidence geometry")
    if k == "low_plan_fill":
        return (f"elected dots cover only {d['fill']:.0%} of the box "
                "footprint — non-box shape (L?) or sparse election; "
                "split-cell territory")
    if k == "large_empty_notch":
        return (f"largest contiguous empty rectangle in own footprint "
                f"{d['notch_m2']:.2f} m2 (>= {NOTCH_M2:.2f}) — non-box "
                "shape (L?); multiplicity judge territory")
    if k == "exemption":
        why = {"kept_wall": "wall-flush geometric exemption",
               "kept_ceiling": "ceiling-mount geometric exemption",
               "kept_outlier": "outlier guard (vote box grew past the "
                               "volume cap; vote box recorded as doubt)",
               "kept": "escalation ladder exhausted (no election)"}
        return (f"{why.get(d['status'], d['status'])} — resolved box kept "
                "verbatim, never carved")
    return k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="fold the doubts into scene_graph.json as the "
                         "additive `carve` block")
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    rep_f = sd / "pool_retake" / "slicevote_report.json"
    if not rep_f.exists():
        raise SystemExit("[doubts] no slicevote_report.json — run "
                         "carve_slicevote.py first")
    rep = json.loads(rep_f.read_text())
    man_f = sd / "scene_manifest_slicevote_preview.json"
    status_by_id = {}
    if man_f.exists():
        man = json.loads(man_f.read_text())
        for o in man.get("objects", []):
            fl = o.get("flags") or []
            status_by_id[o["id"]] = fl[0] if fl else ""

    doubts = []
    for r in rep["results"]:
        d = []
        boxes = r["boxes"]
        status = status_by_id.get(r["id"], "")
        pbox = pano_box(boxes)
        if pbox and boxes.get("vote2"):
            va = float(np.prod(np.maximum(
                np.array(pbox["hi"]) - np.array(pbox["lo"]),
                1e-6)))
            vv = float(np.prod(np.maximum(
                np.array(boxes["vote2"]["hi"])
                - np.array(boxes["vote2"]["lo"]), 1e-6)))
            if va < 0.5 * vv:
                d.append({"kind": "pano_vs_cluster",
                          "ratio": round(va / vv, 3),
                          "pano_box": pbox,
                          "cluster_box": boxes["vote2"]})
        if r["rule"].get("culled_clusters"):
            d.append({"kind": "culled_clusters",
                      "n": r["rule"]["culled_clusters"]})
        if "FALLBACK" in r["rule"].get("slice", ""):
            d.append({"kind": "slice_fallback",
                      "slice": r["rule"]["slice"]})
        pf = r["rule"].get("plan_fill")
        if pf is not None and pf < 0.65:
            d.append({"kind": "low_plan_fill", "fill": pf})
        pc = r["rule"].get("plan_cells")
        if pc and boxes.get("vote2"):   # grid is anchored to the vote box
            notch_m2, (x0, z0, x1, z1) = largest_empty_rect(pc)
            if notch_m2 >= NOTCH_M2:
                cm = pc["cell_m"]
                lo_x = float(boxes["vote2"]["lo"][0])
                lo_z = float(boxes["vote2"]["lo"][2])
                d.append({"kind": "large_empty_notch",
                          "notch_m2": round(notch_m2, 2),
                          "rect_cells": [x0, z0, x1, z1],
                          "rect_m": [round(lo_x + x0 * cm, 3),
                                     round(lo_z + z0 * cm, 3),
                                     round(lo_x + x1 * cm, 3),
                                     round(lo_z + z1 * cm, 3)]})
        if status.startswith("kept"):
            d.append({"kind": "exemption", "status": status})
        for x in d:
            x["text"] = doubt_text(x)
        if d:
            doubts.append({"id": r["id"], "name": r["name"],
                           "status": status, "doubts": d})

    outd = sd / "graph"
    outd.mkdir(exist_ok=True)
    out = outd / "carve_doubts.json"
    out.write_text(json.dumps(
        {"scene": a.scene,
         "source": "graph/record_carve_doubts.py — typed open questions "
                   "from the slice-vote carve. Consumers: multiplicity "
                   "judge + same-product judge (+ scene_graph.json carve "
                   "block via --apply).",
         "n_nodes_with_doubts": len(doubts), "nodes": doubts}, indent=1))
    print(f"[doubts] {len(doubts)} node(s) with doubts -> {out}",
          flush=True)

    if not a.apply:
        return

    gf = sd / "scene_graph.json"
    if not gf.exists():
        raise SystemExit("[doubts] no scene_graph.json — nothing to apply "
                         "into")
    g = json.loads(gf.read_text())
    nodes_block = {}
    for r in rep["results"]:
        nodes_block[r["id"]] = {
            "name": r["name"],
            "status": status_by_id.get(r["id"], ""),
            "tiers": r["rule"].get("tiers", []),
            "slice": r["rule"].get("slice", ""),
        }
    for n in doubts:
        nodes_block[n["id"]]["doubts"] = n["doubts"]
    g["carve"] = {
        "built": datetime.now().isoformat(timespec="seconds"),
        "built_from": str(rep_f),
        "report_status": rep.get("status", ""),
        "by_status": rep.get("by_status", {}),
        "note": "ADDITIVE block (record-then-judge): slice-vote carve "
                "provenance + typed doubts per resolved node; nodes are "
                "never mutated. Boxes live in "
                "scene_manifest_slicevote_preview.json until the "
                "materialize pass folds them in (map promotion). "
                "AUTO-DOUBTS ONLY (Rule #1) — no user-routing channel.",
        "nodes": nodes_block,
    }
    tmp = gf.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(g, indent=1))
    tmp.replace(gf)
    n_doubt = sum(1 for v in nodes_block.values() if v.get("doubts"))
    print(f"[doubts] applied: scene_graph.json `carve` block — "
          f"{len(nodes_block)} nodes ({n_doubt} with doubts)", flush=True)


if __name__ == "__main__":
    main()
