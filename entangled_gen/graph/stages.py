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

import paths  # noqa: E402  (after the sys.path preamble above)


# ==========================================================================
# THE FUNNEL'S PARAMETERS — the flags that used to live only in memory
# ==========================================================================
#
# docs/handoffs/SESSION_2026-08-25B_HANDOFF.md §5d: "~20 hand-run commands, several
# with flags that live only in memory". These are those flags. Naming them
# here does two things: the INTAKE table below builds its command lines
# from them, and the four modules that HARDCODE the filenames they produce
# have somewhere to import from instead.
#
# ⚠ EVERY VALUE HERE CHANGES A FILENAME DOWNSTREAM. They are not tuning
# knobs — `LIFT_SUFFIX` alone renames the lift pool and three manifests,
# and `SCORE_THR` is baked into the f30 name. Changing one without
# re-running the whole funnel gives a scene whose stages disagree about
# what its files are called.

#: the standpoint's working directory. pano_recenter HARDCODES this one
#: (pano_recenter.py:69 — it has no --rig), so it is not free.
RIG = "rig_sp0"

#: pano_lift --suffix. THE `c` IN EVERY DOWNSTREAM NAME. pano_lift mints
#: it (pano_lift.py:106,117,127), pano_recenter must be given the same
#: letter or it cannot find its inputs (pano_recenter.py:74-75), and
#: manifest_filter carries it through.
#: ⚠ pipeline_map.html:1048 prints pano_lift's command WITHOUT --suffix
#: while :1055 claims lift_poolc.json as its output. The map is
#: internally inconsistent there; REVIEW_LOG.md:1557 and the handoff §5d
#: both record `pano_lift --suffix c` as the real command, and the files
#: on disk are named with the c. Following the code and the log.
LIFT_SUFFIX = "c"

#: seg_batched --out-dir's leaf. THE "20" IS A NAMING CONVENTION FOR
#: --box-thr 0.20, not a derivation — nothing in the code links them, and
#: a run at 0.35 writing to this directory would look identical. Recorded
#: here so the convention is at least written down beside the value it
#: refers to.
SEG_DIR = "seg_batched20"

#: seg_batched --box-thr / --topk for the suffix-c run
#: (docs/plans/PLAN_SELF_PANO_RIG.md:27-28). Module defaults are 0.35 / 30.
#: Permissive on purpose: the vote and the judges are what say no.
DET_BOX_THR = 0.20
DET_TOPK = 40

#: pano_lift --min-score / --gate-peak (pipeline_map.html:1048). Equal to
#: each other on purpose, which makes the gate a no-op — the map says so
#: on the node itself. Module defaults are 0.35 / 0.40.
LIFT_MIN_SCORE = 0.20
LIFT_GATE_PEAK = 0.20

#: manifest_filter --thr. f30 ADOPTED (108 -> 102 on living); the "30" in
#: the filename is round(SCORE_THR * 100).
SCORE_THR = 0.30

#: The canonical filenames, DERIVED from the values above rather than
#: spelled out. slicevote.py:1038-1042 and scene_scale.py:159 hardcode
#: these same four strings at module level with no override; this is the
#: place for them to import from when that is fixed.
MANIFEST_RC = f"scene_manifest_pano2{LIFT_SUFFIX}_rc.json"
MANIFEST_F30 = (f"scene_manifest_pano2{LIFT_SUFFIX}_rc"
                f"_f{round(SCORE_THR * 100):02d}.json")
LIFT_POOL = f"{RIG}/lift_pool{LIFT_SUFFIX}.json"
DETECTIONS = f"{RIG}/{SEG_DIR}/detections.json"
RIG_CROPS = f"{RIG}/crops"
SELF_PANO = f"{RIG}/pano_selfrender.png"
BEARINGS = f"{RIG}/vocab_bearings.json"


