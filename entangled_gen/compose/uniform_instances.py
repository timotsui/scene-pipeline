"""UNIFORM-INSTANCES JUDGE — same-product grouping + one shared size
(USER IDEA 2026-08-06, cone-map session).

⚠ SUPERSEDED same night (user ruling): this belongs in the GRAPH judge
chain, not compose — see graph/judge_same_product.py (same grouping,
verdicts write graph/same_product.json, vote doubts ride as context).
This file is kept only as the idea's first draft; do not wire it.

⚠ STATUS: UNTESTED — written during the promotion push, NEVER RUN.
No verdict from this module has been reviewed; nothing consumes its
output yet (shopping is the intended consumer). Run with --dry-run
first: it prints the candidate groups WITHOUT any LLM call.

THE PROBLEM: repeated-class instances (e.g., the chairs around one
table) come out of detection+vote with varying sizes because splat
quality and masks are messy per instance. Physically they are usually
the same product. Detection cannot fix this — it is a SEMANTIC call.

THE DESIGN (scene-agnostic, Rule #1 — no per-scene lists, no hardcoded
class names):
1. CANDIDATE GROUPS (deterministic): resolved nodes with the same name
   whose plan centers sit within GROUP_RADIUS of the group centroid,
   sharing the same nearest-larger-neighbor node (the "anchor" — e.g. a
   table — found geometrically: the closest node whose footprint area is
   >= 2x the member's). Groups of size < 2 are dropped.
2. VERDICT (one LLM call per group, claude.exe like the other judges):
   the judge sees the members' names, sizes, positions and the anchor's
   name, and answers: are these the same product? If yes, pick the
   canonical size (the judge may choose the median or any member's size,
   with a reason).
3. OUTPUT: compose/uniform_instances.json — {groups: [{members,
   same_object, canonical_size, reason}]}. CONSUMER (to wire, not done):
   compose/shopping.py should retrieve ONE asset per same-object group
   and reuse it for every member at the canonical size.

Run:  python compose/uniform_instances.py --scene living_marble --dry-run
      python compose/uniform_instances.py --scene living_marble
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(HERE))
import paths  # noqa: E402
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / 'graph'))
import scene_state  # noqa: E402

GROUP_RADIUS = 2.5      # m — same-name members within this plan radius
ANCHOR_AREA_RATIO = 2.0  # anchor = nearest node with >= 2x footprint area


def plan_center(geo):
    return np.array([(geo["aabb_min"][0] + geo["aabb_max"][0]) / 2,
                     (geo["aabb_min"][2] + geo["aabb_max"][2]) / 2])


def footprint_area(geo):
    s = geo["size"]
    return s[0] * s[2]


def find_anchor(node, nodes):
    """Nearest node with a footprint >= ANCHOR_AREA_RATIO x this one's."""
    c = plan_center(node["geometry"])
    area = footprint_area(node["geometry"])
    best, best_d = None, 1e9
    for m in nodes:
        if m["id"] == node["id"]:
            continue
        if footprint_area(m["geometry"]) < ANCHOR_AREA_RATIO * area:
            continue
        d = float(np.linalg.norm(plan_center(m["geometry"]) - c))
        if d < best_d:
            best, best_d = m, d
    return (best["id"], best["name"], round(best_d, 2)) if best else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--dry-run", action="store_true",
                    help="print candidate groups, no LLM call")
    ap.add_argument("--model", default="haiku",
                    help="claude.exe model alias (matches other judges)")
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    g = json.loads((sd / "scene_graph.json").read_text(encoding="utf-8"))
    # the CURRENT layer, not a hand-named one (user rule 2026-08-09)
    nodes = scene_state.nodes(g)

    # prefer voted sizes when the slice-vote preview exists (UNTESTED
    # chain: vote first, then uniformity)
    voted = {}
    prev = sd / "scene_manifest_slicevote_preview.json"
    if prev.exists():
        for o in json.loads(prev.read_text())["objects"]:
            voted[o["id"]] = o["size"]

    # ---- 1. deterministic candidate groups ----
    by_name = {}
    for n in nodes:
        by_name.setdefault(n["name"], []).append(n)
    groups = []
    for name, members in by_name.items():
        if len(members) < 2:
            continue
        # split by proximity: greedy clusters within GROUP_RADIUS
        left = list(members)
        while left:
            seed = left.pop(0)
            cluster = [seed]
            changed = True
            while changed:
                changed = False
                cen = np.mean([plan_center(m["geometry"])
                               for m in cluster], axis=0)
                for m in list(left):
                    if np.linalg.norm(plan_center(m["geometry"])
                                      - cen) <= GROUP_RADIUS:
                        cluster.append(m)
                        left.remove(m)
                        changed = True
            if len(cluster) < 2:
                continue
            anchors = [find_anchor(m, nodes) for m in cluster]
            anchor_ids = {x[0] for x in anchors if x}
            groups.append({
                "name": name,
                "members": [{
                    "id": m["id"],
                    "size": voted.get(m["id"], m["geometry"]["size"]),
                    "center": [round(float(v), 2)
                               for v in m["geometry"]["center"]]}
                    for m in cluster],
                "shared_anchor": (anchors[0]
                                  if len(anchor_ids) == 1 and anchors[0]
                                  else None),
            })
    print(f"[uniform] {len(groups)} candidate group(s)", flush=True)
    for gr in groups:
        print(f"[uniform]   {gr['name']}: "
              f"{[m['id'] for m in gr['members']]} "
              f"anchor={gr['shared_anchor']}", flush=True)
    if a.dry_run:
        print("[uniform] dry run — no LLM call, nothing written",
              flush=True)
        return

    # ---- 2. one LLM verdict per group (claude.exe, judge pattern) ----
    results = []
    for gr in groups:
        prompt = (
            "You are judging furniture instances found in ONE room.\n"
            f"Candidate group — {len(gr['members'])} objects all "
            f"detected as \"{gr['name']}\""
            + (f", all nearest to the same larger object "
               f"\"{gr['shared_anchor'][1]}\"" if gr["shared_anchor"]
               else "") + ":\n"
            + "\n".join(
                f"  {m['id']}: size {m['size']} m (w x h x d), "
                f"center {m['center']}" for m in gr["members"])
            + "\n\nMeasured sizes vary because 3D reconstruction is "
            "noisy. Question: in a typical real room, would these be "
            "THE SAME PRODUCT (a matched set)? If yes, choose ONE "
            "canonical size for all of them (favor the median of the "
            "plausible measurements; ignore obvious outliers).\n"
            "Answer STRICT JSON only:\n"
            "{\"same_object\": true|false, "
            "\"canonical_size\": [w, h, d] or null, "
            "\"reason\": \"one sentence\"}")
        out = subprocess.run(
            ["claude", "-p", prompt, "--model", a.model,
             "--output-format", "text"],
            capture_output=True, text=True, timeout=120, shell=True)
        verdict = None
        try:
            txt = out.stdout.strip()
            verdict = json.loads(txt[txt.index("{"):txt.rindex("}") + 1])
        except Exception as e:  # noqa: BLE001 — judge output is external
            verdict = {"same_object": None, "canonical_size": None,
                       "reason": f"judge call failed: {e}"}
        results.append({**gr, **verdict})
        print(f"[uniform]   {gr['name']}: same={verdict['same_object']} "
              f"size={verdict['canonical_size']} — {verdict['reason']}",
              flush=True)

    outf = paths.compose_dir(a.scene) / "uniform_instances.json"
    outf.parent.mkdir(parents=True, exist_ok=True)
    outf.write_text(json.dumps(
        {"scene": a.scene, "status": "UNTESTED",
         "source": "compose/uniform_instances.py — same-product "
                   "grouping + canonical size (user idea 2026-08-06); "
                   "consumer wiring (shopping) NOT done",
         "groups": results}, indent=1))
    print(f"[uniform] wrote {outf} (⚠ UNTESTED)", flush=True)


if __name__ == "__main__":
    main()
