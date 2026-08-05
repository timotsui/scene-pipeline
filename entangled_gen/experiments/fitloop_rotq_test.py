"""PH2 FIT LOOP design experiment B (2026-08-03): ROTATION-QUESTION
HEAD-TO-HEAD. Three ways of asking a model to fix a placed item's yaw,
run on the same 4 items, in BOTH candidate cameras (experiment A is
unreviewed, so we do not let it gate this one):

  arm1  direct-angle      1 call  -- item view + room context -> "how many degrees?"
  arm2  8-tile choice     1 call  -- the experiment-A strip -> "which tile is right?"
  arm3  propose-verify    2 calls -- direct angle -> apply -> ONE re-render -> "correct now?"

Every arm ends in a single yaw offset (degrees, CCW seen from above).
The USER judges which offsets are right -- Claude never concludes from
images (standing rule). Deliverable per item/camera: a 4-tile review
sheet (as-placed | arm1 | arm2 | arm3) rendered from ONE camera, so the
answer is judged and not the camera.

Timings are the point of the run as much as the answers: each model
call and each render is timed separately and reported per arm. Calls
run SERIALLY so concurrency cannot corrupt the numbers.

Outputs (data folder, not the repo):
  out/<scene>/compose/review_shots/rotq/
      <oid>_cam<X>_item.png  _ctx.png  _arm3_after.png  _arm<N>_final.png
      prompt_<oid>_cam<X>_arm<N>.txt   raw_<...>.txt
      rotq_record.json   rotq_timing.md
  out/<scene>/compose/review_shots/rotq_sheet_cam<X>_<oid>.png
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

import numpy as np
import trimesh
from PIL import Image, ImageDraw

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
# module-level scene load (manifest, graph, shell, room_c) comes with it
from fitloop_rotcam_test import (  # noqa: E402
    SCENE, ITEMS, TILE, GAP, room_c, wx, wz,
    load_scene_meshes, shell_meshes, yaw_about, render_frame,
)
EG = HERE.parent
sys.path.insert(0, str(EG))
import paths  # noqa: E402
from place import look_at_pose  # noqa: E402  (composition/, path set above)

MODEL = "sonnet"            # same model as the compose image judge (pick.py)
CALL_TIMEOUT_S = 480
CTX_RES = 640
SHEET_TILE = 384

# strips from experiment A are reused verbatim as arm2's stimulus
STRIP = "rotcheck_cam{cam}_{oid}.png"


# --------------------------------------------------------------------------
# claude bridge (project pattern: stdin, stripped env, error sniff)
# --------------------------------------------------------------------------
def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)  # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd, model=MODEL):
    """-> (text, seconds). Latency is returned, not logged, so the caller
    owns the timing record."""
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[rotq] claude.exe not on PATH")
    t0 = time.time()
    r = subprocess.run([exe, "-p", "--model", model],
                       input=prompt, capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       env=claude_env(), cwd=str(cwd),
                       timeout=CALL_TIMEOUT_S)
    dt = time.time() - t0
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        raise RuntimeError(f"claude exit {r.returncode}: "
                           f"{err[:400] or out[:400]}")
    low = (out + " " + err).lower()
    for bad in ("invalid_api_key", "authentication_error", "credit balance"):
        if bad in low:
            raise RuntimeError(f"claude API-billing/auth error: {out[:400]}")
    return out, dt


def parse_json_obj(text):
    """First JSON object in the reply, fenced or bare. -> dict or None."""
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except ValueError:
            pass
    i = text.find("{")
    while i >= 0:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[i:])
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
        i = text.find("{", i + 1)
    return None


def wrap180(d):
    """(-180, 180]; a half turn reads as +180, not -180."""
    v = ((float(d) + 180.0) % 360.0) - 180.0
    return 180.0 if v == -180.0 else v


# --------------------------------------------------------------------------
# geometry / cameras
# --------------------------------------------------------------------------
def item_cams(ctr, diag):
    """The two experiment-A cameras for one item -> {cam: (eye, fov)}."""
    eyeA = np.array([0.0, 1.6, 0.0])
    dist = float(np.linalg.norm(ctr - eyeA))
    fovA = float(np.clip(np.degrees(2 * np.arctan2(0.8 * diag, dist)), 30, 75))
    horiz = room_c - np.array([ctr[0], 0, ctr[2]])
    horiz[1] = 0
    n = np.linalg.norm(horiz)
    horiz = horiz / n if n > 1e-6 else np.array([1.0, 0, 0])
    eyeB = ctr + horiz * (1.5 * diag) + np.array([0, 0.9 * diag, 0])
    eyeB[1] = max(eyeB[1], 0.6)
    return {"A": (eyeA, fovA), "B": (eyeB, 45.0)}


def ctx_cam(ctr):
    """High inside-corner overview, from the corner FARTHEST from the item
    so the item is in frame and not against the lens."""
    best, bestd = None, -1.0
    for x in wx:
        for z in wz:
            c = np.array([x, 0.0, z])
            d = np.linalg.norm(c - np.array([ctr[0], 0, ctr[2]]))
            if d > bestd:
                bestd, best = d, c
    inward = room_c - best
    inward[1] = 0
    inward = inward / max(np.linalg.norm(inward), 1e-6)
    eye = best + inward * 0.35 + np.array([0.0, 2.30, 0.0])
    return eye, 75.0


def project(pose, fov_deg, res, pts):
    """World points -> pixel coords in a square res x res render.
    pyrender/OpenGL camera looks down -z in camera space."""
    inv = np.linalg.inv(pose)
    f = 1.0 / np.tan(np.radians(fov_deg) / 2.0)
    uv = []
    for p in pts:
        pc = (inv @ np.append(np.asarray(p, float), 1.0))[:3]
        z = -pc[2]
        if z <= 1e-6:
            continue
        u = ((pc[0] / z) * f + 1.0) / 2.0 * res
        v = (1.0 - (pc[1] / z) * f) / 2.0 * res
        uv.append((u, v))
    return uv


def bbox_corners(lo, hi):
    return [(x, y, z) for x in (lo[0], hi[0])
            for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]


def label(img, text, xy=(8, 5), fill=(255, 255, 60)):
    d = ImageDraw.Draw(img)
    d.rectangle([xy[0] - 8, xy[1] - 5, xy[0] + 22 + 11 * len(text),
                 xy[1] + 21], fill=(0, 0, 0))
    d.text(xy, text, fill=fill)
    return img


# --------------------------------------------------------------------------
# prompts  (NO per-category rules -- ruling 3, PLAN_FIT_LOOP)
# --------------------------------------------------------------------------
CONVENTION = (
    "Angle convention: POSITIVE degrees turn the object COUNTER-CLOCKWISE "
    "when the room is seen from directly above (bird's-eye view). Negative "
    "degrees turn it clockwise. 0 means it is already correct. Any angle is "
    "allowed, not only multiples of 45."
)

P_DIRECT = """You are correcting the ROTATION of ONE object placed in a 3D room.