def _abs(scene, rel):
    """An absolute path inside the scene directory, as a string.

    ⚠ THIS IS NOT COSMETIC, and getting it wrong is silent. crop_pano and
    seg_batched take their directory arguments as a bare `Path(...)` with
    no scene-dir join (crop_pano.py:76,87; seg_batched.py:68,97,98), and
    run_scene spawns every stage with cwd = THE REPO (run_scene.py:317).
    So the relative strings the map prints — `--out-dir rig_sp0/crops` —
    would create `entangled_gen/rig_sp0/crops` and quietly write the
    whole scene's crops into the source tree, where the next stage would
    not find them and the scene after would inherit them."""
    return str(paths.scene_dir(scene) / rel)

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
    artifacts_optional
               files this stage writes ONLY ON SOME SCENES. If such a
               file EXISTS it must have been written during this run
               (same freshness test as `artifacts` — a present-but-stale
               copy is a lie on disk and FAILS); if it is ABSENT the gate
               notes it and passes. Added 2026-08-11C for the collider
               pair: a colliderless bundle cannot write
               collider_registered.glb, and failing an honest scene for
               it was the gate misfiring (PLAN_COLLIDER_OPTIONAL step 2).
               ⚠ THIS IS NOT A SOFTER `artifacts`. A stage's REAL output
               must stay in `artifacts` — the no-op trap is only caught
               because at least one unconditional file is mtime-checked
               every run. Only a file whose very existence legitimately
               depends on the bundle belongs here.
    graph_keys top-level scene_graph.json blocks that must exist after
               this stage — for a stage that edits the graph without
               adding a layer.
               ⚠ NO STAGE USES THIS TODAY, on purpose. Its only two users
               were `vote` and `voted_edges`, the node-sidecar and the
               edges-only block, and BOTH WERE RETIRED on 2026-08-11 by
               the ruling that every layer must be whole. The check is
               kept because the shape is legitimate, but a new row
               reaching for it should first ask whether what it wants is
               really a layer, or a file (`artifacts`).
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
                 artifacts=(), artifacts_optional=(), graph_keys=(),
                 inputs=(), llm=False, gpu=False, note=""):
        self.key = key
        self.title = title
        self._argv = argv
        self.reads = reads
        self.writes = writes
        self.artifacts = tuple(artifacts)
        self.artifacts_optional = tuple(artifacts_optional)
        self.graph_keys = tuple(graph_keys)
        self.inputs = tuple(inputs)
        self.llm = llm
        self.gpu = gpu
        self.note = note

    def argv(self, scene, extra=()):
        return list(self._argv(scene)) + list(extra)

    def __repr__(self):
        return f"<Stage {self.key}: {self.reads or '-'} -> {self.writes or '-'}>"


