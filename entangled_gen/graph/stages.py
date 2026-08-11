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
    # ---- PHASE B2, THE LOOP-BACK ------------------------------------
    # USER ARCHITECTURE RULING 08-07 (docs/PLAN_VOTEBOX_DOWNSTREAM.md
    # "PHASE B2"): "after slice vote the scene goes all the way back up
    # to geometric edges and down the judges again — just with two more
    # judges at the end."
    #
    # So the vote does not hand straight to J8. The rebuilt edges go back
    # through the SAME judge chain first — J0 triages the new nesting
    # candidates, J1 answers only genuinely new pairs, J4 names and J6
    # appearance are pure cache hits because the crops did not change —
    # and only THEN do J8/J9 run.
    #
    # ORDER IS EXPLICIT AND IT MATTERS: J8 must read its relational facts
    # from the rebuilt edges (the obj_063 stimulus-gap lesson). Running
    # J8 first is judging on facts the vote has already invalidated.
    #
    # ⚠ THESE TWO WERE MISSING FROM THIS TABLE UNTIL 2026-08-11, because
    # the 11-step list in docs/AUTOMATION_READINESS.md omitted them and
    # this table was built from that list. The cost of the omission was
    # not theoretical: with J1 never re-run, a SAME_CANDIDATE pair the
    # VOTE created (two chairs at 96% containment) reached materialize
    # with no verdict and shipped as two objects — and it was written up
    # as "the chain has no judge for this", when the chain has had one
    # since 08-07 and this table had simply left it out.
    Stage(
        "j0_retriage", "J0: triage the pairs the vote's new boxes propose",
        lambda sc: [PY, "graph/triage_pairs.py", "--scene", sc,
                    "--edges-from", "voted_edges"],
        reads="voted", writes=None,
        graph_keys=("voted_edges",),
        llm=True,
        note="Runs ON graph['voted_edges'], not on the record. Only "
             "genuinely new nesting candidates cost a call.",
    ),
    Stage(
        "j1_repairs", "J1: same-or-different on the pairs the vote created",
        lambda sc: [PY, "graph/judge_pairs.py", "--scene", sc,
                    "--edges-from", "voted_edges"],
        reads="voted", writes=None,
        graph_keys=("voted_edges",),
        llm=True,
        note="This is the stage that answers a duplicate the VOTE made by "
             "moving boxes — the two-chairs case. Its SAME verdicts ride "
             "on the voted_edges block and materialize applies them.",
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
#: KEPT AS ITS OWN TUPLE, NOT APPENDED TO CHAIN, because the boundary is
#: real: everything above `grouped` measures a room that EXISTS, and
#: everything here proposes one to build.
#:
#: ⚠ CORRECTION (2026-08-11). An earlier version of this note said these
#: modules were "direction only, not designed". THAT WAS WRONG, and it
#: came from quoting line 8 of PLAN_COMPOSE_LOOP.md — written 07-26G at
#: the very start of that work — while ignoring the record in the body of
#: the same document. The gate table there shows `supported_by` PASSED
#: 07-31 (re-affirmed by R7), `consistency` PASSED 08-01, the S3 add-pass
#: redesign a USER PASS with "make it canon", and S3 v4 built with the
#: user in-session as canon.
#:
#: What was genuinely missing was not the design but the DRIVER: these
#: were run by hand, one command at a time, and no script chained them.
#: That is what this table fixes.
#:
#: THE ORDER IS READ OFF THE CODE, NOT INVENTED. Each module names the
#: file it cannot start without — consistency wants supported_by.json,
#: pick wants shopping.json, fit_walk wants fit_check.json and picks.json
#: — so the dependency order is a fact about the modules. Wiring them
#: here makes them RUNNABLE AND CHECKED.
#:
#: WHAT THE USER HAS ALREADY RULED ON, stage by stage. The earlier note
#: here said the gate status was "still the user's, gate by gate", which
#: read as though none of it had been ruled. Most of it has:
#:
#:     supported_by    PASSED 07-31 (map badge still says R10 OPEN)
#:     consistency     PASSED 08-01
#:     snap            GATE OPEN (R11)
#:     propose_edits   USER PASS — "make it canon"
#:     shopping, pick  CANON 08-03B (k=3 baton)
#:     fit_preview     CANON 08-04 (placement rules 1–7)
#:     fit_declip      CANON 08-04 (rule 8, the jiggle)
#:     fit_check       CANON 08-04 (rule 6, report-only)
#:     fit_walk        RAN TO DRY 08-04B (rule 11)
#:     fit_feedback    CANON 08-04 rule 12 — but see the row's note: its
#:                     effect needs a re-shop nobody has scoped yet
#:     rotation_check  CANON v2 08-04 (4-candidate choice) + the 08-05
#:                     wall-legality menu
#:
#: TWO THINGS ARE DELIBERATELY NOT IN THIS TUPLE. Both are omissions on
#: purpose, not oversights, and both wait on a USER RULING:
#:
#:   * `support_clip` (compose/support_clip.py). The record is genuinely
#:     SPLIT. FOR: docs/REVIEW_LOG.md:834 (R-S2-22) puts it in the order
#:     — "Support semantics must run AFTER geometry repair: parallax
#:     carve -> S1 -> support_clip -> compose sizes". AGAINST: five
#:     consecutive session handoffs carry it as a RETIREMENT CANDIDATE,
#:     because it rewrites layer geometry in place — REVIEW_LOG.md:1129,
#:     "support_clip rewrites graph['resolved'] geometry in place, which
#:     is the pattern this week removed; it is a retirement candidate".
#:     Wiring it would settle that question by default, so it is left out
#:     until the user settles it on purpose.
#:
#:   * SUB ROUNDS (PH2r, the support recursion). User-passed on the
#:     measurements, and pipeline_map.html draws it with the only loop
#:     arrow in step 3 — but the code lives in experiments/
#:     (sub_round_cp1..7.py, driven by experiments/sub_round_all.py) and
#:     the map badges it "SR0–12b · EXP" with "not in fitted_preview
#:     yet". Promoting an experiments/ script into the chain is a
#:     decision about what counts as production code, which is the
#:     user's, so it stays unwired.
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
        inputs=("compose/supported_by.json", "compose/edit_proposals.json",
                "compose/fit_feedback.json"),
        llm=True,
        note="READS fit_feedback.json (shopping.py:168) — the walk-back "
             "channel, canon rule 9: a rejected swap's out-items come "
             "back into the fit set and a rejected add vanishes. That is "
             "a read from a LATER stage, so it only bites on a re-run; "
             "see the fit_feedback row for why no re-run happens yet.",
    ),
    Stage(
        "pick", "choose an asset for every item on the list",
        lambda sc: [PY, "compose/pick.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/picks.json",),
        inputs=("compose/shopping.json",),
        llm=True,
    ),
    # ---- THE FIT LOOP: place -> jiggle -> check -> WALK ---------------
    #
    # ⚠ ORDER CORRECTED 2026-08-11. This tuple used to run fit_check
    # BEFORE fit_declip. That is backwards, and three independent sources
    # say so:
    #
    #   docs/PLAN_FIT_LOOP.md:101 (CANON 08-04 night, rule 8)
    #       "Stage order: fit_preview → fit_declip → fit_check."
    #   compose/fit_declip.py:42-45, the module's own docstring
    #       "the final state is verified by a normal fit_check pass
    #        afterwards, never by the solver itself... Stage order:
    #        fit_preview -> fit_declip -> fit_check."
    #   pipeline_map.html — PLACE → JIGGLE → CHECK → WALK, the edge out
    #       of JIGGLE labelled "declipped poses (fit_declip.json)".
    #
    # WHY IT MATTERS, and it is not cosmetic. fit_declip REWRITES
    # fitted_preview.glb and fitted_preview.json IN PLACE (fit_declip.py
    # :465 writes the glb, :480 the json). Run the check first and:
    #   * fit_check.json describes a scene that no longer exists the
    #     moment declip runs;
    #   * the declipped result is never verified by anything — and
    #     declip explicitly REFUSES to certify itself ("never by the
    #     solver itself");
    #   * worst, the fit_check row below is where this table tells the
    #     reader the Collision-Free number comes from. Measured before
    #     the jiggle, that headline quality number describes the
    #     UN-DECLIPPED scene: the project's own metric, computed on the
    #     wrong state and reported as the right one.
    # Nothing downstream noticed, because both files existed and both
    # were fresh. Freshness is not order.
    Stage(
        "fit_preview", "place the chosen assets in the room",
        lambda sc: [PY, "compose/fit_preview.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/fitted_preview.json",),
        inputs=("compose/picks.json", "compose/shopping.json",
                "compose/snap.json", "compose/fit_walk.json",
                "compose/rotation_check.json",
                "compose/fitted_preview.json"),
        note="EVERY ONE OF THOSE INPUTS IS READ IN THE MODULE, and only "
             "picks.json was declared before: shopping.json:175 (the "
             "size-fit fallback pool), picks.json:181, fit_walk.json:191 "
             "(walk choices win the pick — pick_source 'walk'), "
             "snap.json:319 (the fit target is the SNAPPED box, canon "
             "rule 1), rotation_check.json:351 (uid-gated yaw deltas), "
             "and its OWN PRIOR OUTPUT fitted_preview.json:344 — the "
             "rotation basis carry, so this stage reads the file it is "
             "about to overwrite. Four of the six come from stages that "
             "run AFTER it in this tuple; that is not a cycle, it is the "
             "loop, and it is why re-running this stage alone changes "
             "the scene.",
    ),
    Stage(
        "fit_declip", "push clipping pairs apart until nothing overlaps",
        lambda sc: [PY, "compose/fit_declip.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/fit_declip.json",),
        inputs=("compose/fitted_preview.json", "compose/fitted_preview.glb"),
        note="Reads the GLB, not just the json: load_placed (imported "
             "from fit_check) opens fitted_preview.glb at fit_check.py"
             ":55, and the meshes are what it pushes apart. It then "
             "writes both back IN PLACE — so this stage's real output is "
             "fitted_preview.glb/.json, and fit_declip.json is only the "
             "record of the moves.",
    ),
    Stage(
        "fit_check", "report what clips and what leaves the room",
        lambda sc: [PY, "compose/fit_check.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/fit_check.json",),
        inputs=("compose/fitted_preview.json", "compose/fitted_preview.glb"),
        note="REPORT ONLY — it fixes nothing. This is the file the "
             "Collision-Free number should be read from, because it "
             "measures the PLACED MESHES (fitted_preview.glb, loaded at "
             "fit_check.py:55) rather than the graph's boxes. It runs "
             "AFTER the jiggle so that number describes the scene that "
             "actually exists.",
    ),
    Stage(
        "fit_walk", "swap a candidate when the chosen one does not fit",
        lambda sc: [PY, "compose/fit_walk.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/fit_walk.json",),
        inputs=("compose/fit_check.json", "compose/picks.json",
                "compose/fitted_preview.json", "compose/shopping.json"),
        note="THE LOOP'S EXIT SIGN. fit_walk.json carries "
             "`changed_this_run` (fit_walk.py:124) — the number of NEW "
             "walk choices this run made. 0 means nothing moved, which "
             "is what the map calls DRY on the WALK node. Its choices "
             "ACCUMULATE across rounds (it reads its own previous file "
             "at :77), so the count of choices is not the exit test; "
             "`changed_this_run` is. Also reads fitted_preview.json:48 "
             "(is the item flat?) and shopping.json:53 (the fallback "
             "candidate pool).",
    ),
    # ---- AFTER THE LOOP HAS GONE DRY ---------------------------------
    Stage(
        "fit_feedback", "tell shopping which proposals died at fit time",
        lambda sc: [PY, "compose/fit_feedback.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/fit_feedback.json",),
        inputs=("compose/shopping.json",),
        note="⚠ THIS STAGE PRODUCES ITS FILE AND, TODAY, NOTHING ACTS ON "
             "IT. Canon rule 12 (docs/PLAN_FIT_LOOP.md:135-144): items "
             "whose BEST candidate scores above DRY 0.65 write "
             "rejections shopping.py consumes — swaps revert to their "
             "out-items, adds drop. But shopping.py reads that file "
             "(shopping.py:168) only when SHOPPING RUNS AGAIN, and HOW "
             "WIDE that re-shop should be — shopping alone, shopping "
             "through pick, or the whole compose phase — IS NOT RULED. "
             "Inventing a scope here would be inventing a pipeline. So "
             "the stage runs, the verdicts land on disk where the next "
             "deliberate shopping run will pick them up, and the "
             "re-shop DOES NOT HAPPEN AUTOMATICALLY. Anyone reading a "
             "run log should not mistake a written fit_feedback.json "
             "for a shopping list that has been corrected.",
    ),
    Stage(
        "rotation_check", "ask a judge which way each object really faces",
        lambda sc: [PY, "compose/rotation_check.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/rotation_check.json",),
        inputs=("compose/fitted_preview.json",
                "compose/edit_proposals.json"),
        llm=True, gpu=True,
        note="CLOSING PASS, OUTSIDE THE LOOP — runs ONCE, on the final "
             "walked set. That position is the user's reorder ruling of "
             "08-04 (PLAN_FIT_LOOP.md:110-116, rule 10: \"it is "
             "expensive\" — candidate walks and re-shops must not "
             "re-trigger it), and the map draws it exactly so "
             "(pipeline_map.html:873-879, \"PH2a · ROTATION CHECK\", "
             "\"CANON v2 08-04\", \"CLOSING PASS, outside the loop (rule "
             "10) — runs ONCE on the final walked set · deltas apply via "
             "place→jiggle\"). The 08-05 wall-legality menu "
             "(PLAN_FIT_LOOP.md:253-286) is canon on top of it. "
             "It WRITES A RECORD ONLY and never touches the placement; "
             "its deltas land through the CLOSING place→jiggle pass "
             "declared in FIT_CLOSING below (pipeline_map.html:883, "
             "\"HIGH-conf applied via one closing place→jiggle pass\"). "
             "⚠ THIS STAGE WAS MISSING FROM THIS TABLE UNTIL 2026-08-11, "
             "and fit_preview.py:351-360 has been reading "
             "rotation_check.json the whole time — dead code without "
             "this row, because nothing in the chain ever wrote the file.",
    ),
)

