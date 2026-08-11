"""run_fleet.py — run many scenes, one after another, with nobody watching.

run_scene.py runs ONE scene end to end and stops when that scene goes
wrong. That is right for one scene and wrong for a hundred: a night that
stops at scene 7 has wasted the other ninety-three hours. This file sits
one level above it and has exactly two promises.

    ONE BAD SCENE MUST NOT STOP THE NIGHT. Every scene is a separate
    child process. A crash, a refusal, a failed gate, or a scene that
    wedges and has to be killed is recorded and the fleet moves on. The
    only thing that stops the fleet is --stop-on-fail, asked for by hand.

    IN THE MORNING THERE IS ONE TABLE. out/fleet_<runid>.json and
    out/fleet_<runid>.html: a row per scene with its verdict, its time,
    the stage it died on, and — this is the part that matters — the
    gate's own INFO and WARN lines for that scene.

    AND ONE MORE TABLE: BY MODULE. Per-scene times say which scene was
    slow. Over a hundred scenes the useful question is which MODULE the
    night went into, so the report also carries one row per stage key —
    how many scenes ran it, total, mean, median, worst, and which scene
    was the worst — sorted slowest first. The numbers are read back out
    of each scene's own run_scene log; nothing is re-timed here.

WHY THE WARN AND INFO LINES ARE IN THE TABLE. A scene can PASS and still
be poor. The gate deliberately checks the machinery, not the answers, so
`grouped` can be fresh and whole while eleven objects fell back to a
full-height wedge, forty judge verdicts were defaults because a token
expired, the vote was not canon-eligible, and an unjudged duplicate
shipped as two objects. Every one of those is already counted by
scene_gate.quality_notes(); none of them fails a scene, and none of them
should. So the table carries them next to the verdict, and a hundred
scenes can be sorted by how much of each one was really measured instead
of all looking alike.

THIS FILE REIMPLEMENTS NOTHING. The chain is graph/stages.py, the
checkpoint is graph/scene_gate.py, and one scene is run_scene.py — as a
SUBPROCESS, so that a scene which takes the interpreter down with it
takes only itself. run_scene's exit codes are the whole contract:

    0  pass          1  crashed          2  refused          3  gate failed

COMMON INVOCATIONS

    python run_fleet.py
        every scene paths.gen_scenes() knows about, in order

    python run_fleet.py --scenes bedroom_marble,living_marble
    python run_fleet.py --scenes-file tonight.txt --exclude living_marble

    python run_fleet.py --dry-run --scenes-file tonight.txt
        print the plan — the scene list, the per-scene command line, the
        timeout, where the reports go — and run nothing

    python run_fleet.py --resume
        skip every scene whose final gate already passes. A fleet
        interrupted at scene 60 restarts without redoing the first 59.

    python run_fleet.py --scene-timeout 7200
        two hours per scene instead of the default four

    python run_fleet.py --phase graph --from settled --no-llm
        flags that belong to a scene run are passed straight through to
        run_scene.py and mean there exactly what they mean there

EXIT CODE. 0 when every scene passed, 1 otherwise, with the count
printed. The fleet itself never exits 2 or 3; those are one scene's
codes and they live in the table.
"""
import argparse
import json
import os
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from html import escape
from pathlib import Path

import paths

HERE = Path(__file__).resolve().parent
# graph/ is not a package and its modules import each other by bare name,
# so the directory itself goes on the path. Same preamble run_scene.py and
# the graph modules use.
for _p in (HERE, HERE / "graph"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))

import scene_gate as gate     # noqa: E402  the checkpoint, for final()
import stages                 # noqa: E402  the phase names, so this
                              # driver and run_scene cannot disagree

PY = sys.executable
RUNNER = HERE / "run_scene.py"

#: four hours. Long enough that a real scene with a full render budget
#: finishes, short enough that a wedged one costs a fraction of a night.
DEFAULT_SCENE_TIMEOUT_S = 4 * 3600

#: run_scene.py's exit codes, in the words the table uses. Anything not
#: in here is treated as a crash, because an unknown non-zero code is a
#: process that died in a way run_scene did not choose.
VERDICT_BY_CODE = {
    0: "pass",
    1: "crashed",
    2: "refused",
    3: "gate-failed",
}

#: verdicts that are not a passing scene, worst first. The report sorts
#: rows by this so the failures are at the top of the page at 8am.
FAIL_ORDER = ("crashed", "timeout", "refused", "gate-failed", "skipped",
              "pass")


