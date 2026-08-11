"""SHARED NODE-VIEW CAMERAS — the ONE definition of the aimed-view
camera set that looks at a node's box.

Lifted verbatim out of experiments/render_aimed_views.py on 2026-08-09 for
graph/node_views.py, for the same reason vote_cams.py was lifted out of
slicevote.py: two copies of a camera definition is one copy too many.
render_aimed_views stays the owner of the VOTE argument; this module owns only
the lens.

CONTRACT: pure camera math. Takes explicit arguments, closes over
nothing, touches no files, decides no policy. The caller supplies the
room shell and an emptiness probe; this module answers "where may a
camera stand to look at this box, and with what lens".

Frame = the pipeline BUNDLE frame (y-DOWN). Physical up is -y, so
"raise the camera" means DECREASE y, and ceiling_y < floor_y.

THE CONSTANTS ARE NOT KNOBS. Every one arrived with a user ruling
(R-S2-22..24, 2026-08-06) and none was picked by looking at what a
particular scene produces. Changing one to make a scene come out better
is how a test scene stops being a test.
"""
import math

import numpy as np

OFF_AXIS = 10.0    # deg — near-cardinal / near-top tilt. Exact cardinals
#                    hit axis-aligned thin objects edge-on.
PERP = 65.0        # deg off the original observation ray
FOV_GOOD = 55.0    # natural-perspective lens; the stand-off distance
#                    derives FROM it, not the other way round
FOV_MIN = 35.0
FOV_MAX = 75.0
FILL = 1.5         # half-extent multiple the stand-off is sized to
DIST_MIN = 1.2
DIST_MAX = 4.0
WALL_PAD = 0.30    # m — camera keep-out from the shell planes
EMPTY_R = 0.30     # m — emptiness probe radius at the eye
EMPTY_MAX = 1500   # points allowed inside that sphere. Deliberately
#                    LOOSER than the render verifier: a sphere grazing a
#                    sofa edge is still a usable camera.
CEIL_CLIP_PAD = 0.08   # m below the ceiling that the plan view clips at
EYE_H = 1.6        # m — standing height, the last-resort camera height

CARDINAL_DIRS = ((1.0, 0.0, 0.0), (-1.0, 0.0, 0.0),
                 (0.0, 0.0, 1.0), (0.0, 0.0, -1.0))


def roty(v, deg):
    """Rotate about the world y axis (the frame's vertical)."""
    th = math.radians(deg)
    ca, sa = math.cos(th), math.sin(th)
    return np.array([ca * v[0] + sa * v[2], v[1], -sa * v[0] + ca * v[2]])


def fov_for(half, dist):
    """The lens that frames a box of this half-extent from this distance,
    inside the natural range. Distance is chosen first; fov adapts only
    when the cull forced the camera somewhere else."""
    return float(np.clip(
        math.degrees(2 * math.atan(FILL * max(half, 0.15) / dist)),
        FOV_MIN, FOV_MAX))


def standoff(half):
    """Distance that puts a box of this half-extent in a FOV_GOOD frame,
    and the distance that would be NEEDED if the room did not clamp it.
    They differ for objects too big for the room to stand back from."""
    need = FILL * max(half, 0.15) / math.tan(math.radians(FOV_GOOD) / 2)
    return float(np.clip(need, DIST_MIN, DIST_MAX)), float(need)


def out_of_bounds(eye, shell):
    """Which room planes this standpoint is outside, named. y-down, so
    the ceiling is the SMALLER y and the vertical test reads upside down
    on purpose.

    It returns the FAILING PLANES rather than a bool because the caller
    reports them to a human. Saying only "the camera did not fit" — or
    worse, naming the height when the wall it went through was a side
    wall — sends the reader looking at the wrong number.
    """
    xlo, xhi, zlo, zhi, ceil_y, floor_y = shell
    bad = []
    if eye[0] <= xlo + WALL_PAD:
        bad.append(f"through the x={xlo:.2f} wall")
    if eye[0] >= xhi - WALL_PAD:
        bad.append(f"through the x={xhi:.2f} wall")
    if eye[2] <= zlo + WALL_PAD:
        bad.append(f"through the z={zlo:.2f} wall")
    if eye[2] >= zhi - WALL_PAD:
        bad.append(f"through the z={zhi:.2f} wall")
    if eye[1] <= ceil_y + WALL_PAD:
        bad.append("above the ceiling")
    if eye[1] >= floor_y - WALL_PAD:
        bad.append("below the floor")
    return bad


