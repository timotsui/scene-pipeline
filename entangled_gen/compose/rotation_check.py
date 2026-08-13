"""PH2 FIT LOOP -- ROTATION CHECK (CANON 2026-08-04).

The first step of the fit loop, settled by experiment (PLAN_FIT_LOOP.md
"SETTLED 2026-08-04", pipeline_map.html s3 card): ONE DIRECT-ASK call per
placed object per camera --

  reference photograph of the real room (the detection evidence already in
  scene_graph.json: the pano view the object was seen in, its box outlined,
  plus the saved close-up; both MIRRORED BACK to true left-right, because
  the pano frame is a defined mirror of the real geometry) +
  the object as placed + the whole-room context render
  -> "how far must it turn about its vertical axis to match the real one"

Objects with no detection evidence get the same ask WITHOUT a reference,
plausibility wording. The routing is a lookup, not a judgment -- with one
refinement (user 2026-08-04): a SWAP item inherits the photograph of the
object it REPLACED (edit_proposals.json swap lineage; the swap placer packs
the new item into the old one's envelope, so the original's position and
facing are the right anchor), and its prompt says plainly that it is a
swap. Only STRICT ADDS end up reference-less.

Formats DROPPED on measurement, recorded here so nobody rebuilds them:
8-tile strips (the judge tools up to zoom, 20-29 turns) and propose->verify
(the verify step reversed its own correct answer). Stimulus rule (user):
the judge must be able to answer in one look.

Mechanics carried from the experiments: every call runs in its OWN folder
holding only its own images (the judge demonstrably reads neighbors);
calls run concurrently in one wave (all independent); a failed call
records no-answer and never kills the run; replies already on disk are
reused, which is also the resume path; per-call turns/tokens measured via
--output-format json.

This module WRITES A RECORD ONLY (rotation_check.json + review sheets).
It does not touch fitted_preview -- applying rotations is a separate,
user-gated step.

  python rotation_check.py [--scene bedroom_marble] [--jobs 6]
                           [--items id,id | all] [--cams A,B]
                           [--renders-only] [--timeout 480]
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import trimesh
import pyrender
from PIL import Image, ImageDraw, ImageFont, ImageOps

EG = Path(__file__).parent.parent
sys.path.insert(0, str(EG))
import paths  # noqa: E402
from arch_walls import wall_axis_planes  # noqa: E402
sys.path.insert(0, str(paths.REPO_ROOT / "composition"))
from place import look_at_pose  # noqa: E402

MODEL = "sonnet"
TILE = 384
GAP = 12
CTX_RES = 640
REF_W = 960

CONVENTION = (
    "Angle convention: POSITIVE degrees turn the object COUNTER-CLOCKWISE "
    "when the room is seen from directly above (bird's-eye view). Negative "
    "degrees turn it clockwise. 0 means it is already correct. Any angle is "
    "allowed, not only multiples of 45."
)

REF_NOTE = (
    "IMPORTANT about the reference: it is a PHOTOGRAPH of the real room, "
    "taken from a different viewpoint than the render, and the object in "
    "the render is a stand-in model that does NOT look like the real one. "
    "Match which WAY the object faces within the room -- use the walls, "
    "window and neighbouring furniture to carry the direction across. Do "
    "not try to match its shape, colour or size."
)

ASK_MATCH = """You are correcting the ROTATION of ONE object placed in a 3D room.
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

ASK_SAME = """You are correcting the ROTATION of ONE object placed in a 3D room.
The room is a reconstruction of a real room, and you have a photo of it.

IMAGE 1 -- REFERENCE, a photograph of the REAL room. Left panel: the view
the object was photographed in, with it outlined in yellow. Right panel: a
close-up of that same real object:
{ref}
IMAGE 2 -- the RECONSTRUCTION, rendered from THE SAME CAMERA as that
photograph. Only this object is placed; walls and floor are kept, all other
objects are removed:
{same}

The object is "{name}" (id {oid}).

The two images are the SAME VIEW of the same room, so the object should
appear in the same place in both. {refnote}

Decide how far the placed object must be turned about its vertical axis so
it faces the way the real object does in the photograph.

{convention}

Reply with ONLY a JSON object, no other text:
{{"degrees": <number from -180 to 180>, "confidence": "high"|"medium"|"low",
  "why": "<one short sentence>"}}
"""

ASK_SAME_SWAP = """You are correcting the ROTATION of ONE object placed in a 3D room.
The room is a reconstruction of a real room, and you have a photo of it.

THIS OBJECT IS A SWAP: the real room contained {orig_name} at this spot,
and the reconstruction replaced it with "{name}". The photograph shows the
ORIGINAL {orig_name}, not this object.

IMAGE 1 -- REFERENCE, a photograph of the REAL room. Left panel: the view
the ORIGINAL object was photographed in, with it outlined in yellow. Right
panel: a close-up of that original object:
{ref}
IMAGE 2 -- the RECONSTRUCTION, rendered from THE SAME CAMERA as that
photograph. Only the replacement is placed; walls and floor are kept, all
other objects are removed:
{same}

The object is "{name}" (id {oid}).

The two images are the SAME VIEW of the same room. {refnote}

The replacement occupies the original's spot. Decide how far it must be
turned about its vertical axis so it faces the way the ORIGINAL object
faced -- typically: front toward wherever the original's front pointed
(out from the wall it hung on or stood against).

{convention}

Reply with ONLY a JSON object, no other text:
{{"degrees": <number from -180 to 180>, "confidence": "high"|"medium"|"low",
  "why": "<one short sentence>"}}
"""

SPINS = [0, 90, 180, 270]        # candidate yaws; fine angles = later nudge
LETTERS = "abcd"
FOOT_TOL = 0.15   # footprint slack (the shopping strict mark; scene-agnostic)


def plausible_spins(lo, hi, box_lo, box_hi, tol=FOOT_TOL):
    """DETERMINISTIC PRUNE (user idea 08-04): a spin whose rotated footprint
    cannot fit the OBSERVED box is impossible before anyone looks at
    pixels. 0/180 share the as-placed footprint and always survive; 90/270
    survive only if the swapped footprint fits the box within tol. Pure
    geometry from scene evidence -- no asset semantics anywhere."""
    w, d = hi[0] - lo[0], hi[2] - lo[2]
    bw, bd = box_hi[0] - box_lo[0], box_hi[2] - box_lo[2]
    swapped_ok = (d <= bw * (1 + tol)) and (w <= bd * (1 + tol))
    return [s for s in SPINS if s in (0, 180) or swapped_ok]


