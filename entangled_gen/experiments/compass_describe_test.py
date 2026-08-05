"""DEBUG PROBE: describe orientation per image, INDEPENDENTLY (2026-08-04).

User: "ask the agent to describe the orientation of the object in each of
the images using the compass" -- and only that. Two separate calls, one
image each, in separate clean folders, so the reference reading cannot
anchor the render reading (the two-step single-call form demonstrably
leaked: 'matching the reference layout'). No turn is asked anywhere; the
implied turn is computed afterwards and printed for comparison.

Uses the stimuli already on disk (rose drawn beside the object):
  rotation_check/<oid>_ref.png          -- the photograph
  rotation_check/<oid>_same/same.png    -- the isolated same-camera render

  python compass_describe_test.py [--item obj_008]
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor

HERE = Path(__file__).parent
EG = HERE.parent
sys.path.insert(0, str(EG))
sys.path.insert(0, str(EG / "compose"))
import paths  # noqa: E402
from rotation_check import (  # noqa: E402
    call_measured, parse_json_obj, implied_degrees, MODEL,
)

P_MIN = """IMAGE:
{img}

A compass rose is drawn on the floor in the image: arrows N (red), E, S, W.

Describe the orientation of the "{name}" in the image, using the compass.

Reply with ONLY a JSON object, no other text:
{{"desc": "<your description>",
  "faces": "N"|"NE"|"E"|"SE"|"S"|"SW"|"W"|"NW",
  "confidence": "high"|"medium"|"low"}}
"""

P_PAIRED = """IMAGE 1:
{ref}
IMAGE 2:
{same}

Both images are taken from the SAME camera angle. IMAGE 1 is a photograph
of a room. IMAGE 2 shows a MODIFIED version of the scene, with the "{name}"
isolated -- everything else removed, walls and floor kept.

A compass rose is drawn on the floor in both images: arrows N (red), E, S,
W. It is the same rose in the same spot.

Describe the orientation of the "{name}" in each image, using the compass.

Reply with ONLY a JSON object, no other text:
{{"image1_desc": "<your description>",
  "image1_faces": "N"|"NE"|"E"|"SE"|"S"|"SW"|"W"|"NW",
  "image2_desc": "<your description>",
  "image2_faces": "N"|"NE"|"E"|"SE"|"S"|"SW"|"W"|"NW",
  "confidence": "high"|"medium"|"low"}}
"""

P_ONE = """IMAGE -- {what}:
{img}

The object of interest is "{name}"{outline}. A compass rose is drawn on
the floor beside it: four arrows labelled N (tinted red), E, S, W.

Describe the object's ORIENTATION using that compass. Name the visible
feature that tells you where its FRONT is (headboard, seat opening,
drawers, doors, back panel...), say where that feature sits, and conclude
which arrow the front points along (nearest of N/NE/E/SE/S/SW/W/NW).

