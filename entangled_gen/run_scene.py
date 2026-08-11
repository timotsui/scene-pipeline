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

EXIT CODES
    0  everything ran and the final gate passed
    1  a stage crashed
    2  a stage REFUSED: node_evidence exits 2 when the evidence layer
       would have holes. Not a crash — a deliberate refusal, reported as
       such and passed through so a fleet runner can tell it apart.
    3  a gate failed: the state of the scene was not legal before or
       after a stage, or the final check said the run did not finish
    When more than one thing failed, the exit code is the FIRST failure's.

THE RUN LOG. Every run writes out/<scene>/run_scene_<utc>.json: the argv,
return code and duration of every stage, plus the gate lines from before
and after it. Over a hundred scenes that file, not console scrollback, is
how anyone finds out what happened. Its path is printed at the end.
"""
import argparse
import json
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
              note=""):
        self.data["stages"].append({
            "phase": phase,
            "stage": key,
            "argv": _norm_argv(argv),
            "returncode": rc,
            "seconds": round(seconds, 2),
            "before": _lines(before),
            "after": _lines(after),
            "note": note,
        })

    def skipped(self, phase, key, why):
        self.data["stages"].append({
            "phase": phase, "stage": key, "argv": [], "returncode": None,
            "seconds": 0.0, "before": None, "after": None,
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
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


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
        try:
            out = fn()
        except SystemExit as e:
            dt = time.time() - t0
            log.stage("core", name, _since_mark(mark), RC_CRASH, dt,
                      note=str(e))
            failures.append({"phase": "core", "stage": name,
                             "kind": "crashed", "code": RC_CRASH,
                             "detail": str(e)})
            print(f"[run_scene] FAILED core stage `{name}`: {e}", flush=True)
            return "FAILED"
        dt = time.time() - t0
        log.stage("core", name, _since_mark(mark), 0, dt)
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

def graph_dry_run(sc, selected):
    """Print the exact command line of every stage that would run, and the
    gate checks that would happen around it. Runs nothing."""
    print("\n[dry-run] GRAPH CHAIN")
    for st in selected:
        argv = st.argv(sc)
        cost = ", ".join(x for x in (("LLM" if st.llm else ""),
                                     ("GPU" if st.gpu else "")) if x)
        print(f"\n  {st.key}  —  {st.title}"
              + (f"   [{cost}]" if cost else ""))
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


def run_graph(sc, selected, log, failures, stop_on_fail):
    """Walk the selected part of stages.CHAIN with a checkpoint on each side.

    The shape is fixed and deliberate:
        t0 = now
        before  -> the input state is legal, or the scene stops here
        run     -> non-zero stops the scene
        after   -> it wrote what it promised, DURING this run

    `since=t0` is what makes `after` able to catch the silent no-op: a
    promised file that exists but predates t0 means the stage exited 0
    having done nothing."""
    per_stage = []
    for st in selected:
        argv = st.argv(sc)
        t0 = time.time()

        before = _gate_call(gate.before, sc, st)
        before.print()
        if not before.ok:
            log.stage("graph", st.key, argv, None, time.time() - t0,
                      before=before,
                      note="gate refused to start this stage")
            failures.append({"phase": "graph", "stage": st.key,
                             "kind": "gate-before", "code": RC_GATE,
                             "detail": _first_fail(before)})
            per_stage.append((st, "GATE-BEFORE", time.time() - t0))
            if stop_on_fail:
                return per_stage
            continue

        rc, _ = spawn(argv)
        dt = time.time() - t0
        if rc != 0:
            kind = "refused" if rc == RC_REFUSED else "crashed"
            code = RC_REFUSED if rc == RC_REFUSED else RC_CRASH
            detail = ("refused: incomplete evidence — the stage would have "
                      "written a layer with holes in it and declined"
                      if rc == RC_REFUSED else f"stage exited {rc}")
            log.stage("graph", st.key, argv, rc, dt, before=before,
                      note=detail)
            failures.append({"phase": "graph", "stage": st.key, "kind": kind,
                             "code": code, "detail": detail})
            print(f"[run_scene] {kind.upper()} `{st.key}` (rc={rc}): {detail}",
                  flush=True)
            per_stage.append((st, "REFUSED" if rc == RC_REFUSED else "CRASH", dt))
            if stop_on_fail:
                return per_stage
            continue

        after = _gate_call(gate.after, sc, st, since=t0)
        after.print()
        log.stage("graph", st.key, argv, rc, time.time() - t0,
                  before=before, after=after)
        if not after.ok:
            failures.append({"phase": "graph", "stage": st.key,
                             "kind": "gate-after", "code": RC_GATE,
                             "detail": _first_fail(after)})
            per_stage.append((st, "GATE-AFTER", time.time() - t0))
            if stop_on_fail:
                return per_stage
            continue
        per_stage.append((st, "ok", time.time() - t0))
    return per_stage


def _first_fail(result):
    for level, msg in result.lines:
        if level == "FAIL":
            return msg
    return "gate failed without naming a reason"


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
    ap.add_argument("--phase", choices=("core", "graph", "all"), default="all",
                    help="which half to run (default: all)")
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

    # --no-llm is a skip like any other, but it is worth naming separately
    # so the summary can say which judgements this scene never got.
    llm_skipped = []
    if a.no_llm:
        llm_skipped = [s.key for s in stages.CHAIN if s.llm]
        skip_graph |= set(llm_skipped)

    selected_graph = (stages.select(a.from_key, a.until_key, skip_graph)
                      if do_graph else [])
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
        if llm_skipped:
            print(f"\n[dry-run] --no-llm would skip: {', '.join(llm_skipped)} "
                  f"— the scene would NOT be complete.")
        print("\n[run_scene] dry run complete.")
        return 0

    runid = _runid()
    log = RunLog(sc, runid)
    failures = []
    t_start = time.time()

    summary = {}
    if do_core:
        summary = run_core(sc, skip_core, a.box_thr, log, failures,
                           stop_on_fail)

    per_stage = []
    if do_graph and (not failures or not stop_on_fail):
        per_stage = run_graph(sc, selected_graph, log, failures, stop_on_fail)

    # THE CHECK THAT DID NOT EXIST. Until now a scene could end with a
    # stale layer and the runner reported success. A scene is PASS only
    # when the final gate says the run finished.
    final_result = None
    if do_graph and not a.no_llm:
        final_result = _gate_call(gate.final, sc)
        final_result.print("[gate]")
        if not final_result.ok:
            failures.append({"phase": "graph", "stage": "(final)",
                             "kind": "gate-final", "code": RC_GATE,
                             "detail": _first_fail(final_result)})
    elif do_graph and a.no_llm:
        print("\n[gate] final check SKIPPED: --no-llm means the judges never "
              "ran, so the chain cannot have reached "
              f"`{stages.FINAL_LAYER}`. This scene is not complete.")

    dt = time.time() - t_start
    verdict = "PASS" if not failures and not a.no_llm else "FAIL"
    if not failures and a.no_llm:
        verdict = "INCOMPLETE"
    log_path = log.write(verdict, failures, final_result)

    _print_summary(sc, dt, verdict, summary, per_stage, failures,
                   llm_skipped, final_result, log_path)

    if not failures:
        return 0
    return failures[0]["code"]


def _print_summary(sc, dt, verdict, summary, per_stage, failures,
                   llm_skipped, final_result, log_path):
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
        for st, state, secs in per_stage:
            print(f"    {state:11s} {st.key:12s} "
                  f"{(st.reads or '-'):9s} -> {(st.writes or '-'):9s} "
                  f"{secs:6.1f}s  {st.title}")

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
