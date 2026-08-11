"""Canonical out/ layout — one folder per scene (reorganized 2026-07-05).

    out/<scene>/
        gen_raw.ply           the splat (realplayroom's lives in week5, see ply())
        scene_manifest.json   lifted objects (RAW ply space, physical up = frame.up
                              = -y under rot180; see frame.raw_to_render + the
                              2026-07-05C handoff for the frame contract)
        views/                GPU yaw renders + camera sidecars
        seg/                  GroundingDINO+SAM outputs + manifest overlays/plan
        package/              LLM composition package (GUIDE.md, proposals)
        pano_frames/          panorama sweep frames
        panorama.png  envelope.npz  envelope_heatmap.png  live_placement.json

Shared (not per scene): out/report.html, out/cache, out/archive, out/logs,
out/viewer_caps, out/_debug. Every script builds paths through here.
"""
import contextlib as _contextlib
import json as _json
import os as _os
import socket as _socket
import sys as _sys
import time as _time
from pathlib import Path

# CONSOLE ENCODING GUARD (2026-08-10, unattended-run audit): on Windows a
# piped/redirected stdout is cp1252 (or the OEM codepage), and a print()
# containing any character outside it KILLS the stage with
# UnicodeEncodeError — a w5-partial slicevote run died on its final
# status line this way. Every stage imports paths, so one guard here
# covers the whole pipeline: utf-8 out, and errors="replace" so no
# console, however exotic, can crash a print again.
for _s in (_sys.stdout, _sys.stderr):
    try:
        _s.reconfigure(encoding="utf-8", errors="replace")
    except (AttributeError, ValueError, OSError):
        pass          # non-reconfigurable stream (embedded/captured) — fine

HERE = Path(__file__).parent

# Data lives OUTSIDE the repo (out/ is ~15 GB): machine-local roots come from a
# gitignored local_paths.json next to this file (see local_paths.json.example).
# Fallback: repo-local out/ + sibling week5 checkout, the old in-tree layout.
if (HERE / "local_paths.json").exists():
    _cfg = _json.loads((HERE / "local_paths.json").read_text())
    OUT = Path(_cfg["out"])
    W5 = Path(_cfg["week5"])
else:
    _cfg = {}
    OUT = HERE / "out"
    W5 = HERE.parent.parent / "week5" / "splat_to_placement"   # realplayroom data

CFG = _cfg                 # full parsed config — comp_paths.py reads its keys here
REPO_ROOT = HERE.parent    # scene-pipeline/ (launch_*.bat live here)

# local copies of the week5 render tools (2026-07-05) — edit these, not week5
RENDERTOOLS = HERE / "rendertools"
SHOT = RENDERTOOLS / "shot.py"
RENDER03 = RENDERTOOLS / "03_render.py"