LEGAL_RATIO = 1.15   # footprint elongation below this = indeterminate


def legal_spins(lo, hi, box_lo, box_hi, wall_attached):
    """WALL-LEGALITY CONSTRAINT (user 08-05 "take out the strictly
    illegal options"; born from the sideways-door incident: a HIGH-conf
    +90 pick stood door obj_128's metre-wide face out of its 0.13 m
    wall box). A wall-attached item must keep its THIN axis along the
    wall normal -- and the wall normal IS the observed box's own thin
    axis. Offer only spins whose resulting footprint honors that:
    0/180 keep the as-placed footprint, 90/270 swap it, so which pair
    is legal depends on how the mesh currently stands (a sideways
    placement gets exactly {90,270} -- the menu that can fix it).
    Distinct from the ANNEXED footprint-prune: that pruned by FIT on
    free-standing items (bed benchmark broke); this bans PHYSICALLY
    IMPOSSIBLE poses on wall items only. Near-square footprints (mesh
    or box) are indeterminate -> keep all four. Box-derived, no asset
    semantics, scene-agnostic."""
    if not wall_attached:
        return list(SPINS)
    w, d = hi[0] - lo[0], hi[2] - lo[2]
    bw, bd = box_hi[0] - box_lo[0], box_hi[2] - box_lo[2]
    if (max(w, d) / max(min(w, d), 1e-6) < LEGAL_RATIO
            or max(bw, bd) / max(min(bw, bd), 1e-6) < LEGAL_RATIO):
        return list(SPINS)
    return [0, 180] if (w < d) == (bw < bd) else [90, 270]


P_CHOICE = """IMAGE 1 -- REFERENCE, a photograph of a REAL room. Left panel: the room
with the "{name}" outlined in yellow; right panel: a close-up of it:
{ref}

THE OTHER IMAGES -- {n} CANDIDATE placements of the "{name}" in a
reconstruction of that room, all rendered from THE SAME CAMERA as the
photograph. In each the object is isolated (walls and floor kept,
everything else removed) and stands at a different orientation. A compass
rose is drawn on the floor beside it, identical in every image:
{cands}

The object is a stand-in model that does NOT look like the real one --
compare ORIENTATION only: which way the object faces within the room,
using the rose and the walls.

Which candidate's orientation matches the real "{name}" most?

Reply with ONLY a JSON object, no other text:
{{"pick": {letters}, "confidence": "high"|"medium"|"low",
  "why": "<one short sentence>"}}
"""

P_CHOICE_SWAP = """IMAGE 1 -- REFERENCE, a photograph of a REAL room. THIS OBJECT IS A
SWAP: the real room contained {orig_name} at this spot, and the
reconstruction replaced it with "{name}". The photograph shows the ORIGINAL
{orig_name}, outlined in yellow, with a close-up in the right panel:
{ref}

THE OTHER IMAGES -- {n} CANDIDATE placements of the replacement "{name}",
all rendered from THE SAME CAMERA as the photograph, the object isolated
(walls and floor kept), each at a different orientation, the same compass
rose beside it:
{cands}

Compare ORIENTATION only. The replacement occupies the original's spot and
should face the way the ORIGINAL object faced (front out from the wall it
hung on or stood against).

Which candidate matches that best?

Reply with ONLY a JSON object, no other text:
{{"pick": {letters}, "confidence": "high"|"medium"|"low",
  "why": "<one short sentence>"}}
"""

ASK_SWAP = """You are correcting the ROTATION of ONE object placed in a 3D room.
The room is a reconstruction of a real room, and you have a photo of it.

THIS OBJECT IS A SWAP: the real room contained {orig_name} at this spot,
and the reconstruction replaced it with "{name}". The photograph shows the
ORIGINAL {orig_name}, not this object.

IMAGE 1 -- REFERENCE, the real room. Left panel: the view the ORIGINAL
object was photographed in, with it outlined in yellow. Right panel: a
close-up of that original object:
{ref}
IMAGE 2 -- the replacement as currently placed in the reconstruction, seen
from a camera inside it:
{item}
IMAGE 3 -- the whole reconstructed room from a high corner. The replacement
is outlined in yellow and labelled with its id:
{ctx}

The object is "{name}" (id {oid}).

{refnote}

The replacement occupies the original's spot. Decide how far it must be
turned about its vertical axis so it faces the way the ORIGINAL object
faced -- typically: front toward wherever the original's front pointed
(out from the wall it hung on or stood against).

{convention}

Reply with ONLY a JSON object, no other text:
{{"degrees": <number from -180 to 180>, "confidence": "high"|"medium"|"low",
  "why": "<one short sentence>"}}
"""

COMPASS_BLOCK = """A compass rose is DRAWN ON THE FLOOR in BOTH images, on open floor
right BESIDE the object: four arrows labelled N (tinted red), E, S, W. It
is the SAME rose seen through the SAME camera, so it sits at the same spot
in both images.
For orientation: straight ahead into the image is roughly {ahead},
screen-right is roughly {right}.

Work in TWO STEPS, in this order, and write both down.

STEP 1 -- the REFERENCE photograph only. Describe the real object's
orientation in compass terms: name the visible feature that tells you
where its FRONT is (headboard, seat opening, drawers, doors, back
panel...), say where that feature sits relative to the drawn rose, and
conclude which arrow the front points along (nearest of
N/NE/E/SE/S/SW/W/NW).

STEP 2 -- the RENDER only. Do the same for the placed object.

Do NOT report a turn or any degrees. The turn is computed from your two
directions by the caller.

Reply with ONLY a JSON object, no other text:
{{"real_desc": "<one sentence: the front-telling feature and where it sits>",
  "real_faces": "N"|"NE"|"E"|"SE"|"S"|"SW"|"W"|"NW",
  "placed_desc": "<one sentence: same for the render>",
  "placed_faces": "N"|"NE"|"E"|"SE"|"S"|"SW"|"W"|"NW",
  "confidence": "high"|"medium"|"low"}}
"""

COMPASS_DIRS = {"N": (0.0, 1.0), "NE": (1.0, 1.0), "E": (1.0, 0.0),
                "SE": (1.0, -1.0), "S": (0.0, -1.0), "SW": (-1.0, -1.0),
                "W": (-1.0, 0.0), "NW": (-1.0, 1.0)}  # (x, z), N=+z E=+x


