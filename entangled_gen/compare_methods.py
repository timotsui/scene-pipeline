"""compare_methods.py — put our reconstruction and the GL-TreeSearch
baseline side by side on the one input they share, without pretending the
contest is fair.

WHAT IS BEING COMPARED. Both methods are handed the SAME Marble prompt —
the paragraph the scene was generated from — and both end up with a list
of named boxes. Ours comes from the scene graph's current layer, which
was built by looking at a capture of the real room. GLTS's comes from
13_furniture_layout.json and friends, which were built from the paragraph
and nothing else. glts_run.py produced that side; this file scores both.

WHAT THIS IS NOT. It is not a leaderboard. There is no combined number
here and there will not be one, because no scalar means the same thing
across a method that MEASURES a room and a method that INVENTS one. Every
axis is reported on its own and labelled either

    COMPARABLE  both methods were measured the same way on the same input
    ASYMMETRIC  only one of them can be scored on this at all, and the
                report says which and why

THE TRAP, WHICH THE REPORT STATES OUT LOUD. GLTS optimises DIRECTLY for
the prompt text: the paragraph is its whole world, so naming what the
paragraph names is the task it was given. Ours reconstructs what is
actually in the room. When the prompt says "sheer white curtains" and the
real room has none, ours correctly omits them and scores WORSE on prompt
fidelity. A lower prompt-fidelity number for our method is therefore not
evidence of worse performance — it may be the method working exactly as
intended. Anyone reading section B without that sentence in front of them
will read it backwards, so the sentence is printed at the top of the HTML
and again inside the section.

READ-ONLY. This tool opens scene data and never writes it. The only two
files it creates are its own report, out/comparison_<runid>.{json,html}.

    python compare_methods.py --scene living_marble
    python compare_methods.py --scenes living_marble,bedroom_marble
    python compare_methods.py --scene bedroom_marble --glts-root <path>
"""
import argparse
import html as _html
import json
import math
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import paths
import vocab_from_prompt as vocab

HERE = Path(__file__).resolve().parent
for _p in (HERE, HERE / "graph"):
    if str(_p) not in sys.path:
        sys.path.insert(0, str(_p))
import scene_state                                        # noqa: E402
import stages                                             # noqa: E402

#: Same rule glts_run.py uses, so the two tools cannot disagree about
#: where GLTS lives: local_paths.json wins, the documented checkout is
#: the fallback.
GLTS_WIN = Path(paths.CFG.get(
    "treesearchgen",
    r"D:\T\Documents\GeorgiaTech\Summer2026\Research\code\working\TreeSearchGen"))

# ---- the rules, in one place, because a rule nobody can see is not a
# ---- measurement. Every one of these numbers is printed beside the
# ---- result it produced.

#: two boxes count as interpenetrating only past this much shared volume.
#: Boxes that merely touch, or that clip by a millimetre because one was
#: rounded, are not a physics failure and should not be counted as one.
OVERLAP_MIN_M3 = 1e-4                      # 0.1 litre

#: a pair is ignored when the smaller box is at least this much inside the
#: larger one. That is containment — a book in a bookshelf, a monitor
#: whose box sits inside the desk's — and containment is legitimate in
#: both methods' output.
CONTAINMENT_FRAC = 0.90

#: how far above the floor a box's underside has to be before we go
#: looking for something holding it up.
FLOAT_CLEARANCE_M = 0.05

#: how much of a box's footprint another box has to cover before it counts
#: as the thing underneath it.
SUPPORT_FOOTPRINT_FRAC = 0.25

#: a box is outside the room when it pokes past a wall by more than this.
#: Wall planes are measured to the centimetre, so anything under this is
#: the measurement, not the layout.
OUTSIDE_TOL_M = 0.02

#: node ids that are architecture, not objects
ARCH_PREFIXES = ("arch_", "wall_", "room_")

#: names GLTS gives to architecture inside its object files
GLTS_NON_OBJECTS = {"floor", "wall", "ceiling", "room"}


# ===================== naming and matching ============================

def _norm_token(t):
    """Lowercase, de-plural, and put through the repo's own synonym table.

    Plural stripping is deliberately crude — an 's' or 'es' off the end of
    a word longer than three letters. It is enough for "baskets"/"basket"
    and "shelves" is simply missed, which is a limit worth having in the
    open rather than a stemmer nobody can predict."""
    t = re.sub(r"[^a-z0-9 ]+", "", t.lower()).strip()
    t = vocab.NORMALIZE.get(t, t)
    if len(t) > 3 and t.endswith("es") and not t.endswith("ss"):
        t = t[:-2]
    elif len(t) > 3 and t.endswith("s") and not t.endswith("ss"):
        t = t[:-1]
    return vocab.NORMALIZE.get(t, t)


def norm_name(name):
    """A name as a normalised token list, e.g. 'Sectional Sofas' -> ['sofa'].

    The whole phrase goes through the synonym table first (so "wall art"
    becomes "picture" as one unit), then each token separately."""
    raw = re.sub(r"[^a-z0-9 ]+", " ", (name or "").lower()).strip()
    raw = vocab.NORMALIZE.get(raw, raw)
    toks = [_norm_token(t) for t in raw.split()]
    return [t for t in toks if t]


def names_match(noun, name):
    """Does this output name refer to the prompt's noun? `noun` is the
    prompt's word, `name` is the method's object name — the order matters.

    THE RULE, stated once and printed in the report. Normalise both sides
    (lowercase, punctuation dropped, simple de-pluralisation, the repo's
    NORMALIZE synonyms applied) and split into tokens. It is a match when
    BOTH of these hold:

      * the noun's HEAD WORD — its last token, the thing it actually is —
        appears in the name. "desk lamp" is a lamp, so a lamp must be
        named; an object called "desk" does not satisfy it.
      * one token set is a subset of the other, which is what lets
        "sectional sofa" satisfy "sofa" and "ladder bookshelf" satisfy
        "bookshelf".

    The head test was added after a hand check caught the subset rule on
    its own crediting "desk lamp" to an object named "desk", on BOTH
    methods' output. Being forgiving about wording is the point; being
    forgiving about what the thing is is how a fidelity number stops
    meaning anything. "shelf" still does not match "bookshelf" — different
    words, and guessing they are the same would be the same mistake in a
    politer form."""
    A, B = norm_name(noun), norm_name(name)
    if not A or not B:
        return False
    if A[-1] not in B:
        return False
    sa, sb = set(A), set(B)
    return sa <= sb or sb <= sa


MATCH_RULE_TEXT = (
    "Both sides are lowercased, stripped of punctuation, de-pluralised "
    "(a trailing 's'/'es' on a word longer than three letters), and put "
    "through vocab_from_prompt.NORMALIZE (couch->sofa, painting->picture, "
    "tv->television), then split into tokens. A prompt noun is matched by "
    "an object name when the noun's HEAD WORD (its last token) appears in "
    "the name AND one token set is a subset of the other. So 'sofa' is "
    "matched by 'sectional sofa' and 'bookshelf' by 'ladder bookshelf', "
    "while 'desk lamp' is NOT matched by 'desk' (no lamp) and 'bookshelf' "
    "is not matched by 'shelf' (different word).")


# ===================== geometry, shared by both sides =================

def box_volume(b):
    return max(0.0, b[3] - b[0]) * max(0.0, b[4] - b[1]) * max(0.0, b[5] - b[2])


def box_intersection(a, b):
    """(volume, per-axis overlap) of two [xmin,ymin,zmin,xmax,ymax,zmax]."""
    ov = [max(0.0, min(a[i + 3], b[i + 3]) - max(a[i], b[i])) for i in range(3)]
    return ov[0] * ov[1] * ov[2], ov


def footprint_overlap(a, b):
    """Shared plan-view area, in square metres. Up is the LAST axis in the
    common representation, so the footprint is axes 0 and 1."""
    ox = max(0.0, min(a[3], b[3]) - max(a[0], b[0]))
    oy = max(0.0, min(a[4], b[4]) - max(a[1], b[1]))
    return ox * oy