def load_r3():
    """Import the numpy renderer (Cam/load_splat) from the local copy."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("render03", RENDER03)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def scene_dir(sc):
    return OUT / sc


def ply(sc):
    if sc == "realplayroom":
        # the week5 real-scan splat (real leg), not a generated one
        return W5 / "data" / "superspl" / "playroom_centered.ply"
    return scene_dir(sc) / "gen_raw.ply"


def views_dir(sc):
    return scene_dir(sc) / "views"


def seg_dir(sc):
    return scene_dir(sc) / "seg"


def pano_crops_dir(sc):
    """Pinhole crops sliced from a bundle equirect (crop_pano.py, week8)."""
    return scene_dir(sc) / "pano_crops"


def seg_pano_dir(sc):
    """seg_views outputs on the pano crops (week8 object-ID path)."""
    return scene_dir(sc) / "seg_pano"


def package_dir(sc):
    return scene_dir(sc) / "package"


def compose_dir(sc):
    """STEP 3 COMPOSE+LOOP outputs (supported_by.json, ...). 2026-07-26."""
    return scene_dir(sc) / "compose"


def manifest(sc):
    return scene_dir(sc) / "scene_manifest.json"


def frame_block(sc):
    """The scene's frame record: legacy sweep manifest (bedroom-era) ->
    frame_bootstrap.json (fresh scenes; same schema since 2026-08-06 —
    intake writes the full block incl. raw_to_render + extents)."""
    import json
    legacy = manifest(sc)
    if legacy.exists():
        return json.loads(legacy.read_text())["frame"]
    boot = scene_dir(sc) / "frame_bootstrap.json"
    if boot.exists():
        return json.loads(boot.read_text())
    raise SystemExit(f"[paths] no frame info for {sc}: run "
                     f"frame_bootstrap.py --scene {sc} (fresh scene), or "
                     f"provide the legacy sweep manifest")


def graph_fingerprint(sc):
    """Content hashes of the two graph slices compose layers consume:
    'geometry' (resolved boxes + names + arch planes) and 'testimony'
    (per-node witness words: description + support_view). Compose
    modules stamp this into their output; the viewer's staleness gate
    compares the stamp against the CURRENT graph, so a graph rewrite
    only stales layers whose real inputs changed. (The old mtime gate
    staled every layer on any graph write — e.g. the additive facing
    field, 08-02C.) Returns None if the graph doesn't exist."""
    import hashlib
    p = scene_dir(sc) / "scene_graph.json"
    if not p.exists():
        return None
    g = _json.loads(p.read_text(encoding="utf-8"))
    geo = sorted(
        [(n["id"], n.get("name"),
          n["geometry"]["aabb_min"], n["geometry"]["aabb_max"])
         for n in g.get("resolved", {}).get("nodes", [])]
        + [(n["id"], "arch", n["geometry"]["plane"]["value_raw"], None)
           for n in g.get("nodes", []) if n["id"].startswith("arch_")])
    tes = sorted(
        (n["id"], (n.get("appearance") or {}).get("description"),
         _json.dumps((n.get("appearance") or {}).get("support_view"),
                     sort_keys=True))
        for n in g.get("judged", {}).get("nodes", []))
    h = lambda obj: hashlib.sha256(   # noqa: E731
        _json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]
    return {"geometry": h(geo), "testimony": h(tes)}


def envelope_npz(sc):
    return scene_dir(sc) / "envelope.npz"


def envelope_heatmap(sc):
    return scene_dir(sc) / "envelope_heatmap.png"


def live_placement(sc):
    return scene_dir(sc) / "live_placement.json"


def panorama(sc):
    return scene_dir(sc) / "panorama.png"


def pano_frames(sc):
    return scene_dir(sc) / "pano_frames"


def spots(sc):
    return scene_dir(sc) / "spots.png"


