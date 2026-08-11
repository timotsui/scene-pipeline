"""THE STATE OF THE SCENE — one place that answers "which layer is
current?", so nothing has to guess.

USER RULE (2026-08-09): "we need to always have a single source of truth
for the state of the scene, which should have the latest and greatest."

The scene graph is a stack of layers, each one a stage's edit of the one
before it. That is the right shape — but until now every consumer named
a layer by hand, and they named different ones. `resolved` was the last
name most of them learned, so they kept reading it long after the
vote stage had elected new boxes: 43 of 46 objects had a different
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
A half-layer (the retired `vote` node-sidecar, `voted_edges` with no
nodes) can never become the state of the scene.
"""

import time as _time

# oldest -> newest. Each is a stage's edit of the one before it.
CHAIN = (
    ("record",   "detection: every node found, with all its evidence"),
    ("judged",   "J0/J1 verdicts on the record"),
    ("resolved", "identity settled — duplicates merged, names fixed"),
    ("voted",    "the vote stage: boxes elected"),
    ("settled",  "J8 box rulings, J8s splits, J1 merges"),
    # node_evidence.py. USER RULING 2026-08-11: this is an EVOLUTION OF
    # THE SCENE STATE, not a note for a judge. Every node's stored crop
    # was cut around a box that has since moved, so the crops are STALE
    # and the pictures this stage names SUPERSEDE them. It sits after
    # `settled` and before `grouped` because it reads settled boxes on
    # purpose — grouped is J9's own output, and evidence that depended
    # on it would be feeding J9 its own verdict back.
    ("shown",    "node_evidence: the picture each node is actually seen "
                 "as — stale crops superseded"),
    ("grouped",  "J9: instances grouped into products"),
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


def is_stale(graph, name):
    """Was this layer built from something that has since been rewritten?

    A layer is an edit of the one before it, so rewriting layer N makes
    every layer AFTER N out of date by definition — it was computed from
    inputs that no longer exist. Marked, not deleted: the old content is
    still readable and still says which run produced it."""
    b = _layer(graph, name)
    return bool(b and b.get("stale_since"))


def present(graph, include_stale=False):
    """Every WHOLE layer in the file, oldest first. Whole = it has nodes;
    an edges-only or node-sidecar block is not a state of the scene.

    STALE LAYERS ARE EXCLUDED unless asked for. A layer left over from
    before its input was rewritten is not a state of the scene, it is a
    record of an old one."""
    out = []
    for name in NAMES:
        b = _layer(graph, name)
        if b and b.get("nodes") and (include_stale or not is_stale(graph, name)):
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


def member_evidence(graph):
    """A resolver: `f(node)` -> the RECORD detection records behind it.

    Every judge that reads pixels needs `evidence.members` — the per-view
    detections, each with the crop file cut for it. Only the RECORD nodes
    carry those. A later layer's node carries `members`, a list of ids,
    and the hops are not uniform: a `voted` node's members are record
    ids, but after a J8 split a `settled` node's members are RESOLVED
    ids, so one hop is not enough. This walks both, with each id standing
    for itself when it is not a cluster.

    ONE DEFINITION ON PURPOSE. edge_carry did this walk inline to build
    NEAR's truncation facts and judge_pairs got the same thing a
    different way (overlay voted boxes onto record nodes, keep the
    record's crops); two spellings of one rule is how this repo has
    repeatedly grown a second source of truth. Callers that need the
    record node itself, not its evidence, should still index `graph`."""
    rec = {n["id"]: n for n in (graph.get("nodes") or [])}
    res_src = {n["id"]: (n.get("members") or [n["id"]])
               for n in (graph.get("resolved") or {}).get("nodes") or []}

    def resolve(node):
        out = []
        for rid in (node.get("members") or [node["id"]]):
            for sid in res_src.get(rid, [rid]):
                m = rec.get(sid)
                if m:
                    out += ((m.get("evidence") or {}).get("members") or [])
        return out

    return resolve


class JudgeView:
    """What a pair judge needs from ONE layer, in one shape.

    `nodes`    {id: node} for the layer's object nodes, each carrying a
               `label` whatever the layer calls it (the record says
               `label`, every later layer inherits `name` from
               `resolved`). Geometry is the layer's own — no overlay.
    `edges`    THE list inside the graph, not a copy: a judge appends its
               nominations to it and writing the graph persists them.
    `nesting`  {node id: [containment facts]}, however the layer stores
               them — on the nodes in the record, in a block afterwards.
    `meta_into` the dict a judge should write its run metadata into, so
               the record's metadata is never overwritten by a re-judge
               of a later layer.

    WHY THIS EXISTS. Until 2026-08-11 the two loop-back judges got this
    from `rederive_voted_edges.layer_of` plus an `overlay_voted_geometry`
    call that pasted voted boxes onto RECORD nodes. That module wrote a
    half-layer, `graph['voted_edges']`, which the user retired on 08-11
    (every layer must be whole; edges follow nodes inside a layer). The
    judges still have to run on the voted edges as a second pass — so
    they read the voted LAYER's own edges, and the accessor moved here,
    beside the chain it is reading.
    """

    __slots__ = ("name", "nodes", "edges", "nesting", "meta_into")

    def __init__(self, name, nodes, edges, nesting, meta_into):
        self.name = name
        self.nodes = nodes
        self.edges = edges
        self.nesting = nesting
        self.meta_into = meta_into


def judge_view(graph, name):
    """A JudgeView onto layer `name`. Raises SystemExit if it is absent.

    `record` is the irregular one — its nodes and edges are the file's
    top level and its nesting facts sit on the nodes — so it is handled
    here and no judge has to know."""
    if name == "record":
        det = {n["id"]: n for n in (graph.get("nodes") or [])
               if n.get("source") == "detection"}
        return JudgeView(
            "record", det, graph.setdefault("edges", []),
            {nid: (n.get("nesting") or []) for nid, n in det.items()},
            graph)

    if name not in NAMES:
        raise SystemExit(
            f"[scene_state] '{name}' is not a layer. The chain is: "
            f"{', '.join(NAMES)}.")
    lay = _layer(graph, name)
    if not lay or not lay.get("nodes"):
        raise SystemExit(
            f"[scene_state] the scene has no `{name}` layer — the stage "
            f"that writes it has not run. Present: "
            f"{', '.join(present(graph, include_stale=True)) or 'nothing'}.")

    # Two things every later layer needs adapting for, and both are the
    # reason this helper exists rather than each judge doing it:
    #
    #  * NAME vs LABEL. The record says `label`; every layer from
    #    `resolved` on inherits `name`. The judges' prompts quote
    #    `label`, so give them one spelling.
    #  * NO EVIDENCE BLOCK. A later layer's node carries `members` (ids)
    #    and no `evidence`, so a judge indexing it for crops finds
    #    nothing and silently judges on no pictures. Walk down to the
    #    record and attach the real detections.
    #
    # The nodes here are COPIES. A judge appends verdicts to EDGES, which
    # are the graph's own list; nothing is expected to write a node
    # through this view, and a copy makes that safe rather than subtle.
    ev = member_evidence(graph)
    det = {}
    for n in lay["nodes"]:
        if not n.get("geometry"):
            continue
        det[n["id"]] = dict(n,
                            label=n.get("label") or n.get("name") or "",
                            evidence={**(n.get("evidence") or {}),
                                      "members": ev(n)})
    return JudgeView(name, det, lay.setdefault("edges", []),
                     lay.get("nesting") or {}, lay)


def stamp(graph, name, note="", run_id=None):
    """Record IN THE FILE which layer is current, and MARK EVERY LAYER
    AFTER IT STALE.

    THE STALE SWEEP EXISTS FOR THE UNATTENDED RUN (user requirement
    2026-08-11: "make sure this is going to be smooth for the 100
    automated runs"). Rewriting a layer silently invalidates everything
    downstream — those layers were computed from inputs that no longer
    exist. Before this, the file could hold a NEWER-BY-ORDER layer built
    from OLDER inputs, and `check()` reported a disagreement a human had
    to interpret. On one scene that is a conversation; on a hundred it is
    a stall, or worse, a stage quietly reading last run's answer.

    So the rule is mechanical: writing layer N stamps N and marks
    N+1..end stale. A stale layer is skipped by present()/current() and
    stops being stale the moment its own stage rewrites it — which, in
    an ordered run, happens moments later. On a FRESH scene nothing
    downstream exists yet, so the sweep does nothing at all.

    Marked, never deleted: the content stays readable, and `stale_since`
    names the layer whose rewrite invalidated it.

    EVERY LAYER ALSO RECORDS WHEN IT WAS WRITTEN (2026-08-11). The stale
    sweep can only see LAYERS, and a stage's real inputs are often FILES —
    the vote's preview manifest, the judges' verdict sidecars. Re-run one
    of those stages alone and it rewrites a file that a layer was built
    from, while every layer still looks fresh, because nothing in the
    chain knows the file exists. `written_at` is what lets the gate
    answer that: a layer whose input file is NEWER than the layer itself
    was built from something that has since changed."""
    lay = graph.setdefault("layer", {})
    lay["canonical"] = name
    lay["chain"] = list(NAMES)
    lay["canonical_note"] = (
        note or f"{name}: {DESCRIPTIONS.get(name, '')}. The newest whole "
        "layer is the state of the scene; earlier layers are kept for "
        "reference and are SUPERSEDED for geometry.")
    swept = []
    if name in NAMES:
        for later in NAMES[NAMES.index(name) + 1:]:
            b = _layer(graph, later)
            if not (b and b.get("nodes")):
                continue
            b["stale_since"] = {"layer": name, "run": run_id,
                                "why": (f"`{name}` was rewritten after "
                                        f"this layer was built, so this "
                                        f"was computed from inputs that "
                                        f"no longer exist. Re-run "
                                        f"{later}'s stage.")}
            swept.append(later)
    # a layer being written is, by definition, no longer stale
    me = _layer(graph, name)
    if isinstance(me, dict):
        me.pop("stale_since", None)
        me["written_at"] = _time.time()
    if name == "record":
        # `record` is the file's top level, and _layer() builds a fresh
        # dict for it rather than returning one that lives in the graph —
        # so the line above would write to a throwaway. Put it where it
        # will actually be saved.
        graph.setdefault("layer", {})["record_written_at"] = _time.time()
    lay["stale"] = present(graph, include_stale=True)
    lay["stale"] = [n for n in lay["stale"] if is_stale(graph, n)]
    if swept:
        print(f"[state] `{name}` rewritten — marked stale: "
              f"{', '.join(swept)} (re-run their stages)")
    return graph


def written_at(graph, name):
    """When this layer was last written, as epoch seconds, or None.

    None means the layer predates the stamp recording it (2026-08-11) —
    an honest "I do not know", which a caller must treat as "cannot
    check", never as "old" or as "fine"."""
    if name == "record":
        return (graph.get("layer") or {}).get("record_written_at")
    b = graph.get(name)
    return b.get("written_at") if isinstance(b, dict) else None


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