IMAGE 1 -- the object in place, seen from a camera inside the room:
{item}
IMAGE 2 -- the whole room from a high corner. The object is outlined in
yellow and labelled with its id:
{ctx}

The object is "{name}" (id {oid}).

Read both images. Decide whether this object stands at a sensible
orientation for what it is and for where it sits in this room. If it does
not, say how far it should be turned about its vertical axis.

{convention}

Reply with ONLY a JSON object, no other text:
{{"degrees": <number from -180 to 180>, "confidence": "high"|"medium"|"low",
  "why": "<one short sentence>"}}
"""

P_TILES = """You are correcting the ROTATION of ONE object placed in a 3D room.

IMAGE -- a strip of 8 tiles, left to right:
{strip}

All 8 tiles show the SAME object in the SAME room from the SAME camera.
Tile 1 is the object exactly as it is currently placed. Each following tile
turns the object a further 45 degrees about its vertical axis: tile 2 = +45,
tile 3 = +90, tile 4 = +135, tile 5 = +180, tile 6 = +225, tile 7 = +270,
tile 8 = +315. Nothing else in the room moves.

The object is "{name}" (id {oid}).

Pick the ONE tile in which the object stands at the most sensible
orientation for what it is and for where it sits in this room.

Reply with ONLY a JSON object, no other text:
{{"tile": <1-8>, "confidence": "high"|"medium"|"low",
  "why": "<one short sentence>"}}
