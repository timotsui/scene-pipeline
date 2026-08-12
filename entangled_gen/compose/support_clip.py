"""RETIRED 2026-08-11. NOT IN ANY CHAIN. Do not wire it into one.

USER RULING: "if we already have a similar mechanism — I remember we are
doing fitting sub object on host via a loop or something — so it's safe
to retire if most of the docs say it's retired."

WHY, in one line: it REWRITES A LAYER'S GEOMETRY IN PLACE, and that is
the pattern this project spent August removing. Every other stage now
hands on a whole new layer named for what it did (record -> judged ->
resolved -> voted -> settled -> shown -> grouped), which is what makes
`scene_state` able to say what the current state of a scene is at all.
A module that edits `graph['resolved']` underneath everyone breaks that
guarantee silently.

THE RECORD WAS GENUINELY SPLIT, which is why this sat unresolved for
months rather than being deleted:
  FOR    docs/REVIEW_LOG.md:834 (R-S2-22) puts it in the order —
         "Support semantics must run AFTER geometry repair: parallax
         carve -> S1 -> support_clip -> compose sizes"
  AGAINST five consecutive session handoffs carry it as a RETIREMENT
         CANDIDATE, and REVIEW_LOG.md:1129 says exactly why:
         "support_clip rewrites graph['resolved'] geometry in place,
         which is the pattern this week removed"

WHAT COVERS THE NEED NOW. The problem it was built for is real — the
lift cannot bound an object along the viewing ray when the background
touches it depth-continuously. What answers that today is the compose
fit loop (place -> jiggle -> check -> walk, canon 08-04) working against
the SNAPPED boxes, plus `compose/snap.py` seating each object on what
holds it up. Those act on placement rather than editing a measured
layer, which is the right shape.

IF THE NEED COMES BACK, rebuild it as a proper layer edit: read one
layer, write the next, stamp it. Do not un-retire this file.

--- what it does, kept for reference ---

Support-clip surgery (compose stage, PROTOTYPE 2026-08-06).

The lift cannot bound an object's extent along the viewing ray when the
background touches it depth-continuously (splat porosity leaks tabletop/
floor depths through thin objects — the on-table streak class, R-S2-21
user finding). The graph knows what geometry cannot: X is ON Y, so X ends
at Y's surface. This module cuts every ON node's box at its supporter:

  bottom  : X.aabb_max.y (raw y-down bottom) clipped to the support plane
            (supporter top for object supporters, measured floor for
            arch_floor) + PEN_TOL penetration allowance
  footprint: X's x/z extent clipped to the supporter footprint + OVERHANG
            margin (objects overhang tables a little, not by meters);
            arch supporters (floor/walls) impose no footprint limit

Evidence-based, scene-agnostic, deterministic; no-op for nodes without an
ON edge. PREVIEW BY DEFAULT: writes compose/support_clip_preview.json +
scene_manifest_supportclip_preview.json (viewer layer) and touches neither
scene_graph.json nor any manifest. --apply rewrites geometry in place in
THE CURRENT LAYER — whichever layer scene_state says is the state of the
scene, not the hand-named `resolved` this used to cut — preserving the
original per node as geometry_observed with full per-plane provenance
(surgery on the record, never silent).

Run:  python compose/support_clip.py --scene living_marble [--apply]
"""
import argparse
import json
from pathlib import Path

import sys
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402
# scene_state lives in the sibling graph/ package, not beside us, so its
# directory has to go on the path too (same two-step the other compose
# modules use, e.g. uniform_instances.py).
sys.path.insert(0, str(HERE.parent / "graph"))
import scene_state  # noqa: E402

