"""
STEP 3 COMPOSE+LOOP, module 1 -- SUPPORTED_BY attribution.

Contract (user 07-26G, PLAN_COMPOSE_LOOP.md): the touch-based anchor rule
is crude -- false anchors (obj_061 book grazing a wall from a shelf) and
misses (obj_013 picture resting on a shelf). Per object we DETERMINISTICALLY
list every candidate relation WITH ITS METRICS (existing graph edges +
gravity/beneath scan + wall/ceiling/floor proximity + near-contact scan),
then ONE batched text-only LLM pass reasons over those numbers and returns
the superseding `supported_by` field: 1..n ranked options (ambiguity is a
legitimate output), or none_plausible (=> box/existence flag).

Scope note (user 07-26G): a bundled "second job" (flag nonsense contact
edges in the same pass) was tried as prompt v2 and RETRACTED the same
session -- the nonsense judgment needs the RESOLVED supported_by of both
endpoints (cross-object coherence), so edge cleaning is a DOWNSTREAM
step. This module answers ONE question: what holds each object up.
Candidates stay [cN]-numbered in the output so downstream steps can
reference them.

The graph is NOT rewritten: output is a layer BESIDE it,
out/<scene>/compose/supported_by.json. Superseded edges remain as evidence.
"anchor" becomes a derived reading (top option's supporter is arch_*).

Frame: RAW gen_raw.ply space, physical up = -y => a box's physical BOTTOM
is its MAX raw y (scene_graph.json frame note; the ST-mirror-bug family --
every vertical comparison here goes through phys_h() = -y).

Degrade path: --no-llm (or any call failure) writes candidates with
supported_by: null and status NEEDS_REVIEW -- nothing auto-resolved.

PROMPT SCHEMA: fixed versioned template, deterministic filler, nothing
authored per case (judge_near v2 lesson: code interprets the numbers).
Cache: out/<scene>/compose/supported_by_cache.json keyed by object id +
evidence hash (re-runs free; --fresh ignores it).

Run:
  python compose/supported_by.py --scene bedroom_marble --no-llm   # det. only
  python compose/supported_by.py --scene bedroom_marble --smoke    # 1 batch, no write
  python compose/supported_by.py --scene bedroom_marble
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

MODEL = "sonnet"
CALL_TIMEOUT_S = 480
BATCH_SIZE = 30          # text-only items; ~3 calls for a 90-object room
PROMPT_VERSION = "5"     # v5: "Looks like" sentences downgraded to
                         # identity-only evidence (tight crops cut off the
                         # bottom -- their support claims are scene-dressing;
                         # obj_001 "sitting on a shelf" lesson).
                         # v4 = most-plausible framing + directional overlap
                         # metrics; v3 = single job; v2 = retracted bundle
                         # (template isn't hashed -- never reuse a number)

SUPPORT_EDGE_TYPES = ("ON", "IN", "IN_WALL", "ATTACHED")  # crude rule (viewer)
HOW_VOCAB = ("rests_on", "mounted_on", "leans_on", "hangs_from",
             "embedded_in", "inside")

# tolerances (m) -- box error > contact tolerance (the obj_013 lesson)
BENEATH_TOL = 0.30       # |object bottom - candidate top| window; raised
                         # 0.12 -> 0.30 (user 07-26G: occluded/obfuscated
                         # detections truncate boxes well past 12 cm -- the
                         # metrics do the arguing, so offer generously)
WALL_NEAR = 0.15         # wall/ceiling/floor proximity worth reporting
NEAR_SCAN = 0.05         # new near-contact pairs not already in the graph
MIN_OVERLAP_FRAC = 0.05  # of the upper object's base, for a beneath candidate

ARCH_LABEL = {"arch_floor": "the floor", "arch_ceiling": "the ceiling",
              "arch_wall_x_low": "wall x_low", "arch_wall_x_high": "wall x_high",
              "arch_wall_z_low": "wall z_low", "arch_wall_z_high": "wall z_high"}

TEMPLATE = """\
{firm}You are auditing the support structure of objects extracted from a \
3D scan of ONE indoor room. All boxes were measured; sizes are noisy \
(centimeter-level error is normal, so a small gap or graze can be \
measurement noise rather than real contact).

