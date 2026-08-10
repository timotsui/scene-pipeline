"""SHARED NODE-VIEW CAMERAS — the ONE definition of the aimed-view
camera set that looks at a node's box.

Lifted verbatim out of experiments/pool_retake.py on 2026-08-09 for
graph/node_views.py, for the same reason vote_cams.py was lifted out of
slicevote.py: two copies of a camera definition is one copy too many.
pool_retake stays the owner of the CARVE argument; this module owns only
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
        # CARDINAL TO THE OBJECT (user ruling): try the camera at the
        # object's OWN height first, so it is seen face-on, and rise
        # toward standing height only when that spot fails. The cull
        # arbitrates placement; a fixed eye level never does.
        heights = ([max(c[1] + dirv[1] * dist, ceil_y + WALL_PAD + 0.05)]
                   if nm == "top" else
                   [c[1], (c[1] + stand_y) / 2, stand_y])
        eye, why, tried = None, [], []
        for hy in heights:
            cand = c + dirv * dist
            cand[1] = hy
            oob = out_of_bounds(cand, shell)
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
                      "fov": fov_for(half, d_act)})

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
    return views, dropped
