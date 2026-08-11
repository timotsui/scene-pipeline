"""
STEP 3 COMPOSE+LOOP, 3.1 SEMANTIC / S3 -- PROPOSE EDITS (adds + deletes).

Built 07-27 isolated ("test and review tomorrow"); INCORPORATED into the
lane 08-01 (user ruling) as S3, between S2 consistency and S4 screening.
Proposals land at S4 SCREENING -- the same door as the JUDGE's
add/delete/replace re-entry. Screening is not built yet, so the output
is review-only for now; R5 stays open (duplicat-tripwire rework first).

DELETE proposals -- deterministic aggregation of typed doubt signals,
then ONE batched LLM confirm/deny pass:
  - none_plausible objects (supported_by: obj_083 "greenery through a
    window")
  - objects whose EVERY support-type edge was DROPped and whose own
    support confidence is weak
v2 removals (R5 postmortem): the 'duplicat' word-match detector is GONE
(code never interprets prose -- it relabeled the consistency module's
"duplicate wall contact" as duplicate OBJECT and got two real books
deleted). The existence-disputed detector is GONE too: contract check
08-01 showed materialize_verdicts already REMOVES disputed nodes from
the resolved working set (resolved['removed'] carries them), so it
could only accuse objects that aren't in the inventory.

RAW EVIDENCE TO THE JUDGE (user design 08-01): the confirm/deny call
gets each candidate's consistency verdicts VERBATIM plus all dropped-
edge wordings scene-wide -- no labels, no code interpretation; the one
LLM that owns the stay/go decision reads the words itself. It is told
duplication is NOT a deletion reason; instead it reports
duplicate_suspicions -- pairs the wordings suggest are ONE physical
object recorded twice. Valid pairs are written as reopen_petitions:
referrals to the step-2 pair judge (SAME_CANDIDATE, the judge with
crops), and future hold-inputs for screening's non-visual dedup.
Review-only until those wires exist.

ADD/SWAP proposals -- v5 CANON LOOP (user design 08-02): per-item
forced replies (every object + arch node answers "nothing" or names
an expected-but-absent connection; one final "room" slot for
room-level gaps), looped -- each round FOLDS its proposals into the
working inventory and re-asks, stopping on a dry round or at
--max-rounds (default 6). User ruling replaced the 3-run union with
the loop: later rounds SEE earlier proposals, so it never duplicates
and self-paces; the round stamp is the salience evidence (round 1 =
near-certain misses, later rounds = deeper inferences). Item lines
carry measured in-scene sizes (SCENE units, ~0.8x real metric on
bedroom_marble), which scene-scales the replies' size_m and enables
the SWAP channel: re-interpret N listed items as M new ones (one big
blob <-> several fragments) in roughly the same space. Adds are
PRIORS, never observations -- nothing enters the scene state before
screening rules on it. Fully automatic: no cache, no human picks.

STEP 3, SIZE + BOX (v4/v5, RELATION ROUTER 08-02): S3 hands
screening a COMPLETE graph delta. Sizes normally ride in from the
loop; T_SIZE (scene-size reference frame) is the fallback for
sizeless adds. Placement is pure code, ROUTED BY THE REPLY'S
RELATION ("window on top of the curtain" postmortem -- the anchor id
prefix alone used to force stack-on-top): on_top -> anchor top-face
scan; inside -> anchor interior; mounted_on/hangs_from -> the
wall/ceiling the anchor is ATTACHED to via the support chain
(embedded slab centered behind the anchor, height-clamped into the
room); near -> beside the anchor on its own parent surface (wall-
mounted host: referent top, else nearest furniture top below, else
floor). Free-space scan against sibling footprints, nearest the
"where" referent, both orientations, shrink-to-fit FLAGGED
(clamped); unroutable combinations fail HONESTLY in placement. SWAP validation
is code, not model: the in-items are PACKED into the out-items'
combined envelope -- footprint arithmetic decides feasible /
infeasible (height left free: one tall item may replace several
short ones); out-objects are only marked, they leave the graph at
screening or never. Every proposal box carries
box_source="estimated_prior" so invented geometry can never
masquerade as measured.

Degrade: --no-llm (or call failure) -> delete candidates written with
status CANDIDATE (not confirmed), adds empty. Nothing fabricated.

Output: out/<scene>/compose/edit_proposals.json -- PROPOSALS ONLY.
Stage boundary (restructure 08-02): the loop's output is frozen to
edit_proposals_raw.json BEFORE step 3, so a sizing/placement crash or
rework never costs the model calls again. --size-only reloads that
file (fallback: strips a previous edit_proposals.json) and re-runs
step 3 alone. The raw file is regenerated on every full run -- a
stage contract file, never hand-edited state.

Run:
  python compose/propose_edits.py --scene bedroom_marble --no-llm  # aggregate only
  python compose/propose_edits.py --scene bedroom_marble
  python compose/propose_edits.py --scene bedroom_marble --size-only  # step 3 only
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
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402
from arch_walls import wall_axis_planes  # noqa: E402
# scene_state lives in the sibling graph/ package, not beside us, so its
# directory has to go on the path too (same two-step the other compose
# modules use, e.g. uniform_instances.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "graph"))
import scene_state  # noqa: E402

MODEL = "sonnet"
CALL_TIMEOUT_S = 480
PROMPT_VERSION = "6"
WEAK_TOP_CONF = 0.5      # top-option confidence below this = weak support

SUPPORT_EDGE_TYPES = ("ON", "IN", "IN_WALL", "ATTACHED")

T_DELETE = """\
{firm}You are auditing a 3D scene graph of ONE indoor room. Two tasks, \
one response.

TASK 1 -- DELETE candidates. Each numbered candidate below was flagged \
by earlier pipeline passes (support attribution / edge consistency). \
For each, decide: should this object be REMOVED from the scene model, \
or KEPT? Removal is right when the evidence says the detection is not \
a real standalone object (ghost, misread background). Keep when doubt \
is weak or the object is plausibly real despite a bad box. NOTE: "this \
may be a duplicate of another object" is NOT a deletion reason -- \
duplicates are resolved by merging elsewhere; report them in task 2 \
instead.

TASK 2 -- duplicate suspicions. Below the candidates: every dropped \
edge with the consistency judge's verbatim reason. If any wording \
suggests two detected OBJECTS may be the SAME physical thing (one \
object recorded twice), report the pair. Read carefully: "duplicate \
wall contact inherited from X" means a redundant FACT, not a duplicate \
object. Only report pairs the wording itself points at; do not infer \
from geometry alone. An empty list is the normal outcome.