def in_bounds(eye, shell):
    """Is this standpoint inside the measured room?"""
    return not out_of_bounds(eye, shell)


def directions(geo, eye0):
    """The named view directions for a box, BEFORE any cull. Separate
    from candidates() because a caller sometimes needs to know where a
    view would have pointed without asking whether a camera may stand
    there — comparing an old box's camera against a new one, for
    instance, where the old room state is gone and only the aim matters.
    """
    c = np.asarray(geo["center"], float)
    d0 = c - np.asarray(eye0, float)
    d0[1] = 0.0
    n0 = float(np.linalg.norm(d0))
    d0 = np.array([1.0, 0.0, 0.0]) if n0 < 0.3 else d0 / n0
    out = {f"card{k}": roty(np.array(b, float), OFF_AXIS)
           for k, b in enumerate(CARDINAL_DIRS)}
    tilt = math.radians(max(OFF_AXIS, 15.0))
    up_dir = np.array([math.sin(tilt) * d0[0], -math.cos(tilt),
                       math.sin(tilt) * d0[2]])
    out["top"] = up_dir / np.linalg.norm(up_dir)
    for sgn, nm in ((1, "perpA"), (-1, "perpB")):
        out[nm] = -roty(d0, sgn * PERP)
    return out


def nominal_eye(geo, eye0, view):
    """Where a named view's camera WOULD stand for this box, ignoring the
    room. Returns (eye, aim, fov) or None for a view name with no
    direction (the clip-top plan view, which is a fallback rather than a
    direction). Used to measure how far a camera moved when a box moved —
    an answer that must not depend on the room state at the time."""
    dirs = directions(geo, eye0)
    if view not in dirs:
        return None
    c = np.asarray(geo["center"], float)
    half = float(max(geo["size"])) / 2
    dist, _ = standoff(half)
    eye = c + dirs[view] * dist
    if view != "top":
        eye[1] = c[1]
    return eye, c, fov_for(half, float(np.linalg.norm(eye - c)))


MIN_STANDOFF = 0.45   # m — closer than this to the box centre and the
                      # camera is inside/on top of the object, not
                      # looking at it. A pull that would need to come
                      # closer than this fails and the view is dropped.
REDUNDANT_M = 0.35    # m — two kept cameras closer together than this
                      # are the same picture twice. See prune_redundant.


def pull_inside(eye0, eye, shell, centre=None, steps=40):
    """Slide a camera back toward THE STANDPOINT until it is inside the
    room, and say how far it moved.

    TOWARD THE STANDPOINT, NOT TOWARD THE OBJECT — this was got wrong
    once and the mistake is worth recording. Pulling along the
    sight-line walks the camera INTO the object, which is exactly the
    wrong way for the objects that need help: obj_014's centre sits at
    x=2.45 with the wall at 2.66, i.e. the bookshelf itself stands
    INSIDE the 0.30 m camera keep-out. Every point near it is illegal,
    so a sight-line pull can only fail. The standpoint is open floor by
    construction — someone stood there — so pulling that way always has
    somewhere to arrive.

    The cost is that the viewing direction shifts: a camera dragged
    toward the middle of the room is no longer exactly `card2`. It is
    still roughly from that side, and `prune_redundant` removes it if it
    lands on top of another view. Recorded either way, never silent.

    Returns (eye, metres_moved), or (None, 0.0) if even the standpoint
    itself is outside the shell — which would mean the shell is wrong,
    not the camera."""
    e0 = np.asarray(eye0, float)
    e = np.asarray(eye, float)
    if out_of_bounds(e0, shell):
        return None, 0.0
    lo, hi = 0.0, 1.0        # 0 = the standpoint, 1 = where it wanted
    # binary search for the LARGEST legal fraction — keep as much of the
    # intended viewpoint as the room allows.
    for _ in range(steps):
        mid = (lo + hi) / 2
        if out_of_bounds(e0 + (e - e0) * mid, shell):
            hi = mid
        else:
            lo = mid
    got = e0 + (e - e0) * lo
    if centre is not None:
        c = np.asarray(centre, float)
        if float(np.linalg.norm(got - c)) < MIN_STANDOFF:
            return None, 0.0     # would end up on top of the object
    return got, float(np.linalg.norm(e - got))