PEN_TOL = 0.02      # m an object may visually sink into its support
OVERHANG = 0.10     # m of footprint overhang beyond the supporter's edge


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    gf = sd / "scene_graph.json"
    g = json.loads(gf.read_text(encoding="utf-8"))
    # THE CURRENT LAYER, not `resolved`. This module cuts a box at its
    # supporter's surface, so both boxes have to be the ones the scene
    # actually has; `resolved` is pre-vote, and cutting a supporter that
    # has since changed size puts the plane in the wrong place. The name
    # is kept because --apply writes back into THIS layer and must stamp
    # THIS layer — see the stamp below.
    layer_name, res = scene_state.current(g)
    nodes = {n["id"]: n for n in res["nodes"]}

    # measured floor beats bootstrap floor
    shellf = sd / "room_shell.json"
    if shellf.exists():
        floor_y = json.loads(shellf.read_text())["floor_y_raw"]
    else:
        floor_y = json.loads((sd / "frame_bootstrap.json").read_text())["floor_y"]

    supports = {}          # node id -> supporter id (first ON edge wins)
    for e in res["edges"]:
        if e["type"] == "ON" and e["a"] in nodes and e["a"] not in supports:
            supports[e["a"]] = e["b"]

    clips = []
    for nid, sup in supports.items():
        n = nodes[nid]
        geo = n["geometry"]
        lo = list(geo["aabb_min"])
        hi = list(geo["aabb_max"])
        before = {"aabb_min": list(lo), "aabb_max": list(hi),
                  "size": list(geo["size"])}
        ops = []
        if sup == "arch_floor":
            plane = floor_y
        elif sup in nodes:
            plane = nodes[sup]["geometry"]["aabb_min"][1]   # supporter top (y-down)
        else:
            continue    # unknown supporter (other arch) — leave untouched
        limit = plane + PEN_TOL
        if hi[1] > limit:
            ops.append({"plane": "bottom", "from": hi[1], "to": round(limit, 4),
                        "support": sup})
            hi[1] = limit
        if sup in nodes:   # footprint only for object supporters
            slo = nodes[sup]["geometry"]["aabb_min"]
            shi = nodes[sup]["geometry"]["aabb_max"]
            for ax, nm in ((0, "x"), (2, "z")):
                if lo[ax] < slo[ax] - OVERHANG:
                    ops.append({"plane": f"{nm}_lo", "from": lo[ax],
                                "to": round(slo[ax] - OVERHANG, 4), "support": sup})
                    lo[ax] = slo[ax] - OVERHANG
                if hi[ax] > shi[ax] + OVERHANG:
                    ops.append({"plane": f"{nm}_hi", "from": hi[ax],
                                "to": round(shi[ax] + OVERHANG, 4), "support": sup})
                    hi[ax] = shi[ax] + OVERHANG
        if not ops or any(h <= l for l, h in zip(lo, hi)):
            if ops:
                print(f"[clip] {nid}: clip would EMPTY the box — left "
                      f"untouched, flagged", flush=True)
                clips.append({"id": nid, "name": n["name"], "status": "degenerate",
                              "ops": ops, "before": before})
            continue
        after = {"aabb_min": [round(v, 4) for v in lo],
                 "aabb_max": [round(v, 4) for v in hi],
                 "center": [round((l + h) / 2, 4) for l, h in zip(lo, hi)],
                 "size": [round(h - l, 4) for l, h in zip(lo, hi)]}
        clips.append({"id": nid, "name": n["name"], "support": sup,
                      "status": "clipped", "ops": ops,
                      "before": before, "after": after})
        if a.apply:
            n["geometry_observed"] = before
            n["geometry"] = dict(geo, **after)
            n.setdefault("flags", []).append("support_clipped")

    report = {"scene": a.scene, "stage": "support_clip",
              "layer": layer_name,     # which layer was read, and cut
              "params": {"PEN_TOL": PEN_TOL, "OVERHANG": OVERHANG},
              "floor_y": floor_y, "applied": bool(a.apply),
              "n_on_nodes": len(supports),
              "n_clipped": sum(1 for c in clips if c["status"] == "clipped"),
              "clips": clips}
    cdir = sd / "compose"
    cdir.mkdir(exist_ok=True)
    (cdir / "support_clip_preview.json").write_text(json.dumps(report, indent=1))

    # viewer layer: manifest-style preview of the clipped boxes
    objs = []
    for c in clips:
        if c["status"] != "clipped":
            continue
        af = c["after"]
        objs.append({"id": c["id"], "label": c["name"] + " (clipped)",
                     "score": 1.0, "aabb_min": af["aabb_min"],
                     "aabb_max": af["aabb_max"], "center": af["center"],
                     "size": af["size"], "n_detections": 1, "views": [],
                     "flags": ["support_clip_preview"]})
    man = {"scene": a.scene, "source": "compose/support_clip.py preview",
           "frame": {"space": "raw", "up": [0.0, -1.0, 0.0],
                     "floor_y": floor_y},
           "n_objects": len(objs), "objects": objs}
    (sd / "scene_manifest_supportclip_preview.json").write_text(
        json.dumps(man, indent=2))

    if a.apply:
        # --apply is box surgery on THE LAYER WE READ, so that is the layer
        # the stamp must name. The node dicts above came out of it and were
        # edited in place, so the write-back needs no copying — but the
        # stamp does need the right name: stamping `resolved` after cutting
        # `grouped` would sweep every layer after `resolved` stale,
        # including the one holding the boxes we just wrote, and would tell
        # the file that a layer this run never touched is current. A stamp
        # naming the wrong layer is worse than no stamp at all.
        # The stamp still marks everything AFTER this layer stale: those
        # layers were built from the boxes we just cut, so a finished scene
        # is no longer finished once this flag is used. Without it that
        # invalidation is completely silent — one flag and the whole
        # downstream stack is quietly wrong while the end-of-run gate still
        # reports it clean.
        scene_state.stamp(g, layer_name)
        gf.write_text(json.dumps(g, indent=1), encoding="utf-8")
        print(f"[clip] APPLIED to graph[{layer_name}] "
              f"({report['n_clipped']} nodes)")
    print(f"[clip] ON nodes {len(supports)}; clipped {report['n_clipped']}; "
          f"preview -> compose/support_clip_preview.json")
    for c in clips:
        if c["status"] != "clipped":
            continue
        b, f = c["before"]["size"], c["after"]["size"]
        print(f"  {c['id']:8s} {c['name']:16s} on {c['support']:9s} "
              f"{[round(v,2) for v in b]} -> {[round(v,2) for v in f]} "
              f"({len(c['ops'])} planes)")


if __name__ == "__main__":
    main()