def interpenetration(objs):
    """Every pair of boxes that shares real volume, minus the pairs where
    one is simply inside the other.

    Computed IDENTICALLY for both methods — same function, same constants
    — which is the only reason section C can call itself comparable."""
    pairs, total, contained = [], 0.0, 0
    for i in range(len(objs)):
        for j in range(i + 1, len(objs)):
            a, b = objs[i], objs[j]
            vol, ov = box_intersection(a["box"], b["box"])
            if vol <= OVERLAP_MIN_M3:
                continue
            va, vb = box_volume(a["box"]), box_volume(b["box"])
            small = min(va, vb)
            if small > 0 and vol >= CONTAINMENT_FRAC * small:
                contained += 1                  # legitimate: one is inside
                continue
            total += vol
            pairs.append({"a": a["name"], "b": b["name"],
                          "a_id": a.get("id"), "b_id": b.get("id"),
                          "volume_m3": round(vol, 4),
                          "overlap_xyz_m": [round(v, 3) for v in ov],
                          "frac_of_smaller": round(vol / small, 3)
                          if small else None})
    pairs.sort(key=lambda p: -p["volume_m3"])
    return {"pairs": len(pairs), "volume_m3": round(total, 4),
            "ignored_containment_pairs": contained, "worst": pairs[:12]}


def outside_room(objs, room):
    """Objects poking through a wall, the floor or the ceiling.

    `room` is an axis-aligned box in the same frame as the objects. For
    our side that is the bounding box of the measured shell, which is
    generous for an L-shaped room — an object inside the bounding box but
    outside the polygon is not counted, and the report says so."""
    out = []
    for o in objs:
        b, worst, axes = o["box"], 0.0, []
        for i, ax in enumerate("xyz"):
            lo = room[i] - b[i]                   # how far past the low side
            hi = b[i + 3] - room[i + 3]           # ... and the high side
            for d, side in ((lo, "-"), (hi, "+")):
                if d > OUTSIDE_TOL_M:
                    axes.append(f"{side}{ax} by {d:.2f} m")
                    worst = max(worst, d)
        if axes:
            out.append({"name": o["name"], "id": o.get("id"),
                        "worst_m": round(worst, 3), "how": axes})
    out.sort(key=lambda r: -r["worst_m"])
    return {"count": len(out), "worst_m": out[0]["worst_m"] if out else 0.0,
            "objects": out[:12]}


def floating(objs, floor_up):
    """Boxes whose underside is clear of the floor with nothing beneath.

    THE RULE: the underside is more than 5 cm above the floor, and no
    other object's box both starts below that underside and reaches to
    within 5 cm of it while covering at least a quarter of its footprint.

    A CAVEAT THAT MATTERS FOR OUR SIDE, and it is printed in the report:
    real rooms hang things on walls. A picture, a wall-mounted air
    conditioner and a ceiling light are all correctly floating, so this
    count is not an error count for a reconstruction — it is a
    description. The names are listed for exactly that reason."""
    flo = []
    for o in objs:
        bottom = o["box"][2]
        if bottom - floor_up <= FLOAT_CLEARANCE_M:
            continue
        area = ((o["box"][3] - o["box"][0]) * (o["box"][4] - o["box"][1]))
        held = None
        for p in objs:
            if p is o:
                continue
            if p["box"][2] > bottom or p["box"][5] < bottom - FLOAT_CLEARANCE_M:
                continue
            if area <= 0:
                continue
            if footprint_overlap(o["box"], p["box"]) >= SUPPORT_FOOTPRINT_FRAC * area:
                held = p["name"]
                break
        if held is None:
            flo.append({"name": o["name"], "id": o.get("id"),
                        "underside_m": round(bottom - floor_up, 3)})
    flo.sort(key=lambda r: -r["underside_m"])
    return {"count": len(flo), "objects": flo[:20]}


def physical_validity(objs, room, floor_up):
    return {"n_objects": len(objs),
            "interpenetration": interpenetration(objs),
            "outside_room": outside_room(objs, room),
            "floating": floating(objs, floor_up)}


# ===================== our side =======================================

def ours_frame(scene):
    """The elementwise sign flip that takes a raw box to the upright frame.

    room_shell.json records it (raw_to_render, self-inverse); the scene's
    frame block is the fallback for a scene that has no shell yet."""
    shell = paths.scene_dir(scene) / "room_shell.json"
    if shell.exists():
        d = json.loads(shell.read_text(encoding="utf-8"))
        r2r = (d.get("frame") or {}).get("raw_to_render")
        if r2r:
            return [float(v) for v in r2r]
    try:
        fb = paths.frame_block(scene)
        if fb.get("raw_to_render"):
            return [float(v) for v in fb["raw_to_render"]]
    except SystemExit:
        pass
    return [1.0, 1.0, 1.0]


def to_common(lo, hi, r2r):
    """A raw axis-aligned box -> the common representation.

    COMMON REPRESENTATION, used for BOTH methods: metres, axis-aligned,
    [xmin, ymin, zmin, xmax, ymax, zmax], the first two axes are the floor
    plan and THE LAST AXIS IS UP with the floor at its own room's floor
    height. Our boxes arrive in the raw bundle frame where up is -y, so
    they are flipped into the upright frame and then the axes are reordered
    (x, z, y) to put up last. GLTS already writes z-up, so its boxes need
    no reordering — which is the whole point of having one representation."""
    up = [lo[i] * r2r[i] for i in range(3)]
    uq = [hi[i] * r2r[i] for i in range(3)]
    a = [min(up[i], uq[i]) for i in range(3)]
    b = [max(up[i], uq[i]) for i in range(3)]
    # upright is (x, y=up, z) -> common is (x, z, up)
    return [a[0], a[2], a[1], b[0], b[2], b[1]]


def load_ours(scene):
    """Our objects, our room, and enough provenance to argue with."""
    out = {"available": False, "why": ""}
    gp = paths.scene_dir(scene) / "scene_graph.json"
    if not gp.exists():
        out["why"] = f"no scene_graph.json for {scene}"
        return out
    graph = json.loads(gp.read_text(encoding="utf-8"))
    layer_name, layer = scene_state.current(graph)
    if not layer:
        out["why"] = f"{scene}'s graph has no whole layer"
        return out
    r2r = ours_frame(scene)
    objs = []
    for n in layer.get("nodes") or []:
        nid = n.get("id") or ""
        if nid.startswith(ARCH_PREFIXES):
            continue                    # architecture is the room, not an object
        g = n.get("geometry") or {}
        if not (g.get("aabb_min") and g.get("aabb_max")):
            continue
        objs.append({"id": nid, "name": n.get("name") or nid,
                     "box": to_common(g["aabb_min"], g["aabb_max"], r2r)})
    out.update({"available": True, "layer": layer_name,
                "layer_is_final": layer_name == stages.FINAL_LAYER,
                "chain_expected_final": stages.FINAL_LAYER,
                "n_nodes_in_layer": len(layer.get("nodes") or []),
                "objects": objs, "raw_to_render": r2r,
                "graph": str(gp)})
    out["room"] = load_room_shell(scene)
    return out


def _shoelace(vs):
    a = 0.0
    for i in range(len(vs)):
        x1, y1 = vs[i]
        x2, y2 = vs[(i + 1) % len(vs)]
        a += x1 * y2 - x2 * y1
    return abs(a) / 2.0