For EACH numbered item you get the object's name, size, height, and its \
CANDIDATE relations with measured metrics. Your job: the SINGLE MOST \
PLAUSIBLE explanation of what actually holds the object up, weighing all \
the numbers together (an occluded detection can truncate a box, so a \
moderate gap to an otherwise-obvious supporter can beat an exotic story). \
Physical common sense applies: nothing floats; resting needs support \
beneath; a footprint overlap that is only a thin edge sliver means the \
objects are BESIDE each other, not one inside/on the other; wall mounting \
needs a plausible fastening (AC unit, picture, curtain rod -- a book does \
not mount to a wall); a thin graze against a wall while something solid \
sits beneath is NOT support; leaning objects rest on one thing AND \
balance against another.

About the "Looks like" sentences: they are pixel testimony from crops \
that include the object's surroundings, so they may legitimately mention \
what the object visibly rests on or hangs from. Weigh that testimony \
TOGETHER with the measured numbers; when the two conflict, prefer the \
explanation that reconciles both (a box truncated by occlusion is common \
-- e.g. a floor object whose box bottom floats above the floor).

Return ONE fenced ```json block containing a JSON ARRAY with EXACTLY one \
object per item, same order:
{{"id": "<the id given>", "options": [{{"supporter": "<candidate id>", \
"how": "rests_on|mounted_on|leans_on|hangs_from|embedded_in|inside", \
"against": "<second id, ONLY for leans_on>", "confidence": 0.0-1.0, \
"reason": "one sentence"}}]}}
Rank options best-first. Give MULTIPLE options only when several are \
genuinely semantically viable (e.g. a picture that could hang on the wall \
OR stand on the shelf); one option is the normal case. Supporters must be \
ids from the item's candidate list. If NO candidate makes physical sense, \
return "options": [] and add "none_plausible": true with a "reason" -- \
that usually means the box or the detection is wrong, and saying so is \
valuable. Output ONLY the fenced JSON block.

{items}"""

FIRM_PREFIX = ("Your previous response was malformed. This time output "
               "ONLY one fenced ```json code block containing the JSON "
               "array, no prose.\n\n")


# ---------------------------------------------------------------- geometry
def phys_h(y_raw):
    """Physical height (m, up positive) of a raw-frame y coordinate."""
    return -y_raw


class Box:
    def __init__(self, node):
        g = node["geometry"]
        self.mn = g["aabb_min"]
        self.mx = g["aabb_max"]
        self.size = g["size"]
        self.bottom_h = phys_h(self.mx[1])   # physical bottom = MAX raw y
        self.top_h = phys_h(self.mn[1])

    def base_area(self):
        return max(self.size[0] * self.size[2], 1e-9)

    def volume(self):
        return max(self.size[0] * self.size[1] * self.size[2], 1e-9)


def h_overlap(a, b):
    """Horizontal (x,z) overlap area between two boxes."""
    ox = min(a.mx[0], b.mx[0]) - max(a.mn[0], b.mn[0])
    oz = min(a.mx[2], b.mx[2]) - max(a.mn[2], b.mn[2])
    return max(ox, 0.0) * max(oz, 0.0)


def inter_volume(a, b):
    v = 1.0
    for i in range(3):
        o = min(a.mx[i], b.mx[i]) - max(a.mn[i], b.mn[i])
        if o <= 0:
            return 0.0
        v *= o
    return v


def box_gap(a, b):
    """Min distance between two AABBs (0 when touching/overlapping)."""
    d2 = 0.0
    for i in range(3):
        g = max(a.mn[i] - b.mx[i], b.mn[i] - a.mx[i], 0.0)
        d2 += g * g
    return d2 ** 0.5


def wall_gap(box, plane):
    """Signed gap to a vertical wall plane: >0 interior clearance,
    <0 penetration depth. Returns (gap, face) with face = the box side
    that meets the wall ('x_min'...)."""
    ax = {"x": 0, "z": 2}[plane["axis"]]
    v = plane["value_raw"]
    inward = plane["inward_normal_raw"][ax]
    if inward > 0:      # interior is coords > v
        return box.mn[ax] - v, ("x_min" if ax == 0 else "z_min")
    return v - box.mx[ax], ("x_max" if ax == 0 else "z_max")


def cm(x):
    return f"{x * 100:.1f} cm"


