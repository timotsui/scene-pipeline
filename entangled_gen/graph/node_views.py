"""NODE VIEWS — an aimed, rendered look at every node's CURRENT box.

USER RULING 2026-08-09, after the render-tiles sheet: the CPU tile is
out, the cardinal views work. Use them for the nodes whose stored crop
no longer matches the box (recrop_gate's "escaped" and "re-zoomed"), and
for a split piece — a box that never existed when anything was rendered
— take new ones the same way.

ONE RULE, NOT TWO CASES. The view set is a FUNCTION OF THE BOX. Recompute
the cameras from the node's current geometry and fingerprint them; a box
that moved gets different cameras and re-renders, a box that did not
keeps its pictures, and a box that never existed before has nothing to
keep. The split piece needs no special path — it falls out.

WHY THIS EXISTS AT ALL. A crop is a rectangle out of a photograph, so it
is stuck with that photograph's viewpoint and framing. 37 of 45 nodes
have crops that no longer frame their box. A rendered view is aimed at
the box, so it cannot drift from it by construction.

WHAT IS RENDERED, AND BY WHAT. The SAME WSL gsplat rasterizer
(analyzer/render_targets_wsl.py) that rendered the cube faces the
panorama is stitched from — so these pixels and the crops' pixels come
from one renderer and one file. 768x768, natural lens. NOT the CPU
point-splat painter in rendertools/03_render.py, which discards every
gaussian's orientation and was ruled out.

CROPS ARE NOT TOUCHED, AND NOTHING HERE OVERWRITES ONE. A crop records
what the detector actually saw; a render does not. They are different
kinds of evidence and this module adds the second without disturbing the
first. Which of them a given judge is shown is a separate decision, and
deliberately not made here.

THE STALENESS GATE. The WSL renderer SKIPS a target whose png already
exists, so a changed camera would silently reuse the old picture — the
exact failure that poisoned a sensing pass on 08-06 when pre-rescale
cube faces were re-stitched with a fresh eye. Every view therefore
carries a sidecar holding the hash of (eye, aim, fov, res, clip, ply
identity, box). Mismatch = the png is DELETED so the renderer must
redraw it. Match = crash-resume.

RENDERING IS THE DEFAULT (2026-08-11). The GPU pass used to need
--render, so a forgotten flag made this stage exit 0 having planned the
views and drawn none, and the next stage read whatever pictures the
PREVIOUS run happened to leave behind. An unattended pass over 100
scenes must not be able to succeed silently that way, so the default is
now "do the work" and --no-render is the explicit opt-out. --render is
still accepted and does nothing. Either way the plan file is written —
only the GPU work is optional.

    python graph/node_views.py --scene living_marble              # + GPU
    python graph/node_views.py --scene living_marble --no-render  # plan

Out: out/<scene>/graph/node_views/<node>_<view>.png + .params.json
     out/<scene>/graph/node_views.json     the view set per node
     out/<scene>/graph/node_views/index.html
"""
import argparse
import hashlib
import html
import json
import math
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
for p in (HERE, HERE.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))
import paths            # noqa: E402
import scene_state      # noqa: E402
import view_cams        # noqa: E402
import vote_cams        # noqa: E402

RES = 768               # the vote/pool render size — one size pipeline-wide

# THE REUSE RULE (user rulings 2026-08-09, set on the reuse_decision
# sheet). An existing shot is REUSED, not retaken, when it still frames
# TODAY'S box:
#   in-frame >= INSIDE_FRAC     essentially all of the box is inside the
#                               shot (recrop_gate's INSIDE_FRAC meaning)
#   zoom     >= 1/ZOOM_FACTOR   the shot shows the box at least 1/1.5 as
#                               large as a RETAKE would show it. The bar
#                               is the retake, NOT an abstract ideal —
#                               the obj_008 ruling: a clamped camera can
#                               never fill the frame with a 16 cm object,
#                               and the retake would stand in the same
#                               clamped spot, so demanding more than it
#                               can deliver buys nothing.
# The rule asks NOTHING about the old box: agreement measures (3D IoU)
# were tried and rejected — 2 cm on a 16 cm object destroys IoU with
# zero visible drift. A shot with no recorded camera can never pass.
INSIDE_FRAC = 0.95
ZOOM_FACTOR = 1.5
OPACITY_MIN = 0.30      # emptiness probe reads SOLID geometry only, as
#                         render_aimed_views does; splat haze is not a wall


def safe(nid):
    """Filename for a node id. A split piece is `obj_011#1`, and `#` is a
    fragment marker in a URL — the review page would silently request the
    wrong file. Recorded in node_views.json so nothing has to guess."""
    return nid.replace("#", "_p")


def to_wsl(p):
    p = str(Path(p).resolve())
    return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")


def shell_bounds(sd):
    """The measured room, in the frame the graph speaks. Read, never
    estimated — room_shell.py measured these against the collider."""
    sh = json.loads((sd / "room_shell.json").read_text())
    r2r = sh["frame"]["raw_to_render"]
    xs, zs = [], []
    for w in sh["walls"]:
        v = w["plane_upright_m"] * (r2r[0] if w["axis"] == "x" else r2r[2])
        (xs if w["axis"] == "x" else zs).append(v)
    return (min(xs), max(xs), min(zs), max(zs),
            sh["ceiling_y_raw"], sh["floor_y_raw"])