# --------------------------------------------------------------------------
# the scene list
# --------------------------------------------------------------------------

def read_scenes_file(path):
    """One scene name per line. Blank lines and '#' comments are ignored,
    and a trailing comment on a name line is ignored too, so a list can
    carry a note about why a scene is in it."""
    p = Path(path)
    if not p.exists():
        raise SystemExit(f"[run_fleet] --scenes-file {p} does not exist")
    out = []
    for raw in p.read_text(encoding="utf-8").splitlines():
        name = raw.split("#", 1)[0].strip()
        if name:
            out.append(name)
    return out


def build_scene_list(a):
    """The scenes to run, in order, and every name checked against disk.

    A typo is found HERE and not at scene 60. Discovering at 3am that
    `livingmarble` has no folder, after the other 59 have already run,
    costs the whole night for a missing underscore, so an unknown name
    stops the fleet before it starts."""
    if a.scenes:
        wanted = [s.strip() for s in a.scenes.split(",") if s.strip()]
        source = "--scenes"
    elif a.scenes_file:
        wanted = read_scenes_file(a.scenes_file)
        source = f"--scenes-file {a.scenes_file}"
    else:
        wanted = paths.gen_scenes()
        source = "paths.gen_scenes()"

    excluded = {s.strip() for s in (a.exclude or "").split(",") if s.strip()}
    kept, dropped = [], []
    for name in wanted:
        if name in excluded:
            dropped.append(name)
        elif name in kept:
            continue          # a duplicate in the list is a typo, not a request
        else:
            kept.append(name)

    missing = [s for s in kept if not paths.scene_dir(s).is_dir()]
    if missing:
        known = ", ".join(paths.all_scenes()) or "none"
        raise SystemExit(
            f"[run_fleet] no scene directory for: {', '.join(missing)}\n"
            f"            looked under {paths.OUT}\n"
            f"            scenes on disk: {known}\n"
            f"            nothing has been run.")
    unused = sorted(excluded - set(wanted))
    if unused:
        print(f"[run_fleet] note: --exclude named {', '.join(unused)}, "
              f"which was not in the list anyway")
    if not kept:
        raise SystemExit("[run_fleet] the scene list is empty — nothing to do")
    return kept, dropped, source


# --------------------------------------------------------------------------
# running one scene
# --------------------------------------------------------------------------

def scene_argv(scene, a):
    """The run_scene.py command line for one scene.

    Only the flags that belong to a SCENE run are passed through. The
    fleet's own flags (--resume, --scene-timeout, the report paths) mean
    nothing to run_scene and are not sent."""
    argv = [PY, str(RUNNER), "--scene", scene]
    if a.phase != "all":
        argv += ["--phase", a.phase]
    if a.from_key:
        argv += ["--from", a.from_key]
    if a.until_key:
        argv += ["--until", a.until_key]
    if a.skip:
        argv += ["--skip", a.skip]
    if a.no_llm:
        argv += ["--no-llm"]
    if a.box_thr is not None:
        argv += ["--box-thr", str(a.box_thr)]
    if a.scene_continue_on_fail:
        argv += ["--continue-on-fail"]
    return argv


def kill_tree(proc):
    """Kill the timed-out scene AND everything it started on this side.

    Killing only the direct child leaves its descendants running. A scene
    that timed out is usually mid-render, so the descendants are the
    expensive ones: python, the cmd.exe wrapper, wsl.exe. On Windows the
    reliable way to take a whole tree down is taskkill with /T (tree) and
    /F (force), because Python's own kill() reaches one process only.

    WHAT THIS CANNOT KILL. Anything already running INSIDE the WSL VM is
    not in the Windows process tree at all — wsl.exe is a client, not the
    parent of the Linux process. Reaping that side needs a separate call
    into the VM, which is reap_wsl_renderers() below.

    Returns a line saying what happened, for the scene's report row."""
    if proc.poll() is not None:
        return "the scene had already exited when the timeout fired"
    pid = proc.pid
    try:
        r = subprocess.run(["taskkill", "/T", "/F", "/PID", str(pid)],
                           text=True, errors="replace",
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=60)
        note = (f"taskkill /T /F on pid {pid} returned {r.returncode}: "
                f"{' '.join((r.stdout or '').split())[:200]}")
    except (OSError, subprocess.SubprocessError) as e:
        # taskkill is part of Windows, but this must work anywhere and
        # must never be the thing that stops the fleet, so fall back to
        # killing the one process we have a handle on and say so.
        try:
            proc.kill()
        except OSError:
            pass
        note = (f"taskkill unavailable ({type(e).__name__}: {e}); killed only "
                f"the direct child pid {pid}, so any grandchildren it "
                f"started are still running")

    # Confirm the pid is really gone before the next scene starts. A
    # scene that overlaps the next one competes for the GPU, which is the
    # one shared resource nothing arbitrates (docs/POWER_CRASHES.md).
    for _ in range(20):
        if proc.poll() is not None:
            break
        time.sleep(0.5)
    if proc.poll() is None:
        note += f"; WARNING pid {pid} was still alive 10s after the kill"
    else:
        note += f"; pid {pid} confirmed gone"
    return note