# ---------------------------------------------------------- candidate pass
def build_candidates(nodes, arch_planes, edges, beneath_tol=BENEATH_TOL):
    """Per object: every candidate relation with measured metrics.
    Returns {oid: {"cands": [{partner, src, rel, text}], "partners": set,
                   "context": [str]}}. cands order is stable -- item_block
    numbers them [c1..cN] and the LLM's nonsense verdicts reference those."""
    boxes = {n["id"]: Box(n) for n in nodes}
    names = {n["id"]: n["name"] for n in nodes}
    floor_h = phys_h(arch_planes["arch_floor"]["value_raw"])
    ceil_h = phys_h(arch_planes["arch_ceiling"]["value_raw"])

    by_pair = {}
    for e in edges:
        by_pair.setdefault(e["a"], []).append(e)
        by_pair.setdefault(e["b"], []).append(e)

    out = {}
    for n in nodes:
        oid = n["id"]
        A = boxes[oid]
        cands, partners, context = [], set(), []

        def add(partner, src, rel, text):
            cands.append({"partner": partner, "src": src, "rel": rel,
                          "text": text})
            partners.add(partner)

        def obj_metrics(bid):
            B = boxes[bid]
            c = A.bottom_h - B.top_h          # +: A's bottom above B's top
            frac = h_overlap(A, B) / A.base_area()
            iv = inter_volume(A, B) / min(A.volume(), B.volume())
            gap = box_gap(A, B)
            parts = []
            if abs(c) <= beneath_tol and frac > 0:
                parts.append(f"its top is {cm(abs(c))} "
                             f"{'below' if c >= 0 else 'above'} this "
                             f"object's bottom")
            elif c < -beneath_tol and (frac > 0 or iv > 0.005):
                # partner rises far above this object's bottom: overlap is
                # side-by-side / engulfing, NOT support from beneath --
                # the obj_001 plant-beside-bookshelf lesson (direction was
                # invisible and the model deduced "on a shelf inside")
                parts.append(f"its top is {abs(c):.2f} m ABOVE this "
                             f"object's bottom (boxes overlap side-by-side "
                             f"or nested, not stacked)")
            if frac > 0:
                fp = f"{frac * 100:.0f}% of this object's base footprint " \
                     f"is over the other's"
                for ax, i in (("x", 0), ("z", 2)):
                    w = min(A.mx[i], B.mx[i]) - max(A.mn[i], B.mn[i])
                    if 0 < w < 0.3 * A.size[i]:
                        b_center = (B.mn[i] + B.mx[i]) / 2
                        a_center = (A.mn[i] + A.mx[i]) / 2
                        side = "low" if b_center < a_center else "high"
                        fp += (f" — only a {cm(w)} strip along its "
                               f"{ax}_{side} edge")
                        break
                parts.append(fp)
            if iv > 0.005:
                parts.append(f"boxes interpenetrate {iv * 100:.0f}% of the "
                             f"smaller volume")
            if gap > 0:
                parts.append(f"box gap {cm(gap)}")
            return "; ".join(parts) if parts else "boxes touch"

        # 1) existing graph edges (all types = evidence)
        for e in by_pair.get(oid, []):
            other = e["b"] if e["a"] == oid else e["a"]
            if e["a"] != oid:                 # reverse edge = context only
                if e["type"] in SUPPORT_EDGE_TYPES:
                    context.append(f"{names.get(other, other)} ({other}) is "
                                   f"{e['type']} it")
                continue
            if other.startswith("arch_"):
                pl = arch_planes[other]
                if pl["axis"] == "y":
                    if other == "arch_floor":
                        d = A.bottom_h - floor_h
                        m = (f"bottom is {cm(abs(d))} "
                             f"{'above' if d >= 0 else 'below'} the floor")
                    else:
                        d = ceil_h - A.top_h
                        m = (f"top is {cm(abs(d))} "
                             f"{'below' if d >= 0 else 'above'} the ceiling")
                else:
                    g, face = wall_gap(A, pl)
                    m = (f"face {face} penetrates the wall plane {cm(-g)}"
                         if g < 0 else f"face {face} is {cm(g)} from the "
                         f"wall plane")
                add(other, "edge", e["type"],
                    f"{e['type']} {ARCH_LABEL[other]} ({other}) "
                    f"[graph edge]: {m}")
            else:
                add(other, "edge", e["type"],
                    f"{e['type']} {names.get(other, other)} "
                    f"({other}) [graph edge]: {obj_metrics(other)}")

        # 2) gravity/beneath scan: what lies under the bottom face
        for m in nodes:
            bid = m["id"]
            if bid == oid or bid in partners:
                continue
            B = boxes[bid]
            c = A.bottom_h - B.top_h
            frac = h_overlap(A, B) / A.base_area()
            if abs(c) <= beneath_tol and frac >= MIN_OVERLAP_FRAC:
                add(bid, "computed", "beneath",
                    f"beneath it: {names[bid]} ({bid}) "
                    f"[computed]: {obj_metrics(bid)}")
        if "arch_floor" not in partners:
            # ALWAYS offer the floor with its measured clearance (v1 lesson:
            # a 15 cm cutoff hid the floor from truncated-box bookshelves and
            # the model rightly complained) -- the number does the arguing.
            d = A.bottom_h - floor_h
            add("arch_floor", "computed", "floor",
                f"the floor (arch_floor) [computed]: bottom "
                f"is {cm(abs(d))} "
                f"{'above' if d >= 0 else 'below'} it")

        # 3) wall/ceiling proximity not already edged
        for aid, pl in arch_planes.items():
            if aid in partners or pl["axis"] == "y":
                continue
            g, face = wall_gap(A, pl)
            if g < WALL_NEAR:
                m = (f"face {face} penetrates the wall plane {cm(-g)}"
                     if g < 0 else f"face {face} is {cm(g)} from the wall")
                add(aid, "computed", "near-wall",
                    f"near {ARCH_LABEL[aid]} ({aid}) [computed]: {m}")
        if "arch_ceiling" not in partners:
            d = ceil_h - A.top_h
            if d <= WALL_NEAR:
                add("arch_ceiling", "computed", "near-ceiling",
                    f"near the ceiling (arch_ceiling) [computed]: "
                    f"top is {cm(abs(d))} "
                    f"{'below' if d >= 0 else 'above'} it")

        # 4) near-contact objects the graph has no edge for
        for m in nodes:
            bid = m["id"]
            if bid == oid or bid in partners:
                continue
            g = box_gap(A, boxes[bid])
            if g < NEAR_SCAN:
                add(bid, "computed", "near",
                    f"near {names[bid]} ({bid}) [computed]: "
                    f"box gap {cm(g)}")

        out[oid] = {"cands": cands, "partners": partners, "context": context}
    return out


