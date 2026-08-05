"""ROTATION QUESTION, WITH THE REAL ROOM AS REFERENCE (2026-08-04).

The run already on disk (fitloop_rotq_test.py) asked "is this orientation
plausible?" -- a furniture prior, with nothing from the captured room in
front of the model. This run asks "does this MATCH the real object?" by
handing the model the photograph the object was detected in.

No new splat renders: the description stage already saved, per object, the
pano view it was seen in, its 2D box in that view, and a cropped picture of
it (scene_graph.json evidence -> graph/crops/). This reads those.

ROUTING (user's rule, 2026-08-04): an object the original scene did not
have cannot be matched to it, so it falls back to the plausibility question.
That is a lookup, not a judgment -- an object has a reference exactly when
its graph node carries evidence views. In bedroom_marble 28 of the 31
placed objects do; add_r1n9, swap_r1n1_in1 and swap_r3n1_in1 do not.

Same 3 arms and same 2 cameras as the run on disk, so the two are
comparable condition for condition. Claude scores no correctness -- the
user judges the sheets (standing rule).

  out/<scene>/compose/review_shots/rotref_sheet_cam{A,B}_<id>.png
  out/<scene>/compose/review_shots/rotref/   (stimuli, prompts, replies)
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageOps

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from fitloop_rotcam_test import (  # noqa: E402
    SCENE, ITEMS, TILE, GAP, room_c,
    load_scene_meshes, shell_meshes, yaw_about, render_frame,
)
from fitloop_rotq_test import (  # noqa: E402
    MODEL, CTX_RES, CONVENTION, P_DIRECT, P_TILES, P_VERIFY,
    call_claude, parse_json_obj, wrap180, item_cams, ctx_cam,
    project, bbox_corners,
)
EG = HERE.parent
sys.path.insert(0, str(EG))
import paths  # noqa: E402
from place import look_at_pose  # noqa: E402

STRIP = "rotcheck_cam{cam}_{oid}.png"     # experiment-A strips, reused
REF_W = 960                                # pano crops are 960x960


# --------------------------------------------------------------------------
# the reference: what the description stage already saw
# --------------------------------------------------------------------------
def best_evidence(node):
    """The single detection to show: untruncated first, then highest score.
    -> member dict, or None if this object was never seen in the room."""
    mem = (node.get("evidence") or {}).get("members") or []
    if not mem:
        return None
    return sorted(mem, key=lambda m: (bool(m.get("truncated")),
                                      -float(m.get("score") or 0.0)))[0]


def ref_sheet(scene_dir, member, oid, out_path, mirror=True):
    """One image, two panels: the whole view the object was detected in
    (its box outlined), and the saved close-up of the object itself.

    MIRROR (2026-08-04, user caught it): the pano frame is a DEFINED
    left-right mirror of raw -- "Crops are mirror images (like Marble's
    always were; detector-indifferent, lift exact via recorded mapping)",
    PLAN_SELF_PANO_RIG.md. Detection and lifting are indifferent to it, but
    a model asked WHICH WAY something faces is not: unmirrored, every
    left-right answer comes out inverted. So both panels are flipped back
    before they are shown -- pixels first, then the box drawn at mirrored
    coordinates so the label text stays readable.
    """
    view_p = scene_dir / "pano_crops" / f"{member['view']}.webp"
    crop_p = scene_dir / "graph" / "crops" / member["crop"]
    if not view_p.exists() or not crop_p.exists():
        return None
    wide = Image.open(view_p).convert("RGB")
    if wide.size != (REF_W, REF_W):
        wide = wide.resize((REF_W, REF_W))
    if mirror:
        wide = ImageOps.mirror(wide)
    b = member.get("box_2d")
    if b and len(b) == 4:
        x0, x1 = (REF_W - b[2], REF_W - b[0]) if mirror else (b[0], b[2])
        d = ImageDraw.Draw(wide)
        d.rectangle([x0 - 3, b[1] - 3, x1 + 3, b[3] + 3],
                    outline=(255, 220, 0), width=5)
        d.text((x0, max(0, b[1] - 16)), oid, fill=(255, 220, 0))

    close = Image.open(crop_p).convert("RGB")
    if mirror:
        close = ImageOps.mirror(close)    # cut from the same mirrored view
    s = min(REF_W / close.width, REF_W / close.height)
    close = close.resize((max(1, int(close.width * s)),
                          max(1, int(close.height * s))))
    panel = Image.new("RGB", (REF_W, REF_W), (25, 25, 25))
    panel.paste(close, ((REF_W - close.width) // 2,
                        (REF_W - close.height) // 2))

    sheet = Image.new("RGB", (REF_W * 2 + GAP, REF_W + 30), (25, 25, 25))
    sheet.paste(wide, (0, 30))
    sheet.paste(panel, (REF_W + GAP, 30))
    d = ImageDraw.Draw(sheet)
    d.text((8, 9), f"the real room -- view {member['view']}, "
                   f"{oid} outlined", fill=(255, 255, 60))
    d.text((REF_W + GAP + 8, 9), "the real object, close up",
           fill=(255, 255, 60))
    sheet.save(out_path)
    return out_path


# --------------------------------------------------------------------------
# prompts -- the matching versions. Same JSON contract, same convention
# line, so replies parse identically to the run already on disk.
# --------------------------------------------------------------------------
REF_NOTE = (
    "IMPORTANT about the reference: it is a PHOTOGRAPH of the real room, "
    "taken from a different viewpoint than the render, and the object in "
    "the render is a stand-in model that does NOT look like the real one. "
    "Match which WAY the object faces within the room -- use the walls, "
    "window and neighbouring furniture to carry the direction across. Do "
    "not try to match its shape, colour or size."
)

R_DIRECT = """You are correcting the ROTATION of ONE object placed in a 3D room.
The room is a reconstruction of a real room, and you have a photo of it.