#: STEP 1-2 — INTAKE. The Marble bundle becomes a measured room: a frame,
#: a self-rendered pano, twenty crops, a word list, detections, 3D boxes,
#: a scale and a room shell. Everything the graph chain reads.
#:
#: ⚠ THIS TUPLE REPLACES `run_scene.py`'s OLD `--phase core`, WHICH WAS A
#: DIFFERENT LANE ENTIRELY. That one ran crop_pano (default out-dir) ->
#: vocab_from_prompt -> seg_views -> seg_pano_overlay -> lift_pano ->
#: manifest_pano_to_raw and wrote pano_crops/, seg_pano/ and
#: scene_manifest_pano.json. NOTHING DOWNSTREAM READS ANY OF THEM: the
#: chain reads rig_sp0/crops/, rig_sp0/seg_batched20/detections.json,
#: rig_sp0/lift_poolc.json and scene_manifest_pano2c_rc_f30.json. Proof
#: from disk: out/living_marble — the scene the entire chain was verified
#: against — has no pano_crops/ and no seg_pano/ at all. That lane is
#: docs/PIPELINE.md's "pano path — week8 object-ID lane"; the modules stay
#: on disk, out of the runner. USER RULING 2026-08-11: the map is right,
#: and what it marks stale leaves the core pipeline.
#:
#: THE ORDER IS THE MAP'S (pipeline_map.html, nodes INTAKE, P1-P6, N1, 4w).
#: `envelope.py` is NOT here: the map parks it 07-26 and draws it with no
#: outgoing arrow — its only reader is the viewer's bench layer.
#:
#: ⚠ THE MAP'S COMMAND STRINGS ARE NOT RUNNABLE, and this table is built
#: from the CODE, not from them. Three ways they fall short:
#:   * seg_batched's --views-dir and --out-dir are required=True and
#:     appear in neither the map string nor any doc's command line;
#:   * the map prints pano_lift without --suffix while claiming its
#:     c-suffixed outputs (see LIFT_SUFFIX above);
#:   * the paths are relative, and the runner's cwd is the repo (see
#:     _abs above).
#: Every flag below is either a named constant at the top of this file or
#: an absolute path derived from the scene. Nothing is a literal typed
#: twice.
INTAKE = (
    Stage(
        "frame", "read the bundle's frame: floor, ceiling, up — and "
                 "register the collider when the bundle has a good one",
        lambda sc: [PY, "frame_bootstrap.py", "--scene", sc],
        artifacts=("frame_bootstrap.json",),
        artifacts_optional=("collider_registered.glb",
                            "collider_registration.json"),
        note="THE COLLIDER IS OPTIONAL since 2026-08-11C (R-S2-110/111, "
             "user: 'splat floor wins') — floor/ceiling are measured from "
             "the splat on EVERY scene, with room_shell's own clip + "
             "histogram, imported. A collider, when present, still runs "
             "the trusted-bundle agreement check; a disagreement condemns "
             "the COLLIDER (not the world), which is then not registered "
             "and the scene runs colliderless. This lifted the corpus "
             "ceiling from 34 of 318 harvested worlds to all of them. "
             "Also converts the .spz to gen_raw.ply if that is missing. "
             "A bundle with no .spz still refuses — there is no scene "
             "without the splat.",
    ),
    Stage(
        "stitch", "render the room's own 360° pano from the splat",
        lambda sc: [PY, "pano_stitch.py", "--scene", sc],
        artifacts=(SELF_PANO, f"{RIG}/pano_selfrender_meta.json"),
        gpu=True,
        note="Six cube faces through WSL gsplat, stitched to an 8192x4096 "
             "equirect, eye at the room centre + 1.6 m. The pipeline looks "
             "at the room through THIS, not through the bundle's own pano "
             "— which is why 318 of the 323 harvested worlds having no "
             "pano_rgb_0.png does not disqualify them. Resumable: the six "
             "faces are cached under a fingerprint of the camera and the "
             "splat, so a re-run after a crash re-renders none of them.",
    ),
    Stage(
        "crops", "cut twenty pinhole views out of that pano",
        lambda sc: [PY, "crop_pano.py", "--scene", sc,
                    "--pano", _abs(sc, SELF_PANO),
                    "--out-dir", _abs(sc, RIG_CROPS)],
        artifacts=(f"{RIG_CROPS}/pano_y000_pp00.webp",
                   f"{RIG_CROPS}/pano_y000_pp00.json"),
        inputs=(SELF_PANO,),
        note="20 cameras: 8 yaws level, 8 at -40°, 4 at +40°, 75° fov, "
             "960 px. Each gets a same-stem .json with its camera, which "
             "is what makes the lift possible later. THE --out-dir IS THE "
             "WHOLE POINT of this invocation: without it crop_pano writes "
             "to pano_crops/, the retired lane's directory, and nothing "
             "downstream would find them.",
    ),
    Stage(
        "vocab", "decide what words to look for in this room",
        lambda sc: [PY, "vocab_build.py", "--scene", sc],
        artifacts=("vocab.json",),
        llm=True,
        note="The prompt's nouns UNION what a model actually sees in the "
             "pano — intent plus observation, because a generated room "
             "contains things the prompt never mentioned. About six haiku "
             "calls, NOT cached, so a re-run re-spends them. Degrades leg "
             "by leg and says which: no pano skips the look pass, a failed "
             "concreteness pass keeps every term.",
    ),
    Stage(
        "bearings", "ask roughly which direction each word is in",
        lambda sc: [PY, "pano_bearings.py", "--scene", sc],
        artifacts=(BEARINGS,),
        inputs=("vocab.json", SELF_PANO),
        llm=True,
        note="ONE call. Turns the word list into a per-view word list, so "
             "the detector is not asked about a bed while looking at the "
             "kitchen wall. A term the model cannot place stays GLOBAL — "
             "searched everywhere — so this can only narrow work, never "
             "lose an object. Not cached.",
    ),
    Stage(
        "detect", "find and segment those words in every view",
        lambda sc: [PY, "seg_batched.py", "--scene", sc,
                    "--views-dir", _abs(sc, RIG_CROPS),
                    "--glob", "pano_*.webp",
                    "--out-dir", _abs(sc, f"{RIG}/{SEG_DIR}"),
                    "--bearings", _abs(sc, BEARINGS),
                    "--box-thr", str(DET_BOX_THR),
                    "--topk", str(DET_TOPK)],
        artifacts=(DETECTIONS,),
        inputs=("vocab.json", BEARINGS,
                f"{RIG_CROPS}/pano_y000_pp00.webp"),
        gpu=True,
        note="GroundingDINO + SAM, terms batched about five at a time "
             "because a long prompt scores every term worse (the 07-26 "
             "batching effect). Writes detections.json after EVERY view, "
             "so a crash halfway leaves a usable file. --box-thr and "
             "--topk are deliberately permissive: this stage's job is to "
             "miss nothing, and the vote and the judges are what say no.",
    ),
    Stage(
        "lift", "turn the masks into 3D boxes",
        lambda sc: [PY, "pano_lift.py", "--scene", sc,
                    "--seg-dir", SEG_DIR,
                    "--suffix", LIFT_SUFFIX,
                    "--min-score", str(LIFT_MIN_SCORE),
                    "--gate-peak", str(LIFT_GATE_PEAK)],
        artifacts=(LIFT_POOL, f"scene_manifest_pano2{LIFT_SUFFIX}.json",
                   f"scene_manifest_pano2{LIFT_SUFFIX}_gated.json"),
        inputs=(DETECTIONS, f"{RIG}/pano_selfrender_meta.json"),
        note="Each mask's rays meet the splat's own points — no collider "
             "involved. Every camera is re-verified against the pano "
             "before it is trusted (a mini-G1 correlation check) and a "
             "camera that fails is SKIPPED and printed, not guessed at. "
             "--seg-dir is relative to the rig dir, unlike the two "
             "absolute paths the detect stage needs; that asymmetry is "
             "the modules', not this table's.",
    ),
    Stage(
        "recenter", "go back and look properly at whatever was seen badly",
        lambda sc: [PY, "pano_recenter.py", "--scene", sc,
                    "--suffix", LIFT_SUFFIX,
                    "--min-score", str(LIFT_MIN_SCORE)],
        artifacts=(MANIFEST_RC,),
        inputs=(LIFT_POOL, f"scene_manifest_pano2{LIFT_SUFFIX}_gated.json"),
        gpu=True,
        note="THE FILTER, and the most valuable stage in the funnel. For "
             "every weak object it re-crops the pano aimed straight at it "
             "and re-detects: confirms, REFUTES (the object is deleted), "
             "or ENRICHES — zooming into a shelf turns what it contains "
             "into child objects with their own photos. Uncapped, because "
             "the shots are free CPU resamples of a pano we already have. "
             "The GPU is the seg_views child it spawns on the retakes.",
    ),
    Stage(
        "filter", "drop the detections too weak to keep",
        lambda sc: [PY, "manifest_filter.py", "--scene", sc,
                    "--manifest", MANIFEST_RC,
                    "--thr", str(SCORE_THR)],
        artifacts=(MANIFEST_F30,),
        inputs=(MANIFEST_RC,),
        note="108 -> 102 on living, and f30 is the adopted setting. "
             "NOTHING IS DELETED: what falls below the bar moves to a "
             "`filtered_out` list in the same file, flagged, so a later "
             "question about a missing object has an answer. Dedup was "
             "RETIRED here on 07-26 — duplicates stay, because merging "
             "two detections is a judge's verdict, not a threshold's.",
    ),
    Stage(
        "scale", "measure how far off metric the room is, and fix it",
        lambda sc: [PY, "scene_scale.py", "--scene", sc],
        artifacts=("scene_scale.json",),
        inputs=(MANIFEST_F30,),
        llm=True,
        note="One cached call asks, per detected class, what size that "
             "kind of thing usually is and whether it is a reliable ruler "
             "at all; only the reliable ones measure. The scene is then "
             "rescaled IN PLACE — splat, collider, frame, every manifest, "
             "the lift pool, the pano eye — with *_prescale.* backups, and "
             "a second apply is REFUSED. Too little agreement and it "
             "degrades to 1.0 and says so rather than guessing.",
    ),
    Stage(
        "shell", "measure the walls, floor and ceiling",
        lambda sc: [PY, "room_shell.py", "--scene", sc],
        artifacts=("room_shell.json",),
        inputs=("frame_bootstrap.json",),
        note="W4 USER PASS 08-09. Default mode now runs the polygon fit "
             "itself: one segment per wall INCLUDING the angled connectors "
             "that cut a corner off, so an L-shaped room is not forced "
             "into a rectangle. A failed fit degrades to the v1 four "
             "planes and records `polygon_error` — never a silent skip. "
             "⚠ Two separate readers were found on 2026-08-11 assuming "
             "every wall is an axis plane (edge_carry, judge_coherence); "
             "both crashed or went silent on a connector. Anything new "
             "reading room_shell.json must handle kind=='connector'.",
    ),
)

