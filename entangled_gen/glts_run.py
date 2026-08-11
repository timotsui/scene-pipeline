"""glts_run.py — run the GL-TreeSearch baseline on one of our scenes.

WHY THIS EXISTS. The paper's claim is a comparison: our pipeline
RECONSTRUCTS a real room from a capture, GL-TreeSearch (GLTS) GENERATES a
room from a text prompt. To compare them at all, both must be given THE
SAME INPUT — and the one input they genuinely share is the Marble prompt
that the scene was generated from. That prompt is already on disk in
every scene's bundle. This file takes it, hands it to GLTS, and records
what happened.

WHAT IT IS NOT. This is not a fair fight and the comparison must never
pretend otherwise. GLTS is given a paragraph and nothing else; ours is
given a capture of the room the paragraph describes. GLTS INVENTS a room
size; ours MEASURES one. The scoring in compare_methods.py keeps the two
kinds of number apart for that reason.

HOW IT RUNS. GLTS lives in WSL (Ubuntu-24.04) and drives its own venv,
Blender and the objathor assets. Its launcher already takes the two
things needed for isolation:

    PROJECT_ROOT            where every artifact of this run lands
    BENCHMARK_INSTRUCTIONS  the prompt file to read

so one run per scene cannot touch another's output. This module fills
those in per scene, times each stage, counts the model calls, and writes
a result file next to the output.

ISOLATION AND PARALLELISM. Two GLTS runs are safe on disk — different
PROJECT_ROOTs, nothing shared. They are NOT safe on the GPU: the Blender
compose/decompose steps drive CUDA on a machine that hard-powers-off
under GPU burst (docs/POWER_CRASHES.md). So the Blender phase takes
`paths.gpu_lock`, exactly as our own render stages do, and the layout
phase — which is model calls and CPU search — runs free. That is the
split that makes `--parallel` worth having: the expensive, slow,
model-bound part overlaps, and the part that can kill the machine does
not.

    python glts_run.py --scene living_marble
    python glts_run.py --scene living_marble --end-step 13   # no Blender
    python glts_run.py --scenes living_marble,bedroom_marble --parallel 2
    python glts_run.py --scene living_marble --dry-run
"""
import argparse
import concurrent.futures as futures
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import paths

HERE = Path(__file__).resolve().parent

#: the GLTS checkout, on the Windows side. Overridable from local_paths.json
#: so this is not another machine-specific constant baked into the tree.
GLTS_WIN = Path(paths.CFG.get(
    "treesearchgen",
    r"D:\T\Documents\GeorgiaTech\Summer2026\Research\code\working\TreeSearchGen"))

WSL_DISTRO = "Ubuntu-24.04"

#: GLTS's own stage numbering, from run_test_claude.sh:
#:   0      one LLM call, the cheapest possible smoke test
#:   13     the full layout: room, regions, retrieval, MCTS+PRM. No Blender.
#:   15     Blender compose/decompose -> 16_scene.glb
LAYOUT_END = 13
FULL_END = 15


def to_wsl(p):
    """D:\\a\\b -> /mnt/d/a/b. GLTS runs inside WSL but every path we hand
    it points at the Windows filesystem."""
    p = Path(p)
    drive = p.drive.rstrip(":").lower()
    rest = str(p)[len(p.drive):].replace("\\", "/").lstrip("/")
    return f"/mnt/{drive}/{rest}"


def scene_prompt(scene):
    """The Marble prompt this scene was generated from.

    THIS IS THE SHARED INPUT, and it is the whole basis of the
    comparison. It lives in the bundle folder the scene was harvested
    from, whose path each scene records in bundle_path.txt."""
    bp = paths.scene_dir(scene) / "bundle_path.txt"
    if not bp.exists():
        raise SystemExit(f"[glts] {scene} has no bundle_path.txt, so there "
                         f"is no prompt to give GLTS")
    bundle = Path(bp.read_text(encoding="utf-8").strip())
    for cand in (bundle / "prompt.txt",
                 *sorted(bundle.glob("*prompt.txt"))):
        if cand.exists():
            txt = cand.read_text(encoding="utf-8").strip()
            if txt:
                return " ".join(txt.split()), cand
    raise SystemExit(f"[glts] no prompt.txt under {bundle}")


def out_root(scene):
    """Where this scene's GLTS run lands, INSIDE the GLTS checkout.

    It has to live there because GLTS resolves output_root relative to
    its own working directory. One directory per scene is what keeps two
    runs from touching each other."""
    return GLTS_WIN / f"output_ovm_{scene}"


def result_path(scene):
    return out_root(scene) / "glts_run.json"