def write_atomic(path, text, encoding="utf-8"):
    """Write a file so that a crash can never leave it half-written.

    WHY THIS EXISTS (2026-08-11, unattended-run audit). `scene_graph.json`
    is 1.5 MB and holds the WHOLE scene — record, judged, resolved, vote,
    voted, settled, shown. Four stages rewrote it with a bare
    `write_text`, which truncates the file to zero and then streams the
    new content back. This machine hard-powers-off under GPU burst
    (docs/POWER_CRASHES.md), and two of those four stages run right after
    a GPU stage. A cut in that window leaves a truncated graph, and the
    graph is NOT a layer that can be re-derived: detection, lifting,
    description and edges all sit upstream of the chain and would every
    one of them have to be run again. Over a hundred unattended scenes
    that stops being unlucky and starts being a matter of time.

    Write to a temporary file beside the target, flush it to the disk,
    then rename. On Windows and on POSIX alike `Path.replace` is atomic
    within a filesystem, so a reader sees either the whole old file or
    the whole new one and never a mixture. `record_vote_doubts` already
    did exactly this; it is now the one way every stage writes.

    The temp file is left in place if the write itself fails, so there is
    something to look at, and it never overwrites the good file.

    LINE ENDINGS ARE DELIBERATELY LEFT ALONE. `newline` is not pinned, so
    this writes exactly the bytes `Path.write_text` wrote before — CRLF on
    this machine. Pinning "\n" here would be tidier in the abstract and
    would rewrite every 1.5 MB scene graph on disk the first time a stage
    touched it, turning a one-line edit into a whole-file diff on all 100
    scenes. Atomicity was the problem; formatting was not."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding=encoding) as f:
        f.write(text)
        f.flush()
        _os.fsync(f.fileno())          # the bytes are on the disk, not in a cache
    tmp.replace(path)
    return path


# ===================== LOCKS ==========================================
# Two locks, one mechanism. `gpu_lock` keeps two renders off the card at
# the same time; `scene_lock` keeps two processes out of the same scene
# folder. Both are FILE locks, because the things they arbitrate happen
# in separate OS processes and a threading.Lock cannot see across one.

_LOCK_POLL_S = 0.5          # how often a waiter looks again
_LOCK_UNREADABLE_GRACE_S = 30.0   # see _read_holder


def _pid_alive(pid):
    """Is this pid a process that exists right now?

    Deliberately NOT os.kill(pid, 0): on Windows os.kill with a signal
    that is not a console-control event calls TerminateProcess, so the
    obvious portable idiom would KILL the very process we are asking
    about. On Windows we open a query handle instead, and treat
    "access denied" as alive — the process exists, it just belongs to
    somebody else."""
    if pid is None:
        return False
    if _os.name == "nt":
        import ctypes
        from ctypes import wintypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        h = k32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False,
                            int(pid))
        if not h:
            return ctypes.get_last_error() == 5      # ERROR_ACCESS_DENIED
        try:
            code = wintypes.DWORD()
            if not k32.GetExitCodeProcess(h, ctypes.byref(code)):
                return True          # can't tell — assume alive, don't break
            return code.value == STILL_ACTIVE
        finally:
            k32.CloseHandle(h)
    try:
        _os.kill(int(pid), 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True                  # someone else's process, but it exists
    return True


def _read_holder(lock_path):
    """Who holds this lock file, as a dict, or None if it has gone away.

    A holder that has created the file but not yet written it looks the
    same as a corrupt one, so an unreadable file is reported with
    pid None and the file's own mtime, and the caller only breaks it
    once it has been unreadable for _LOCK_UNREADABLE_GRACE_S. That
    window is milliseconds in the normal case."""
    try:
        raw = Path(lock_path).read_text(encoding="utf-8")
    except FileNotFoundError:
        return None
    except OSError:
        raw = ""
    try:
        d = _json.loads(raw)
        if isinstance(d, dict) and "pid" in d:
            return d
    except ValueError:
        pass
    try:
        mt = Path(lock_path).stat().st_mtime
    except OSError:
        return None
    return {"pid": None, "since": mt, "what": "(unwritten or corrupt)",
            "host": None, "unreadable": True}


def _is_stale(holder, stale_after):
    """Reasons a lock file may be broken, and the reason it is not.

    A power cut is the case this whole function exists for: the machine
    goes off mid-render (docs/POWER_CRASHES.md), the lock file survives
    on disk, and its owner does not. If a stale lock could only be
    cleared by a timeout, the next run would sit and wait for that
    timeout, over and over, and one crash at 01:00 would cost the rest
    of the night. So the FIRST test is whether the pid is still a live
    process, which after a reboot is answered "no" immediately.

    The age timeout is the backstop for the cases the pid test cannot
    answer honestly: a pid that has been recycled by a new process
    (rare, but it makes a dead holder look alive), and a lock written by
    a different machine, where the pid means nothing at all. It is set
    generously on purpose — a legitimate render can take minutes and
    node_views allows its renderer 7200 s — because breaking a LIVE
    holder's lock is the worse mistake: it puts two renders on the card
    at once, which is the exact thing being prevented."""
    if holder is None:
        return None
    now = _time.time()
    age = now - float(holder.get("since") or now)
    if holder.get("unreadable"):
        if age > _LOCK_UNREADABLE_GRACE_S:
            return f"lock file unreadable for {age:.0f}s"
        return None
    host = holder.get("host")
    if host and host != _socket.gethostname():
        if age > stale_after:
            return (f"held by another machine ({host}) for {age:.0f}s, "
                    f"past the {stale_after:.0f}s timeout")
        return None
    if not _pid_alive(holder.get("pid")):
        return f"holder pid {holder.get('pid')} is gone"
    if age > stale_after:
        return (f"held by live pid {holder.get('pid')} for {age:.0f}s, "
                f"past the {stale_after:.0f}s timeout")
    return None


def _break_lock(lock_path, holder, why, tag):
    """Delete a lock we have judged stale, loudly, and only if it is
    still the same lock we judged. Re-reading first closes most of the
    race where the real holder released and somebody else acquired
    between our look and our delete; the remainder is one render
    overlapping once, i.e. exactly today's behaviour with no lock."""
    fresh = _read_holder(lock_path)
    if fresh is None:
        return
    if (fresh.get("pid") != holder.get("pid")
            or fresh.get("since") != holder.get("since")):
        return                       # somebody else's lock now — leave it
    print(f"[{tag}] BREAKING A STALE LOCK: {why} "
          f"(was: {holder.get('what')!r}, since "
          f"{_time.strftime('%H:%M:%S', _time.localtime(float(holder.get('since') or 0)))})",
          flush=True)
    try:
        _os.unlink(lock_path)
    except OSError:
        pass


