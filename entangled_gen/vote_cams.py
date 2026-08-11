"""SHARED VOTE CAMERAS — the ONE definition of the vote's camera math.

Lifted verbatim out of slicevote.py on 2026-08-07 for the J8
split-cell judge (PLAN_VOTEBOX_DOWNSTREAM Phase A, "Stimuli v2"): the
judge's sheets project the vote's 3D boxes ONTO the vote's own card
and plan renders, so the overlay must be drawn with the SAME camera the
renderer used. Two copies of that math is one copy too many — the
anti-drift requirement in the design is literally this module. Importers:

    slicevote.py          renders + votes (the producer)
    graph/judge_multiplicity.py annotates those renders (the consumer)

CONTRACT: pure camera math only — takes explicit arguments, closes over
nothing, touches no files. Frame = the pipeline BUNDLE frame (y-DOWN;
world up = [0, -1, 0]), so "raise the camera" means DECREASE y.
Vote thresholds (SHELL_EPS, PAD, CAP_M, OUTLIER_K, EMPTY_R/EMPTY_MAX,
WALL_PAD, DET_THR, DIL_ISO) are vote policy, not camera math, and stay
in slicevote.py — the ones here are the lens itself.
"""
import math
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))
from sweep_recenter import c2w_from_eye_aim  # noqa: E402

RES = 768        # square render resolution the vote's cameras assume
FOV_GOOD = 55.0  # natural-perspective lens; stand-off derives from it
OFF_AXIS = 10.0  # cardinal cards are nudged off-axis by this many degrees
WALL_PAD = 0.30  # m — camera-standpoint keep-out from the shell planes
#                  (also the plan camera's ceiling clamp; a consumer
#                  rebuilding that camera needs the same number)


class MatCamLite:
    def __init__(self, R, pos, f, cx, cy):
        self.R, self.pos = R, pos
        self.f, self.cx, self.cy = f, cx, cy

    def project(self, pts):
        rel = (pts - self.pos) @ self.R.T
        x, y, z = rel[:, 0], rel[:, 1], rel[:, 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            u = self.cx + self.f * x / z
            v = self.cy - self.f * y / z
        return u, v, z


def make_cam(eye, aim, fov, res):
    M = c2w_from_eye_aim(eye, aim, [0.0, -1.0, 0.0])
    R = np.stack([M[:3, 0], -M[:3, 1], M[:3, 2]])
    f = res / (2 * math.tan(math.radians(fov) / 2))
    return MatCamLite(R, np.asarray(eye, np.float64), f, res / 2, res / 2)


def roty(v, deg):
    th = math.radians(deg)
    ca, sa = math.cos(th), math.sin(th)
    return np.array([ca * v[0] + sa * v[2], v[1], -sa * v[0] + ca * v[2]])


def top_cam_for(geo, eye0, ceil_y, wall_pad, in_bounds, empty_at,
                empty_max):
    """Plan-view camera candidates for ONE node, matching the renders
    experiments/render_aimed_views.py wrote as <id>_top.png / <id>_ctop.png.

    geo        the resolved node's geometry dict (center + size)
    eye0       the original standpoint (rig_sp0 eye_raw)
    ceil_y     shell ceiling y (raw frame; y-down, so ceiling < floor)
    wall_pad   keep-out from the shell planes
    in_bounds  fn(eye) -> bool   — scene state, passed in by the caller
    empty_at   fn(eye) -> int    — gaussians within the probe radius
    empty_max  the emptiness the 'top' standpoint must beat

    Returns ([(view_name, eye, fov), ...], center). The 'top' candidate
    stands inside the room and is culled by in_bounds/empty_at; 'ctop'
    is the clip-top fallback ABOVE the ceiling (no bounds apply — the
    clip creates the free space) and is added whenever 'top' was culled
    or cannot frame the object. Both candidates' PARAMETERS depend only
    on geo/eye0/ceil_y/wall_pad, never on the cull — so a consumer that
    knows WHICH view the vote used can rebuild that exact camera with
    permissive stand-ins for in_bounds/empty_at.
    """
    c = np.array(geo["center"], float)
    half = max(geo["size"]) / 2
    dist = float(np.clip(
        1.5 * max(half, 0.15) / math.tan(math.radians(FOV_GOOD) / 2),
        1.2, 4.0))
    d0 = c - eye0
    d0[1] = 0
    if np.linalg.norm(d0) < 0.3:
        d0 = np.array([1.0, 0, 0])
    d0 /= np.linalg.norm(d0)
    out = []
    tilt = math.radians(max(OFF_AXIS, 15.0))
    up_dir = np.array([math.sin(tilt) * d0[0], -math.cos(tilt),
                       math.sin(tilt) * d0[2]])
    up_dir /= np.linalg.norm(up_dir)
    eye = c + up_dir * dist
    eye[1] = max(c[1] + up_dir[1] * dist, ceil_y + wall_pad + 0.05)
    top_ok = False
    if in_bounds(eye) and empty_at(eye) <= empty_max:
        dist_act = float(np.linalg.norm(eye - c))
        fov = float(np.clip(math.degrees(
            2 * math.atan(1.5 * max(half, 0.15) / dist_act)), 35, 75))
        out.append(("top", eye, fov))
        top_ok = True
    need = 1.5 * max(half, 0.15) / math.tan(math.radians(FOV_GOOD) / 2)
    if not top_ok or dist < need - 1e-6:
        up = np.array([math.sin(math.radians(10)) * d0[0], -1.0,
                       math.sin(math.radians(10)) * d0[2]])
        up /= np.linalg.norm(up)
        eye = c + up * max(need, 2.0)
        fov = float(np.clip(math.degrees(
            2 * math.atan(1.5 * max(half, 0.15)
                          / float(np.linalg.norm(eye - c)))), 35, 75))
        out.append(("ctop", eye, fov))
    return out, c