def _count_calls(log_text):
    """How many model calls this run made.

    Counted from the bridge's own log lines rather than from anything we
    keep ourselves, so the number describes what GLTS actually did. If
    the bridge's format changes this returns None rather than a wrong
    number — an honest gap beats a confident fiction."""
    # The bridge prints one line per completed call, e.g.
    #   [claude-bridge] ROOM SIZE ok in 5s (attempt 1)
    # A retry prints its own line, so this counts CALLS MADE, which is
    # the cost being compared, not questions asked.
    pats = (r"\[claude-bridge\]", r"\[claude-agent\]", r"claude --model")
    for p in pats:
        n = len(re.findall(p, log_text))
        if n:
            return n, p
    return None, None


#: what a completed run must have left behind, per stop-step. GLTS numbers
#: its outputs, so the last file is the proof the last step ran.
FINAL_ARTIFACT = {0: "1_room_size.json",
                  LAYOUT_END: "13_furniture_layout.json",
                  FULL_END: "16_scene.glb"}


def _completed(root, end_step):
    """Did this run actually FINISH, or did it exit 0 having given up?

    GLTS RETURNS 0 EVEN WHEN THE SCENE FAILED. Observed 2026-08-11: the
    bedroom run stopped at step 11 because the model returned a 26-
    character string for a field GLTS caps at 25, retried three times,
    recorded the failure in failed_instructions.json — and exited 0. The
    launcher is a shell script whose last command succeeded, so the
    return code describes the script, not the scene.

    This is the same hazard the rest of this pipeline was audited for: a
    stage that succeeds and does nothing. Trusting rc here would have put
    a half-finished baseline into a comparison table. So completion is
    judged by what is ON DISK — the numbered artifact the last step
    writes — and by GLTS's own failure log."""
    fail_f = root / "failed_instructions.json"
    failed = []
    if fail_f.exists():
        try:
            failed = json.loads(fail_f.read_text(encoding="utf-8")) or []
        except (ValueError, OSError):
            failed = [{"error": "failed_instructions.json unreadable"}]
    if failed:
        steps = []
        for e in failed:
            for s in (e.get("failed_steps") or []):
                steps.append(f"step {s.get('step_index')} "
                             f"({s.get('step_name')})")
        return False, ("GLTS recorded a failure: "
                       + (", ".join(steps) or "see failed_instructions.json")), failed
    want = FINAL_ARTIFACT.get(end_step)
    if want and not (root / "0" / want).exists():
        return False, (f"no {want} — the run stopped before step "
                       f"{end_step} finished"), failed
    return True, "", failed