def compass_name(v):
    """(x,z) horizontal vector -> nearest 8-point compass name."""
    x, z = float(v[0]), float(v[2]) if len(v) == 3 else float(v[1])
    best, bd = "N", -2.0
    n = (x * x + z * z) ** 0.5
    if n < 1e-9:
        return "N"
    for k, (dx, dz) in COMPASS_DIRS.items():
        dn = (dx * dx + dz * dz) ** 0.5
        d = (x * dx + z * dz) / (n * dn)
        if d > bd:
            bd, best = d, k
    return best


def compass_anchors(eye, look):
    """Camera-anchored compass names: ahead/behind/screen-right/screen-left.
    Screen right = cross(fwd, up), the look-at convention pyrender uses."""
    fwd = np.asarray(look, float) - np.asarray(eye, float)
    fwd[1] = 0.0
    right = np.cross(fwd, np.array([0.0, 1.0, 0.0]))
    return {"ahead": compass_name(fwd), "behind": compass_name(-fwd),
            "right": compass_name(right), "left": compass_name(-right)}


COMPASS_ARROWS = {"N": (0.0, 0.0, 1.0), "E": (1.0, 0.0, 0.0),
                  "S": (0.0, 0.0, -1.0), "W": (-1.0, 0.0, 0.0)}
COMPASS_ARM = 0.6   # metres


def compass_origin(lo, hi, eye, fy=0.0):
    """A clear floor spot BESIDE the object (user 08-04: next to it, not on
    it): step from the footprint centre toward the camera, past the
    footprint edge plus the arm length, so no arrow crosses the object.
    `fy` is the measured render-frame floor the rose is drawn on."""
    cx, cz = (lo[0] + hi[0]) / 2, (lo[2] + hi[2]) / 2
    d = np.array([float(eye[0]) - cx, float(eye[2]) - cz])
    n = np.linalg.norm(d)
    d = d / n if n > 1e-6 else np.array([1.0, 0.0])
    half = (abs(d[0]) * (hi[0] - lo[0]) + abs(d[1]) * (hi[2] - lo[2])) / 2
    step = half + COMPASS_ARM + 0.15
    return (cx + d[0] * step, fy, cz + d[1] * step)


def crop_to_object(img, pose, fov, res, lo, hi, origin):
    """Object-framed crop (user-approved 08-04): a room-framed 960 view
    leaves a small object ~100 px and the judge builds zoom tools (obj_054
    transcript: crop_script.py + System.Drawing expeditions). We know
    where the object is -- crop to the union of its projected box and the
    compass rose, with margin. Geometry-driven, no per-category anything."""
    pts = [(x, y, z) for x in (lo[0], hi[0]) for y in (lo[1], hi[1])
           for z in (lo[2], hi[2])]
    for nm, v in COMPASS_ARROWS.items():
        pts.append((origin[0] + v[0] * COMPASS_ARM, origin[1],
                    origin[2] + v[2] * COMPASS_ARM))
    uv = project(pose, fov, res, pts)
    if not uv:
        return img
    us, vs = [p[0] for p in uv], [p[1] for p in uv]
    m = 70   # px margin: label chips + local wall context
    x0 = max(0, int(min(us)) - m)
    y0 = max(0, int(min(vs)) - m)
    x1 = min(res, int(max(us)) + m)
    y1 = min(res, int(max(vs)) + m)
    if x1 - x0 < 100 or y1 - y0 < 100:
        return img
    return img.crop((x0, y0, x1, y1))


def _compass_font(size=30):
    try:
        return ImageFont.truetype("arial.ttf", size)
    except OSError:
        return ImageFont.load_default()


def draw_compass(img, pose, fov, res, origin, col_n=(255, 60, 60),
                 col=(60, 220, 255)):
    """Floor compass rose at `origin`, projected through the SAME camera as
    the panel it is drawn on (user 08-04: compass ON the image, not in
    words). N tinted red, the rest cyan; every stroke gets a black
    underlay and the letters are large on black chips (user 08-04: white
    lines blended into the background, letters too small). Uses the same
    N=+z/E=+x table as implied_degrees, keeping the arithmetic check valid
    against what the judge sees."""
    d = ImageDraw.Draw(img)
    o_uv = project(pose, fov, res, [origin])
    if not o_uv:
        return img
    ox, oy = o_uv[0]
    font = _compass_font(30)
    for nm, v in COMPASS_ARROWS.items():
        uv = project(pose, fov, res,
                     [(origin[0] + v[0] * COMPASS_ARM, origin[1],
                       origin[2] + v[2] * COMPASS_ARM)])
        if not uv:
            continue
        tx, ty = uv[0]
        c = col_n if nm == "N" else col
        d.line([ox, oy, tx, ty], fill=(0, 0, 0), width=10)   # underlay
        d.line([ox, oy, tx, ty], fill=c, width=5)
        bx, by = ox - tx, oy - ty
        n = max((bx * bx + by * by) ** 0.5, 1e-6)
        bx, by = bx / n * 18, by / n * 18
        for s in (0.45, -0.45):
            hx, hy = tx + bx - by * s, ty + by + bx * s
            d.line([tx, ty, hx, hy], fill=(0, 0, 0), width=9)
            d.line([tx, ty, hx, hy], fill=c, width=5)
        lx, ly = tx + (tx - ox) * 0.22, ty + (ty - oy) * 0.22
        tw = d.textlength(nm, font=font)
        d.rectangle([lx - tw / 2 - 7, ly - 21, lx + tw / 2 + 7, ly + 21],
                    fill=(0, 0, 0))
        d.text((lx - tw / 2, ly - 18), nm, fill=c, font=font)
    d.ellipse([ox - 7, oy - 7, ox + 7, oy + 7], fill=(0, 0, 0))
    d.ellipse([ox - 5, oy - 5, ox + 5, oy + 5], fill=(255, 255, 255))
    return img