def prune_redundant(views, dropped):
    """Drop views whose camera was pulled onto another view's camera.

    The cost of pulling cameras in is that they CONVERGE: pull hard
    enough and eight views become eight pictures of the same spot at
    eight times the price. A view removed here is removed for being a
    DUPLICATE, which is an honest reason — unlike the old cull, which
    removed distinct views for being a centimetre out of bounds."""
    kept = []
    for v in views:
        e = np.asarray(v["eye"], float)
        twin = next((k for k in kept
                     if float(np.linalg.norm(
                         np.asarray(k["eye"], float) - e)) < REDUNDANT_M),
                    None)
        if twin is None:
            kept.append(v)
            continue
        dropped.append({"view": v["view"], "tried": [{"eye": v["eye"]}],
                        "aim": v["aim"],
                        "why": [f"after being pulled inside the room this "
                                f"camera stands within {REDUNDANT_M} m of "
                                f"`{twin['view']}` — the same picture "
                                f"twice"]})
    return kept


MAIN_FILL = 1.15      # margin around the box for the MAIN photo. Tighter
                      # than the 1.5 the cardinal standoff uses: this
                      # camera is placed to fit, not to stand back.
MAIN_FOV_MIN = 10.0   # THE MAIN VIEW MAY ZOOM IN FREELY. FOV_MIN = 35 is
                      # a natural-lens floor for the cardinal views;
                      # applying it here demanded the camera stand 0.55 m
                      # from a ceiling light and left 18 of 45 nodes with
                      # NO main photo at all. The constraint that matters
                      # is the WIDE end (a very wide render stretches and
                      # distorts); narrowing is just a zoom and is free
                      # on a rendered view. Going narrow is also what
                      # keeps the camera NEAR THE STANDPOINT for small
                      # objects, which is the whole point of the rule.
MAIN_STEP = 0.25      # m — floor grid the search walks
MAIN_OCCLUDED_MAX = 400   # gaussians allowed between eye and box before
                          # the line of sight counts as blocked


