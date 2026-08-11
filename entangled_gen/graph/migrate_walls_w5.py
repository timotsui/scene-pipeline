"""W5/W6 WALL MIGRATION — the polygon shell enters the scene graph.

One EDIT on the graph (graph-edit rule): inherit the whole structure,
replace only the architecture wall nodes and re-point the wall-relative
edges. User ruling 2026-08-09 (4th session): "make sure we update all
the locations relative to walls to the correct place, [otherwise] the
edges of the graph [point at] a 'new wall'; the structure of most if
not all should just be the same."

  GETS   scene_graph.json + room_shell.json's "polygon" block.
  EDITS  (a) record-layer architecture: the four v1 arch_wall_* nodes
             are REPLACED by one node per polygon segment
             (arch_wall_00..NN — cardinal planes + the connector),
             evidence carried from the polygon fit; arch_floor /
             arch_ceiling untouched.
         (b) every IN_WALL edge in the PRE-VOTE layers (record, judged,
             resolved): re-pointed to the polygon segment that actually
             claims that node's box in that layer (nearest plane with
             tangent overlap), evidence updated (wall id, axis, plane,
             distance, on-wall footprint recomputed from the same box).
             An edge whose new distance exceeds WALL_TOL is KEPT with a
             caveat — a judge ruled on it; distance drift is recorded,
             never silently deleted.
  DOES NOT touch voted/settled/grouped — those layers are REBUILT from
         resolved by their own modules (build_voted, materialize_layers)
         so the new walls and vote boxes flow down mechanically.
  A MISTAKE looks like: an edge silently dropped or re-typed, a wall
         node keeping v1 geometry under a new name, or a layer edited
         that a builder owns.

Run:  python graph/migrate_walls_w5.py --scene living_marble          (dry)
      python graph/migrate_walls_w5.py --scene living_marble --apply
"""
import argparse
import json
import shutil
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
for _p in (HERE, HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import paths  # noqa: E402
import scene_state  # noqa: E402

WALL_TOL = 0.10       # m — build_edges' IN_WALL claim distance
TANGENT_SLACK = 0.10  # m — footprint-vs-segment-extent overlap slack


def interval_plane_dist(lo, hi, v):
    if lo <= v <= hi:
        return 0.0
    return min(abs(lo - v), abs(hi - v))


AXIS_KEEP_MARGIN = 0.05  # m — an edge keeps its recorded axis unless a
                         # cross-axis segment is closer by more than this
                         # (breaks corner-object distance ties in favour
                         # of the judged relationship; a decisively
                         # closer cross-axis wall is a CORRECTION and
                         # wins — obj_034's historic tie-order claim)


def seg_claim(segs, g, prefer_axis=None):
    """The polygon segment nearest this box (build_edges semantics,
    walked over segments with a tangent-overlap guard). Returns
    (seg, distance, overlapped) — overlapped False means the fallback
    nearest-by-distance was used (caveat-worthy). prefer_axis: the old
    edge's recorded raw wall axis; see AXIS_KEEP_MARGIN."""
    lo, hi = g["aabb_min"], g["aabb_max"]
    best, best_any, best_axis = None, None, None
    for s in segs:
        if s["kind"] != "connector":
            axi = 0 if s["axis"] == "x" else 2
            tax = 2 if axi == 0 else 0
            tc = 1 if axi == 0 else 0
            p, q = s["endpoints_raw"]
            t0, t1 = sorted((p[tc], q[tc]))
            d = interval_plane_dist(lo[axi], hi[axi], s["plane_raw_m"])
            ovl = not (hi[tax] < t0 - TANGENT_SLACK
                       or lo[tax] > t1 + TANGENT_SLACK)
        else:
            n2 = np.asarray(s["inward_normal_raw"], float)
            c = float(s["plane_offset_raw"])
            corners = np.array([[x, z] for x in (lo[0], hi[0])
                                for z in (lo[2], hi[2])], float)
            sd = corners @ n2 - c
            d = 0.0 if (sd.min() < 0 < sd.max()) else float(
                np.abs(sd).min())
            p, q = np.asarray(s["endpoints_raw"], float)
            tdir = q - p
            L = float(np.linalg.norm(tdir))
            t = (corners - p) @ (tdir / L)
            ovl = not (t.max() < -TANGENT_SLACK or t.min() > L + TANGENT_SLACK)
        if ovl and (best is None or d < best[1]):
            best = (s, d)
        if (ovl and prefer_axis is not None
                and s.get("axis") == prefer_axis
                and (best_axis is None or d < best_axis[1])):
            best_axis = (s, d)
        if best_any is None or d < best_any[1]:
            best_any = (s, d)
    if (best_axis is not None and best is not None
            and best_axis[1] <= best[1] + AXIS_KEEP_MARGIN):
        return best_axis[0], best_axis[1], True
    if best is not None:
        return best[0], best[1], True
    return best_any[0], best_any[1], False


def arch_nodes_from_polygon(poly, floor_y, ceil_y):
    nodes = []
    for s in poly["segments"]:
        nid = "arch_" + s["id"]
        base = {
            # source stays "envelope": every consumer (build_edges,
            # rederive_voted_edges, edge_carry, viewer) selects
            # architecture by source == "envelope"; the polygon origin
            # lives in provenance.detector
            "id": nid, "source": "envelope", "type": "architecture",
            "label": f"wall {s['id'].split('_')[-1]}",
            "label_provisional": False, "labels": [],
            "distinct_labels": ["wall"],
            "evidence": {"views": [], "n_detections": 0, "n_whole": 0,
                         "members": [], "measured": s["status"] == "measured",
                         "traced_ink_fraction": s["traced_ink_fraction"],
                         "length_m": s["length_m"],
                         **({"fit": s["evidence"]} if s.get("evidence")
                            else {})},
            "provenance": {"manifest": None, "peak_score": None, "flags": [],
                           "detector": "room_shell.py --poly (W4) via "
                                       "migrate_walls_w5"},
            "open_questions": [],
        }
        if s["kind"] != "connector":
            axi_ch = s["axis"]
            side = s["interior_side_raw"]
            normal = [0.0, 0.0, 0.0]
            normal[0 if axi_ch == "x" else 2] = float(-side)
            tc = 1 if axi_ch == "x" else 0
            p, q = s["endpoints_raw"]
            t0, t1 = sorted((p[tc], q[tc]))
            base["geometry"] = {
                "plane": {"axis": axi_ch, "value_raw": s["plane_raw_m"],
                          "inward_normal_raw": normal,
                          "note": "polygon shell segment (W4 trace->"
                                  "close->merge; majority plane)"},
                "extent": {("z_raw" if axi_ch == "x" else "x_raw"): [t0, t1],
                           "y_raw": [ceil_y, floor_y]},
                "yaw": None, "amodal": None}
        else:
            n2 = s["inward_normal_raw"]
            base["label"] = f"wall {s['id'].split('_')[-1]} (connector)"
            base["geometry"] = {
                "plane": {"axis": None, "kind": "connector",
                          "inward_normal_raw": [n2[0], 0.0, n2[1]],
                          "offset_raw": s["plane_offset_raw"],
                          "note": "polygon connector segment — angled "
                                  "outline piece; defines interior only "
                                  "(no axis-aligned plane)"},
                "extent": {"endpoints_raw": s["endpoints_raw"],
                           "y_raw": [ceil_y, floor_y]},
                "yaw": None, "amodal": None}
        nodes.append(base)
    return nodes


def migrate_edges(edges, nodes_by_id, segs, layer, report):
    n_seen = n_repoint = n_far = 0
    for e in edges:
        if e.get("type") != "IN_WALL":
            continue
        n_seen += 1
        node = nodes_by_id.get(e["a"])
        if node is None:
            report.append(f"  {layer}: {e['a']} IN_WALL — node not in "
                          "layer, edge left verbatim (caveat added)")
            e.setdefault("caveats", []).append(
                "w5_wall_migration: node absent from layer, not re-pointed")
            continue
        pax = e.get("evidence", {}).get("wall_axis")
        if pax not in ("x", "z"):
            # slim-evidence layers (resolved): the old v1 wall id names
            # its axis — arch_wall_x_high -> "x", arch_wall_z_low -> "z"
            for ch in ("x", "z"):
                if str(e["b"]).startswith(f"arch_wall_{ch}_"):
                    pax = ch
        s, d, ovl = seg_claim(segs, node["geometry"], prefer_axis=pax)
        old_b, old_d = e["b"], e.get("evidence", {}).get("wall_distance_m")
        new_b = "arch_" + s["id"]
        g = node["geometry"]
        ev = e.setdefault("evidence", {})
        if s["kind"] != "connector":
            tcol = 2 if s["axis"] == "x" else 0
            ev.update({"wall_distance_m": round(d, 3),
                       "wall_axis": s["axis"],
                       "wall_value_raw": s["plane_raw_m"],
                       "wall_segment": s["id"],
                       "on_wall_tangent_raw": [round(g["aabb_min"][tcol], 3),
                                               round(g["aabb_max"][tcol], 3)],
                       "on_wall_y_raw": [round(g["aabb_min"][1], 3),
                                         round(g["aabb_max"][1], 3)]})
        else:
            ev.update({"wall_distance_m": round(d, 3),
                       "wall_axis": "connector",
                       "wall_value_raw": None,
                       "wall_segment": s["id"],
                       "on_wall_y_raw": [round(g["aabb_min"][1], 3),
                                         round(g["aabb_max"][1], 3)]})
        prev = ev.get("w5_migration")
        ev["w5_migration"] = {"from": old_b, "old_distance_m": old_d}
        if prev:                       # idempotence: keep the FIRST origin
            ev["w5_migration"] = prev
        e["b"] = new_b
        if old_b != new_b:
            n_repoint += 1
        if d > WALL_TOL:
            n_far += 1
            e.setdefault("caveats", []).append(
                f"w5_wall_migration: distance to the claiming polygon "
                f"segment is {d:.3f} m (> {WALL_TOL} claim rule); edge "
                "kept — a judge ruled on it")
        if not ovl:
            e.setdefault("caveats", []).append(
                "w5_wall_migration: no tangent overlap with any segment; "
                "nearest-by-distance fallback used")
        report.append(f"  {layer}: {e['a']:9s} {old_b} -> {new_b}  "
                      f"d {old_d} -> {d:.3f}")
    return n_seen, n_repoint, n_far


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--apply", action="store_true")
    a = ap.parse_args()
    sd = paths.scene_dir(a.scene)
    gp = sd / "scene_graph.json"
    graph = json.loads(gp.read_text())
    sh = json.loads((sd / "room_shell.json").read_text())
    poly = sh.get("polygon")
    if poly is None:
        sys.exit("room_shell.json has no polygon block — run "
                 "room_shell.py --poly first")
    floor_y, ceil_y = sh["floor_y_raw"], sh["ceiling_y_raw"]

    # (a) record-layer architecture nodes
    old_walls = [n for n in graph["nodes"]
                 if str(n["id"]).startswith("arch_wall")]
    keep = [n for n in graph["nodes"]
            if not str(n["id"]).startswith("arch_wall")]
    new_walls = arch_nodes_from_polygon(poly, floor_y, ceil_y)
    print(f"[migrate] record arch walls: {[n['id'] for n in old_walls]} "
          f"-> {[n['id'] for n in new_walls]}")

    # (b) IN_WALL edges, pre-vote layers only
    report = []
    stats = {}
    for layer in ("record", "judged", "resolved"):
        if layer == "record":
            edges = graph["edges"]
            nodes = graph["nodes"]
        else:
            edges = graph[layer]["edges"]
            nodes = graph[layer]["nodes"]
        nbi = {n["id"]: n for n in nodes}
        stats[layer] = migrate_edges(edges, nbi, poly["segments"],
                                     layer, report)

    # self-check: no node may hold two IN_WALL edges to the SAME wall
    for layer in ("record", "judged", "resolved"):
        edges = graph["edges"] if layer == "record" \
            else graph[layer]["edges"]
        seen = set()
        for e in edges:
            if e.get("type") != "IN_WALL":
                continue
            k = (e["a"], e["b"])
            if k in seen:
                print(f"[migrate] WARNING {layer}: duplicate IN_WALL "
                      f"{k[0]} -> {k[1]} after migration — inspect")
            seen.add(k)

    for line in report:
        print(line)
    for layer, (n_seen, n_repoint, n_far) in stats.items():
        print(f"[migrate] {layer}: {n_seen} IN_WALL edges, "
              f"{n_repoint} re-pointed to a different wall, "
              f"{n_far} beyond the {WALL_TOL} m claim rule (caveated)")

    if not a.apply:
        print("[migrate] DRY RUN — nothing written (--apply to write)")
        return
    bak = gp.with_suffix(".json.pre_w5_walls.bak")
    if not bak.exists():
        shutil.copy2(gp, bak)
        print(f"[migrate] backup: {bak.name}")
    graph["nodes"] = keep + new_walls
    # We rewrote three layers at once: record (the wall nodes above, plus
    # its IN_WALL edges), judged and resolved. Stamp the EARLIEST of them,
    # `record`, because the stale sweep runs forward from whatever it is
    # given: stamping record marks judged, resolved and everything after
    # them stale, which is exactly right. Our edits to judged and resolved
    # were a repair of their wall edges, NOT a rebuild from the new record,
    # so they are still owed a proper re-run and must not look fresh.
    # Stamping the LATEST layer instead would leave judged and resolved
    # claiming to be up to date, which is the bug this fixes.
    scene_state.stamp(graph, "record")
    gp.write_text(json.dumps(graph, indent=1))
    print(f"[migrate] wrote {gp}")
    print("[migrate] the downstream layers are now MARKED STALE in the "
          "file automatically — rebuild them with build_voted --apply, "
          "then materialize_layers --settle-only --apply, then "
          "materialize_layers --apply")


if __name__ == "__main__":
    main()
