"""NODE EVIDENCE — what each node is SEEN as, repaired and written into
the graph.

Was `recrop_gate.py` until 2026-08-10, when the user promoted it from a
gate into a module: "each module enriches and edits the scenegraph to a
better state. the graph coming out of this gate module will supersede
and be the singular best representation of the scene graph."

So this is NOT a helper the judges call. It is a LAYER EDIT. It inherits
the whole graph, repairs one thing — the pictures each node is judged on
— and hands on the layer `shown`. Downstream judges stop reaching into
graph/crops and simply read the node. One edit; everyone inherits it.

WHY IT HAD TO BECOME ONE. The gate named every node showing the wrong
photo and the renderer (node_views.py) took correctly aimed pictures,
and NEITHER WAS EVER WIRED TO ANYTHING — both were write-only, while J9
and six other readers went on picking detector crops by detection score,
which is exactly the evidence this gate flags as untrustworthy. The
missing piece was never a better gate; it was a consumer.

USER RULING 2026-08-09. A blanket re-crop pass is NOT wanted: on the
comparison sheet most re-cuts came out near-identical to the crop
already stored, so redoing them buys nothing and risks a tighter frame
than we want. A re-crop is a TARGETED REPAIR. This module decides who
needs one, and (from B2/B3 onward) performs it.

WHAT SUPERSEDES WHAT (user ruling 2026-08-10, "mostly no is a no").
Three of the four conditions leave a stored crop that is a picture of
the WRONG THING, and showing it beside the repair is noise with a
caption. Only re-zoom leaves evidence worth keeping:

    borrowed      superseded   shows the PARENT, not this piece
    not_in_photo  superseded   box off the edge — shows something else
    escaped       superseded   shows part of the box, rest cut off
    rezoomed      KEPT + a re-cut joins it — the crop shows the right
                  object, only at the wrong scale, and this is the very
                  case the condition was written for ("big pano box
                  became smaller box, we might want to re-crop so the
                  descriptor is zoomed")

SUPERSEDE MEANS IN WHAT THE JUDGE SEES, NOT IN THE FOLDER. graph/crops
stays exactly as it is — a crop is the DETECTION RECORD, and
evidence.members[*].crop points at it. Nothing here writes into that
folder either: build_graph.cut_crops WIPES and rebuilds it every run
(the R-S2-67 ownership rule), so anything left there would die silently
on the next run — the precise stale-crop failure that rule closed.
Repairs live in this stage's own folder, under the same rule: rebuild
means replace, never top up.

A "re-crop" is the same photograph cut to a different rectangle — the
one you get by projecting the node's CURRENT box into the photo the crop
came from. It renders nothing. The OTHER repair, for the cases a re-crop
provably cannot fix, is a reshoot: an aimed render from node_views.py.

THE LAYER IS PINNED, NOT DISCOVERED (2026-08-10). This used to read
`scene_state.current(graph)`, and the docstring described that as layer
`grouped` because grouped happened to be current the day it was written.
That cannot stand once J9 CONSUMES this module: grouped is J9's own
OUTPUT, so reading "whatever is current" makes the evidence depend on
the verdict it feeds. The box truth this module needs is `settled` —
after J8's ship rulings, J8s' cuts and J1's merges, before J9 groups
anything — so `settled` is what it reads, by name.

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

WHAT AN APPLIED RE-CROP IS CALLED — the question this module used to
park, DECIDED 2026-08-10. Stored crops are named <node>_m<detection>.png
because each one IS a detection; a re-crop is not a detection but a tile
derived from a box, so it must never overwrite one. Repairs are
therefore named for what they are and live in this stage's folder:

    graph/node_evidence/recut/<node>__<view>.png    same photo, new rect
    graph/node_views/<node>_<view>.png              the aimed renders

THE MARGIN IS NOT TIGHT, AND THAT IS THE POINT (user 2026-08-10: "make
sure there is good margins so its not super tight, it helps to provide
some surroundings for image recognition"). A re-cut therefore uses the
CONTEXT pad family that describe_nodes.py already defines and uses —
not CROP_PAD 0.10, which is the tight detection framing. Re-using an
existing constant rather than inventing one keeps this a statement of
meaning instead of a number fitted to a scene. The bottom pad is the
largest on purpose: it shows what the object sits on.

    python graph/node_evidence.py --scene living_marble     # decide
"""
import argparse
import html
import json
import math
import shutil
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
import vote_cams        # noqa: E402   the vote's camera maths, so a
#                       vote render can be measured with the SAME
#                       projection that drew it

# --- the two design defaults (see the module docstring) ------------------
INSIDE_FRAC = 0.95
ZOOM_FACTOR = 1.5

# the pipeline's own crop rule — graph/build_graph.py cut_crops()
CROP_PAD = 0.10
CROPS_PER_MEMBER = 2        # what judge_same_product / judge_cases show

# THE BOX TRUTH THIS MODULE READS, BY NAME (see the docstring). Never
# scene_state.current(): once J9 consumes this, "current" is J9's own
# output and the evidence would depend on the verdict it feeds.
BOX_LAYER = "settled"

# The re-cut margin. NOT CROP_PAD.
#
# These STARTED as describe_nodes.py's context-crop constants (0.35 /
# 0.35 / 0.75), copied here — and the old comment claimed the meaning
# was "defined in one place", which was never true: they are two
# literals in two files. TIGHTENED HERE ONLY, 2026-08-10 late, on the
# user's review of the re-cut previews ("the margin might be a bit too
# much... make it slightly tighter").
#
# DELIBERATELY NOT CHANGED IN describe_nodes.py. Those pads frame the
# CONTEXT CROPS J6 writes its descriptions from; moving them would
# change judge stimuli and force a re-run of the description pass. This
# stage's re-cut is its own repair and can be framed on its own terms.
# If the two are ever meant to agree again, make it ONE import rather
# than two literals that happen to match.
#
# Bottom stays the largest on purpose, and is cut least, because it
# shows what the object sits on — the thing a reviewer checks first.
CTX_PAD_SIDE = 0.25         # was 0.35
CTX_PAD_TOP = 0.25          # was 0.35
CTX_PAD_BOTTOM = 0.60       # was 0.75
CTX_MIN_PAD = 40            # px floor, so a small box still gets context
VOTE_FILL_MIN = 0.12        # a vote render only counts as a usable tile
                            # if the box takes at least this share of the
                            # frame's width. Below it the object is a
                            # speck in a room shot — technically "inside
                            # the frame", useless as evidence. Judgement,
                            # not a measurement.