def main_view_cam(geo, eye0, shell, empty_at, occluded_at,
                  step=MAIN_STEP, fov_fit=None):
    """THE MAIN PHOTO'S CAMERA — searched, not computed.

    USER RULING 2026-08-11, and it replaces widening the lens: "i don't
    want to depend on using super wide FOV since i want to defend
    against things that are truly large. move the camera at eye level
    but as near the default camera as possible... and if many points are
    possible, use the ones close to the default camera."

    WHY A SEARCH BEATS A FORMULA. The old rule fixed four compass
    directions and dropped the view when that direction had no room. But
    this room is 4.7 m wide and 8.4 m long — an object that cannot be
    framed from the side is often perfectly framable from along the
    length. Fixing the direction threw those solutions away. Searching
    positions finds them, and the lens never has to stretch.

    THE RULES, ALL AT ONCE:
      * eye level, always — the height the room was actually captured at
      * inside the room, clear of the walls
      * not standing inside furniture (the emptiness probe)
      * able to frame the box at a NORMAL lens (<= FOV_MAX). No wide
        angle escape hatch — that is the point
      * able to SEE it: nothing solid between eye and box
      * of everything that qualifies, THE ONE NEAREST THE STANDPOINT

    Returns a view dict (with `dist_to_default` and how many positions
    were considered), or None with a spoken reason — an object that
    cannot be photographed from anywhere legal must say so, not be
    quietly handed a bad camera."""
    c = np.asarray(geo["center"], float)
    # THE HALF-DIAGONAL, NOT HALF THE LONGEST SIDE.
    #
    # BUG FOUND BY THE USER 2026-08-11 ("some of the main view reshoots
    # still don't have the full object in them"). Framing was sized from
    # max(size)/2, which is the radius of a sphere that fits INSIDE the
    # box, not one that CONTAINS it. A camera lensed for that sphere cuts
    # the corners off every box that is not a flat slab: obj_016 came out
    # with 61% of itself in frame, obj_011#1 69%, obj_039 75%. The
    # containing radius is the half-diagonal, which for obj_016 is 0.51 m
    # against the 0.335 m used — half again too small.
    #
    # Measured, not assumed: 8 of the 11 main views were clipped before
    # this line changed.
    half = float(np.linalg.norm(np.asarray(geo["size"], float))) / 2
    e0 = np.asarray(eye0, float)
    xlo, xhi, zlo, zhi = shell[0], shell[1], shell[2], shell[3]
    # THE CAPTURE HEIGHT, NOT AN ASSUMED STANDING HEIGHT.
    #
    # BUG, user-found 2026-08-11 ("a lot of these reshoots are not
    # biasing the default camera position, but that's what we want").
    # This used `floor - EYE_H`, i.e. a 1.6 m standing person. On this
    # scene the standpoint actually sits 2.26 m above the floor, so
    # EVERY main photo was taken 0.66 m below the viewpoint the room was
    # captured from — a constant vertical offset on all 45 nodes, which
    # is exactly the "it went somewhere else" the user was seeing.
    # "Eye level" means the level of the eye that took the panorama.
    stand_y = float(e0[1])
    if not (shell[4] + WALL_PAD < stand_y < shell[5] - WALL_PAD):
        # standpoint outside the shell: fall back rather than trust it
        stand_y = shell[5] - EYE_H

    # THE CAMERA MUST BE IN A DISTANCE BAND, NOT MERELY FAR ENOUGH BACK.
    # Bounding only the near end meant every position qualified for a
    # small object, so the search took the one nearest the standpoint and
    # left the object a speck: obj_005, a bookshelf, drew a camera 5.63 m
    # away at the 35 deg floor. The far bound is the distance at which
    # the box stops filling the frame.
    reach = MAIN_FILL * max(half, 0.15)
    near = max(reach / math.tan(math.radians(FOV_MAX) / 2), MIN_STANDOFF)
    far = reach / math.tan(math.radians(MAIN_FOV_MIN) / 2)

    xs = np.arange(xlo + WALL_PAD, xhi - WALL_PAD + 1e-9, step)
    zs = np.arange(zlo + WALL_PAD, zhi - WALL_PAD + 1e-9, step)
    if not len(xs) or not len(zs):
        return None, "the room has no floor area once the wall pad is applied"
    gx, gz = np.meshgrid(xs, zs, indexing="ij")
    pts = np.stack([gx.ravel(),
                    np.full(gx.size, stand_y),
                    gz.ravel()], 1)
    # THE DEFAULT CAMERA IS CANDIDATE ZERO. A 0.25 m grid never lands
    # exactly on the standpoint, so "just turn the camera you already
    # have" was never actually offered — the nearest grid point was up
    # to 0.18 m away and won by default. Putting the real standpoint in
    # the list means the answer to "can this be done by turning the
    # default camera?" is yes whenever it is true.
    if not out_of_bounds(e0, shell):
        pts = np.vstack([e0[None, :], pts])

    # cheap filters first, so the expensive tests run on few candidates
    d_obj = np.linalg.norm(pts - c, axis=1)
    ok = (d_obj >= near) & (d_obj <= far)
    if not ok.any():
        if not (d_obj >= near).any():
            return None, (f"no standpoint in the room is {near:.2f} m "
                          f"from this object — too large to frame at "
                          f"{FOV_MAX:.0f} deg from anywhere inside")
        return None, (f"no legal standpoint sits between {near:.2f} m "
                      f"and {far:.2f} m from this object — the room "
                      f"gives nowhere to stand at a usable framing")
    pts, d_obj = pts[ok], d_obj[ok]
    order = np.argsort(np.linalg.norm(pts - e0, axis=1))   # nearest first

    considered = 0
    for i in order:
        considered += 1
        eye = pts[i]
        if empty_at(eye) > EMPTY_MAX:
            continue
        if occluded_at(eye, c, half) > MAIN_OCCLUDED_MAX:
            continue
        d = float(d_obj[i])
        fov = float(np.clip(
            math.degrees(2 * math.atan(MAIN_FILL * max(half, 0.15) / d)),
            MAIN_FOV_MIN, FOV_MAX))
        # MEASURE THE LENS, DO NOT APPROXIMATE IT (2026-08-11, second
        # framing bug). The line above sizes from atan(radius/distance) —
        # a SPHERE's tangent. Two errors compound at close range: a
        # sphere's true angular size is asin(r/d), which is larger, and a
        # BOX's corners project further out than its bounding sphere.
        # obj_039 came out at 92% in frame with the maths saying it fit.
        # `fov_fit` projects the eight real corners and returns the lens
        # that actually contains them; a position needing more than
        # FOV_MAX is REJECTED and the search moves on rather than
        # shipping a clipped main photo.
        if fov_fit is not None:
            exact = fov_fit(eye, c, geo, fov)
            if exact is None or exact > FOV_MAX + 1e-6:
                continue
            fov = float(max(exact, MAIN_FOV_MIN))
        return {"view": "main", "eye": [float(v) for v in eye],
                "aim": [float(v) for v in c],
                "fov": fov,
                "dist_to_default": float(np.linalg.norm(eye - e0)),
                "dist_to_object": round(d, 3),
                "considered": considered,
                "of_candidates": int(len(pts))}, None
    return None, (f"{len(pts)} standpoint(s) were far enough back, but "
                  f"every one is inside furniture or has something "
                  f"blocking the view")