INTAKE_KEYS = tuple(s.key for s in INTAKE)

#: STEP 4g/J — RECORD, then JUDGE. The measured room becomes a scene
#: graph, and the graph's identities get settled: what is one object and
#: what is two, what each thing is called, what is really there.
#:
#: ⚠ THIS IS THE HALF THAT WAS MISSING FROM EVERY TABLE UNTIL 2026-08-11B,
#: and it is the reason a fresh bundle could not reach the vote. `CHAIN`
#: starts at the vote and reads `resolved`; nothing built `resolved`. Both
#: test scenes only ever worked because they were clones that already had
#: that layer. Ten designed stages simply were not written down anywhere a
#: runner could execute them.
#:
#: THE ORDER IS RULED, not chosen here — PIPELINE.md:301-312 and
#: PLAN_SCENE_GRAPH.md:234:
#:
#:     G1 build_graph  ->  G2 build_edges                  stamps `record`
#:     J0 triage_pairs ->  J1 judge_pairs  ->  J5 judge_near
#:     J2 build_judged ->  J3 judge_names  ->  J4 judge_coherence
#:                                                         stamps `judged`
#:     J6 describe_nodes  ->  J7 materialize_verdicts    stamps `resolved`
#:
#: ⚠ THE NUMBERING IS J3 = NAMES, J4 = COHERENCE. PLAN_VOTEBOX_DOWNSTREAM
#: said "J4 names" twice and was corrected 08-11; older copies and
#: anyone's memory may still have it the wrong way round.
#:
#: `graph/judge_cases.py` is RETIRED — its own docstring says "do not wire
#: it into any orchestration"; describe_nodes absorbed its queue
#: machinery. It is not here, and it should not be added.
#:
#: KEPT SEPARATE FROM `CHAIN` ON PURPOSE. `--phase graph` has meant "the
#: vote onward" in every handoff and every command line, and that meaning
#: is worth keeping. This is `--phase record`.
#:
#: WHY THERE IS NO LOOP HERE. J4 runs ONCE and its flags are a queue, not
#: a re-scan trigger; J6 runs ONCE and what it does not settle SHIPS; J7
#: is deterministic and cached. That is a deliberate design ruling
#: (PIPELINE.md, "There is NO iteration loop at the graph stage"), not an
#: omission. The one loop-back in this pipeline is Phase B2, and it runs
#: AFTER the vote — see the CHAIN table below.
RECORD = (
    Stage(
        "build_graph", "G1: turn the measured objects into graph nodes, "
                       "with their pictures",
        lambda sc: [PY, "graph/build_graph.py", "--scene", sc,
                    "--manifest", MANIFEST_F30,
                    "--pool", LIFT_POOL,
                    "--crop-src", RIG_CROPS],
        artifacts=("scene_graph.json",),
        inputs=(MANIFEST_F30, LIFT_POOL, "room_shell.json"),
        note="The manifest's objects become nodes VERBATIM — no "
             "pre-merged dedup, so both halves of every duplicate-suspect "
             "pair are nodes and merging stays a judge's verdict. It also "
             "cuts each node its crops, and turns the room shell's "
             "polygon into one architecture node per wall SEGMENT. The "
             "three paths are passed rather than left to the module's "
             "defaults, which hardcode the same strings a fourth time.",
    ),
    Stage(
        "build_edges", "G2: work out what is on, in, or against what",
        lambda sc: [PY, "graph/build_edges.py", "--scene", sc],
        writes="record",
        inputs=("room_shell.json",),
        note="Pure geometry, no judgement: ON, IN, IN_WALL, ATTACHED, "
             "INTERPENETRATES, the SAME_CANDIDATE queue and the NEAR "
             "fallbacks that stop anything floating unexplained. STAMPS "
             "`record`, which is why this row and not G1 declares the "
             "layer. Self-checks and exits 1 on a frame or invariant "
             "violation.",
    ),
    Stage(
        "j0", "J0: which box-inside-box pairs are worth a look?",
        lambda sc: [PY, "graph/triage_pairs.py", "--scene", sc,
                    "--edges-from", "record"],
        reads="record",
        artifacts=("graph/triage_pairs_cache.json",),
        llm=True,
        note="ONE cheap text call over the whole docket. Containment >= "
             "0.90 pairs are exactly what the SAME_CANDIDATE IoU floor "
             "deliberately excludes, so without this they never reach a "
             "judge at all. Asymmetric by design: nominate on doubt, "
             "because a wrong nomination costs one crop call and a wrong "
             "skip ships a duplicate.",
    ),
    Stage(
        "j1", "J1: same object or two?",
        lambda sc: [PY, "graph/judge_pairs.py", "--scene", sc,
                    "--edges-from", "record"],
        reads="record",
        artifacts=("graph/judge_pairs_cache.json",),
        llm=True,
        note="Crops of both, one verdict per SAME_CANDIDATE edge. A "
             "fragment of a thing IS that thing (SAME); its contents are "
             "not (DISTINCT). Additive — nothing is merged here; J2 "
             "materializes it.",
    ),
    Stage(
        "j5", "J5: what is holding up the things that appear to float?",
        lambda sc: [PY, "graph/judge_near.py", "--scene", sc],
        reads="record",
        artifacts=("graph/judge_near_cache.json",),
        llm=True,
        note="RUNS AFTER J1 AND THE ORDER IS LOAD-BEARING: it folds J1's "
             "SAME verdicts first, so one object detected twice cannot "
             "occupy two slots on a floater's menu of candidate supports. "
             "That ordering became a refusal on 2026-08-11B; before, "
             "running it early was silently wrong.",
    ),
    Stage(
        "build_judged", "J2: apply the merges and re-point everything",
        lambda sc: [PY, "graph/build_judged.py", "--scene", sc],
        reads="record", writes="judged",
        inputs=("graph/judge_pairs_cache.json", "graph/judge_near_cache.json"),
        note="Zero model calls — union-find over the SAME verdicts, then "
             "the edges re-derived and the judgements carried across. "
             "Reproducible at any time from the record plus the caches, "
             "which is what makes the record safe to treat as immutable.",
    ),
    Stage(
        "j3", "J3: give every object its real name",
        lambda sc: [PY, "graph/judge_names.py", "--scene", sc],
        reads="judged",
        artifacts=("graph/judge_names_cache.json",),
        llm=True,
        note="⚠ J3 IS NAMES. PLAN_VOTEBOX_DOWNSTREAM.md said 'J4 names' "
             "twice and was corrected on 08-11; if a doc disagrees, this "
             "and PIPELINE.md:301-312 are right.",
    ),
    Stage(
        "j4", "J4: does the room as a whole make sense?",
        lambda sc: [PY, "graph/judge_coherence.py", "--scene", sc],
        reads="judged",
        artifacts=("graph/judge_coherence_cache.json",),
        llm=True,
        note="Text only, and it runs ONCE — its flags are a queue for J6, "
             "never a trigger to re-scan. AFTER J3 AND THAT MATTERS: its "
             "cache key hashes a digest that quotes every object's name, "
             "so running it on provisional names caches an answer about "
             "names that are about to change. A refusal since 08-11B.",
    ),
    Stage(
        "j6", "J6: describe each object, and settle what J4 flagged",
        lambda sc: [PY, "graph/describe_nodes.py", "--scene", sc],
        reads="judged",
        artifacts=("graph/appearance_cache_v2.json",),
        llm=True,
        note="THE LAST JUDGE OF THIS HALF, and it runs ONCE: what it does "
             "not settle SHIPS. Appearance for every node, plus the "
             "existence and rename adjudications J4 queued — each with a "
             "zoomed-out context tile, because identity is unanswerable at "
             "tight-crop zoom (the obj_138 door-frame lesson).",
    ),
    Stage(
        "resolved", "J7: turn every verdict into the shipping object set",
        lambda sc: [PY, "graph/materialize_verdicts.py", "--scene", sc],
        reads="judged", writes="resolved",
        inputs=("graph/appearance_cache_v2.json",
                "graph/judge_coherence_cache.json",
                "graph/judge_names_cache.json"),
        llm=True,
        note="Rejected, structural and disputed nodes leave, each with its "
             "reason recorded; the judges' sentences become the closed "
             "edge vocabulary. BOX GEOMETRY IS VERBATIM — no surgery here, "
             "by the user's stage-contract ruling of 07-26; moving boxes "
             "is the vote's job, and it is the next stage. This is the "
             "CANONICAL HANDOFF: `resolved` is where measurement ends and "
             "the CHAIN table below begins.",
    ),
)