def run_one(scene, end_step=FULL_END, start_step=0, dry=False, timeout_s=14400):
    """One scene through GLTS, timed, isolated, recorded."""
    prompt, prompt_src = scene_prompt(scene)
    root = out_root(scene)
    instr = GLTS_WIN / f"instructions_ovm_{scene}.txt"

    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cmd = (f"cd '{to_wsl(GLTS_WIN)}' && "
           f"PROJECT_ROOT='{root.name}' "
           f"BENCHMARK_INSTRUCTIONS='{instr.name}' "
           f"bash run_test_claude.sh {end_step} {start_step}")
    argv = ["wsl.exe", "-d", WSL_DISTRO, "--", "bash", "-lc", cmd]

    if dry:
        print(f"\n[glts] {scene}")
        print(f"  prompt from : {prompt_src}")
        print(f"  prompt      : {prompt[:110]}...")
        print(f"  instructions: {instr}")
        print(f"  output root : {root}")
        print(f"  steps       : {start_step}..{end_step}"
              + ("  (layout only, no Blender)" if end_step < 14 else ""))
        print(f"  $ {' '.join(argv)}")
        return {"scene": scene, "dry_run": True}

    root.mkdir(parents=True, exist_ok=True)
    instr.write_text(prompt + "\n", encoding="utf-8")
    log_path = root / "glts_run.log"

    print(f"[glts] {scene}: steps {start_step}..{end_step} -> {root.name}",
          flush=True)
    t0 = time.time()
    rc, chunks = -1, []
    try:
        # THE BLENDER PHASE TAKES THE GPU LOCK, THE LAYOUT PHASE DOES NOT.
        # Steps 14-15 drive CUDA Blender; everything below is model calls
        # and CPU search. Holding the lock across the whole run would make
        # --parallel pointless, and not holding it at all would put two
        # Blender processes on a card that hard-powers-off under burst.
        needs_gpu = end_step >= 14
        ctx = (paths.gpu_lock(f"GLTS blender {scene}") if needs_gpu
               else _null_ctx())
        with ctx:
            proc = subprocess.Popen(argv, cwd=str(HERE), text=True,
                                    stdout=subprocess.PIPE,
                                    stderr=subprocess.STDOUT,
                                    encoding="utf-8", errors="replace")
            for line in proc.stdout:
                chunks.append(line)
                if len(chunks) % 40 == 0:
                    print(f"[glts] {scene}: {len(chunks)} lines "
                          f"({time.time()-t0:.0f}s)", flush=True)
            rc = proc.wait(timeout=timeout_s)
    except subprocess.TimeoutExpired:
        proc.kill()
        chunks.append(f"\n[glts] KILLED after {timeout_s}s\n")
    except OSError as e:
        chunks.append(f"\n[glts] could not start: {e}\n")
    dt = time.time() - t0

    log = "".join(chunks)
    paths.write_atomic(log_path, log)
    calls, how = _count_calls(log)
    done, why, failed = _completed(root, end_step)

    res = {
        "scene": scene,
        "method": "glts",
        "started": started,
        "ended": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seconds": round(dt, 1),
        "returncode": rc,
        # rc==0 is NOT enough — see _completed(). A run is ok only when it
        # left the artifact its last step writes and logged no failure.
        "ok": rc == 0 and done,
        "completed": done,
        "incomplete_why": why,
        "glts_failed_instructions": failed,
        "steps": [start_step, end_step],
        "model_calls": calls,
        "model_calls_counted_by": how,
        "prompt_source": str(prompt_src),
        "prompt_chars": len(prompt),
        "output_root": str(root),
        "log": str(log_path),
        "artifacts": sorted(p.name for p in (root / "0").glob("*.json"))
        if (root / "0").exists() else [],
    }
    paths.write_atomic(result_path(scene), json.dumps(res, indent=1))
    verdict = ("ok" if res["ok"] else
               f"FAILED rc={rc}" if rc != 0 else
               "INCOMPLETE (exited 0 but did not finish)")
    print(f"[glts] {scene}: {verdict} in {dt/60:.1f} min"
          + (f", {calls} model calls" if calls else "")
          + f" -> {result_path(scene)}", flush=True)
    if not done:
        print(f"[glts] {scene}: {why}", flush=True)
    return res


class _null_ctx:
    def __enter__(self):
        return None

    def __exit__(self, *a):
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scene", default="")
    ap.add_argument("--scenes", default="",
                    help="comma-separated; runs them all")
    ap.add_argument("--end-step", type=int, default=FULL_END,
                    help=f"GLTS stage to stop after (default {FULL_END}; "
                         f"{LAYOUT_END} = layout only, no Blender; "
                         f"0 = one LLM call, the cheapest smoke test)")
    ap.add_argument("--start-step", type=int, default=0)
    ap.add_argument("--parallel", type=int, default=1,
                    help="how many scenes at once. Safe on disk (one output "
                         "root each); the Blender phase still serialises on "
                         "the GPU lock.")
    ap.add_argument("--timeout", type=int, default=14400,
                    help="seconds per scene before it is killed")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    scenes = [s.strip() for s in
              (a.scenes or a.scene).split(",") if s.strip()]
    if not scenes:
        raise SystemExit("give --scene or --scenes")
    for s in scenes:
        if not paths.scene_dir(s).exists():
            raise SystemExit(f"[glts] no scene directory for {s}")

    print(f"[glts] {len(scenes)} scene(s): {', '.join(scenes)}   "
          f"parallel={a.parallel}  steps={a.start_step}..{a.end_step}")
    t0 = time.time()
    if a.parallel <= 1 or len(scenes) == 1:
        res = [run_one(s, a.end_step, a.start_step, a.dry_run, a.timeout)
               for s in scenes]
    else:
        with futures.ThreadPoolExecutor(max_workers=a.parallel) as ex:
            res = list(ex.map(
                lambda s: run_one(s, a.end_step, a.start_step, a.dry_run,
                                  a.timeout), scenes))

    if a.dry_run:
        return 0
    print("\n" + "=" * 60)
    ok = sum(1 for r in res if r.get("ok"))
    print(f"[glts] {ok}/{len(res)} ok in {(time.time()-t0)/60:.1f} min")
    for r in res:
        print(f"  {r['scene']:20s} {'ok  ' if r.get('ok') else 'FAIL'} "
              f"{r.get('seconds', 0)/60:6.1f} min  "
              f"calls={r.get('model_calls')}")
    print("=" * 60)
    return 0 if ok == len(res) else 1


if __name__ == "__main__":
    sys.exit(main())
