"""EXPERIMENT 2026-08-05 (user): TOP-DOWN rotation stimulus.

The canon rotation check (compose/rotation_check.py) judges from the ROOM
PERSPECTIVE: a real photograph + 4 candidate renders from that photograph's
own camera. This tries the other view entirely -- judge from ABOVE.

The catch this has to solve: there is no top-down PHOTOGRAPH. The pano rig
sits at eye height. So the "real" side is a top-down render of the SPLAT
(gen_raw.ply) with the ceiling clipped away at render time.

Both sides live in the SAME 3D space (raw ply <-> render frame is
diag(-1,-1,1), a proper rotation), so unlike the photograph path there is
NO mirror to correct -- the bug that inverted every answer on the first
grounded run cannot occur here.

Deliberately NOT cropped: reference and candidates share resolution, fov
and pose, so they correspond pixel for pixel. Only the camera differs from
canon: object still isolated over the shell, still 4 candidates at
0/90/180/270, still neutral names, still one call per object.

FRAME RULE (measured 2026-08-05 -- do not "fix" back to raw):
splat-transform applies diag(-1,-1,1) to a .ply on load, i.e. it works in
the RENDER frame, which is what that frame is named after (manifest note:
"webp/render space = coords * raw_to_render"). Camera AND clip box go in
RENDER coords -- the frame fitted_preview is already in -- so nothing is
converted. Established by fitting 4 clip-box observations against the ply:
perm (0,1,2), signs (-1,-1,1), zero error. Raw coords instead put the eye
2.4 m UNDER the floor on the mirrored side of the room and render bare
floor. Also: shot.py's argparse rejects flag values starting with '-', so
every optional is passed --k=v.

READING THE VERDICTS: they are DELTAS on the CURRENT preview, exactly as
in canon (fit_preview.py: "a 0 verdict on a corrected object means KEEP the
correction"). Objects with rotcheck_applied_deg != 0 already carry a
correction, so 0 is the right answer for them; that field is recorded per
item so the comparison stays honest.

  python topdown_choice_test.py [--scene bedroom_marble] [--items all|ids]
                                [--jobs 8] [--renders-only] [--flip-bed]
"""
import argparse
import hashlib
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).parent
EG = HERE.parent
sys.path.insert(0, str(EG))
sys.path.insert(0, str(EG / "compose"))

import paths                                     # noqa: E402
from rotation_check import (load_scene, render_frame,   # noqa: E402
                            render_object_rgba, project, yaw_about,
                            call_measured, parse_json_obj,
                            SPINS, LETTERS)
import rotation_check as rc                      # noqa: E402
from place import look_at_pose                   # noqa: E402

SHOT = EG / "rendertools" / "shot.py"
MODEL = "sonnet"
RES = 900


P_TOPDOWN = """IMAGE 1 -- REFERENCE, a TOP-DOWN view of a REAL room, looking straight
down from above with the ceiling removed. The "{name}" is the object framed
at the CENTRE of the view:
{ref}

THE OTHER IMAGES -- {n} CANDIDATE placements of the "{name}" in a
reconstruction of that same room, all rendered from THE SAME TOP-DOWN
CAMERA as the reference, at the same scale and framing. In each the object
is isolated (walls and floor kept, everything else removed) and stands at a
different orientation:
{cands}

The candidate is a stand-in model that does NOT look like the real one --
compare ORIENTATION only: which way the object faces within the room, using
the walls and the room layout as reference.

Which candidate's orientation matches the real "{name}" most?

Reply with ONLY a JSON object, no other text:
{{"pick": {letters}, "confidence": "high"|"medium"|"low",
  "why": "<one short sentence>"}}
"""


def vec(a):
    """x,y,z for the CLI; -0.0 normalised away (it reads as a flag)."""
    return ",".join(f"{(v if v != 0 else 0.0):.4f}" for v in a)