def crude_tiers(edges):
    """The viewer's crude rule (index.html:1200-1212), ported verbatim."""
    rank = {"floor": 3, "wall": 2, "ceiling": 1}
    tiers = {}
    for e in edges:
        if e["type"] not in SUPPORT_EDGE_TYPES:
            continue
        if not str(e["b"]).startswith("arch_"):
            continue
        t = ("floor" if e["b"] == "arch_floor"
             else "ceiling" if e["b"] == "arch_ceiling" else "wall")
        if e["a"] not in tiers or rank[t] > rank[tiers[e["a"]]]:
            tiers[e["a"]] = t
    return tiers


# ------------------------------------------------------------------- LLM
def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)  # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd, model):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[supported_by] claude.exe not on PATH")
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


def item_block(i, node, cand, desc):
    b = Box(node)
    s = node["geometry"]["size"]
    head = (f"ITEM {i} · {node['id']} \"{node['name']}\" — size "
            f"{s[0]:.2f}×{s[2]:.2f}×{s[1]:.2f} m (w×d×h), bottom "
            f"{b.bottom_h:.2f} m above floor, top {b.top_h:.2f} m.")
    if desc:
        head += f"\n  Looks like: {desc}"
    if cand["context"]:
        head += "\n  Context: " + "; ".join(cand["context"][:6]) + "."
    body = "\n".join(f"  [c{i + 1}] {c['text']}"
                     for i, c in enumerate(cand["cands"])) \
        or "  (no candidate relations found within tolerance)"
    return head + "\n  Candidate relations (measured):\n" + body