RECORD_KEYS = tuple(s.key for s in RECORD)

#: THE PHASES, IN THE ORDER A SCENE GOES THROUGH THEM, named once so that
#: run_scene and run_fleet cannot drift apart on what `--phase` accepts.
#: They did: run_fleet offered ("core", "graph", "all") and so could not
#: be asked for compose at all — on the driver whose whole job is running
#: a hundred scenes unattended.
PHASES_ORDER = ("core", "record", "graph", "compose")

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
        "doubts", "write down what the vote was unsure about",
        lambda sc: [PY, "graph/record_vote_doubts.py", "--scene", sc],
        reads="resolved", writes=None,
        artifacts=("graph/vote_doubts.json",),
        note="THE SIDECAR IS THE WHOLE OUTPUT. This stage used to write "
             "the same doubts twice — the file AND a graph['vote'] block "
             "— and the no-op trap was caught here: without its flag it "
             "updated the file but not the block, so J8 judged stale "
             "doubts. The block is retired (user ruling 2026-08-11), the "
             "duplication with it, and writing is the default now. "
             "vote_doubts.json is read by build_voted, materialize_layers "
             "and the gate; `artifacts` is what proves it was written.",
    ),
    Stage(
        "voted", "build the `voted` layer from the elected boxes",
        lambda sc: [PY, "graph/build_voted.py", "--scene", sc],
        reads="resolved", writes="voted",
        inputs=("scene_manifest_slicevote_preview.json",
                "vote/slicevote_report.json"),
    ),
    # ⚠ THE `voted_edges` STAGE WAS HERE AND IS RETIRED (2026-08-11).
    #
    # USER RULING: "I think the pipeline viewer is generally correct.
    # Items marked Stale should not be in the core pipeline."
    # pipeline_map.html draws graph['voted_edges'] as a TOMBSTONE, retired
    # 08-09: every layer must be WHOLE, and edges follow nodes INSIDE a
    # layer (graph/edge_carry.py). A block with edges and no nodes is the
    # last half-layer in the pipeline, and it ran beside graph['voted'],
    # deriving its own second opinion about the same geometry.
    #
    # THE LOOP-BACK ITSELF SURVIVES — only its half-layer is gone. J0 and
    # J1 still re-run after the vote (the 08-07 ruling below); they now
    # read the voted LAYER's own edges via --edges-from voted.
    #
    # PROVED BEFORE REMOVING, not assumed. build_voted already re-derives
    # the same edges with the same function: edge_carry.carry() calls
    # build_edges.derive_edges, the identical call rederive_voted_edges
    # made. Re-derived in memory on 2026-08-11 and compared pair by pair
    # against graph['voted_edges'] on autotest_living (85 edges) and
    # autotest_bedroom (145): ZERO pairs in one and not the other, and
    # identical counts of every edge type. rederive_voted_edges.py stays
    # on disk, unwired, like every other retirement here.
    #
    # (That comparison only held after fixing a real defect the exercise
    # uncovered: edge_carry passed wall_claim_dist the wall's `plane`
    # where it expects the whole `geometry`, so every wall lookup missed
    # and EVERY layer from `voted` on carried zero IN_WALL edges — 18
    # missing on living, 24 on bedroom. See edge_carry.py:176.)
    # ---- PHASE B2, THE LOOP-BACK ------------------------------------
    # USER ARCHITECTURE RULING 08-07 (docs/plans/PLAN_VOTEBOX_DOWNSTREAM.md
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
                    "--edges-from", "voted"],
        reads="voted", writes=None,
        artifacts=("graph/triage_pairs_cache.json",),
        llm=True,
        note="Runs on the VOTED LAYER's own edges, not on the record. "
             "Only genuinely new nesting candidates cost a call. No "
             "`graph_keys` any more: the block it used to require is "
             "retired, and `reads` already says the layer must be there.",
    ),
    Stage(
        "j1_repairs", "J1: same-or-different on the pairs the vote created",
        lambda sc: [PY, "graph/judge_pairs.py", "--scene", sc,
                    "--edges-from", "voted"],
        reads="voted", writes=None,
        artifacts=("graph/judge_pairs_cache.json",),
        llm=True,
        note="This is the stage that answers a duplicate the VOTE made by "
             "moving boxes — the two-chairs case. Its SAME verdicts ride "
             "on the voted layer's own edges and materialize applies them.",
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
        note="⚠ `reads` IS CONSERVATIVE, NOT LITERAL for the GEOMETRY. "
             "This pass starts again from `voted` and re-applies the same "
             "four geometry rules `settled` did, then adds J9's grouping "
             "on top. `shown` is declared because it is the NEWEST layer "
             "that must be fresh for this to be a legal moment to run, and "
             "the stale sweep makes that imply every earlier layer is "
             "fresh too. "
             "IT DOES NOW READ `shown` FOR ONE THING (fixed 2026-08-11B, "
             "user: \"a core function of the pipeline\"): each node's "
             "PICTURE decision is carried across by "
             "materialize_layers.inherit_shown(). Before that fix the "
             "block existed on every node of `shown` and on NONE of "
             "`grouped` — the pipeline decided what each object is seen "
             "as and then dropped the answer on the last step, in the "
             "layer compose reads. Matched by id; a node with no "
             "counterpart (a fresh split piece) is COUNTED in "
             "counts.shown_missing, never assumed away.",
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
#: TWO THINGS ARE NOT IN THIS TUPLE, AND BOTH ARE NOW SETTLED (08-11):
#:
#:   * `support_clip` — RETIRED by user ruling. "If we already have a
#:     similar mechanism... it's safe to retire if most of the docs say
#:     it's retired." It rewrote layer geometry IN PLACE, the pattern
#:     August removed everywhere else, and what it was built for is
#:     covered by the fit loop working against snapped boxes. The record
#:     was genuinely split (R-S2-22 put it in the order; five handoffs
#:     called it a retirement candidate), which is why it sat unresolved
#:     for months. The file stays on disk with the reasoning at the top
#:     of its docstring. DO NOT UN-RETIRE IT — if the need returns,
#:     rebuild it as a proper layer edit that stamps a new layer.
#:
#:   * SUB ROUNDS (PH2r, the support recursion) — DEFERRED by user
#:     ruling, not rejected. User-passed on the measurements, and
#:     pipeline_map.html draws it with the only loop arrow in step 3, but
#:     the code lives in experiments/ (sub_round_cp1..7.py, driven by
#:     experiments/sub_round_all.py) and the map badges it "not in
#:     fitted_preview yet". The base pipeline has run end to end on ONE
#:     scene; promoting experimental code before that is proven across a
#:     batch adds risk to the thing being validated. Revisit after a
#:     clean multi-scene run.
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
    #   docs/plans/PLAN_FIT_LOOP.md:101 (CANON 08-04 night, rule 8)
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
             "IT. Canon rule 12 (docs/plans/PLAN_FIT_LOOP.md:135-144): items "
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
    Stage(
        "sub_rounds", "place each anchor's deferred sub objects on its "
                      "real surfaces",
        lambda sc: [PY, "experiments/sub_round_all.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/sub_experiment/index.html",),
        inputs=("compose/shopping.json", "compose/fitted_preview.json",
                "compose/supported_by.json"),
        llm=True, gpu=True,
        note="UN-PARKED 2026-08-13 (R-S2-168, user ruling at the "
             "convexity-night wrap-up; canon SR0-SR9 in "
             "PLAN_SUB_ROUNDS.md, user-passed on bedroom_marble and "
             "fleet-proven 6/7 on fresh08). Runs cp1..cp7 per anchor "
             "with deferred subs; a failing anchor is recorded and "
             "skipped, never a stage-killer (an UNPLACED anchor cannot "
             "seed its subs — fresh08's window seat). ⚠ POSITION: this "
             "row and the two after it run AFTER the FIT_CLOSING pass "
             "(run_scene.run_compose splits `post` at rotation_check) — "
             "the closing place→jiggle REBUILDS the GLB, so subs merged "
             "before it would be WIPED. No per-anchor caching yet: every "
             "compose re-run redoes the fleet (~1 min/anchor).",
    ),
    Stage(
        "merge_subs", "land the placed subs in the main fitted preview",
        lambda sc: [PY, "compose/merge_sub_placements.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/merge_subs.json",),
        inputs=("compose/fitted_preview.json",),
        note="TRANSPORT ONLY (R-S2-168 wiring): copies each PLACED "
             "sub's mesh nodes into fitted_preview.glb (RAW both "
             "sides, verified) and appends minimal placed records so "
             "gravity sees them. Re-run guard: already-merged ids are "
             "skipped loudly. The GLB is backed up once to "
             "fitted_preview_presubs.glb.",
    ),
    Stage(
        "gravity", "settle every placed mesh onto what supports it",
        lambda sc: [PY, "compose/fit_gravity.py", "--scene", sc],
        reads="grouped", writes=None,
        artifacts=("compose/fit_gravity.json",),
        inputs=("compose/fitted_preview.json",
                "compose/supported_by.json"),
        note="R-S2-168 (user: 'everything rests on something'). 2 cm "
             "height-map contact, support-depth order so riders land "
             "on settled hosts; wall/ceiling mounts exempt; down when "
             "floating, up when embedded (fresh08: pillows lifted "
             "13-18 cm out of the bed body onto the blanket). "
             "Idempotent within SETTLED_TOL 5 mm. Honest side effect: "
             "a WRONG floor-support verdict becomes a visible object "
             "on the floor instead of a hidden floater (the lamp/pot "
             "finding) — that is the point, not a defect.",
    ),
    Stage(
        "prep_viewer", "build the payload that lets a human look at this "
                       "scene",
        lambda sc: [PY, "viewer/prep_scene.py", "--scene", sc],
        artifacts=("repo:viewer/data/{scene}.bin",),
        note="⚠ THE STAGE THAT WAS IN NO TABLE, and the omission had a "
             "shape worth remembering: a scene could pass all 45 stages "
             "and every gate and still be INVISIBLE. The viewer lists "
             "whatever is in viewer/data/*.bin, and nothing in the "
             "pipeline put anything there — `fresh02` finished completely "
             "and did not appear in the dropdown. Over a hundred scenes "
             "that is a hundred results nobody can look at without "
             "remembering a command by hand, which is the exact class of "
             "problem this table exists to remove. "
             "IT IS LAST AND IT IS CHEAP TO SKIP: ~19.5 MB per scene "
             "(about 2 GB across a hundred), it spends no model calls and "
             "no GPU, and `--skip prep_viewer` drops it for a run whose "
             "scenes nobody intends to open.",
    ),
)