def implied_degrees(placed_name, real_name):
    """CCW-positive yaw (the yaw_about convention: +90 maps +z to +x) that
    turns placed_faces into real_faces. None if either name is unknown."""
    p = COMPASS_DIRS.get(str(placed_name).upper())
    r = COMPASS_DIRS.get(str(real_name).upper())
    if not p or not r:
        return None
    # (x,z) pairs; y-component of p x r in 3D = p_z*r_x - p_x*r_z
    ang = np.degrees(np.arctan2(p[1] * r[0] - p[0] * r[1],
                                p[0] * r[0] + p[1] * r[1]))
    return wrap180(ang)


ASK_PLAUSIBLE = """You are correcting the ROTATION of ONE object placed in a 3D room.

IMAGE 1 -- the object in place, seen from a camera inside the room:
{item}
IMAGE 2 -- the whole room from a high corner. The object is outlined in
yellow and labelled with its id:
{ctx}

The object is "{name}" (id {oid}).

Read both images. Decide whether this object stands at a sensible
orientation for what it is and for where it sits in this room. If it does
not, say how far it should be turned about its vertical axis.

{convention}

Reply with ONLY a JSON object, no other text:
{{"degrees": <number from -180 to 180>, "confidence": "high"|"medium"|"low",
  "why": "<one short sentence>"}}
"""


# --------------------------------------------------------------------------
# claude bridge (project pattern: stdin, stripped env, measured json)
# --------------------------------------------------------------------------
def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)  # stale-API-key hijack gotcha (project memory)
    return env


def parse_json_obj(text):
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(1))
        except ValueError:
            pass
    i = text.find("{")
    while i >= 0:
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[i:])
            if isinstance(obj, dict):
                return obj
        except ValueError:
            pass
        i = text.find("{", i + 1)
    return None


def wrap180(d):
    v = ((float(d) + 180.0) % 360.0) - 180.0
    return 180.0 if v == -180.0 else v


def call_measured(prompt, cwd, model, timeout):
    """-> (reply_text, wall_s, cost). cost carries num_turns + tokens."""
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[rot] claude.exe not on PATH")
    t0 = time.time()
    r = subprocess.run([exe, "-p", "--model", model,
                        "--output-format", "json"],
                       input=prompt, capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       env=claude_env(), cwd=str(cwd), timeout=timeout)
    dt = time.time() - t0
    out = (r.stdout or "").strip()
    if r.returncode != 0:
        raise RuntimeError(f"claude exit {r.returncode}: "
                           f"{((r.stderr or '') + out)[:300]}")
    env = parse_json_obj(out) or {}
    usage = env.get("usage") or {}
    cost = {"num_turns": env.get("num_turns"),
            "in_tok": usage.get("input_tokens"),
            "out_tok": usage.get("output_tokens"),
            "cache_read_tok": usage.get("cache_read_input_tokens"),
            "cost_usd": env.get("total_cost_usd")}
    text = env.get("result") if isinstance(env.get("result"), str) else out
    return text, dt, cost


# --------------------------------------------------------------------------
# scene load + renders (proven in the 08-03/08-04 experiments)
# --------------------------------------------------------------------------
def load_scene(scene):
    cdir = paths.compose_dir(scene)
    man = {"frame": paths.frame_block(scene)}
    graph = json.loads((paths.scene_dir(scene) / "scene_graph.json")
                       .read_text(encoding="utf-8"))
    r2r = np.array(man["frame"].get("raw_to_render", [1, 1, 1]), np.float32)
    to_render = np.diag([r2r[0], r2r[1], r2r[2], 1.0])

    xs_raw, zs_raw, floor_raw, ceil_raw = wall_axis_planes(graph["nodes"])
    wx = sorted((xs_raw[0] * r2r[0], xs_raw[-1] * r2r[0]))
    wz = sorted((zs_raw[0] * r2r[2], zs_raw[-1] * r2r[2]))
    # THE MEASURED FLOOR, not an assumed y=0 (user-caught 2026-08-12, the
    # fresh04 bed: the synthetic slab sat at 0 while the scene's real
    # floor is at -0.98, so the slab hovered at mid-room height and hid
    # every low object from every camera -- the judge's "yellow box shows
    # only blank floor" was literally true. Same disease as R-S2-134's
    # absolute eye height: a frame constant pretending to be 0.)
    fy, cy = sorted((floor_raw * r2r[1], ceil_raw * r2r[1]))
    room_c = np.array([(wx[0] + wx[1]) / 2, (fy + cy) / 2,
                       (wz[0] + wz[1]) / 2])

    sc = trimesh.load(cdir / "fitted_preview.glb", force="scene")
    by_item = {}
    for gname, geom in sc.geometry.items():
        m = geom.copy()
        m.apply_transform(to_render)
        by_item.setdefault(gname.rsplit("_t", 1)[0], []).append(m)

    fl = trimesh.creation.box(
        extents=[wx[1] - wx[0] + 0.4, 0.05, wz[1] - wz[0] + 0.4])
    fl.apply_translation([room_c[0], fy - 0.025, room_c[2]])
    walls = [fl]
    H, T = max(2.6, cy - fy), 0.05
    for x in wx:
        w = trimesh.creation.box(extents=[T, H, wz[1] - wz[0] + 0.4])
        w.apply_translation([x, fy + H / 2, room_c[2]])
        walls.append(w)
    for z in wz:
        w = trimesh.creation.box(extents=[wx[1] - wx[0] + 0.4, H, T])
        w.apply_translation([room_c[0], fy + H / 2, z])
        walls.append(w)
    for m in walls:
        m.visual = trimesh.visual.ColorVisuals(
            m, vertex_colors=[210, 208, 202, 255])

    nodes = {n["id"]: n for n in graph["nodes"]}
    return cdir, nodes, by_item, walls, wx, wz, room_c, fy


def yaw_about(center, deg):
    a = np.radians(deg)
    c, s = np.cos(a), np.sin(a)
    R = np.array([[c, 0, s, 0], [0, 1, 0, 0], [-s, 0, c, 0], [0, 0, 0, 1]])
    T1 = np.eye(4); T1[:3, 3] = -np.asarray(center)
    T2 = np.eye(4); T2[:3, 3] = np.asarray(center)
    return T2 @ R @ T1


