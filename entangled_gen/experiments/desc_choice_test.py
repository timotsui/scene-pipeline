"""ONE-SHOT describe -> choice-vs-description (user 08-04: "just one shot
it", no loops). Two calls per object, both single-look:

  1. DESCRIBE the photo (the verified channel): ref sheet + rose ->
     one sentence + compass facing.
  2. CHOOSE among the 4 cropped candidate renders, NO reference image --
     the description text is the target. Matching stays a model act
     (mapping description->candidate in code would require trusting the
     asset's canonical front, which the user banned).

Uses stimuli already on disk (rotation_check/<oid>_same/). Record ->
rotation_check/desc_choice_<oid>.json.

  python desc_choice_test.py --items obj_008,obj_054,obj_031
"""
import argparse
import json
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).parent
EG = HERE.parent
sys.path.insert(0, str(EG))
sys.path.insert(0, str(EG / "compose"))
import paths  # noqa: E402
from rotation_check import (  # noqa: E402
    call_measured, parse_json_obj, wrap180, MODEL, SPINS, LETTERS,
)

P_DESC = """IMAGE -- a PHOTOGRAPH of a real room. Left panel: the room with the
"{name}" outlined in yellow; right panel: a close-up of it. A compass rose
is drawn on the floor beside the object: arrows N (red), E, S, W:
{ref}

Describe the ORIENTATION of the "{name}" using the compass, in whatever
terms fit the object (user rule: as you see fit):
- if it has a clear FRONT (a face it is used or viewed from), say which
  arrow the front points along;
- if it has no front but a clear LONG AXIS, say which two opposite arrows
  the axis runs between;
- if its orientation is genuinely meaningless (symmetric every way),
  say so.

Reply with ONLY a JSON object, no other text:
{{"desc": "<one or two sentences, whatever orientation language fits>",
  "kind": "front"|"axis"|"none",
  "direction": "<N|NE|E|SE|S|SW|W|NW, or e.g. N-S for an axis, or null>",
  "confidence": "high"|"medium"|"low"}}
"""

P_PICK = """The real "{name}" in a real room has this orientation (described from a
photograph; the compass refers to a rose drawn on the floor beside it):

  "{desc}"  -- {orient_line}.

IMAGES -- four CANDIDATE placements of a stand-in "{name}" in a
reconstruction of that room, each at a different orientation. The SAME
compass rose is drawn beside it in every image:
candidate a: {ca}
candidate b: {cb}
candidate c: {cc}
candidate d: {cd}

The stand-in does not look like the real object -- compare ORIENTATION
only, using the rose and the walls.

Which candidate matches the described orientation best?

Reply with ONLY a JSON object, no other text:
{{"pick": "a"|"b"|"c"|"d", "confidence": "high"|"medium"|"low",
  "why": "<one short sentence>"}}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--items", default="obj_008,obj_054,obj_031")
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()
    items = [i.strip() for i in args.items.split(",") if i.strip()]

    cdir = paths.compose_dir(args.scene)
    rdir = cdir / "rotation_check"
    names = {p["id"]: p["name"] for p in json.loads(
        (cdir / "fitted_preview.json").read_text(encoding="utf-8"))["placed"]}
    mapping = dict(zip(LETTERS, SPINS))

    def stage1(oid):
        folder = rdir / f"{oid}_dc_desc"
        folder.mkdir(exist_ok=True)
        import shutil
        shutil.copyfile(rdir / f"{oid}_ref.png", folder / "ref.png")
        prompt = P_DESC.format(name=names.get(oid, "object"),
                               ref=folder / "ref.png")
        (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
        txt, dt, cost = call_measured(prompt, folder, args.model, 480)
        (folder / "reply.txt").write_text(txt, encoding="utf-8")
        j = parse_json_obj(txt) or {}
        return oid, j, dt, cost

    def stage2(arg):
        oid, j1 = arg
        kind = str(j1.get("kind", "front"))
        if kind == "none":
            # the object itself says orientation is meaningless -> the
            # pipeline answer is "no correction", zero further cost
            return oid, {"pick": "a", "confidence": j1.get("confidence"),
                         "why": "orientation meaningless per description "
                                "-- no correction, stage 2 skipped"}, 0.0, \
                {"skipped": True}
        folder = rdir / f"{oid}_dc_pick"
        folder.mkdir(exist_ok=True)
        import shutil
        for le in LETTERS:
            shutil.copyfile(rdir / f"{oid}_same" / f"candidate_{le}.png",
                            folder / f"candidate_{le}.png")
        d = j1.get("direction")
        orient_line = (f"front points {d}" if kind == "front"
                       else f"no front; long axis runs {d}")
        prompt = P_PICK.format(name=names.get(oid, "object"),
                               desc=j1.get("desc", ""),
                               orient_line=orient_line,
                               ca=folder / "candidate_a.png",
                               cb=folder / "candidate_b.png",
                               cc=folder / "candidate_c.png",
                               cd=folder / "candidate_d.png")
        (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
        txt, dt, cost = call_measured(prompt, folder, args.model, 480)
        (folder / "reply.txt").write_text(txt, encoding="utf-8")
        j = parse_json_obj(txt) or {}
        return oid, j, dt, cost

    t0 = time.time()
    with ThreadPoolExecutor(max_workers=len(items)) as ex:
        s1 = {oid: (j, dt, cost) for oid, j, dt, cost
              in ex.map(stage1, items)}
    with ThreadPoolExecutor(max_workers=len(items)) as ex:
        s2 = {oid: (j, dt, cost) for oid, j, dt, cost
              in ex.map(stage2, [(o, s1[o][0]) for o in items])}

    out = []
    for oid in items:
        j1, dt1, c1 = s1[oid]
        j2, dt2, c2 = s2[oid]
        pick = str(j2.get("pick", "")).strip().lower()
        deg = wrap180(mapping[pick]) if pick in mapping else None
        rec = {"item": oid, "name": names.get(oid, "?"),
               "desc": j1.get("desc"), "kind": j1.get("kind"),
               "direction": j1.get("direction"),
               "desc_conf": j1.get("confidence"),
               "pick": pick, "degrees": deg,
               "pick_conf": j2.get("confidence"), "why": j2.get("why"),
               "s1": {"s": round(dt1, 1), "turns": c1.get("num_turns")},
               "s2": {"s": round(dt2, 1), "turns": c2.get("num_turns")}}
        out.append(rec)
        (rdir / f"desc_choice_{oid}.json").write_text(
            json.dumps(rec, indent=2), encoding="utf-8")
        print(f"[dc] {oid:<10}{rec['name']:<18}{rec['kind']}:{rec['direction']} -> "
              f"pick {pick} = {deg}  "
              f"(desc {dt1:.0f}s/{c1.get('num_turns')}t + "
              f"pick {dt2:.0f}s/{c2.get('num_turns')}t)")
        print(f"     desc: \"{str(j1.get('desc'))[:100]}\"")
        print(f"     why:  \"{str(j2.get('why'))[:100]}\"")
    print(f"\n[dc] wall {time.time()-t0:.0f}s for {len(items)} objects "
          "(both stages)")


if __name__ == "__main__":
    main()