def load_room_shell(scene):
    """The MEASURED room: height from the floor/ceiling planes, footprint
    from the traced polygon when the scene has one and from the outer wall
    planes when it does not. Which of the two was used is reported, because
    a bounding box is not a polygon and an L-shaped room is where that
    difference shows."""
    p = paths.scene_dir(scene) / "room_shell.json"
    if not p.exists():
        return {"available": False, "why": f"no room_shell.json for {scene}"}
    d = json.loads(p.read_text(encoding="utf-8"))
    floor = float(d.get("floor_upright_m", 0.0))
    ceil = float(d.get("ceiling_upright_m", 0.0))
    poly = (d.get("polygon") or {}).get("vertices_upright")
    if poly:
        xs = [v[0] for v in poly]
        zs = [v[1] for v in poly]
        area, src = _shoelace(poly), "traced polygon (room_shell --poly)"
        bbox = [min(xs), min(zs), max(xs), max(zs)]
    else:
        planes = {}
        for w in d.get("walls") or []:
            planes.setdefault(w["axis"], []).append(float(w["plane_upright_m"]))
        if not ({"x", "z"} <= set(planes)):
            return {"available": False,
                    "why": "room_shell.json has neither a polygon nor "
                           "walls on both horizontal axes"}
        bbox = [min(planes["x"]), min(planes["z"]),
                max(planes["x"]), max(planes["z"])]
        area = (bbox[2] - bbox[0]) * (bbox[3] - bbox[1])
        src = ("outer wall planes — a rectangle, not a traced outline: "
               "this scene's shell has no polygon")
    return {"available": True, "floor_up_m": floor, "ceiling_up_m": ceil,
            "height_m": round(ceil - floor, 3),
            "footprint_area_m2": round(area, 2),
            "footprint_bbox_m": [round(v, 3) for v in bbox],
            "footprint_bbox_size_m": [round(bbox[2] - bbox[0], 3),
                                      round(bbox[3] - bbox[1], 3)],
            "footprint_source": src,
            "room_box": [bbox[0], bbox[1], floor, bbox[2], bbox[3], ceil],
            "file": str(p)}


def ours_cost(scene):
    """What our run cost, from the newest run record the scene has.

    A run record describes ONE INVOCATION, and an invocation is often a
    slice of the chain (`--from views`). The stage list is reported rather
    than a bare total so nobody reads a partial run as the whole pipeline;
    `covers_full_chain` says which it was."""
    recs = sorted(paths.scene_dir(scene).glob("run_scene_*.json"))
    if not recs:
        return {"available": False,
                "why": f"{scene} has no run_scene_*.json, so what our own "
                       f"run cost was never recorded for this scene"}
    p = recs[-1]
    d = json.loads(p.read_text(encoding="utf-8"))
    st = d.get("stages") or []
    ran = [s.get("stage") for s in st]
    llm = [k for k in ran if k in stages.BY_KEY and stages.BY_KEY[k].llm]
    total = round(sum(float(s.get("seconds") or 0) for s in st), 1)
    missing = [k for k in stages.KEYS if k not in ran]
    vote_s = next((float(s.get("seconds") or 0) for s in st
                   if s.get("stage") == "vote"), None)
    # TWO WAYS THIS NUMBER MISLEADS, both stated in the report rather
    # than left for a reader to fall into.
    #
    # 1. A RUN RECORD IS ONE INVOCATION, and an invocation is often a
    #    slice (`--from views`). The vote is the expensive stage by a
    #    long way — 2538 s of the bedroom's 57 min, about three quarters
    #    of it — so a record that skipped it is not a pipeline cost at
    #    all. It is labelled "chain minus vote", never "the total".
    # 2. NEITHER TOTAL INCLUDES THE GEOMETRIC CORE. Crop, segment and
    #    lift run before the graph chain and are not in stages.py, and
    #    GLTS has no counterpart to them whatsoever — there is no
    #    capture in its world to process. Our figure is therefore a
    #    LOWER BOUND on our method and the comparison is generous to us.
    label = ("the whole graph chain" if not missing else
             "chain minus " + ", ".join(missing))
    return {"available": True, "file": str(p), "runid": d.get("runid"),
            "seconds": total,
            "seconds_covers": label,
            "stages_run": ran, "stages_missing": missing,
            "vote_seconds": round(vote_s, 1) if vote_s else None,
            "vote_share_pct": round(100.0 * vote_s / total, 1)
            if vote_s and total else None,
            "llm_stages": llm, "n_llm_stages": len(llm),
            "covers_full_chain": not missing,
            "chain": list(stages.KEYS),
            "verdict": d.get("verdict"),
            "note": f"seconds is the sum of this record's per-stage times "
                    f"and covers {label}. The vote is the expensive stage "
                    f"(about three quarters of a full run), so a record "
                    f"without it is NOT a full-pipeline figure. AND NO "
                    f"RECORD HERE INCLUDES THE GEOMETRIC CORE — crop, "
                    f"segment and lift run before the graph chain, are not "
                    f"in graph/stages.py, and have no GLTS counterpart at "
                    f"all, so our cost is a LOWER BOUND. n_llm_stages "
                    f"counts stages graph/stages.py marks llm=True — "
                    f"stages, not calls: one judge stage makes one model "
                    f"call per node."}


# ===================== the GLTS side ==================================

def glts_dirs(scene, root_override=None):
    """(run root, the numbered output folder). --glts-root may point at
    either, so both spellings work."""
    if root_override:
        r = Path(root_override)
        return (r.parent, r) if r.name == "0" else (r, r / "0")
    r = GLTS_WIN / f"output_ovm_{scene}"
    return r, r / "0"


def glts_cost(root):
    """GLTS's own record of what it cost.

    glts_run.py writes glts_run.json. A run made before that existed has
    only its log, so the model calls are recounted from the log with
    glts_run's own counter and the wall clock is reported as unknown
    rather than guessed."""
    rec = root / "glts_run.json"
    if rec.exists():
        d = json.loads(rec.read_text(encoding="utf-8"))
        return {"available": True, "source": str(rec),
                "seconds": d.get("seconds"), "model_calls": d.get("model_calls"),
                "counted_by": d.get("model_calls_counted_by"),
                "returncode": d.get("returncode"), "ok": d.get("ok"),
                "steps": d.get("steps")}
    for cand in (root / "glts_run.log", root / "run.log",
                 root / "0" / "log.ansi"):
        if not cand.exists():
            continue
        import glts_run
        n, how = glts_run._count_calls(
            cand.read_text(encoding="utf-8", errors="replace"))
        if n:
            return {"available": True, "source": str(cand), "seconds": None,
                    "model_calls": n, "counted_by": how, "returncode": None,
                    "ok": None,
                    "note": "no glts_run.json — this run predates it. The "
                            "calls were recounted from the log with "
                            "glts_run._count_calls; the wall clock was "
                            "never recorded and is NOT guessed."}
    return {"available": False,
            "why": "no glts_run.json and no log to recount from"}


def _glts_box(o):
    """One GLTS object -> the common representation.

    THE CONVENTION, read off the data rather than assumed: `location` is
    [x, y] and is the CENTRE of the footprint, `size` is [dx, dy, dz], and
    where a z is given (15_object_orientation.json's `loc`) it is the
    UNDERSIDE — every floor-standing object in that file has z exactly 0,
    which a centre could not be."""
    loc = o.get("location") or o.get("loc") or []
    if len(loc) < 2:
        return None
    sz = o.get("size") or []
    if len(sz) < 3:
        return None
    x, y = float(loc[0]), float(loc[1])
    z = float(loc[2]) if len(loc) > 2 else 0.0
    dx, dy, dz = (abs(float(v)) for v in sz[:3])
    return [x - dx / 2, y - dy / 2, z, x + dx / 2, y + dy / 2, z + dz]


def _glts_walk(node, out):
    """GLTS writes its object lists in two shapes and both are in the wild:
    13's `areas[].object_list`, and 14's `areas[]` keyed by the furniture
    an object sits on, each holding `vis_furnitures_list` plus the `fur`
    itself. Rather than encode both, walk the JSON and collect every dict
    that has a name and a size — the definition of an object here."""
    if isinstance(node, dict):
        if node.get("name") and node.get("size") and (
                node.get("location") or node.get("loc")):
            out.append(node)
            return
        for v in node.values():
            _glts_walk(v, out)
    elif isinstance(node, list):
        for v in node:
            _glts_walk(v, out)