class Scene:
    def __init__(self, scene, layer=None):
        self.scene = scene
        self.sd = paths.scene_dir(scene)
        self.out = self.sd / "graph" / "node_views"
        self.g = json.loads((self.sd / "scene_graph.json").read_text())
        # THE LAYER MAY BE NAMED BY THE CALLER (2026-08-10). Default is
        # unchanged — whatever is current. But node_evidence must ask for
        # `settled` by name: it feeds J9, and `current` is `grouped`,
        # which is J9's OWN OUTPUT. That is not a hypothetical — J9's
        # SAME_PRODUCT rule writes the product size INTO member boxes,
        # so on living 3 of the 11 nodes it wants reshot have a
        # different box in grouped than in settled. Aiming at grouped
        # would frame the verdict's box and hand it back as evidence.
        self.layer = layer or scene_state.current_name(self.g)
        if layer:
            b = self.g.get(layer)
            got = b.get("nodes") if isinstance(b, dict) else None
            if not got:
                raise SystemExit(
                    f"[views] no whole `{layer}` layer — present: "
                    f"{', '.join(scene_state.present(self.g))}")
            self.cur = {n["id"]: n for n in got}
        else:
            self.cur = {n["id"]: n for n in scene_state.nodes(self.g)}
        # THE LAYER THE EXISTING PICTURES WERE SHOT FROM.
        # experiments/render_aimed_views.py reads g["resolved"] by name, so every
        # picture in aimed_views_resolved/ was framed on a RESOLVED box. Three
        # stages have edited the boxes since (voted, settled, grouped).
        # Keeping the old layer here is what lets the gate say WHY a
        # reshoot is needed instead of only that one is.
        self.prior = {n["id"]: n for n in
                      (self.g.get("resolved") or {}).get("nodes", [])}
        # THE REUSE POOL IS OUR OWN PRIOR RENDERS (2026-08-10, user
        # ruling: nothing may depend on what a future automated scene
        # will not produce). It used to be aimed_views_resolved/ — the
        # renders of experiments/render_aimed_views.py, the box method
        # that lost the 08-06 bake-off. That method does not run on a
        # fresh scene, so living reused 26 shots while scenes 2..100
        # would have reused none: the same code, two behaviours, and the
        # unattended one never exercised.
        #
        # Our own store is a better pool anyway. Every render we take
        # writes <safe-id>_<view>.params.json beside it holding the exact
        # eye/aim/fov — the same record pool_targets.json held, produced
        # by us, for every scene, with no other method required. First
        # run on any scene renders everything; later runs reuse whatever
        # still frames the box. One behaviour everywhere.
        self.pool = self.out
        self.pool_cams = {}
        for pf in sorted(self.out.glob("*.params.json")):
            try:
                t = json.loads(pf.read_text())
            except ValueError:
                continue
            if all(k in t for k in ("eye", "aim", "fov")):
                self.pool_cams[pf.name[:-len(".params.json")]] = t
        self.shell = shell_bounds(self.sd)
        self.eye0 = np.array(json.loads(
            (self.sd / "rig_sp0" / "pano_selfrender_meta.json")
            .read_text())["eye_raw"], float)
        self.ply = paths.ply(scene)
        st = self.ply.stat()
        self.ply_id = [self.ply.name, st.st_size, int(st.st_mtime)]
        print(f"[views] layer {self.layer}: {len(self.cur)} nodes", flush=True)
        print("[views] loading splat for the emptiness probe ...", flush=True)
        xyz, _, _, _ = paths.load_r3().load_splat(str(self.ply),
                                                  opacity_min=OPACITY_MIN)
        self.xyz = xyz
        print(f"[views] {len(xyz):,} solid gaussians", flush=True)

    def empty_at(self, eye):
        d = self.xyz - eye
        r = view_cams.EMPTY_R
        return int((np.einsum("ij,ij->i", d, d) < r * r).sum())

    def fov_fit(self, eye, aim, geo, fov0=None, margin=1.06):
        """The lens that contains this box from this eye. CLOSED FORM.

        The camera's ORIENTATION does not depend on its field of view —
        `make_cam` builds the basis from (eye, aim, up) and fov only sets
        the focal scale f = res / (2 tan(fov/2)). So the answer is direct:
        rotate the eight corners into camera space, take the largest
        |x|/z and |y|/z, and that ratio IS the tangent of the half-angle
        the box demands.

        (This started life as an iteration that rendered with a trial fov,
        measured the pixel overshoot and rescaled. It converged on the
        first pass and spent the second confirming — because the quantity
        it was computing reduces algebraically to the line below. User
        asked why it needed passes at all; it did not.)

        `fov0` is ignored, kept so the caller's signature does not change.
        Returns None if any corner is at or behind the camera plane."""
        lo = np.asarray(geo["aabb_min"], float)
        hi = np.asarray(geo["aabb_max"], float)
        pts = np.array([[x, y, z] for x in (lo[0], hi[0])
                        for y in (lo[1], hi[1]) for z in (lo[2], hi[2])],
                       np.float64)
        M = vote_cams.c2w_from_eye_aim(list(eye), list(aim), [0.0, -1.0, 0.0])
        R = np.stack([M[:3, 0], -M[:3, 1], M[:3, 2]])
        cam = (pts - np.asarray(eye, float)) @ R.T
        z = cam[:, 2]
        if (z <= 0.05).any():
            return None
        ratio = float(np.maximum(np.abs(cam[:, 0]) / z,
                                 np.abs(cam[:, 1]) / z).max())
        return 2 * math.degrees(math.atan(ratio * margin))

    def occluded_at(self, eye, centre, half):
        """How much solid stuff sits BETWEEN this eye and that box.

        The same idea slicevote culls with: a point counts as blocking
        when it lies inside the cone from eye to box AND is nearer than
        the box's near face. Deliberately cheap — one dot product per
        gaussian, no sorting, no rendering — because the main-photo
        search calls it once per candidate standpoint.

        A near-zero count is a clear line of sight. It does NOT promise
        a good picture: a thin object seen edge-on is unobstructed and
        still unreadable. It only rules out the camera being behind a
        wall or a sofa."""
        eye = np.asarray(eye, float)
        c = np.asarray(centre, float)
        to_c = c - eye
        d_c = float(np.linalg.norm(to_c))
        if d_c < 1e-6:
            return len(self.xyz)
        u = to_c / d_c
        rel = self.xyz - eye
        depth = rel @ u
        # only what is in FRONT of the eye and NEARER than the box
        near = (depth > 0.10) & (depth < d_c - half)
        if not near.any():
            return 0
        rel = rel[near]
        depth = depth[near]
        # perpendicular distance from the sight line, against the cone
        # that the box subtends at that depth
        perp2 = np.einsum("ij,ij->i", rel, rel) - depth * depth
        radius = half * (depth / d_c)          # cone widens with depth
        return int((perp2 < radius * radius).sum())


def fingerprint(sc, nid, v, geo):
    """What this picture IS. Any change to the camera, the lens, the
    clip, the box it was aimed at, or the file it was drawn from must
    change this hash — otherwise a stale png survives a real edit."""
    payload = {
        "node": nid,
        "view": v["view"],
        "eye": [round(float(x), 6) for x in v["eye"]],
        "aim": [round(float(x), 6) for x in v["aim"]],
        "fov": round(float(v["fov"]), 6),
        "clip_y_gt": (round(float(v["clip_y_gt"]), 6)
                      if v.get("clip_y_gt") is not None else None),
        "res": RES,
        "ply": sc.ply_id,
        "box": [round(float(x), 5)
                for x in list(geo["aabb_min"]) + list(geo["aabb_max"])],
    }
    h = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode()).hexdigest()[:12]
    return h, payload


