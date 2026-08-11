"""THE ORDER OF THE GRAPH CHAIN — declared once, in a table.

Until now the eleven steps from the vote to `grouped` lived in a person's
head and in docs/AUTOMATION_READINESS.md. Running a scene meant a human
typing eleven commands with the right flags in the right order. That
works for one scene. Rule #1 is a hundred scenes with nobody watching, and
an order that lives in prose cannot be executed, checked, or resumed.

So the order is DATA here, and everything else reads it:

    run_scene.py       walks this table and calls each stage
    scene_gate.py      uses `reads`/`writes`/`artifacts` to decide whether
                       the state is legal before and after each stage

WHAT A ROW PROMISES. Each stage names the layer it READS and the layer it
WRITES, and those two names are the module's whole boundary with the rest
of the pipeline. A stage may look at nothing older than `reads` and must
leave `writes` current and fresh. That is what "clear boundaries between
modules" means in practice, and the gate enforces it between every pair.

WHY SOME ROWS WRITE NO LAYER. Three kinds of stage live here:

  * LAYER stages edit the scene graph and stamp a new layer
    (build_voted -> `voted`, materialize -> `settled` / `grouped`,
    node_evidence -> `shown`).
  * JUDGE stages spend model calls and write a VERDICT FILE next to the
    graph (multiplicity.json, split_cuts.json, same_product.json). They
    deliberately do not touch the graph; materialize is what turns their
    verdicts into a layer. Keeping that split is why a judge can be
    re-run without rewriting geometry.
  * SIDECAR stages write neither a layer nor a verdict but a working file
    the next stage needs (vote_doubts.json, node_views.json).

For the last two kinds `writes` is None and `artifacts` carries the
check instead: the named file must exist AND have been written during
this stage's run. That mtime test is the only generic way to catch the
failure this whole exercise is about — a stage that exits 0 having done
nothing.

WHY `reads` IS "PRESENT AND FRESH", NOT "CURRENT". node_evidence reads
`settled` by name on purpose even when `shown` already exists from an
earlier run, because its output feeds J9 and `grouped` is J9's own
verdict. Requiring `reads` to be the CURRENT layer would make a re-run
of a middle stage illegal. Requiring it to be present and not stale is
the real constraint.

ADDING A STAGE means adding a row here. Nothing else has to learn it.
"""
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
for _p in (HERE, HERE.parent):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

PY = sys.executable

# Written 2026-08-11 against the verified 08-11 living_marble run
# (docs/AUTOMATION_READINESS.md section 1). The flags shown are the ones
# that survive the default-inversion of the same date: writing is now the
# default everywhere, so a row carries a flag only when the flag SELECTS
# a behaviour, never merely to switch writing on.


class Stage:
    """One step of the chain.

    key        short name; what --skip and --from/--until take
    title      one line for the log, in plain English
    argv       the command, as a list, given the scene name
    reads      layer that must be present and not stale BEFORE this runs
    writes     layer that must be present, fresh and stamped AFTER it
    artifacts  files (relative to the scene dir) that must exist and have
               been touched DURING this run
    graph_keys top-level scene_graph.json blocks that must exist after it
               — for the stages that edit the graph without adding a
               layer (`vote`, `voted_edges`: neither has nodes, so
               neither can ever become the state of the scene)
    inputs     FILES this stage consumes that ANOTHER stage produced.
               These are the dependencies the layer chain cannot see, and
               they are the hole this field closes. The stale sweep only
               understands LAYERS, but half of what these stages read is
               a file: the vote's preview manifest, the judges' verdict
               sidecars. Re-run one of those stages by itself and it
               rewrites a file that a later layer was built from, while
               every layer still looks fresh — because nothing in the
               chain knew the file was an input. With `inputs` declared,
               the gate can compare each file's mtime against the
               `written_at` of the layer that consumed it and say so.
    llm        does this stage spend model calls
    gpu        does this stage want the GPU (so a runner can warn about
               the clock lock, see docs/POWER_CRASHES.md)
    """

    def __init__(self, key, title, argv, reads=None, writes=None,
                 artifacts=(), graph_keys=(), inputs=(), llm=False,
                 gpu=False, note=""):
        self.key = key
        self.title = title
        self._argv = argv
        self.reads = reads
        self.writes = writes
        self.artifacts = tuple(artifacts)
        self.graph_keys = tuple(graph_keys)
        self.inputs = tuple(inputs)
        self.llm = llm
        self.gpu = gpu
        self.note = note

    def argv(self, scene, extra=()):
        return list(self._argv(scene)) + list(extra)

    def __repr__(self):
        return f"<Stage {self.key}: {self.reads or '-'} -> {self.writes or '-'}>"