def load_glts(scene, root_override=None):
    root, d0 = glts_dirs(scene, root_override)
    out = {"available": False, "root": str(root), "dir": str(d0)}
    if not d0.exists():
        out["why"] = (f"GLTS has not been run for this scene: nothing at "
                      f"{d0}")
        out["cost"] = glts_cost(root)
        return out

    def _load(name):
        p = d0 / name
        if not p.exists():
            return None
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except ValueError:
            return None

    size = _load("1_room_size.json") or {}
    fur = _load("13_furniture_layout.json")
    small = _load("14_small_object_layout.json")
    orient = _load("15_object_orientation.json")

    # THE INVENTED ROOM IS NOT ONE DECISION — IT IS REVISED MID-SEARCH.
    # Verified on the completed bedroom run: files 1..3 carry
    # room_dimension [4.2, 3.5, 3.0] and files 4..13 carry [6.0, 3.5, 3.0].
    # It grows at step 4 and then stays. So the step-1 guess is NOT the
    # room the objects were laid out in, and scoring against it would
    # report GLTS as guessing a room it never used. Take the LAST word:
    # 13_furniture_layout.json, or the highest-numbered file carrying the
    # key. The whole history is kept, because "the room size is revised
    # during the search" is itself a finding about how GLTS works.
    history = []
    for p in sorted(d0.glob("*.json")):
        m = re.match(r"(\d+)_", p.name)
        if not m:
            continue
        try:
            v = json.loads(p.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if isinstance(v, dict) and v.get("room_dimension"):
            history.append({"step": int(m.group(1)), "file": p.name,
                            "room_dimension": v["room_dimension"]})
    history.sort(key=lambda r: r["step"])
    if fur and fur.get("room_dimension"):
        dim, dim_src = fur["room_dimension"], "13_furniture_layout.json"
    elif history:
        dim, dim_src = history[-1]["room_dimension"], history[-1]["file"]
    else:
        dim, dim_src = size.get("room_dimension"), (
            "1_room_size.json" if size.get("room_dimension") else None)
    revised = [h for h in history
               if list(map(float, h["room_dimension"])) != list(map(float, dim or []))]

    # 15 is the placement that actually goes to Blender and it is the only
    # file carrying a height for every object, so it is preferred when it
    # exists; 13 + 14 are the fallback for a run stopped at the layout.
    raw, src = [], ""
    if orient:
        for name, v in orient.items():
            if isinstance(v, dict) and v.get("size"):
                raw.append(dict(v, name=name))
        src = "15_object_orientation.json"
    if not raw:
        for f in (fur, small):
            if f:
                _glts_walk(f, raw)
        src = "13_furniture_layout.json + 14_small_object_layout.json"

    objs, dropped = [], []
    seen = set()
    for o in raw:
        nm = str(o.get("name") or "").strip()
        if nm.lower() in GLTS_NON_OBJECTS:
            dropped.append(nm)             # architecture, not furniture
            continue
        box = _glts_box(o)
        if box is None or nm.lower() in seen:
            continue
        seen.add(nm.lower())
        objs.append({"id": nm, "name": nm, "box": box,
                     "description": o.get("description")})

    # WHAT GLTS MEANT TO PLACE, versus what it actually placed.
    #
    # Step 11 retrieves an asset for every object the plan calls for; the
    # search then places a subset, and only what reaches
    # 15_object_orientation.json is in the scene. On the bedroom that gap
    # is large: 24 objects retrieved, 7 placed. Reporting only the 7
    # would make GLTS look like it planned a sparse room, when in fact it
    # planned a full one and lost most of it — a different failure, and
    # the more interesting one. Reported, never scored: dropping an
    # object may be the search correctly refusing to fit it.
    retrieved = _load("11_retrieved_results.json")
    n_retrieved, retrieved_names = None, []
    if isinstance(retrieved, dict) and isinstance(retrieved.get("objects"), list):
        for entry in retrieved["objects"]:
            if isinstance(entry, dict):
                retrieved_names.extend(str(k) for k in entry)
        n_retrieved = len(retrieved_names)

    # FURNITURE AND SMALL OBJECTS ARE PLACED BY DIFFERENT STEPS, so they
    # must not be counted against each other. GLTS names a small object
    # for its parent — "coffee table_ceramic vase" is the vase ON the
    # coffee table — and those are placed at step 14, not 13. A run
    # stopped at 13 has therefore not lost them; it has not reached them.
    # Counting all 28 retrieved names against 5 placed would manufacture
    # a 23-object failure out of a 8-object one, which is the kind of
    # inflated number this whole report exists to avoid.
    def _is_small(n):
        return "_" in n
    placed = {o["name"].lower() for o in objs}
    furn_retrieved = [n for n in retrieved_names if not _is_small(n)]
    small_retrieved = [n for n in retrieved_names if _is_small(n)]
    lost = [n for n in furn_retrieved
            if n.lower() not in placed
            and n.lower() not in GLTS_NON_OBJECTS]
    reached_small = bool(small and _load("14_small_object_layout.json"))

    out.update({
        "available": bool(objs) or dim is not None,
        "objects": objs, "object_source": src,
        "retrieved_count": n_retrieved,
        "retrieved_names": retrieved_names,
        "retrieved_furniture": furn_retrieved,
        "retrieved_small_objects": small_retrieved,
        "small_object_step_reached": reached_small,
        "retrieved_but_not_placed": lost,
        "dropped_as_architecture": dropped,
        "room_dimension": dim,
        "room_dimension_source": dim_src,
        "room_dimension_history": history,
        "room_dimension_was_revised": bool(revised),
        "room_dimension_note":
            "The room GLTS laid the objects out in, taken from "
            f"{dim_src}. GLTS REVISES its own room during the search — "
            f"{len(history)} of its files carry a room_dimension and "
            + ("they do not all agree, so the first guess is not what the "
               "objects were placed in. The history is in "
               "room_dimension_history."
               if revised else "they all agree."),
        "files_present": sorted(p.name for p in d0.glob("*.json")),
        "cost": glts_cost(root),
    })
    if not out["available"]:
        out["why"] = f"{d0} exists but holds no readable layout"
    return out


# ===================== the axes =======================================

def axis_cost(ours, glts):
    return {"label": "COMPARABLE",
            "ours": ours, "glts": glts,
            "caveat": "Cost is cost PER METHOD RUN, not cost for the same "
                      "product. Ours reconstructs a room that exists — it "
                      "spends its time on detection, lifting, voting and "
                      "judging a capture. GLTS generates a room that does "
                      "not — it spends its time on model calls and tree "
                      "search. The two totals are directly comparable as "
                      "numbers and are NOT comparable as value for money."}


#: Words a prompt uses that NOTHING can be placed for — qualities, moods,
#: materials-as-adjectives, parts of the room's description rather than
#: things in it. Kept explicit and printed in the report so the choice can
#: be argued with; a matcher nobody can inspect is not a measurement.
#: Grown from the two Marble prompts in use; extend it when a new prompt
#: introduces a new abstraction, never to make a number look better.
ABSTRACT_NOUNS = {
    # feelings and qualities
    "sense", "elegance", "comfort", "warmth", "focus", "atmosphere",
    "tone", "style", "mood", "feel", "look", "charm", "character",
    # visual properties, not objects
    "texture", "finish", "colour", "color", "color palette",
    "colour palette", "palette", "line", "shape", "pattern", "detail",
    "accent", "metal accent", "illumination", "lighting", "light",
    "brightness", "shade", "tint",
    # abstractions and collectives that name no single thing
    "object", "item", "thing", "piece", "collection", "assortment",
    "arrangement", "seating", "storage", "space", "area", "room",
    "scene", "side", "corner", "center", "centre", "foreground",
    "background", "surface", "floor plan", "layout",
    # things outside the room, or the room's own fabric
    "view", "garden", "greenery", "outdoors", "environment", "sunlight",
    "daylight", "wall", "floor", "ceiling",
    # descriptors that arrive as nouns
    "minimalist", "realistic", "modern", "contemporary",
}


def _is_abstract(noun):
    """Is this prompt noun something nothing could be placed for?

    Matches the whole phrase or its head word, so "metal accent" and
    "accent" both go, and "color palette" goes even though "palette"
    alone might be a real object elsewhere."""
    n = noun.strip().lower()
    if n in ABSTRACT_NOUNS:
        return True
    head = n.split()[-1] if n.split() else n
    return head in ABSTRACT_NOUNS


def axis_prompt_fidelity(prompt_text, ours, glts):
    """Which of the prompt's nouns each method's output names, and what
    each method names that the prompt never mentioned."""
    raw_nouns = vocab.extract_vocab(prompt_text, staples=False)

    # A PROMPT NOUN IS ONLY A FAIR TEST IF SOMETHING COULD BE PLACED FOR
    # IT. vocab_from_prompt builds a DETECTION vocabulary, where a word
    # too many costs nothing, so it happily returns "sense", "elegance",
    # "comfort", "warmth", "texture", "illumination". Neither method can
    # put an elegance in a room. Leaving them in the denominator made the
    # living room read "23 prompt nouns, ours named 6" when ours had in
    # fact named SIX OF THE SIX placeable things the prompt asked for.
    # That is not a small distortion, it is the whole number.
    #
    # The filter is a published stop-list rather than a cleverer parser,
    # because a rule a reader can audit beats one they must trust. Both
    # the kept and the dropped lists go into the report.
    nouns = [n for n in raw_nouns if not _is_abstract(n)]
    dropped = [n for n in raw_nouns if _is_abstract(n)]
    res = {"label": "COMPARABLE",
           "prompt_nouns": nouns, "n_prompt_nouns": len(nouns),
           "prompt_nouns_all": raw_nouns,
           "prompt_nouns_dropped_as_abstract": dropped,
           "noun_source": "vocab_from_prompt.extract_vocab(text, "
                          "staples=False) — the repo's own extractor. The "
                          "staples (door, window, pillow, curtain, ceiling "
                          "light) are switched OFF on purpose: they are "
                          "words the detector vocabulary adds to cover "
                          "what a prompt forgot to say, and crediting or "
                          "penalising a method on a word the prompt never "
                          "used would not be prompt fidelity.",
           "match_rule": MATCH_RULE_TEXT,
           "trap": TRAP,
           "methods": {}}
    for key, side in (("ours", ours), ("glts", glts)):
        if not side.get("available"):
            res["methods"][key] = {"available": False,
                                   "why": side.get("why", "not available")}
            continue
        names = [o["name"] for o in side["objects"]]
        matched, missed = [], []
        for n in nouns:
            hits = sorted({m for m in names if names_match(n, m)})
            (matched if hits else missed).append(
                {"noun": n, "named": hits} if hits else n)
        extra = sorted({m for m in names
                        if not any(names_match(n, m) for n in nouns)})
        res["methods"][key] = {
            "available": True, "n_objects": len(names),
            "matched": matched, "n_matched": len(matched),
            "missed": missed, "n_missed": len(missed),
            "extra": extra, "n_extra": len(extra)}
    return res


def axis_physical(ours, glts):
    res = {"label": "COMPARABLE",
           "rules": {
               "interpenetration": f"a pair counts when the two boxes share "
                                   f"more than {OVERLAP_MIN_M3} m3, so "
                                   f"touching faces and millimetre rounding "
                                   f"do not count.",
               "containment": f"a pair is IGNORED when the smaller box is "
                              f"at least {int(CONTAINMENT_FRAC * 100)}% "
                              f"inside the larger one — a book in a "
                              f"bookshelf is not a collision.",
               "outside_room": f"a box is outside when it passes a wall, "
                               f"the floor or the ceiling by more than "
                               f"{OUTSIDE_TOL_M} m.",
               "floating": f"the underside is more than "
                           f"{FLOAT_CLEARANCE_M} m above the floor and no "
                           f"other box both starts below it and reaches to "
                           f"within {FLOAT_CLEARANCE_M} m of it while "
                           f"covering at least "
                           f"{int(SUPPORT_FOOTPRINT_FRAC * 100)}% of its "
                           f"footprint. A picture, a wall-mounted air "
                           f"conditioner and a ceiling light are all "
                           f"correctly floating, so on a RECONSTRUCTION "
                           f"this is a description of the room, not an "
                           f"error count. TWO MORE REASONS OUR SIDE FLOATS "
                           f"AND GLTS DOES NOT, both structural rather "
                           f"than defects: (1) GLTS PLACES objects ON a "
                           f"floor it invented, so a floor-standing object "
                           f"cannot float by construction — a zero here is "
                           f"the method's premise, not an achievement; "
                           f"(2) ours is measured at the `grouped` layer, "
                           f"BEFORE compose/snap re-seats anything, and "
                           f"the room-shell epsilon (SHELL_EPS, 0.05 m) "
                           f"deliberately lifts the floor plane — so a "
                           f"sofa reported at 0.10-0.14 m is the known "
                           f"pre-snap state of the chain, not a "
                           f"reconstruction that lost the floor. Read the "
                           f"heights: centimetres are the epsilon, metres "
                           f"are a ceiling light.",
           },
           "methods": {}}
    if ours.get("available") and (ours.get("room") or {}).get("available"):
        room = ours["room"]
        res["methods"]["ours"] = dict(
            physical_validity(ours["objects"], room["room_box"],
                              room["floor_up_m"]),
            room_box_note="the room box is the bounding box of the measured "
                          "shell; for a non-rectangular room that is "
                          "generous, so 'outside' is a floor for our side, "
                          "never a ceiling. " + room["footprint_source"])
    else:
        res["methods"]["ours"] = {
            "available": False,
            "why": ours.get("why") or (ours.get("room") or {}).get(
                "why", "no measured room to check against")}
    if glts.get("available") and glts.get("room_dimension"):
        d = [float(v) for v in glts["room_dimension"]]
        res["methods"]["glts"] = dict(
            physical_validity(glts["objects"], [0, 0, 0, d[0], d[1], d[2]], 0.0),
            room_box_note=f"GLTS's own invented room, "
                          f"{d[0]}x{d[1]}x{d[2]} m, from "
                          f"{glts.get('room_dimension_source')} — the room "
                          f"the objects were actually laid out in, not the "
                          f"step-1 guess. "
                          + str(glts.get("room_dimension_note", "")))
        # The earlier, superseded guesses are scored too, so that "GLTS
        # revised its room" is a number and not just a remark.
        for h in glts.get("room_dimension_history") or []:
            a = [float(v) for v in h["room_dimension"]]
            if a == d:
                continue
            res["methods"]["glts"].setdefault("superseded_room_dimensions", [])
            res["methods"]["glts"]["superseded_room_dimensions"].append({
                "file": h["file"], "room_dimension": a,
                "outside_against_it": outside_room(
                    glts["objects"], [0, 0, 0, a[0], a[1], a[2]])["count"]})
    else:
        res["methods"]["glts"] = {
            "available": False,
            "why": glts.get("why", "GLTS has not been run for this scene")}
    return res


def axis_grounding(ours, glts):
    """FIDELITY TO THE REAL ROOM. Only ours can be scored here, because
    only ours saw the room. GLTS never claimed to do this."""
    res = {"label": "ASYMMETRIC",
           "what_it_measures":
               "How close the layout is to the room that actually exists. "
               "Only our method can be scored on it, because only our "
               "method was shown the room: GLTS was given a paragraph and "
               "invented a room to fit it, which is what it is for. A bad "
               "number here is not GLTS failing at its own task — it is "
               "the measure of what a paragraph cannot tell you.",
           "real_room": ours.get("room") if ours.get("available") else
           {"available": False, "why": ours.get("why", "ours not available")},
           "ours_object_count": len(ours.get("objects") or [])
           if ours.get("available") else None,
           "ours_layer": ours.get("layer"),
           "glts_object_count": len(glts.get("objects") or [])
           if glts.get("available") else None,
           "glts_room_dimension": glts.get("room_dimension"),
           "glts_room_dimension_source": glts.get("room_dimension_source"),
           "glts_room_dimension_history": glts.get("room_dimension_history"),
           "glts_room_dimension_note": glts.get("room_dimension_note")}
    room = res["real_room"]
    d = glts.get("room_dimension")
    if room.get("available") and d:
        d = [float(v) for v in d]
        area = d[0] * d[1]
        rl = room["footprint_area_m2"]
        bb = room["footprint_bbox_size_m"]
        # The guess is a rectangle, so it is compared against BOTH the
        # measured floor area and the measured bounding rectangle. They
        # differ for any room that is not a box, and hiding that behind
        # one percentage would be a choice pretending to be a fact.
        res["room_error"] = {
            "glts_footprint_m": [d[0], d[1]],
            "glts_footprint_area_m2": round(area, 2),
            "real_footprint_area_m2": rl,
            "area_error_m2": round(area - rl, 2),
            "area_error_pct": round(100.0 * (area - rl) / rl, 1) if rl else None,
            "real_bbox_size_m": bb,
            "bbox_side_errors_m": [round(min(d[0], d[1]) - min(bb), 2),
                                   round(max(d[0], d[1]) - max(bb), 2)],
            "bbox_side_note": "sides are compared shortest-to-shortest and "
                              "longest-to-longest, because GLTS's room has "
                              "no orientation to line up with ours.",
            "glts_height_m": d[2], "real_height_m": room["height_m"],
            "height_error_m": round(d[2] - room["height_m"], 3),
            "real_footprint_source": room["footprint_source"]}
    if res["ours_object_count"] is not None and res["glts_object_count"] is not None:
        res["object_count_error"] = (res["glts_object_count"]
                                     - res["ours_object_count"])
    return res


TRAP = (
    "GLTS optimises DIRECTLY for the prompt text — the paragraph is its "
    "whole world, so naming what the paragraph names IS its task. Our "
    "method reconstructs what is actually in the room. Where the prompt "
    "says 'sheer white curtains' and the real room has none, ours "
    "correctly omits them and scores WORSE here. A LOWER PROMPT-FIDELITY "
    "NUMBER FOR OURS IS THEREFORE NOT NECESSARILY WORSE PERFORMANCE — it "
    "may be the method working. Read the lists, not the counts.")

HONESTY = (
    "This is not a fair fight and nothing here should be read as one. "
    "GLTS is given a paragraph and nothing else; ours is given a capture "
    "of the room that paragraph describes. GLTS INVENTS a room size; ours "
    "MEASURES one. So there is no combined score and no winner on this "
    "page, on purpose: no single number means the same thing on both "
    "sides. Each axis stands alone and says whether it is COMPARABLE "
    "(both measured the same way on the same input) or ASYMMETRIC (only "
    "one method can be scored on it, and why).")


def compare_scene(scene, glts_root=None):
    rec = {"scene": scene}
    try:
        prompt_file = vocab.bundle_prompt_file(scene)
        prompt_text = prompt_file.read_text(encoding="utf-8")
        rec["prompt_file"] = str(prompt_file)
        rec["prompt"] = " ".join(prompt_text.split())
    except (FileNotFoundError, OSError) as e:
        prompt_text = ""
        rec["prompt_file"] = None
        rec["prompt_error"] = str(e)
    ours = load_ours(scene)
    glts = load_glts(scene, glts_root)
    rec["shared_input"] = ("the Marble prompt this scene was generated "
                           "from — the one input both methods were given")
    # WHICH FOLDER EACH SIDE CAME FROM, always, so nobody has to guess.
    # Our side is often run on a CLONE of a scene (autotest_bedroom is a
    # copy of bedroom_marble) while GLTS ran under the original name, and
    # the two only belong on the same page because they were given the
    # same prompt. Printing both paths is what lets a reader check that.
    rec["provenance"] = {
        "ours_scene_folder": str(paths.scene_dir(scene)),
        "ours_graph": ours.get("graph"),
        "ours_layer": ours.get("layer"),
        "glts_output_folder": glts.get("dir"),
        "glts_root_was_overridden": bool(glts_root),
        "note": "Our side and the GLTS side are paired by PROMPT, not by "
                "folder name — a scene may have been run on a clone. Use "
                "--glts-root to pair them explicitly."}
    rec["ours_meta"] = {k: v for k, v in ours.items() if k != "objects"}
    rec["glts_meta"] = {k: v for k, v in glts.items() if k != "objects"}
    rec["A_cost"] = axis_cost(ours_cost(scene), glts.get("cost") or
                              {"available": False,
                               "why": "GLTS has not been run for this scene"})
    rec["B_prompt_fidelity"] = (
        axis_prompt_fidelity(prompt_text, ours, glts) if prompt_text
        else {"label": "COMPARABLE", "unavailable": True,
              "why": rec.get("prompt_error", "no prompt for this scene")})
    rec["C_physical_validity"] = axis_physical(ours, glts)
    rec["D_grounding"] = axis_grounding(ours, glts)
    return rec


# ===================== reports ========================================

def e(x):
    return _html.escape(str(x))


def _rows(pairs):
    return "".join(f"<tr><th>{e(k)}</th><td>{e(v)}</td></tr>"
                   for k, v in pairs)


def _missing(why):
    return f'<p class="missing">NOT AVAILABLE — {e(why)}</p>'


def _num(v, unit="", nd=1):
    if v is None:
        return "not recorded"
    if isinstance(v, float):
        return f"{v:.{nd}f}{unit}"
    return f"{v}{unit}"


def _phys_table(name, m):
    if not m.get("interpenetration"):
        return f"<h4>{e(name)}</h4>" + _missing(m.get("why", "no result"))
    ip, orm, fl = m["interpenetration"], m["outside_room"], m["floating"]
    h = [f"<h4>{e(name)}</h4>",
         f'<p class="note">{e(m.get("room_box_note", ""))}</p>',
         "<table>",
         _rows([("objects scored", m["n_objects"]),
                ("interpenetrating pairs", ip["pairs"]),
                ("overlapping volume (m3)", ip["volume_m3"]),
                ("pairs ignored as containment", ip["ignored_containment_pairs"]),
                ("objects outside the room", orm["count"]),
                ("worst excursion (m)", orm["worst_m"]),
                ("floating objects", fl["count"])]),
         "</table>"]
    if ip["worst"]:
        h.append("<p>worst overlaps:</p><table><tr><th>a</th><th>b</th>"
                 "<th>m3</th><th>overlap x,y,up (m)</th></tr>")
        for p in ip["worst"]:
            h.append(f"<tr><td>{e(p['a'])}</td><td>{e(p['b'])}</td>"
                     f"<td>{p['volume_m3']}</td>"
                     f"<td>{e(p['overlap_xyz_m'])}</td></tr>")
        h.append("</table>")
    if orm["objects"]:
        h.append("<p>outside the room: " + ", ".join(
            f"{e(o['name'])} ({e(', '.join(o['how']))})"
            for o in orm["objects"]) + "</p>")
    if fl["objects"]:
        h.append("<p>floating: " + ", ".join(
            f"{e(o['name'])} ({o['underside_m']} m up)"
            for o in fl["objects"]) + "</p>")
    return "".join(h)


def scene_html(rec):
    h = [f"<h2>{e(rec['scene'])}</h2>"]
    h.append(f'<p class="note">Shared input: {e(rec["shared_input"])}'
             + (f' — <code>{e(rec["prompt_file"])}</code>'
                if rec.get("prompt_file") else "") + "</p>")
    if rec.get("prompt"):
        h.append(f'<details><summary>the prompt both methods were given'
                 f'</summary><p>{e(rec["prompt"])}</p></details>')
    om, gm, pv = rec["ours_meta"], rec["glts_meta"], rec["provenance"]
    h.append("<table>" + _rows([
        ("ours: scene folder", pv["ours_scene_folder"]),
        ("ours: graph layer scored",
         f'{om.get("layer")} (the chain ends on '
         f'{om.get("chain_expected_final")})' if om.get("available")
         else "NOT AVAILABLE — " + str(om.get("why"))),
        ("glts: output folder", pv["glts_output_folder"]),
        ("glts: layout read from",
         gm.get("object_source") if gm.get("available")
         else "NOT AVAILABLE — " + str(gm.get("why"))),
        ("how the two are paired", pv["note"]),
    ]) + "</table>")

    # ---- A
    a = rec["A_cost"]
    h.append(f'<h3>A. Cost <span class="tag">{a["label"]}</span></h3>')
    h.append(f'<p class="note">{e(a["caveat"])}</p>')
    o, g = a["ours"], a["glts"]
    h.append("<table><tr><th></th><th>ours</th><th>GLTS</th></tr>")
    h.append(f"<tr><th>wall clock (s)</th>"
             f"<td>{_num(o.get('seconds')) if o.get('available') else 'not recorded'}</td>"
             f"<td>{_num(g.get('seconds')) if g.get('available') else 'not recorded'}</td></tr>")
    h.append(f"<tr><th>model cost</th>"
             f"<td>{e(str(o.get('n_llm_stages')) + ' LLM stages: ' + ', '.join(o.get('llm_stages') or [])) if o.get('available') else 'not recorded'}</td>"
             f"<td>{e(str(g.get('model_calls')) + ' model calls') if g.get('available') else 'not recorded'}</td></tr>")
    if not o.get("available"):
        h.append(f'<tr><th>ours</th><td colspan="2" class="missing">'
                 f'{e(o.get("why", ""))}</td></tr>')
    else:
        h.append(f"<tr><th>which stages ran</th><td colspan=\"2\">"
                 f"{e(', '.join(o.get('stages_run') or []))} — "
                 f"<b>{e(o.get('seconds_covers'))}</b>"
                 + (f", and the vote alone was {o['vote_seconds']} s "
                    f"({o['vote_share_pct']}% of it)"
                    if o.get("vote_seconds") else "")
                 + f" ({e(o.get('file'))})</td></tr>")
        h.append(f'<tr><th>read this number carefully</th>'
                 f'<td colspan="2">{e(o.get("note", ""))}</td></tr>')
    if not g.get("available"):
        h.append(f'<tr><th>GLTS</th><td colspan="2" class="missing">'
                 f'{e(g.get("why", ""))}</td></tr>')
    elif g.get("note"):
        h.append(f'<tr><th>GLTS note</th><td colspan="2">{e(g["note"])}</td></tr>')
    h.append("</table>")

    # ---- B
    b = rec["B_prompt_fidelity"]
    h.append(f'<h3>B. Prompt fidelity <span class="tag">{b["label"]}</span></h3>')
    if b.get("unavailable"):
        h.append(_missing(b.get("why", "")))
    else:
        h.append(f'<p class="trap">{e(b["trap"])}</p>')
        h.append(f'<p class="note">Prompt nouns: {e(b["noun_source"])}</p>')
        h.append(f'<p class="note">Matching rule: {e(b["match_rule"])}</p>')
        h.append(f'<p>{b["n_prompt_nouns"]} nouns in the prompt: '
                 f'{e(", ".join(b["prompt_nouns"]))}</p>')
        h.append("<table><tr><th></th><th>ours</th><th>GLTS</th></tr>")
        mm = b["methods"]
        for label, key in (("objects in output", "n_objects"),
                           ("prompt nouns named", "n_matched"),
                           ("prompt nouns missed", "n_missed"),
                           ("objects not in the prompt", "n_extra")):
            cells = []
            for side in ("ours", "glts"):
                m = mm.get(side, {})
                cells.append(str(m.get(key)) if m.get("available")
                             else "n/a")
            h.append(f"<tr><th>{label}</th><td>{cells[0]}</td>"
                     f"<td>{cells[1]}</td></tr>")
        h.append("</table>")
        for side, title in (("ours", "ours"), ("glts", "GLTS")):
            m = mm.get(side, {})
            h.append(f"<h4>{title}</h4>")
            if not m.get("available"):
                h.append(_missing(m.get("why", "")))
                continue
            h.append("<p><b>named</b>: " + (", ".join(
                f"{e(x['noun'])} &rarr; {e(', '.join(x['named']))}"
                for x in m["matched"]) or "none") + "</p>")
            h.append("<p><b>missed</b>: " + (", ".join(
                e(x) for x in m["missed"]) or "none") + "</p>")
            h.append("<p><b>in the output but not in the prompt</b>: "
                     + (", ".join(e(x) for x in m["extra"]) or "none") + "</p>")

    # ---- C
    c = rec["C_physical_validity"]
    h.append(f'<h3>C. Physical validity <span class="tag">{c["label"]}</span></h3>')
    h.append("<table>" + _rows(list(c["rules"].items())) + "</table>")
    h.append(_phys_table("ours", c["methods"]["ours"]))
    h.append(_phys_table("GLTS", c["methods"]["glts"]))
    sup = (c["methods"]["glts"] or {}).get("superseded_room_dimensions")
    if sup:
        h.append('<p class="note">GLTS revised its own room during the '
                 'search, so these earlier sizes are superseded. Scored '
                 'against them the counts would be: ' + "; ".join(
                     f"{e(s['file'])} {e(s['room_dimension'])} &rarr; "
                     f"{s['outside_against_it']} outside" for s in sup)
                 + ".</p>")

    # ---- D
    d = rec["D_grounding"]
    h.append(f'<h3>D. Grounding in the real room '
             f'<span class="tag">{d["label"]}</span></h3>')
    h.append(f'<p class="trap">{e(d["what_it_measures"])}</p>')
    rr = d["real_room"]
    if not rr.get("available"):
        h.append(_missing(rr.get("why", "")))
    else:
        h.append("<table><tr><th></th><th>real room (measured)</th>"
                 "<th>GLTS (invented)</th><th>error</th></tr>")
        err = d.get("room_error")
        gd = d.get("glts_room_dimension")
        h.append(f"<tr><th>footprint area (m2)</th><td>{rr['footprint_area_m2']}</td>"
                 f"<td>{err['glts_footprint_area_m2'] if err else 'n/a'}</td>"
                 f"<td>{(str(err['area_error_m2']) + ' (' + str(err['area_error_pct']) + '%)') if err else 'n/a'}</td></tr>")
        h.append(f"<tr><th>footprint sides (m)</th>"
                 f"<td>{e(rr['footprint_bbox_size_m'])}</td>"
                 f"<td>{e(err['glts_footprint_m']) if err else 'n/a'}</td>"
                 f"<td>{e(err['bbox_side_errors_m']) if err else 'n/a'}</td></tr>")
        h.append(f"<tr><th>height (m)</th><td>{rr['height_m']}</td>"
                 f"<td>{err['glts_height_m'] if err else 'n/a'}</td>"
                 f"<td>{err['height_error_m'] if err else 'n/a'}</td></tr>")
        h.append(f"<tr><th>objects</th><td>{d['ours_object_count']} "
                 f"(our <code>{e(d['ours_layer'])}</code> layer)</td>"
                 f"<td>{d['glts_object_count'] if d['glts_object_count'] is not None else 'n/a'}</td>"
                 f"<td>{d.get('object_count_error', 'n/a')}</td></tr>")
        h.append("</table>")
        h.append(f'<p class="note">Real footprint from: '
                 f'{e(rr["footprint_source"])}. {e(err["bbox_side_note"]) if err else ""}</p>')
        # WHAT GLTS MEANT TO PLACE vs WHAT IT PLACED. Without this the
        # object-count row reads as "GLTS planned a sparse room", which is
        # the wrong conclusion: it planned a full one and its own search
        # dropped most of it. Reported, never scored — a dropped object
        # may be the search correctly refusing to fit something.
        gm = rec.get("glts_meta") or {}
        if gm.get("retrieved_count"):
            lost = gm.get("retrieved_but_not_placed") or []
            nf = len(gm.get("retrieved_furniture") or [])
            ns = len(gm.get("retrieved_small_objects") or [])
            small_note = (
                "" if gm.get("small_object_step_reached") else
                f" The other {ns} retrieved name(s) are SMALL OBJECTS "
                f"(named for their parent, e.g. "
                f"<code>coffee table_ceramic vase</code>), which step 14 "
                f"places; this run stopped before it, so they are not "
                f"counted as lost — it never reached them.")
            h.append(f'<p class="note"><b>GLTS intent vs result:</b> of '
                     f'{nf} FURNITURE items retrieved at step 11, '
                     f'{d["glts_object_count"]} survived into the final '
                     f'placement — {len(lost)} were lost during the search. '
                     f'This is why its prompt fidelity above is low: not '
                     f'that it never planned them, but that they did not '
                     f'survive. Lost: '
                     f'{e(", ".join(lost)) if lost else "none"}.{small_note}'
                     f'</p>')
    return "".join(h)


def build_html(records, runid):
    css = """
body{background:#fff;color:#111;font:15px/1.5 Georgia,'Times New Roman',serif;
 margin:0 auto;padding:2em 1.2em;max-width:56em}
h1,h2,h3,h4{font-family:Arial,Helvetica,sans-serif;line-height:1.25}
h1{font-size:1.5em} h2{font-size:1.3em;border-top:2px solid #111;padding-top:.6em;margin-top:2em}
h3{font-size:1.1em;margin-top:1.6em} h4{font-size:1em;margin:1.2em 0 .3em}
table{border-collapse:collapse;margin:.6em 0;width:100%;font-size:.93em}
th,td{border:1px solid #999;padding:.3em .5em;text-align:left;vertical-align:top}
th{background:#eee;font-family:Arial,Helvetica,sans-serif;font-weight:bold}
code{font-family:Consolas,monospace;font-size:.9em}
.tag{font-family:Arial,Helvetica,sans-serif;font-size:.62em;border:1px solid #111;
 padding:.1em .45em;vertical-align:middle;letter-spacing:.06em}
.note{font-size:.9em;color:#333}
.trap{border-left:4px solid #111;padding:.5em .8em;background:#f2f2f2}
.missing{background:#f2f2f2;padding:.3em .5em}
details{margin:.5em 0}
"""
    h = [f"<title>method comparison {e(runid)}</title>",
         f"<style>{css}</style>",
         "<h1>Our reconstruction vs GL-TreeSearch, axis by axis</h1>",
         f'<p class="note">run {e(runid)} &middot; '
         f'{e(datetime.now(timezone.utc).isoformat(timespec="seconds"))}</p>',
         f'<p class="trap">{e(HONESTY)}</p>',
         f'<p class="trap">{e(TRAP)}</p>']
    h += [scene_html(r) for r in records]
    return "\n".join(h)


def console(rec):
    s = rec["scene"]
    om, gm = rec["ours_meta"], rec["glts_meta"]
    print(f"\n=== {s} " + "=" * max(0, 56 - len(s)))
    print(f"  ours: {om.get('layer') or 'NOT AVAILABLE'}"
          f"{'' if om.get('available') else ' - ' + str(om.get('why'))}"
          f"   glts: {gm.get('object_source') if gm.get('available') else 'NOT RUN - ' + str(gm.get('why'))}")
    a = rec["A_cost"]
    o, g = a["ours"], a["glts"]
    print(f"  A cost      [COMPARABLE]  ours "
          f"{_num(o.get('seconds'), 's') if o.get('available') else 'not recorded'}"
          f", {o.get('n_llm_stages', '?')} LLM stages"
          f"   |  glts "
          f"{_num(g.get('seconds'), 's') if g.get('available') else 'not recorded'}"
          f", {g.get('model_calls') if g.get('available') else '?'} model calls")
    if o.get("available"):
        print(f"     ours covers {o.get('seconds_covers')}"
              + (f"; the vote alone is {o['vote_seconds']}s "
                 f"({o['vote_share_pct']}%)" if o.get("vote_seconds") else "")
              + "; neither side's number includes crop/seg/lift, which GLTS "
                "has no counterpart for")
    b = rec["B_prompt_fidelity"]
    if b.get("unavailable"):
        print(f"  B fidelity  [COMPARABLE]  not available - {b.get('why')}")
    else:
        line = f"  B fidelity  [COMPARABLE]  {b['n_prompt_nouns']} prompt nouns"
        for k, lbl in (("ours", "ours"), ("glts", "glts")):
            m = b["methods"].get(k, {})
            line += (f"  |  {lbl} {m['n_matched']} named / {m['n_missed']} "
                     f"missed / {m['n_extra']} extra" if m.get("available")
                     else f"  |  {lbl} n/a")
        print(line)
        print("     (a lower number for ours may be the method working - "
              "it reports the room, not the paragraph)")
    c = rec["C_physical_validity"]
    for k, lbl in (("ours", "ours"), ("glts", "glts")):
        m = c["methods"][k]
        if not m.get("interpenetration"):
            print(f"  C physics   [COMPARABLE]  {lbl}: not available - "
                  f"{m.get('why')}")
            continue
        print(f"  C physics   [COMPARABLE]  {lbl}: {m['n_objects']} objects, "
              f"{m['interpenetration']['pairs']} overlapping pairs "
              f"({m['interpenetration']['volume_m3']} m3), "
              f"{m['outside_room']['count']} outside, "
              f"{m['floating']['count']} floating")
    d = rec["D_grounding"]
    err = d.get("room_error")
    if err:
        print(f"  D grounding [ASYMMETRIC]  real "
              f"{err['real_footprint_area_m2']} m2 x {err['real_height_m']} m "
              f"vs GLTS's guess {err['glts_footprint_area_m2']} m2 x "
              f"{err['glts_height_m']} m "
              f"(area {err['area_error_pct']}%, height "
              f"{err['height_error_m']:+.2f} m)")
        if d.get("object_count_error") is not None:
            print(f"     objects: ours {d['ours_object_count']} in the real "
                  f"room, glts {d['glts_object_count']} invented "
                  f"({d.get('object_count_error'):+d})")
        # glts_meta is the GLTS block with the objects list stripped out,
        # so take the placed count from the grounding axis instead.
        g = rec.get("glts_meta") or {}
        if g.get("retrieved_count"):
            lost = g.get("retrieved_but_not_placed") or []
            nf = len(g.get("retrieved_furniture") or [])
            print(f"     glts intent vs result: {nf} furniture retrieved, "
                  f"{d['glts_object_count']} placed"
                  + (f" - {len(lost)} lost in the search "
                     f"({', '.join(lost[:6])}"
                     + (" ..." if len(lost) > 6 else "") + ")" if lost else ""))
    else:
        print(f"  D grounding [ASYMMETRIC]  not available - "
              f"{d['real_room'].get('why', 'no GLTS room to compare')}")


def main():
    ap = argparse.ArgumentParser(
        description=__doc__.splitlines()[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="No combined score is produced, on purpose: see the module "
               "docstring.")
    ap.add_argument("--scene", default="")
    ap.add_argument("--scenes", default="", help="comma-separated")
    ap.add_argument("--glts-root", default="",
                    help="where this scene's GLTS output lives (the run "
                         "root or its '0' folder). Default: "
                         "<treesearchgen>/output_ovm_<scene>, the same rule "
                         "glts_run.py uses. With several scenes, give "
                         "comma-separated scene=path pairs — our side is "
                         "often run on a clone of a scene while GLTS ran "
                         "under the original name, so the pairing has to be "
                         "sayable.")
    ap.add_argument("--out-dir", default="",
                    help="where the two report files go (default: the "
                         "shared out/ root)")
    a = ap.parse_args()

    scenes = [s.strip() for s in (a.scenes or a.scene).split(",") if s.strip()]
    if not scenes:
        raise SystemExit("give --scene or --scenes")
    # --glts-root is either one path (one scene) or scene=path pairs, so a
    # caller can pair a clone of ours with the GLTS run of the original.
    roots = {}
    if a.glts_root:
        if "=" in a.glts_root:
            for part in a.glts_root.split(","):
                if "=" not in part:
                    raise SystemExit(f"--glts-root: '{part}' is not "
                                     f"scene=path")
                k, v = part.split("=", 1)
                roots[k.strip()] = v.strip()
            unknown = set(roots) - set(scenes)
            if unknown:
                raise SystemExit(f"--glts-root names scenes that are not "
                                 f"being compared: {', '.join(sorted(unknown))}")
        elif len(scenes) > 1:
            raise SystemExit("--glts-root as a bare path names ONE run. "
                             "With several scenes give comma-separated "
                             "scene=path pairs instead.")
        else:
            roots[scenes[0]] = a.glts_root
    for s in scenes:
        if not paths.scene_dir(s).exists():
            raise SystemExit(f"[compare] no scene directory for {s}")

    runid = (datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    records = [compare_scene(s, roots.get(s)) for s in scenes]

    out_dir = Path(a.out_dir) if a.out_dir else paths.OUT
    out_dir.mkdir(parents=True, exist_ok=True)
    doc = {"runid": runid,
           "generated": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "honesty": HONESTY, "trap": TRAP,
           "glts_root_default": str(GLTS_WIN),
           "glts_root_override": roots or None,
           "scenes": records}
    jp = out_dir / f"comparison_{runid}.json"
    hp = out_dir / f"comparison_{runid}.html"
    paths.write_atomic(jp, json.dumps(doc, indent=1))
    paths.write_atomic(hp, build_html(records, runid))

    print("=" * 62)
    print("OUR RECONSTRUCTION vs GL-TREESEARCH — no combined score, "
          "no winner.")
    print("Each axis is labelled COMPARABLE or ASYMMETRIC and stands alone.")
    for r in records:
        console(r)
    print("\n" + "=" * 62)
    print(f"  {jp}")
    print(f"  {hp}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
