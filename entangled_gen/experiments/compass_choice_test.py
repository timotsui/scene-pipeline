"""CHOICE FORM, REBUILT (2026-08-04): four SEPARATE candidate images.

User: "render a few orientations of the isolated bed in test fit and
straight up ask it which one matches the most." The old 8-tile strip died
because it was one unreadable composite (judge built zoom tools, 20-29
turns). This is the same idea in the shape today's findings demand:

  - 4 candidates at 90-degree steps, EACH ITS OWN FULL-SIZE FILE
  - same camera as the reference photo, object isolated + layered,
    compass rose beside it (all the verified stimulus machinery)
  - neutral filenames (candidate_a..d) so nothing leaks which spin is
    which; the mapping is recorded in the record, not shown to the judge
  - one clean folder, one call

BENCHMARK: per the 08-04 bed finding (asset +z = head, ends swapped), the
correct pick is the 180-degree candidate. The record notes the expected
answer AFTER the call, never in the prompt.

  python compass_choice_test.py [--item obj_008]
"""
import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
EG = HERE.parent
sys.path.insert(0, str(EG))
sys.path.insert(0, str(EG / "compose"))
import paths  # noqa: E402
from rotation_check import (  # noqa: E402
    load_scene, load_swap_map, resolve_reference, detection_cam_render_frame,
    render_layered, draw_compass, compass_origin, ref_sheet, yaw_about,
    call_measured, parse_json_obj, MODEL, REF_W,
)
from place import look_at_pose  # noqa: E402

SPINS = [0, 90, 180, 270]
LETTERS = "abcd"

P_CHOICE = """IMAGE 1 -- REFERENCE, a photograph of a REAL room. Left panel: the room
with the "{name}" outlined in yellow; right panel: a close-up of it:
{ref}

IMAGES 2-5 -- four CANDIDATE placements of the "{name}" in a reconstruction
of that room, all rendered from THE SAME CAMERA as the photograph. In each
the object is isolated (walls and floor kept, everything else removed) and
stands at a different orientation. A compass rose is drawn on the floor
beside it, identical in every image:
candidate a: {ca}
candidate b: {cb}
candidate c: {cc}
candidate d: {cd}

The object is a stand-in model that does NOT look like the real one --
compare ORIENTATION only: which way the object faces within the room,
using the rose and the walls.

Which candidate's orientation matches the real "{name}" most?

Reply with ONLY a JSON object, no other text:
{{"pick": "a"|"b"|"c"|"d", "confidence": "high"|"medium"|"low",
  "why": "<one short sentence>"}}
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--item", default="obj_008")
    ap.add_argument("--name", default="bed")
    ap.add_argument("--model", default=MODEL)
    args = ap.parse_args()
    oid = args.item

    sd = paths.scene_dir(args.scene)
    rig = sd / "rig_sp0"
    eye_raw = json.loads((rig / "pano_selfrender_meta.json")
                         .read_text(encoding="utf-8"))["eye_raw"]
    cdir, nodes, by_item, shell, wx, wz, room_c = load_scene(args.scene)
    swap_map = load_swap_map(cdir)

    mem, orig = resolve_reference(oid, nodes, swap_map)
    if not mem:
        raise SystemExit(f"[choice] {oid} has no reference")
    side_p = rig / "crops" / f"{mem['view']}.json"
    if not side_p.exists():
        side_p = sd / "pano_crops" / f"{mem['view']}.json"
    side = json.loads(side_p.read_text(encoding="utf-8"))
    eye, look, fov = detection_cam_render_frame(side, eye_raw)
    pose = look_at_pose(np.asarray(eye, float), np.asarray(look, float),
                        [0, 1, 0])

    tgt = by_item[oid]
    allb = np.vstack([m.bounds for m in tgt])
    lo, hi = allb.min(0), allb.max(0)
    ctr = (lo + hi) / 2
    origin = compass_origin(lo, hi, eye)

    folder = cdir / "rotation_check" / f"{oid}_choice"
    folder.mkdir(parents=True, exist_ok=True)
    ref_p = ref_sheet(sd, mem, oid, folder / "ref.png",
                      compass=(pose, fov, origin))

    t0 = time.time()
    cand = {}
    for letter, deg in zip(LETTERS, SPINS):
        spun = []
        for m in tgt:
            mm = m.copy()
            mm.apply_transform(yaw_about(ctr, deg))
            spun.append(mm)
        img = render_layered(shell, spun, eye, look, fov, REF_W)
        img = draw_compass(img, pose, fov, REF_W, origin)
        p = folder / f"candidate_{letter}.png"
        img.save(p)
        cand[letter] = (deg, p)
    render_s = time.time() - t0

    prompt = P_CHOICE.format(name=args.name, ref=ref_p,
                             ca=cand["a"][1], cb=cand["b"][1],
                             cc=cand["c"][1], cd=cand["d"][1])
    (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
    txt, dt, cost = call_measured(prompt, folder, args.model, 480)
    (folder / "reply.txt").write_text(txt, encoding="utf-8")
    j = parse_json_obj(txt) or {}
    pick = str(j.get("pick", "")).strip().lower()
    picked_deg = cand.get(pick, (None, None))[0]

    expected = 180   # the 08-04 finding: asset +z = head, ends swapped
    rec = {"item": oid, "date": "2026-08-04", "mode": "choice-4-separate",
           "mapping": {k: v[0] for k, v in cand.items()},
           "pick": pick, "picked_degrees": picked_deg,
           "expected_degrees": expected,
           "hit": (picked_deg == expected),
           "why": j.get("why"), "confidence": j.get("confidence"),
           "model_s": round(dt, 1), "turns": cost.get("num_turns"),
           "out_tok": cost.get("out_tok"), "render_s": round(render_s, 1)}
    (cdir / "rotation_check" / f"choice_{oid}.json").write_text(
        json.dumps(rec, indent=2), encoding="utf-8")
    print(f"[choice] pick {pick} = {picked_deg} deg "
          f"(expected {expected}; {'HIT' if rec['hit'] else 'MISS'}) "
          f"| {dt:.0f}s, {cost.get('num_turns')} turns")
    print(f"[choice] why: {j.get('why')}")


if __name__ == "__main__":
    main()