"""

P_VERIFY = """You are checking a ROTATION correction that was just applied to
ONE object in a 3D room.

IMAGE 1 -- BEFORE, the object as it was placed:
{before}
IMAGE 2 -- AFTER, the same object and camera, turned {applied:+.1f} degrees:
{after}

The object is "{name}" (id {oid}).

Look at the AFTER image. Does the object now stand at a sensible orientation
for what it is and for where it sits in this room? If it does not, say how
much FURTHER it must be turned, starting from the AFTER state.

{convention}

Reply with ONLY a JSON object, no other text:
{{"ok": true|false, "extra_degrees": <number from -180 to 180>,
  "confidence": "high"|"medium"|"low", "why": "<one short sentence>"}}
"""


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--cams", default="A,B")
    ap.add_argument("--items", default=",".join(ITEMS))
    ap.add_argument("--renders-only", action="store_true",
                    help="build stimuli + prompts, ZERO model calls")
    args = ap.parse_args()
    cams = [c.strip() for c in args.cams.split(",") if c.strip()]
    items = [i.strip() for i in args.items.split(",") if i.strip()]

    sdir = paths.compose_dir(SCENE) / "review_shots"
    odir = sdir / "rotq"
    odir.mkdir(parents=True, exist_ok=True)

    names = {p["id"]: p["name"] for p in json.loads(
        (paths.compose_dir(SCENE) / "fitted_preview.json")
        .read_text(encoding="utf-8"))["placed"]}

    by_item = load_scene_meshes()
    shell = shell_meshes()
    t_wall0 = time.time()
    rec = {"scene": SCENE, "model": args.model, "date": "2026-08-03",
           "note": "PH2 rotation-question head-to-head; user eyeballs = GT",
           "render_s": 0.0, "runs": []}

    def timed_render(meshes, eye, target, fov, res):
        t0 = time.time()
        img = render_frame(meshes, eye, target, fov, res=res)
        dt = time.time() - t0
        rec["render_s"] += dt
        return img, dt

    for oid in items:
        if oid not in by_item:
            print(f"[rotq] {oid} not in fitted preview, skipped")
            continue
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

        # ---- room context view (camera-independent; arms 1 and 3 see it)
        ceye, cfov = ctx_cam(ctr)
        cimg, _ = timed_render(shell + others + tgt, ceye, room_c, cfov,
                               CTX_RES)
        cpose = look_at_pose(np.asarray(ceye, float),
                             np.asarray(room_c, float), [0, 1, 0])
        uv = project(cpose, cfov, CTX_RES, bbox_corners(lo, hi))
        if uv:
            us = [p[0] for p in uv]
            vs = [p[1] for p in uv]
            d = ImageDraw.Draw(cimg)
            box = [min(us) - 6, min(vs) - 6, max(us) + 6, max(vs) + 6]
            d.rectangle(box, outline=(255, 220, 0), width=4)
            d.text((box[0], max(0, box[1] - 14)), oid, fill=(255, 220, 0))
        ctx_p = odir / f"{oid}_ctx.png"
        cimg.save(ctx_p)

        for cam in cams:
            eye, fov = item_cams(ctr, diag)[cam]

            # ---- stimulus: the item as placed, from this camera
            base, _ = timed_render(shell + others + tgt, eye, ctr, fov, TILE)
            base_p = odir / f"{oid}_cam{cam}_item.png"
            base.save(base_p)
            # the experiment-A strip, copied verbatim into odir: claude -p
            # only has read permission inside its cwd tree
            src_strip = sdir / STRIP.format(cam=cam, oid=oid)
            strip_p = odir / STRIP.format(cam=cam, oid=oid)
            if src_strip.exists():
                shutil.copyfile(src_strip, strip_p)

            run = {"item": oid, "name": name, "cam": cam, "arms": {}}

            def record(arm, degrees, calls, call_s, extra=None):
                run["arms"][arm] = {
                    "degrees": None if degrees is None else wrap180(degrees),
                    "calls": calls, "model_s": round(sum(call_s), 2),
                    "call_s": [round(x, 2) for x in call_s],
                    **(extra or {})}

            # ---------------- arm 1: direct angle (1 call)
            p1 = P_DIRECT.format(item=base_p, ctx=ctx_p, name=name, oid=oid,
                                 convention=CONVENTION)
            (odir / f"prompt_{oid}_cam{cam}_arm1.txt").write_text(
                p1, encoding="utf-8")
            deg1, cs1, why1 = None, [], None
            if not args.renders_only:
                txt, dt = call_claude(p1, odir, args.model)
                (odir / f"raw_{oid}_cam{cam}_arm1.txt").write_text(
                    txt, encoding="utf-8")
                cs1.append(dt)
                j = parse_json_obj(txt) or {}
                if isinstance(j.get("degrees"), (int, float)):
                    deg1 = wrap180(j["degrees"])
                why1 = j.get("why")
                record("arm1_direct", deg1, 1, cs1,
                       {"why": why1, "confidence": j.get("confidence")})
                print(f"[rotq] {oid} cam{cam} arm1 -> {deg1} ({dt:.1f}s)")

            # ---------------- arm 2: 8-tile multiple choice (1 call)
            deg2, cs2 = None, []
            if not strip_p.exists():
                print(f"[rotq] MISSING strip {strip_p} -- arm2 skipped")
            else:
                p2 = P_TILES.format(strip=strip_p, name=name, oid=oid)
                (odir / f"prompt_{oid}_cam{cam}_arm2.txt").write_text(
                    p2, encoding="utf-8")
                if not args.renders_only:
                    txt, dt = call_claude(p2, odir, args.model)
                    (odir / f"raw_{oid}_cam{cam}_arm2.txt").write_text(
                        txt, encoding="utf-8")
                    cs2.append(dt)
                    j = parse_json_obj(txt) or {}
                    t = j.get("tile")
                    if isinstance(t, (int, float)) and 1 <= int(t) <= 8:
                        deg2 = wrap180((int(t) - 1) * 45)
                    record("arm2_tiles", deg2, 1, cs2,
                           {"tile": t, "why": j.get("why"),
                            "confidence": j.get("confidence")})
                    print(f"[rotq] {oid} cam{cam} arm2 -> tile {t} "
                          f"= {deg2} ({dt:.1f}s)")

            # ---------------- arm 3: propose -> apply -> verify (2 calls)
            deg3, cs3 = None, []
            if not args.renders_only:
                # call 1 is the same question as arm1 but a SEPARATE call, so
                # arm3's cost and its estimate are both its own
                p3a = P_DIRECT.format(item=base_p, ctx=ctx_p, name=name,
                                      oid=oid, convention=CONVENTION)
                txt, dt = call_claude(p3a, odir, args.model)
                (odir / f"raw_{oid}_cam{cam}_arm3a.txt").write_text(
                    txt, encoding="utf-8")
                cs3.append(dt)
                j = parse_json_obj(txt) or {}
                prop = wrap180(j["degrees"]) if isinstance(
                    j.get("degrees"), (int, float)) else 0.0
                after, _ = timed_render(shell + others + spun(prop),
                                        eye, ctr, fov, TILE)
                after_p = odir / f"{oid}_cam{cam}_arm3_after.png"
                after.save(after_p)
                p3b = P_VERIFY.format(before=base_p, after=after_p,
                                      applied=prop, name=name, oid=oid,
                                      convention=CONVENTION)
                (odir / f"prompt_{oid}_cam{cam}_arm3b.txt").write_text(
                    p3b, encoding="utf-8")
                txt2, dt2 = call_claude(p3b, odir, args.model)
                (odir / f"raw_{oid}_cam{cam}_arm3b.txt").write_text(
                    txt2, encoding="utf-8")
                cs3.append(dt2)
                j2 = parse_json_obj(txt2) or {}
                extra = j2.get("extra_degrees")
                extra = float(extra) if isinstance(
                    extra, (int, float)) and not j2.get("ok") else 0.0
                deg3 = wrap180(prop + extra)
                record("arm3_verify", deg3, 2, cs3,
                       {"proposed": prop, "extra": extra,
                        "ok_first_try": bool(j2.get("ok")),
                        "why": j2.get("why"),
                        "confidence": j2.get("confidence")})
                print(f"[rotq] {oid} cam{cam} arm3 -> {prop:+.0f} then "
                      f"{extra:+.0f} = {deg3} ({dt + dt2:.1f}s)")

            # ---------------- review sheet: one camera, four answers
            if not args.renders_only:
                tiles, labs = [base], ["as placed (0)"]
                for arm, deg in (("arm1", deg1), ("arm2", deg2),
                                 ("arm3", deg3)):
                    if deg is None:
                        img = Image.new("RGB", (TILE, TILE), (60, 30, 30))
                        labs.append(f"{arm}: NO ANSWER")
                    else:
                        img, _ = timed_render(shell + others + spun(deg),
                                              eye, ctr, fov, TILE)
                        img.save(odir / f"{oid}_cam{cam}_{arm}_final.png")
                        labs.append(f"{arm}: {deg:+.0f}")
                    tiles.append(img)
                W = TILE * 4 + GAP * 3
                sheet = Image.new("RGB", (W, TILE + 30), (25, 25, 25))
                for i, (t, lab) in enumerate(zip(tiles, labs)):
                    sheet.paste(t, (i * (TILE + GAP), 30))
                    ImageDraw.Draw(sheet).text(
                        (i * (TILE + GAP) + 8, 9), lab, fill=(255, 255, 60))
                ImageDraw.Draw(sheet).text(
                    (W - 260, 9), f"{oid} {name} / cam{cam}",
                    fill=(150, 220, 255))
                out_sheet = sdir / f"rotq_sheet_cam{cam}_{oid}.png"
                sheet.save(out_sheet)
                print(f"[rotq] sheet -> {out_sheet}")

            rec["runs"].append(run)

    rec["wall_s"] = round(time.time() - t_wall0, 1)
    rec["render_s"] = round(rec["render_s"], 1)
    (odir / "rotq_record.json").write_text(
        json.dumps(rec, indent=2), encoding="utf-8")

    # ---------------- timing table
    agg = {}
    for r in rec["runs"]:
        for arm, a in r["arms"].items():
            g = agg.setdefault(arm, {"calls": 0, "s": 0.0, "n": 0,
                                     "answered": 0})
            g["calls"] += a["calls"]
            g["s"] += a["model_s"]
            g["n"] += 1
            g["answered"] += int(a["degrees"] is not None)
    lines = ["# Rotation-question head-to-head — timing",
             "", f"scene {SCENE} / model {args.model} / serial calls",
             f"wall clock {rec['wall_s']}s, of which rendering "
             f"{rec['render_s']}s", "",
             "| arm | conditions | model calls | total model s | "
             "s per condition | answered |",
             "|---|---|---|---|---|---|"]
    for arm in sorted(agg):
        g = agg[arm]
        lines.append(f"| {arm} | {g['n']} | {g['calls']} | {g['s']:.1f} | "
                     f"{g['s'] / max(g['n'], 1):.1f} | "
                     f"{g['answered']}/{g['n']} |")
    lines += ["", "Angles are the arm's final answer, CCW seen from above.",
              "Correctness is NOT scored here — the user judges the sheets.",
              "", "| item | cam | arm1 | arm2 | arm3 |", "|---|---|---|---|---|"]
    for r in rec["runs"]:
        g = lambda k: (r["arms"].get(k, {}).get("degrees"))  # noqa: E731
        lines.append(f"| {r['item']} {r['name']} | {r['cam']} | "
                     f"{g('arm1_direct')} | {g('arm2_tiles')} | "
                     f"{g('arm3_verify')} |")
    txt = "\n".join(lines) + "\n"
    (odir / "rotq_timing.md").write_text(txt, encoding="utf-8")
    print("\n" + txt)


if __name__ == "__main__":
    main()