def reap_wsl_renderers():
    """Best effort at the Linux side of a timed-out scene, reported aloud.

    The GPU work runs inside the WSL VM. The Windows-side tree kill above
    cannot touch it, so this asks the VM itself to kill the renderer by
    command line. It is best effort by nature — the pattern could miss, a
    future renderer could be named something else — so it REPORTS what it
    found instead of pretending. Silence here is the failure mode that
    costs a night: the next scene starts, the orphan is still on the
    card, and this machine hard-powers-off under GPU burst.

    Never raises. If WSL itself is unreachable, that is a line in the
    report and the fleet goes on."""
    pattern = "render_targets_wsl.py"
    try:
        r = subprocess.run(["wsl", "-e", "pkill", "-f", pattern],
                           text=True, errors="replace",
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                           timeout=120)
    except (OSError, subprocess.SubprocessError) as e:
        return (f"could not ask WSL to reap `{pattern}` "
                f"({type(e).__name__}: {e}) — check by hand with "
                f"`wsl -e ps aux` and nvidia-smi before the next fleet")
    # pkill's contract: 0 means it signalled at least one process, 1 means
    # nothing matched. Both are useful answers and neither is an error.
    if r.returncode == 0:
        return (f"WSL: killed at least one orphaned `{pattern}` left behind "
                f"by the timeout")
    if r.returncode == 1:
        return f"WSL: no `{pattern}` was running — nothing to reap"
    return (f"WSL: pkill -f {pattern} returned {r.returncode}: "
            f"{' '.join((r.stdout or '').split())[:200]}")


def run_one(scene, argv, timeout_s, log_path):
    """Run one scene to completion, a timeout, or its own death.

    Returns (verdict, returncode, seconds, note). Never raises for
    anything the child did: deciding what a failure means is this file's
    job and the answer is always 'write it down and go on to the next
    scene'.

    THE CHILD IS KILLED WITH ITS TREE, AND THE VM IS ASKED SEPARATELY. On
    a timeout the whole Windows-side process tree goes (kill_tree), and
    then the WSL side is asked to reap its renderer (reap_wsl_renderers),
    because a process inside the VM is not a descendant of anything here.
    Both report what they did into the scene's row, so an operator
    reading the morning table can see whether the card was actually left
    free for the next scene rather than having to guess.

    Popen rather than subprocess.run, because a tree kill needs the pid
    and run() does not hand one out."""
    t0 = time.time()
    note = ""
    try:
        proc = subprocess.Popen(argv, cwd=HERE, text=True, errors="replace",
                                stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT)
    except OSError as e:
        # The child could not be started at all (a missing interpreter, a
        # path that moved). That is a failure of this scene, not of the
        # fleet, so it is recorded like any other.
        out = f"[run_fleet] could not start run_scene.py: {e}\n"
        rc, verdict = None, "crashed"
        _write_scene_log(scene, argv, log_path, t0, rc, out)
        return verdict, rc, time.time() - t0, f"could not start: {e}"

    try:
        out, _ = proc.communicate(timeout=(timeout_s or None))
        rc, verdict = proc.returncode, None
    except subprocess.TimeoutExpired:
        killed = kill_tree(proc)
        reaped = reap_wsl_renderers()
        print(f"[run_fleet] TIMEOUT teardown: {killed}", flush=True)
        print(f"[run_fleet] TIMEOUT teardown: {reaped}", flush=True)
        note = f"{killed}; {reaped}"
        # Collect whatever the scene printed before it was killed. The
        # pipe is drained after the kill so this cannot block forever.
        try:
            out, _ = proc.communicate(timeout=60)
        except (subprocess.TimeoutExpired, OSError, ValueError):
            out = ""
        out = out or ""
        out += (f"\n\n[run_fleet] KILLED after {timeout_s}s — the scene "
                f"exceeded --scene-timeout.\n"
                f"[run_fleet] windows tree: {killed}\n"
                f"[run_fleet] wsl side    : {reaped}\n")
        rc, verdict = None, "timeout"
    dt = time.time() - t0

    _write_scene_log(scene, argv, log_path, t0, rc, out or "")

    if verdict is None:
        verdict = VERDICT_BY_CODE.get(rc, "crashed")
    return verdict, rc, dt, note