def render_frame(meshes, eye, target, fov, res=TILE):
    scene = pyrender.Scene(bg_color=[1, 1, 1, 1], ambient_light=[0.5] * 3)
    for m in meshes:
        scene.add(pyrender.Mesh.from_trimesh(m, smooth=False))
    pose = look_at_pose(np.asarray(eye, float), np.asarray(target, float),
                        [0, 1, 0])
    scene.add(pyrender.PerspectiveCamera(yfov=np.radians(fov)), pose=pose)
    scene.add(pyrender.DirectionalLight(intensity=3.0), pose=pose)
    side = look_at_pose(np.asarray(target, float) + np.array([1.5, 2.5, 1.0]),
                        np.asarray(target, float), [0, 1, 0])
    scene.add(pyrender.DirectionalLight(intensity=1.5), pose=side)
    r = pyrender.OffscreenRenderer(res, res)
    color, _ = r.render(scene)
    r.delete()
    return Image.fromarray(color)


R2R = np.array([-1.0, -1.0, 1.0])


def detection_cam_render_frame(sidecar, eye_raw):
    """Detection sidecar (pano frame) -> (eye, look_target, fov) in the
    RENDER frame. Mapping verified 08-04 by the refcam box check: 25/28
    placed boxes land on their detection boxes, hits within a few px."""
    d_p = np.array([float(t) for t in sidecar["look"].split(",")])
    d_raw = np.array([d_p[0], -d_p[1], d_p[2]])   # recorded pano->raw
    eye = np.asarray(eye_raw) * R2R
    fwd = d_raw * R2R
    return eye, eye + fwd, float(sidecar["fov"])


def render_object_rgba(meshes, eye, target, fov, res):
    """The target ALONE on transparency, composited over the shell render
    (user ruling 08-04: no shell offsets -- layering keeps wall-flush
    pictures and floor-sunk mats visible where a joint z-buffer render
    would swallow them)."""
    scene = pyrender.Scene(bg_color=[0, 0, 0, 0], ambient_light=[0.5] * 3)
    for m in meshes:
        scene.add(pyrender.Mesh.from_trimesh(m, smooth=False))
    pose = look_at_pose(np.asarray(eye, float), np.asarray(target, float),
                        [0, 1, 0])
    scene.add(pyrender.PerspectiveCamera(yfov=np.radians(fov)), pose=pose)
    scene.add(pyrender.DirectionalLight(intensity=3.0), pose=pose)
    side = look_at_pose(np.asarray(target, float) + np.array([1.5, 2.5, 1.0]),
                        np.asarray(target, float), [0, 1, 0])
    scene.add(pyrender.DirectionalLight(intensity=1.5), pose=side)
    r = pyrender.OffscreenRenderer(res, res)
    color, _ = r.render(scene, flags=pyrender.RenderFlags.RGBA)
    r.delete()
    return Image.fromarray(color, "RGBA")


def render_layered(shell, tgt, eye, look, fov, res):
    img = render_frame(shell, eye, look, fov, res=res).convert("RGBA")
    img.alpha_composite(render_object_rgba(tgt, eye, look, fov, res))
    return img.convert("RGB")


def item_cams(ctr, diag, room_c, fy):
    # eye heights are floor-RELATIVE (the 08-12 blank-floor lesson)
    eyeA = np.array([0.0, fy + 1.6, 0.0])
    dist = float(np.linalg.norm(ctr - eyeA))
    fovA = float(np.clip(np.degrees(2 * np.arctan2(0.8 * diag, dist)), 30, 75))
    horiz = room_c - np.array([ctr[0], 0, ctr[2]])
    horiz[1] = 0
    n = np.linalg.norm(horiz)
    horiz = horiz / n if n > 1e-6 else np.array([1.0, 0, 0])
    eyeB = ctr + horiz * (1.5 * diag) + np.array([0, 0.9 * diag, 0])
    eyeB[1] = max(eyeB[1], fy + 0.6)
    return {"A": (eyeA, fovA), "B": (eyeB, 45.0)}


def ctx_cam(ctr, wx, wz, room_c, fy):
    best, bestd = None, -1.0
    for x in wx:
        for z in wz:
            c = np.array([x, fy, z])
            d = np.linalg.norm(c - np.array([ctr[0], fy, ctr[2]]))
            if d > bestd:
                bestd, best = d, c
    inward = room_c - best
    inward[1] = 0
    inward = inward / max(np.linalg.norm(inward), 1e-6)
    return best + inward * 0.35 + np.array([0.0, 2.30, 0.0]), 75.0


def project(pose, fov_deg, res, pts):
    inv = np.linalg.inv(pose)
    f = 1.0 / np.tan(np.radians(fov_deg) / 2.0)
    uv = []
    for p in pts:
        pc = (inv @ np.append(np.asarray(p, float), 1.0))[:3]
        z = -pc[2]
        if z <= 1e-6:
            continue
        uv.append((((pc[0] / z) * f + 1.0) / 2.0 * res,
                   (1.0 - (pc[1] / z) * f) / 2.0 * res))
    return uv


def best_evidence(node):
    """Untruncated first, then highest score. None = never seen."""
    mem = (node.get("evidence") or {}).get("members") or []
    if not mem:
        return None
    return sorted(mem, key=lambda m: (bool(m.get("truncated")),
                                      -float(m.get("score") or 0.0)))[0]


def load_swap_map(cdir):
    """edit_proposals.json swap lineage -> {in_id: (out_ids, out_names)}."""
    p = cdir / "edit_proposals.json"
    if not p.exists():
        return {}
    out = {}
    for s in (json.loads(p.read_text(encoding="utf-8")).get("swaps") or []):
        for item in (s.get("in") or []):
            out[item["id"]] = (s.get("out") or [], s.get("out_names") or [])
    return out


def resolve_reference(oid, nodes, swap_map):
    """-> (member, orig_name). Own evidence first; a SWAP item inherits the
    photograph of the object it replaced (user ruling 08-04 -- the swap
    placer packs the new item into the old one's envelope, so the
    original's position/facing anchor the replacement). orig_name is set
    only on the swap path. (None, None) = strict add, no reference."""
    mem = best_evidence(nodes.get(oid, {}))
    if mem:
        return mem, None
    if oid in swap_map:
        out_ids, out_names = swap_map[oid]
        for i, out_id in enumerate(out_ids):
            m = best_evidence(nodes.get(out_id, {}))
            if m:
                return m, (out_names[i] if i < len(out_names)
                           else (out_names[0] if out_names else "object"))
    return None, None


