"""ONE OBJECT, RUN CONCURRENTLY, WITH THE COST ACTUALLY MEASURED (08-04).

Same experiment as fitloop_rotref_test.py -- three ways of asking for a
rotation correction, two cameras, the detection photograph as reference --
narrowed to a single object and run with the calls in parallel, because the
serial version took ~59 minutes of model time for 20 answers and the user
stopped it as not pipeline-applicable.

Two things this adds:

1. CONCURRENCY. The conditions are independent except inside arm 3, whose
   verify call needs its propose call's answer and a render of it. So the
   run is two waves: {arm1, arm2, arm3-propose} x {camA, camB} together,
   then {arm3-verify} x {camA, camB} together. 8 calls in 2 waves.

2. MEASUREMENT, not a story about why it is slow. Every call goes through
   `claude -p --output-format json`, which reports num_turns, duration_api_ms
   and token usage. Last time I explained the latency by guessing and was
   wrong; the per-call turn count is what settles it.

The reference photograph is mirrored back to true left-right by ref_sheet()
(the pano frame is a defined mirror -- see its docstring). That is the fix
this re-run exists to test.

Nothing here is a pipeline stage. Output ->
  out/<scene>/compose/review_shots/rotref_one/
  out/<scene>/compose/review_shots/rotref_one_sheet_cam{A,B}_<oid>.png
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from fitloop_rotcam_test import (  # noqa: E402
    SCENE, TILE, GAP, room_c,
    load_scene_meshes, shell_meshes, yaw_about, render_frame,
)
from fitloop_rotq_test import (  # noqa: E402
    MODEL, CALL_TIMEOUT_S, CTX_RES, CONVENTION, P_DIRECT, P_TILES, P_VERIFY,
    claude_env, parse_json_obj, wrap180, item_cams, ctx_cam,
    project, bbox_corners,
)
from fitloop_rotref_test import (  # noqa: E402
    REF_NOTE, R_DIRECT, R_TILES, R_VERIFY, best_evidence, ref_sheet,
)
EG = HERE.parent
sys.path.insert(0, str(EG))
import paths  # noqa: E402
from place import look_at_pose  # noqa: E402

STRIP = "rotcheck_cam{cam}_{oid}.png"


def call_claude_measured(prompt, cwd, model=MODEL, timeout=CALL_TIMEOUT_S):
    """One call via `claude -p --output-format json`.
    -> (reply_text, wall_seconds, cost_dict). cost_dict carries num_turns and
    token usage, which is what makes 'why is it slow' answerable."""
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[one] claude.exe not on PATH")
    t0 = time.time()
    r = subprocess.run([exe, "-p", "--model", model, "--output-format", "json"],
                       input=prompt, capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       env=claude_env(), cwd=str(cwd), timeout=timeout)
    dt = time.time() - t0
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        raise RuntimeError(f"claude exit {r.returncode}: "
                           f"{(r.stderr or out)[:300]}")
    env = parse_json_obj(out) or {}
    usage = env.get("usage") or {}
    cost = {"num_turns": env.get("num_turns"),
            "duration_api_ms": env.get("duration_api_ms"),
            "in_tok": usage.get("input_tokens"),
            "out_tok": usage.get("output_tokens"),
            "cache_read_tok": usage.get("cache_read_input_tokens"),
            "cost_usd": env.get("total_cost_usd")}
    text = env.get("result") if isinstance(env.get("result"), str) else out
    return text, dt, cost


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--item", default="obj_109")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--cams", default="A,B")
    ap.add_argument("--jobs", type=int, default=6,
                    help="max calls in flight (each spawns a claude.exe)")
    ap.add_argument("--timeout", type=int, default=CALL_TIMEOUT_S,
                    help="per-call timeout, seconds (the 8-tile arm has "
                         "exceeded 480 -- the bed run died on it 08-04)")
    ap.add_argument("--no-mirror-ref", action="store_true",
                    help="show the reference as stored, i.e. mirrored -- "
                         "the bug this run exists to fix")
    args = ap.parse_args()
    cams = [c.strip() for c in args.cams.split(",") if c.strip()]
    oid = args.item

    scene_dir = paths.scene_dir(SCENE)
    sdir = paths.compose_dir(SCENE) / "review_shots"
    odir = sdir / "rotref_one"
    odir.mkdir(parents=True, exist_ok=True)

    graph = json.loads((scene_dir / "scene_graph.json")
                       .read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in graph["nodes"]}
    names = {p["id"]: p["name"] for p in json.loads(
        (paths.compose_dir(SCENE) / "fitted_preview.json")
        .read_text(encoding="utf-8"))["placed"]}

    by_item = load_scene_meshes()
    if oid not in by_item:
        raise SystemExit(f"[one] {oid} not in the fitted preview")
    shell = shell_meshes()
    tgt = by_item[oid]
    others = [m for k, v in by_item.items() if k != oid for m in v]
    allb = np.vstack([m.bounds for m in tgt])
    lo, hi = allb.min(0), allb.max(0)
    ctr = (lo + hi) / 2
    diag = float(np.linalg.norm(hi - lo))
    name = names.get(oid, "object")

    def spun(deg):
        R = yaw_about(ctr, deg)
        out = []
        for m in tgt:
            mm = m.copy()
            mm.apply_transform(R)
            out.append(mm)
        return out

    # ---------------- stimuli (local renders, serial, seconds)
    t_render0 = time.time()
    mem = best_evidence(nodes.get(oid, {}))
    ref_p = ref_sheet(scene_dir, mem, oid, odir / f"{oid}_ref.png",
                      mirror=not args.no_mirror_ref) if mem else None
    mode = "match_reference" if ref_p else "plausible_fallback"
    print(f"[one] {oid} {name} -> {mode}"
          + (f" [view {mem['view']}, mirror "
             f"{'OFF (as stored)' if args.no_mirror_ref else 'ON (corrected)'}]"
             if mem else ""))

    ceye, cfov = ctx_cam(ctr)
    cimg = render_frame(shell + others + tgt, ceye, room_c, cfov, res=CTX_RES)
    cpose = look_at_pose(np.asarray(ceye, float),
                         np.asarray(room_c, float), [0, 1, 0])
    uv = project(cpose, cfov, CTX_RES, bbox_corners(lo, hi))
    if uv:
        us, vs = [p[0] for p in uv], [p[1] for p in uv]
        d = ImageDraw.Draw(cimg)
        box = [min(us) - 6, min(vs) - 6, max(us) + 6, max(vs) + 6]
        d.rectangle(box, outline=(255, 220, 0), width=4)
        d.text((box[0], max(0, box[1] - 14)), oid, fill=(255, 220, 0))
    ctx_p = odir / f"{oid}_ctx.png"
    cimg.save(ctx_p)

    base_of, prompts = {}, {}
    for cam in cams:
        eye, fov = item_cams(ctr, diag)[cam]
        base = render_frame(shell + others + tgt, eye, ctr, fov, res=TILE)
        base_p = odir / f"{oid}_cam{cam}_item.png"
        base.save(base_p)
        base_of[cam] = (base, base_p, eye, fov)
        src_strip = sdir / STRIP.format(cam=cam, oid=oid)
        strip_p = odir / STRIP.format(cam=cam, oid=oid)
        if src_strip.exists():
            shutil.copyfile(src_strip, strip_p)   # claude -p reads only in cwd

        p1 = (R_DIRECT.format(ref=ref_p, item=base_p, ctx=ctx_p, name=name,
                              oid=oid, refnote=REF_NOTE, convention=CONVENTION)
              if ref_p else
              P_DIRECT.format(item=base_p, ctx=ctx_p, name=name, oid=oid,
                              convention=CONVENTION))
        p2 = (R_TILES.format(ref=ref_p, strip=strip_p, name=name, oid=oid,
                             refnote=REF_NOTE)
              if ref_p else
              P_TILES.format(strip=strip_p, name=name, oid=oid))
        prompts[(cam, "arm1")] = p1
        prompts[(cam, "arm2")] = p2
        prompts[(cam, "arm3a")] = p1          # same question, its own call
        for k in ("arm1", "arm2", "arm3a"):
            (odir / f"prompt_{oid}_cam{cam}_{k}.txt").write_text(
                prompts[(cam, k)], encoding="utf-8")
    render_s = time.time() - t_render0

    # ---------------- wave 1: everything that needs nothing from anyone
    calls = [(cam, arm) for cam in cams for arm in ("arm1", "arm2", "arm3a")]
    results = {}

    def fire(key):
        """One call. NEVER raises -- a slow or failed call is recorded as a
        no-answer, not a run-killer (the 08-04 bed run died when one 8-tile
        call hit the timeout inside ex.map). Replies already on disk are
        reused instead of re-paid, which is also the resume path."""
        cam, arm = key
        raw_p = odir / f"raw_{oid}_cam{cam}_{arm}.txt"
        if raw_p.exists() and raw_p.read_text(encoding="utf-8").strip():
            print(f"[one] cam{cam} {arm} reused from disk")
            return (key, raw_p.read_text(encoding="utf-8"), 0.0,
                    {"reused": True}, time.time())
        t0 = time.time()
        try:
            txt, dt, cost = call_claude_measured(
                prompts[key], odir, args.model, timeout=args.timeout)
        except Exception as e:
            dt = time.time() - t0
            print(f"[one] cam{cam} {arm} FAILED after {dt:.1f}s: "
                  f"{type(e).__name__}: {str(e)[:150]}")
            return key, "", dt, {"error": f"{type(e).__name__}"}, t0
        raw_p.write_text(txt, encoding="utf-8")
        print(f"[one] cam{cam} {arm} done in {dt:.1f}s "
              f"({cost.get('num_turns')} turns, {cost.get('out_tok')} out tok)")
        return key, txt, dt, cost, t0

    t_wave1 = time.time()
    print(f"[one] wave 1: {len(calls)} calls, up to {args.jobs} at once")
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for key, txt, dt, cost, t0 in ex.map(fire, calls):
            results[key] = (txt, dt, cost)
    wave1_s = time.time() - t_wave1

    # ---------------- arm 3 verify: needs its own proposal rendered first
    wave2_in = {}
    for cam in cams:
        base, base_p, eye, fov = base_of[cam]
        j = parse_json_obj(results[(cam, "arm3a")][0]) or {}
        prop = wrap180(j["degrees"]) if isinstance(
            j.get("degrees"), (int, float)) else 0.0
        t0 = time.time()
        after = render_frame(shell + others + spun(prop), eye, ctr, fov,
                             res=TILE)
        after_p = odir / f"{oid}_cam{cam}_arm3_after.png"
        after.save(after_p)
        render_s += time.time() - t0
        p3b = (R_VERIFY.format(ref=ref_p, before=base_p, after=after_p,
                               applied=prop, name=name, oid=oid,
                               refnote=REF_NOTE, convention=CONVENTION)
               if ref_p else
               P_VERIFY.format(before=base_p, after=after_p, applied=prop,
                               name=name, oid=oid, convention=CONVENTION))
        (odir / f"prompt_{oid}_cam{cam}_arm3b.txt").write_text(
            p3b, encoding="utf-8")
        prompts[(cam, "arm3b")] = p3b
        wave2_in[cam] = prop

    t_wave2 = time.time()
    keys2 = [(cam, "arm3b") for cam in cams]
    print(f"[one] wave 2: {len(keys2)} calls")
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for key, txt, dt, cost, t0 in ex.map(fire, keys2):
            results[key] = (txt, dt, cost)
    wave2_s = time.time() - t_wave2

    # ---------------- assemble
    rec = {"scene": SCENE, "item": oid, "name": name, "model": args.model,
           "date": "2026-08-04", "mode": mode,
           "reference_mirrored_back": not args.no_mirror_ref,
           "note": "one object, calls run concurrently, per-call turns and "
                   "tokens measured. user eyeballs = GT",
           "reference": ({"view": mem["view"], "crop": mem["crop"],
                          "score": mem.get("score")} if mem else None),
           "jobs": args.jobs, "render_s": round(render_s, 1),
           "wave1_s": round(wave1_s, 1), "wave2_s": round(wave2_s, 1),
           "runs": []}

    for cam in cams:
        base, base_p, eye, fov = base_of[cam]
        run = {"item": oid, "name": name, "cam": cam, "mode": mode,
               "reference": rec["reference"], "arms": {}}

        def put(arm, degrees, keys, extra=None):
            cs = [results[k][1] for k in keys]
            run["arms"][arm] = {
                "degrees": None if degrees is None else wrap180(degrees),
                "calls": len(keys), "model_s": round(sum(cs), 2),
                "call_s": [round(c, 2) for c in cs],
                "cost": [results[k][2] for k in keys], **(extra or {})}

        j1 = parse_json_obj(results[(cam, "arm1")][0]) or {}
        d1 = j1.get("degrees")
        put("arm1_direct", d1 if isinstance(d1, (int, float)) else None,
            [(cam, "arm1")],
            {"why": j1.get("why"), "confidence": j1.get("confidence")})

        j2 = parse_json_obj(results[(cam, "arm2")][0]) or {}
        t = j2.get("tile")
        d2 = (wrap180((int(t) - 1) * 45)
              if isinstance(t, (int, float)) and 1 <= int(t) <= 8 else None)
        put("arm2_tiles", d2, [(cam, "arm2")],
            {"tile": t, "why": j2.get("why"),
             "confidence": j2.get("confidence")})

        j3 = parse_json_obj(results[(cam, "arm3b")][0]) or {}
        prop = wave2_in[cam]
        ex_deg = j3.get("extra_degrees")
        ex_deg = float(ex_deg) if isinstance(ex_deg, (int, float)) \
            and not j3.get("ok") else 0.0
        put("arm3_verify", prop + ex_deg,
            [(cam, "arm3a"), (cam, "arm3b")],
            {"proposed": prop, "extra": ex_deg,
             "ok_first_try": bool(j3.get("ok")), "why": j3.get("why"),
             "confidence": j3.get("confidence")})

        # review sheet: as placed | arm1 | arm2 | arm3, one camera
        tiles, labs = [base], ["as placed (0)"]
        for arm in ("arm1_direct", "arm2_tiles", "arm3_verify"):
            deg = run["arms"][arm]["degrees"]
            short = arm.split("_")[0]
            if deg is None:
                img = Image.new("RGB", (TILE, TILE), (60, 30, 30))
                labs.append(f"{short}: NO ANSWER")
            else:
                t0 = time.time()
                img = render_frame(shell + others + spun(deg), eye, ctr, fov,
                                   res=TILE)
                render_s += time.time() - t0
                img.save(odir / f"{oid}_cam{cam}_{short}_final.png")
                labs.append(f"{short}: {deg:+.0f}")
            tiles.append(img)
        W = TILE * 4 + GAP * 3
        sheet = Image.new("RGB", (W, TILE + 30), (25, 25, 25))
        for i, (tl, lab) in enumerate(zip(tiles, labs)):
            sheet.paste(tl, (i * (TILE + GAP), 30))
            ImageDraw.Draw(sheet).text((i * (TILE + GAP) + 8, 9), lab,
                                       fill=(255, 255, 60))
        ImageDraw.Draw(sheet).text(
            (W - 320, 9),
            f"{oid} {name} / cam{cam} / reference mirrored back",
            fill=(150, 220, 255))
        sheet.save(sdir / f"rotref_one_sheet_cam{cam}_{oid}.png")
        rec["runs"].append(run)

    rec["render_s"] = round(render_s, 1)
    rec["wall_s"] = round(wave1_s + wave2_s, 1)
    # per-item filename -- a second object must not clobber the first's record
    (odir / f"rotref_one_record_{oid}.json").write_text(
        json.dumps(rec, indent=2), encoding="utf-8")

    # ---------------- the cost table this run exists to produce
    lines = ["# One object, concurrent, measured", "",
             f"{oid} {name} / {args.model} / {args.jobs} calls in flight",
             f"wall {rec['wall_s']}s (wave1 {rec['wave1_s']}s + wave2 "
             f"{rec['wave2_s']}s), local rendering {rec['render_s']}s", "",
             "| cam | arm | call s | turns | out tok | cache read tok |",
             "|---|---|---|---|---|---|"]
    tot_calls = 0
    for cam in cams:
        for arm in ("arm1", "arm2", "arm3a", "arm3b"):
            _t, dt, c = results[(cam, arm)]
            tot_calls += 1
            lines.append(f"| {cam} | {arm} | {dt:.1f} | {c.get('num_turns')} "
                         f"| {c.get('out_tok')} | {c.get('cache_read_tok')} |")
    ser = sum(results[k][1] for k in results)
    lines += ["", f"{tot_calls} calls. Serial would have been {ser:.0f}s; "
                  f"concurrent wall was {rec['wall_s']}s "
                  f"({ser / max(rec['wall_s'], 1e-6):.1f}x).",
              "", "| cam | arm1 | arm2 | arm3 |", "|---|---|---|---|"]
    for r in rec["runs"]:
        g = lambda k: r["arms"][k]["degrees"]  # noqa: E731
        lines.append(f"| {r['cam']} | {g('arm1_direct')} | "
                     f"{g('arm2_tiles')} | {g('arm3_verify')} |")
    lines += ["", "Angles are each arm's final answer, CCW seen from above.",
              "Correctness is NOT scored here — the user judges the sheets."]
    txt = "\n".join(lines) + "\n"
    (odir / f"rotref_one_timing_{oid}.md").write_text(txt, encoding="utf-8")
    print("\n" + txt)


if __name__ == "__main__":
    main()