# ⚠ JUDGEMENT, NOT MEASUREMENT: these are a framing preference the user
# gave by eye on this scene's previews. Nothing measured says 0.25 is
# right; it is "somewhat less than before" and no more.

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
        # PINNED, not discovered — BOX_LAYER's comment says why. A scene
        # whose chain has not reached `settled` yet is a caller error and
        # says so, rather than quietly judging on some other layer.
        self.layer = BOX_LAYER
        b = self.g.get(BOX_LAYER)
        block = b.get("nodes") if isinstance(b, dict) else None
        if not block:
            raise SystemExit(
                f"[node_evidence] this scene has no whole `{BOX_LAYER}` "
                f"layer — present: {', '.join(scene_state.present(self.g))}"
                f". The box truth is read by name, never from whatever "
                f"happens to be current.")
        self.cur = {n["id"]: n for n in block}
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
        self._vp = {}

    def view_paths(self, m):
        """(photo, camera sidecar) for one detection member.

        A MEMBER MAY LIVE OUTSIDE rig_sp0/crops. Inline retake members
        state their own scene-relative `img` — build_graph.cut_crops has
        always honoured that, this module did not, and it cost two nodes:
        the SP4 enrichment children (obj_005_c00, obj_017_c00) were
        reported as having no usable crop when in fact their photo AND
        its camera sidecar both existed, one folder over in rig_sp0/rcc.
        Same rule as cut_crops, no new convention: the sidecar sits next
        to the photo and carries its name."""
        if m.get("img"):
            p = self.sd / m["img"]
            return p, p.with_suffix(".json")
        return (self.views / f'{m["view"]}.webp',
                self.views / f'{m["view"]}.json')

    def cam(self, view):
        m = json.loads(self._vp[view][1].read_text())
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
                self._vp[view][0]).convert("RGB")
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

    def vote_views(self, nid):
        """The vote stage's own renders of this node, as tile candidates.

        WHY THESE COUNT (user ruling 2026-08-11). slicevote already
        rendered ~217 aimed views with recorded cameras and they were
        sitting unused while this module planned re-cuts and reshoots.
        Reusing them does NOT repeat the R-S2-78 mistake: the vote is a
        CHAIN stage that runs on every scene, not a demoted experiment
        that happened to leave files on this one.

        THEY ARE CONE-CULLED, AND THAT IS ACCEPTED (user: "the cull will
        always remove, culling is fine, use them anyway"). Whatever stood
        between camera and object was deleted so the detector could see
        it, so a judge sees the object unobstructed. The page SAYS SO on
        every such tile rather than passing it off as a plain photograph.

        A RENDER IS ITS OWN CROP. The whole image is the tile, so the
        `in_crop` question does not arise — only whether the box lands
        inside the frame, and how much of the frame it fills."""
        out = []
        sl = self.sd / "vote" / "slices"
        if not sl.is_dir():
            return out
        stem = nid.replace("#", "_p")
        for pf in sorted(sl.glob("*.params.json")):
            n = pf.name[:-len(".params.json")]
            core = n[5:] if n.startswith("vote_") else n
            if not (core == stem or core.startswith(stem + "_")):
                continue
            png = sl / f"{n}.png"
            if not png.exists():
                continue
            try:
                t = json.loads(pf.read_text())
            except ValueError:
                continue
            if not all(k in t for k in ("eye", "aim", "fov")):
                continue
            out.append({"name": n, "png": png, "cam": t,
                        "view": core[len(stem):].lstrip("_") or "view",
                        "culled": (t.get("cull") or {}).get("rule", "")})
        return out

    def vote_view_fit(self, cand, geo):
        """Project the box into a vote render. Returns in_photo (how much
        of the box the frame contains) and fill (how much of the frame
        the box takes), or None when the box straddles the camera."""
        lo = np.asarray(geo["aabb_min"], float)
        hi = np.asarray(geo["aabb_max"], float)
        pts3 = np.array([[x, y, z] for x in (lo[0], hi[0])
                         for y in (lo[1], hi[1]) for z in (lo[2], hi[2])],
                        np.float32)
        t = cand["cam"]
        res = int(t.get("res", 768))
        cam = vote_cams.make_cam(t["eye"], t["aim"], t["fov"], res)
        u, v, z = cam.project(pts3)
        if (z <= 0.05).any():
            return None
        prj = [float(u.min()), float(v.min()), float(u.max()),
               float(v.max())]
        photo = [0.0, 0.0, float(res), float(res)]
        a_prj = area(prj)
        if a_prj <= 0:
            return None
        vis = area(inter(prj, photo))
        return {"in_photo": round(vis / a_prj, 3),
                "fill": round(math.sqrt(max(vis, 0.0)) / res, 3),
                "proj_rect": [int(x) for x in prj], "res": res}

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
                photo, side = self.view_paths(m)
                if m.get("crop") and (self.crops / m["crop"]).exists() \
                        and side.exists() and photo.exists():
                    self._vp[m["view"]] = (photo, side)
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
    # THE VOTE'S OWN RENDERS, measured by the same rule. A render is its
    # own crop, so only two things matter: does the box land inside the
    # frame, and does it fill enough of it to be worth looking at. Best
    # = fills the most while still fully inside.
    vv = []
    for cand in sc.vote_views(nid):
        fit = sc.vote_view_fit(cand, geo)
        if fit is None:
            continue
        vv.append({"view": cand["view"], "name": cand["name"],
                   "png": str(cand["png"]), "culled": cand["culled"],
                   "fit": fit,
                   "ok": (fit["in_photo"] >= INSIDE_FRAC
                          and fit["fill"] >= VOTE_FILL_MIN)})
    row["vote_views"] = vv
    ok = [v for v in vv if v["ok"]]
    row["vote_best"] = max(ok, key=lambda v: v["fit"]["fill"]) if ok else None
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