def why_reshoot(sc, nid, v, geo):
    """The case for taking this picture, in numbers, or None if there is
    no case to make.

    A gate that only says "stale" cannot be reviewed — you have to take
    its word. So this reports what actually changed: the box, and how far
    the camera therefore moved.

    THE OLD CAMERA IS RECONSTRUCTED, NOT READ. render_aimed_views wrote no
    sidecar beside its renders, so nothing on disk records the camera
    that drew them. What is recorded is the LAYER it read (`resolved`),
    so the old camera is recomputed from the old box through this same
    module. Stated plainly here because a reconstructed number must never
    be mistaken for a measured one.
    """
    prior = sc.prior.get(nid)
    if prior is None:
        return {"kind": "no_prior_box",
                "text": "this box did not exist when anything was shot — "
                        "it was created after the `resolved` layer"}
    pg = prior.get("geometry") or {}
    if not pg.get("center"):
        return None
    a, b = np.array(geo["center"], float), np.array(pg["center"], float)
    sa = np.array(geo["size"], float)
    sb = np.array(pg["size"], float)
    d_ctr = float(np.linalg.norm(a - b))
    d_size = float(np.abs(sa - sb).max())
    out = {"kind": "box_changed",
           "centre_moved_m": round(d_ctr, 4),
           "size_changed_m": round(d_size, 4),
           "old_size": [round(float(x), 3) for x in sb],
           "new_size": [round(float(x), 3) for x in sa]}
    new_cam = view_cams.nominal_eye(geo, sc.eye0, v["view"])
    old_cam = view_cams.nominal_eye(pg, sc.eye0, v["view"])
    if new_cam and old_cam:
        out["camera_moved_m"] = round(
            float(np.linalg.norm(np.array(new_cam[0]) - np.array(old_cam[0]))),
            3)
        out["fov_changed_deg"] = round(new_cam[2] - old_cam[2], 1)
    out["text"] = (
        f"the box moved {d_ctr * 100:.0f} cm and changed size by "
        f"{d_size * 100:.0f} cm since the `resolved` layer these were "
        f"shot from"
        + (f", so the camera moves {out['camera_moved_m'] * 100:.0f} cm"
           if "camera_moved_m" in out else ""))
    return out


def _screen_ext(cam, geo):
    cn = box_corners(geo)
    u, vv, z = cam.project(cn)
    if not np.all(z > 0.05):
        return None
    return float(u.min()), float(u.max()), float(vv.min()), float(vv.max())


def reuse_test(sc, nid, v, geo):
    """Does an existing pool shot of this view still frame TODAY'S box
    (the reuse rule above)? Returns a record that EXPLAINS ITSELF either
    way — {"pass": bool, "reason": ...} — or None when no shot exists at
    all (nothing to test). A fail that only said "fail" could not be
    reviewed, and 44 unexplained reshoots is how this gap was found."""
    # OUR OWN FILENAMES, so a split piece keeps its identity. The old
    # pool was keyed `nid.split("#")[0]` because the demoted pass never
    # shot split pieces and obj_011#1 could only ever match its PARENT's
    # picture — a borrow dressed up as a reuse. safe() is the name we
    # write under, so obj_011#1 now matches obj_011_p1 and nothing else.
    stem = safe(nid)
    png = sc.pool / f"{stem}_{v['view']}.png"
    if not png.exists():
        return None
    t = sc.pool_cams.get(f"{stem}_{v['view']}")
    if not t:
        return {"pass": False, "prior_file": png.name,
                "reason": "no recorded camera — reuse cannot be verified"}
    old = _screen_ext(vote_cams.make_cam(t["eye"], t["aim"], t["fov"], RES),
                      geo)
    new = _screen_ext(vote_cams.make_cam(v["eye"], v["aim"], v["fov"], RES),
                      geo)
    if old is None or new is None:
        return {"pass": False, "prior_file": png.name,
                "reason": "today's box has a corner at or behind the "
                          "shot's camera"}
    x0, x1, y0, y1 = old
    area = (x1 - x0) * (y1 - y0)
    if area <= 0:
        return {"pass": False, "prior_file": png.name,
                "reason": "degenerate projection"}
    inf = (max(min(x1, RES) - max(x0, 0), 0)
           * max(min(y1, RES) - max(y0, 0), 0)) / area
    new_px = max(new[1] - new[0], new[3] - new[2])
    zoom = (max(x1 - x0, y1 - y0) / new_px) if new_px > 0 else 0.0
    rec = {"prior_file": png.name, "in_frame": round(inf, 3),
           "zoom_vs_retake": round(zoom, 3)}
    if inf >= INSIDE_FRAC and zoom >= 1.0 / ZOOM_FACTOR:
        return {**rec, "pass": True,
                "text": (f"reused: the old shot holds {inf:.0%} of "
                         f"today's box at {zoom:.2f}x the zoom a retake "
                         "would give")}
    why = []
    if inf < INSIDE_FRAC:
        why.append(f"only {inf:.0%} of today's box is inside the shot "
                   f"(needs {INSIDE_FRAC:.0%})")
    if zoom < 1.0 / ZOOM_FACTOR:
        why.append(f"the shot shows the box at {zoom:.2f}x the size a "
                   f"retake would (needs {1/ZOOM_FACTOR:.2f}x)")
    return {**rec, "pass": False, "reason": "; ".join(why)}


def gate(sc, nid, v, geo, suffix=""):
    """Fingerprint one view, drop a stale png, write the sidecar.

    Returns (status, stem, hash, why):
      keep         the picture on disk was drawn by THIS camera
      to_be_shot   no picture of this node from this view has ever existed
      to_be_reshot a picture exists but was framed on a box that has moved
    """
    h, payload = fingerprint(sc, nid, v, geo)
    stem = f"{safe(nid)}_{v['view']}{suffix}"
    png, side = sc.out / f"{stem}.png", sc.out / f"{stem}.params.json"
    old = None
    if side.exists():
        try:
            old = json.loads(side.read_text()).get("hash")
        except Exception as e:                               # noqa: BLE001
            print(f"[views] sidecar {side.name} unreadable ({e}) — "
                  "treating the render as stale", flush=True)
    fresh = (old == h)
    if png.exists() and not fresh:
        png.unlink()
        print(f"[views] {stem}: {old or 'NO sidecar'} -> {h} — png DELETED",
              flush=True)
    # The sidecar is how a LATER run knows which camera drew the png next
    # to it, so a half-written one either costs a GPU re-render or, worse,
    # parses with the wrong hash. It is small; write it whole or not at all.
    paths.write_atomic(side, json.dumps({"hash": h, **payload}, indent=1))
    if png.exists():
        return "keep", stem, h, None
    # Is there an OLDER picture of this view, from before this module
    # existed? render_aimed_views's renders are the only ones, and a split piece
    # has none because its box is younger than they are.
    if suffix:
        return "to_be_shot", stem, h, {"kind": "audit_render",
                                       "text": "a camera the cull rejected, rendered so the rejection can be judged"}
    ru = reuse_test(sc, nid, v, geo)
    if ru is not None and ru.get("pass"):
        return "reuse_prior", stem, h, ru
    why = why_reshoot(sc, nid, v, geo)
    if ru is not None:
        return "to_be_reshot", stem, h, {**(why or {}),
                                         "prior_file": ru["prior_file"],
                                         "reuse_fail": ru}
    return "to_be_shot", stem, h, why


