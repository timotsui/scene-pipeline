"""run_scene.py — run one scene end to end, unattended, with a checkpoint
between every stage.

A scene is built in TWO PHASES, and this file is the one place where the
whole thing is written down.

THE GEOMETRIC CORE takes the Marble bundle and turns pictures into 3D
boxes. It is the verified Session-A path and it has not changed:

    bundle (out/<scene>/bundle_path.txt)
      -> crop_pano             pinhole crops from the equirect pano
      -> vocab_from_prompt     detection vocab (prompt nouns + synonyms)
      -> seg_views             GroundingDINO + SAM over the crops
      -> seg_pano_overlay      gate artifacts (pano overlay + crop montage)
      -> lift_pano             mask rays ∩ collider -> scene_manifest_pano.json
      -> manifest_pano_to_raw  raw-frame variants (panoraw_{a,b,c})

THE GRAPH CHAIN takes the scene graph from the vote to `grouped`: eleven
steps that until 2026-08-11 lived only in docs/AUTOMATION_READINESS.md
and in whatever a person remembered. This file does NOT repeat them. The
order is data in graph/stages.py, and this runner walks that table. Add a
stage there and it runs here; nothing else has to learn it.

THE CHECKPOINT IS THE POINT. Around every graph-chain stage we ask
graph/scene_gate.py two questions the stage cannot answer about itself:

    before  is the layer this stage reads present and NOT STALE?
    after   did this stage really write, JUST NOW, the layer and the
            files it promised — and is that layer now the state of the
            scene?

The failure this guards against is not a crash. A crash is loud and the
runner stops. It is a stage that succeeds and does nothing, so the next
stage quietly reads the previous run's answer. And at the end, `final()`
asks the question nothing ever asked before: did the run FINISH — nothing
stale, the chain ended on `grouped`, the evidence layer whole? A scene
only counts as PASS when that answers yes.

COMMON INVOCATIONS

    python run_scene.py --scene bedroom_marble
        both phases, stopping at the first failure

    python run_scene.py --scene bedroom_marble --phase core
    python run_scene.py --scene bedroom_marble --phase graph
        one phase only

    python run_scene.py --list
        print the graph chain and exit

    python run_scene.py --scene S --phase graph --dry-run
        print every command and every gate check that WOULD happen,
        and run nothing

    python run_scene.py --scene S --phase graph --from settled --until j9
        re-run a range of the chain

    python run_scene.py --scene S --skip crop,seg,j8
        skip by name; core stage names and graph stage keys both work

    python run_scene.py --scene S --no-llm
        the free stages only. The scene is NOT complete afterwards and
        the summary says so loudly.

    python run_scene.py --scene S --continue-on-fail
        run everything and report every failure, instead of stopping

THE ONE LOOP. Compose is not a straight line. Its fit block —
fit_preview -> fit_declip -> fit_check -> fit_walk — REPEATS UNTIL IT
GOES DRY (canon 08-04, docs/PLAN_FIT_LOOP.md:118-123; a real
living_marble run needed four rounds, docs/REVIEW_LOG.md:779). "Dry"
is not a guess: fit_walk writes `changed_this_run`, the number of new
candidate swaps it made this pass, and 0 means the scene stopped
moving. A hard cap (--fit-max-rounds, default 6) stops a run that will
not converge, and hitting that cap is reported as a FAILURE — stopping
because we ran out of patience is not a fitted scene. Every round is
fully gated like any other pass, and every run-log row carries its
round number so four rows called `fit_preview` cannot be mistaken for
one stage run four times by accident.

EXIT CODES
    0  everything ran and the final gate passed
    1  a stage crashed
    2  a stage REFUSED: node_evidence exits 2 when the evidence layer
       would have holes. Not a crash — a deliberate refusal, reported as
       such and passed through so a fleet runner can tell it apart.
    3  a gate failed: the state of the scene was not legal before or
       after a stage, the final check said the run did not finish, or
       the compose fit loop hit its round cap without going dry
    When more than one thing failed, the exit code is the FIRST failure's.

THE RUN LOG. Every run writes out/<scene>/run_scene_<utc>-<pid>.json: the
argv, return code and duration of every stage, when it started and ended,
how long the two gate checks around it took, plus the gate lines from
before and after it. Over a hundred scenes that file, not console
scrollback, is how anyone finds out what happened. Its path is printed at
the end.

WHERE THE TIME WENT. The end-of-run summary prints a TIMING block: every
stage that ran, its seconds, and its share of the run, slowest first. One
scene's block answers "what was slow tonight"; run_fleet.py reads these
same run logs across every scene and prints the same thing per MODULE,
which is the question a hundred scenes actually raise.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import paths

HERE = Path(__file__).resolve().parent
# graph/ is not a package, and the modules in it import each other by bare
# name, so the directory itself has to be on the path. Same preamble the
# graph modules use on themselves (see graph/node_views.py).
for _p in (HERE, HERE / "graph"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import scene_gate as gate     # noqa: E402  the checkpoint
import stages                 # noqa: E402  the chain, as data

PY = sys.executable

#: the geometric core, in order. Names here are what --skip takes.
CORE_STAGES = ("crop", "vocab", "seg", "overlay", "lift", "variants")

#: which core stages want the GPU, so the clock-lock warning can fire for
#: a core-only run too (docs/POWER_CRASHES.md).
CORE_GPU = {"seg", "lift"}

# Failure kinds, and the exit code each one means. Kept together so the
# mapping is impossible to get out of step with the docstring.
RC_CRASH = 1
RC_REFUSED = 2
RC_GATE = 3


# --------------------------------------------------------------------------
# the run log
# --------------------------------------------------------------------------

class RunLog:
    """A machine-readable record of one run of one scene.

    Console output scrolls away and nobody re-reads it. This is what is
    left afterwards: what was run, what it returned, how long it took,
    and what the gate said on either side of it."""

    def __init__(self, scene, runid):
        self.scene = scene
        self.runid = runid
        self.path = paths.scene_dir(scene) / f"run_scene_{runid}.json"
        self.data = {
            "scene": scene,
            "runid": runid,
            "started": _utc_iso(),
            "ended": None,
            "argv": [str(a) for a in sys.argv],
            "stages": [],
            "final_gate": None,
            "failures": [],
            "verdict": None,
        }

    def stage(self, phase, key, argv, rc, seconds, before=None, after=None,
              note="", started=None, ended=None,
              seconds_gate_before=None, seconds_gate_after=None,
              round_no=None):
        """One stage, as a row.

        `round_no` IS WHAT KEEPS A LOOP HONEST IN THE LOG. (It is
        `round_no` and not `round` because this method calls the builtin
        `round()` three lines down, and a parameter named `round` shadows
        it — caught by the scratchpad loop test, which is what a fake
        stage runner is for.) The fit block
        repeats until it goes dry, so one run writes four rows called
        `fit_preview`, and a reader — or the fleet's by-module table —
        looking at four identical names has no way to tell a loop from a
        bug. The round number (1, 2, 3 … or the string "closing" for the
        pass that applies the rotation deltas) is written on every row
        that belongs to a repeated block, and None on every row that
        runs once. run_fleet.by_module keys on the stage name and
        APPENDS each row's seconds to that stage's sample list, so four
        rounds SUM into fit_preview's total rather than overwriting each
        other — which is the behaviour we want. Its `scenes` column
        counts samples, so a looped stage inflates that one count; the
        seconds are right, the sample count is rows not scenes.

        `seconds` is WALL CLOCK FOR THE CHILD PROCESS ITSELF and nothing
        else — not the gate checks on either side of it, which are timed
        separately as `seconds_gate_before` / `seconds_gate_after` so a
        slow stage is never confused with a slow check. On the GPU stages
        that wall clock includes time this process spent waiting on a
        renderer running inside WSL, which is where most of it goes; the
        runner cannot see inside that, so the number is honestly "how
        long we waited", not "how long the GPU worked".

        `started` and `ended` are ISO UTC strings rather than durations
        because durations cannot be lined up: two runs on the same night
        can only be compared against each other on a clock."""
        self.data["stages"].append({
            "phase": phase,
            "stage": key,
            "round": round_no,
            "argv": _norm_argv(argv),
            "returncode": rc,
            "seconds": round(seconds, 2),
            "started": started,
            "ended": ended,
            "seconds_gate_before": (None if seconds_gate_before is None
                                    else round(seconds_gate_before, 2)),
            "seconds_gate_after": (None if seconds_gate_after is None
                                   else round(seconds_gate_after, 2)),
            "before": _lines(before),
            "after": _lines(after),
            "note": note,
        })

    def skipped(self, phase, key, why):
        self.data["stages"].append({
            "phase": phase, "stage": key, "round": None,
            "argv": [], "returncode": None,
            "seconds": 0.0, "started": None, "ended": None,
            "seconds_gate_before": None, "seconds_gate_after": None,
            "before": None, "after": None,
            "skipped": why, "note": why,
        })

    def write(self, verdict, failures, final_result=None):
        self.data["ended"] = _utc_iso()
        self.data["verdict"] = verdict
        self.data["failures"] = failures
        self.data["final_gate"] = _lines(final_result)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self.data, indent=2),
                             encoding="utf-8")
        return self.path


def _utc_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _runid():
    """A run id that sorts by time and is still unique.

    The bare timestamp was not enough. It has one-second resolution, and
    two runs started inside the same second — a fleet retrying a scene, a
    person starting a run while a script starts another — silently
    overwrote each other's run log, so one of the two runs simply had no
    record. The process id is the cheapest thing guaranteed distinct
    between two live runs, so it goes on the end. The timestamp stays
    first so a directory listing is still in run order, and both parts
    are filename-safe on Windows."""
    return (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + f"-{os.getpid()}")


def _norm_argv(argv):
    """One command is a list of strings; a stage that ran several is a list
    of those lists. Both shapes are kept as they are so the log never has
    to lie about how many commands a stage was."""
    if argv and isinstance(argv[0], (list, tuple)):
        return [[str(x) for x in one] for one in argv]
    return [str(x) for x in argv]


def _since_mark(mark):
    """The command line(s) spawned since `mark` was taken. A core stage is
    one command today, so unwrap that case for readability."""
    ran = ARGV_TRACE[mark:]
    return ran[0] if len(ran) == 1 else ran


def _lines(result):
    """A gate Result as plain data, or None. `ok` plus the report lines."""
    if result is None:
        return None
    return {"ok": result.ok, "what": result.what,
            "lines": [{"level": lv, "msg": m} for lv, m in result.lines]}


# --------------------------------------------------------------------------
# running a command
# --------------------------------------------------------------------------

#: every command line this process has spawned, in order. The core stages
#: build their own argv inside their functions, so this is how the run log
#: learns what they actually ran without changing their signatures.
ARGV_TRACE = []


def spawn(argv, capture=False):
    """Run a module CLI in the repo dir. Returns (returncode, stdout text).

    Never raises on a non-zero code: deciding what a failure means is the
    caller's job, because a 2 from node_evidence is a refusal and a 1 is
    a crash and they are not the same event."""
    ARGV_TRACE.append([str(x) for x in argv])
    printable = " ".join(str(a) for a in argv)
    print(f"\n$ {printable}", flush=True)
    if capture:
        r = subprocess.run(argv, cwd=HERE, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(r.stdout, end="", flush=True)
        return r.returncode, r.stdout
    r = subprocess.run(argv, cwd=HERE)
    return r.returncode, ""


def run(argv, capture=False):
    """The core phase's caller: same contract it has always had — a
    non-zero return code stops the scene."""
    rc, out = spawn(argv, capture=capture)
    if rc != 0:
        printable = " ".join(str(a) for a in argv)
        raise SystemExit(f"stage failed (rc={rc}): {printable}")
    return out


# --------------------------------------------------------------------------
# the geometric core — unchanged behaviour
# --------------------------------------------------------------------------

def stage_crop(sc):
    run([PY, "crop_pano.py", "--scene", sc])
    n = len(list(paths.pano_crops_dir(sc).glob("pano_*.webp")))
    return {"crops": n}


def stage_vocab(sc):
    """vocab_from_prompt prints '# N terms ...' then the GD prompt on the last
    line. Capture it, persist to seg_pano/vocab.txt, return the prompt string."""
    out = run([PY, "vocab_from_prompt.py", "--scene", sc], capture=True)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    vocab = lines[-1].strip()
    seg = paths.seg_pano_dir(sc)
    seg.mkdir(parents=True, exist_ok=True)
    (seg / "vocab.txt").write_text(vocab + "\n", encoding="utf-8")
    n_terms = len([t for t in vocab.split(".") if t.strip()])
    return {"vocab": vocab, "terms": n_terms}


def stage_seg(sc, vocab, box_thr):
    run([PY, "seg_views.py", "--scene", sc,
         "--views-dir", str(paths.pano_crops_dir(sc)),
         "--glob", "pano_*.webp",
         "--out-dir", str(paths.seg_pano_dir(sc)),
         "--prompt", vocab,
         "--box-thr", str(box_thr)])
    dets = json.loads((paths.seg_pano_dir(sc) / "detections.json").read_text())
    return {"detections": sum(len(v) for v in dets.values()),
            "views_with_dets": sum(1 for v in dets.values() if v)}


def stage_overlay(sc):
    run([PY, "seg_pano_overlay.py", "--scene", sc])
    return {}


def stage_lift(sc):
    run([PY, "lift_pano.py", "--scene", sc])
    man = json.loads((paths.scene_dir(sc) / "scene_manifest_pano.json").read_text())
    return {"objects": len(man.get("objects", []))}


def stage_variants(sc):
    run([PY, "manifest_pano_to_raw.py", "--scene", sc])
    variants = sorted(p.name for p in paths.scene_dir(sc).glob("scene_manifest_panoraw_*.json"))
    return {"variants": variants}


def core_dry_run(sc, skip, box_thr):
    """What the core WOULD run. The seg command is shown with a placeholder
    prompt because the real one is whatever the vocab stage prints on this
    run, and a dry run does not run it."""
    plan = [
        ("crop", [PY, "crop_pano.py", "--scene", sc]),
        ("vocab", [PY, "vocab_from_prompt.py", "--scene", sc]),
        ("seg", [PY, "seg_views.py", "--scene", sc,
                 "--views-dir", str(paths.pano_crops_dir(sc)),
                 "--glob", "pano_*.webp",
                 "--out-dir", str(paths.seg_pano_dir(sc)),
                 "--prompt", "<vocab from the vocab stage>",
                 "--box-thr", str(box_thr)]),
        ("overlay", [PY, "seg_pano_overlay.py", "--scene", sc]),
        ("lift", [PY, "lift_pano.py", "--scene", sc]),
        ("variants", [PY, "manifest_pano_to_raw.py", "--scene", sc]),
    ]
    print("\n[dry-run] GEOMETRIC CORE")
    for name, argv in plan:
        if name in skip:
            print(f"  skip  {name}")
            continue
        print(f"  run   {name}")
        print(f"        $ {' '.join(str(a) for a in argv)}")
    print("  (the core has no gate; its outputs are judged by the user on "
          "the gate artifacts printed in the summary)")


def run_core(sc, skip, box_thr, log, failures, stop_on_fail):
    """The six geometric stages, in order, exactly as they always ran.

    The core has no scene_gate checkpoint: it predates the scene graph and
    its outputs are manifests, not layers. Its stages are logged the same
    way so one run log covers the whole scene."""
    summary = {}
    vocab = None

    def call(name, fn):
        """One core stage: time it, log it, and turn a failure into a
        recorded failure instead of an immediate exit, so that
        --continue-on-fail means the same thing in both phases."""
        if name in skip:
            log.skipped("core", name, "skipped by --skip")
            return None
        mark = len(ARGV_TRACE)
        t0 = time.time()
        started = _utc_iso()
        try:
            out = fn()
        except SystemExit as e:
            dt = time.time() - t0
            log.stage("core", name, _since_mark(mark), RC_CRASH, dt,
                      note=str(e), started=started, ended=_utc_iso())
            failures.append({"phase": "core", "stage": name,
                             "kind": "crashed", "code": RC_CRASH,
                             "detail": str(e)})
            print(f"[run_scene] FAILED core stage `{name}`: {e}", flush=True)
            return "FAILED"
        dt = time.time() - t0
        log.stage("core", name, _since_mark(mark), 0, dt,
                  started=started, ended=_utc_iso())
        summary[name] = out
        return out

    for name in CORE_STAGES:
        if name == "crop":
            if call("crop", lambda: stage_crop(sc)) == "FAILED" and stop_on_fail:
                return summary
        elif name == "vocab":
            r = call("vocab", lambda: stage_vocab(sc))
            if r == "FAILED":
                if stop_on_fail:
                    return summary
            elif r is not None:
                vocab = r["vocab"]
            if vocab is None:
                # Either the stage was skipped or it failed; a previous run
                # may have left the prompt on disk, which is what --skip
                # vocab is for.
                vf = paths.seg_pano_dir(sc) / "vocab.txt"
                vocab = vf.read_text(encoding="utf-8").strip() if vf.exists() else None
        elif name == "seg":
            if "seg" in skip:
                log.skipped("core", "seg", "skipped by --skip")
                continue
            if not vocab:
                msg = ("seg stage needs a vocab (run the vocab stage or "
                       "provide seg_pano/vocab.txt)")
                log.stage("core", "seg", [], RC_CRASH, 0.0, note=msg)
                failures.append({"phase": "core", "stage": "seg",
                                 "kind": "crashed", "code": RC_CRASH,
                                 "detail": msg})
                print(f"[run_scene] FAILED core stage `seg`: {msg}", flush=True)
                if stop_on_fail:
                    return summary
                continue
            if call("seg", lambda: stage_seg(sc, vocab, box_thr)) == "FAILED" \
                    and stop_on_fail:
                return summary
        elif name == "overlay":
            if call("overlay", lambda: stage_overlay(sc)) == "FAILED" and stop_on_fail:
                return summary
        elif name == "lift":
            if call("lift", lambda: stage_lift(sc)) == "FAILED" and stop_on_fail:
                return summary
        elif name == "variants":
            if call("variants", lambda: stage_variants(sc)) == "FAILED" and stop_on_fail:
                return summary
    return summary


# --------------------------------------------------------------------------
# the graph chain — order and flags come from graph/stages.py
# --------------------------------------------------------------------------

def graph_dry_run(sc, selected, title="GRAPH CHAIN", max_rounds=None,
                  final_gate=True):
    """Print the exact command line of every stage that would run, and the
    gate checks that would happen around it. Runs nothing.

    `max_rounds` is passed for the compose phase, and its presence is
    what turns the fit block from four lines into a loop with a stated
    exit condition and a stated cap. A dry run that showed the four
    stages as a straight line would be describing a pipeline this runner
    no longer has."""
    print(f"\n[dry-run] {title}")
    looping = _split_loop(selected) if max_rounds else None
    if looping:
        pre, loop, post = looping
        print(f"  the fit block is a LOOP: "
              f"{' -> '.join(s.key for s in loop)} -> repeat")
        print(f"    exit : {stages.FIT_LOOP_EXIT[0]} "
              f"`{stages.FIT_LOOP_EXIT[1]}` == {stages.FIT_LOOP_EXIT[2]}"
              f"  (0 new walks = DRY, read from fit_walk's own output)")
        print(f"    cap  : {max_rounds} rounds (--fit-max-rounds). Hitting "
              f"the cap is reported as a FAILURE, never as a pass.")
        print(f"    each round is fully gated, and every run-log row "
              f"carries its round number")
        print(f"    then, only if rotation_check passes, a CLOSING pass: "
              f"{' -> '.join(stages.FIT_CLOSING)}")
    for st in selected:
        argv = st.argv(sc)
        cost = ", ".join(x for x in (("LLM" if st.llm else ""),
                                     ("GPU" if st.gpu else "")) if x)
        in_loop = bool(looping) and st.key in stages.FIT_LOOP
        print(f"\n  {st.key}  —  {st.title}"
              + (f"   [{cost}]" if cost else "")
              + ("   [fit loop — runs once per round]" if in_loop else ""))
        print(f"    gate.before(scene, {st.key!r})"
              + (f"  -> requires layer `{st.reads}` present and not stale"
                 if st.reads else "  -> reads no layer"))
        print(f"    $ {' '.join(str(a) for a in argv)}")
        promises = []
        if st.writes:
            promises.append(f"layer `{st.writes}` fresh and current")
        for k in st.graph_keys:
            promises.append(f"graph['{k}'] present")
        for f in st.artifacts:
            promises.append(f"{f} written during this stage")
        print(f"    gate.after(scene, {st.key!r}, since=t0)"
              + ("  -> requires " + "; ".join(promises) if promises
                 else "  -> promises nothing checkable"))
    if final_gate:
        print(f"\n  gate.final(scene)  -> the chain must end on "
              f"`{stages.FINAL_LAYER}`, no layer stale, evidence layer whole")


def _gate_call(fn, *args, **kw):
    """Run a gate function, turning its own SystemExit (no scene graph on
    disk, unknown stage) into a failed Result instead of killing the run.
    Unattended means one broken scene must not take the fleet with it."""
    try:
        return fn(*args, **kw)
    except SystemExit as e:
        r = gate.Result("gate could not run")
        r.add("FAIL", str(e))
        return r


def run_graph(sc, selected, log, failures, stop_on_fail,
              phase="graph", round_no=None):
    """Walk the selected part of stages.CHAIN with a checkpoint on each side.

    The shape is fixed and deliberate:
        t0 = now
        before  -> the input state is legal, or the scene stops here
        run     -> non-zero stops the scene
        after   -> it wrote what it promised, DURING this run

    `since=t0` is what makes `after` able to catch the silent no-op: a
    promised file that exists but predates t0 means the stage exited 0
    having done nothing. t0 is taken before the `before` check so that
    slack always runs the safe way — earlier, never later.

    THE THREE CLOCKS ARE KEPT APART. The stage's own wall clock, the
    `before` check and the `after` check are timed separately. The checks
    are cheap, but "cheap" is a claim, and the only way anyone can see
    that it stays true over a hundred scenes is if the number is written
    down next to the stage it guards.

    `round_no` IS PASSED STRAIGHT THROUGH, NOT INTERPRETED. When this is
    one pass of the fit loop, every row it writes carries the round, and
    the gate still runs PER PASS exactly as it always did: `since=t0` is
    taken fresh each time, so each round's artifacts must have been
    written during THAT round. A loop does not weaken the no-op trap; it
    springs it once per round."""
    per_stage = []
    for st in selected:
        argv = st.argv(sc)
        t0 = time.time()
        started = _utc_iso()

        before = _gate_call(gate.before, sc, st)
        before.print()
        t_gate_before = time.time() - t0
        if not before.ok:
            log.stage(phase, st.key, argv, None, 0.0,
                      before=before,
                      note="gate refused to start this stage",
                      started=started, ended=_utc_iso(),
                      seconds_gate_before=t_gate_before, round_no=round_no)
            failures.append({"phase": phase, "stage": st.key,
                             "round": round_no,
                             "kind": "gate-before", "code": RC_GATE,
                             "detail": _first_fail(before)})
            per_stage.append((st, "GATE-BEFORE", t_gate_before, round_no))
            if stop_on_fail:
                return per_stage
            continue

        t_stage0 = time.time()
        rc, _ = spawn(argv)
        dt = time.time() - t_stage0
        if rc != 0:
            kind = "refused" if rc == RC_REFUSED else "crashed"
            code = RC_REFUSED if rc == RC_REFUSED else RC_CRASH
            detail = ("refused: incomplete evidence — the stage would have "
                      "written a layer with holes in it and declined"
                      if rc == RC_REFUSED else f"stage exited {rc}")
            log.stage(phase, st.key, argv, rc, dt, before=before,
                      note=detail, started=started, ended=_utc_iso(),
                      seconds_gate_before=t_gate_before, round_no=round_no)
            failures.append({"phase": phase, "stage": st.key, "kind": kind,
                             "round": round_no,
                             "code": code, "detail": detail})
            print(f"[run_scene] {kind.upper()} `{st.key}` (rc={rc}): {detail}",
                  flush=True)
            per_stage.append((st, "REFUSED" if rc == RC_REFUSED else "CRASH",
                              dt, round_no))
            if stop_on_fail:
                return per_stage
            continue

        t_after0 = time.time()
        after = _gate_call(gate.after, sc, st, since=t0)
        after.print()
        t_gate_after = time.time() - t_after0
        log.stage(phase, st.key, argv, rc, dt,
                  before=before, after=after,
                  started=started, ended=_utc_iso(),
                  seconds_gate_before=t_gate_before,
                  seconds_gate_after=t_gate_after, round_no=round_no)
        if not after.ok:
            failures.append({"phase": phase, "stage": st.key,
                             "round": round_no,
                             "kind": "gate-after", "code": RC_GATE,
                             "detail": _first_fail(after)})
            per_stage.append((st, "GATE-AFTER", dt, round_no))
            if stop_on_fail:
                return per_stage
            continue
        per_stage.append((st, "ok", dt, round_no))
    return per_stage


def _first_fail(result):
    for level, msg in result.lines:
        if level == "FAIL":
            return msg
    return "gate failed without naming a reason"


# --------------------------------------------------------------------------
# COMPOSE — the same machinery, plus the one loop in the pipeline
# --------------------------------------------------------------------------

def _loop_is_dry(sc):
    """Is the fit loop dry? Answered from fit_walk's OWN OUTPUT.

    Returns (dry, detail). `dry` is True, False, or None when the file
    could not answer at all — and None is deliberately not False: "the
    stage did not say" and "the stage said no" are different facts, and
    only one of them justifies another round.

    THE FIELD IS NOT GUESSED. stages.FIT_LOOP_EXIT names the file, the
    field and the value that means dry, and that triple was read off
    compose/fit_walk.py:124, which writes `changed_this_run` = the
    number of NEW walk choices this run made. The total number of
    choices is the wrong number to look at: fit_walk reads its own
    previous file (fit_walk.py:77) and ACCUMULATES, so the total never
    falls and a loop watching it would never stop."""
    rel, field, dry_value = stages.FIT_LOOP_EXIT
    p = paths.scene_dir(sc) / rel
    if not p.exists():
        return None, f"{rel} is not on disk"
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        return None, f"{rel} could not be read: {e}"
    if not isinstance(data, dict) or field not in data:
        return None, f"{rel} has no `{field}` field"
    return data[field] == dry_value, f"{field}={data[field]!r}"


def _loop_fingerprint(sc):
    """THE FALLBACK, and it is only a fallback. If fit_walk ever stops
    writing its count, the loop can still tell "nothing changed" from
    "something changed" by comparing the file itself between rounds.
    Weaker — a re-run that rewrites a timestamp looks like a change, so
    this can only ever run too long, never stop too early."""
    rel = stages.FIT_LOOP_EXIT[0]
    p = paths.scene_dir(sc) / rel
    if not p.exists():
        return None
    try:
        return hashlib.sha1(p.read_bytes()).hexdigest()
    except OSError:
        return None


def _split_loop(selected):
    """(before, loop, after) for a compose selection, or None when the
    loop block is not wholly and contiguously present.

    Partial is a legitimate thing to ask for — `--from fit_walk` while
    debugging one module — so it is not an error. But it is not the
    loop, and the caller says so out loud rather than pretending a
    single pass was the stage."""
    keys = [s.key for s in selected]
    if not all(k in keys for k in stages.FIT_LOOP):
        return None
    lo = keys.index(stages.FIT_LOOP[0])
    hi = keys.index(stages.FIT_LOOP[-1])
    if tuple(keys[lo:hi + 1]) != tuple(stages.FIT_LOOP):
        return None
    return selected[:lo], selected[lo:hi + 1], selected[hi + 1:]


def run_compose(sc, selected, log, failures, stop_on_fail, max_rounds):
    """The compose phase: straight-line stages, then the fit LOOP, then
    the closing pass.

    THE FIT BLOCK IS NOT A LIST OF FOUR STAGES, IT IS A LOOP — canon
    08-04 (docs/PLAN_FIT_LOOP.md:118-123, the user verbatim: "Loop =
    place -> jiggle -> check -> WALK -> repeat until dry; ran to dry on
    bedroom_marble tonight (2 passes)"), and docs/REVIEW_LOG.md:779
    records a living_marble run that needed FOUR rounds. Running it once
    is running the first round and calling the scene finished.

    Each round is a normal gated pass: `run_graph` with the round number
    on every row, so the gate's since=t0 no-op trap fires per round and
    the run log can tell round 3's fit_check from round 1's.

    THE CAP IS A STOP, NOT AN EXIT. Convergence is `changed_this_run ==
    0`. If the rounds run out first, this reports a FAILURE and says
    plainly that the loop did not converge: "we stopped iterating
    because we ran out of patience" is not a scene that fitted."""
    split = _split_loop(selected)
    if split is None:
        if any(s.key in stages.FIT_LOOP for s in selected):
            print("\n[run_scene] NOTE: the fit loop stages "
                  f"({' -> '.join(stages.FIT_LOOP)}) are not all selected, "
                  "or not contiguous, so they run ONCE each, in order, "
                  "and NOT as a loop. That is a partial run: the scene "
                  "is not fitted until the whole block runs to dry.",
                  flush=True)
        return run_graph(sc, selected, log, failures, stop_on_fail,
                         phase="compose")

    pre, loop, post = split
    per_stage = []

    if pre:
        per_stage += run_graph(sc, pre, log, failures, stop_on_fail,
                               phase="compose")
        if failures and stop_on_fail:
            return per_stage

    print("\n" + "-" * 60)
    print(f"[run_scene] FIT LOOP: {' -> '.join(s.key for s in loop)}")
    print(f"            repeat until {stages.FIT_LOOP_EXIT[0]} reports "
          f"`{stages.FIT_LOOP_EXIT[1]}` == {stages.FIT_LOOP_EXIT[2]} "
          f"(0 new walks = DRY)")
    print(f"            hard cap {max_rounds} rounds — hitting it is a "
          f"FAILURE, not a pass")
    print("-" * 60, flush=True)

    dry = False
    rounds_run = 0
    prev_print = _loop_fingerprint(sc)
    for rnd in range(1, max_rounds + 1):
        rounds_run = rnd
        print(f"\n[run_scene] fit loop round {rnd}/{max_rounds}", flush=True)
        rows = run_graph(sc, loop, log, failures, stop_on_fail,
                         phase="compose", round_no=rnd)
        per_stage += rows
        if failures and stop_on_fail:
            return per_stage

        # The exit condition is only readable if the stage that writes it
        # actually finished. A failed walk leaves the PREVIOUS round's
        # file on disk, and reading that would be the exact stale-answer
        # bug this runner exists to catch.
        walked_ok = any(st.key == stages.FIT_LOOP[-1] and state == "ok"
                        for st, state, _s, _r in rows)
        if not walked_ok:
            print(f"[run_scene] fit loop STOPPED after round {rnd}: "
                  f"`{stages.FIT_LOOP[-1]}` did not complete, so there is "
                  f"no fresh answer to whether the loop is dry.", flush=True)
            failures.append({"phase": "compose", "stage": "(fit loop)",
                             "round": rnd, "kind": "loop-broken",
                             "code": RC_GATE,
                             "detail": f"the loop stopped at round {rnd} "
                                       f"because {stages.FIT_LOOP[-1]} did "
                                       f"not complete; the scene is not "
                                       f"fitted"})
            return per_stage

        answer, detail = _loop_is_dry(sc)
        if answer is None:
            # FALLBACK, announced. Never silent: a loop whose exit test
            # changed shape is exactly the thing that should be noisy.
            now = _loop_fingerprint(sc)
            answer = (now is not None and now == prev_print)
            prev_print = now
            print(f"[run_scene] ⚠ fit loop: {detail} — falling back to "
                  f"comparing the file between rounds. This is weaker; "
                  f"it can only run too long, never stop too early.",
                  flush=True)
            detail += " (fallback: file unchanged)" if answer else \
                      " (fallback: file changed)"
        print(f"[run_scene] fit loop round {rnd}: {detail} -> "
              f"{'DRY' if answer else 'not dry, another round'}", flush=True)
        if answer:
            dry = True
            break

    if not dry:
        msg = (f"the fit loop hit its {max_rounds}-round cap WITHOUT going "
               f"dry: {stages.FIT_LOOP_EXIT[0]} still reports new walk "
               f"choices, so items are still being swapped and the scene "
               f"is NOT fitted. This is a failure, not a pass — raise "
               f"--fit-max-rounds only if you have a reason to believe it "
               f"converges, and otherwise look at what keeps walking.")
        print(f"\n[run_scene] FIT LOOP DID NOT CONVERGE — {msg}", flush=True)
        failures.append({"phase": "compose", "stage": "(fit loop)",
                         "round": rounds_run, "kind": "loop-cap",
                         "code": RC_GATE, "detail": msg})
        if stop_on_fail:
            return per_stage
    else:
        print(f"\n[run_scene] fit loop DRY after {rounds_run} round(s).",
              flush=True)

    if post:
        per_stage += run_graph(sc, post, log, failures, stop_on_fail,
                               phase="compose")
        if failures and stop_on_fail:
            return per_stage

    # THE CLOSING PASS. rotation_check writes a record and touches
    # nothing; its yaw deltas reach the scene only when the placement is
    # rebuilt with them and the jiggle re-settles what moved
    # (pipeline_map.html:883, "HIGH-conf applied via one closing
    # place→jiggle pass"). It runs ONLY if rotation_check itself ran and
    # passed in THIS run — replaying a place→jiggle over an old
    # rotation_check.json would be applying yesterday's verdicts and
    # calling it today's work.
    rot_ok = any(st.key == "rotation_check" and state == "ok"
                 for st, state, _s, _r in per_stage)
    if rot_ok:
        closing = [stages.get(k) for k in stages.FIT_CLOSING]
        print("\n[run_scene] closing pass (applies the rotation deltas): "
              f"{' -> '.join(stages.FIT_CLOSING)}", flush=True)
        per_stage += run_graph(sc, closing, log, failures, stop_on_fail,
                               phase="compose", round_no="closing")
    elif any(s.key == "rotation_check" for s in selected):
        print("\n[run_scene] closing pass SKIPPED: rotation_check did not "
              "run or did not pass in this run, so there are no fresh "
              "yaw deltas to apply.", flush=True)
    return per_stage


# --------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------

def parse_skip(raw):
    """Split --skip into core stage names and graph stage keys.

    One flag covers both phases because from a user's point of view there
    is one list of things a scene does. A token that is neither is a typo
    and stops the run — silently ignoring it would mean a stage the user
    thought was skipped runs anyway."""
    core, graph_keys, unknown = set(), set(), []
    for tok in (t.strip() for t in raw.split(",")):
        if not tok:
            continue
        if tok in CORE_STAGES:
            core.add(tok)
        elif tok in stages.BY_KEY:
            graph_keys.add(tok)
        else:
            unknown.append(tok)
    if unknown:
        raise SystemExit(
            f"--skip: unknown stage(s) {', '.join(unknown)}.\n"
            f"  core stages : {', '.join(CORE_STAGES)}\n"
            f"  graph stages: {', '.join(stages.KEYS)}")
    return core, graph_keys


def gpu_warning(selected_graph, core_names):
    """Printed once, at startup, when anything in this run wants the GPU.

    This machine hard-powers-off under GPU burst — a power-delivery fault,
    not heat (docs/POWER_CRASHES.md). The mitigation is a clock lock, and
    the crash itself is a reboot, so a crash always clears a lock applied
    by hand. We only remind; applying it needs an admin shell and checking
    it is not this runner's job."""
    wants = ([s.key for s in selected_graph if s.gpu]
             + sorted(n for n in core_names if n in CORE_GPU))
    if not wants:
        return
    print("\n" + "!" * 60)
    print("[run_scene] GPU WARNING — this machine hard-powers-off under GPU")
    print("            burst. It is power delivery, not temperature.")
    print(f"            Stages in this run that use the GPU: {', '.join(wants)}")
    print("            Before a long run, check that:")
    print("              * tools/watch_gpu.ps1 is running (it logs the burst")
    print("                that precedes a crash, so the next one is not blind)")
    print("              * the clock lock is on: nvidia-smi -lgc 0,1500,")
    print("                which needs an ADMIN shell mid-session. The")
    print("                GPUClockLock scheduled task re-applies it at every")
    print("                boot, which covers the case after a crash.")
    print("            See docs/POWER_CRASHES.md.")
    print("!" * 60, flush=True)


class ArgParser(argparse.ArgumentParser):
    """argparse exits 2 on a usage error, and 2 is spoken for here — it
    means a stage REFUSED (node_evidence declining to write an evidence
    layer with holes). A fleet runner reading exit codes must not confuse
    a typo on the command line with a scene that refused itself, so a
    usage error leaves by the crash door instead."""

    def error(self, message):
        self.print_usage(sys.stderr)
        self.exit(RC_CRASH, f"{self.prog}: error: {message}\n")


def main():
    ap = ArgParser(
        description="Run one scene end to end: the geometric core, the "
                    "graph chain, and a gate between every stage.")
    ap.add_argument("--scene", help="scene name under out/")
    ap.add_argument("--box-thr", type=float, default=0.35,
                    help="GroundingDINO box threshold for the seg stage")
    ap.add_argument("--skip", default="",
                    help="comma-separated stages to skip. Core stages: "
                         + ",".join(CORE_STAGES)
                         + ". Graph stages: " + ",".join(stages.KEYS))
    ap.add_argument("--phase", choices=("core", "graph", "compose", "all"),
                    default="all",
                    help="which part to run (default: all). core = bundle "
                         "to boxes; graph = boxes to `grouped`; compose = "
                         "`grouped` to a furnished scene")
    ap.add_argument("--from", dest="from_key", default=None,
                    help="graph chain: first stage to run")
    ap.add_argument("--until", dest="until_key", default=None,
                    help="graph chain: last stage to run")
    ap.add_argument("--no-llm", action="store_true",
                    help="skip every stage that spends model calls. The "
                         "scene will NOT be complete.")
    ap.add_argument("--list", action="store_true",
                    help="print the graph chain and exit")
    ap.add_argument("--continue-on-fail", action="store_true",
                    help="run the rest of the chain after a failure and "
                         "report every failure at the end (default: stop "
                         "at the first)")
    ap.add_argument("--dry-run", action="store_true",
                    help="print every command and gate check that would "
                         "happen, and execute nothing")
    ap.add_argument("--fit-max-rounds", type=int,
                    default=stages.FIT_MAX_ROUNDS,
                    help=f"hard cap on rounds of the compose fit loop "
                         f"({' -> '.join(stages.FIT_LOOP)}), default "
                         f"{stages.FIT_MAX_ROUNDS}. The loop's real exit "
                         f"is `{stages.FIT_LOOP_EXIT[1]}` == "
                         f"{stages.FIT_LOOP_EXIT[2]} in "
                         f"{stages.FIT_LOOP_EXIT[0]}; this cap only stops "
                         f"a run that will not converge, and hitting it "
                         f"is reported as a FAILURE.")
    a = ap.parse_args()

    if a.list:
        print(stages.describe())
        return 0
    if not a.scene:
        ap.error("--scene is required (except with --list)")

    sc = a.scene
    skip_core, skip_graph = parse_skip(a.skip)
    stop_on_fail = not a.continue_on_fail
    do_core = a.phase in ("core", "all")
    do_graph = a.phase in ("graph", "all")
    do_compose = a.phase in ("compose", "all")

    # --no-llm is a skip like any other, but it is worth naming separately
    # so the summary can say which judgements this scene never got.
    llm_skipped = []
    if a.no_llm:
        llm_skipped = [s.key for s in stages.CHAIN + stages.COMPOSE if s.llm]
        skip_graph |= set(llm_skipped)

    # --from / --until name a stage in ONE of the two chains. Work out
    # which, so `--from supported_by` does not get handed to the graph
    # selector and rejected as an unknown stage.
    ck = set(stages.COMPOSE_KEYS)
    range_is_compose = (a.from_key in ck) or (a.until_key in ck)
    selected_graph = (
        stages.select(None if range_is_compose else a.from_key,
                      None if range_is_compose else a.until_key,
                      skip_graph)
        if do_graph else [])
    selected_compose = (
        stages.select_compose(a.from_key if range_is_compose else None,
                              a.until_key if range_is_compose else None,
                              skip_graph)
        if do_compose else [])
    core_selected = ([n for n in CORE_STAGES if n not in skip_core]
                     if do_core else [])

    if do_core:
        # bundle presence is the one precondition of the core phase
        bp = paths.scene_dir(sc) / "bundle_path.txt"
        if not bp.exists():
            raise SystemExit(f"missing {bp} — write the Marble bundle folder "
                             f"path into it")
        bundle = bp.read_text().strip()
    else:
        bundle = "(core not run)"

    print(f"[run_scene] scene={sc}  phase={a.phase}  bundle={bundle}"
          f"  box_thr={a.box_thr}"
          f"  skip={sorted(skip_core | skip_graph) or 'none'}")
    if do_graph:
        print(f"[run_scene] graph chain: "
              f"{', '.join(s.key for s in selected_graph) or 'nothing selected'}")
    if llm_skipped:
        print(f"[run_scene] --no-llm: skipping {', '.join(llm_skipped)}")

    gpu_warning(selected_graph, core_selected)

    if a.dry_run:
        print("\n[run_scene] DRY RUN — nothing below is executed, and no run "
              "log is written.")
        if do_core:
            core_dry_run(sc, skip_core, a.box_thr)
        if do_graph:
            graph_dry_run(sc, selected_graph)
        if do_compose:
            graph_dry_run(sc, selected_compose, "COMPOSE",
                          max_rounds=a.fit_max_rounds,
                          final_gate=False)
        if llm_skipped:
            print(f"\n[dry-run] --no-llm would skip: {', '.join(llm_skipped)} "
                  f"— the scene would NOT be complete.")
        print("\n[run_scene] dry run complete.")
        return 0

    runid = _runid()
    log = RunLog(sc, runid)
    failures = []
    t_start = time.time()

    # ONE WRITER PER SCENE, FOR THE WHOLE RUN.
    #
    # paths.write_atomic makes each write of scene_graph.json all-or-
    # nothing, but it cannot stop a LOST UPDATE: two runs of the same
    # scene each read the 1.5 MB graph, each edit their own layer, each
    # rename their copy over the other, and the second one wins. The
    # checkpoint would not catch it either — it asks whether a layer is
    # present and freshly written, never who wrote it.
    #
    # A second run of the same scene is an operator mistake, not a queue,
    # so scene_lock REFUSES rather than waits, and names the other pid.
    # It is held for the whole run and released even if a stage raises.
    with paths.scene_lock(sc, f"run_scene {a.phase} (run {runid})"):
        summary = {}
        if do_core:
            summary = run_core(sc, skip_core, a.box_thr, log, failures,
                               stop_on_fail)

        per_stage = []
        if do_graph and (not failures or not stop_on_fail):
            per_stage = run_graph(sc, selected_graph, log, failures,
                                  stop_on_fail)
        # COMPOSE runs on the same machinery and the same checkpoint. It
        # is a separate phase only because it starts where measurement
        # stops: everything above describes a room that exists, this
        # proposes one to build.
        #
        # It gets its own driver for ONE reason: the fit block is a loop
        # (canon 08-04), and a loop cannot be expressed by walking a
        # list once. Everything outside that block runs exactly as it
        # did, through the same run_graph and the same gate.
        if do_compose and (not failures or not stop_on_fail):
            per_stage += run_compose(sc, selected_compose, log, failures,
                                     stop_on_fail, a.fit_max_rounds)

    # THE CHECK THAT DID NOT EXIST. Until now a scene could end with a
    # stale layer and the runner reported success. A scene is PASS only
    # when the final gate says the run finished.
    # "DID THE RUN FINISH" IS ONLY A FAIR QUESTION OF A WHOLE RUN.
    # The final gate asks whether the chain reached `grouped`. Asked of a
    # deliberately partial run — `--until vote`, `--skip j9`, `--no-llm` —
    # the answer is no, and it is no because that is what was ASKED FOR.
    # Reporting that as a failure trains people to ignore the gate, which
    # is the one thing it cannot survive. So a partial run is INCOMPLETE,
    # never FAIL, and the reason is printed.
    # `skip_graph` already absorbs --no-llm's stages, so subtract them
    # back out or the same cause would be reported twice.
    user_skipped = sorted(skip_graph - set(llm_skipped))
    partial = [r for r in (
        ("--no-llm (the judges never ran)" if a.no_llm else None),
        (f"--until {a.until_key}" if a.until_key
         and a.until_key != stages.KEYS[-1] else None),
        (f"--skip {', '.join(user_skipped)}" if user_skipped else None),
    ) if r]
    final_result = None
    if do_graph and not partial:
        final_result = _gate_call(gate.final, sc)
        final_result.print("[gate]")
        if not final_result.ok:
            # ⚠ THIS SAID `phase`, WHICH DOES NOT EXIST HERE (fixed
            # 2026-08-11). `phase` is a parameter of run_graph; inside
            # main it is a NameError, and it fired exactly when the
            # FINAL GATE FAILED — that is, on every scene that did not
            # finish, which is every fresh scene. The exception escaped
            # before log.write(), so no run log was written for precisely
            # the runs whose log anyone would want, and
            # run_fleet._stage_died_on then read an older run's log or
            # none at all.
            #
            # The value is the literal "final", not "graph": the final
            # gate is not part of either phase. It asks its question
            # after everything has run, and with compose now in the same
            # run, calling it a graph-phase failure would file it under a
            # phase it does not belong to. "(final)" is already the
            # stage name on the same row, so the two agree.
            failures.append({"phase": "final", "stage": "(final)",
                             "kind": "gate-final", "code": RC_GATE,
                             "detail": _first_fail(final_result)})
    elif do_graph and partial:
        print(f"\n[gate] final check SKIPPED: this run was deliberately "
              f"partial ({'; '.join(partial)}), so the chain was never "
              f"going to reach `{stages.FINAL_LAYER}`. THE SCENE IS NOT "
              f"COMPLETE — run it without those options, or check it with "
              f"`python graph/scene_gate.py --scene {sc} --final`.")

    dt = time.time() - t_start
    verdict = "PASS" if not failures and not partial else "FAIL"
    if not failures and partial:
        verdict = "INCOMPLETE"
    # THE LOG IS WRITTEN BEFORE ANYTHING IS PRINTED, AND THE PRINTING
    # CANNOT TAKE IT DOWN. The run log is the artifact that survives the
    # night; the summary is a convenience that scrolls away. Losing the
    # log because the reporting code raised is the wrong failure order,
    # so the write comes first and the summary runs inside a guard. If
    # the summary does break, say so and still return the run's real
    # exit code — a formatting bug must not turn a failed scene into a
    # passing one, or a passing scene into a crash.
    log_path = log.write(verdict, failures, final_result)

    try:
        _print_summary(sc, dt, verdict, summary, per_stage, failures,
                       llm_skipped, final_result, log_path,
                       log.data["stages"])
    except Exception as e:                       # noqa: BLE001 — deliberate
        print(f"\n[run_scene] the end-of-run summary failed to print "
              f"({type(e).__name__}: {e}). THE RUN LOG IS INTACT and was "
              f"written before this: {log_path}", flush=True)

    if not failures:
        return 0
    return failures[0]["code"]


def _print_timing(stage_rows, wall_seconds):
    """WHERE THE TIME WENT IN THIS SCENE.

    Every stage that actually ran, its own wall clock, and its share of
    the run, slowest first. A skipped stage is left out — a zero row
    tells nobody anything and only pushes the real ones down the page.

    The gate column is here on purpose. The two checks around a stage are
    supposed to be cheap; printing them is how anyone would find out that
    one had stopped being cheap, instead of blaming the stage.

    A LOOPED STAGE IS SUMMED, NOT LISTED FOUR TIMES. Since the fit block
    repeats until it goes dry, one run can hold four `fit_preview` rows,
    and four separate lines each with its own share of the run answers
    nobody's question and buries the stages underneath. Rows are totalled
    per stage, and the `runs` column says how many passes went into the
    number — which is the same shape run_fleet.by_module already uses
    across scenes, so the two tables cannot tell different stories."""
    ran = [s for s in stage_rows if not s.get("skipped")]
    if not ran:
        return
    total = sum(float(s.get("seconds") or 0.0) for s in ran)
    gate_total = sum(float(s.get("seconds_gate_before") or 0.0)
                     + float(s.get("seconds_gate_after") or 0.0) for s in ran)
    acc = {}
    for s in ran:
        key = (s.get("stage", "?"), s.get("phase", "?"))
        a = acc.setdefault(key, {"seconds": 0.0, "gate": 0.0, "runs": 0})
        a["seconds"] += float(s.get("seconds") or 0.0)
        a["gate"] += (float(s.get("seconds_gate_before") or 0.0)
                      + float(s.get("seconds_gate_after") or 0.0))
        a["runs"] += 1
    print("\n  TIMING (stage wall clock, slowest first):")
    print(f"    {'stage':14s} {'phase':7s} {'runs':>4s} {'seconds':>9s} "
          f"{'share':>7s} {'gate s':>7s}")
    for (key, phase), a in sorted(acc.items(), key=lambda kv: -kv[1]["seconds"]):
        share = (100.0 * a["seconds"] / total) if total > 0 else 0.0
        print(f"    {key:14s} {phase:7s} {a['runs']:4d} {a['seconds']:9.1f} "
              f"{share:6.1f}% {a['gate']:7.2f}")
    print(f"    {'TOTAL':14s} {'':7s} {len(ran):4d} {total:9.1f} "
          f"{100.0 if total else 0:6.1f}% {gate_total:7.2f}")
    # The run's wall clock is a little longer than the sum of the stages:
    # the difference is the final gate, argument handling, and the gaps
    # between stages. Showing both means the gap is visible instead of
    # being quietly absorbed into whichever stage is nearest.
    print(f"    stages {total:.1f}s of {wall_seconds:.1f}s run wall clock "
          f"({wall_seconds - total:.1f}s outside the stages: the final "
          f"gate and startup)")


def _print_summary(sc, dt, verdict, summary, per_stage, failures,
                   llm_skipped, final_result, log_path, stage_rows=()):
    print("\n" + "=" * 60)
    print(f"[run_scene] {verdict}  scene={sc}  {dt:.1f}s")

    if "crop" in summary:
        print(f"  crops         : {summary['crop']['crops']}")
    if "vocab" in summary:
        print(f"  vocab terms   : {summary['vocab']['terms']}")
        print(f"  vocab         : {summary['vocab']['vocab']}")
    if "seg" in summary:
        print(f"  detections    : {summary['seg']['detections']}"
              f" (in {summary['seg']['views_with_dets']} crops)")
    if "lift" in summary:
        print(f"  objects       : {summary['lift']['objects']}  -> scene_manifest_pano.json")
    if "variants" in summary:
        print(f"  raw variants  : {summary['variants']['variants']}")

    if per_stage:
        print("\n  graph chain:")
        for st, state, secs, rnd in per_stage:
            # The round is printed on the row it belongs to, because four
            # rows called fit_preview with no round are indistinguishable
            # from the same stage having been run four times by mistake.
            tag = "" if rnd is None else f" [round {rnd}]"
            print(f"    {state:11s} {st.key:14s} "
                  f"{(st.reads or '-'):9s} -> {(st.writes or '-'):9s} "
                  f"{secs:6.1f}s  {st.title}{tag}")

    _print_timing(stage_rows, dt)

    if llm_skipped:
        print("\n  " + "*" * 56)
        print("  *  --no-llm: THIS SCENE IS NOT COMPLETE.")
        print(f"  *  Judge stages never ran: {', '.join(llm_skipped)}")
        print("  *  Without them nothing rules on multiplicity, on where a")
        print("  *  split object cuts, or on which instances are the same")
        print(f"  *  product, so the chain cannot reach `{stages.FINAL_LAYER}`.")
        print("  *  Re-run without --no-llm before treating this scene as done.")
        print("  " + "*" * 56)

    if final_result is not None:
        print(f"\n  final gate    : {'PASS' if final_result.ok else 'FAIL'}")
        for level, msg in final_result.lines:
            print(f"    {level:4s}  {msg}")

    if failures:
        print(f"\n  FAILURES ({len(failures)}):")
        for f in failures:
            print(f"    {f['kind']:12s} {f['phase']}/{f['stage']}  "
                  f"(exit {f['code']})")
            print(f"      {f['detail']}")

    # These four belong to the GEOMETRIC CORE, so they are only worth
    # listing when the core actually ran. A graph-only run printed them
    # as four missing files, which reads like a failure and is not one.
    if summary:
        sd = paths.seg_pano_dir(sc)
        print("\n  gate artifacts (USER judges):")
        for p in [sd / "pano_overlay.png", sd / "crops_boxes.png",
                  sd / "manifest_overlay_pano.png",
                  sd / "manifest_plan_pano.png"]:
            print(f"    {'OK ' if p.exists() else '?? '}{p}")

    print(f"\n  run log: {log_path}")
    print(f"  viewer : python viewer/serve.py --scene {sc} --port 8321")
    print(f"           http://localhost:8321/?scene={sc}&man=panoraw_c")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