# ---- the repair plan ---------------------------------------------------
# What each node's evidence SHOULD be, given what fired. Decided here and
# nowhere else, so that B2 (re-cut) and B3 (reshoot) are executors with no
# opinions of their own — the same split as `judge` vs the report.
#
#   keep      nothing wrong; the stored crops stand
#   recut     the photo contains the box; a new rectangle from that same
#             photo shows it. No GPU. The ONLY condition a re-crop fixes.
#   reshoot   no rectangle from any stored photo can show this node —
#             a request for a DIFFERENT VIEW (node_views.py)
#   blocked   cannot be repaired here and the reason is named, never
#             silently dropped
#
# Orthogonal to all of them, `keep_crops` names the stored crops that
# SURVIVE — decided per crop, not per node (see below). A re-zoomed crop
# is kept and a repair joins it; that is the user's ruling expressed as
# data instead of as a fifth kind of repair.
def plan_repair(row):
    """The node's repair, from the conditions its crops fired.

    A NODE IS PLANNED ON ITS BEST CROP, the same rule `judge` uses to
    decide whether it fires at all: a node with one good crop and one
    bad one needs nothing. `judge` has already applied that — row
    ["fires"] is empty unless NO crop was clean."""
    # WHICH STORED CROPS SURVIVE, decided per CROP — because the user's
    # ruling is about conditions, and one node's crops can fire
    # different ones. A crop stays if it is clean, or if its ONLY
    # complaint is re-zoom (right object, wrong scale: real evidence).
    # A crop that escaped, ran off the photo, or belongs to a parent is
    # a picture of the wrong thing and is dropped whatever else happens
    # to the node. Getting this per-node instead of per-crop would have
    # thrown away the good crop of every node that also had a bad one.
    row["keep_crops"] = [c["crop"] for c in row["crops"]
                         if set(c.get("fires") or []) <= {"rezoomed"}
                         and not row["borrowed_from"]]
    fires = row["fires"]
    if not fires:
        row["repair"] = "keep"
        row["repair_why"] = ("at least one stored crop still frames this "
                             "node's box")
        return row
    # A VOTE RENDER IS A SUPPLEMENTARY VIEW, NOT THE MAIN PHOTO.
    #
    # CORRECTED 2026-08-11 (user: "we can still be cropping it no? we saw
    # these objects in `the crop it shows now`"). For about an hour this
    # module promoted a vote render to MAIN whenever one framed the box,
    # which took the repair plan from 24 re-cuts to 1 — not because
    # re-cutting had stopped being right, but because it had been demoted
    # below a picture taken from wherever the vote's camera happened to
    # stand, cone-culled, of whatever side it happened to see.
    #
    # THE MAIN PHOTO IS FROM THE DEFAULT VIEWPOINT. The order is the
    # user's: the stored crop if it still frames the box, else a re-cut
    # of that same photograph, else — and only then — a new picture. The
    # vote renders ride along as extra views, which is what they are.
    row["vote_views_supplementary"] = True
    if "no_geometry" in fires or "no_crops" in fires:
        row["repair"] = "blocked"
        row["repair_why"] = ("no geometry to project" if "no_geometry"
                             in fires else "no usable crop to start from")
        return row
    # BORROWED FIRST, and it always reshoots. Conditions 2 and 3 cannot
    # see it (a split piece's box sits inside its parent's, so the
    # parent's crop frames it perfectly) — so a re-cut would faithfully
    # reproduce the parent's object at the piece's rectangle. The photo
    # is not wrong about the box; it is wrong about WHOSE box it is.
    if "borrowed" in fires:
        row["repair"] = "reshoot"
        row["repair_why"] = (
            f'crops belong to {row["borrowed_from"]}, not this node — a '
            f're-cut would re-frame the parent, not photograph this piece')
        return row
    # Can any single stored crop be repaired by re-cutting? Only one
    # whose PHOTO holds the box (in_photo >= INSIDE_FRAC) but whose
    # stored rectangle misses it. If the box runs off every photo, no
    # rectangle exists to cut and the answer is a new view.
    recutable = [c for c in row["crops"]
                 if c.get("in_photo", 0) >= INSIDE_FRAC
                 and c.get("proj_rect")]
    if recutable:
        row["repair"] = "recut"
        row["repair_why"] = (
            f'{len(recutable)} of {row["n_crops"]} photos still contain '
            f'the box; the stored rectangle no longer does')
        row["recut_from"] = [c["view"] for c in recutable]
        return row
    row["repair"] = "reshoot"
    row["repair_why"] = ("the box runs off the edge of every photo it "
                         "has — no rectangle cut from them can show it")
    return row


def recut_rect(prj, w, h):
    """The rectangle a re-cut would take: the projected box padded with
    the CONTEXT family (see the docstring), clamped to the photo.
    Deliberately generous — a judge reads an object better with some of
    what is around it, and the bottom shows what it sits on."""
    x0, y0, x1, y1 = prj
    bw, bh = x1 - x0, y1 - y0
    ps = max(CTX_PAD_SIDE * bw, CTX_MIN_PAD)
    pt = max(CTX_PAD_TOP * bh, CTX_MIN_PAD)
    pb = max(CTX_PAD_BOTTOM * bh, CTX_MIN_PAD)
    return (max(0, int(x0 - ps)), max(0, int(y0 - pt)),
            min(w, int(x1 + ps)), min(h, int(y1 + pb)))


# ---- B2: performing the re-cuts ----------------------------------------
def do_recuts(sc, rows, out):
    """Cut the planned re-crops. Same photograph, new rectangle.

    THE FOLDER IS WIPED AND REBUILT, like every stage's output (the
    R-S2-67 ownership rule): node numbers are handed out fresh on a
    re-run, so a leftover file can share a name with a new re-cut and
    serve a dead object's picture. That exact failure cost 9 crops on
    08-06 and poisoned J9's sheets. Cutting takes seconds; topping up
    buys nothing and risks everything.

    NOTHING IS RENDERED HERE and nothing outside this folder is touched
    — graph/crops keeps every detection exactly as the detector left it.
    """
    rc = out / "recut"
    if rc.exists():
        shutil.rmtree(rc)
    rc.mkdir(parents=True, exist_ok=True)
    n_cut = n_skip = 0
    for r in rows:
        r["recut_files"] = []
        if r["repair"] != "recut":
            continue
        for c in r["crops"]:
            if c.get("in_photo", 0) < INSIDE_FRAC or not c.get("proj_rect"):
                continue
            im = sc.img(c["view"])
            box = recut_rect(c["proj_rect"], im.width, im.height)
            if box[2] - box[0] < 4 or box[3] - box[1] < 4:
                n_skip += 1          # degenerate — named, not silent
                c["recut"] = None
                c["recut_why"] = "projected box is smaller than 4 px"
                continue
            # THE NAME CARRIES THE DETECTION, NOT JUST THE VIEW. A node
            # can hold two detections in ONE photograph, and naming by
            # <node>__<view> made the second silently overwrite the
            # first — 40 cut, 39 on disk. One filename, two writers is
            # the same failure that served dead objects' crops on 08-06.
            # The stored crop's stem is unique per detection, so borrow
            # it rather than invent a counter.
            name = (f'{r["id"].replace("#", "_")}__'
                    f'{Path(c["crop"]).stem}.png')
            im.crop(box).save(rc / name)
            c["recut"] = name
            c["recut_rect"] = [int(v) for v in box]
            r["recut_files"].append(name)
            n_cut += 1
    return n_cut, n_skip


# ---- B3: attaching the reshoots ----------------------------------------
# WHAT THE READER SEES IS THE PROBLEM, NOT OUR WORD FOR IT (user
# 2026-08-10 late: "the tags are stupid, tell me the actual problem").
# The keys stay — they are in node_evidence.json, the CSS and every
# other module — but nothing on the page shows a reader "escaped" and
# expects them to know what it means.
TAG_LABEL = {
    "escaped": "the tile cuts the object off",
    "not_in_photo": "the object runs off the edge of the photo",
    "borrowed": "this is the parent's photo, not its own",
    "rezoomed": "the tile is at the wrong zoom",
    "no_geometry": "no box to work from",
    "no_crops": "no picture at all",
}


def tag_label(key):
    return TAG_LABEL.get(key, key.replace("_", " "))