COMPOSE_KEYS = tuple(s.key for s in COMPOSE)

#: THE FIT BLOCK IS A LOOP, AND IT REPEATS UNTIL IT GOES DRY.
#:
#: docs/plans/PLAN_FIT_LOOP.md:118-123 (CANON 08-04 late night, the user
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
BY_KEY = {s.key: s for s in INTAKE}
BY_KEY.update({s.key: s for s in RECORD})
BY_KEY.update({s.key: s for s in CHAIN})
BY_KEY.update({s.key: s for s in COMPOSE})

# A key in two tuples would make --skip and --from silently ambiguous, and
# the funnel and the chain both have a stage that could plausibly be
# called "lift" or "filter". Catch it at import, not at 3 a.m.
_seen = {}
for _group, _name in ((INTAKE, "INTAKE"), (RECORD, "RECORD"),
                      (CHAIN, "CHAIN"), (COMPOSE, "COMPOSE")):
    for _s in _group:
        if _s.key in _seen:
            raise SystemExit(
                f"stage key '{_s.key}' is in both {_seen[_s.key]} and "
                f"{_name}. Keys are how --skip / --from / --until name a "
                f"stage, so they must be unique across all three tables.")
        _seen[_s.key] = _name
del _seen, _group, _name, _s

#: the layer the chain must end on for a scene to count as finished
FINAL_LAYER = "grouped"


