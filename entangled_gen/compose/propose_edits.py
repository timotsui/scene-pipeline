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

ADD proposals -- v3 (user design 08-02): ONE batched call, whole room
as context, but the reply is FORCED PER ITEM -- every object and arch
node answers "nothing missing" (the normal case) or names an
expected-but-absent connection, plus one final "room" slot for
room-level gaps that fit no single item. v2's room-level brainstorm
rotated its proposal tail across runs; the per-item form gave an
identical stable core (expB, 3 runs). The loop experiment (expC: adds
folded back into the inventory) DIVERGED -- phantom items raised
confidence in their complements and grew accessories -- so adds are
PRIORS, never observations: an add enters the scene state only after
a pixel check at screening confirms it. Every add still declares
support (derived from its anchor); anchor="room" marks the scan
channel. K-RUN UNION (canon, user 08-02): the add pass runs K times
(--add-runs, default 3) INSIDE one invocation; the union ships with
per-proposal "seen k/K" counts. Stability is EVIDENCE for screening,
never a filter here, and there is no cache and no human picking --
the pipeline is fully automatic by the prime directive.

STEP 3, SIZE + BOX -- v4 (user design 08-02): S3 hands screening a
COMPLETE graph delta -- every add leaves here with a concrete box.
3a ONE batched sizing call whose reference frame is the scene's own
measured object sizes (the room is not exactly metric, ~0.8x real on
bedroom_marble; textbook cm would oversize everything). 3b pure-code
placement: free-space scan of the anchor's top face (or floor / wall
plane) against sibling footprints, nearest the "where" referent;
both orientations tried; shrink-to-fit FLAGGED (clamped), never
silent. Every add box carries box_source="estimated_prior" so
invented geometry can never masquerade as measured. Screening rules
on entry; nothing here touches the graph.

Degrade: --no-llm (or call failure) -> delete candidates written with
status CANDIDATE (not confirmed), adds empty. Nothing fabricated.

Output: out/<scene>/compose/edit_proposals.json -- PROPOSALS ONLY.

Run:
  python compose/propose_edits.py --scene bedroom_marble --no-llm  # aggregate only
  python compose/propose_edits.py --scene bedroom_marble
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
PROMPT_VERSION = "4"
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
that are small, occluded, or low-contrast. Below: the room dimensions \
and every item with its CONNECTIONS -- what it rests on, and \
everything that rests on / hangs on / sits inside it.

For EVERY item listed (architecture included), answer: is anything \
OBVIOUSLY expected to be connected to THIS item but absent? Use the \
whole room as context -- never propose something that already exists \
elsewhere in the inventory, and never propose decor filler. Be \
CONSERVATIVE: most items should get an empty answer. Only everyday \
items whose absence would make the composed room read as wrong. \
Anchor each proposal to the item it would physically rest on or hang \
from -- not a merely associated item.

The LAST entry is "room": a whole-room scan. Considering everything \
above, is anything expected in a room like this that is absent and \
did NOT fit any single item's answer? Same conservatism applies.