def parse_response(text, want):
    """want: {oid: allowed_partner_ids}. Returns {oid: verdict}."""
    m = re.search(r"```(?:json)?\s*(\[.*?\])\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        i = text.find("[")
        if i >= 0:
            try:
                arr, _ = json.JSONDecoder().raw_decode(text[i:])
                raw = json.dumps(arr)
            except ValueError:
                raw = None
    if raw is None:
        return {}
    try:
        arr = json.loads(raw)
    except ValueError:
        return {}
    good = {}
    if not isinstance(arr, list):
        return good
    for e in arr:
        if not isinstance(e, dict) or e.get("id") not in want:
            continue
        oid, allowed = e["id"], want[e["id"]]
        opts, ok = [], True
        for o in e.get("options") or []:
            if not isinstance(o, dict):
                ok = False
                break
            sup, how = o.get("supporter"), o.get("how")
            try:
                conf = round(min(1.0, max(0.0, float(o.get("confidence")))), 2)
            except (TypeError, ValueError):
                ok = False
                break
            reason = o.get("reason")
            if sup not in allowed or how not in HOW_VOCAB \
                    or not isinstance(reason, str) or not reason.strip():
                ok = False
                break
            opt = {"supporter": sup, "how": how, "confidence": conf,
                   "reason": reason.strip()}
            ag = o.get("against")
            if ag:
                if ag not in allowed:
                    ok = False
                    break
                opt["against"] = ag
            opts.append(opt)
        if not ok:
            continue
        v = {"options": opts}
        if e.get("none_plausible"):
            v["none_plausible"] = True
            v["reason"] = str(e.get("reason", "")).strip()
        if not opts and not v.get("none_plausible"):
            continue                       # empty without the flag = malformed
        good[oid] = v
    return good


# ------------------------------------------------------------------ main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--batch-size", type=int, default=BATCH_SIZE)
    ap.add_argument("--no-llm", action="store_true",
                    help="deterministic pass only; supported_by stays null")
    ap.add_argument("--beneath-tol", type=float, default=BENEATH_TOL,
                    help="beneath-scan window in m (default %(default)s)")
    ap.add_argument("--smoke", action="store_true",
                    help="one batch, print, no write")
    ap.add_argument("--fresh", action="store_true", help="ignore cache")
    args = ap.parse_args()

    gpath = paths.scene_dir(args.scene) / "scene_graph.json"
    graph = json.loads(gpath.read_text(encoding="utf-8"))
    res = graph["resolved"]
    nodes = res["nodes"]
    edges = res["edges"]
    arch_planes = {n["id"]: n["geometry"]["plane"] for n in graph["nodes"]
                   if n["id"].startswith("arch_")}
    jdesc = {n["id"]: (n.get("appearance") or {}).get("description")
             for n in graph["judged"]["nodes"]}

    cdir = paths.compose_dir(args.scene)
    cdir.mkdir(parents=True, exist_ok=True)
    cache_path = cdir / "supported_by_cache.json"
    cache = (json.loads(cache_path.read_text(encoding="utf-8"))
             if cache_path.exists() and not args.fresh else {})

    # crude rule port -- must match the viewer's counts before we diverge
    crude = crude_tiers(edges)
    tc = {"floor": 0, "wall": 0, "ceiling": 0}
    for t in crude.values():
        tc[t] += 1
    print(f"[supported_by] crude touch rule (viewer port): "
          f"{len(crude)} anchors = floor {tc['floor']} / wall {tc['wall']} "
          f"/ ceiling {tc['ceiling']} -- verify against the :8321 header")

    cands = build_candidates(nodes, arch_planes, edges,
                             beneath_tol=args.beneath_tol)
    n_lines = sum(len(c["cands"]) for c in cands.values())
    print(f"[supported_by] deterministic pass: {len(nodes)} objects, "
          f"{n_lines} candidate lines "
          f"({n_lines / max(len(nodes), 1):.1f}/object)")

    # evidence hash per object = prompt version + its item text
    blocks = {n["id"]: item_block(0, n, cands[n["id"]],
                                  jdesc.get(n["id"])) for n in nodes}
    ehash = {oid: hashlib.md5((PROMPT_VERSION + b).encode()).hexdigest()
             for oid, b in blocks.items()}

    verdicts = {}
    for oid in blocks:
        c = cache.get(oid)
        if c and c.get("evidence_hash") == ehash[oid]:
            verdicts[oid] = c["verdict"]

    todo = [n for n in nodes if n["id"] not in verdicts]
    if args.no_llm:
        print(f"[supported_by] --no-llm: {len(todo)} objects left "
              f"unresolved (NEEDS_REVIEW)")
        todo_ids = {n["id"] for n in todo}
    else:
        print(f"[supported_by] {len(verdicts)} cached, {len(todo)} to judge "
              f"(model {args.model}, prompt v{PROMPT_VERSION}, "
              f"batch {args.batch_size})")
        batches = [todo[i:i + args.batch_size]
                   for i in range(0, len(todo), args.batch_size)]
        if args.smoke:
            batches = batches[:1]
        for bi, batch in enumerate(batches):
            want = {n["id"]: cands[n["id"]]["partners"] for n in batch}
            items = "\n\n".join(item_block(i + 1, n, cands[n["id"]],
                                           jdesc.get(n["id"]))
                                for i, n in enumerate(batch))
            got = {}
            for attempt, firm in enumerate(("", FIRM_PREFIX)):
                try:
                    out = call_claude(TEMPLATE.format(firm=firm, items=items),
                                      cdir, args.model)
                except (RuntimeError, subprocess.TimeoutExpired) as ex:
                    print(f"[supported_by] batch {bi}: call failed: {ex}")
                    break
                got = parse_response(out, want)
                if got:
                    break
            print(f"[supported_by] batch {bi}: {len(got)}/{len(batch)} "
                  f"verdicts")
            if args.smoke:
                print(json.dumps(got, indent=1)[:3000])
                return
            for oid, v in got.items():
                verdicts[oid] = v
                cache[oid] = {"evidence_hash": ehash[oid], "verdict": v,
                              "model": args.model, "date": str(date.today())}
            cache_path.write_text(json.dumps(cache, indent=1),
                                  encoding="utf-8")
        todo_ids = {n["id"] for n in nodes if n["id"] not in verdicts}

    # assemble the layer
    objects = []
    delta = {"demoted": [], "added": [], "kept": 0}
    for n in nodes:
        oid = n["id"]
        v = verdicts.get(oid)
        sb = v["options"] if v else None
        top = sb[0] if sb else None
        anchor = None
        if top and str(top["supporter"]).startswith("arch_"):
            anchor = ("floor" if top["supporter"] == "arch_floor"
                      else "ceiling" if top["supporter"] == "arch_ceiling"
                      else "wall")
        ct = crude.get(oid)
        if ct and not anchor and sb is not None:
            delta["demoted"].append(oid)
        elif not ct and anchor:
            delta["added"].append(oid)
        elif ct and anchor:
            delta["kept"] += 1
        clist = cands[oid]["cands"]
        rec = {"id": oid, "name": n["name"],
               "candidates": [f"[c{i + 1}] {c['text']}"
                              for i, c in enumerate(clist)],
               "supported_by": sb,
               "anchor": anchor, "crude_tier": ct,
               "status": "ok" if v else "NEEDS_REVIEW"}
        if v and v.get("none_plausible"):
            rec["none_plausible"] = True
            rec["flag_reason"] = v.get("reason", "")
        objects.append(rec)

    layer = {
        "scene": args.scene, "built": str(date.today()),
        "generated_by": "compose/supported_by.py",
        "model": None if args.no_llm else args.model,
        "prompt_version": PROMPT_VERSION,
        "note": ("supported_by SUPERSEDES the geometric contact edges "
                 "(ON/IN/IN_WALL/ATTACHED/NEAR), which remain in the graph "
                 "as evidence. anchor = top option's supporter is arch_*. "
                 "Boxes verbatim; graph untouched."),
        "crude_check": {"anchors": len(crude), **tc},
        "counts": {"objects": len(nodes),
                   "resolved": sum(1 for o in objects if o["status"] == "ok"),
                   "needs_review": sum(1 for o in objects
                                       if o["status"] == "NEEDS_REVIEW"),
                   "multi_option": sum(1 for o in objects
                                       if o["supported_by"]
                                       and len(o["supported_by"]) > 1),
                   "none_plausible": sum(1 for o in objects
                                         if o.get("none_plausible"))},
        "delta_vs_crude": delta,
        "objects": objects,
    }
    opath = cdir / "supported_by.json"
    opath.write_text(json.dumps(layer, indent=1), encoding="utf-8")
    print(f"[supported_by] wrote {opath}")
    print(f"[supported_by] counts: {json.dumps(layer['counts'])}")
    print(f"[supported_by] delta vs crude: kept {delta['kept']}, demoted "
          f"{delta['demoted']}, added {delta['added']}")
    if todo_ids:
        print(f"[supported_by] NEEDS_REVIEW ({len(todo_ids)}): "
              f"{sorted(todo_ids)[:12]}{' ...' if len(todo_ids) > 12 else ''}")


if __name__ == "__main__":
    main()