def plan(sc, include_culled=False, culled_only=False):
    """Decide the whole scene's view set. Renders nothing.

    Culled cameras are queued AHEAD of kept ones. A batch that is
    interrupted then leaves the audit complete rather than half a
    set of pictures nobody was asking about — which is exactly how
    the first attempt at this was wasted.
    """
    rows, kept_targets, cull_targets = [], [], []
    for nid, node in sc.cur.items():
        geo = node.get("geometry") or {}
        if not geo.get("aabb_min"):
            rows.append({"id": nid, "name": node.get("name"),
                         "views": [], "dropped": [],
                         "note": "no geometry — nothing to aim at"})
            continue
        views, dropped = view_cams.candidates(geo, sc.eye0, sc.shell,
                                              sc.empty_at)
        # THE MAIN PHOTO GOES FIRST, and it is a different kind of view:
        # the others are "look at it from that side", this one is "the
        # one picture of this object", searched for at eye level as near
        # the capture standpoint as the room allows.
        mv, mwhy = view_cams.main_view_cam(geo, sc.eye0, sc.shell,
                                           sc.empty_at, sc.occluded_at,
                                           fov_fit=sc.fov_fit)
        if mv is not None:
            views = [mv] + views
            print(f"[views] {nid:<12} MAIN {mv['dist_to_object']:.2f} m "
                  f"from the object, {mv['dist_to_default']:.2f} m from "
                  f"the standpoint, fov {mv['fov']:.0f} deg "
                  f"({mv['considered']} of {mv['of_candidates']} "
                  f"standpoints tried)", flush=True)
        else:
            dropped.append({"view": "main", "why": [mwhy], "tried": [],
                            "aim": [float(x) for x in
                                    (geo.get("center") or [0, 0, 0])]})
            print(f"[views] {nid:<12} MAIN — NONE: {mwhy}", flush=True)
        vrows = []
        for v in views:
            status, stem, h, why = gate(sc, nid, v, geo)
            need = status in ("to_be_shot", "to_be_reshot")
            vrows.append({**v, "file": f"{stem}.png", "hash": h,
                          "status": status, "why": why,
                          "needs_render": need})
            if need and not culled_only:
                kept_targets.append({
                    "name": stem, "label": f"{nid} {node.get('name')}",
                    "eye": v["eye"], "aim": v["aim"], "fov": v["fov"],
                    **({"clip_y_gt": v["clip_y_gt"]}
                       if v.get("clip_y_gt") is not None else {})})
        # THE CULLED CAMERAS, AS PICTURES (user 2026-08-09: "let me see
        # what we are culling"). A cull reported as geometry asks the
        # reader to trust the geometry. Rendered, it is a picture you can
        # judge: a camera 20 cm past a wall plane may still see the
        # object perfectly well, and if it does the cull is too strict.
        # These are AUDIT ONLY — named apart so nothing downstream can
        # mistake one for a view this module kept.
        crows = []
        if include_culled:
            for d in dropped:
                t = (d.get("tried") or [{}])[0]
                if not t.get("eye"):
                    continue
                c = np.array(geo["center"], float)
                eye = np.array(t["eye"], float)
                cv = {"view": d["view"], "eye": t["eye"],
                      "aim": [float(x) for x in c],
                      "fov": view_cams.fov_for(
                          float(max(geo["size"])) / 2,
                          float(np.linalg.norm(eye - c))),
                      "culled": True, "why": d["why"]}
                status, stem, hh, _ = gate(sc, nid, cv, geo,
                                           suffix="__culled")
                cv.update({"file": f"{stem}.png", "hash": hh,
                           "needs_render": status != "keep"})
                crows.append(cv)
                if cv["needs_render"]:
                    cull_targets.append({
                        "name": stem,
                        "label": f"{nid} {node.get('name')} CULLED "
                                 f"{d['view']}",
                        "eye": cv["eye"], "aim": cv["aim"],
                        "fov": cv["fov"]})
        n_card = sum(1 for v in vrows if v["view"].startswith("card"))
        rows.append({"id": nid, "name": node.get("name"),
                     "safe": safe(nid), "size": geo.get("size"),
                     "geometry": geo,
                     "views": vrows, "culled_views": crows,
                     "dropped": dropped,
                     "n_views": len(vrows), "n_cardinal": n_card})
        print(f"[views] {nid:<12} {len(vrows)} views "
              f"({', '.join(v['view'] for v in vrows) or 'NONE'})"
              f"{'  +' + str(sum(1 for v in vrows if v['needs_render'])) + ' to render' if any(v['needs_render'] for v in vrows) else ''}",
              flush=True)
        for d in dropped:
            print(f"[views]      dropped {d['view']}: {'; '.join(d['why'])}",
                  flush=True)
    return rows, cull_targets + kept_targets


BOX_EDGES = ((0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6),
             (6, 4), (0, 4), (1, 5), (2, 6), (3, 7))


def box_corners(geo):
    lo, hi = geo["aabb_min"], geo["aabb_max"]
    return np.array([[x, y, z] for x in (lo[0], hi[0])
                     for y in (lo[1], hi[1]) for z in (lo[2], hi[2])],
                    float)


def whole_image(p):
    """True if the png on disk is a complete, readable picture.

    The module docstring's fingerprint promise covers the WSL renders,
    which carry a params sidecar and a hash compare. The box overlays
    below have neither: they are judged fresh purely by being newer than
    their source. A power cut during the save (docs/POWER_CRASHES.md)
    leaves a truncated png whose mtime is newer than its source, so every
    later run would keep it, and node_evidence would hand exactly that
    file to J9 as the node's one picture of the object. An unattended run
    has to repair a half-written picture, not present it as evidence.

    verify() reads the file's structure without decoding the pixels, so
    it is cheap, and it raises on a file that stops early. Pillow leaves
    the image object unusable afterwards, which is why this opens the
    file only to check it and the caller re-opens for the real read.
    """
    from PIL import Image
    try:
        with Image.open(p) as im:
            im.verify()
        return True
    except Exception:                                        # noqa: BLE001
        return False