Return ONE fenced ```json block, a JSON ARRAY with EXACTLY one entry \
per item, same order as listed:
{{"id": "<item id>", "adds": []}}  -- nothing missing (the normal case)
or {{"id": "<item id>", "adds": [{{"name": "<lowercase item>", \
"relation": "on_top|inside|mounted_on|hangs_from|near", \
"where": "one short phrase", "confidence": 0.0-1.0, \
"reason": "one sentence"}}]}}
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


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--no-llm", action="store_true",
                    help="aggregate delete candidates only; no adds")
    ap.add_argument("--add-runs", type=int, default=3,
                    help="K union runs of the add pass (canon: 3)")
    args = ap.parse_args()

    cdir = paths.compose_dir(args.scene)
    gpath = paths.scene_dir(args.scene) / "scene_graph.json"
    graph = json.loads(gpath.read_text(encoding="utf-8"))
    res = graph["resolved"]
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
    deletes, adds, petitions = [], [], []
    add_answered = None   # v3 add pass: per-item reply coverage
    if args.no_llm:
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
        # add proposals -- v3 (user design 08-02, "experiment B2"): the
        # whole room is context, but the REPLY IS FORCED PER ITEM --
        # every object and arch node answers "nothing to add" (normal)
        # or names an expected-but-absent connection, then one final
        # "room" slot scans for room-level gaps that fit no single item.
        # Empirical basis (expB/expC, bedroom_marble): per-item slots
        # gave an identical stable core across runs where the old
        # room-level brainstorm rotated its tail; the loop experiment
        # (adds folded back into the inventory) DIVERGED -- invented
        # items raised confidence in their complements (phantom keyboard
        # -> mouse 0.75) and grew accessories (mirror on the invented
        # wardrobe). Hence the standing rule: these are PRIORS, and an
        # add may enter the scene state only after a pixel check at
        # screening confirms it. anchor="room" marks the scan channel.
        parent, kids = {}, {}
        for o in sbL["objects"]:
            top = (o.get("supported_by") or [{}])[0]
            sup, how = top.get("supporter"), top.get("how")
            if not sup:
                continue
            parent[o["id"]] = f'{how} {names.get(sup, sup)} ({sup})'
            kids.setdefault(sup, []).append(
                f'{names.get(o["id"], "?")} ({o["id"]}, {how})')
        shell = {n["id"]: n["geometry"]["plane"]["value_raw"]
                 for n in graph["nodes"] if n["id"].startswith("arch_")}
        dims = (f'room ~{abs(shell["arch_wall_x_low"] - shell["arch_wall_x_high"]):.1f} x '
                f'{abs(shell["arch_wall_z_low"] - shell["arch_wall_z_high"]):.1f} m, '
                f'height {abs(shell["arch_ceiling"] - shell["arch_floor"]):.1f} m')
        arch_ids = [n["id"] for n in graph["nodes"]
                    if n["id"].startswith("arch_")]
        lines = [dims, "", "ITEMS (id, name, connections):"]
        order = []
        for o in sbL["objects"]:
            oid = o["id"]
            order.append(oid)
            k = kids.get(oid)
            lines.append(
                f'- {oid} "{names.get(oid, "?")}" -- rests: '
                f'{parent.get(oid, "(unresolved)")}'
                + (f'; holds: {"; ".join(k)}' if k else ''))
        for aid in arch_ids:
            order.append(aid)
            k = kids.get(aid) or []
            label = aid.replace("arch_", "").replace("_", " ")
            lines.append(f'- {aid} [{label}] -- holds {len(k)}: '
                         + ("; ".join(k) if k else "(nothing)"))
        order.append("room")
        lines.append('- room [the whole room -- final scan, '
                     'see instructions]')
        def support_of(anchor):
            if anchor.startswith("obj_"):
                return f"on:{anchor}"
            if anchor.startswith("arch_wall"):
                return "wall"
            if anchor == "arch_ceiling":
                return "ceiling"
            return "floor"   # arch_floor + the room-scan channel

        # K-RUN UNION (canon, user 08-02): the add pass runs K times in
        # THIS invocation and the union ships with per-proposal seen
        # counts -- stability is EVIDENCE handed to screening, never a
        # filter here. Fully automatic: no cache, no human picks.
        add_answered = []
        sightings = []
        runs_done = 0
        for r in range(args.add_runs):
            got = None
            for firm in ("", FIRM_PREFIX):
                try:
                    out = call_claude(
                        T_ADD.format(firm=firm,
                                     inventory="\n".join(lines)),
                        cdir, args.model)
                except (RuntimeError, subprocess.TimeoutExpired) as ex:
                    print(f"[propose_edits] add run {r + 1} failed: {ex}")
                    break
                got = parse_array(out)
                if got is not None:
                    break
            if got is None:
                continue
            runs_done += 1
            by_item = {e.get("id"): e for e in got if isinstance(e, dict)}
            add_answered.append(
                f"{sum(1 for o in order if o in by_item)}/{len(order)}")
            for oid in order:   # anchor comes from list position,
                for a in (by_item.get(oid, {}).get("adds") or []):
                    if not isinstance(a, dict):
                        continue
                    name = a.get("name")
                    if not isinstance(name, str) or not name.strip():
                        continue
                    sightings.append({
                        "anchor": oid,
                        "name": name.strip().lower(),
                        "relation": str(a.get("relation", "")).strip(),
                        "where": str(a.get("where", "")).strip(),
                        "confidence": conf_of(a.get("confidence")),
                        "reason": str(a.get("reason", "")).strip()})
        union = {}
        for s in sightings:
            union.setdefault((s["name"], s["anchor"]), []).append(s)
        for (nm, anc), ss in union.items():
            best = max(ss, key=lambda x: x["confidence"])
            adds.append({
                "name": nm, "support": support_of(anc),
                "anchor": anc, "anchor_name": names.get(anc, anc),
                "relation": best["relation"], "where": best["where"],
                "confidence": round(sum(x["confidence"] for x in ss)
                                    / len(ss), 2),
                "confidence_max": best["confidence"],
                "seen": f"{len(ss)}/{runs_done}",
                "reason": best["reason"]})
        adds.sort(key=lambda a: (-int(a["seen"].split("/")[0]),
                                 -a["confidence"]))

        # ---- STEP 3: size + box (v4, user design 08-02) -------------
        # 3a ONE batched sizing call: the scene's own measured sizes are
        # the reference frame (the room is not exactly metric -- ~0.8x
        # real scale on bedroom_marble), so new items are sized
        # consistently with their neighbors, never from textbook cm.
        # 3b pure-code placement: free-space scan on the anchor surface
        # (or floor / wall plane), nearest the "where" referent; shrink-
        # to-fit is flagged, never silent. box_source=estimated_prior
        # marks invented geometry forever.
        if adds:
            boxes = {n["id"]: n["geometry"]
                     for n in graph["resolved"]["nodes"]}
            parent_id = {}
            for o in sbL["objects"]:
                topt = (o.get("supported_by") or [{}])[0]
                if topt.get("supporter"):
                    parent_id[o["id"]] = topt["supporter"]
            ref_lines = [
                f'  {oid} "{names.get(oid, "?")}": '
                f'{boxes[oid]["size"][0]:.2f} x {boxes[oid]["size"][2]:.2f}'
                f' x {boxes[oid]["size"][1]:.2f}'
                for oid in sorted(boxes)]
            item_lines = []
            for i, a in enumerate(adds, 1):
                anc = a["anchor"]
                if anc in boxes:
                    g = boxes[anc]
                    actx = (f'anchor {a["anchor_name"]} ({anc}) footprint '
                            f'{g["size"][0]:.2f} x {g["size"][2]:.2f} m')
                else:
                    actx = f'anchor {anc} (architecture)'
                item_lines.append(
                    f'ITEM {i}: {a["name"]} -- {a["relation"] or "on"} '
                    f'{actx}; where: {a["where"] or "-"}')
            sgot = None
            for firm in ("", FIRM_PREFIX):
                try:
                    out = call_claude(
                        T_SIZE.format(firm=firm,
                                      reference="\n".join(ref_lines),
                                      items="\n".join(item_lines)),
                        cdir, args.model)
                except (RuntimeError, subprocess.TimeoutExpired) as ex:
                    print(f"[propose_edits] sizing pass failed: {ex}")
                    break
                sgot = parse_array(out)
                if sgot is not None and len(sgot) == len(adds):
                    break
                sgot = None

            shell_ids = {n["id"] for n in graph["nodes"]
                         if n["id"].startswith("arch_")}
            floor_y = shell["arch_floor"]
            xs = sorted((shell["arch_wall_x_low"],
                         shell["arch_wall_x_high"]))
            zs = sorted((shell["arch_wall_z_low"],
                         shell["arch_wall_z_high"]))
            room = (xs[0] + 0.05, zs[0] + 0.05, xs[1] - 0.05, zs[1] - 0.05)
            floor_rects = [_footprint(g) for oid, g in boxes.items()
                           if g["aabb_min"][1] < floor_y + 0.5]

            def referent_of(a, placed):
                text = (a["where"] + " " + a["reason"]).lower()
                cands = [(len(nm), oid) for oid, nm in
                         ((i_, names.get(i_, "").lower())
                          for i_ in boxes) if nm and nm in text]
                cands += [(len(p["name"]), p["id"]) for p in placed
                          if p["name"] in text]
                return max(cands)[1] if cands else None

            placed = []   # add records that already got boxes (referents)
            pboxes = {}   # add id -> box
            for i, a in enumerate(adds):
                a["id"] = f"add_{i+1:03d}"
                a["box_source"] = "estimated_prior"
                sz = (sgot or [{}] * len(adds))[i]
                sm = sz.get("size_m") if isinstance(sz, dict) else None
                if (not isinstance(sm, list) or len(sm) != 3
                        or not all(isinstance(v, (int, float)) and v > 0
                                   for v in sm)):
                    a["placement"] = {"failed": "no size from sizing pass"}
                    continue
                w, d, h = float(sm[0]), float(sm[1]), float(sm[2])
                a["size_m"] = [round(w, 3), round(d, 3), round(h, 3)]
                ref = referent_of(a, placed)
                allb = dict(boxes)
                allb.update(pboxes)
                sup = a["support"]
                spot = None
                if sup.startswith("on:") and sup[3:] in boxes:
                    anc = sup[3:]
                    g = boxes[anc]
                    bounds = _footprint(g)
                    obst = [_footprint(allb[k]) for k in allb
                            if parent_id.get(k) == anc or
                            (k in pboxes and adds[int(k[4:]) - 1]
                             .get("support") == sup)]
                    tgt = ((allb[ref]["center"][0], allb[ref]["center"][2])
                           if ref and ref in allb else
                           (g["center"][0], g["center"][2]))
                    spot = _find_spot(bounds, w, d, obst, tgt)
                    ybase, method = g["aabb_max"][1], f"on_top:{anc}"
                elif sup == "floor":
                    tgt = ((allb[ref]["center"][0], allb[ref]["center"][2])
                           if ref and ref in allb else
                           ((room[0] + room[2]) / 2,
                            (room[1] + room[3]) / 2))
                    obst = floor_rects + [_footprint(b)
                                          for b in pboxes.values()]
                    spot = _find_spot(room, w, d, obst, tgt)
                    ybase, method = floor_y, "floor"
                elif sup == "wall" and a["anchor"] in shell_ids:
                    plane = shell[a["anchor"]]
                    t = 0.1   # embedded slab thickness
                    if ref and ref in allb:
                        rc = allb[ref]
                        cy = rc["center"][1]
                        other = rc["center"][2] if "_x_" in a["anchor"] \
                            else rc["center"][0]
                    else:
                        cy = floor_y + 1.4
                        other = (room[1] + room[3]) / 2 \
                            if "_x_" in a["anchor"] else \
                            (room[0] + room[2]) / 2
                    if "_x_" in a["anchor"]:
                        box = _mk_box(plane, other, t, w, cy - h / 2, h)
                    else:
                        box = _mk_box(other, plane, w, t, cy - h / 2, h)
                    a["box"] = box
                    a["placement"] = {"method": f"wall:{a['anchor']}",
                                      "referent": ref, "clamped": False}
                    pboxes[a["id"]] = box
                    placed.append(a)
                    continue
                else:
                    a["placement"] = {"failed":
                                      f"no placement rule for {sup}"}
                    continue
                if spot is None:
                    a["placement"] = {"failed": "no free spot found",
                                      "method": method, "referent": ref}
                    continue
                x, z, fw, fd, clamped = spot
                box = _mk_box(x, z, fw, fd, ybase, h)
                a["box"] = box
                a["placement"] = {"method": method, "referent": ref,
                                  "clamped": clamped}
                pboxes[a["id"]] = box
                placed.append(a)

    layer = {
        "scene": args.scene, "built": str(date.today()),
        "generated_by": "compose/propose_edits.py",
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
                   "add_runs": None if args.no_llm else args.add_runs,
                   "add_items_answered": add_answered,
                   "reopen_petitions": len(petitions)},
        "deletes": deletes,
        "adds": adds,
        "reopen_petitions": petitions,
    }
    opath = cdir / "edit_proposals.json"
    opath.write_text(json.dumps(layer, indent=1), encoding="utf-8")
    print(f"[propose_edits] wrote {opath}")
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
        print(f"    ADD {a['name']} <- {a.get('anchor')} "
              f"({a.get('anchor_name')}) [seen {a.get('seen', '?')}, "
              f"conf {a['confidence']}]: {geo}")
    for p in petitions:
        print(f"    PETITION {p['pair'][0]}+{p['pair'][1]} "
              f"({p['names'][0]}/{p['names'][1]}) [{p['confidence']}]: "
              f"{p['evidence'][:100]}")


if __name__ == "__main__":
    main()