CHAIN = (
    Stage(
        "vote", "elect a box for every object from its own plan and "
                "elevation slices",
        lambda sc: [PY, "slicevote.py", "--scene", sc],
        reads="resolved", writes=None,
        artifacts=("vote/slicevote_report.json",),
        gpu=True,
        note="The vote is deterministic: the same node under the same "
             "sha and parameters gives identical intermediates, so a "
             "difference between runs is code or parameters, never drift.",
    ),
    Stage(
        "doubts", "write what the vote was unsure about into the graph",
        lambda sc: [PY, "graph/record_vote_doubts.py", "--scene", sc],
        reads="resolved", writes=None,
        artifacts=("graph/vote_doubts.json",),
        graph_keys=("vote",),
        note="This is the stage the no-op trap was caught on: without its "
             "flag it updated vote_doubts.json but NOT the graph `vote` "
             "block J8 reads, and J8 judged stale doubts. Writing is the "
             "default now.",
    ),
    Stage(
        "voted", "build the `voted` layer from the elected boxes",
        lambda sc: [PY, "graph/build_voted.py", "--scene", sc],
        reads="resolved", writes="voted",
        inputs=("scene_manifest_slicevote_preview.json",
                "vote/slicevote_report.json"),
    ),
    Stage(
        "voted_edges", "re-derive the edges against the boxes the vote elected",
        lambda sc: [PY, "graph/rederive_voted_edges.py", "--scene", sc],
        reads="resolved", writes=None,
        graph_keys=("voted_edges",),
        note="Edges follow nodes (edge_carry.py). It reads the RESOLVED "
             "node set and the voted boxes, and writes graph['voted_edges'] "
             "— an edges-only block, which is why it is not a layer: a "
             "block with no nodes can never be the state of the scene. "
             "Both judges below read it by that name and refuse to run "
             "without it, so the ordering is enforced twice.",
    ),
    Stage(
        "j8", "J8: is this one object or several?",
        lambda sc: [PY, "graph/judge_multiplicity.py", "--scene", sc],
        reads="voted", writes=None,
        artifacts=("graph/multiplicity.json",),
        llm=True, gpu=True,
    ),
    Stage(
        "j8s", "J8s: where do the pieces of a split object cut?",
        lambda sc: [PY, "graph/split_cuts.py", "--scene", sc],
        reads="voted", writes=None,
        artifacts=("graph/split_cuts.json",),
        llm=True, gpu=True,
    ),
    Stage(
        "settled", "materialize the J8 rulings, the J8s splits and the "
                   "J1 merges into `settled`",
        lambda sc: [PY, "graph/materialize_layers.py", "--scene", sc,
                    "--settle-only"],
        reads="voted", writes="settled",
        inputs=("graph/multiplicity.json", "graph/split_cuts.json",
                "graph/vote_doubts.json",
                "scene_manifest_slicevote_preview.json"),
        note="SAME MODULE AS `grouped`, AND THE DIFFERENCE MATTERS. "
             "--settle-only writes geometry; without it the module also "
             "writes `grouped`, which is J9's output. Run the full one "
             "here and you write `grouped` from a state J9 has never "
             "seen. Geometry first, group last.",
    ),
    Stage(
        "views", "plan (and where needed render) an aimed look at every "
                 "settled box",
        lambda sc: [PY, "graph/node_views.py", "--scene", sc,
                    "--layer", "settled"],
        reads="settled", writes=None,
        artifacts=("graph/node_views.json",),
        gpu=True,
        note="Usually nearly free: on the 08-11 run 33 of 35 repairs "
             "needed no render at all, because the vote's own renders "
             "already framed the boxes. The GPU is only touched when a "
             "node genuinely has no usable picture.",
    ),
    Stage(
        "evidence", "decide the one picture each node is seen as -> `shown`",
        lambda sc: [PY, "graph/node_evidence.py", "--scene", sc],
        reads="settled", writes="shown",
        inputs=("graph/node_views.json",),
        gpu=True,
        note="Reads `settled` BY NAME, never 'whatever is current'. It "
             "feeds J9, and `grouped` is J9's own output — evidence taken "
             "from `grouped` would hand J9 back its own verdict as proof "
             "of itself.",
    ),
    Stage(
        "j9", "J9: which instances are the same product?",
        lambda sc: [PY, "graph/judge_same_product.py", "--scene", sc],
        reads="shown", writes=None,
        artifacts=("graph/same_product.json",),
        llm=True,
    ),
    Stage(
        "grouped", "materialize J9's grouping into `grouped`",
        lambda sc: [PY, "graph/materialize_layers.py", "--scene", sc],
        reads="shown", writes="grouped",
        inputs=("graph/same_product.json", "graph/multiplicity.json",
                "graph/split_cuts.json",
                "scene_manifest_slicevote_preview.json"),
        note="⚠ `reads` IS CONSERVATIVE, NOT LITERAL. This pass does not "
             "read `shown` at all — it starts again from `voted` and "
             "re-applies the same four geometry rules `settled` did, then "
             "adds J9's grouping on top. `shown` is declared because it is "
             "the NEWEST layer that must be fresh for this to be a legal "
             "moment to run, and the stale sweep makes that imply every "
             "earlier layer is fresh too. The audit note stands: because "
             "this pass rebuilds rather than inherits, the per-node "
             "`shown` block does NOT survive into `grouped`. See "
             "docs/PLAN_AUTOMATION_2026-08-11.md.",
    ),
)