def draw_boxes(sc, rows):
    """Draw each node's box onto every picture taken of it.

    THE CAMERA IS NOT RE-DERIVED. vote_cams.make_cam is the projection
    already shared by the vote and the J8 judge sheets, and it matches
    the convention render_targets_wsl.py rasterises with. Rebuilding the
    maths here would be the second copy the shared module exists to
    prevent.

    Without the box drawn, a view only shows that SOMETHING was rendered.
    With it, the picture answers the question actually being asked: does
    this box contain this object.
    """
    import vote_cams
    from PIL import Image, ImageDraw
    n = 0
    for r in rows:
        geo = r.get("geometry")
        if not geo:
            continue
        cn = box_corners(geo)
        for v in list(r.get("views", [])) + list(r.get("culled_views", [])):
            src = sc.out / v["file"]
            if not src.exists():
                continue
            dst = sc.out / v["file"].replace(".png", "_box.png")
            # The mtime test comes first because it is the cheap one: a
            # picture older than its source is being redrawn anyway and
            # never needs reading. Only a picture that looks fresh is
            # opened and checked, because "fresh" here is a guess made
            # from a timestamp, and a png cut off mid-save looks fresher
            # than the picture it was drawn from.
            if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
                if whole_image(dst):
                    v["box_file"] = dst.name
                    continue
                dst.unlink()
                print(f"[views] {dst.name}: truncated png (a run died "
                      "while saving it) — DELETED, drawing it again",
                      flush=True)
            im = Image.open(src).convert("RGB")
            cam = vote_cams.make_cam(v["eye"], v["aim"], v["fov"], im.width)
            u, vv, z = cam.project(cn)
            dr = ImageDraw.Draw(im)
            drawn = 0
            for a, b in BOX_EDGES:
                # An edge with a corner at or behind the image plane
                # cannot be drawn honestly, so it is left out rather than
                # guessed at. How many were skipped is recorded.
                if z[a] <= 0.05 or z[b] <= 0.05:
                    continue
                dr.line([(u[a], vv[a]), (u[b], vv[b])],
                        fill=(255, 214, 102), width=3)
                drawn += 1
            im.save(dst)
            v["box_file"] = dst.name
            v["box_edges_drawn"] = drawn
            n += 1
    print(f"[views] box drawn on {n} pictures", flush=True)


def render(sc, targets):
    """One WSL gsplat batch. The renderer skips any png already on disk,
    which is safe here ONLY because gate() deleted the stale ones."""
    tf = sc.out / "render_targets.json"
    tf.write_text(json.dumps(targets, indent=1))
    cmd = ("wsl -d Ubuntu-24.04 -- bash -c \"cd /root/splat_analyzer && "
           "/root/miniconda3/envs/splatanalyzer/bin/python "
           f"'{to_wsl(HERE.parent / 'analyzer' / 'render_targets_wsl.py')}' "
           f"--targets '{to_wsl(tf)}' --ply '{to_wsl(sc.ply)}' "
           f"--out '{to_wsl(sc.out)}' --res {RES}\"")
    print(f"[views] rendering {len(targets)} views via WSL gsplat "
          f"(~{len(targets) * 1.6 / 60:.0f} min, 1 s GPU pacing each) ...",
          flush=True)
    subprocess.run(cmd, check=True, timeout=7200, shell=True)


CSS = """
body{font:15px/1.55 system-ui,sans-serif;margin:0;padding:28px;
     background:#14161a;color:#e8eaed}
h1{font-size:21px;margin:0 0 6px} p{max-width:80ch;color:#b9bec7}
.key{background:#1c1f25;border:1px solid #2a2f38;border-radius:8px;
     padding:14px 18px;max-width:80ch;margin:16px 0 10px}
.key b{color:#e8eaed}
.tally{display:flex;gap:10px;flex-wrap:wrap;margin:14px 0 26px}
.pill{border-radius:7px;padding:9px 14px;font-size:13px;
      border:1px solid #2a2f38;background:#1c1f25}
.pill b{font-size:19px;display:block;line-height:1.25}
.row{border-top:1px solid #2a2f38;padding:18px 0}
.hd{display:flex;gap:12px;align-items:baseline;flex-wrap:wrap}
.id{font-weight:600;font-size:16px}
.meta{font-size:12.5px;color:#8b93a1}
.reason{font-size:13px;color:#ffd166;margin:7px 0 0;max-width:80ch}
.band{display:flex;gap:16px;flex-wrap:wrap;margin-top:14px}
.cell{width:250px}
.cap{font-size:11.5px;color:#8b93a1;margin-top:5px;line-height:1.45}
.drop{color:#ff8b6b;font-size:12px;margin-top:9px}
img{display:block;border-radius:5px;background:#0d0f12;width:250px}
a{color:#7fb2ff;text-decoration:none} a:hover{text-decoration:underline}
.tag{display:inline-block;font-size:10.5px;font-weight:700;
     letter-spacing:.07em;padding:3px 8px;border-radius:4px;
     margin-bottom:7px}
.t_shot{background:#4a3410;color:#ffd166;border:1px solid #6b4a14}
.t_reshot{background:#4a1f14;color:#ff9b7b;border:1px solid #6e2e1e}
.t_keep{background:#12351f;color:#7fe0a0;border:1px solid #1d5230}
.slot{width:250px;height:250px;border:1px dashed #6b4a14;border-radius:5px;
      display:flex;align-items:center;justify-content:center;
      color:#ffd166;font-size:13px;font-weight:600;text-align:center;
      padding:10px;background:#1a1712}
.old{opacity:.8}
.cell.reshot{outline:2px solid #a03d28;outline-offset:3px;border-radius:6px;background:#1d1512;padding:4px}
.r{color:#ff8b6b}
.lab{font-size:11px;text-transform:uppercase;letter-spacing:.07em;color:#6b7280;margin:14px 0 2px;font-weight:700}
.cullwrap{display:flex;gap:20px;align-items:flex-start;margin-top:16px;
          flex-wrap:wrap}
.cullmap{background:#101317;border:1px solid #2a2f38;border-radius:6px;
         padding:6px;line-height:0}
.culltext{flex:1;min-width:min(100%,30ch)}
.legend{font-size:12px;color:#8b93a1;margin:6px 0 0}
.sw{display:inline-block;width:10px;height:10px;border-radius:50%;
    margin:0 5px 0 12px;vertical-align:-1px}
"""

STATUS_TAG = {"to_be_shot": ("TO BE SHOT", "t_shot"),
              "to_be_reshot": ("TO BE RESHOT", "t_reshot"),
              "reuse_prior": ("REUSED", "t_keep"),
              "keep": ("KEEP", "t_keep")}

PPM = 34          # px per metre on the room map
MAP_PAD = 26      # px of margin so a camera outside the room still draws