COMPOSE_KEYS = tuple(s.key for s in COMPOSE)

#: THE FIT BLOCK IS A LOOP, AND IT REPEATS UNTIL IT GOES DRY.
#:
#: docs/PLAN_FIT_LOOP.md:118-123 (CANON 08-04 late night, the user
#: verbatim: "oh shit. this is good. save to canon"):
#:     "Loop = place → jiggle → check → WALK → repeat until dry; ran to
#:      dry on bedroom_marble tonight (2 passes)"
#: and docs/REVIEW_LOG.md:779 (R-S2-15) records a real living_marble run
#: reaching dry in FOUR rounds. One pass is not the stage; it is the
#: first round of it.
#:
#: These keys must stay CONTIGUOUS in COMPOSE, in this order — the
#: runner treats them as one block.
FIT_LOOP = ("fit_preview", "fit_declip", "fit_check", "fit_walk")

#: How the runner learns the loop is dry, READ FROM THE STAGE'S OWN
#: OUTPUT rather than guessed: (file, field, value-that-means-dry).
#: fit_walk.py:124 writes `changed_this_run` = the number of NEW walk
#: choices this run made; pipeline_map.html:864 states the rule on the
#: WALK node itself — "0 new = DRY".
FIT_LOOP_EXIT = ("compose/fit_walk.json", "changed_this_run", 0)