IMAGE 1 -- REFERENCE, the real room. Left panel: the view the object was
photographed in, with the object outlined in yellow. Right panel: a close-up
of that same real object:
{ref}
IMAGE 2 -- the object as currently placed in the reconstruction, seen from a
camera inside it:
{item}
IMAGE 3 -- the whole reconstructed room from a high corner. The object is
outlined in yellow and labelled with its id:
{ctx}

The object is "{name}" (id {oid}).

{refnote}

Decide how far the placed object must be turned about its vertical axis so
that it faces the same way as the real object does in the reference.

{convention}

Reply with ONLY a JSON object, no other text:
{{"degrees": <number from -180 to 180>, "confidence": "high"|"medium"|"low",
  "why": "<one short sentence>"}}
"""

R_TILES = """You are correcting the ROTATION of ONE object placed in a 3D room.
The room is a reconstruction of a real room, and you have a photo of it.

IMAGE 1 -- REFERENCE, the real room. Left panel: the view the object was
photographed in, with the object outlined in yellow. Right panel: a close-up
of that same real object:
{ref}
IMAGE 2 -- a strip of 8 tiles, left to right:
{strip}

All 8 tiles show the SAME object in the SAME reconstructed room from the
SAME camera. Tile 1 is the object exactly as it is currently placed. Each
following tile turns the object a further 45 degrees about its vertical
axis: tile 2 = +45, tile 3 = +90, tile 4 = +135, tile 5 = +180, tile 6 =
+225, tile 7 = +270, tile 8 = +315. Nothing else in the room moves.

The object is "{name}" (id {oid}).

{refnote}

Pick the ONE tile in which the object faces the same way as the real object
does in the reference.

Reply with ONLY a JSON object, no other text:
{{"tile": <1-8>, "confidence": "high"|"medium"|"low",
  "why": "<one short sentence>"}}
"""

R_VERIFY = """You are checking a ROTATION correction that was just applied to
ONE object in a reconstruction of a real room.

IMAGE 1 -- REFERENCE, the real room. Left panel: the view the object was
photographed in, with the object outlined in yellow. Right panel: a close-up
of that same real object:
{ref}
IMAGE 2 -- BEFORE, the object as it was placed:
{before}
IMAGE 3 -- AFTER, the same object and camera, turned {applied:+.1f} degrees:
{after}

The object is "{name}" (id {oid}).

{refnote}