def cull_map(sc, row, geo):
    """A top-down map of the room with every camera drawn where it WANTED
    to stand — kept ones filled, culled ones hollow and red, each joined
    to the object it was aiming at.

    This exists because a cull reported only as a sentence is not
    reviewable: the reader has to trust that the camera really did land
    outside. Drawn, it is one look. North is +z, east is +x, matching the
    numbers in the drop reasons.
    """
    xlo, xhi, zlo, zhi = sc.shell[:4]
    pad = view_cams.WALL_PAD
    pts = [(v["eye"][0], v["eye"][2]) for v in row["views"]]
    for d in row.get("dropped", []):
        pts += [(t["eye"][0], t["eye"][2]) for t in d.get("tried", [])]
    x0 = min([xlo] + [p[0] for p in pts]) - 0.4
    x1 = max([xhi] + [p[0] for p in pts]) + 0.4
    z0 = min([zlo] + [p[1] for p in pts]) - 0.4
    z1 = max([zhi] + [p[1] for p in pts]) + 0.4
    W = (x1 - x0) * PPM + 2 * MAP_PAD
    H = (z1 - z0) * PPM + 2 * MAP_PAD

    def sx(x):
        return MAP_PAD + (x - x0) * PPM

    def sz(z):                       # +z drawn upward, so the map reads
        return H - MAP_PAD - (z - z0) * PPM   # like a floor plan

    s = [f'<svg viewBox="0 0 {W:.0f} {H:.0f}" width="{W:.0f}" '
         f'height="{H:.0f}" style="max-width:100%">',
         f'<rect x="{sx(xlo):.1f}" y="{sz(zhi):.1f}" '
         f'width="{(xhi - xlo) * PPM:.1f}" height="{(zhi - zlo) * PPM:.1f}" '
         'fill="#1b1e24" stroke="#5a6472" stroke-width="2"/>',
         f'<rect x="{sx(xlo + pad):.1f}" y="{sz(zhi - pad):.1f}" '
         f'width="{(xhi - xlo - 2 * pad) * PPM:.1f}" '
         f'height="{(zhi - zlo - 2 * pad) * PPM:.1f}" fill="none" '
         'stroke="#3d4550" stroke-width="1" stroke-dasharray="4 4"/>']
    lo, hi = geo["aabb_min"], geo["aabb_max"]
    s.append(f'<rect x="{sx(lo[0]):.1f}" y="{sz(hi[2]):.1f}" '
             f'width="{max((hi[0] - lo[0]) * PPM, 2):.1f}" '
             f'height="{max((hi[2] - lo[2]) * PPM, 2):.1f}" '
             'fill="#7fb2ff" fill-opacity=".30" stroke="#7fb2ff"/>')
    s.append(f'<circle cx="{sx(sc.eye0[0]):.1f}" cy="{sz(sc.eye0[2]):.1f}" '
             'r="4" fill="none" stroke="#8b93a1" stroke-width="1.5"/>')
    for v in row["views"]:
        ex, ez = sx(v["eye"][0]), sz(v["eye"][2])
        ax, az = sx(v["aim"][0]), sz(v["aim"][2])
        s.append(f'<line x1="{ex:.1f}" y1="{ez:.1f}" x2="{ax:.1f}" '
                 f'y2="{az:.1f}" stroke="#7fe0a0" stroke-width="1" '
                 'stroke-opacity=".55"/>')
        s.append(f'<circle cx="{ex:.1f}" cy="{ez:.1f}" r="5" '
                 'fill="#7fe0a0"/>')
        s.append(f'<text x="{ex + 8:.1f}" y="{ez + 4:.1f}" fill="#7fe0a0" '
                 f'font-size="11">{html.escape(v["view"])}</text>')
    for d in row.get("dropped", []):
        aim = d.get("aim")
        for t in d.get("tried", []):
            ex, ez = sx(t["eye"][0]), sz(t["eye"][2])
            if aim:
                s.append(f'<line x1="{ex:.1f}" y1="{ez:.1f}" '
                         f'x2="{sx(aim[0]):.1f}" y2="{sz(aim[2]):.1f}" '
                         'stroke="#ff8b6b" stroke-width="1" '
                         'stroke-dasharray="3 3" stroke-opacity=".45"/>')
            s.append(f'<circle cx="{ex:.1f}" cy="{ez:.1f}" r="5" '
                     'fill="none" stroke="#ff8b6b" stroke-width="1.6"/>')
        if d.get("tried"):
            t = d["tried"][0]
            s.append(f'<text x="{sx(t["eye"][0]) + 8:.1f}" '
                     f'y="{sz(t["eye"][2]) + 4:.1f}" fill="#ff8b6b" '
                     f'font-size="11">{html.escape(d["view"])}</text>')
    s.append("</svg>")
    return "".join(s)



def tile(sc, v, kind):
    """One picture on the sheet: the render with the node's box drawn on
    it, or a labelled placeholder when it has not been taken yet."""
    e = html.escape
    label, cls = (("KEPT", "t_keep") if kind == "keep"
                  else ("CULLED", "t_reshot"))
    if kind == "keep":
        label, cls = STATUS_TAG[v.get("status", "to_be_shot")]
    src = v.get("box_file") or v["file"]
    w = v.get("why") or {}
    if v.get("status") == "reuse_prior":
        rel = f'{w.get("prior_file", "")}'
        body = f'<a href="{rel}"><img src="{rel}"></a>'
    elif v.get("status") == "to_be_reshot" and w.get("prior_file"):
        # the evidence picture: the reuse_decision annotated copy has
        # BOTH boxes drawn on the shot being rejected (blue = the box it
        # was aimed at, yellow = today's); fall back to the raw shot
        ann = sc.sd / "graph" / "reuse_decision" / v["file"]
        rel = (f'../reuse_decision/{v["file"]}' if ann.exists()
               else f'{w["prior_file"]}')
        body = f'<a href="{rel}"><img class="old" src="{rel}"></a>'
    else:
        body = (f'<a href="{src}"><img src="{src}"></a>'
                if (sc.out / src).exists()
                else f'<div class="slot">TO BE SHOT<br>'
                     f'<span style="font-weight:400">{e(v["view"])}</span>'
                     "</div>")
    cap = [f'<b>{e(v["view"])}</b> &middot; fov {v["fov"]:.0f}']
    if kind == "cull":
        cap.append(e(v["why"][0]) if v.get("why") else "culled")
    else:
        w = v.get("why") or {}
        if "camera_moved_m" in w:
            cap.append(f'camera moves {w["camera_moved_m"] * 100:.0f} cm')
        if w.get("prior_file"):
            cap.append(f'<a href="{w["prior_file"]}">'
                       "the old picture</a>")
    cell_cls = "cell reshot" if v.get("status") == "to_be_reshot" \
        else "cell"
    if v.get("status") == "to_be_reshot" and (v.get("why") or {}) \
            .get("reuse_fail"):
        cap.append('<span class="r">'
                   + e((v["why"]["reuse_fail"].get("reason") or ""))
                   + "</span>")
    return (f'<div class="{cell_cls}"><span class="tag {cls}">{label}'
            f'</span>{body}<div class="cap">{" &middot; ".join(cap)}'
            "</div></div>")


