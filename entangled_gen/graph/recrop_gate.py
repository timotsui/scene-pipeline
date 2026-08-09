"""RE-CROP GATE — which nodes need a new tile, and why.

USER RULING 2026-08-09. A blanket re-crop pass is NOT wanted: on the
comparison sheet most re-cuts came out near-identical to the crop
already stored, so redoing them buys nothing and risks a tighter frame
than we want. A re-crop is a TARGETED REPAIR. This module decides who
needs one; it does not perform one.

NOTHING IS RENDERED anywhere in this idea. A "re-crop" is the same
photograph cut to a different rectangle — the one you get by projecting
the node's CURRENT box (graph layer `grouped`: after J8's ship rulings,
J8s' cuts and J1's merges) into the photo the crop came from.

WHO THIS MATTERS FOR. graph/crops/ feeds J1 (same object or part),
J3 (names), J4/J6 (flagged cases), J5 (floaters), J6 (which WRITES the
description), J9 (same product and the size to buy) and
compose/pick.py (which model to actually buy, on look and feel). So a
node showing the wrong photo is not one bad verdict downstream — it is
named, described, matched and bought on evidence about something else.
J8 and J8s are not affected; they work from renders.

THE THREE CONDITIONS (a node fires if ANY holds)

  1  BORROWED   the crops are not this node's own. Today that means a
     split piece: materialize gives it the parent's members wholesale,
     so a members-walk cannot tell — the test is PROVENANCE, the marker
     materialize already stamps (`from: split_piece` / `split_from`,
     and `appearance.describes`). This is the condition the whole idea
     started from, and note that conditions 2 and 3 CANNOT catch it: a
     piece's box sits inside its parent's, so the parent's crop frames
     it perfectly and at a similar scale.

  2  ESCAPED    the current box no longer sits inside the crop, though
     the PHOTO still contains it — so a different rectangle from this
     same photo would show it. This is the only condition a re-crop can
     actually fix, which is why it is measured against the part of the
     box the photo contains, not against the whole box. Conflating
     those two made the first version fire on 40 of 45 nodes and
     disagree with what the user could plainly see on the sheet.

  2b NOT_IN_PHOTO  the box runs off the edge of the photograph. No
     rectangle cut from this photo can show it. That is a request for a
     DIFFERENT VIEW, and it is reported separately because re-cropping
     is not the repair.

  3  RE-ZOOMED  the box still sits inside, but at a very different
     scale — the user's case: "big pano box became smaller box, we
     might want to re-crop so the descriptor is zoomed", and the
     reverse. A description written of a wide shot is not a description
     of the object when the object is now a third of the frame.

THE TWO CONSTANTS ARE DESIGN DEFAULTS, NOT MEASUREMENTS. They were NOT
chosen by looking at what this scene happens to produce — picking a
threshold to suit the scene under test is how a test scene stops being
a test. Each is written as a statement of meaning, so moving it is a
decision about meaning:

  INSIDE_FRAC 0.95  "the crop should show essentially all of the box";
                    the 5% slack absorbs rounding and the pad's edge
                    clamping, not a real escape.
  ZOOM_FACTOR 1.5   "the object now fills less than half, or more than
                    double, of the tile it used to" — 1.5x on a side is
                    2.25x in area.

NOT DECIDED HERE, deliberately: what an applied re-crop is CALLED.
Stored crops are named <node>_m<detection>.png because each one IS a
detection. A re-crop is not a detection — it is a tile derived from a
box — so overwriting a detection's file would erase the record of what
the detector actually saw. That is a design question, not a detail, so
this module has no --apply.

    python graph/recrop_gate.py --scene living_marble
"""
import argparse
import html
import json
import sys
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