def candidates(geo, eye0, shell, empty_at):
    """Every camera that may look at this box, after the cull.

    geo      the node's CURRENT geometry — center + size. The view set is
             a function of the box, which is the whole point: a box that
             moved gets different cameras, and a box that never existed
             before (a split piece) gets its own.
    eye0     the observation standpoint, for the perpendicular views and
             the plan tilt.
    shell    (xlo, xhi, zlo, zhi, ceiling_y, floor_y) in the same frame.
    empty_at callable(eye) -> number of splat points within EMPTY_R.

    Returns a list of {view, eye, aim, fov} (plus clip_y_gt on 'ctop'),
    and a per-candidate record of WHY anything was dropped — a view that
    silently vanished is the failure this project keeps re-learning.

    THE CULL IS GENERAL. No view is special-cased: 'bottom' dies on its
    own because below the floor is out of bounds.
    """
    c = np.asarray(geo["center"], float)
    half = float(max(geo["size"])) / 2
    dist, need = standoff(half)
    ceil_y, floor_y = shell[4], shell[5]

    d0 = c - np.asarray(eye0, float)
    d0[1] = 0.0
    n0 = float(np.linalg.norm(d0))
    d0 = np.array([1.0, 0.0, 0.0]) if n0 < 0.3 else d0 / n0

    cands = [(f"card{k}", roty(np.array(b, float), OFF_AXIS))
             for k, b in enumerate(CARDINAL_DIRS)]
    tilt = math.radians(max(OFF_AXIS, 15.0))
    up_dir = np.array([math.sin(tilt) * d0[0], -math.cos(tilt),
                       math.sin(tilt) * d0[2]])
    cands.append(("top", up_dir / np.linalg.norm(up_dir)))
    for sgn, nm in ((1, "perpA"), (-1, "perpB")):
        cands.append((nm, -roty(d0, sgn * PERP)))

    stand_y = floor_y - EYE_H          # y-down: minus = raise
    views, dropped, top_ok = [], [], False
    for nm, dirv in cands:
        # ---- USER RULING 2026-08-11: EYE LEVEL, AND STAY NEAR THE
        # ---- STANDPOINT. Replaces the old three-height ladder (object
        # centre -> halfway -> standing) and the drop-if-outside cull.
        #
        # WHY THE LADDER WENT. It existed to find SOME legal height, and
        # a fixed eye level is both simpler and truer to how the room was
        # actually seen: the panorama was captured at eye level, so a
        # camera at that height is looking at geometry the splat
        # reconstructs well.
        #
        # WHY DROPPING WENT. Measured on living_marble: of 34 culled
        # cameras, 21% were outside by <= 0.30 m and 56% by <= 1.00 m —
        # and the keep-out is ITSELF 0.30 m, so "outside by 0.01" means a
        # camera standing 29 cm from a wall. obj_014's perpB was thrown
        # away over ONE CENTIMETRE. Throwing away a whole view to avoid
        # moving a camera 1 cm is not a cull, it is a bug with a reason
        # string.
        #
        # WHAT REPLACES IT: pull the camera along its own line toward the
        # object until it is legal, and let the lens widen to compensate
        # (fov_for already did this; its docstring says "fov adapts only
        # when the cull forced the camera somewhere else" — that path was
        # barely reachable before).
        #
        # SECOND REASON, NOT GEOMETRIC: a gaussian splat is only well
        # reconstructed near where it was observed from. obj_012's card0
        # wanted to stand 6.97 m from the standpoint, outside the room,
        # rendering geometry nothing ever looked at from there. Staying
        # close is a QUALITY argument, not only a legality one.
        heights = ([max(c[1] + dirv[1] * dist, ceil_y + WALL_PAD + 0.05)]
                   if nm == "top" else [stand_y])
        eye, why, tried = None, [], []
        pulled_by, wanted_at = None, None
        for hy in heights:
            cand = c + dirv * dist
            cand[1] = hy
            oob = out_of_bounds(cand, shell)
            if oob and nm != "top":
                pulled, moved = pull_inside(eye0, cand, shell, centre=c)
                if pulled is not None:
                    tried.append({"eye": [float(x) for x in cand],
                                  "outside": oob,
                                  "pulled_in_m": round(moved, 3),
                                  "pulled_to": [float(x) for x in pulled]})
                    # A MOVED CAMERA MUST SAY SO ON THE VIEW ITSELF, not
                    # only in a drop record — a successful pull would
                    # otherwise leave no trace and the reviewer could not
                    # tell an as-intended view from one dragged toward
                    # the middle of the room. Same rule the `tried` list
                    # already follows for culls.
                    pulled_by = round(moved, 3)
                    wanted_at = [float(x) for x in cand]
                    cand, oob = pulled, []
            # EVERY ATTEMPT IS RECORDED, not just its verdict. A cull is
            # reviewable only if you can see where the camera wanted to
            # stand; a reason string alone asks the reader to take the
            # module's word for it.
            tried.append({"eye": [float(x) for x in cand],
                          "outside": oob})
            if oob:
                why.append(f"at eye height {hy:.2f} the camera stands "
                           + " and ".join(oob))
                continue
            n_near = empty_at(cand)
            if n_near > EMPTY_MAX:
                tried[-1]["inside_geometry"] = n_near
                why.append(f"at eye height {hy:.2f} the camera stands "
                           f"inside geometry ({n_near} points within "
                           f"{EMPTY_R} m)")
                continue
            eye = cand
            break
        if eye is None:
            dropped.append({"view": nm, "why": why, "tried": tried,
                            "aim": [float(x) for x in c]})
            continue
        if nm == "top":
            top_ok = True
        d_act = float(np.linalg.norm(eye - c))
        views.append({"view": nm, "eye": [float(v) for v in eye],
                      "aim": [float(v) for v in c],
                      "fov": fov_for(half, d_act),
                      **({"pulled_in_m": pulled_by,
                          "wanted_eye": wanted_at}
                         if pulled_by is not None else {})})

    # CLIP-TOP PLAN VIEW (user: "clip top for plan view if needed").
    # Camera ABOVE the ceiling with the ceiling clipped out of the splat,
    # so bounds and emptiness do not apply — the clip is what creates the
    # free space. Stand-off is UNCLAMPED here, which is the only way a
    # room-scale object ever fits a frame.
    if not top_ok or dist < need - 1e-6:
        up = np.array([math.sin(math.radians(10)) * d0[0], -1.0,
                       math.sin(math.radians(10)) * d0[2]])
        up /= np.linalg.norm(up)
        eye = c + up * max(need, 2.0)
        views.append({"view": "ctop", "eye": [float(v) for v in eye],
                      "aim": [float(v) for v in c],
                      "fov": fov_for(half, float(np.linalg.norm(eye - c))),
                      "clip_y_gt": float(ceil_y + CEIL_CLIP_PAD)})
    return prune_redundant(views, dropped), dropped