def _try_take(lock_path, what):
    """Create the lock file, or return the current holder.

    O_CREAT | O_EXCL is the whole mechanism: the filesystem decides who
    wins, and it decides once, so two processes cannot both believe they
    hold it. Everything else in here is bookkeeping for the waiter."""
    Path(lock_path).parent.mkdir(parents=True, exist_ok=True)
    try:
        fd = _os.open(lock_path,
                      _os.O_CREAT | _os.O_EXCL | _os.O_WRONLY, 0o644)
    except FileExistsError:
        return _read_holder(lock_path)
    with _os.fdopen(fd, "w", encoding="utf-8") as f:
        f.write(_json.dumps({"pid": _os.getpid(),
                             "host": _socket.gethostname(),
                             "since": _time.time(), "what": what}))
        f.flush()
        _os.fsync(f.fileno())
    return None


@_contextlib.contextmanager
def gpu_lock(what="gpu work", stale_after=7200.0):
    """Hold this while a subprocess is rendering, so only one render at
    a time touches the graphics card.

        with paths.gpu_lock(f"{scene} {nid} vote cards"):
            subprocess.run(wsl_render_cmd, ...)

    WHY THIS EXISTS (2026-08-11, unattended-run audit). This machine
    hard-powers-off under GPU burst — read docs/POWER_CRASHES.md. The
    load is nearly idle on average and spikes to ~140 W for a second at
    a time, and it is the spikes that kill it. Nothing in this repo
    arbitrated the card: judge_multiplicity runs eight worker threads
    and since v2.4 builds each stimulus inside the worker, so ONE scene
    can put eight rasterisations on the card at once, and two scenes
    running together double that again. The renderer's own
    `time.sleep(1.0)` (analyzer/render_targets_wsl.py) paces one process
    and can do nothing about the others. This lock makes those bursts
    queue instead of add up.

    It is a file lock, at a FIXED path under the shared out/ root
    (out/gpu.lock), because the contenders are separate OS processes and
    every scene must contend for the same card. The standing rule is
    that a stage writes only inside its own scene folder; this is the
    one deliberate exception, and it is deliberate because a per-scene
    lock would arbitrate nothing — the GPU is one piece of hardware
    shared by every scene on the machine.

    A stale lock must never stall the night, so see _is_stale: a dead
    holder is detected by its pid, not by waiting out a timeout.

    ESCAPE HATCH: set SCENE_PIPELINE_NO_GPU_LOCK=1 and this becomes a
    no-op, for anyone debugging who wants their renders to overlap.

    Waiting is quiet unless it actually happens: one line naming the
    holder when a process has to queue, and nothing at all when it does
    not."""
    if _os.environ.get("SCENE_PIPELINE_NO_GPU_LOCK"):
        yield
        return
    with _file_lock(OUT / "gpu.lock", what, stale_after, "gpulock",
                    wait=True):
        yield


