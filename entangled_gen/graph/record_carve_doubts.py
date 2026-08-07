"""RECORD CARVE DOUBTS — typed open questions from the slice-vote carve
(USER RULING 2026-08-06 late: the carve's doubt flags are RECORDED, never
decided on; judges consume them).

⚠ STATUS: UNTESTED PROMOTION (cone-map session). Writes a SIDECAR next
to the graph (graph/carve_doubts.json) — it does NOT mutate
scene_graph.json; folding these into the record proper (the
description-making pass, so node cards carry the doubt) is part of the
user-gated map promotion.

Reads pool_retake/slicevote_report.json; per node emits typed doubts:
- arm_vs_cluster: the own-mask arm box is <50% of the vote-cluster box
  volume (possible multi-node structure — multiplicity-judge territory)
- culled_clusters: N vote clusters were culled by anchoring (possible
  second instance — multiplicity evidence)
- slice_fallback: the slice came from the wedge fallback (no top
  detection) — lower-confidence geometry

Run:  python graph/record_carve_doubts.py --scene living_marble
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    rep_f = sd / "pool_retake" / "slicevote_report.json"
    if not rep_f.exists():
        raise SystemExit("[doubts] no slicevote_report.json — run "
                         "carve_slicevote.py first")
    rep = json.loads(rep_f.read_text())
    doubts = []
    for r in rep["results"]:
        d = []
        boxes = r["boxes"]
        if boxes.get("arm") and boxes.get("vote2"):
            va = float(np.prod(np.maximum(
                np.array(boxes["arm"]["hi"]) - np.array(boxes["arm"]["lo"]),
                1e-6)))
            vv = float(np.prod(np.maximum(
                np.array(boxes["vote2"]["hi"])
                - np.array(boxes["vote2"]["lo"]), 1e-6)))
            if va < 0.5 * vv:
                d.append({"kind": "arm_vs_cluster",
                          "ratio": round(va / vv, 3),
                          "arm_box": boxes["arm"],
                          "cluster_box": boxes["vote2"]})
        if r["rule"].get("culled_clusters"):
            d.append({"kind": "culled_clusters",
                      "n": r["rule"]["culled_clusters"]})
        if "FALLBACK" in r["rule"].get("slice", ""):
            d.append({"kind": "slice_fallback",
                      "slice": r["rule"]["slice"]})
        if d:
            doubts.append({"id": r["id"], "name": r["name"], "doubts": d})
    outd = sd / "graph"
    outd.mkdir(exist_ok=True)
    out = outd / "carve_doubts.json"
    out.write_text(json.dumps(
        {"scene": a.scene, "status": "UNTESTED",
         "source": "graph/record_carve_doubts.py — typed open questions "
                   "from the slice-vote carve; SIDECAR (record-proper "
                   "integration is gated with the map promotion). "
                   "Consumers: multiplicity judge + same-product judge.",
         "n_nodes_with_doubts": len(doubts), "nodes": doubts}, indent=1))
    print(f"[doubts] {len(doubts)} node(s) with doubts -> {out} "
          f"(⚠ UNTESTED)", flush=True)


if __name__ == "__main__":
    main()