HERE = Path(__file__).resolve().parent
for p in (HERE, HERE.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import paths            # noqa: E402
import scene_state      # noqa: E402

# --- the two design defaults (see the module docstring) ------------------
INSIDE_FRAC = 0.95
ZOOM_FACTOR = 1.5

# the pipeline's own crop rule — graph/build_graph.py cut_crops()
CROP_PAD = 0.10
CROPS_PER_MEMBER = 2        # what judge_same_product / judge_cases show

COL_DET = (0, 176, 255)
COL_PROJ = (255, 64, 129)
COL_EDGE = (255, 150, 190)
COL_CUT = (255, 214, 0)
TILE_H = 190

EDGES = [(a, b) for a in range(8) for b in range(a + 1, 8)
         if bin(a ^ b).count("1") == 1]
VERTICAL = {(a, b) for a, b in EDGES if (a ^ b) == 2}


# ---- geometry ----------------------------------------------------------
def area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def inter(a, b):
    return [max(a[0], b[0]), max(a[1], b[1]),
            min(a[2], b[2]), min(a[3], b[3])]


def pad_box(box, w, h):
    x0, y0, x1, y1 = box
    px, py = (x1 - x0) * CROP_PAD, (y1 - y0) * CROP_PAD
    return (max(0, int(x0 - px)), max(0, int(y0 - py)),
            min(w, int(x1 + px)), min(h, int(y1 + py)))


class Scene:
    """Everything read off disk once, plus the camera contract.

    THE CAMERA IS NOT RE-DERIVED. compose/rotation_check.py's
    detection_cam_render_frame() is the trusted mapping ("verified 08-04
    by the refcam box check: 25/28 placed boxes land on their detection
    boxes, hits within a few px"); it continues into the RENDER frame
    for pyrender, so this stops one step earlier and works in the photo's
    own frame:

        p_photo = (p_graph - eye_raw) * pano_to_raw_signs

    Both terms are recorded, neither estimated. The eye is NOT the
    origin — the sidecar's cam=0,0,0 is photo-local, which is what makes
    a naive projection land in the wrong place. And the mirror has to be
    applied to the POINT rather than the camera rebuilt in the graph's
    frame, because that frame is an improper mirror of the photo's
    ("improper (det -1) by DESIGN, the readability mirror").
    """

    def __init__(self, scene):
        self.sd = paths.scene_dir(scene)
        self.views = self.sd / "rig_sp0" / "crops"
        self.crops = self.sd / "graph" / "crops"
        self.r3 = paths.load_r3()
        self.g = json.loads((self.sd / "scene_graph.json").read_text())
        self.layer = scene_state.current(self.g)[0]
        self.cur = {n["id"]: n for n in scene_state.nodes(self.g)}
        self.rec = {n["id"]: n for n in self.g["nodes"]}
        self.res_nodes = {n["id"]: n for n in
                          (self.g.get("resolved") or {}).get("nodes", [])}
        meta = json.loads(
            (self.sd / "rig_sp0" / "pano_selfrender_meta.json")
            .read_text(encoding="utf-8"))
        self.eye = np.array(meta["eye_raw"], np.float32)
        self.signs = np.array(meta.get("pano_to_raw_signs", [1, -1, 1]),
                              np.float32)
        self._img = {}

    def cam(self, view):
        m = json.loads((self.views / f"{view}.json").read_text())
        res = int(m["res"].split("x")[0])
        f = [float(t) for t in m["cam"].split(",")]
        look = np.array([float(t) for t in m["look"].split(",")], np.float32)
        up = [float(t) for t in m["up"].split(",")]
        pos = np.array(f, np.float32)
        return self.r3.Cam(pos, pos + look, up, float(m["fov"]), res,
                           res), res

    def img(self, view):
        if view not in self._img:
            self._img[view] = Image.open(
                self.views / f"{view}.webp").convert("RGB")
        return self._img[view]

    def corners(self, view, geo):
        lo = np.asarray(geo["aabb_min"], float)
        hi = np.asarray(geo["aabb_max"], float)
        c = np.array([[x, y, z] for x in (lo[0], hi[0])
                      for y in (lo[1], hi[1]) for z in (lo[2], hi[2])],
                     np.float32)
        cam, res = self.cam(view)
        u, v, z = cam.project((c - self.eye) * self.signs)
        if (z <= 0.05).any():        # straddles the camera plane —
            return None, res         # meaningless, not merely inaccurate
        return np.stack([u, v], 1), res

    def record_ids(self, nid):
        """settled id -> record ids. Two hops: a current node's members
        are RESOLVED ids and a resolved node's are RECORD ids."""
        out = []
        for rid in (self.cur.get(nid, {}).get("members") or [nid]):
            out += (self.res_nodes.get(rid, {}).get("members") or [rid])
        return out

    def shown_crops(self, nid):
        """The crops this node actually shows a judge: highest detection
        score first, capped the same way the judges cap them."""
        dets = []
        for sid in self.record_ids(nid):
            for m in (self.rec.get(sid, {}).get("evidence")
                      or {}).get("members", []):
                if m.get("crop") and (self.crops / m["crop"]).exists() \
                        and (self.views / f"{m['view']}.json").exists():
                    dets.append({**m, "_from": sid})
        dets.sort(key=lambda m: -m.get("score", 0.0))
        return dets[:CROPS_PER_MEMBER]


# ---- the gate ----------------------------------------------------------
def borrowed(node):
    """Condition 1, by PROVENANCE — the only thing that can see it.
    A split piece inherits its parent's `members` wholesale, so walking
    members says the crops are its own. materialize's own markers do
    not lie."""
    if node.get("from") == "split_piece" or node.get("split_from"):
        return node.get("split_from") or "(a parent)"
    ap = node.get("appearance") or {}
    if ap.get("describes") and ap["describes"] != node["id"]:
        return ap["describes"]
    return None


def judge(sc, nid):
    node = sc.cur[nid]
    geo = node.get("geometry") or {}
    row = {"id": nid, "name": node.get("name"), "layer": sc.layer,
           "fires": [], "borrowed_from": borrowed(node), "crops": []}
    if row["borrowed_from"]:
        row["fires"].append("borrowed")
    if not geo.get("aabb_min"):
        row["fires"].append("no_geometry")
        return row
    for det in sc.shown_crops(nid):
        view = det["view"]
        im = sc.img(view)
        stored = pad_box(det["box_2d"], im.width, im.height)
        pts, _ = sc.corners(view, geo)
        c = {"crop": det["crop"], "view": view, "of": det["_from"],
             "score": det.get("score"), "truncated": det.get("truncated"),
             "stored_rect": [int(v) for v in stored]}
        if pts is None:
            c["verdict"] = "box straddles the camera plane — cannot judge"
            row["crops"].append(c)
            continue
        prj = [float(pts[:, 0].min()), float(pts[:, 1].min()),
               float(pts[:, 0].max()), float(pts[:, 1].max())]
        photo = [0.0, 0.0, float(im.width), float(im.height)]
        a_prj, a_sto = area(prj), area(stored)
        a_vis = area(inter(prj, photo))
        c["proj_rect"] = [int(v) for v in prj]
        # TWO DIFFERENT FAILURES, separated (they were conflated in the
        # first version and it made 40 of 45 nodes look broken):
        #   in_photo — how much of the box this PHOTOGRAPH contains at
        #              all. If the box runs off the edge, no rectangle
        #              cut from this photo can show it; that is a
        #              request for a DIFFERENT VIEW, not a re-crop.
        #   in_crop  — of the part the photo does contain, how much the
        #              stored crop already shows. THIS is the re-crop
        #              question, and it is the only fair way to ask it.
        c["in_photo"] = round(a_vis / a_prj, 3) if a_prj > 0 else 0.0
        c["in_crop"] = round(area(inter(prj, stored)) / a_vis, 3) \
            if a_vis > 0 else 0.0
        c["zoom"] = round(float(np.sqrt(a_prj / a_sto)), 3) \
            if a_sto > 0 else None
        c["fires"] = []
        if c["in_photo"] < INSIDE_FRAC:
            c["fires"].append("not_in_photo")
        if c["in_crop"] < INSIDE_FRAC:
            c["fires"].append("escaped")
        elif c["zoom"] and (c["zoom"] >= ZOOM_FACTOR
                            or c["zoom"] <= 1 / ZOOM_FACTOR):
            c["fires"].append("rezoomed")
        row["crops"].append(c)
    # A NODE IS JUDGED ON ITS BEST CROP, NOT ITS WORST. A node shows the
    # judges more than one crop, and it only needs repair when NONE of
    # them is any good. The first version OR-ed the per-crop fires, so
    # obj_000 — which has one crop framing its box perfectly and one
    # taken from a view that cuts it off — was reported as needing a
    # re-crop. That is how the gate came to disagree with what the user
    # could see, and the disagreement was the gate's fault.
    clean = [c for c in row["crops"] if not c.get("fires")]
    row["n_crops"] = len(row["crops"])
    row["n_clean"] = len(clean)
    if not clean:
        for c in row["crops"]:
            for f in c.get("fires", []):
                if f not in row["fires"]:
                    row["fires"].append(f)
        if not row["crops"]:
            row["fires"].append("no_crops")
    return row


# ---- the report --------------------------------------------------------
def draw(im, pts, cut, det, off, w=3):
    d = ImageDraw.Draw(im)
    ox, oy = off
    if det:
        d.rectangle([det[0] - ox, det[1] - oy, det[2] - ox, det[3] - oy],
                    outline=COL_DET, width=w + 1)
    if pts is not None:
        for a, b in EDGES:
            up = (a, b) in VERTICAL
            d.line([pts[a][0] - ox, pts[a][1] - oy,
                    pts[b][0] - ox, pts[b][1] - oy],
                   fill=COL_PROJ if up else COL_EDGE, width=w if up else 2)
    if cut:
        d.rectangle([cut[0] - ox, cut[1] - oy, cut[2] - ox, cut[3] - oy],
                    outline=COL_CUT, width=w)
    return im


def fit(im, h=TILE_H):
    return im.resize((max(1, round(im.width * h / im.height)), h))


CSS = """
body{font:15px/1.55 system-ui,sans-serif;margin:0;padding:28px;
     background:#14161a;color:#e8eaed}
h1{font-size:21px;margin:0 0 6px}
p,li{max-width:74ch;color:#b9bec7}
.key{background:#1c1f25;border:1px solid #2a2f38;border-radius:8px;
     padding:12px 16px;max-width:74ch;margin:14px 0 22px}
.key b{color:#e8eaed}
table{border-collapse:collapse;width:100%;margin-top:10px}
td,th{border-top:1px solid #2a2f38;padding:10px 8px;vertical-align:top;
      text-align:left}
th{color:#8b93a1;font-weight:600;font-size:12px;text-transform:uppercase;
   letter-spacing:.04em;border-top:none}
img{display:block;border-radius:4px}
.id{font-weight:600} .meta{font-size:12px;color:#8b93a1;margin-top:6px}
.tag{display:inline-block;border-radius:4px;padding:1px 7px;font-size:12px;
     font-weight:600;margin-right:5px}
.borrowed{background:#7c3aed;color:#fff}
.escaped{background:#dc2626;color:#fff}
.not_in_photo{background:#374151;color:#e8eaed}
.rezoomed{background:#d97706;color:#fff}
.no_geometry{background:#374151;color:#e8eaed}
.quiet{color:#6b7280}
.wrap{overflow-x:auto}
"""


def write_report(sc, rows, out):
    e = html.escape
    fire = [r for r in rows if r["fires"]]
    h = [f"<style>{CSS}</style>",
         "<h1>Which nodes need a new tile?</h1>",
         f"<p>Layer <b>{e(sc.layer)}</b> &mdash; {len(rows)} nodes, "
         f"<b>{len(fire)}</b> fire at least one condition. A re-crop is "
         "the same photograph cut to a different rectangle; nothing is "
         "rendered. Nothing has been written &mdash; this page only "
         "decides.</p>",
         '<div class="key">'
         '<span class="tag borrowed">borrowed</span> the crops are not '
         "this node's own &mdash; a split piece showing its parent's "
         "photo. Found by provenance, because a piece inherits its "
         "parent's members and a members-walk cannot see it. "
         "<b>Conditions 2 and 3 cannot catch this</b>: a piece's box "
         "sits inside its parent's, so the parent's crop frames it "
         "well.<br><br>"
         '<span class="tag escaped">escaped</span> the photo still '
         "contains the box, but the stored crop shows less than "
         f"{INSIDE_FRAC:.0%} of it &mdash; a different rectangle from "
         "this same photo would. <b>This is the only condition a "
         "re-crop can fix.</b><br><br>"
         '<span class="tag not_in_photo">not_in_photo</span> the box '
         "runs off the edge of the photograph, so no rectangle cut from "
         "it can show the whole thing. That needs a different view, not "
         "a re-crop, and is listed separately for exactly that "
         "reason.<br><br>"
         '<span class="tag rezoomed">rezoomed</span> the box is inside, '
         f"but at {ZOOM_FACTOR}&times; or less than "
         f"1/{ZOOM_FACTOR:g}&times; the stored crop's scale &mdash; the "
         "object now fills a very different share of the tile, so a "
         "description written of the old one is a description of a "
         "different shot.<br><br>"
         "<b>Both numbers are design defaults, not measurements.</b> "
         "They were not chosen by looking at what this scene produces "
         "&mdash; picking a threshold to suit the scene under test is "
         "how a test scene stops being a test.</div>",
         '<div class="wrap"><table><tr><th>node</th><th>why</th>'
         "<th>the crop it shows now</th>"
         "<th>what a re-crop would give</th>"
         "<th>the photo</th></tr>"]
    for r in fire:
        tags = "".join(f'<span class="tag {f}">{f}</span>'
                       for f in r["fires"])
        note = ""
        if r["borrowed_from"]:
            note = (f'<div class="meta">crops belong to '
                    f'<b>{e(r["borrowed_from"])}</b></div>')
        h.append(f'<tr><td><div class="id">{e(r["id"])}</div>'
                 f'<div class="meta">{e(str(r["name"]))}</div></td>'
                 f"<td>{tags}{note}")
        h.append(f'<div class="meta">{r["n_clean"]} of {r["n_crops"]} '
                 "crops usable</div>")
        for c in r["crops"]:
            h.append(f'<div class="meta">{e(c["view"])}<br>'
                     f'in photo {c.get("in_photo", "n/a")} &middot; '
                     f'in crop {c.get("in_crop", "n/a")} &middot; '
                     f'zoom {c.get("zoom", "n/a")}</div>')
        h.append("</td>")
        # show the node's BEST crop — the one a re-crop has to beat
        cands = [x for x in r["crops"] if x.get("proj_rect")]
        cands.sort(key=lambda x: -(x.get("in_photo", 0)
                                   * x.get("in_crop", 0)))
        c = cands[0] if cands else None
        if not c:
            h.append('<td colspan="3" class="quiet">no usable crop'
                     "</td></tr>")
            continue
        im = sc.img(c["view"])
        pts, _ = sc.corners(c["view"], sc.cur[r["id"]]["geometry"])
        st, pr = c["stored_rect"], c["proj_rect"]
        pb = pad_box(pr, im.width, im.height)
        stem = r["id"].replace("#", "_") + "__" + c["view"]
        a = fit(im.crop(tuple(st)))
        a.save(out / f"{stem}_now.png")
        b = im.crop(tuple(pb))
        if b.width > 3 and b.height > 3:
            fit(draw(b, pts, pr, None, (pb[0], pb[1]))).save(
                out / f"{stem}_new.png")
        full = draw(im.copy(), pts, pr, st, (0, 0), w=5).resize((460, 460))
        full.save(out / f"{stem}_full.png")
        h.append(f'<td><img src="{stem}_now.png"></td>'
                 f'<td><img src="{stem}_new.png"></td>'
                 f'<td><img src="{stem}_full.png" width="460"></td></tr>')
    h.append("</table></div>")
    quiet = [r for r in rows if not r["fires"]]
    h.append(f'<p class="quiet">{len(quiet)} nodes keep their crops '
             "unchanged, which is the ruling: a re-crop is a targeted "
             "repair, not a pass over everything.</p>")
    (out / "index.html").write_text("\n".join(h), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    a = ap.parse_args()
    sc = Scene(a.scene)
    rows = [judge(sc, nid) for nid in sc.cur]
    out = sc.sd / "graph" / "recrop_gate"
    out.mkdir(parents=True, exist_ok=True)
    (out / "recrop_gate.json").write_text(json.dumps(
        {"scene": a.scene, "layer": sc.layer, "status": "UNTESTED",
         "decides_only": "nothing is written; --apply does not exist "
                         "because what an applied re-crop is CALLED is "
                         "an open design question (a re-crop is not a "
                         "detection, so it must not overwrite one)",
         "constants": {"INSIDE_FRAC": INSIDE_FRAC,
                       "ZOOM_FACTOR": ZOOM_FACTOR,
                       "note": "design defaults, NOT tuned on this scene"},
         "rows": rows}, indent=1))
    write_report(sc, rows, out)
    n = {}
    for r in rows:
        for f in r["fires"]:
            n[f] = n.get(f, 0) + 1
    print(f"layer {sc.layer}: {len(rows)} nodes, "
          f"{sum(1 for r in rows if r['fires'])} fire")
    for k, v in sorted(n.items(), key=lambda t: -t[1]):
        print(f"   {v:>3}  {k}")
    print(f"-> {out / 'index.html'}")


if __name__ == "__main__":
    main()