#: STEP 3 — COMPOSE. Turns the finished graph into an actual furnished
#: scene: what holds what up, what to buy, where to put it, and then the
#: fitting pass that stops things clipping.
#:
#: KEPT AS ITS OWN TUPLE, NOT APPENDED TO CHAIN, for two reasons. The
#: graph chain ends at `grouped` and that is a real boundary — everything
#: above is measurement of a room that exists, everything here is
#: proposal about a room being built. And these modules are less settled:
#: PLAN_COMPOSE_LOOP.md says the later ones are "direction only, not
#: designed", and until 2026-08-11 they were run BY HAND, one at a time,
#: with the user gating each. There is no driver anywhere in the repo.
#:
#: THE ORDER IS READ OFF THE CODE, NOT INVENTED. Each module names the
#: file it cannot start without — consistency wants supported_by.json,
#: pick wants shopping.json, fit_walk wants fit_check.json and picks.json
#: — so the dependency order is a fact about the modules. Wiring them
#: here makes them RUNNABLE AND CHECKED. It does not make them ruled on;
#: that is still the user's, gate by gate.
COMPOSE = (
    Stage(
        "supported_by", "decide what holds each object up",
        lambda sc: [PY, "compose/supported_by.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/supported_by.json",),
        llm=True,
    ),
    Stage(
        "consistency", "check every contact edge against both endpoints' "
                       "support",
        lambda sc: [PY, "compose/consistency.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/consistency.json",),
        inputs=("compose/supported_by.json",),
        llm=True,
    ),
    Stage(
        "snap", "seat each object against what supports it",
        lambda sc: [PY, "compose/snap.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/snap.json",),
        inputs=("compose/supported_by.json",),
        llm=True,
        note="This is the stage that re-seats the boxes SHELL_EPS lifted "
             "off the floor, so a scene that has not reached it still "
             "shows floor-standing objects a few centimetres in the air.",
    ),
    Stage(
        "propose_edits", "propose the box and identity edits the checks "
                         "asked for",
        lambda sc: [PY, "compose/propose_edits.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/edit_proposals.json",),
        inputs=("compose/consistency.json", "compose/supported_by.json"),
        llm=True,
    ),
    Stage(
        "shopping", "turn the settled objects into a shopping list",
        lambda sc: [PY, "compose/shopping.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/shopping.json",),
        inputs=("compose/supported_by.json", "compose/edit_proposals.json"),
        llm=True,
    ),
    Stage(
        "pick", "choose an asset for every item on the list",
        lambda sc: [PY, "compose/pick.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/picks.json",),
        inputs=("compose/shopping.json",),
        llm=True,
    ),
    Stage(
        "fit_preview", "place the chosen assets in the room",
        lambda sc: [PY, "compose/fit_preview.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/fitted_preview.json",),
        inputs=("compose/picks.json",),
    ),
    Stage(
        "fit_check", "report what clips and what leaves the room",
        lambda sc: [PY, "compose/fit_check.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/fit_check.json",),
        inputs=("compose/fitted_preview.json",),
        note="REPORT ONLY — it fixes nothing. This is the file the "
             "Collision-Free number should be read from, because it "
             "measures the PLACED MESHES rather than the graph's boxes.",
    ),
    Stage(
        "fit_declip", "push clipping pairs apart until nothing overlaps",
        lambda sc: [PY, "compose/fit_declip.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/fit_declip.json",),
        inputs=("compose/fitted_preview.json",),
    ),
    Stage(
        "fit_walk", "swap a candidate when the chosen one does not fit",
        lambda sc: [PY, "compose/fit_walk.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/fit_walk.json",),
        inputs=("compose/fit_check.json", "compose/picks.json"),
    ),
)