def _write_scene_log(scene, argv, log_path, t0, rc, out):
    """Everything the scene printed, under a header saying what it was."""
    dt = time.time() - t0
    header = (f"# run_fleet: {scene}\n"
              f"# $ {' '.join(str(x) for x in argv)}\n"
              f"# started {_iso(t0)}  ended {_iso(time.time())}  "
              f"{dt:.1f}s  rc={rc}\n\n")
    try:
        log_path.parent.mkdir(parents=True, exist_ok=True)
        paths.write_atomic(log_path, header + out)
    except OSError as e:
        print(f"[run_fleet] warning: could not write {log_path}: {e}")


# --------------------------------------------------------------------------
# what the gate says about a scene, after it ran
# --------------------------------------------------------------------------

def gate_lines(scene):
    """scene_gate.final(scene) as plain data, or a recorded failure.

    final() raises SystemExit when there is no scene graph on disk at
    all, which is exactly what a scene that died in the geometric core
    looks like. That is a fact about the scene, not an error in the
    fleet, so it becomes a FAIL line like any other."""
    try:
        res = gate.final(scene)
    except SystemExit as e:
        return {"ok": False, "what": f"final state of `{scene}`",
                "lines": [{"level": "FAIL", "msg": str(e)}]}
    except Exception as e:                       # noqa: BLE001
        # A malformed graph must not take the fleet down between scenes.
        return {"ok": False, "what": f"final state of `{scene}`",
                "lines": [{"level": "FAIL",
                           "msg": f"the gate could not read this scene: "
                                  f"{type(e).__name__}: {e}"}]}
    return {"ok": res.ok, "what": res.what,
            "lines": [{"level": lv, "msg": m} for lv, m in res.lines]}


def died_on(scene, started_at):
    """The stage a scene died on, taken from run_scene's own run log.

    run_scene.py writes out/<scene>/run_scene_<utc>.json with a
    `failures` list. Reading it here means the fleet never has to parse
    console output or duplicate run_scene's idea of what a failure is.
    Only logs written since this scene started count, so an old failure
    from last week is never reported as tonight's."""
    try:
        logs = sorted(paths.scene_dir(scene).glob("run_scene_*.json"),
                      key=lambda p: p.stat().st_mtime)
    except OSError:
        return None, None
    for p in reversed(logs):
        try:
            if p.stat().st_mtime + 5 < started_at:
                break                    # older than this run: stop looking
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        fails = data.get("failures") or []
        if fails:
            f = fails[0]
            return f"{f.get('phase')}/{f.get('stage')}", str(p)
        return None, str(p)
    return None, None


# --------------------------------------------------------------------------
# the morning report
# --------------------------------------------------------------------------

def _iso(epoch=None):
    t = datetime.fromtimestamp(epoch, timezone.utc) if epoch \
        else datetime.now(timezone.utc)
    return t.strftime("%Y-%m-%dT%H:%M:%SZ")


def _runid():
    """A run id that sorts by time and is still unique.

    The bare timestamp has one-second resolution, so two fleets started
    inside the same second wrote out/fleet_<runid>.json over each other
    and one night's report simply vanished. The process id is the
    cheapest thing guaranteed distinct between two live runs, so it goes
    on the end; the timestamp stays first so a directory listing is still
    in run order, and both parts are filename-safe on Windows. Same rule
    as run_scene.py's own run id, deliberately."""
    return (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            + f"-{os.getpid()}")


def _hms(seconds):
    s = int(round(seconds))
    return f"{s // 3600}h{(s % 3600) // 60:02d}m{s % 60:02d}s"