def get(key):
    try:
        return BY_KEY[key]
    except KeyError:
        raise SystemExit(
            f"unknown stage '{key}'.\n"
            f"  intake : {', '.join(INTAKE_KEYS)}\n"
            f"  record : {', '.join(RECORD_KEYS)}\n"
            f"  graph  : {', '.join(KEYS)}\n"
            f"  compose: {', '.join(COMPOSE_KEYS)}")


def _select(group, keys, from_key=None, until_key=None, skip=()):
    """The stages of one table to run, honouring --from / --until / --skip."""
    skip = {s.strip() for s in skip if s and s.strip()}
    for label, key in (("--from", from_key), ("--until", until_key)):
        if key and key in skip:
            raise SystemExit(f"{label} {key} is also in --skip: the range "
                             f"cannot start or end on a stage that is not "
                             f"going to run")
    lo = keys.index(from_key) if from_key else 0
    hi = keys.index(until_key) if until_key else len(keys) - 1
    if lo > hi:
        raise SystemExit(f"--from {from_key} comes after --until {until_key}")
    return [s for s in group[lo:hi + 1] if s.key not in skip]


def select_intake(from_key=None, until_key=None, skip=()):
    """The intake stages to run, same rules as select()."""
    return _select(INTAKE, INTAKE_KEYS, from_key, until_key, skip)


def select_record(from_key=None, until_key=None, skip=()):
    """The record/judge stages to run, same rules as select()."""
    return _select(RECORD, RECORD_KEYS, from_key, until_key, skip)


def select_compose(from_key=None, until_key=None, skip=()):
    """The compose stages to run, same rules as select()."""
    return _select(COMPOSE, COMPOSE_KEYS, from_key, until_key, skip)


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
    w = max(len(k) for k in INTAKE_KEYS + RECORD_KEYS + KEYS + COMPOSE_KEYS)
    lines = []
    for title, group in (("INTAKE — the bundle becomes a measured room",
                          INTAKE),
                         ("RECORD + JUDGE — the room becomes a graph, and "
                          "its identities get settled", RECORD),
                         ("GRAPH CHAIN — the vote onward", CHAIN),
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