def plan_views_for(sc, nid):
    """The aimed view NAMES node_views planned for one node, for the
    review page to quote. Read-only and failure-tolerant: a missing or
    wrong-layer node_views.json means "nothing planned yet", which the
    page says out loud — it never invents a plan. Layer is checked for
    the same reason attach_reshoots checks it: a plan aimed at another
    layer describes a different box."""
    try:
        nv = sc.sd / "graph" / "node_views.json"
        if not nv.exists():
            return []
        d = json.loads(nv.read_text())
        if d.get("layer") != BOX_LAYER:
            return []
        row = next((r for r in d.get("rows", []) if r["id"] == nid), None)
        return [v["view"] for v in (row or {}).get("views", [])
                if v.get("view")]
    except Exception:                                        # noqa: BLE001
        return []


def attach_reshoots(sc, rows):
    """Give every `reshoot` node the aimed pictures that serve it.

    NO RENDERING HAPPENS HERE. node_views.py owns the cameras and the
    GPU batch; this only reads its decision and resolves each view to a
    file that exists. Run it first with `--layer settled --only <ids>`
    (settled, NOT current: current is `grouped`, which is J9's own
    output, and on living 3 of these 11 nodes have a different box
    there).

    A VIEW'S PICTURE IS NOT ALWAYS IN node_views/. The reuse gate
    (R-S2-57) satisfies a view either by keeping a node_views render or
    by REUSING a prior shot that still frames today's box — and the
    prior lives in graph/node_views/ too, from an earlier run. `file` names it
    sit; for a reuse it is the prior that actually exists. Resolving
    only the first path would have attached 26 of 48 filenames that are
    not on disk, and the failure would not have surfaced until a judge
    was handed a missing image."""
    nv = sc.sd / "graph" / "node_views.json"
    if not nv.exists():
        return 0, ["node_views.json does not exist — run node_views.py "
                   "--layer settled --only <the reshoot ids> first"]
    d = json.loads(nv.read_text())
    if d.get("layer") != BOX_LAYER:
        return 0, [f'node_views.json was aimed at `{d.get("layer")}`, not '
                   f'`{BOX_LAYER}` — re-run it with --layer {BOX_LAYER} '
                   f'or the pictures frame a different box than the plan']
    by_id = {r["id"]: r for r in d.get("rows", [])}
    n, problems = 0, []
    for r in rows:
        if r["repair"] != "reshoot":
            continue
        row = by_id.get(r["id"])
        if not row or not row.get("views"):
            problems.append(f'{r["id"]}: no views planned')
            continue
        files = []
        for v in row["views"]:
            # ONE PLACE ONLY (2026-08-10). node_views now reuses its OWN
            # prior renders, so every picture it names — reused or fresh
            # — lives in graph/node_views/. The old second path into
            # aimed_views_resolved/ is gone: it pointed at the demoted
            # method's renders, which a fresh automated scene never
            # produces, so keeping it would mean living resolving files
            # that scenes 2..100 cannot.
            rel = f'graph/node_views/{v["file"]}'
            if (sc.sd / rel).exists():
                files.append({"view": v["view"], "path": rel,
                              "status": v["status"]})
            else:
                problems.append(f'{r["id"]}/{v["view"]}: no file on disk '
                                f'— node_views planned it but the render '
                                f'has not been taken yet')
        r["reshoot_files"] = files
        n += len(files)
        if not files:
            problems.append(f'{r["id"]}: planned but no picture exists')
    return n, problems


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