def ref_sheet(scene_dir, member, oid, out_path, compass=None):
    """Two panels, both MIRRORED BACK to true left-right (the pano frame is
    a defined mirror -- PLAN_SELF_PANO_RIG; a facing question inverts
    without this). Box drawn at mirrored coordinates, label readable.
    compass=(pose, fov, origin): draw the floor rose on the wide panel --
    valid because the corrected photo and the proper camera share pixel
    coords (the refcam box check proved it)."""
    # same rule as cut_crops/node_evidence: a member may state its own
    # scene-relative img (rcc retakes do); else the canonical rig crops.
    # pano_crops/ is the RETIRED week8 dir, kept as a last-resort legacy read.
    if member.get("img"):
        view_p = scene_dir / member["img"]
    else:
        view_p = scene_dir / "rig_sp0" / "crops" / f"{member['view']}.webp"
    if not view_p.exists():
        view_p = scene_dir / "pano_crops" / f"{member['view']}.webp"
    crop_p = scene_dir / "graph" / "crops" / member["crop"]
    if not view_p.exists() or not crop_p.exists():
        return None
    wide = Image.open(view_p).convert("RGB")
    if wide.size != (REF_W, REF_W):
        wide = wide.resize((REF_W, REF_W))
    wide = ImageOps.mirror(wide)
    b = member.get("box_2d")
    if b and len(b) == 4:
        x0, x1 = REF_W - b[2], REF_W - b[0]
        d = ImageDraw.Draw(wide)
        d.rectangle([x0 - 3, b[1] - 3, x1 + 3, b[3] + 3],
                    outline=(255, 220, 0), width=5)
        d.text((x0, max(0, b[1] - 16)), oid, fill=(255, 220, 0))
    if compass:
        wide = draw_compass(wide, compass[0], compass[1], REF_W, compass[2])
    close = ImageOps.mirror(Image.open(crop_p).convert("RGB"))
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
    d.text((8, 9), f"the real room -- view {member['view']}, {oid} outlined "
                   "(mirror corrected)", fill=(255, 255, 60))
    d.text((REF_W + GAP + 8, 9), "the real object, close up",
           fill=(255, 255, 60))
    sheet.save(out_path)
    return out_path


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--cams", default="A,B")
    ap.add_argument("--items", default="all",
                    help="'all' = every object in fitted_preview")
    ap.add_argument("--jobs", type=int, default=6)
    ap.add_argument("--timeout", type=int, default=480)
    ap.add_argument("--renders-only", action="store_true")
    ap.add_argument("--prune", action="store_true",
                    help="footprint-prune candidates (tried 08-04: broke "
                         "the bed benchmark; off by default)")
    ap.add_argument("--compass", action="store_true",
                    help="add camera-anchored NESW anchors and require "
                         "real_faces/placed_faces in the reply (user "
                         "experiment 08-04)")
    args = ap.parse_args()
    cams = [c.strip() for c in args.cams.split(",") if c.strip()]

    scene_dir = paths.scene_dir(args.scene)
    cdir, nodes, by_item, shell, wx, wz, room_c, fy = load_scene(args.scene)
    placed = json.loads((cdir / "fitted_preview.json")
                        .read_text(encoding="utf-8"))["placed"]
    names = {p["id"]: p["name"] for p in placed}
    attach = {p["id"]: (p.get("attachment")
                        or ([p["mount"]] if p.get("mount") else []))
              for p in placed}
    # measurement basis: verdicts are only valid for the asset they were
    # rendered against (uid) AND are DELTAS on top of whatever rotation
    # the measured preview already carried -- fit_preview composes
    # measured_applied_deg + the fresh delta (a 0 verdict on a corrected
    # object means KEEP the correction, not undo it)
    uids = {p["id"]: p.get("uid") for p in placed}
    applied0 = {p["id"]: p.get("rotcheck_applied_deg", 0.0)
                for p in placed}
    items = ([p["id"] for p in placed] if args.items == "all"
             else [i.strip() for i in args.items.split(",") if i.strip()])
    swap_map = load_swap_map(cdir)

    rdir = cdir / "rotation_check"
    rdir.mkdir(exist_ok=True)
    (rdir / "sheets").mkdir(exist_ok=True)

    # ---------------- stimuli: one clean folder per call ------------------
    # SAME-CAMERA form (user gate passed 08-04): a referenced object gets
    # ONE call -- reference photo | the reconstruction from THE SAME camera,
    # object isolated and layered over the shell. The camera question
    # dissolves: the canonical camera is the one that saw the object.
    rig = scene_dir / "rig_sp0"
    eye_raw = json.loads((rig / "pano_selfrender_meta.json")
                         .read_text(encoding="utf-8"))["eye_raw"]
    t0 = time.time()
    jobs_list = []          # (oid, cam_tag, folder, prompt, mode)
    geo = {}
    skipped = []
    for oid in items:
        if oid not in by_item:
            skipped.append(oid)
            continue
        tgt = by_item[oid]
        others = [m for k, v in by_item.items() if k != oid for m in v]
        allb = np.vstack([m.bounds for m in tgt])
        lo, hi = allb.min(0), allb.max(0)
        ctr = (lo + hi) / 2
        diag = float(np.linalg.norm(hi - lo))
        name = names.get(oid, "object")

        mem, orig_name = resolve_reference(oid, nodes, swap_map)
        ref_master = None
        if mem:
            # camera first: with --compass the ref sheet needs it to draw
            # the rose on the photo panel
            # sidecar next to the photo, carrying its name (the
            # cut_crops/node_evidence rule); pano_crops/ = retired legacy
            if mem.get("img"):
                side_p = (scene_dir / mem["img"]).with_suffix(".json")
            else:
                side_p = rig / "crops" / f"{mem['view']}.json"
            if not side_p.exists():
                side_p = scene_dir / "pano_crops" / f"{mem['view']}.json"
            side = json.loads(side_p.read_text(encoding="utf-8"))
            eye, look, fov = detection_cam_render_frame(side, eye_raw)
            pose = look_at_pose(np.asarray(eye, float),
                                np.asarray(look, float), [0, 1, 0])
            origin = compass_origin(lo, hi, eye, fy)
            # rose on the ref ALWAYS (08-04: a describe prompt promised a
            # rose the ref lacked — the model rightly spent 20 turns not
            # finding it; the stimulus must carry what any prompt claims)
            comp = (pose, fov, origin)
            ref_master = ref_sheet(scene_dir, mem, oid,
                                   rdir / f"{oid}_ref.png", compass=comp)

        if ref_master:
            # CANON v2 (user 08-04: "if we have something that works and
            # don't rely on the asset implied presets, let's just do
            # that"): 4-candidate CHOICE. Four SEPARATE full-size renders
            # (never a strip -- the composite made the judge tool up), the
            # photo's own camera, object isolated + layered, rose beside
            # it. The judge COMPARES; it never has to name the render's
            # facing (the channel that failed 6/6 on the bed) and nothing
            # depends on the asset's canonical front (the bed's +z=head
            # defect is exactly what this form caught: benchmark HIT).
            mode = ("match_swap_origin" if orig_name else "match_reference")
            folder = rdir / f"{oid}_same"
            folder.mkdir(exist_ok=True)
            # clean-folder rule: stale stimuli out (replies stay -- they
            # are the stimulus-keyed cache)
            for f in list(folder.glob("*.png")) + [folder / "prompt.txt"]:
                if f.exists():
                    f.unlink()
            shutil.copyfile(ref_master, folder / "ref.png")

            # deterministic prune vs the OBSERVED box (graph evidence);
            # swap items have no graph node -- their own placed bounds
            # stand in as the envelope (still prunes oblong 90/270)
            gnode = nodes.get(oid)
            if gnode and gnode.get("geometry", {}).get("aabb_min"):
                gb = gnode["geometry"]
                box_lo = np.array(gb["aabb_min"]) * np.array([-1, -1, 1])
                box_hi = np.array(gb["aabb_max"]) * np.array([-1, -1, 1])
                box_lo, box_hi = np.minimum(box_lo, box_hi), \
                    np.maximum(box_lo, box_hi)
            else:
                box_lo, box_hi = lo, hi
            # PRUNE OFF BY DEFAULT (user 08-04 "fuck that then lets not use
            # it"): sound geometry, but the binary lineup broke the bed
            # benchmark (180 high-conf -> 0 medium) while saving only ~15%.
            # The 90/270 candidates act as contrast anchors. Kept behind
            # --prune with this measurement so nobody re-invents it blind.
            # WALL LEGALITY is separate and ON by default (user 08-05):
            # wall items only ever see poses that stand IN their wall.
            spins = legal_spins(lo, hi, box_lo, box_hi,
                                "wall" in (attach.get(oid) or []))
            if len(spins) < 4:
                print(f"[rot] {oid} wall-legality menu: {spins}")
            if args.prune:
                keep = plausible_spins(lo, hi, box_lo, box_hi)
                spins = [s for s in spins if s in keep]

            cand = {}
            for letter, cdeg in zip(LETTERS, spins):
                spun_m = []
                for m in tgt:
                    mm = m.copy()
                    mm.apply_transform(yaw_about(ctr, cdeg))
                    spun_m.append(mm)
                cimg2 = render_layered(shell, spun_m, eye, look, fov, REF_W)
                cimg2 = draw_compass(cimg2, pose, fov, REF_W, origin)
                cimg2 = crop_to_object(cimg2, pose, fov, REF_W, lo, hi,
                                       origin)
                cimg2.save(folder / f"candidate_{letter}.png")
                cand[letter] = cdeg
            cands_txt = "\n".join(
                f"candidate {le}: {folder / f'candidate_{le}.png'}"
                for le in cand)
            letters_txt = "|".join(f'"{le}"' for le in cand)
            tpl = P_CHOICE_SWAP if orig_name else P_CHOICE
            prompt = tpl.format(ref=folder / "ref.png", name=name,
                                orig_name=orig_name or "", n=len(cand),
                                cands=cands_txt, letters=letters_txt)
            geo[oid] = {"kind": "det", "cam": (eye, look, fov), "ctr": ctr,
                        "tgt": tgt, "others": None, "mode": mode,
                        "view": mem["view"], "mapping": cand,
                        "compass": (pose, fov, origin)}
            jobs_list.append((oid, "det", folder, prompt, mode))
        else:
            # strict add: never seen anywhere -- plausibility, camera A only
            mode = "plausible_fallback"
            ceye, cfov = ctx_cam(ctr, wx, wz, room_c, fy)
            cimg = render_frame(shell + others + tgt, ceye, room_c, cfov,
                                res=CTX_RES)
            cpose = look_at_pose(np.asarray(ceye, float),
                                 np.asarray(room_c, float), [0, 1, 0])
            uv = project(cpose, cfov, CTX_RES,
                         [(x, y, z) for x in (lo[0], hi[0])
                          for y in (lo[1], hi[1]) for z in (lo[2], hi[2])])
            if uv:
                us, vs = [p[0] for p in uv], [p[1] for p in uv]
                d = ImageDraw.Draw(cimg)
                box = [min(us) - 6, min(vs) - 6, max(us) + 6, max(vs) + 6]
                d.rectangle(box, outline=(255, 220, 0), width=4)
                d.text((box[0], max(0, box[1] - 14)), oid,
                       fill=(255, 220, 0))
            eyeA, fovA = item_cams(ctr, diag, room_c, fy)["A"]
            folder = rdir / f"{oid}_camA"
            folder.mkdir(exist_ok=True)
            render_frame(shell + others + tgt, eyeA, ctr, fovA,
                         res=TILE).save(folder / "item.png")
            cimg.save(folder / "ctx.png")
            prompt = ASK_PLAUSIBLE.format(item=folder / "item.png",
                                          ctx=folder / "ctx.png", name=name,
                                          oid=oid, convention=CONVENTION)
            geo[oid] = {"kind": "A", "cam": (eyeA, ctr, fovA), "ctr": ctr,
                        "tgt": tgt, "others": others, "mode": mode,
                        "view": None}
            jobs_list.append((oid, "A", folder, prompt, mode))
        (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
    render_s = time.time() - t0
    print(f"[rot] {len(jobs_list)} calls staged "
          f"({len(items) - len(skipped)} objects, ONE call each), renders "
          f"{render_s:.1f}s"
          + (f", skipped (not in preview): {skipped}" if skipped else ""))
    if args.renders_only:
        return

    # ---------------- one wave: every call independent ---------------------
    def fire(job):
        oid, cam, folder, prompt, mode = job
        # replies are STIMULUS-KEYED (08-04): prompt text AND image bytes --
        # a restyled overlay changes only the pixels, and that must not
        # reuse a stale answer. Legacy reply.txt is adopted only for the
        # unchanged non-compass prompt it was paid under.
        hh = hashlib.md5(prompt.encode("utf-8"))
        for f in sorted(folder.glob("*.png")):
            hh.update(f.read_bytes())
        h = hh.hexdigest()[:10]
        raw_p = folder / f"reply_{h}.txt"
        legacy = folder / "reply.txt"
        if not raw_p.exists() and legacy.exists() and not args.compass:
            legacy.rename(raw_p)
        if raw_p.exists() and raw_p.read_text(encoding="utf-8").strip():
            print(f"[rot] {oid} reused from disk")
            return job, raw_p.read_text(encoding="utf-8"), 0.0, \
                {"reused": True}
        try:
            txt, dt, cost = call_measured(prompt, folder, args.model,
                                          args.timeout)
        except Exception as e:
            print(f"[rot] {oid} FAILED: {type(e).__name__}: {str(e)[:150]}")
            return job, "", 0.0, {"error": type(e).__name__}
        raw_p.write_text(txt, encoding="utf-8")
        print(f"[rot] {oid} -> {(parse_json_obj(txt) or {}).get('degrees')} "
              f"({dt:.1f}s, {cost.get('num_turns')} turns)")
        return job, txt, dt, cost

    t_wave = time.time()
    results = []
    with ThreadPoolExecutor(max_workers=args.jobs) as ex:
        for out in ex.map(fire, jobs_list):
            results.append(out)
    wave_s = time.time() - t_wave

    # ---------------- record + review sheets ------------------------------
    rec = {"scene": args.scene, "model": args.model, "date": "2026-08-04",
           "canon": "SAME-CAMERA direct ask: reference photo | isolated "
                    "layered render from the detection camera, one call per "
                    "object (pairs gate passed 08-04); swaps inherit the "
                    "replaced object's photo; strict adds -> plausibility",
           "note": "record only -- nothing applied to fitted_preview; "
                   "user eyeballs = GT",
           "jobs": args.jobs, "render_s": round(render_s, 1),
           "wave_s": round(wave_s, 1), "runs": []}

    t0 = time.time()
    for (oid, cam, folder, _p, mode), txt, dt, cost in results:
        j = parse_json_obj(txt) or {}
        g = geo[oid]
        d = j.get("degrees")
        deg = wrap180(d) if isinstance(d, (int, float)) else None
        deg_src = "model"
        pick = str(j.get("pick", "")).strip().lower() or None
        if deg is None and pick and g.get("mapping") \
                and pick in g["mapping"]:
            deg, deg_src = wrap180(g["mapping"][pick]), "choice_pick"
        rf, pf = j.get("real_faces"), j.get("placed_faces")
        imp = implied_degrees(pf, rf) if (rf or pf) else None
        if deg is None and imp is not None:
            deg, deg_src = imp, "computed_from_faces"
        entry = {
            "item": oid, "name": names.get(oid, "object"), "mode": mode,
            "measured_uid": uids.get(oid),
            "measured_applied_deg": applied0.get(oid, 0.0),
            "cam": cam, "view": g["view"], "degrees": deg,
            "degrees_source": deg_src, "pick": pick,
            "mapping": g.get("mapping"),
            "confidence": j.get("confidence"), "why": j.get("why"),
            "model_s": round(dt, 2), "cost": cost}
        if rf or pf:
            entry.update({
                "real_faces": rf, "placed_faces": pf,
                "real_desc": j.get("real_desc"),
                "placed_desc": j.get("placed_desc"),
                "implied_degrees": imp, "degrees_source": deg_src})
        rec["runs"].append(entry)

        # review sheet: as placed | answer applied, from the SAME camera
        eye, look, fov = g["cam"]
        if g["kind"] == "det":
            base = Image.open(folder / "candidate_a.png")  # a = 0, as placed
            res_px = REF_W
        else:
            base = Image.open(folder / "item.png")
            res_px = TILE
        tiles = [(base, "as placed (0)")]
        if deg is not None and abs(deg) > 1e-6:
            if g["kind"] == "det" and pick and (folder /
                                                f"candidate_{pick}.png"
                                                ).exists():
                img = Image.open(folder / f"candidate_{pick}.png")
            else:
                R = yaw_about(g["ctr"], deg)
                spun = []
                for m in g["tgt"]:
                    mm = m.copy()
                    mm.apply_transform(R)
                    spun.append(mm)
                if g["kind"] == "det":
                    img = render_layered(shell, spun, eye, look, fov, res_px)
                    if g.get("compass"):
                        img = draw_compass(img, g["compass"][0],
                                           g["compass"][1], res_px,
                                           g["compass"][2])
                else:
                    img = render_frame(shell + g["others"] + spun, eye, look,
                                       fov, res=res_px)
            tiles.append((img, f"answer: {deg:+.0f}"))
        elif deg is not None:
            tiles.append((base.copy(), "answer: keep (0)"))
        else:
            tiles.append((Image.new("RGB", (res_px, res_px), (60, 30, 30)),
                          "NO ANSWER"))
        W = res_px * 2 + GAP
        sheet = Image.new("RGB", (W, res_px + 30), (25, 25, 25))
        for i2, (t, lab) in enumerate(tiles):
            sheet.paste(t, (i2 * (res_px + GAP), 30))
            ImageDraw.Draw(sheet).text((i2 * (res_px + GAP) + 8, 9), lab,
                                       fill=(255, 255, 60))
        ImageDraw.Draw(sheet).text(
            (W - 340, 9), f"{oid} {names.get(oid, '?')} / {mode}",
            fill=(150, 220, 255))
        sheet.save(rdir / "sheets" / f"{oid}.png")
    rec["render_s"] = round(rec["render_s"] + time.time() - t0, 1)

    rec["runs"].sort(key=lambda r: r["item"])
    out_p = cdir / "rotation_check.json"
    out_p.write_text(json.dumps(rec, indent=2), encoding="utf-8")

    n_ans = sum(1 for r in rec["runs"] if r["degrees"] is not None)
    n_nz = sum(1 for r in rec["runs"] if r["degrees"] not in (None, 0.0))
    print(f"\n[rot] {len(rec['runs'])} objects, {n_ans}/{len(results)} "
          f"answered, {n_nz} non-zero answers")
    print(f"[rot] wall {wave_s:.0f}s wave + {rec['render_s']}s renders "
          f"-> {out_p}")


if __name__ == "__main__":
    main()