#: Default hard cap on the rounds. NOT an exit condition — a stop. A run
#: that hits it has not converged and must be reported as a FAILURE, not
#: quietly accepted: "we stopped iterating because we ran out of
#: patience" is not a result.
FIT_MAX_ROUNDS = 6

#: THE CLOSING PASS. rotation_check only records verdicts; the yaw
#: deltas reach the scene when the placement is rebuilt with them
#: (fit_preview.py:351-360 applies the uid-gated ones) and the jiggle
#: re-settles what moved. pipeline_map.html:883: "HIGH-conf applied via
#: one closing place→jiggle pass". Same two modules as the loop's first
#: two steps — deliberately the same stage keys, so the run log and the
#: fleet's by-module totals keep all of fit_preview's time under
#: fit_preview instead of splitting it across a near-duplicate name.
FIT_CLOSING = ("fit_preview", "fit_declip")

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
            mark = "  loop" if s.key in FIT_LOOP else ""
            lines.append(f"{s.key.ljust(w)}  {(s.reads or '-'):9s} "
                         f"{(s.writes or '-'):9s} {cost:7s} {s.title}{mark}")
    # A flat list of stage names would hide the two things about compose
    # that are not a straight line, so say them here rather than let the
    # table imply one pass each.
    lines.append("")
    lines.append(f"  the fit loop: {' -> '.join(FIT_LOOP)} -> repeat")
    lines.append(f"    exit  : {FIT_LOOP_EXIT[0]} `{FIT_LOOP_EXIT[1]}` "
                 f"== {FIT_LOOP_EXIT[2]}  (0 new walks = DRY)")
    lines.append(f"    cap   : {FIT_MAX_ROUNDS} rounds (--fit-max-rounds); "
                 f"hitting it is a FAILURE, not a pass")
    lines.append(f"  closing pass after rotation_check: "
                 f"{' -> '.join(FIT_CLOSING)}  (applies the yaw deltas)")
    return "\n".join(lines)


if __name__ == "__main__":
    print(describe())
