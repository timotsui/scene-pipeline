"""Audit realization of the cleaned scene graph, one object ID at a time.

The denominator is the newest complete, non-stale scene-graph layer.  This is
the graph after duplicate resolution, overlap cleanup, box voting, and product
grouping when those stages exist.  Raw detections are never the denominator.

Each graph object receives exactly one final outcome:

  placed_as_requested  its own ID appears in the final placement record
  replaced              a validated swap asset covers its slot
  not_placed            neither of the above, with the best saved reason

Those three populations must sum to the measured graph population.  Assets
that were added without a measured graph object are reported separately.

Run:  python eval_funnel.py
Out:  out/eval_renders/realization_funnel.json
"""
import json

import paths
from graph import scene_state


SCENES = ["natural_living", "sunlit_office", "blue_living",
          "panel_bedroom", "arch_bedroom", "plaster_bedroom",
          "bedroom_marble", "living_marble", "fresh04", "fresh06"]


def _load(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def _sub_round_results(compose_dir):
    """Object ID -> final sub-round receipt, across every kind of anchor."""
    out = {}
    for path in sorted((compose_dir / "sub_experiment").glob(
            "*/cp5_final/placements.json")):
        rec = _load(path) or {}
        for sub in rec.get("subs") or []:
            if sub.get("id"):
                out[sub["id"]] = sub
    return out


def _short_reason(entry):
    return entry.get("why") or entry.get("reason") or entry.get("status")


def _missing_reason(oid, failed_by, shopping_by, deferred_by,
                    sub_result_by, swaps_by_source, deletes_by):
    if oid in failed_by:
        return _short_reason(failed_by[oid]) or "final placement failed"

    shopping = shopping_by.get(oid)
    if shopping and shopping.get("status") == "NO_MATCH":
        return "no acceptable asset match in the retrieval library"

    sub = sub_result_by.get(oid)
    if sub:
        status = sub.get("status") or "UNKNOWN"
        if status == "PLACED":
            return ("placed in the small-object pass but absent from the "
                    "final scene record")
        if status == "NO_ASSET":
            return "no acceptable asset match in the retrieval library"
        if status == "NO_BOARD":
            return "support surface was unavailable to the small-object pass"
        return f"small-object pass ended with status {status}"

    if oid in deferred_by:
        return "deferred small object has no final placement receipt"

    if oid in swaps_by_source:
        return "proposed replacement did not reach the final scene"

    if oid in deletes_by:
        why = _short_reason(deletes_by[oid])
        return (f"removed by the composition review: {why}" if why else
                "removed by the composition review")

    return "no final placement receipt"


def audit_scene(scene):
    scene_dir = paths.scene_dir(scene)
    compose_dir = scene_dir / "compose"
    graph = _load(scene_dir / "scene_graph.json")
    fitted = _load(compose_dir / "fitted_preview.json")
    shopping = _load(compose_dir / "shopping.json")
    if graph is None or fitted is None or shopping is None:
        return {"available": False,
                "why": "no compatible scene graph and final compose receipts"}

    layer_name, layer = scene_state.current(graph)
    if not layer_name or not layer:
        return {"available": False,
                "why": "scene graph has no complete, non-stale layer"}

    nodes = layer.get("nodes") or []
    measured_by_id = {node["id"]: node for node in nodes}
    if len(measured_by_id) != len(nodes):
        raise ValueError(f"{scene}: duplicate IDs in graph layer {layer_name}")
    measured_ids = set(measured_by_id)

    placed = fitted.get("placed") or []
    placed_by_id = {entry["id"]: entry for entry in placed}
    if len(placed_by_id) != len(placed):
        raise ValueError(f"{scene}: duplicate IDs in final placement record")
    placed_ids = set(placed_by_id)

    edits = _load(compose_dir / "edit_proposals.json") or {}
    swaps_by_source = {}
    replacement_for = {}
    replacement_asset_ids = set()
    for swap in edits.get("swaps") or []:
        source_ids = {oid for oid in (swap.get("out") or [])
                      if oid in measured_ids}
        input_ids = {entry.get("id") for entry in (swap.get("in") or [])
                     if entry.get("id")}
        final_inputs = input_ids & placed_ids
        for oid in source_ids:
            swaps_by_source.setdefault(oid, []).append(swap)
            if final_inputs:
                replacement_for.setdefault(oid, set()).update(final_inputs)
        if source_ids:
            replacement_asset_ids.update(final_inputs)

    failed_by = {entry.get("id"): entry
                 for entry in ((fitted.get("not_placed") or []) +
                               (fitted.get("failed") or []))
                 if entry.get("id")}
    shopping_by = {entry["id"]: entry
                   for entry in shopping.get("items") or []}
    deferred_by = {entry["id"]: entry
                   for entry in shopping.get("subs_deferred") or []}
    sub_result_by = _sub_round_results(compose_dir)
    deletes_by = {entry["id"]: entry for entry in edits.get("deletes") or []
                  if entry.get("id")}

    outcomes = []
    counts = {"placed_as_requested": 0, "replaced": 0, "not_placed": 0}
    for oid in sorted(measured_ids):
        node = measured_by_id[oid]
        name = node.get("name") or node.get("label")
        if oid in placed_ids:
            outcome = "placed_as_requested"
            row = {"id": oid, "name": name, "outcome": outcome,
                   "asset_id": oid,
                   "asset_name": placed_by_id[oid].get("name")}
        elif oid in replacement_for:
            outcome = "replaced"
            rep_ids = sorted(replacement_for[oid])
            row = {"id": oid, "name": name, "outcome": outcome,
                   "replacement_ids": rep_ids,
                   "replacement_names": [placed_by_id[r].get("name")
                                          for r in rep_ids]}
        else:
            outcome = "not_placed"
            row = {"id": oid, "name": name, "outcome": outcome,
                   "reason": _missing_reason(
                       oid, failed_by, shopping_by, deferred_by,
                       sub_result_by, swaps_by_source, deletes_by)}
        counts[outcome] += 1
        outcomes.append(row)

    measured = len(measured_ids)
    accounted = sum(counts.values())
    if accounted != measured:
        raise AssertionError(
            f"{scene}: outcomes {accounted} do not sum to measured {measured}")

    covered = counts["placed_as_requested"] + counts["replaced"]
    extra_ids = sorted(placed_ids - measured_ids - replacement_asset_ids)
    extras = [{"id": oid, "name": placed_by_id[oid].get("name")}
              for oid in extra_ids]
    return {
        "available": True,
        "measured_layer": layer_name,
        "measured_scene_graph_objects": measured,
        **counts,
        "slots_filled": covered,
        "exact_match_pct": round(100.0 * counts["placed_as_requested"] /
                                 measured) if measured else None,
        "slot_coverage_pct": round(100.0 * covered / measured)
                             if measured else None,
        "extra_unmeasured_assets": len(extras),
        "extras": extras,
        "replacement_asset_count": len(replacement_asset_ids),
        "final_placement_records": len(placed_ids),
        "outcomes": outcomes,
    }


def main():
    table = {}
    for scene in SCENES:
        rec = audit_scene(scene)
        table[scene] = rec
        if not rec["available"]:
            print(f"[funnel] {scene:18s} -- {rec['why']}")
            continue
        print(
            f"[funnel] {scene:18s} "
            f"{rec['measured_scene_graph_objects']:3d} measured -> "
            f"{rec['placed_as_requested']:3d} as requested + "
            f"{rec['replaced']:2d} replaced + "
            f"{rec['not_placed']:2d} not placed = "
            f"{rec['slots_filled']:3d} filled "
            f"({rec['slot_coverage_pct']:3d}%); "
            f"{rec['extra_unmeasured_assets']} extra")

    out = paths.OUT / "eval_renders" / "realization_funnel.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "definition": {
            "denominator": ("objects in the newest complete, non-stale "
                            "scene-graph layer; never raw detections"),
            "invariant": ("placed_as_requested + replaced + not_placed "
                          "= measured_scene_graph_objects"),
            "extras": "placed assets with no measured graph-object slot",
        },
        "scenes": table,
    }, indent=1), encoding="utf-8")
    print(f"[funnel] -> {out}")


if __name__ == "__main__":
    main()
