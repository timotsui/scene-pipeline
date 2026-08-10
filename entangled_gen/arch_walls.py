"""Room bounds from a scene graph's ARCHITECTURE nodes — id-agnostic.

Written 2026-08-10 (unattended-run audit): five compose modules looked
walls up by the literal v1 ids (arch_wall_x_low..) and crash with
KeyError on any W5 polygon graph (arch_wall_00..NN). This is the one
shared way to read the room's axis-aligned wall planes; it works on v1
4-wall graphs, W5 polygon graphs (connector segments have axis None
and are outline-only — excluded from axis extremes), and the legacy
grid-bound placeholder graphs alike.

All values RAW frame, exactly as stored on the nodes; callers apply
their own frame transforms.
"""


def wall_axis_planes(nodes):
    """(xs, zs, floor_y, ceil_y) from architecture nodes.

    xs / zs: SORTED lists of the wall plane values per axis (take
    [0] / [-1] for the room's outer bounds — a polygon shell may carry
    more than one wall per axis side). floor_y / ceil_y: plane values,
    None when absent. Raises ValueError with a clear message when an
    axis has fewer than 2 wall planes — never a silent wrong room."""
    xs, zs, floor_y, ceil_y = [], [], None, None
    for n in nodes:
        nid = str(n.get("id", ""))
        if not nid.startswith("arch_"):
            continue
        pl = (n.get("geometry") or {}).get("plane") or {}
        if nid == "arch_floor":
            floor_y = pl.get("value_raw")
        elif nid == "arch_ceiling":
            ceil_y = pl.get("value_raw")
        elif nid.startswith("arch_wall") and pl.get("axis") == "x":
            xs.append(pl["value_raw"])
        elif nid.startswith("arch_wall") and pl.get("axis") == "z":
            zs.append(pl["value_raw"])
    if len(xs) < 2 or len(zs) < 2:
        raise ValueError(
            f"architecture nodes carry {len(xs)} x / {len(zs)} z wall "
            "planes — need >= 2 per axis (is the graph's record layer "
            "missing its shell nodes?)")
    return sorted(xs), sorted(zs), floor_y, ceil_y


def arch_label(nid):
    """Human-readable name for an architecture node id, any naming
    scheme (v1 arch_wall_x_low, W5 arch_wall_00, legacy arch_wall_x0)."""
    fixed = {"arch_floor": "the floor", "arch_ceiling": "the ceiling"}
    if nid in fixed:
        return fixed[nid]
    if str(nid).startswith("arch_wall"):
        return "wall " + str(nid)[len("arch_wall_"):]
    return str(nid)