def write_report(sc, rows, n_pending):
    e = html.escape
    tally = {"keep": 0, "to_be_shot": 0, "to_be_reshot": 0,
             "reuse_prior": 0}
    for r in rows:
        for v in r.get("views", []):
            st = v.get("status", "to_be_shot")
            tally[st] = tally.get(st, 0) + 1
    n_moved = sum(1 for r in rows if any(
        (v.get("why") or {}).get("kind") == "box_changed"
        for v in r.get("views", [])))
    n_newbox = sum(1 for r in rows if any(
        (v.get("why") or {}).get("kind") == "no_prior_box"
        for v in r.get("views", [])))
    # HOW BIG THE CHANGES ACTUALLY ARE. "Every box changed" is true and
    # nearly useless on its own — it is also true when a box moved half a
    # millimetre. The gate fires on ANY change, so the distribution is
    # the number that shows whether it is over-firing.
    # why the reshoots fail, tallied for the header
    fail_kinds = {"out of frame": 0, "zoom too low": 0, "both": 0,
                  "no recorded camera": 0, "behind camera": 0}
    for r in rows:
        for v in r.get("views", []):
            f = (v.get("why") or {}).get("reuse_fail")
            if v.get("status") != "to_be_reshot" or not f:
                continue
            rr = f.get("reason") or ""
            if "no recorded camera" in rr:
                fail_kinds["no recorded camera"] += 1
            elif "behind" in rr:
                fail_kinds["behind camera"] += 1
            elif "inside the shot" in rr and "retake would" in rr:
                fail_kinds["both"] += 1
            elif "inside the shot" in rr:
                fail_kinds["out of frame"] += 1
            elif "retake would" in rr:
                fail_kinds["zoom too low"] += 1
    deltas = sorted(max(w.get("centre_moved_m", 0), w.get("size_changed_m", 0))
                    for r in rows
                    for w in [next((v.get("why") for v in r.get("views", [])
                                    if (v.get("why") or {}).get("kind")
                                    == "box_changed"), None)] if w)
    med = deltas[len(deltas) // 2] if deltas else 0.0
    tiny = sum(1 for d in deltas if d < 0.01)
    h = [f"<style>{CSS}</style>",
         "<h1>Why every one of these has to be shot</h1>",
         "<p>The camera is aimed at the box. Move the box and the picture "
         "is of the wrong place, so the gate's only question is whether "
         "the box a picture was framed on is still the box the node has. "
         "Each view below says which it is, and the ones not yet taken "
         "are marked <b>TO BE SHOT</b>.</p>",
         '<div class="key">'
         "<b>What the existing pictures were framed on.</b> Every render "
         "reused here was shot by an EARLIER RUN of this module, from the box as it stood then "
         "layer, because that is the layer that module reads by name. "
         "Three stages have edited the boxes since &mdash; "
         "<code>voted</code> elected new ones, <code>settled</code> "
         "applied the split and box rulings, <code>grouped</code> is "
         f"current. <b>All {n_moved} boxes changed</b>, by a median of "
         f"<b>{med * 100:.0f} cm</b>"
         + (f" &mdash; but {tiny} of them changed by under a centimetre, "
            "and this gate fires on any change at all. Those "
            f"{tiny} are the ones to look at if you think it is "
            "over-firing." if tiny else "")
         + (f" A further {n_newbox} box did not exist at all."
            if n_newbox else "") +
         "<br><br>"
         "<b>Nothing could have been kept on this run in any case.</b> "
         "This folder is new, so there is no picture of any node to "
         "keep &mdash; the pictures reused here are in "
         "another folder, under another naming scheme, with no sidecar "
         "recording what camera drew them, so they are linked for "
         "comparison and never reused. The keep/reshoot distinction only "
         "starts saving work on the SECOND run.<br><br>"
         "<b>The old camera is reconstructed, not read.</b> "
         "<code>render_aimed_views</code> wrote no sidecar beside its renders, so "
         "nothing on disk records the camera that drew them. What is "
         "recorded is the layer it read, so the old camera is recomputed "
         "from the old box through the same module. Said plainly because "
         "a reconstructed number must not be mistaken for a measured "
         "one.<br><br>"
         "<b>Coverage is uneven and that is physical.</b> A camera must "
         "stand inside the room, 0.3 m off every wall, at least 1.2 m "
         "back. The room is 5.28 m across its narrow axis, so an object "
         "on a wall has nowhere to stand on that side. Every culled view "
         "says which wall killed it, under its row.</div>",
         '<div class="tally">'
         f'<div class="pill" style="border-color:#6b4a14"><b>'
         f'{tally["to_be_shot"]}</b>to be shot</div>'
         f'<div class="pill" style="border-color:#6e2e1e"><b>'
         f'{tally["to_be_reshot"]}</b>to be reshot</div>'
         f'<div class="pill" style="border-color:#1d5230"><b>'
         f'{tally["keep"]}</b>kept as they are</div>'
         f'<div class="pill" style="border-color:#2a5578"><b>'
         f'{tally["reuse_prior"]}</b>existing shots reused</div>'
         "</div>",
         '<div class="key"><b>Why the reshoots fail the reuse test</b> '
         "(each reshot cell below is outlined red and carries its own "
         "reason):<br>"
         + " &middot; ".join(f"<b>{v}</b> {k}"
                             for k, v in fail_kinds.items() if v)
         + "</div>"]

    # ---- THE CULL, CHECKED AGAINST THE ONLY OTHER OPINION ON DISK ----
    # render_aimed_views ran the same cull on the OLD boxes. Where it produced a
    # picture and this run culls the same view, the two disagree, and a
    # disagreement is the only cheap evidence available that the cull is
    # wrong. Shown first, in full, rather than buried in the rows.
    clash = []
    for r in rows:
        for d in r.get("dropped", []):
            p = sc.pool / f'{r["id"]}_{d["view"]}.png'
            if p.exists():
                clash.append((r, d, p))
    n_drop = sum(len(r.get("dropped", [])) for r in rows)
    h.append("<h2 style='font-size:17px;margin:26px 0 4px'>The cull, "
             "checked against the pictures that already exist</h2>"
             f"<p><code>render_aimed_views</code> ran this same cull on the OLD "
             f"boxes. Of the <b>{n_drop}</b> views culled now, "
             f"<b>{n_drop - len(clash)}</b> it also had no picture for "
             f"&mdash; the two agree. <b>{len(clash)}</b> it did shoot, "
             "and those are the only cases where this cull can be shown "
             "to be wrong. Each is below with the picture it took.</p>")
    if clash:
        h.append('<div class="band">')
        for r, d, p in clash:
            w = next((v.get("why") for v in r["views"] if v.get("why")), {})
            h.append('<div class="cell" style="width:300px">'
                     f'<span class="tag t_reshot">CULLED NOW</span>'
                     f'<a href="{p.name}">'
                     f'<img class="old" style="width:300px" '
                     f'src="{p.name}"></a>'
                     f'<div class="cap"><b>{e(r["id"])} {e(d["view"])}</b> '
                     f'&middot; {e(str(r.get("name")))}<br>'
                     f'{e("; ".join(d["why"][:1]))}<br>'
                     + (e(w.get("text", "")) if w else "") + "</div></div>")
        h.append("</div>")
    h.append('<p class="legend">On every map below: '
             '<span class="sw" style="background:#7fe0a0"></span>a camera '
             'that was kept &nbsp;'
             '<span class="sw" style="border:2px solid #ff8b6b"></span>'
             'where a culled camera wanted to stand &nbsp;'
             '<span class="sw" style="background:#7fb2ff;'
             'border-radius:2px"></span>the object &nbsp;'
             '<span class="sw" style="border:2px solid #8b93a1"></span>'
             'the observation standpoint. Solid outline = the room, '
             'dashed = the 0.3 m camera keep-out. +z is up, +x is '
             'right.</p>')
    for r in rows:
        h.append('<div class="row"><div class="hd">'
                 f'<span class="id">{e(r["id"])}</span>'
                 f'<span class="meta">{e(str(r.get("name")))}'
                 + (f' &middot; {" x ".join(f"{v:.2f}" for v in r["size"])} m'
                    if r.get("size") else "")
                 + f' &middot; {r.get("n_views", 0)} views, '
                   f'{r.get("n_cardinal", 0)} cardinal</span></div>')
        whys = [v["why"] for v in r.get("views", []) if v.get("why")]
        if whys:
            h.append(f'<div class="reason">{e(whys[0]["text"])}'
                     + (f' &middot; old size {whys[0]["old_size"]} m '
                        f'&rarr; new {whys[0]["new_size"]} m'
                        if "old_size" in whys[0] else "") + "</div>")
        h.append('<div class="lab">KEPT &mdash; these get used</div>'
                 '<div class="band">')
        for v in r["views"]:
            h.append(tile(sc, v, "keep"))
        h.append("</div>")
        if r.get("culled_views"):
            h.append('<div class="lab" style="color:#ff8b6b;margin-top:16px">'
                     "CULLED &mdash; rendered here ONLY so you can judge "
                     "the rejection; nothing downstream reads these</div>"
                     '<div class="band">')
            for v in r["culled_views"]:
                h.append(tile(sc, v, "cull"))
            h.append("</div>")
        elif r.get("dropped"):
            h.append('<div class="lab" style="color:#ff8b6b;margin-top:16px">'
                     f'CULLED &mdash; {len(r["dropped"])} views, not '
                     "rendered (re-run with <code>--include-culled</code> "
                     "to see them)</div>")
        if r.get("dropped"):
            h.append('<div class="cullwrap"><div class="cullmap">'
                     + cull_map(sc, r, sc.cur[r["id"]]["geometry"])
                     + '</div><div class="culltext">')
            for d in r["dropped"]:
                had = (sc.pool / f'{r["id"]}_{d["view"]}.png')
                h.append(f'<div class="drop">no <b>{e(d["view"])}</b> — '
                         f'{e("; ".join(d["why"]) or "no standpoint passed")}'
                         + (' &middot; <a href="'
                            f'{had.name}">but an earlier run DID shoot this '
                            "view, on the old box</a>"
                            if had.exists() else "") + "</div>")
            h.append("</div></div>")
        if r.get("note"):
            h.append(f'<div class="drop">{e(r["note"])}</div>')
        h.append("</div>")
    (sc.out / "index.html").write_text("\n".join(h), encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--render", action="store_true",
                    help="accepted for backward compatibility; rendering "
                         "is now the default (use --no-render to opt out)")
    ap.add_argument("--no-render", dest="no_render", action="store_true",
                    help="plan the views but render nothing (no GPU)")
    ap.add_argument("--include-culled", action="store_true",
                    help="also render the cameras the cull REJECTED, so "
                         "the rejection can be judged from a picture "
                         "instead of from geometry. Audit only — these "
                         "are named apart and nothing downstream reads "
                         "them.")
    ap.add_argument("--culled-only", action="store_true",
                    help="render ONLY the rejected cameras — the audit, "
                         "without paying for the kept views first")
    ap.add_argument("--only", default="",
                    help="comma-separated node ids (default: every node)")
    ap.add_argument("--layer", default="",
                    help="aim at this layer's boxes by NAME instead of "
                         "whatever is current. node_evidence passes "
                         "`settled`, because current is `grouped` and "
                         "grouped is J9's own output.")
    a = ap.parse_args()
    sc = Scene(a.scene, a.layer or None)
    if a.only:
        want = set(a.only.split(","))
        missing = sorted(want - set(sc.cur))
        if missing:
            raise SystemExit(f"[views] not in layer {sc.layer}: {missing}")
        sc.cur = {k: v for k, v in sc.cur.items() if k in want}
    sc.out.mkdir(parents=True, exist_ok=True)
    inc = a.include_culled or a.culled_only
    rows, targets = plan(sc, inc, a.culled_only)
    if targets and not a.no_render:
        render(sc, targets)
        rows, targets = plan(sc, inc, a.culled_only)  # report truth
    draw_boxes(sc, rows)
    # node_evidence reads this file and refuses to attach pictures if it
    # disagrees with the layer it was aimed at, so a half-written copy
    # would stop the next stage dead. Written beside itself and renamed.
    paths.write_atomic(sc.sd / "graph" / "node_views.json", json.dumps(
        {"scene": a.scene, "layer": sc.layer, "res": RES,
         "renderer": "analyzer/render_targets_wsl.py (WSL gsplat)",
         "cameras": "graph/view_cams.py",
         "box_overlay": "vote_cams.make_cam — the shared projection",
         "constants": {k: getattr(view_cams, k) for k in
                       ("OFF_AXIS", "PERP", "FOV_GOOD", "FILL", "WALL_PAD",
                        "EMPTY_R", "EMPTY_MAX", "DIST_MIN", "DIST_MAX")},
         "crops_untouched": True,
         "culled_rendered": bool(a.include_culled),
         "pending_render": len(targets),
         "rows": rows}, indent=1))
    write_report(sc, rows, len(targets))
    n_v = sum(r.get("n_views", 0) for r in rows)
    n_c = sum(len(r.get("culled_views", [])) for r in rows)
    n_d = sum(len(r.get("dropped", [])) for r in rows)
    print(f"\n[views] {len(rows)} nodes, {n_v} views kept, {n_d} culled"
          + (f" ({n_c} of them rendered for the audit)" if n_c else "")
          + f", {len(targets)} still to render")
    print(f"-> {sc.out / 'index.html'}")


if __name__ == "__main__":
    main()