Reply with ONLY a JSON object, no other text:
{{"desc": "<one or two sentences: the feature and how the object sits>",
  "faces": "N"|"NE"|"E"|"SE"|"S"|"SW"|"W"|"NW",
  "confidence": "high"|"medium"|"low"}}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--item", default="obj_008")
    ap.add_argument("--name", default="bed")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--minimal", action="store_true",
                    help="the bare ask (user 08-04): 'describe the "
                         "orientation of the object in the image using "
                         "the compass' -- no feature coaching, no panel "
                         "explanations")
    ap.add_argument("--paired", action="store_true",
                    help="user 08-04: ONE call, both images, 'same angle, "
                         "IMAGE 2 = the object isolated in a modified "
                         "scene'; describe each with the compass")
    args = ap.parse_args()
    oid = args.item

    rdir = paths.compose_dir(args.scene) / "rotation_check"
    src = {
        "ref": (rdir / f"{oid}_ref.png",
                "a PHOTOGRAPH of a real room. Left panel: the room with "
                "the object outlined in yellow; right panel: a close-up "
                "of it",
                ", outlined in yellow in the left panel"),
        "render": (rdir / f"{oid}_same" / "same.png",
                   "a RENDERED reconstruction of a room. Only the object "
                   "of interest is placed; walls and floor are kept, "
                   "everything else is removed",
                   ""),
    }
    if args.paired:
        folder = rdir / f"{oid}_describe_paired"
        folder.mkdir(exist_ok=True)
        ref_l = folder / "ref.png"
        same_l = folder / "same.png"
        shutil.copyfile(src["ref"][0], ref_l)
        shutil.copyfile(src["render"][0], same_l)
        prompt = P_PAIRED.format(ref=ref_l, same=same_l, name=args.name)
        (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
        txt, dt, cost = call_measured(prompt, folder, args.model, 480)
        (folder / "reply.txt").write_text(txt, encoding="utf-8")
        j = parse_json_obj(txt) or {}
        f1, f2 = j.get("image1_faces"), j.get("image2_faces")
        imp = implied_degrees(f2, f1)
        print(f"[desc] paired call ({dt:.0f}s, {cost.get('num_turns')} "
              "turns)")
        print(f"  photo    -> {f1}: \"{j.get('image1_desc')}\"")
        print(f"  modified -> {f2}: \"{j.get('image2_desc')}\"")
        print(f"  implied turn (modified -> photo): {imp} deg "
              f"(yaw_about units); confidence {j.get('confidence')}")
        (rdir / f"describe_{oid}_paired.json").write_text(json.dumps(
            {"item": oid, "date": "2026-08-04", "mode": "paired",
             "image1": {"faces": f1, "desc": j.get("image1_desc")},
             "image2": {"faces": f2, "desc": j.get("image2_desc")},
             "confidence": j.get("confidence"), "model_s": round(dt, 1),
             "turns": cost.get("num_turns"), "implied_turn_deg": imp},
            indent=2), encoding="utf-8")
        return

    jobs = []
    for tag, (img_p, what, outline) in src.items():
        if not img_p.exists():
            raise SystemExit(f"[desc] missing stimulus {img_p}")
        suffix = "min" if args.minimal else ""
        folder = rdir / f"{oid}_describe_{tag}{suffix}"
        folder.mkdir(exist_ok=True)
        local = folder / img_p.name
        shutil.copyfile(img_p, local)
        if args.minimal:
            prompt = P_MIN.format(img=local, name=args.name)
        else:
            prompt = P_ONE.format(what=what, img=local, name=args.name,
                                  outline=outline)
        (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
        jobs.append((tag, folder, prompt))

    def fire(job):
        tag, folder, prompt = job
        txt, dt, cost = call_measured(prompt, folder, args.model, 480)
        (folder / "reply.txt").write_text(txt, encoding="utf-8")
        return tag, txt, dt, cost

    t0 = time.time()
    out = {}
    with ThreadPoolExecutor(max_workers=2) as ex:
        for tag, txt, dt, cost in ex.map(fire, jobs):
            j = parse_json_obj(txt) or {}
            out[tag] = {"faces": j.get("faces"), "desc": j.get("desc"),
                        "confidence": j.get("confidence"),
                        "model_s": round(dt, 1),
                        "turns": cost.get("num_turns")}
            print(f"[desc] {tag:<7} -> faces {j.get('faces')} "
                  f"({dt:.0f}s, {cost.get('num_turns')} turns)")
            print(f"        \"{j.get('desc')}\"")

    imp = implied_degrees(out.get("render", {}).get("faces"),
                          out.get("ref", {}).get("faces"))
    rec = {"item": oid, "date": "2026-08-04",
           "note": "independent per-image describes, no turn asked, no "
                   "anchoring possible; implied turn computed afterwards",
           "wall_s": round(time.time() - t0, 1),
           "ref": out.get("ref"), "render": out.get("render"),
           "implied_turn_deg": imp}
    (rdir / f"describe_{oid}{"_min" if args.minimal else ""}.json").write_text(
        json.dumps(rec, indent=2), encoding="utf-8")
    print(f"\n[desc] implied turn (render -> ref): {imp} deg in yaw_about "
          f"units; wall {rec['wall_s']}s -> describe_{oid}.json")


if __name__ == "__main__":
    main()