def evidence_canvas(im, pts, prj, stored, out_w=460):
    """The DIRECT EVIDENCE for the verdict, drawn so it can be seen.

    Drawing the box straight onto the photo cannot show "the object runs
    off the edge" — the part that proves it is the part outside the
    frame, and it gets clipped away with the drawing (user 2026-08-10:
    "i want to see the direct evidence visualized"). So the photo is
    pasted onto a larger canvas and the projected box is drawn at full
    extent, crossing the photo's edge in plain view. The white outline
    is the photograph's own boundary: box outside it = pixels that do
    not exist, and no rectangle cut from this photo can ever contain
    them. That is the whole argument for a reshoot, in one picture."""
    pad_l = int(max(0, -min(prj[0], 0)))
    pad_t = int(max(0, -min(prj[1], 0)))
    pad_r = int(max(0, prj[2] - im.width))
    pad_b = int(max(0, prj[3] - im.height))
    m = 12 if (pad_l or pad_t or pad_r or pad_b) else 4   # breathing room
    pad_l, pad_t = pad_l + m, pad_t + m
    pad_r, pad_b = pad_r + m, pad_b + m
    canvas = Image.new("RGB", (im.width + pad_l + pad_r,
                               im.height + pad_t + pad_b), (26, 27, 31))
    canvas.paste(im, (pad_l, pad_t))
    off = (-pad_l, -pad_t)
    draw(canvas, pts, prj, stored, off, w=5)
    # the photograph's own edge, LAST so it sits on top of the box
    ImageDraw.Draw(canvas).rectangle(
        [pad_l, pad_t, pad_l + im.width - 1, pad_t + im.height - 1],
        outline=(255, 255, 255), width=3)
    return canvas.resize(
        (out_w, max(1, round(canvas.height * out_w / canvas.width))))


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
.ok{background:#065f46;color:#d1fae5;font-weight:500}
.quiet{color:#6b7280}
/* the reshoots are the only decision that costs anything — they are
   marked so the eye finds them without reading a single word */
.reshoot-row > td{background:#2a1a12;border-top:2px solid #f59e0b}
.needs{margin-top:8px;display:inline-block;background:#f59e0b;color:#1a1b1f;
       font-weight:700;font-size:11px;letter-spacing:.03em;
       padding:2px 8px;border-radius:4px}
.callout{background:#2a1a12;border-left:4px solid #f59e0b;padding:14px 18px;
         border-radius:6px;margin:18px 0}
.callout a{color:#fbbf24;font-weight:600;text-decoration:none;
           margin-right:2px}
.callout a:hover{text-decoration:underline}
.legend{background:#16171b;border:1px solid #2a2c33;border-radius:6px;
        padding:14px 18px;margin:18px 0;font-size:13px;line-height:1.5}
.wrap{overflow-x:auto}
"""


def write_report(sc, rows, out):
    e = html.escape
    fire = [r for r in rows if r["fires"]]
    rep = {}
    for r in rows:
        rep[r["repair"]] = rep.get(r["repair"], 0) + 1
    tally = " &middot; ".join(f"<b>{v}</b> {k}" for k, v in
                              sorted(rep.items(), key=lambda t: -t[1]))
    h = [f"<style>{CSS}</style>",
         "<h1>What each node is seen as &mdash; and what needs "
         "repairing</h1>",
         f"<p>Box layer <b>{e(sc.layer)}</b>, read by name (never "
         "&ldquo;whatever is current&rdquo; &mdash; once J9 reads this "
         "module, current is J9's own output). {n} nodes, "
         f"<b>{len(fire)}</b> fire at least one condition.</p>"
         .replace("{n}", str(len(rows))),
         f"<p>The plan: {tally}. <b>Nothing has been performed.</b> No "
         "pixels written, nothing rendered &mdash; this page only "
         "decides, and you rule on it before anything is cut or "
         "shot.</p>",
         '<div class="key">'
         "<b>The repairs.</b><br>"
         '<span class="tag rezoomed">recut</span> the same photograph '
         "cut to a new rectangle around the box. No GPU. Cut with "
         "<b>generous margins</b> (the context pads describe_nodes "
         "already uses &mdash; 0.35 sides and top, 0.75 below, 40px "
         "floor), because an object is easier to recognise with some of "
         "its surroundings, and the deeper bottom shows what it sits "
         "on.<br><br>"
         '<span class="tag borrowed">reshoot</span> no rectangle from '
         "any stored photo can show this node, so it needs a different "
         "view: an aimed render. Queued for your go, never rendered "
         "automatically.<br><br>"
         '<span class="tag not_in_photo">keep+recut</span> re-zoom only '
         "&mdash; the stored crop shows the right object at the wrong "
         "scale, so it <b>stays</b> as evidence and a properly framed "
         "re-cut joins it.<br><br>"
         '<span class="tag no_geometry">blocked</span> cannot be '
         "repaired here; the reason is named rather than dropped."
         "</div>",
         '<div class="key">'
         '<span class="tag escaped">the tile cuts the object off</span> '
         "The object IS in the photo, but the tile we cut shows less "
         f"than {INSIDE_FRAC:.0%} of it. Cutting a different rectangle "
         "out of the same photo would show the whole thing. "
         "<b>This is the only problem a re-cut can fix</b>, and it is "
         "free &mdash; same photo, new rectangle, no new picture "
         "needed.<br><br>"
         '<span class="tag not_in_photo">the object runs off the edge '
         "of the photo</span> Part of it is outside the picture "
         "altogether, so no rectangle cut from this photo can ever show "
         "all of it. Re-cutting cannot help. This one needs a NEW "
         "PICTURE from a different angle &mdash; which is why these are "
         "the expensive ones.<br><br>"
         '<span class="tag borrowed">this is the parent\'s photo, not '
         "its own</span> The node is a piece that was split off "
         "something bigger, and it inherited its parent's pictures. So "
         "the tile shows the WHOLE parent, not this piece. Note the "
         "other two checks cannot catch this: the piece's box sits "
         "inside the parent's, so the parent's tile frames it "
         "perfectly &mdash; it just shows the wrong object. Found by "
         "tracking where the crops came from.<br><br>"
         '<span class="tag rezoomed">the tile is at the wrong '
         f"zoom</span> The object fits, but it is now {ZOOM_FACTOR}"
         f"&times; bigger or smaller than when the tile was cut, so it "
         "fills a very different share of the picture. A description "
         "written from the old tile is a description of a different "
         "shot.<br><br>"
         "<b>Both numbers are design defaults, not measurements.</b> "
         "They were not chosen by looking at what this scene produces "
         "&mdash; picking a threshold to suit the scene under test is "
         "how a test scene stops being a test.</div>",
         ]
    # THE RESHOOTS ARE THE ONLY EXPENSIVE DECISION ON THIS PAGE (user
    # 2026-08-10 late: "recut is trivial, highlight the reshoots"). A
    # re-cut is the same photograph cut to a new rectangle — free, no
    # GPU, reversible. A reshoot means RENDERING NEW PICTURES, and it is
    # the only thing here that needs the user's go. So they sort first,
    # they are named up front, and their rows are marked.
    _rs = [r for r in rows if r["repair"] == "reshoot"]
    if _rs:
        _links = " ".join(
            f'<a href="#n_{e(r["id"]).replace("#", "_")}">{e(r["id"])}</a>'
            f' <span class="quiet">{e(str(r["name"]))}</span>'
            for r in sorted(_rs, key=lambda x: x["id"]))
        h.append(
            f'<div class="callout"><b>{len(_rs)} node(s) need a NEW '
            "PICTURE.</b> These are the only ones that cost anything. "
            "Their box runs off the edge of every photo they own, so no "
            "rectangle cut from what we already have can show the whole "
            "object &mdash; a re-cut cannot fix them.<br><br>"
            f"{_links}<br><br>"
            f'<span class="quiet">The other '
            f'{len([r for r in rows if r["repair"] == "recut"])} repairs '
            "are re-cuts: same photograph, new rectangle, no GPU, "
            "nothing rendered.</span></div>")
    # WHAT THE COLOURED BOXES MEAN (user 2026-08-10 late: "i can see a
    # bunch of coloured boxes, i have no idea what each are"). The
    # pictures carried four different overlays and the page never said
    # which was which — a reviewer cannot check a verdict drawn in a
    # code they have not been given. Swatches are the real constants,
    # so this cannot drift from what is actually drawn.
    def _sw(rgb, label, text):
        return (f'<div style="margin:6px 0"><span style="display:'
                f"inline-block;width:26px;height:12px;border-radius:2px;"
                f"background:rgb{rgb};vertical-align:middle;"
                f'margin-right:9px"></span><b>{label}</b> &mdash; '
                f"{text}</div>")

    h.append(
        '<div class="legend"><b>What the colours mean</b>'
        + _sw(COL_PROJ, "pink box",
              "the object's 3D box, projected into this photograph. The "
              "upright edges are the bright pink ones. THIS IS THE THING "
              "BEING JUDGED &mdash; if it is drawn somewhere the object "
              "plainly is not, the box is wrong, not the picture.")
        + _sw(COL_CUT, "yellow rectangle",
              "that same pink box reduced to a plain rectangle. This is "
              "what the measurements are taken on, and what a re-cut "
              "would be built around.")
        + _sw(COL_DET, "blue rectangle",
              "the tile we currently cut &mdash; exactly the picture in "
              "the 'crop it shows now' column. Compare it against the "
              "yellow: yellow sticking out of blue is object the judge "
              "never sees.")
        + _sw((255, 255, 255), "white outline",
              "the edge of the photograph itself. Anything drawn outside "
              "it does not exist in this picture, and no tile cut from "
              "it can ever recover that part &mdash; which is the whole "
              "case for a new shot.")
        + "</div>")
    h += ['<div class="wrap"><table><tr><th>node</th>'
          "<th>flagged? the repair, and why</th>"
          "<th>the crop it shows now</th>"
          "<th>what it will be judged on instead</th>"
          # "the photo" said nothing (user 2026-08-10: "rename it, very
          # confusing"). It is the WHOLE source photograph the crop was
          # cut out of, with the box drawn on it — the context that
          # shows whether the crop was cut from the right place.
          "<th>the whole photo it was cut from<br>"
          "<span style='font-weight:400;opacity:.7'>box drawn on it</span>"
          "</th></tr>"]
    # EVERY NODE IS LISTED, FLAGGED OR NOT (user ruling 2026-08-10:
    # "i want the list of objects, current shot, no matter triggered a
    # reshoot or not, show it to me, tell me if it was flagged for a
    # reshoot and why"). The page used to table only the nodes that
    # fire and collapse the rest into one sentence — so the reviewer
    # could see the repairs but never the decisions NOT to repair,
    # which is half of what there is to judge.
    # ORDER: reshoots (the expensive decision) -> re-cuts (free) ->
    # kept (nothing to do). Reading order should match how much the
    # reader's attention is worth.
    _rank = {"reshoot": 0, "blocked": 1, "recut": 2, "vote_view": 3,
             "keep": 4}
    for r in sorted(rows, key=lambda x: (_rank.get(x["repair"], 9),
                                         x["id"])):
        tags = "".join(f'<span class="tag {f}">{e(tag_label(f))}</span>'
                       for f in r["fires"]) or (
            '<span class="tag ok">nothing wrong — keeping its tile</span>')
        note = ""
        if r["borrowed_from"]:
            note = (f'<div class="meta">crops belong to '
                    f'<b>{e(r["borrowed_from"])}</b></div>')
        _rowcls = ' class="reshoot-row"' if r["repair"] == "reshoot" else ""
        _anchor = e(r["id"]).replace("#", "_")
        h.append(f'<tr{_rowcls} id="n_{_anchor}"><td>'
                 f'<div class="id">{e(r["id"])}</div>'
                 f'<div class="meta">{e(str(r["name"]))}</div>'
                 + ('<div class="needs">NEEDS A NEW PICTURE</div>'
                    if r["repair"] == "reshoot" else "") + "</td>"
                 f'<td><div class="id">{e(r["repair"])}</div>'
                 f'<div class="meta">{e(r["repair_why"])}</div>'
                 f'<div style="margin-top:8px">{tags}{note}</div>')
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
        # the rectangle a re-cut would ACTUALLY take — the context pads,
        # not CROP_PAD. The preview has to show the margin the repair
        # will have, or the page is arguing for a picture nobody gets.
        pb = recut_rect(pr, im.width, im.height)
        stem = r["id"].replace("#", "_") + "__" + c["view"]
        a = fit(im.crop(tuple(st)))
        a.save(out / f"{stem}_now.png")
        # WHEN THE RE-CUT WAS ACTUALLY TAKEN, SHOW THE REAL FILE — not a
        # redrawn preview with the box wire on it. The judge will be
        # given the clean picture, so the clean picture is what should
        # be reviewed; a preview that flatters itself is worth nothing.
        # A RESHOOT NODE MUST NOT BE SHOWN A RE-CUT PREVIEW. It was
        # planned `reshoot` precisely BECAUSE a re-cut cannot work here,
        # so previewing one advertises a repair that was rejected and
        # hides the one actually chosen (user caught this on obj_039 and
        # obj_042). Show the aimed picture that really serves it.
        if r.get("reshoot_files"):
            f = r["reshoot_files"][0]
            new_src = "../../" + f["path"]
            new_note = (f'aimed view <b>{e(f["view"])}</b> &mdash; '
                        + ("a prior shot reused (it still frames this "
                           "box)" if f["status"] == "reuse_prior"
                           else "rendered for this box")
                        + f' &middot; {len(r["reshoot_files"])} in all')
        elif r["repair"] == "reshoot":
            # A RESHOOT NODE MUST NEVER BE SHOWN A RE-CUT PREVIEW —
            # SECOND FIX (user 2026-08-10 late). R-S2-75 fixed this for
            # the case where an aimed picture EXISTS; run without
            # --reshoot and it fell straight back through to the
            # preview branch, advertising the repair this node was
            # denied and hiding the one actually chosen. The reviewer
            # is judging whether a reshoot is warranted, so the honest
            # answer when no picture exists yet is to SAY SO and name
            # what is planned — not to draw a rectangle nobody will use.
            _pl = plan_views_for(sc, r["id"])
            new_src = None
            new_note = (
                "<b>no picture yet.</b> This node needs a NEW SHOT: its "
                "box runs off the edge of every photo it owns, so no "
                "rectangle cut from them can show the whole object "
                "&mdash; that is why a re-cut was rejected here."
                + (f'<br>planned aimed view(s): <b>{e(", ".join(_pl))}</b>'
                   if _pl else
                   "<br><i>no views planned yet &mdash; run node_views.py "
                   f"--layer {BOX_LAYER} first</i>"))
        elif r["repair"] == "vote_view" and r.get("vote_best"):
            # THE REAL FILE, and the caveat with it. These renders had
            # whatever stood in front of the object deleted so the vote's
            # detector could see it. A judge shown one sees the object
            # unobstructed, which is a real difference from a photograph
            # and is said here rather than left to be discovered.
            _b = r["vote_best"]
            new_src = "../../vote/slices/" + Path(_b["png"]).name
            _cull = _b.get("culled") or ""
            new_src_note = (
                f'<b>the vote stage\'s own render</b> &mdash; view '
                f'<code>{e(_b["view"])}</code>, box sits '
                f'{_b["fit"]["in_photo"]:.0%} inside the frame and fills '
                f'{_b["fit"]["fill"]:.0%} of it. Costs nothing: this '
                f'picture already exists.')
            if "in_cone" in _cull:
                new_src_note += (
                    '<br><b style="color:#f59e0b">Occluders removed.</b> '
                    "Anything standing between the camera and this object "
                    "was deleted so the vote's detector could see it, so "
                    "the object looks unobstructed here even if it is "
                    "partly hidden in the room.")
            elif "clip_y_gt" in _cull:
                new_src_note += ("<br>Ceiling clipped (plan view from "
                                 "above the room).")
            new_note = new_src_note
        elif r["repair"] == "keep":
            # THIRD BRANCH OF THE SAME RULE. A `keep` node is not being
            # repaired at all, so drawing it a re-cut preview shows a
            # picture nobody will ever be handed and reads as though a
            # change were pending. Its answer to "what will it be
            # judged on" is the crop already on its left.
            new_src = None
            new_note = ("<b>no change.</b> This node keeps the crop on "
                        "the left &mdash; that is what it will be "
                        "judged on. It was not flagged: at least one "
                        "stored crop still frames its box.")
        elif c.get("recut"):
            new_src, new_note = f'recut/{c["recut"]}', "the file itself"
        else:
            b = im.crop(tuple(pb))
            if b.width > 3 and b.height > 3:
                fit(draw(b, pts, pr, None, (pb[0], pb[1]))).save(
                    out / f"{stem}_new.png")
            new_src, new_note = f"{stem}_new.png", "preview, not taken"
        evidence_canvas(im.copy(), pts, pr, st).save(
            out / f"{stem}_full.png")
        # THE NUMBERS THAT DECIDED IT, printed beside the picture that
        # shows it — so the verdict can be checked, not just believed.
        _ip, _ic = c.get("in_photo"), c.get("in_crop")
        _why = []
        if _ip is not None:
            _why.append(
                f"<b>{_ip:.0%}</b> of the object is inside the photo"
                + (f" &mdash; under {INSIDE_FRAC:.0%}, so it runs off "
                   "the edge" if _ip < INSIDE_FRAC else " &mdash; fine"))
        if _ic is not None:
            _why.append(
                f"the tile shows <b>{_ic:.0%}</b> of that"
                + (f" &mdash; under {INSIDE_FRAC:.0%}, so the tile cuts "
                   "it off" if _ic < INSIDE_FRAC else " &mdash; fine"))
        if c.get("zoom"):
            _bad = (c["zoom"] >= ZOOM_FACTOR or c["zoom"] <= 1 / ZOOM_FACTOR)
            _why.append(f'zoom <b>{c["zoom"]:.2f}&times;</b>'
                        + (f" &mdash; past {ZOOM_FACTOR}&times; either way"
                           if _bad else " &mdash; fine"))
        # new_src is None for a reshoot node with no picture yet: the
        # cell carries the explanation alone rather than an image that
        # would misrepresent the plan.
        _newcell = (f'<img src="{new_src}" style="max-height:260px">'
                    if new_src else "")
        h.append(f'<td><img src="{stem}_now.png"></td>'
                 f'<td>{_newcell}'
                 f'<div class="meta">{new_note}</div></td>'
                 f'<td><img src="{stem}_full.png" width="460">'
                 '<div class="meta">white outline = the edge of the '
                 "photograph. Anything drawn outside it does not exist "
                 "in this picture, so no tile cut from it can show "
                 "that part.<br>" + "<br>".join(_why)
                 + "</div></td></tr>")
    h.append("</table></div>")
    quiet = [r for r in rows if not r["fires"]]
    h.append(f'<p class="quiet">{len(rows)} nodes listed &mdash; '
             f'{len(rows) - len(quiet)} flagged for a repair, '
             f"{len(quiet)} keeping their crops unchanged (shown at the "
             "bottom, tagged <b>not flagged</b>). A re-crop is a "
             "targeted repair, not a pass over everything &mdash; so the "
             "decisions NOT to repair are as much a part of this review "
             "as the repairs.</p>")
    (out / "index.html").write_text("\n".join(h), encoding="utf-8")


LAYER = "shown"


def chosen_picture(sc, r):
    """The ONE picture this node is now seen as, resolved to a file that
    exists, or None with a spoken reason.

    Order is the repair plan's own: a vote render that already frames the
    box, else a kept crop, else the re-cut, else the aimed render."""
    rep = r.get("repair")
    if rep == "vote_view" and r.get("vote_best"):
        b = r["vote_best"]
        p = Path(b["png"])
        return ({"source": "vote_render", "view": b["view"],
                 "path": p.as_posix(),
                 "in_photo": b["fit"]["in_photo"],
                 "fill": b["fit"]["fill"],
                 "occluders_removed": "in_cone" in (b.get("culled") or ""),
                 "why": r.get("repair_why")}, None) if p.exists() else \
               (None, f"vote render missing on disk: {p.name}")
    if rep == "reshoot":
        fs = r.get("reshoot_files") or []
        if not fs:
            return None, ("planned reshoot but no aimed picture attached "
                          "— run node_views.py then --reshoot")
        # THE MAIN VIEW BY NAME, NEVER "WHATEVER IS FIRST".
        #
        # BUG 2026-08-11, user-found: this took fs[0], and when the
        # `main` render was missing that silently became card0 — a
        # cardinal view from wherever the standoff rule put the camera,
        # shipped as the object's main photo. It happened to 9 of 11
        # nodes because a fov change deleted their main pngs and the
        # re-render was never run. A missing main photo must be a
        # PROBLEM, not a quiet substitution; the cardinals are already
        # carried as supplementary views and do not need promoting.
        f = next((x for x in fs if x.get("view") == "main"), None)
        if f is None:
            return None, (
                "the `main` render is missing — node_views planned it but "
                "the file is not on disk (run node_views.py --render). "
                f"{len(fs)} other view(s) are attached and stay "
                "SUPPLEMENTARY; a cardinal view is not a main photo")
        return {"source": "aimed_render", "view": f.get("view"),
                "path": f["path"], "n_views": len(fs),
                "status": f.get("status"),
                "why": r.get("repair_why")}, None
    if rep == "recut":
        cut = next((c for c in r.get("crops") or [] if c.get("recut")), None)
        if not cut:
            return None, ("planned re-cut but none taken — run with "
                          "--recut")
        return {"source": "recut", "view": cut.get("view"),
                "path": f"graph/node_evidence/recut/{cut['recut']}",
                "why": r.get("repair_why")}, None
    if rep == "keep":
        keep = (r.get("keep_crops") or [None])[0]
        if not keep:
            return None, "planned keep but no crop survived"
        cr = next((c for c in r.get("crops") or []
                   if c.get("crop") == keep), None)
        return {"source": "stored_crop", "view": (cr or {}).get("view"),
                "path": f"graph/crops/{keep}",
                "why": r.get("repair_why")}, None
    return None, f"no picture rule for repair `{rep}`"


def write_layer(sc, rows, apply_it):
    """graph['shown'] — the whole `settled` layer, with every node's
    CURRENT picture named on it.

    ONE EDIT, EVERYONE INHERITS (the project's graph rule). The layer is
    settled's nodes and edges VERBATIM; the only addition is a `shown`
    block per node. Nothing here recomputes geometry — the boxes are
    settled's, unchanged, and this stage has no opinion about them.

    WHY IT IS A LAYER AND NOT A SIDECAR (user ruling 2026-08-11): the
    stored crops are STALE — cut around boxes that have since moved — so
    the pictures named here SUPERSEDE them for every reader. A sidecar
    would leave seven readers still choosing crops by detection score,
    which is the exact gap that made this module necessary."""
    graph = sc.g
    base = graph.get(BOX_LAYER) or {}
    nodes = json.loads(json.dumps(base.get("nodes")))    # verbatim copy
    it = nodes.items() if isinstance(nodes, dict) else \
        ((n["id"], n) for n in nodes)
    by_id = dict(it)
    named = problems = 0
    for r in rows:
        nd = by_id.get(r["id"])
        if nd is None:
            continue
        pic, err = chosen_picture(sc, r)
        if pic is None:
            nd["shown"] = {"picture": None, "problem": err,
                           "repair": r.get("repair")}
            problems += 1
            continue
        # THE MAIN PHOTO, PLUS EVERY OTHER CORRECT VIEW OF THIS OBJECT
        # (user 2026-08-11: "each object have a set of images. one is the
        # main image ... then it will have a set of other views ... as
        # long as they are correct, and shows the object, i would like to
        # keep them. but we always need a main photo").
        #
        # The main photo is from the DEFAULT VIEWPOINT — crop, re-cut, or
        # a render standing in for it. The extras are whatever else the
        # pipeline already made and that still frames this box: the
        # vote's cardinals and plan shots, and any aimed render. They are
        # supplementary BY POSITION IN THIS LIST, so nothing downstream
        # has to guess which picture is the one.
        extras = []
        for v in (r.get("vote_views") or []):
            if not v.get("ok"):
                continue
            extras.append({"source": "vote_render", "view": v["view"],
                           "path": Path(v["png"]).as_posix(),
                           "in_photo": v["fit"]["in_photo"],
                           "fill": v["fit"]["fill"],
                           "occluders_removed":
                               "in_cone" in (v.get("culled") or "")})
        for f in (r.get("reshoot_files") or [])[1:]:
            extras.append({"source": "aimed_render", "view": f.get("view"),
                           "path": f["path"], "status": f.get("status")})
        nd["shown"] = {"picture": pic, "repair": r.get("repair"),
                       "views": extras, "n_views": len(extras),
                       "supersedes_crops": [c.get("crop")
                                            for c in (r.get("crops") or [])
                                            if c.get("crop")]}
        named += 1
    layer = {"nodes": nodes,
             "edges": json.loads(json.dumps(base.get("edges") or [])),
             "run": {"stage": "node_evidence", "from_layer": BOX_LAYER,
                     "status": "UNTESTED"},
             "counts": {"nodes": len(by_id), "with_picture": named,
                        "problems": problems},
             "note": ("every node's CURRENT picture. graph/crops is the "
                      "detection record and is untouched; these entries "
                      "SUPERSEDE it for anything that shows a node to a "
                      "judge or a buyer.")}
    print(f"[evidence] layer `{LAYER}`: {named} node(s) with a picture, "
          f"{problems} problem(s)")
    if not apply_it:
        print("[evidence] DRY — layer NOT written (rerun with --apply)")
        return layer
    before = {k: v for k, v in graph.items() if k != LAYER}
    graph[LAYER] = layer
    scene_state.stamp(graph, LAYER)
    p = sc.sd / "scene_graph.json"
    p.write_text(json.dumps(graph, indent=1), encoding="utf-8")
    after = json.loads(p.read_text(encoding="utf-8"))
    changed = [k for k in set(before) | (set(after) - {LAYER})
               if k != "layer"
               if json.dumps(before.get(k), sort_keys=True)
               != json.dumps(after.get(k), sort_keys=True)]
    print(f"[evidence] wrote graph['{LAYER}'] into {p}")
    print(f"[evidence] additive check: "
          f"{'PASS' if not changed else 'FAIL ' + str(changed)} — "
          f"{len(before)} other top-level blocks compared")
    return layer


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--apply", action="store_true",
                    help="write graph['shown'] — the layer naming each "
                         "node's current picture. Without it the layer "
                         "is computed and reported but not written.")
    ap.add_argument("--reshoot", action="store_true",
                    help="attach the aimed pictures that serve each "
                         "reshoot node. Renders NOTHING — node_views.py "
                         "owns the GPU batch; run it first with "
                         "--layer settled --only <the reshoot ids>.")
    ap.add_argument("--recut", action="store_true",
                    help="perform the planned re-cuts (same photographs, "
                         "new rectangles; no GPU, nothing rendered). "
                         "Without it this module only decides.")
    a = ap.parse_args()
    sc = Scene(a.scene)
    rows = [plan_repair(judge(sc, nid)) for nid in sc.cur]
    out = sc.sd / "graph" / "node_evidence"
    out.mkdir(parents=True, exist_ok=True)
    cut = skip = shots = 0
    problems = []
    if a.recut:
        cut, skip = do_recuts(sc, rows, out)
    if a.reshoot:
        shots, problems = attach_reshoots(sc, rows)
    write_layer(sc, rows, a.apply)
    (out / "node_evidence.json").write_text(json.dumps(
        {"scene": a.scene, "layer": sc.layer, "status": "UNTESTED",
         "step": ("B2 — re-cuts PERFORMED (no GPU, nothing rendered). "
                  "B3 the reshoots (after the user's go), B4 writes the "
                  "`shown` layer." if a.recut else
                  "B1 — DECIDES ONLY. No pixels are written and nothing "
                  "is rendered. Pass --recut to perform the re-cuts."),
         "reshoot": {"attached": bool(a.reshoot), "pictures": shots,
                     "problems": problems,
                     "renders_nothing": "node_views.py owns the cameras "
                                        "and the GPU batch; this only "
                                        "resolves its decision to files "
                                        "that exist (a reused view's "
                                        "picture is an earlier run's, "
                                        "not node_views/)"},
         "recut": {"performed": bool(a.recut), "files": cut,
                   "skipped_degenerate": skip,
                   "dir": "graph/node_evidence/recut",
                   "note": "the same photograph cut to a new rectangle "
                           "around the CURRENT box, padded with the "
                           "context family. graph/crops is untouched — a "
                           "crop is the detection record."},
         "constants": {"INSIDE_FRAC": INSIDE_FRAC,
                       "ZOOM_FACTOR": ZOOM_FACTOR,
                       "ctx_pad": [CTX_PAD_SIDE, CTX_PAD_TOP,
                                   CTX_PAD_BOTTOM, CTX_MIN_PAD],
                       "note": "design defaults, NOT tuned on this scene; "
                               "the ctx pads are describe_nodes.py's, "
                               "re-used rather than re-invented"},
         "rows": rows}, indent=1))
    write_report(sc, rows, out)
    n, rep = {}, {}
    for r in rows:
        for f in r["fires"]:
            n[f] = n.get(f, 0) + 1
        rep[r["repair"]] = rep.get(r["repair"], 0) + 1
    print(f"layer {sc.layer}: {len(rows)} nodes, "
          f"{sum(1 for r in rows if r['fires'])} fire")
    for k, v in sorted(n.items(), key=lambda t: -t[1]):
        print(f"   {v:>3}  {k}")
    done = ([] + (["re-cuts taken"] if a.recut else [])
            + (["reshoots attached"] if a.reshoot else []))
    print("the repair plan"
          + (f" ({', '.join(done)}):" if done else " (nothing performed):"))
    for k, v in sorted(rep.items(), key=lambda t: -t[1]):
        print(f"   {v:>3}  {k}")
    blocked = [r["id"] for r in rows if r["repair"] == "blocked"]
    if blocked:
        print(f"   BLOCKED, named not dropped: {', '.join(blocked)}")
    if a.reshoot:
        print(f"reshoot pictures attached: {shots} "
              f"(rendered nothing — node_views owns the GPU)")
        for p in problems:
            print(f"   PROBLEM: {p}")
    if a.recut:
        print(f"re-cuts written: {cut}"
              + (f"  ({skip} skipped, degenerate)" if skip else "")
              + "   graph/crops untouched")
    else:
        want = sum(1 for r in rows if r["repair"] == "recut")
        print(f"nothing performed — {want} nodes want a re-cut; "
              f"pass --recut to take them")
    print(f"-> {out / 'index.html'}")


if __name__ == "__main__":
    main()