COMPOSE_KEYS = tuple(s.key for s in COMPOSE)

KEYS = tuple(s.key for s in CHAIN)
BY_KEY = {s.key: s for s in CHAIN}
BY_KEY.update({s.key: s for s in COMPOSE})

#: the layer the chain must end on for a scene to count as finished
FINAL_LAYER = "grouped"


def get(key):
    try:
        return BY_KEY[key]
    except KeyError:
        raise SystemExit(
            f"unknown stage '{key}'. The graph chain is: "
            f"{', '.join(KEYS)}. Compose is: {', '.join(COMPOSE_KEYS)}")


def select_compose(from_key=None, until_key=None, skip=()):
    """The compose stages to run, same rules as select()."""
    skip = {s.strip() for s in skip if s and s.strip()}
    lo = COMPOSE_KEYS.index(from_key) if from_key else 0
    hi = (COMPOSE_KEYS.index(until_key) if until_key
          else len(COMPOSE_KEYS) - 1)
    if lo > hi:
        raise SystemExit(f"--from {from_key} comes after --until {until_key}")
    return [s for s in COMPOSE[lo:hi + 1] if s.key not in skip]


def select(from_key=None, until_key=None, skip=()):
    """The stages to run, in order, honouring --from / --until / --skip."""
    skip = {s.strip() for s in skip if s and s.strip()}
    for k in skip:
        get(k)                       # validate; raises on a typo
    # Naming a stage as the start or end of the range AND skipping it is a
    # contradiction, and silently honouring the skip would show a range
    # that begins somewhere it does not. Say so rather than guess.
    for label, key in (("--from", from_key), ("--until", until_key)):
        if key and key in skip:
            raise SystemExit(f"{label} {key} is also in --skip: the range "
                             f"cannot start or end on a stage that is not "
                             f"going to run")
    lo = KEYS.index(get(from_key).key) if from_key else 0
    hi = KEYS.index(get(until_key).key) if until_key else len(KEYS) - 1
    if lo > hi:
        raise SystemExit(f"--from {from_key} comes after --until {until_key}")
    return [s for s in CHAIN[lo:hi + 1] if s.key not in skip]


def describe():
    """Both chains as a human-readable table. Printed by run_scene --list."""
    w = max(len(k) for k in KEYS + COMPOSE_KEYS)
    lines = []
    for title, group in (("GRAPH CHAIN — the room as measured", CHAIN),
                         ("COMPOSE — the room as furnished", COMPOSE)):
        lines.append("")
        lines.append(title)
        lines.append(f"{'stage'.ljust(w)}  {'reads':9s} {'writes':9s} "
                     f"{'cost':7s} what it does")
        lines.append("-" * (w + 62))
        for s in group:
            cost = ("LLM" if s.llm else "") + ("+GPU" if s.llm and s.gpu
                                               else ("GPU" if s.gpu else ""))
            lines.append(f"{s.key.ljust(w)}  {(s.reads or '-'):9s} "
                         f"{(s.writes or '-'):9s} {cost:7s} {s.title}")
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe())