def render_layered_up(shell, tgt, eye, look, up, fov, res):
    """render_layered with an EXPLICIT up vector -- the canon helper
    hardwires [0,1,0], degenerate for a straight-down camera."""
    orig = rc.look_at_pose

    def patched(e, t, _u):
        return orig(np.asarray(e, float), np.asarray(t, float), up)
    rc.look_at_pose = patched
    try:
        img = render_frame(shell, eye, look, fov, res=res).convert("RGBA")
        img.alpha_composite(render_object_rgba(tgt, eye, look, fov, res))
    finally:
        rc.look_at_pose = orig
    return img.convert("RGB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--items", default="all")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--jobs", type=int, default=8)
    ap.add_argument("--timeout", type=int, default=480)
    ap.add_argument("--cut", type=float, default=1.8,
                    help="splat clip: drop everything this far above floor")
    ap.add_argument("--margin", type=float, default=1.6,
                    help="frame the object's footprint x this")
    ap.add_argument("--res", type=int, default=RES)
    ap.add_argument("--gpu", default="0")
    ap.add_argument("--renders-only", action="store_true")
    ap.add_argument("--flip-bed", action="store_true",
                    help="pre-spin obj_008 by 180 so the correct answer is "
                         "NOT 'leave it' -- reproduces the original blind "
                         "benchmark condition on already-corrected geometry")
    args = ap.parse_args()

    cdir, nodes, by_item, shell, wx, wz, room_c = load_scene(args.scene)
    man = json.loads(paths.manifest(args.scene).read_text(encoding="utf-8"))
    floor_r = float(man["frame"]["floor_y"]) * -1.0      # render frame, +y up
    fp = json.loads((cdir / "fitted_preview.json")
                    .read_text(encoding="utf-8"))["placed"]
    names = {p["id"]: p["name"] for p in fp}
    uids = {p["id"]: p.get("uid") for p in fp}
    mounts = {p["id"]: p.get("mount") for p in fp}
    applied = {p["id"]: p.get("rotcheck_applied_deg", 0.0) for p in fp}

    # canon verdicts, for the head-to-head column
    canon = {}
    rc_path = cdir / "rotation_check.json"
    if rc_path.exists():
        for run in json.loads(rc_path.read_text(encoding="utf-8")
                              ).get("runs", []):
            canon[run.get("item")] = {"degrees": run.get("degrees"),
                                      "confidence": run.get("confidence")}

    items = ([p["id"] for p in fp] if args.items == "all"
             else [i.strip() for i in args.items.split(",") if i.strip()])

    out = cdir / "topdown_check"
    out.mkdir(exist_ok=True)

    # ---------------- stimuli: one clean folder per call ------------------
    t0 = time.time()
    jobs_list, geo, skipped = [], {}, []
    ylo, yhi = floor_r - 0.25, floor_r + args.cut
    box = (f"{wx[0]-0.3:.3f},{ylo:.3f},{wz[0]-0.3:.3f},"
           f"{wx[1]+0.3:.3f},{yhi:.3f},{wz[1]+0.3:.3f}")

    for oid in items:
        if oid not in by_item:
            skipped.append(oid)
            continue
        tgt = [m.copy() for m in by_item[oid]]
        allb = np.vstack([m.bounds for m in tgt])
        lo, hi = allb.min(0), allb.max(0)
        ctr = (lo + hi) / 2
        if args.flip_bed and oid == "obj_008":
            tgt = [m.copy() for m in tgt]
            for m in tgt:
                m.apply_transform(yaw_about(ctr, 180.0))
        name = names.get(oid, "object")

        # camera clears the object; framed on its footprint
        eye_y = floor_r + max(2.5, (hi[1] - floor_r) + 1.0)
        eye = np.array([ctr[0], eye_y, ctr[2]])
        look = np.array([ctr[0], floor_r, ctr[2]])
        up = np.array([0.0, 0.0, 1.0])
        half = max(hi[0] - lo[0], hi[2] - lo[2]) / 2 * args.margin
        fov = float(np.clip(np.degrees(2 * np.arctan2(half, eye_y - ctr[1])),
                            25, 100))
        pose = look_at_pose(eye, look, up)

        folder = out / f"{oid}_td"
        folder.mkdir(exist_ok=True)
        for f in list(folder.glob("*.png")) + list(folder.glob("*.webp")):
            f.unlink()                       # clean-folder rule (replies stay)

        ref = folder / "reference.webp"
        subprocess.run(
            [sys.executable, str(SHOT), vec(eye), vec(look), f"--up={vec(up)}",
             f"--fov={fov:.3f}", f"--box={box}",
             f"--res={args.res}x{args.res}", f"--ply={paths.ply(args.scene)}",
             f"--gpu={args.gpu}", f"--out={ref}", "--no-open"],
            check=True, stdout=subprocess.DEVNULL)
        Image.open(ref).convert("RGB").save(folder / "reference.png")
        ref.unlink()

        mapping = {}
        for letter, deg in zip(LETTERS, SPINS):
            spun = []
            for m in tgt:
                mm = m.copy()
                mm.apply_transform(yaw_about(ctr, deg))
                spun.append(mm)
            render_layered_up(shell, spun, eye, look, up, fov,
                              args.res).save(folder / f"candidate_{letter}.png")
            mapping[letter] = deg

        cands = "\n".join(f"candidate {le}: {folder / f'candidate_{le}.png'}"
                          for le in mapping)
        prompt = P_TOPDOWN.format(
            ref=folder / "reference.png", name=name, n=len(mapping),
            cands=cands, letters="|".join(f'"{le}"' for le in mapping))
        (folder / "prompt.txt").write_text(prompt, encoding="utf-8")

        # gate image (not part of the stimulus): placed box on the splat
        pts = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
               for z in (lo[2], hi[2])]
        uv = project(pose, fov, args.res, pts)
        chk = Image.open(folder / "reference.png").convert("RGB")
        if uv:
            us, vs = [p[0] for p in uv], [p[1] for p in uv]
            ImageDraw.Draw(chk).rectangle(
                [min(us), min(vs), max(us), max(vs)],
                outline=(255, 220, 0), width=3)
        chk.save(folder / "_selfcheck.png")

        geo[oid] = {"name": name, "uid": uids.get(oid),
                    "mount": mounts.get(oid),
                    "rotcheck_applied_deg": applied.get(oid, 0.0),
                    "mapping": mapping, "fov": round(fov, 2),
                    "eye": [round(float(v), 3) for v in eye],
                    "footprint_m": [round(float(hi[0] - lo[0]), 2),
                                    round(float(hi[2] - lo[2]), 2)]}
        jobs_list.append((oid, folder, prompt))

    render_s = time.time() - t0
    print(f"[td] {len(jobs_list)} stimuli staged, renders {render_s:.1f}s"
          + (f", skipped: {skipped}" if skipped else ""))
    if args.renders_only:
        return

    # ---------------- one wave: every call independent --------------------
    def fire(job):
        oid, folder, prompt = job
        hh = hashlib.md5(prompt.encode("utf-8"))
        for f in sorted(folder.glob("*.png")):
            if f.name != "_selfcheck.png":       # gate art is not stimulus
                hh.update(f.read_bytes())
        raw_p = folder / f"reply_{hh.hexdigest()[:10]}.txt"
        if raw_p.exists():
            text, dt, cost = raw_p.read_text(encoding="utf-8"), 0.0, None
        else:
            try:
                text, dt, cost = call_measured(prompt, folder, args.model,
                                               args.timeout)
                raw_p.write_text(text, encoding="utf-8")
            except Exception as e:              # never a run-killer
                return {"item": oid, "error": str(e)[:200], **geo[oid]}
        obj = parse_json_obj(text) or {}
        pick = (obj.get("pick") or "").strip().lower()[:1]
        deg = geo[oid]["mapping"].get(pick)
        return {"item": oid, "pick": pick or None, "degrees": deg,
                "confidence": obj.get("confidence"), "why": obj.get("why"),
                "model_s": round(dt, 1), "cost": cost, **geo[oid]}

    t1 = time.time()
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        runs = list(ex.map(fire, jobs_list))
    wave_s = time.time() - t1

    for r in runs:
        r["canon_degrees"] = (canon.get(r["item"]) or {}).get("degrees")
        r["canon_confidence"] = (canon.get(r["item"]) or {}).get("confidence")
        r["agrees_with_canon"] = (
            None if r.get("degrees") is None or r["canon_degrees"] is None
            else abs(float(r["degrees"]) - float(r["canon_degrees"])) < 1e-6)

    rec = {"scene": args.scene, "model": args.model,
           "date": time.strftime("%Y-%m-%d"),
           "experiment": "TOP-DOWN 4-candidate choice (user 2026-08-05)",
           "note": ("verdicts are DELTAS on the CURRENT preview; items with "
                    "rotcheck_applied_deg != 0 already carry a correction, "
                    "so 0 is correct for them. flip_bed="
                    + str(args.flip_bed)),
           "render_s": round(render_s, 1), "wave_s": round(wave_s, 1),
           "runs": runs}
    (cdir / "topdown_check.json").write_text(json.dumps(rec, indent=1),
                                             encoding="utf-8")

    ans = [r for r in runs if r.get("degrees") is not None]
    agree = [r for r in ans if r.get("agrees_with_canon")]
    print(f"[td] {len(ans)}/{len(runs)} answered, wave {wave_s:.1f}s")
    print(f"[td] agrees with canon: {len(agree)}/{len(ans)}")
    print(f"[td] wrote {cdir / 'topdown_check.json'}")


if __name__ == "__main__":
    main()