def sort_rows(rows):
    """Failures first, then the passing scenes, each group in run order.
    Nobody reads a morning report to admire the scenes that worked."""
    return sorted(rows, key=lambda r: (FAIL_ORDER.index(r["verdict"])
                                       if r["verdict"] in FAIL_ORDER
                                       else 0, r["index"]))


def totals(rows):
    """N passed and N of each kind of failure, plus the wall clock."""
    by_kind = {}
    for r in rows:
        by_kind[r["verdict"]] = by_kind.get(r["verdict"], 0) + 1
    # A scene skipped by --resume is one whose gate ALREADY passes, so it
    # is not a scene that failed tonight. It is counted separately rather
    # than as a pass, because nothing ran to produce it.
    failed = sum(n for k, n in by_kind.items() if k not in ("pass", "skipped"))
    return {"scenes": len(rows),
            "passed": by_kind.get("pass", 0),
            "skipped": by_kind.get("skipped", 0),
            "failed": failed,
            "by_verdict": by_kind,
            "seconds": sum(r["seconds"] for r in rows)}


def by_module(rows):
    """WHERE DID THE NIGHT GO — one row per stage key, across every scene.

    Per-scene totals answer "which scene was slow". After a hundred
    scenes the question that actually gets asked is "which MODULE is the
    night", and no per-scene number answers it. So the times are read
    back out of each scene's own run_scene_<runid>.json — the same file
    died_on() already reads, and only ever a log written since that scene
    started, so last week's run can never be counted as tonight's.

    NOTHING IS RE-TIMED HERE and nothing new is written per scene. The
    only shared file in this whole path is the fleet report, written once
    at the end by this process. The GPU is the one resource several
    scenes could contend for; files must not become a second one.

    A stage that was skipped is not counted: it did not run, and a zero
    would drag its mean down as if it had been fast."""
    acc = {}
    for r in rows:
        p = r.get("run_log")
        if not p:
            continue                    # skipped, or died before it logged
        try:
            data = json.loads(Path(p).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue                    # a truncated log is not worth a crash
        for st in data.get("stages") or []:
            if st.get("skipped"):
                continue
            key = st.get("stage") or "?"
            secs = float(st.get("seconds") or 0.0)
            gate = (float(st.get("seconds_gate_before") or 0.0)
                    + float(st.get("seconds_gate_after") or 0.0))
            a = acc.setdefault(key, {"stage": key, "phase": st.get("phase"),
                                     "samples": [], "gate_seconds": 0.0,
                                     "scenes": []})
            a["samples"].append(secs)
            a["gate_seconds"] += gate
            a["scenes"].append((secs, r["scene"]))

    out = []
    for a in acc.values():
        worst_secs, worst_scene = max(a["scenes"])
        out.append({
            "stage": a["stage"],
            "phase": a["phase"],
            "scenes": len(a["samples"]),
            "total_seconds": round(sum(a["samples"]), 1),
            "mean_seconds": round(statistics.mean(a["samples"]), 1),
            "median_seconds": round(statistics.median(a["samples"]), 1),
            "max_seconds": round(worst_secs, 1),
            "max_scene": worst_scene,
            "gate_seconds": round(a["gate_seconds"], 2),
        })
    # Slowest module first: the top row is where the night went, and that
    # is the only row most people will read.
    return sorted(out, key=lambda d: -d["total_seconds"])


def print_by_module(mods):
    if not mods:
        print("\n[run_fleet] BY MODULE: no run_scene logs from tonight to "
              "read, so there is nothing to total.")
        return
    total = sum(m["total_seconds"] for m in mods)
    print("\n  BY MODULE (every scene tonight, slowest module first):")
    print(f"    {'stage':12s} {'ph':5s} {'n':>3s} {'total':>9s} {'share':>7s} "
          f"{'mean':>8s} {'median':>8s} {'max':>8s}  worst scene")
    for m in mods:
        share = (100.0 * m["total_seconds"] / total) if total > 0 else 0.0
        print(f"    {m['stage']:12s} {(m['phase'] or '?'):5s} "
              f"{m['scenes']:3d} {m['total_seconds']:9.1f} {share:6.1f}% "
              f"{m['mean_seconds']:8.1f} {m['median_seconds']:8.1f} "
              f"{m['max_seconds']:8.1f}  {m['max_scene']}")
    print(f"    {'TOTAL':12s} {'':5s} {'':3s} {total:9.1f}")


def write_json(path, data):
    return paths.write_atomic(path, json.dumps(data, indent=2) + "\n")


def _notes(row, levels):
    return [ln["msg"] for ln in (row.get("gate") or {}).get("lines", [])
            if ln["level"] in levels]


def write_html(path, data):
    """A plain page with no external assets. Read at 8am on whatever is
    to hand, possibly offline; nothing here loads from the network."""
    t = data["totals"]
    kinds = ", ".join(f"{n} {k}" for k, n in sorted(t["by_verdict"].items())
                      if k not in ("pass", "skipped")) or "none"
    css = """
body{font:14px/1.45 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;
     margin:24px;color:#111;background:#fff}
h1{font-size:20px;margin:0 0 4px}
.sub{color:#555;margin:0 0 18px}
table{border-collapse:collapse;width:100%}
th,td{border-bottom:1px solid #ddd;padding:6px 8px;text-align:left;
      vertical-align:top}
th{background:#f2f2f2;font-weight:600}
td.v{font-weight:700;white-space:nowrap}
tr.pass td.v{color:#0a7f2e}
tr.crashed td.v,tr.timeout td.v{color:#b00020}
tr.gate-failed td.v,tr.refused td.v{color:#a35c00}
tr.skipped td.v{color:#666}
td.num{text-align:right;white-space:nowrap}
ul{margin:0;padding-left:16px}
li{margin:1px 0}
.warn{color:#a35c00}
.info{color:#555}
code{font:12px/1.4 Consolas,Menlo,monospace;background:#f6f6f6;padding:1px 3px}
"""
    h = ["<style>" + css + "</style>",
         f"<h1>fleet {escape(data['runid'])} — "
         f"{t['passed']} of {t['scenes']} passed"
         + (f", {t['skipped']} already done" if t["skipped"] else "")
         + "</h1>",
         f"<p class=sub>failed: {escape(kinds)} &middot; wall clock "
         f"{_hms(t['seconds'])} &middot; started {escape(data['started'])} "
         f"&middot; ended {escape(data['ended'])}<br>"
         f"<code>{escape(' '.join(data['argv']))}</code></p>",
         "<table><tr><th>scene</th><th>verdict</th><th>time</th>"
         "<th>died on</th><th>gate notes (WARN / INFO)</th>"
         "<th>log</th></tr>"]
    for r in sort_rows(data["scenes"]):
        warns = _notes(r, ("FAIL", "WARN"))
        infos = _notes(r, ("INFO",))
        notes = "".join(f"<li class=warn>{escape(m)}</li>" for m in warns) \
            + "".join(f"<li class=info>{escape(m)}</li>" for m in infos)
        # The teardown note only exists on a scene that was killed, and
        # it is the one thing an operator must read before starting
        # another fleet: it says whether the card was left free.
        if r.get("note"):
            notes = f"<li class=warn>teardown: {escape(r['note'])}</li>" + notes
        h.append(
            f"<tr class={r['verdict']}>"
            f"<td>{escape(r['scene'])}</td>"
            f"<td class=v>{escape(r['verdict'])}</td>"
            f"<td class=num>{_hms(r['seconds'])}</td>"
            f"<td>{escape(r.get('died_on') or '')}</td>"
            f"<td>{'<ul>' + notes + '</ul>' if notes else ''}</td>"
            f"<td><code>{escape(r.get('log') or '')}</code></td></tr>")
    h.append("</table>")
    h.append("<p class=sub>A scene can PASS and still be poor: the gate "
             "checks the machinery, not the answers. The WARN and INFO "
             "lines are how much of the scene was really measured.</p>")

    mods = data.get("by_module") or []
    h.append("<h1 style='margin-top:28px'>by module</h1>")
    h.append("<p class=sub>Where the night went. One row per stage, totalled "
             "across every scene that ran it, slowest first. Times come from "
             "each scene&rsquo;s own run_scene log; nothing is re-timed. A "
             "GPU stage&rsquo;s seconds include time spent waiting on a "
             "renderer inside WSL.</p>")
    if not mods:
        h.append("<p class=sub>No run_scene logs from tonight to total.</p>")
    else:
        mtotal = sum(m["total_seconds"] for m in mods) or 1.0
        h.append("<table><tr><th>stage</th><th>phase</th><th>scenes</th>"
                 "<th>total</th><th>share</th><th>mean</th><th>median</th>"
                 "<th>max</th><th>slowest scene</th><th>gate</th></tr>")
        for m in mods:
            h.append(
                f"<tr><td><code>{escape(m['stage'])}</code></td>"
                f"<td>{escape(m['phase'] or '')}</td>"
                f"<td class=num>{m['scenes']}</td>"
                f"<td class=num>{_hms(m['total_seconds'])}</td>"
                f"<td class=num>{100.0 * m['total_seconds'] / mtotal:.1f}%</td>"
                f"<td class=num>{_hms(m['mean_seconds'])}</td>"
                f"<td class=num>{_hms(m['median_seconds'])}</td>"
                f"<td class=num>{_hms(m['max_seconds'])}</td>"
                f"<td>{escape(m['max_scene'])}</td>"
                f"<td class=num>{m['gate_seconds']:.1f}s</td></tr>")
        h.append(f"<tr><td><b>total</b></td><td></td><td></td>"
                 f"<td class=num><b>{_hms(mtotal)}</b></td>"
                 f"<td colspan=5></td><td></td></tr>")
        h.append("</table>")
    return paths.write_atomic(path, "\n".join(h) + "\n")


# --------------------------------------------------------------------------
# command line
# --------------------------------------------------------------------------

def build_parser():
    ap = argparse.ArgumentParser(
        description="Run many scenes through run_scene.py, unattended: one "
                    "bad scene never stops the fleet, and the morning has "
                    "one table.")
    g = ap.add_argument_group("which scenes")
    g.add_argument("--scenes", default="",
                   help="explicit comma-separated scene list")
    g.add_argument("--scenes-file", default="",
                   help="file with one scene name per line; '#' comments "
                        "and blank lines are ignored")
    g.add_argument("--exclude", default="",
                   help="comma-separated scenes to drop from the list")
    g.add_argument("--resume", action="store_true",
                   help="skip any scene whose final gate already passes, so "
                        "an interrupted fleet restarts where it stopped")

    g = ap.add_argument_group("how the fleet behaves")
    g.add_argument("--scene-timeout", type=float,
                   default=DEFAULT_SCENE_TIMEOUT_S,
                   help=f"seconds one scene may take before it is killed and "
                        f"recorded as `timeout` (default "
                        f"{DEFAULT_SCENE_TIMEOUT_S}, 0 = no limit)")
    g.add_argument("--stop-on-fail", action="store_true",
                   help="stop the whole fleet at the first scene that does "
                        "not pass (default: record it and go on)")
    g.add_argument("--dry-run", action="store_true",
                   help="print the plan and run nothing")
    g.add_argument("--scene-continue-on-fail", action="store_true",
                   help="pass --continue-on-fail down to run_scene.py, so a "
                        "scene runs its whole chain instead of stopping at "
                        "its own first bad stage. OFF BY DEFAULT ON PURPOSE: "
                        "a stage that runs on a bad earlier layer produces "
                        "garbage and the gate would refuse it anyway, so the "
                        "extra stages cost time and teach nothing. Turn it "
                        "on when you want the full picture of ONE broken "
                        "scene — every failure it has, in one pass, instead "
                        "of finding them one re-run at a time.")

    g = ap.add_argument_group("passed through to run_scene.py")
    # ⚠ `record` AND `compose` WERE BOTH MISSING FROM THIS LIST until
    # 2026-08-11B — so the driver written to run a hundred scenes
    # overnight could not be asked for the compose phase at all, and the
    # new record phase would have been rejected as an invalid choice.
    # Kept in step with run_scene's own --phase by reading the same table.
    g.add_argument("--phase",
                   choices=tuple(stages.PHASES_ORDER) + ("all",),
                   default="all")
    g.add_argument("--from", dest="from_key", default=None,
                   help="first stage to run, in whichever table names it")
    g.add_argument("--until", dest="until_key", default=None,
                   help="last stage to run, in whichever table names it")
    g.add_argument("--skip", default="",
                   help="comma-separated stages to skip")
    g.add_argument("--no-llm", action="store_true",
                   help="skip every stage that spends model calls; the "
                        "scenes will NOT be complete")
    g.add_argument("--box-thr", type=float, default=None,
                   help="GroundingDINO box threshold for the seg stage")
    return ap


def main():
    a = build_parser().parse_args()

    scenes, dropped, source = build_scene_list(a)
    runid = _runid()
    json_path = paths.OUT / f"fleet_{runid}.json"
    html_path = paths.OUT / f"fleet_{runid}.html"
    timeout_s = a.scene_timeout if a.scene_timeout and a.scene_timeout > 0 else 0

    print(f"[run_fleet] {len(scenes)} scene(s) from {source}"
          + (f", excluding {', '.join(dropped)}" if dropped else ""))
    print(f"[run_fleet] per-scene timeout: "
          f"{_hms(timeout_s) if timeout_s else 'none'}"
          f"   on failure: {'STOP' if a.stop_on_fail else 'go on'}"
          f"   resume: {'yes' if a.resume else 'no'}")
    print(f"[run_fleet] report: {json_path}")
    print(f"[run_fleet]         {html_path}")

    if a.dry_run:
        print("\n[run_fleet] DRY RUN — nothing below is executed, no scene is "
              "touched, and no report is written.")
        for i, sc in enumerate(scenes, 1):
            print(f"\n  {i}/{len(scenes)}  {sc}")
            print(f"    $ {' '.join(str(x) for x in scene_argv(sc, a))}")
            print(f"    log  {paths.scene_dir(sc) / f'run_fleet_{runid}.log'}")
            if a.resume:
                print("    (--resume: would be skipped if its final gate "
                      "already passes)")
        print("\n[run_fleet] dry run complete.")
        return 0

    rows = []
    t_start = time.time()
    stopped_early = None
    for i, sc in enumerate(scenes, 1):
        log_path = paths.scene_dir(sc) / f"run_fleet_{runid}.log"
        row = {"index": i, "scene": sc, "verdict": None, "returncode": None,
               "seconds": 0.0, "started": _iso(), "died_on": None,
               "log": str(log_path), "run_log": None, "gate": None,
               "note": "",
               "argv": [str(x) for x in scene_argv(sc, a)]}

        if a.resume:
            g = gate_lines(sc)
            if g["ok"]:
                print(f"[{i}/{len(scenes)}] {sc}: SKIPPED — its final gate "
                      f"already passes, so it is done (--resume)")
                row.update(verdict="skipped", gate=g, log=None,
                           argv=[], seconds=0.0)
                rows.append(row)
                continue

        print(f"[{i}/{len(scenes)}] {sc}: start  {_iso()}", flush=True)
        t0 = time.time()
        verdict, rc, dt, note = run_one(sc, scene_argv(sc, a), timeout_s,
                                        log_path)
        row["verdict"], row["returncode"], row["seconds"] = verdict, rc, dt
        row["note"] = note
        row["gate"] = gate_lines(sc)
        # died_on() returns the run log path too, and only ever one
        # written since this scene started. by_module() reads its timings
        # out of exactly that file, so the same freshness rule covers
        # both and no stale log can be counted as tonight's.
        if verdict != "pass":
            row["died_on"], row["run_log"] = died_on(sc, t0)
        else:
            _, row["run_log"] = died_on(sc, t0)
        rows.append(row)

        note = f" at {row['died_on']}" if row.get("died_on") else ""
        print(f"[{i}/{len(scenes)}] {sc}: {verdict.upper()}{note}  "
              f"{_hms(dt)}", flush=True)

        if verdict != "pass" and a.stop_on_fail:
            stopped_early = sc
            print(f"[run_fleet] --stop-on-fail: stopping at `{sc}`; "
                  f"{len(scenes) - i} scene(s) not run")
            break

    data = {
        "runid": runid,
        "started": _iso(t_start),
        "ended": _iso(),
        "argv": [str(x) for x in sys.argv],
        "source": source,
        "requested": scenes,
        "excluded": dropped,
        "stopped_early_at": stopped_early,
        "scene_timeout_s": timeout_s,
        "totals": totals(rows),
        "by_module": by_module(rows),
        "scenes": rows,
    }
    write_json(json_path, data)
    write_html(html_path, data)

    t = data["totals"]
    failed = t["failed"]
    print("\n" + "=" * 60)
    print(f"[run_fleet] {t['passed']} passed, {failed} not, "
          f"in {_hms(t['seconds'])}")
    for kind, n in sorted(t["by_verdict"].items()):
        if kind != "pass":
            print(f"              {n:3d}  {kind}")
    print_by_module(data["by_module"])
    print()
    print(f"  {json_path}")
    print(f"  {html_path}")
    print("=" * 60)
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