Return ONE fenced ```json block, a single JSON OBJECT:
{{"verdicts": [EXACTLY one per candidate, same order: {{"id": "<the id \
given>", "verdict": "DELETE|KEEP", "confidence": 0.0-1.0, "reason": \
"one sentence"}}],
 "duplicate_suspicions": [zero or more: {{"pair": ["<obj id>", \
"<obj id>"], "confidence": 0.0-1.0, "evidence": "the giveaway \
wording, quoted"}}]}}
Output ONLY the fenced JSON block.

{items}

DROPPED-EDGE WORDINGS (scene-wide, verbatim):
{drops}"""

T_ADD = """\
{firm}You are reviewing ONE reconstructed indoor room. The \
reconstruction detects most large furniture reliably but misses items \
that are small, occluded, or low-contrast, and it sometimes MIS-GROUPS \
geometry (one object detected as several fragments, or several objects \
merged into one blob). Below: the room dimensions and every item with \
its measured in-scene size (width x depth x height, meters -- SCENE \
units, not exactly real-world metric) and its CONNECTIONS.

For EVERY item listed (architecture included), give THREE channels:

1. "implied" -- does THIS item's FUNCTION or PLACEMENT depend on \
something that is absent from the room? A holder needs a thing to \
hold, a covering needs a thing to cover, a control needs a thing it \
controls, a display needs an input. Answer this question for every \
item -- it is the most valuable channel. Each entry MUST include \
"evidence": the listed fact your inference rests on, quoted or \
closely paraphrased from the lines above.

2. "expected" -- anything OBVIOUSLY expected to be connected to THIS \
item by everyday convention, but absent? Never propose something that \
already exists elsewhere in the inventory, never decor filler. Be \
CONSERVATIVE: most items get an empty list.

3. "swaps" -- OPTIONAL and RARE: should THIS item (possibly together \
with other listed items) be RE-INTERPRETED as different object(s)? \
Use only when a listed name/size/grouping does not make physical \
sense: one big blob that is really several distinct objects, or \
several fragments that are really one object. A swap REPLACES the \
"out" items with the "in" items in roughly the same space: do the \
arithmetic from the listed sizes -- the in items must plausibly \
occupy the out items' combined footprint. Never use a swap to merely \
rename a single item to a similar thing.

HARD STAGE RULE -- bulky free-standing furniture is SWAP-ONLY. Ask: \
could the reconstruction plausibly have MISSED this thing at this \
spot? Something that claims a big patch of OPEN floor (wardrobe / \
dresser / armchair scale) cannot have been invisible -- that empty \
floor was observed. So such items may NOT appear in "implied" or \
"expected": either they truly are not there (propose nothing) or a \
detected item IS them, mis-read (propose a swap). Things that \
consume no contested space ARE ordinary adds: flat wall items \
(posters, mirrors), embedded openings (a window behind a curtain -- \
overlapping an existing object is fine and expected), and anything \
small or tucked away.

Anchor every proposal to the item it would physically rest on or \
hang from -- not a merely associated item. Give size_m in the SAME \
SCENE UNITS, sized consistently with the listed sizes around it.

The LAST entry is "room": a whole-room scan. Considering everything \
above, is anything expected in a room like this that is absent and \
did NOT fit any single item's answer? Same conservatism and the same \
large-furniture rule apply.

Return ONE fenced ```json block, a JSON ARRAY with EXACTLY one entry \
per item, same order as listed:
{{"id": "<item id>", "implied": [], "expected": [], "swaps": []}}
implied entries: {{"name": "<lowercase item>", "relation": \
"on_top|inside|mounted_on|hangs_from|near", "where": "one short \
phrase", "size_m": [width, depth, height], "evidence": "the listed \
fact this rests on", "confidence": 0.0-1.0, "reason": "one sentence"}}
expected entries: same shape, no "evidence" field.
swap entries: {{"out": ["<ids of listed items to replace; the first \
must be THIS item>"], "in": [{{"name": "<lowercase item>", "size_m": \
[width, depth, height]}}], "confidence": 0.0-1.0, "reason": "one \
sentence"}}
Output ONLY the fenced JSON block.

{inventory}"""

T_SIZE = """\
{firm}You are sizing NEW items about to be inserted into a \
reconstructed 3D room. The room's coordinate scale may differ from \
true real-world metric scale, so DO NOT use textbook dimensions -- \
size each new item CONSISTENTLY with the measured in-scene reference \
objects below (same units).

REFERENCE -- every object in the room, measured in-scene (meters, \
width x depth x height):
{reference}

NEW ITEMS to size (each with its anchor's measured size):
{items}

For each new item give footprint + height IN THE SAME SCENE UNITS, \
sized for its specific anchor (a blanket for THIS bed, a keyboard \
proportional to THIS desk and monitor).

Return ONE fenced ```json block, a JSON ARRAY, EXACTLY one entry per \
new item, same order:
{{"name": "<name>", "size_m": [width, depth, height]}}
Output ONLY the fenced JSON block.
"""

FIRM_PREFIX = ("Your previous response was malformed. This time output "
               "ONLY one fenced ```json code block containing exactly "
               "the JSON structure requested, no prose.\n\n")


# ---------- step-3 box construction (pure code, no LLM) ----------------

def _rects_overlap(a, b):
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1]
                or b[3] <= a[1])


def _scan_free(bounds, w, d, obstacles, target, step=0.05):
    """Slide a w x d footprint over bounds (xmin, zmin, xmax, zmax) on a
    grid; return the free center (x, z) nearest target, or None."""
    xmin, zmin, xmax, zmax = bounds
    if w > xmax - xmin or d > zmax - zmin:
        return None
    best, bestd = None, None
    x = xmin + w / 2
    while x <= xmax - w / 2 + 1e-9:
        z = zmin + d / 2
        while z <= zmax - d / 2 + 1e-9:
            rect = (x - w / 2, z - d / 2, x + w / 2, z + d / 2)
            if not any(_rects_overlap(rect, o) for o in obstacles):
                dd = (x - target[0]) ** 2 + (z - target[1]) ** 2
                if bestd is None or dd < bestd:
                    best, bestd = (x, z), dd
            z += step
        x += step
    return best


def _find_spot(bounds, w, d, obstacles, target):
    """Try both footprint orientations, shrinking to fit if needed.
    Returns (x, z, w, d, clamped) or None."""
    for scale in (1.0, 0.8, 0.64, 0.5):
        for fw, fd in ((w * scale, d * scale), (d * scale, w * scale)):
            got = _scan_free(bounds, fw, fd, obstacles, target)
            if got:
                return got[0], got[1], fw, fd, scale < 1.0
    return None


def _footprint(g):
    return (g["aabb_min"][0], g["aabb_min"][2],
            g["aabb_max"][0], g["aabb_max"][2])


def _mk_box(x, z, w, d, ybase, h):
    mn = [round(x - w / 2, 3), round(ybase, 3), round(z - d / 2, 3)]
    mx = [round(x + w / 2, 3), round(ybase + h, 3), round(z + d / 2, 3)]
    return {"aabb_min": mn, "aabb_max": mx,
            "center": [round((a + b) / 2, 3) for a, b in zip(mn, mx)],
            "size": [round(b - a, 3) for a, b in zip(mn, mx)]}