Look at the AFTER image. Does the object now face the same way as the real
object does in the reference? If it does not, say how much FURTHER it must
be turned, starting from the AFTER state.

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

    scene_dir = paths.scene_dir(SCENE)
    sdir = paths.compose_dir(SCENE) / "review_shots"
    odir = sdir / "rotref"
    odir.mkdir(parents=True, exist_ok=True)

    graph = json.loads((scene_dir / "scene_graph.json")
                       .read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in graph["nodes"]}
    names = {p["id"]: p["name"] for p in json.loads(
        (paths.compose_dir(SCENE) / "fitted_preview.json")
        .read_text(encoding="utf-8"))["placed"]}

    by_item = load_scene_meshes()
    shell = shell_meshes()
    t_wall0 = time.time()
    rec = {"scene": SCENE, "model": args.model, "date": "2026-08-04",
           "note": "rotation question WITH the detection photo as reference; "
                   "user eyeballs = GT",
           "render_s": 0.0, "runs": []}

    def timed_render(meshes, eye, target, fov, res):
        t0 = time.time()
        img = render_frame(meshes, eye, target, fov, res=res)
        rec["render_s"] += time.time() - t0
        return img

    for oid in items:
        if oid not in by_item:
            print(f"[rotref] {oid} not in fitted preview, skipped")
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

        # ---- ROUTING: was this object ever seen in the real room?
        mem = best_evidence(nodes.get(oid, {}))
        ref_p = None
        if mem:
            ref_p = ref_sheet(scene_dir, mem, oid, odir / f"{oid}_ref.png")
        mode = "match_reference" if ref_p else "plausible_fallback"
        why_fb = ("no graph node" if oid not in nodes else
                  "no detection evidence" if not mem else
                  "reference images missing on disk")
        print(f"[rotref] {oid} {name} -> {mode}"
              + ("" if ref_p else f" ({why_fb})")
              + (f" [view {mem['view']} score {mem.get('score')}]"
                 if mem else ""))

        # ---- room context view (arms 1 and 3 see it)
        ceye, cfov = ctx_cam(ctr)
        cimg = timed_render(shell + others + tgt, ceye, room_c, cfov, CTX_RES)
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

        for cam in cams:
            eye, fov = item_cams(ctr, diag)[cam]
            base = timed_render(shell + others + tgt, eye, ctr, fov, TILE)
            base_p = odir / f"{oid}_cam{cam}_item.png"
            base.save(base_p)
            # claude -p only reads inside its cwd tree -- copy the strip in
            src_strip = sdir / STRIP.format(cam=cam, oid=oid)
            strip_p = odir / STRIP.format(cam=cam, oid=oid)
            if src_strip.exists():
                shutil.copyfile(src_strip, strip_p)

            run = {"item": oid, "name": name, "cam": cam, "mode": mode,
                   "reference": ({"view": mem["view"], "crop": mem["crop"],
                                  "score": mem.get("score"),
                                  "truncated": mem.get("truncated"),
                                  "sheet": ref_p.name} if ref_p else None),
                   "arms": {}}

            def record(arm, degrees, calls, call_s, extra=None):
                run["arms"][arm] = {
                    "degrees": None if degrees is None else wrap180(degrees),
                    "calls": calls, "model_s": round(sum(call_s), 2),
                    "call_s": [round(x, 2) for x in call_s],
                    **(extra or {})}

            # ---------------- arm 1: direct angle (1 call)
            if ref_p:
                p1 = R_DIRECT.format(ref=ref_p, item=base_p, ctx=ctx_p,
                                     name=name, oid=oid, refnote=REF_NOTE,
                                     convention=CONVENTION)
            else:
                p1 = P_DIRECT.format(item=base_p, ctx=ctx_p, name=name,
                                     oid=oid, convention=CONVENTION)
            (odir / f"prompt_{oid}_cam{cam}_arm1.txt").write_text(
                p1, encoding="utf-8")
            deg1, cs1 = None, []
            if not args.renders_only:
                txt, dt = call_claude(p1, odir, args.model)
                (odir / f"raw_{oid}_cam{cam}_arm1.txt").write_text(
                    txt, encoding="utf-8")
                cs1.append(dt)
                j = parse_json_obj(txt) or {}
                if isinstance(j.get("degrees"), (int, float)):
                    deg1 = wrap180(j["degrees"])
                record("arm1_direct", deg1, 1, cs1,
                       {"why": j.get("why"), "confidence": j.get("confidence")})
                print(f"[rotref] {oid} cam{cam} arm1 -> {deg1} ({dt:.1f}s)")

            # ---------------- arm 2: 8-tile multiple choice (1 call)
            deg2, cs2 = None, []
            if not strip_p.exists():
                print(f"[rotref] MISSING strip {strip_p} -- arm2 skipped")
            else:
                if ref_p:
                    p2 = R_TILES.format(ref=ref_p, strip=strip_p, name=name,
                                        oid=oid, refnote=REF_NOTE)
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
                    print(f"[rotref] {oid} cam{cam} arm2 -> tile {t} "
                          f"= {deg2} ({dt:.1f}s)")

            # ---------------- arm 3: propose -> apply -> verify (2 calls)
            deg3, cs3 = None, []
            if not args.renders_only:
                txt, dt = call_claude(p1, odir, args.model)   # same question
                (odir / f"raw_{oid}_cam{cam}_arm3a.txt").write_text(
                    txt, encoding="utf-8")
                cs3.append(dt)
                j = parse_json_obj(txt) or {}
                prop = wrap180(j["degrees"]) if isinstance(
                    j.get("degrees"), (int, float)) else 0.0
                after = timed_render(shell + others + spun(prop),
                                     eye, ctr, fov, TILE)
                after_p = odir / f"{oid}_cam{cam}_arm3_after.png"
                after.save(after_p)
                if ref_p:
                    p3b = R_VERIFY.format(ref=ref_p, before=base_p,
                                          after=after_p, applied=prop,
                                          name=name, oid=oid,
                                          refnote=REF_NOTE,
                                          convention=CONVENTION)
                else:
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
                print(f"[rotref] {oid} cam{cam} arm3 -> {prop:+.0f} then "
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
                        img = timed_render(shell + others + spun(deg),
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
                    (W - 300, 9), f"{oid} {name} / cam{cam} / {mode}",
                    fill=(150, 220, 255))
                sheet.save(sdir / f"rotref_sheet_cam{cam}_{oid}.png")
                print(f"[rotref] sheet -> rotref_sheet_cam{cam}_{oid}.png")

            rec["runs"].append(run)

    rec["wall_s"] = round(time.time() - t_wall0, 1)
    rec["render_s"] = round(rec["render_s"], 1)
    (odir / "rotref_record.json").write_text(
        json.dumps(rec, indent=2), encoding="utf-8")
    print(f"\n[rotref] {len(rec['runs'])} conditions, "
          f"wall {rec['wall_s']}s -> {odir / 'rotref_record.json'}")


if __name__ == "__main__":
    main()