@_contextlib.contextmanager
def scene_lock(sc, what="scene run", stale_after=7200.0):
    """Hold this for a whole scene run, so only one process writes a
    scene's files.

        with paths.scene_lock(scene, "run_scene full"):
            ...the entire scene...

    MEANT TO BE USED in run_scene.py, wrapped around the whole scene (it
    is not wired into the stages themselves — the point is one writer
    per scene, not one writer per stage).

    WHY THIS EXISTS (2026-08-11, unattended-run audit). `write_atomic`
    makes each write of the 1.5 MB scene_graph.json all-or-nothing, but
    it does nothing about a LOST UPDATE. Two processes read the same
    graph, each edits its own layer, each renames its copy over the
    other, and the second one silently wins — and the checkpoint still
    passes, because it checks that the file is present and recent, not
    who wrote it. The layer the first process produced is simply gone,
    with nothing on disk to say so.

    Unlike gpu_lock this FAILS FAST rather than queueing. A second run
    of the same scene is an operator mistake, not a queue: waiting would
    turn the mistake into a mysterious stall, and running both is what
    loses the update. The error names the other pid so it can be looked
    at or killed.

    The lock file lives inside the scene's own folder
    (out/<scene>/.scene.lock), which keeps the per-scene isolation rule
    intact. Stale locks are handled exactly as in gpu_lock: a holder
    killed by a power cut leaves a dead pid, which the next run detects
    and breaks immediately instead of refusing to start."""
    with _file_lock(scene_dir(sc) / ".scene.lock", what, stale_after,
                    f"scenelock:{sc}", wait=False):
        yield


@_contextlib.contextmanager
def _file_lock(lock_path, what, stale_after, tag, wait):
    """The shared body of gpu_lock and scene_lock. `wait` picks between
    queueing politely and refusing outright. Release is in a finally, so
    an exception inside the block still gives the lock back."""
    lock_path = Path(lock_path)
    announced = False
    while True:
        holder = _try_take(lock_path, what)
        if holder is None:
            break
        why = _is_stale(holder, stale_after)
        if why:
            _break_lock(lock_path, holder, why, tag)
            continue
        if not wait:
            raise SystemExit(
                f"[{tag}] REFUSING TO START: {lock_path.name} is held by "
                f"pid {holder.get('pid')} on {holder.get('host')} "
                f"({holder.get('what')!r}). Two processes writing one "
                f"scene lose each other's edits. Wait for that run, or "
                f"kill pid {holder.get('pid')} and delete {lock_path}.")
        if not announced:
            # ASCII on purpose: this line goes to a piped log under a
            # non-utf-8 console codepage more often than not.
            print(f"[{tag}] waiting for {lock_path.name} - held by pid "
                  f"{holder.get('pid')} ({holder.get('what')!r})",
                  flush=True)
            announced = True
        _time.sleep(_LOCK_POLL_S)
    try:
        yield
    finally:
        try:
            _os.unlink(lock_path)
        except OSError:
            pass


def gen_scenes():
    """Scenes with a generated splat on disk (excludes realplayroom)."""
    return sorted(d.name for d in OUT.iterdir()
                  if d.is_dir() and (d / "gen_raw.ply").exists())


def all_scenes():
    """Every scene folder (has a manifest or a splat)."""
    return sorted(d.name for d in OUT.iterdir() if d.is_dir()
                  and ((d / "gen_raw.ply").exists() or (d / "scene_manifest.json").exists()))