def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)  # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd, model):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[propose_edits] claude.exe not on PATH")
    r = subprocess.run([exe, "-p", prompt, "--model", model],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=claude_env(), cwd=str(cwd),
                       timeout=CALL_TIMEOUT_S)
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        raise RuntimeError(f"claude exit {r.returncode}: "
                           f"{err[:400] or out[:400]}")
    low = (out + " " + err).lower()
    for bad in ("invalid_api_key", "authentication_error", "credit balance"):
        if bad in low:
            raise RuntimeError(f"claude API-billing/auth error: {out[:400]}")
    return out


def parse_array(text):
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        i = text.find("[")
        if i >= 0:
            try:
                arr, _ = json.JSONDecoder().raw_decode(text[i:])
                return arr
            except ValueError:
                return None
    if raw is None:
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def parse_object(text):
    m = re.search(r"```(?:json)?\s*(\{.*\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        i = text.find("{")
        if i < 0:
            return None
        try:
            obj, _ = json.JSONDecoder().raw_decode(text[i:])
        except ValueError:
            return None
        return obj if isinstance(obj, dict) else None
    try:
        obj = json.loads(raw)
    except ValueError:
        return None
    return obj if isinstance(obj, dict) else None


def conf_of(x, default=0.0):
    try:
        return round(min(1.0, max(0.0, float(x))), 2)
    except (TypeError, ValueError):
        return default


def size_ok(sm):
    return (isinstance(sm, list) and len(sm) == 3
            and all(isinstance(v, (int, float)) and 0 < v < 10
                    for v in sm))


def size_and_place(adds, swaps, swapped_out, graph, sbL, names,
                   cdir, model):
    """STEP 3: size + box (v4/v5, user design 08-02) -- standalone so
    --size-only can re-run it from a frozen loop output without
    repaying the loop's model calls. Sizes normally ride in from the
    loop; T_SIZE (scene-size reference frame) is the fallback for
    sizeless adds -- the ONE model call here. Placement is pure code:
    free-space scan of the anchor top face / floor / wall plane
    against sibling footprints, nearest the "where" referent, both
    orientations, shrink-to-fit FLAGGED (clamped). Swap validation:
    in-items PACKED into the out-items' combined envelope, footprint
    arithmetic decides feasible/infeasible. Mutates adds/swaps in
    place; every box carries box_source="estimated_prior"."""
    if not (adds or swaps):
        return
    # Boxes come from THE CURRENT LAYER, not `resolved`. Placement packs a
    # new object against its neighbours' measured extents, so reading the
    # pre-vote boxes would scan free space in a room whose furniture is the
    # wrong size and in the wrong place.
    boxes = {n["id"]: n["geometry"] for n in scene_state.nodes(graph)}
    # .get + skip: a W5 polygon CONNECTOR wall carries no axis-aligned
    # value_raw — it must not blow up this map (outline-only geometry)
    shell = {n["id"]: n["geometry"]["plane"]["value_raw"]
             for n in graph["nodes"] if n["id"].startswith("arch_")
             and (n["geometry"].get("plane") or {}).get("value_raw")
             is not None}
    # wall axis from the NODE, never from the id string — the old
    # `"_x_" in wall` test is always false on W5 ids (arch_wall_00..)
    # and silently put every wall slab on the wrong axis
    wall_axis = {n["id"]: (n["geometry"].get("plane") or {}).get("axis")
                 for n in graph["nodes"]
                 if n["id"].startswith("arch_wall")}
    parent_id = {}
    for o in sbL["objects"]:
        topt = (o.get("supported_by") or [{}])[0]
        if topt.get("supporter"):
            parent_id[o["id"]] = topt["supporter"]
    need_size = [a for a in adds
                 if not size_ok(a.get("size_m"))]
    if need_size:
        ref_lines = [
            f'  {oid} "{names.get(oid, "?")}": '
            f'{boxes[oid]["size"][0]:.2f} x '
            f'{boxes[oid]["size"][2]:.2f} x '
            f'{boxes[oid]["size"][1]:.2f}'
            for oid in sorted(boxes)]
        item_lines = []
        for i, a in enumerate(need_size, 1):
            anc = a["anchor"]
            if anc in boxes:
                g = boxes[anc]
                actx = (f'anchor {a["anchor_name"]} ({anc}) '
                        f'footprint {g["size"][0]:.2f} x '
                        f'{g["size"][2]:.2f} m')
            else:
                actx = f'anchor {anc} (architecture)'
            item_lines.append(
                f'ITEM {i}: {a["name"]} -- '
                f'{a["relation"] or "on"} {actx}; '
                f'where: {a["where"] or "-"}')
        sgot = None
        for firm in ("", FIRM_PREFIX):
            try:
                out = call_claude(
                    T_SIZE.format(firm=firm,
                                  reference="\n".join(ref_lines),
                                  items="\n".join(item_lines)),
                    cdir, model)
            except (RuntimeError,
                    subprocess.TimeoutExpired) as ex:
                print(f"[propose_edits] sizing fallback "
                      f"failed: {ex}")
                break
            sgot = parse_array(out)
            if sgot is not None and len(sgot) == len(need_size):
                break
            sgot = None
        for a, sz in zip(need_size, sgot or []):
            sm = sz.get("size_m") if isinstance(sz, dict) else None
            if size_ok(sm):
                a["size_m"] = [round(float(v), 3) for v in sm]

    shell_ids = {n["id"] for n in graph["nodes"]
                 if n["id"].startswith("arch_")}
    floor_y = shell["arch_floor"]
    # UP-SIGN AWARENESS (bug found 08-02 review: every box had
    # been placed on the anchor's underside): raw frames may be
    # negative-y-up (bedroom_marble: floor 0.0, ceiling -2.76).
    up = -1.0 if shell["arch_ceiling"] < floor_y else 1.0

    def top_of(g):
        """The anchor's TOP surface y in this frame."""
        return g["aabb_min"][1] if up < 0 else g["aabb_max"][1]

    def mk_up_box(x, z, w, d, base, h):
        """Box standing ON base (its support surface),
        extending h in the UP direction."""
        return _mk_box(x, z, w, d,
                       base if up > 0 else base - h, h)
    xs_raw, zs_raw, _floor_raw, _ceil_raw = wall_axis_planes(graph["nodes"])
    xs = (xs_raw[0], xs_raw[-1])
    zs = (zs_raw[0], zs_raw[-1])
    room = (xs[0] + 0.05, zs[0] + 0.05, xs[1] - 0.05, zs[1] - 0.05)
    floor_rects = [_footprint(g) for oid, g in boxes.items()
                   if g["aabb_min"][1] < floor_y + 0.5
                   and oid not in swapped_out]

    def referent_of(a, placed):
        text = (a["where"] + " " + a["reason"]).lower()
        cands = [(len(nm), oid) for oid, nm in
                 ((i_, names.get(i_, "").lower())
                  for i_ in boxes) if nm and nm in text]
        cands += [(len(p["name"]), p["id"]) for p in placed
                  if p["name"] in text]
        return max(cands)[1] if cands else None

    placed = []   # records that already got boxes (referents)
    pboxes = {}   # proposal id -> box
    psup = {}     # proposal id -> support (obstacle grouping)

    def displacement_of(box):
        """Measured evidence for screening's could-this-have-
        been-missed judgment: how much space the proposal
        claims, and how much of it hides inside existing
        objects (a window behind a curtain overlaps ~fully; a
        wardrobe on open floor overlaps ~nothing)."""
        mn, mx = box["aabb_min"], box["aabb_max"]
        vol = max(1e-9, (mx[0] - mn[0]) * (mx[1] - mn[1])
                  * (mx[2] - mn[2]))
        ov = 0.0
        for k, g in boxes.items():
            if k in swapped_out:
                continue
            dx = (min(mx[0], g["aabb_max"][0])
                  - max(mn[0], g["aabb_min"][0]))
            dy = (min(mx[1], g["aabb_max"][1])
                  - max(mn[1], g["aabb_min"][1]))
            dz = (min(mx[2], g["aabb_max"][2])
                  - max(mn[2], g["aabb_min"][2]))
            if dx > 0 and dy > 0 and dz > 0:
                ov += dx * dy * dz
        return {"footprint_m2":
                round((mx[0] - mn[0]) * (mx[2] - mn[2]), 3),
                "overlap_frac": round(min(1.0, ov / vol), 2)}

    # swaps first: pack the in-items into the out-envelope.
    # Feasibility = FOOTPRINT arithmetic (height left free: one
    # tall item may replace several short ones).
    for s in swaps:
        envs = [boxes[o_] for o_ in s["out"] if o_ in boxes]
        if not envs:
            s["feasible"] = False
            continue
        mn = [min(g["aabb_min"][i] for g in envs)
              for i in range(3)]
        mx = [max(g["aabb_max"][i] for g in envs)
              for i in range(3)]
        s["envelope"] = {"aabb_min": [round(v, 3) for v in mn],
                         "aabb_max": [round(v, 3) for v in mx]}
        bounds = (mn[0], mn[2], mx[0], mx[2])
        tgt = ((mn[0] + mx[0]) / 2, (mn[2] + mx[2]) / 2)
        obst = []
        ok = True
        for ir in sorted(
                s["in"], key=lambda r: -(r["size_m"][0]
                                         * r["size_m"][1])
                if r.get("size_m") else 0):
            sm = ir.get("size_m")
            if not size_ok(sm):
                ir["placement"] = {"failed": "no size"}
                ok = False
                continue
            w, d, h = float(sm[0]), float(sm[1]), float(sm[2])
            spot = _find_spot(bounds, w, d, obst, tgt)
            if spot is None:
                ir["placement"] = {"failed":
                                   "does not fit envelope"}
                ok = False
                continue
            x, z, fw, fd, cl = spot
            box = mk_up_box(x, z, fw, fd,
                            mx[1] if up < 0 else mn[1], h)
            ir["box"] = box
            ir["box_source"] = "estimated_prior"
            ir["placement"] = {"method": "swap_envelope",
                               "clamped": cl}
            obst.append(_footprint(box))
            pboxes[ir["id"]] = box
            placed.append({"name": ir["name"], "id": ir["id"]})
        s["feasible"] = ok

    # RELATION ROUTER (08-02, "window on top of the curtain"
    # postmortem): the reply's relation vocabulary -- on_top | inside |
    # mounted_on | hangs_from | near -- picks the placement rule; the
    # anchor id prefix alone no longer forces stack-on-top. Unresolved
    # combinations fail HONESTLY (recorded, screening sees them).
    def attach_surface_of(oid):
        """The wall/ceiling this object is ultimately attached to,
        walking the support chain (curtain hangs_from wall -> that
        wall). None if the chain grounds out on floor/furniture."""
        cur = oid
        for _ in range(3):
            cur = parent_id.get(cur)
            if cur is None or cur == "arch_floor":
                return None
            if cur.startswith("arch_wall") or cur == "arch_ceiling":
                return cur
        return None

    def nearest_top_below(anc_g, need_w, need_d):
        """Closest furniture top under a wall-mounted host that can
        hold the footprint (the 'remote near the AC' case)."""
        ax, az = anc_g["center"][0], anc_g["center"][2]
        abot = anc_g["aabb_max"][1] if up < 0 else anc_g["aabb_min"][1]
        best = None
        for k, g in boxes.items():
            if k in swapped_out:
                continue
            if up * (abot - top_of(g)) < 0:   # top not below the host
                continue
            fx0, fz0, fx1, fz1 = _footprint(g)
            if (fx1 - fx0) * (fz1 - fz0) < need_w * need_d:
                continue
            d2 = (g["center"][0] - ax) ** 2 + (g["center"][2] - az) ** 2
            if best is None or d2 < best[0]:
                best = (d2, k)
        return best[1] if best else None

    for a in adds:
        a["box_source"] = "estimated_prior"
        if not size_ok(a.get("size_m")):
            a["placement"] = {"failed": "no size (loop + "
                              "fallback both empty)"}
            continue
        w, d, h = (float(v) for v in a["size_m"])
        ref = referent_of(a, placed)
        allb = dict(boxes)
        allb.update(pboxes)
        rel = str(a.get("relation") or "").strip().lower()
        anc = a["anchor"]
        sup = a["support"]

        def finish(box, method, clamped=False, group=None, note=None):
            a["box"] = box
            a["placement"] = {"method": method, "referent": ref,
                              "clamped": clamped}
            if note:
                a["placement"]["note"] = note
            a["displacement"] = displacement_of(box)
            pboxes[a["id"]] = box
            psup[a["id"]] = group
            placed.append(a)

        def fail(why, method=None):
            a["placement"] = {"failed": why, "referent": ref}
            if method:
                a["placement"]["method"] = method

        def ref_tgt(default):
            return ((allb[ref]["center"][0], allb[ref]["center"][2])
                    if ref and ref in allb else default)

        def scan_top(surf, tgt=None):
            """Free spot on surf's top face."""
            g_ = allb[surf]
            obst = [_footprint(allb[k]) for k in allb
                    if k not in swapped_out
                    and (parent_id.get(k) == surf
                         or psup.get(k) == ("on", surf))]
            if tgt is None:
                tgt = ref_tgt((g_["center"][0], g_["center"][2]))
            spot = _find_spot(_footprint(g_), w, d, obst, tgt)
            if spot is None:
                fail("no free spot found", f"on_top:{surf}")
                return
            x, z, fw, fd, cl = spot
            finish(mk_up_box(x, z, fw, fd, top_of(g_), h),
                   f"on_top:{surf}", cl, ("on", surf))

        def scan_inside(surf):
            """Free spot INSIDE surf, standing on its inner floor."""
            g_ = allb[surf]
            obst = [_footprint(allb[k]) for k in allb
                    if k not in swapped_out
                    and psup.get(k) == ("in", surf)]
            spot = _find_spot(_footprint(g_), w, d, obst,
                              (g_["center"][0], g_["center"][2]))
            if spot is None:
                fail("no free spot found", f"inside:{surf}")
                return
            x, z, fw, fd, cl = spot
            bottom = (g_["aabb_max"][1] if up < 0
                      else g_["aabb_min"][1])
            finish(mk_up_box(x, z, fw, fd, bottom, h),
                   f"inside:{surf}", cl, ("in", surf),
                   "taller than host" if h > g_["size"][1] else None)

        def scan_floor(tgt=None):
            if tgt is None:
                tgt = ref_tgt(((room[0] + room[2]) / 2,
                               (room[1] + room[3]) / 2))
            obst = floor_rects + [_footprint(b)
                                  for b in pboxes.values()]
            spot = _find_spot(room, w, d, obst, tgt)
            if spot is None:
                fail("no free spot found", "floor")
                return
            x, z, fw, fd, cl = spot
            finish(mk_up_box(x, z, fw, fd, floor_y, h), "floor", cl,
                   ("floor", None))

        def wall_slab(wall, cy, other, method):
            """Slab embedded in the wall plane, height-clamped into
            the room (the window-through-the-ceiling fix)."""
            t = 0.1
            if wall_axis.get(wall) not in ("x", "z"):
                fail(f"wall {wall} has no axis-aligned plane (polygon "
                     "connector) — cannot embed a slab", method)
                return
            lo = min(floor_y, shell["arch_ceiling"])
            hi = max(floor_y, shell["arch_ceiling"])
            cy = min(hi - h / 2, max(lo + h / 2, cy))
            if wall_axis[wall] == "x":
                box = _mk_box(shell[wall], other, t, w, cy - h / 2, h)
            else:
                box = _mk_box(other, shell[wall], w, t, cy - h / 2, h)
            finish(box, method, group=("wall", wall))

        if sup == "wall" and anc in shell_ids:
            # anchored to a wall directly: v6 behavior + height clamp
            if ref and ref in allb:
                rc = allb[ref]
                cy = rc["center"][1]
                other = rc["center"][2] if wall_axis.get(anc) == "x" \
                    else rc["center"][0]
            else:
                cy = floor_y + up * 1.4
                other = (room[1] + room[3]) / 2 \
                    if wall_axis.get(anc) == "x" \
                    else (room[0] + room[2]) / 2
            wall_slab(anc, cy, other, f"wall:{anc}")
        elif sup == "floor":
            scan_floor()
        elif anc in boxes:
            g = boxes[anc]
            if rel in ("mounted_on", "hangs_from"):
                surf = attach_surface_of(anc)
                if surf == "arch_ceiling":
                    # hang below the ceiling over the anchor
                    cv = shell["arch_ceiling"]
                    finish(_mk_box(g["center"][0], g["center"][2],
                                   w, d, min(cv, cv - up * h), h),
                           "ceiling_hang", group=("ceil", None))
                elif surf:   # a wall: embed behind/at the anchor
                    cy = g["center"][1]
                    other = g["center"][2] \
                        if wall_axis.get(surf) == "x" \
                        else g["center"][0]
                    wall_slab(surf, cy, other,
                              f"wall_via:{anc}:{surf}")
                else:
                    fail(f"mount surface unresolved ({anc} is not "
                         f"wall/ceiling-attached)", f"{rel}:{anc}")
            elif rel == "inside":
                scan_inside(anc)
            elif rel == "near":
                par = parent_id.get(anc)
                if par in boxes:          # host stands on furniture
                    scan_top(par, tgt=(g["center"][0],
                                       g["center"][2]))
                elif par in shell_ids and par != "arch_floor":
                    # wall/ceiling-mounted host: referent object top,
                    # else nearest furniture top below, else floor
                    landing = (ref if ref and ref in boxes
                               and ref != anc else
                               nearest_top_below(g, w, d))
                    if landing:
                        scan_top(landing, tgt=(g["center"][0],
                                               g["center"][2]))
                    else:
                        scan_floor(tgt=(g["center"][0],
                                        g["center"][2]))
                else:                     # floor-standing host
                    scan_floor(tgt=(g["center"][0], g["center"][2]))
            else:                         # on_top + unknown default
                scan_top(anc)
        else:
            fail(f"no placement rule for {sup} "
                 f"(relation {rel or 'none'})")



def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--no-llm", action="store_true",
                    help="aggregate delete candidates only; no adds")
    ap.add_argument("--size-only", action="store_true",
                    help="skip the loop: reload edit_proposals_raw.json "
                         "(fallback: strip edit_proposals.json) and "
                         "re-run step 3 sizing/placement alone")
    ap.add_argument("--max-rounds", type=int, default=3,
                    help="loop cap (arbitrary, user 08-02); the "
                         "natural stop is a dry round")
    args = ap.parse_args()

    cdir = paths.compose_dir(args.scene)
    gpath = paths.scene_dir(args.scene) / "scene_graph.json"
    graph = json.loads(gpath.read_text(encoding="utf-8"))
    # names from THE CURRENT LAYER, not `resolved`: this is the inventory
    # the model is shown and the vocabulary the proposals must speak. A
    # node the judges split is absent from `resolved` and a merged-away one
    # is still in it, so the pre-vote list both invents and omits objects.
    _layer, res = scene_state.current(graph)
    names = {n["id"]: n["name"] for n in res["nodes"]}

    sbp = cdir / "supported_by.json"
    cop = cdir / "consistency.json"
    for p, what in ((sbp, "supported_by"), (cop, "consistency")):
        if not p.exists():
            raise SystemExit(f"[propose_edits] no {p.name} -- run "
                             f"compose/{what}.py first (this module reads "
                             f"both, writes nothing they read)")
    sbL = json.loads(sbp.read_text(encoding="utf-8"))
    coL = json.loads(cop.read_text(encoding="utf-8"))
    sb = {o["id"]: o for o in sbL["objects"]}

    # ---------------- DELETE candidates: deterministic aggregation -------
    cand = {}       # id -> [signal strings]

    def flag(oid, signal):
        cand.setdefault(oid, []).append(signal)

    for o in sbL["objects"]:
        if o.get("none_plausible"):
            flag(o["id"], "supported_by: none_plausible -- "
                          + o.get("flag_reason", "")[:160])

    # every support-type edge dropped + weak own support
    by_subject = {}
    for e in coL["edges"]:
        if e["type"] in SUPPORT_EDGE_TYPES:
            by_subject.setdefault(e["a"], []).append(e)
    for oid, edges in by_subject.items():
        if not edges or not all(e["verdict"] == "DROP" for e in edges):
            continue
        top = (sb.get(oid, {}).get("supported_by") or [{}])[0]
        if conf_of(top.get("confidence"), 1.0) < WEAK_TOP_CONF:
            flag(oid, f"all {len(edges)} support-type edges DROPped and "
                      f"top support confidence "
                      f"{top.get('confidence')} < {WEAK_TOP_CONF}")

    print(f"[propose_edits] delete candidates: {len(cand)}")
    for oid, sigs in sorted(cand.items()):
        print(f"    {oid} ({names.get(oid, '?')}): {len(sigs)} signal(s)")

    # ---------------- LLM passes ----------------------------------------
    deletes, adds, petitions, swaps = [], [], [], []
    add_answered = None   # per-round reply coverage
    round_elapsed = None
    swapped_out = set()
    if args.size_only:
        # DEV RE-ENTRY (not a pipeline path): canonical runs are one
        # invocation; this reloads a frozen loop output to debug step 3
        src = next((p for p in (cdir / "edit_proposals_raw.json",
                                cdir / "edit_proposals.json")
                    if p.exists()), None)
        if src is None:
            raise SystemExit("[propose_edits] --size-only: neither "
                             "edit_proposals_raw.json nor "
                             "edit_proposals.json exists for this scene")
        prev = json.loads(src.read_text(encoding="utf-8"))
        deletes = prev.get("deletes") or []
        adds = prev.get("adds") or []
        swaps = prev.get("swaps") or []
        petitions = prev.get("reopen_petitions") or []
        meta = prev.get("counts") or prev   # final vs raw layout
        add_answered = meta.get("round_answered")
        round_elapsed = meta.get("round_elapsed_s")
        # strip step-3 artifacts back to pure loop output
        for a in adds:
            for k in ("box", "box_source", "placement", "displacement"):
                a.pop(k, None)
        for s in swaps:
            for k in ("envelope", "feasible"):
                s.pop(k, None)
            for ir in s.get("in") or []:
                for k in ("box", "box_source", "placement"):
                    ir.pop(k, None)
        swapped_out = {o_ for s in swaps for o_ in (s.get("out") or [])}
        print(f"[propose_edits] --size-only: {len(adds)} adds + "
              f"{len(swaps)} swaps from {src.name}; step 3 alone")
    elif args.no_llm:
        deletes = [{"id": oid, "name": names.get(oid),
                    "signals": sigs, "status": "CANDIDATE",
                    "verdict": None}
                   for oid, sigs in sorted(cand.items())]
        print("[propose_edits] --no-llm: candidates written unconfirmed, "
              "no adds proposed, no petitions")
    else:
        # audit call: delete confirm/deny + duplicate suspicions.
        # RAW EVIDENCE, verbatim -- code pipes, never interprets.
        co_by_obj = {}
        for e in coL["edges"]:
            line = (f'{e.get("verdict", "?")} {e["a"]} -{e["type"]}- '
                    f'{e["b"]}: '
                    + (f'"{e["reason"]}"' if e.get("reason")
                       else f'[{e.get("class", "code-stamped")}]'))
            for oid in (e["a"], e["b"]):
                co_by_obj.setdefault(oid, []).append(line)
        drops = [e for e in coL["edges"]
                 if e.get("verdict") == "DROP" and e.get("reason")]
        dtxt = "\n".join(
            f'- {e["a"]} ("{names.get(e["a"], e["a"])}") -{e["type"]}- '
            f'{e["b"]} ("{names.get(e["b"], e["b"])}"): "{e["reason"]}"'
            for e in drops) or "(none)"
        if cand or drops:
            items = []
            for i, (oid, sigs) in enumerate(sorted(cand.items()), 1):
                o = sb.get(oid, {})
                top = (o.get("supported_by") or [{}])[0]
                ver = co_by_obj.get(oid) or ["(none)"]
                items.append(
                    f'CANDIDATE {i}: {oid} "{names.get(oid, "?")}" -- '
                    f'current support: {top.get("how")} '
                    f'{top.get("supporter")} ({top.get("confidence")})\n'
                    + "\n".join(f"  signal: {s}" for s in sigs)
                    + "\n  consistency verdicts on this object "
                    "(verbatim):\n"
                    + "\n".join(f"    {v}" for v in ver[:8]))
            got = None
            for firm in ("", FIRM_PREFIX):
                try:
                    out = call_claude(
                        T_DELETE.format(
                            firm=firm,
                            items=("\n\n".join(items)
                                   or "(no delete candidates this run)"),
                            drops=dtxt),
                        cdir, args.model)
                except (RuntimeError, subprocess.TimeoutExpired) as ex:
                    print(f"[propose_edits] audit pass failed: {ex}")
                    break
                got = parse_object(out)
                if got:
                    break
            by_id = {e.get("id"): e
                     for e in (got or {}).get("verdicts", [])
                     if isinstance(e, dict)}
            for oid, sigs in sorted(cand.items()):
                e = by_id.get(oid)
                ok = e and e.get("verdict") in ("DELETE", "KEEP") \
                    and isinstance(e.get("reason"), str)
                deletes.append({
                    "id": oid, "name": names.get(oid), "signals": sigs,
                    "status": "JUDGED" if ok else "CANDIDATE",
                    "verdict": e["verdict"] if ok else None,
                    "confidence": conf_of(e.get("confidence")) if ok
                    else None,
                    "reason": e["reason"].strip() if ok else None})
            valid = set(names)
            for s in (got or {}).get("duplicate_suspicions", []):
                if not isinstance(s, dict):
                    continue
                pair = s.get("pair") or []
                if (len(pair) == 2 and pair[0] != pair[1]
                        and all(str(p).startswith("obj_") and p in valid
                                for p in pair)):
                    petitions.append({
                        "pair": [pair[0], pair[1]],
                        "names": [names[pair[0]], names[pair[1]]],
                        "confidence": conf_of(s.get("confidence")),
                        "evidence": str(s.get("evidence", "")).strip()})
        # add/swap proposals -- v5 CANON LOOP (user 08-02): rounds fold
        # this round's proposals into the working inventory and re-ask;
        # stop when a round proposes nothing (dry) or at --max-rounds.
        # The loop replaced the 3-run union by user ruling (total count
        # is the wrong metric -- semantic/spatial coherence is): the
        # loop self-paces, never duplicates (later rounds SEE earlier
        # proposals), and the round stamp is the salience evidence
        # (round 1 = near-certain misses, later = deeper inferences).
        # SWAP channel (user design): re-interpret N listed items as M
        # new ones (one big <-> several small); in-scene sizes ride in
        # the item lines so the trade is arithmetic, and CODE validates
        # the envelope in step 3, never the model. Proposals only --
        # nothing enters the scene state before screening rules.
        # the loop's working inventory is measured from THE CURRENT LAYER,
        # not `resolved` — the sizes in these item lines are what scene-
        # scales every reply, so pre-vote boxes would quietly rescale the
        # whole round.
        boxes = {n["id"]: n["geometry"] for n in scene_state.nodes(graph)}
        xs_raw, zs_raw, floor_raw, ceil_raw = wall_axis_planes(graph["nodes"])
        dims = (f'room ~{xs_raw[-1] - xs_raw[0]:.1f} x '
                f'{zs_raw[-1] - zs_raw[0]:.1f} m, '
                f'height {abs(ceil_raw - floor_raw):.1f} m')
        arch_ids = [n["id"] for n in graph["nodes"]
                    if n["id"].startswith("arch_")]

        def support_of(anchor):
            if anchor.startswith("obj_"):
                return f"on:{anchor}"
            if anchor.startswith("arch_wall"):
                return "wall"
            if anchor == "arch_ceiling":
                return "ceiling"
            return "floor"   # arch_floor + the room-scan channel

        # working inventory (display state the loop folds into; the
        # real graph is never touched)
        inv_names = dict(names)
        inv_size = {oid: [g["size"][0], g["size"][2], g["size"][1]]
                    for oid, g in boxes.items()}   # w, d, h
        inv_parent, inv_kids = {}, {}
        for o in sbL["objects"]:
            top = (o.get("supported_by") or [{}])[0]
            sup, how = top.get("supporter"), top.get("how")
            if not sup:
                continue
            inv_parent[o["id"]] = (f'{how} {inv_names.get(sup, sup)} '
                                   f'({sup})')
            inv_kids.setdefault(sup, []).append(
                f'{inv_names.get(o["id"], "?")} ({o["id"]}, {how})')
        obj_rows = [o["id"] for o in sbL["objects"]]
        swapped_out = set()
        add_answered = []
        round_elapsed = []
        rounds_done = 0

        for rnd in range(1, args.max_rounds + 1):
            t_rnd = time.time()
            lines = [dims, "", "ITEMS (id, name, in-scene size "
                     "w x d x h m, connections):"]
            order = []
            for oid in obj_rows:
                order.append(oid)
                sz = inv_size.get(oid)
                stxt = (f'{sz[0]:.2f} x {sz[1]:.2f} x {sz[2]:.2f}'
                        if sz else 'size ?')
                k = inv_kids.get(oid)
                lines.append(
                    f'- {oid} "{inv_names.get(oid, "?")}" [{stxt}] -- '
                    f'rests: {inv_parent.get(oid, "(unresolved)")}'
                    + (f'; holds: {"; ".join(k)}' if k else ''))
            for aid in arch_ids:
                order.append(aid)
                k = inv_kids.get(aid) or []
                label = aid.replace("arch_", "").replace("_", " ")
                lines.append(f'- {aid} [{label}] -- holds {len(k)}: '
                             + ("; ".join(k) if k else "(nothing)"))
            order.append("room")
            lines.append('- room [the whole room -- final scan, '
                         'see instructions]')

            got = None
            for firm in ("", FIRM_PREFIX):
                try:
                    out = call_claude(
                        T_ADD.format(firm=firm,
                                     inventory="\n".join(lines)),
                        cdir, args.model)
                except (RuntimeError, subprocess.TimeoutExpired) as ex:
                    print(f"[propose_edits] round {rnd} failed: {ex}")
                    break
                got = parse_array(out)
                if got is not None:
                    break
            if got is None:
                break
            rounds_done = rnd
            by_item = {e.get("id"): e for e in got if isinstance(e, dict)}
            add_answered.append(
                f"{sum(1 for o in order if o in by_item)}/{len(order)}")

            round_text = "\n".join(lines).lower()
            new_adds, new_swaps = [], []
            for oid in order:   # anchor = list position, never the reply
                ent = by_item.get(oid) or {}
                for ch in ("implied", "expected"):
                    for a in (ent.get(ch) or []):
                        if not isinstance(a, dict):
                            continue
                        nm = a.get("name")
                        if not isinstance(nm, str) or not nm.strip():
                            continue
                        # the swap-only constraint for bulky open-space
                        # claims is PROMPT CONTEXT the agent applies
                        # (user 08-02: no hard-coded gate); code only
                        # MEASURES displacement in step 3.
                        new_adds.append((oid, ch, a))
                for s in (ent.get("swaps") or []):
                    if not isinstance(s, dict):
                        continue
                    outs = s.get("out")
                    ins = [it for it in (s.get("in") or [])
                           if isinstance(it, dict)
                           and isinstance(it.get("name"), str)
                           and it["name"].strip()]
                    if (not isinstance(outs, list) or not outs or not ins
                            or len(set(outs)) != len(outs)
                            or not all(isinstance(o_, str)
                                       and o_.startswith("obj_")
                                       and o_ in obj_rows
                                       for o_ in outs)):
                        continue
                    new_swaps.append({
                        "out": outs, "in": ins,
                        "confidence": conf_of(s.get("confidence")),
                        "reason": str(s.get("reason", "")).strip()})
            round_elapsed.append(round(time.time() - t_rnd, 1))
            print(f"[propose_edits] round {rnd}: {len(new_adds)} adds, "
                  f"{len(new_swaps)} swaps in {round_elapsed[-1]:.0f}s "
                  f"({len(order)} items)")
            if not new_adds and not new_swaps:
                break   # DRY -- the loop's natural stop

            for i, (oid, ch, a) in enumerate(new_adds, 1):
                nid = f"add_r{rnd}n{i}"
                rec = {"id": nid, "round": rnd, "channel": ch,
                       "name": a["name"].strip().lower(),
                       "support": support_of(oid), "anchor": oid,
                       "anchor_name": inv_names.get(oid, oid),
                       "relation": str(a.get("relation", "")).strip(),
                       "where": str(a.get("where", "")).strip(),
                       "confidence": conf_of(a.get("confidence")),
                       "reason": str(a.get("reason", "")).strip()}
                if ch == "implied":
                    ev = str(a.get("evidence", "")).strip()
                    rec["evidence"] = ev
                    # mechanical check only: does the quote actually
                    # appear in this round's item lines? (paraphrases
                    # legitimately fail -- informational, not a gate)
                    rec["evidence_found"] = bool(
                        ev and ev.lower() in round_text)
                if size_ok(a.get("size_m")):
                    rec["size_m"] = [round(float(v), 3)
                                     for v in a["size_m"]]
                adds.append(rec)
                # fold into the working inventory
                anc = oid if oid != "room" else "arch_floor"
                how = rec["relation"] or "on_top"
                inv_names[nid] = rec["name"]
                if rec.get("size_m"):
                    inv_size[nid] = rec["size_m"]
                inv_parent[nid] = (f'{how} {inv_names.get(anc, anc)} '
                                   f'({anc})')
                inv_kids.setdefault(anc, []).append(
                    f'{rec["name"]} ({nid}, {how})')
                obj_rows.append(nid)

            for j, s in enumerate(new_swaps, 1):
                sid = f"swap_r{rnd}n{j}"
                in_recs = []
                for m, it in enumerate(s["in"], 1):
                    ir = {"id": f"{sid}_in{m}",
                          "name": it["name"].strip().lower()}
                    if size_ok(it.get("size_m")):
                        ir["size_m"] = [round(float(v), 3)
                                        for v in it["size_m"]]
                    in_recs.append(ir)
                rec = {"id": sid, "round": rnd, "out": s["out"],
                       "out_names": [inv_names.get(o_, o_)
                                     for o_ in s["out"]],
                       "in": in_recs,
                       "confidence": s["confidence"],
                       "reason": s["reason"]}
                host_parent = inv_parent.get(s["out"][0])
                first_in = in_recs[0]["id"]
                # remove out items from the working inventory
                out_children = []
                for o_ in s["out"]:
                    swapped_out.add(o_)
                    if o_ in obj_rows:
                        obj_rows.remove(o_)
                    for kl in inv_kids.values():
                        kl[:] = [t for t in kl if f'({o_},' not in t]
                    # children of an out item re-hang on the first in
                    for kid_id, ptxt in list(inv_parent.items()):
                        if f'({o_})' in ptxt and kid_id in obj_rows:
                            out_children.append(kid_id)
                            inv_parent[kid_id] = (
                                f'on_top {in_recs[0]["name"]} '
                                f'({first_in})')
                            inv_kids.setdefault(first_in, []).append(
                                f'{inv_names.get(kid_id, "?")} '
                                f'({kid_id}, on_top)')
                rec["out_children"] = out_children
                for ir in in_recs:
                    inv_names[ir["id"]] = ir["name"]
                    if ir.get("size_m"):
                        inv_size[ir["id"]] = ir["size_m"]
                    inv_parent[ir["id"]] = (host_parent
                                            or "(unresolved)")
                    obj_rows.append(ir["id"])
                swaps.append(rec)

        # freeze the loop's output BEFORE step 3: a sizing/placement
        # crash or rework must never cost the model calls again
        # (--size-only re-enters from this file; regenerated every
        # full run, never hand-edited)
        rpath = cdir / "edit_proposals_raw.json"
        rpath.write_text(json.dumps({
            "scene": args.scene, "built": str(date.today()),
            "generated_by": "compose/propose_edits.py",
            "graph_fingerprint": paths.graph_fingerprint(args.scene),
            "model": args.model, "prompt_version": PROMPT_VERSION,
            "note": "LOOP OUTPUT ONLY -- pre step 3, no boxes; the "
                    "--size-only re-entry point",
            "rounds": len(add_answered or []),
            "round_answered": add_answered,
            "round_elapsed_s": round_elapsed,
            "deletes": deletes, "adds": adds, "swaps": swaps,
            "reopen_petitions": petitions,
        }, indent=1), encoding="utf-8")
        print(f"[propose_edits] wrote {rpath} (loop output frozen)")

    size_and_place(adds, swaps, swapped_out, graph, sbL, names,
                   cdir, args.model)

    layer = {
        "scene": args.scene, "built": str(date.today()),
        "elapsed_s": round(time.time() - t0, 1),
        "generated_by": "compose/propose_edits.py",
        "graph_fingerprint": paths.graph_fingerprint(args.scene),
        "model": None if args.no_llm else args.model,
        "prompt_version": PROMPT_VERSION,
        "note": ("S3 IN-LANE MODULE -- proposals only; adds/deletes land "
                 "at S4 SCREENING (not built yet), the same door as the "
                 "judge's add/delete/replace re-entry. reopen_petitions "
                 "are referrals to the step-2 pair judge (SAME_CANDIDATE) "
                 "+ future screening hold-inputs -- unwired, review-only."),
        "counts": {"delete_candidates": len(cand),
                   "delete_proposed": sum(1 for d in deletes
                                          if d.get("verdict") == "DELETE"),
                   "adds_proposed": len(adds),
                   "adds_boxed": sum(1 for a in adds if a.get("box")),
                   "swaps_proposed": len(swaps),
                   "swaps_feasible": sum(1 for s in swaps
                                         if s.get("feasible")),
                   "rounds": None if args.no_llm else
                   len(add_answered or []),
                   "round_answered": add_answered,
                   "round_elapsed_s": None if args.no_llm
                   else round_elapsed,
                   "reopen_petitions": len(petitions)},
        "deletes": deletes,
        "adds": adds,
        "swaps": swaps,
        "reopen_petitions": petitions,
    }
    opath = cdir / "edit_proposals.json"
    opath.write_text(json.dumps(layer, indent=1), encoding="utf-8")
    print(f"[propose_edits] wrote {opath} "
          f"({time.time() - t0:.0f}s elapsed)")
    print(f"[propose_edits] counts: {json.dumps(layer['counts'])}")
    for d in deletes:
        if d.get("verdict") == "DELETE":
            print(f"    DELETE {d['id']} ({d['name']}) "
                  f"[{d['confidence']}]: {d['reason'][:100]}")
    for a in adds:
        pl = a.get("placement") or {}
        if a.get("box"):
            s = a["box"]["size"]
            geo = (f'box {s[0]}x{s[2]}x{s[1]} @ {a["box"]["center"]} '
                   f'({pl.get("method")}'
                   + (", clamped" if pl.get("clamped") else "") + ")")
        else:
            geo = f'NO BOX ({pl.get("failed", "?")})'
        ev = (" ev✓" if a.get("evidence_found")
              else " ev?" if a.get("channel") == "implied" else "")
        print(f"    ADD r{a.get('round', '?')} "
              f"[{a.get('channel', '?')}{ev}] {a['name']} <- "
              f"{a.get('anchor')} ({a.get('anchor_name')}) "
              f"[conf {a['confidence']}]: {geo}")
    for s in swaps:
        feas = "FEASIBLE" if s.get("feasible") else "INFEASIBLE"
        ins = ", ".join(f'{ir["name"]}'
                        + (f' {ir["size_m"]}' if ir.get("size_m")
                           else '') for ir in s["in"])
        print(f"    SWAP r{s['round']} {'+'.join(s['out'])} "
              f"({'/'.join(s['out_names'])}) -> {ins} [{feas}, "
              f"conf {s['confidence']}]: {s['reason'][:80]}")
    for p in petitions:
        print(f"    PETITION {p['pair'][0]}+{p['pair'][1]} "
              f"({p['names'][0]}/{p['names'][1]}) [{p['confidence']}]: "
              f"{p['evidence'][:100]}")


if __name__ == "__main__":
    main()
