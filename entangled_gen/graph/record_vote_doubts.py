"""RECORD VOTE DOUBTS — typed open questions from the slice-vote vote
(USER RULING 2026-08-06 late: the vote's doubt flags are RECORDED, never
decided on; judges consume them. USER GO 2026-08-07: record-proper
integration — the description-making pass — is no longer gated; --apply
folds the doubts into scene_graph.json as the additive `vote` block).

Two outputs:
1. SIDECAR graph/vote_doubts.json (always) — the typed doubt list.
2. --apply: scene_graph.json gains a top-level additive `vote` block
   (record-then-judge pattern, same as triage_meta etc.: nodes are NEVER
   mutated; the block references them by id). Per node: vote status,
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
- rebox_rejected_smaller: a vote-EXEMPT node's face-on (perp) re-box
  found the object at < 1/3 of the current box on BOTH in-plane axes and
  the 3x sanity guard threw the proposal away, so the oversized box
  ships. A confident detection (score present, >= 200 claimed dots) that
  says "what is in this box is much smaller than this box" is evidence of
  MULTIPLE things inside one box — the exempt paths otherwise raise no
  doubt at all and could never reach the multiplicity judge (user
  ruling 2026-08-08, obj_018 "ceiling light": one box over a compact
  fixture AND a 0.7 m strip). Growth rejections never fire this.
- rebox_truncated: the face-on (perp) re-box was ACCEPTED, but the mask
  ran OFF THE FRAME on >= 2 of the 4 in-plane sides, so those sides kept
  their PRIOR extents instead of being measured (slicevote's
  border-truncation guard, recorded as truncated_edges +
  truncation_kept_sides). Most of the shipping box is then still a
  guess, which is an open QUESTION rather than a result — what the box
  contains is unresolved (user ruling 2026-08-08: the same routing that
  sends a REJECTED re-box to the multiplicity judge sends a heavily
  truncated one; motivating case obj_038 "window", 3 of 4 in-plane sides
  on priors). One truncated side is normal for a wall-flush object and
  does NOT fire this.
- exemption: box kept verbatim, never voted (kept_wall / kept_ceiling
  / kept_floor / kept_outlier / kept) — recorded so judges know which
  geometry the vote never touched

RULE #1 (no human in the loop): the docket is AUTO-DOUBTS ONLY. A
user_routed channel existed for ~an hour on 2026-08-07 (hardcoded
obj_011) and was REMOVED the same day as a Rule-1 violation — the
pipeline must raise its own questions scene-agnostically; dev-time
review findings go to REVIEW_LOG/eval notes, never into pipeline
source. If the auto rules miss a real case, that is an honest miss for
downstream/eval to reveal, or a scene-agnostic rule-design decision
taken with the user at a gate.

Run:  python graph/record_vote_doubts.py --scene living_marble [--apply]
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

# rebox_rejected_smaller thresholds. These MIRROR slicevote.py's
# own perp constants (PERP_MAX_RATIO 3.0 -> the 1/3 shrink bound,
# PERP_MIN_CLAIM 200) — the vote is a script with side effects at import
# (argparse, ply read), so its values are restated here rather than
# imported. This rule only READS a rejection the vote already recorded;
# it never re-decides one, so a drift between the two files can at worst
# widen or narrow which rejections raise a doubt.
REBOX_SHRINK_MAX = 1.0 / 3.0   # every in-plane ratio must be under this
REBOX_MIN_CLAIM = 200          # dots the face-on mask claimed

# rebox_truncated. A face-on re-box measures the two IN-PLANE axes, i.e.
# 4 sides (lo/hi each); slicevote's border-truncation guard makes
# every side whose mask ran off the frame keep the ORIGINAL (prior)
# extent instead. At >= 2 of 4 sides on priors, most of the box is a
# guess and the question "what is in it" is open. One truncated side is
# routine for a wall-flush object (the frame clips the wall it lies on)
# and is not a doubt. Like the rejection rule above, this only READS
# what the vote already recorded; it never re-decides a re-box.
REBOX_IN_PLANE_SIDES = 4       # lo + hi on each of the two in-plane axes
REBOX_TRUNC_MIN_EDGES = 2      # doubt when this many image borders clipped


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


def rebox_proposed_box(orig, to):
    """Full lo/hi of the face-on re-box candidate the vote REJECTED.
    `to` = the perp re-box's two IN-PLANE extents, [[axis, lo, hi], ...];
    the remaining (normal) axis keeps the ORIGINAL box's extent, because
    depth is exactly what a face-on view cannot measure."""
    lo = [float(v) for v in orig["lo"]]
    hi = [float(v) for v in orig["hi"]]
    for k, l, h in to:
        lo[int(k)], hi[int(k)] = float(l), float(h)
    return {"lo": [round(v, 3) for v in lo],
            "hi": [round(v, 3) for v in hi]}


def rebox_final_box(boxes, to):
    """The box an ACCEPTED face-on re-box left behind — the one that
    ships. The vote records it as boxes["shipping"] (the re-box after
    any wall clip), so it is read VERBATIM and never recomputed; only if
    that is missing is it rebuilt from the original box + the re-box's
    in-plane extents, exactly as the rejected path does."""
    b = boxes.get("shipping") or boxes.get("rebox")
    if b:
        return {"lo": [round(float(v), 3) for v in b["lo"]],
                "hi": [round(float(v), 3) for v in b["hi"]]}
    return rebox_proposed_box(boxes["original"], to)


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
    if k == "rebox_rejected_smaller":
        pct = "/".join(f"{r:.0%}" for r in d["extent_ratio"])
        return (f"face-on view found an object at {pct} of this box's "
                f"extents (detection {d['score']:.2f}, {d['claimed']} "
                "dots) — the box is much larger than what is in it; "
                "possible multiple fixtures — multiplicity judge "
                "territory")
    if k == "rebox_truncated":
        edges = "/".join(d["truncated_edges"])
        return (f"face-on re-box measured only {d['n_measured_sides']} of "
                f"{REBOX_IN_PLANE_SIDES} in-plane sides — {edges} ran off "
                "the frame and kept their prior extents; what this box "
                "contains is unresolved — multiplicity judge territory")
    if k == "exemption":
        why = {"kept_wall": "wall-flush geometric exemption",
               "kept_ceiling": "ceiling-mount geometric exemption",
               "kept_outlier": "outlier guard (vote box grew past the "
                               "volume cap; vote box recorded as doubt)",
               "kept": "escalation ladder exhausted (no election)"}
        return (f"{why.get(d['status'], d['status'])} — resolved box kept "
                "verbatim, never voted")
    return k


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="fold the doubts into scene_graph.json as the "
                         "additive `vote` block")
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    rep_f = sd / "pool_retake" / "slicevote_report.json"
    if not rep_f.exists():
        raise SystemExit("[doubts] no slicevote_report.json — run "
                         "slicevote.py first")
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
        # A vote-EXEMPT node's face-on (perp) re-box that was REJECTED
        # for being far SMALLER than the box it was measuring. Growth
        # rejections and centre-jump-only rejections are NOT this doubt:
        # every recorded in-plane ratio must be under the shrink bound.
        # Confidence gate: the same claim floor the vote itself demands
        # before it will even try a re-box, plus a recorded detection
        # score — a weak/absent detection says nothing about multiplicity.
        rb = r["rule"].get("rebox")
        if (isinstance(rb, dict)
                and str(rb.get("result", "")).startswith("REJECTED")):
            ratios = [float(x) for x in (rb.get("extent_ratio") or [])]
            shrank = bool(ratios) and all(x < REBOX_SHRINK_MAX
                                          for x in ratios)
            confident = (rb.get("score") is not None
                         and int(rb.get("claimed") or 0) >= REBOX_MIN_CLAIM)
            if shrank and confident and rb.get("to") and boxes.get("original"):
                d.append({"kind": "rebox_rejected_smaller",
                          "plane": rb.get("plane", "?"),
                          "extent_ratio": ratios,
                          "score": float(rb["score"]),
                          "claimed": int(rb["claimed"]),
                          "center_shift_m": rb.get("center_shift_m"),
                          "proposed_box": rebox_proposed_box(
                              boxes["original"], rb["to"]),
                          "rejected_because": rb.get("result", "")})
        # An ACCEPTED face-on re-box that had almost nothing to measure:
        # the mask ran off the frame on >= 2 of the 4 in-plane sides, so
        # the vote's border-truncation guard left those sides on the
        # ORIGINAL box's prior extents. The re-box "succeeded", but most
        # of the shipping box is still a guess — an open question about
        # what the box contains, not a measurement (user ruling
        # 2026-08-08). Rejections take the branch above instead.
        if (isinstance(rb, dict) and rb.get("result") == "reboxed"
                and len(rb.get("truncated_edges") or [])
                >= REBOX_TRUNC_MIN_EDGES):
            kept_sides = rb.get("truncation_kept_sides") or []
            d.append({"kind": "rebox_truncated",
                      "plane": rb.get("plane", "?"),
                      "truncated_edges": list(rb["truncated_edges"]),
                      "truncation_kept_sides": kept_sides,
                      "n_measured_sides": (REBOX_IN_PLANE_SIDES
                                           - len(kept_sides)),
                      "score": (float(rb["score"])
                                if rb.get("score") is not None else None),
                      "claimed": int(rb.get("claimed") or 0),
                      "final_box": rebox_final_box(boxes, rb.get("to"))})
        if status.startswith("kept"):
            d.append({"kind": "exemption", "status": status})
        for x in d:
            x["text"] = doubt_text(x)
        if d:
            doubts.append({"id": r["id"], "name": r["name"],
                           "status": status, "doubts": d})

    outd = sd / "graph"
    outd.mkdir(exist_ok=True)
    out = outd / "vote_doubts.json"
    out.write_text(json.dumps(
        {"scene": a.scene,
         "source": "graph/record_vote_doubts.py — typed open questions "
                   "from the slice-vote vote. Consumers: multiplicity "
                   "judge + same-product judge (+ scene_graph.json vote "
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
    g["vote"] = {
        "built": datetime.now().isoformat(timespec="seconds"),
        "built_from": str(rep_f),
        "report_status": rep.get("status", ""),
        "by_status": rep.get("by_status", {}),
        "note": "ADDITIVE block (record-then-judge): slice-vote vote "
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
    print(f"[doubts] applied: scene_graph.json `vote` block — "
          f"{len(nodes_block)} nodes ({n_doubt} with doubts)", flush=True)


if __name__ == "__main__":
    main()
