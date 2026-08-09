"""THE STATE OF THE SCENE — one place that answers "which layer is
current?", so nothing has to guess.

USER RULE (2026-08-09): "we need to always have a single source of truth
for the state of the scene, which should have the latest and greatest."

The scene graph is a stack of layers, each one a stage's edit of the one
before it. That is the right shape — but until now every consumer named
a layer by hand, and they named different ones. `resolved` was the last
name most of them learned, so they kept reading it long after the
vote-box stage had elected new boxes: 43 of 46 objects had a different
box in `resolved` than the one actually decided, and the glass door
differed by 300x on one axis. Nothing was wrong in the file. Nothing
said which part of it was current.

So: THE CHAIN IS DECLARED ONCE, HERE. `current()` returns the newest
layer that actually exists, and every reader asks for that instead of
naming one. Adding a stage means adding its name to CHAIN — every
consumer follows automatically, which is the point.

Two ways a layer can be named current, and they must agree:
  * ORDER — this module's CHAIN, newest last. Self-maintaining.
  * POINTER — graph["layer"]["canonical"], stamped by the stage that
    wrote the layer. Explicit, and readable by anything that opens the
    file without importing this module.
`check()` reports a disagreement rather than silently preferring one;
a mismatch means a stage wrote a layer and did not stamp it, which is a
bug in that stage.

A layer is only eligible to be current when it is WHOLE — it has nodes.
A half-layer (the retired `carve` node-sidecar, `carved_edges` with no
nodes) can never become the state of the scene.
"""

# oldest -> newest. Each is a stage's edit of the one before it.
CHAIN = (
    ("record",   "detection: every node found, with all its evidence"),
    ("judged",   "J0/J1 verdicts on the record"),
    ("resolved", "identity settled — duplicates merged, names fixed"),
    ("voted",    "the vote-box stage: boxes elected"),
    ("settled",  "J8 box rulings, J8s splits, J1 merges"),
    ("carved",   "J9 same-product annotations"),
)
NAMES = tuple(n for n, _ in CHAIN)
DESCRIPTIONS = dict(CHAIN)


def _layer(graph, name):
    """The block for a layer name. `record` is the file's top level, not
    a sub-block — the only irregular one, and it is handled here so no
    caller has to know."""
    if name == "record":
        return {"nodes": graph.get("nodes") or [],
                "edges": graph.get("edges") or []}
    b = graph.get(name)
    return b if isinstance(b, dict) else None


def present(graph):
    """Every WHOLE layer in the file, oldest first. Whole = it has nodes;
    an edges-only or node-sidecar block is not a state of the scene."""
    out = []
    for name in NAMES:
        b = _layer(graph, name)
        if b and b.get("nodes"):
            out.append(name)
    return out


def current_name(graph):
    """The newest whole layer. This is THE state of the scene."""
    got = present(graph)
    return got[-1] if got else None


def current(graph):
    """(name, layer) for the newest whole layer, or (None, None)."""
    name = current_name(graph)
    return (name, _layer(graph, name)) if name else (None, None)


def nodes(graph):
    name, lay = current(graph)
    return (lay or {}).get("nodes") or []


def edges(graph):
    name, lay = current(graph)
    return (lay or {}).get("edges") or []


def stamp(graph, name, note=""):
    """Record IN THE FILE which layer is current. Called by the stage that
    just wrote one, so a reader that never imports this module can still
    see the answer."""
    lay = graph.setdefault("layer", {})
    lay["canonical"] = name
    lay["chain"] = list(NAMES)
    lay["canonical_note"] = (
        note or f"{name}: {DESCRIPTIONS.get(name, '')}. The newest whole "
        "layer is the state of the scene; earlier layers are kept for "
        "reference and are SUPERSEDED for geometry.")
    return graph


def check(graph):
    """Compare the two answers. Returns (ok, message)."""
    by_order = current_name(graph)
    pointer = (graph.get("layer") or {}).get("canonical")
    if by_order is None:
        return False, "no whole layer in this graph"
    if pointer is None:
        return False, (f"newest whole layer is '{by_order}' but nothing "
                       f"has stamped graph['layer']['canonical'] — the "
                       f"stage that wrote it did not declare it")
    if pointer != by_order:
        return False, (f"DISAGREEMENT: the chain says '{by_order}' is "
                       f"newest, the file says '{pointer}'. A stage wrote "
                       f"a layer without stamping it, or stamped one it "
                       f"did not write.")
    return True, f"current layer: {by_order}"
