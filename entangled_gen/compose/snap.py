"""
STEP 3 COMPOSE+LOOP, 3.2 PHYSICAL / PH1 v1 -- SNAP + BOX ADJUDICATION.

v0 (R4 PASSED): deterministic scripted snap, zero LLM -- corrections that
make each TOP supported_by option physically exact; LARGE deltas = suspect
evidence. v1 (user design 08-01 late, after the curtain-thickness
diagnosis): the scripted snap becomes a PROPOSAL. Clean boxes snap as
before. FLAGGED boxes -- LARGE corrections on anchor-class objects
(arch-supported or >= DOCKET_MIN_DIM) plus every judge suspect_box
pointer -- go to ONE batched agent call that picks from a TYPED MENU per
case (lesson from the reverted shrink experiment: the agent chooses, code
executes; no freehand resizing):

  ADOPT_REFIT_AND_SNAP  adopt the code-computed refit box, then snap
  SNAP_AS_IS            the scripted proposal was right; snap unchanged box
  NO_SNAP               support attribution itself in doubt -> don't bake
                        it in; leave the box where observed
  DEFER_TO_SURGERY      evidence conflicting/insufficient -> PH3 work order

REFIT (pure code, mechanical): re-fuse the box from its raw per-view lift
measurements (provenance chain: resolved members -> manifest members ->
lift_pool<sfx>.json), rejecting per-bound outliers by MAD -- the curtain
mechanism: one bleeding mask's far bound survives the q=0.05 fusion at
small n; the refit drops it and re-measures from the member majority.

Ordering: adjudication runs AFTER a scripted pass A (its deltas build the
docket), then pass B re-snaps everything with adopted refits substituted
and held boxes pinned, so dependents land on final supporter tops.

Degrade (--no-llm or call failure): pass-A scripted behavior verbatim,
docket cases marked status CANDIDATE -- exactly v0's output, never a
guessed verdict. Output out/<scene>/compose/snap.json -- ANALYZER LAYER
ONLY: the graph and its boxes stay verbatim; refit/snapped boxes exist
only here.

Run:
  python compose/snap.py --scene bedroom_marble            # full v1
  python compose/snap.py --scene bedroom_marble --no-llm   # v0 behavior
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
from collections import Counter
from datetime import date
from pathlib import Path
from statistics import median

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

MODEL = "sonnet"
CALL_TIMEOUT_S = 480
ADJ_PROMPT_VERSION = "2"  # v2 (08-02, R10b structural fixes): explicit
                          # majority decision rule (magnitude alone never
                          # a reason to defer); docket frames refits as
                          # "k of n measurements agree"; judge flags
                          # arrive with their direction stated. Verdict
                          # CACHE (snap_cache.json, evidence-keyed) +
                          # USER RULINGS (snap_rulings.json) added --
                          # snap was the only judged module re-rolling
                          # verdicts every run (the curtain flip).
LARGE_CORRECTION = 0.10   # m -- flag threshold: box vs verdict disagree
TOP_TOL = 0.35            # m -- "near the supporter's top" window
CHAIN_MAX = 12
# docket rule: LARGE + support involves ARCHITECTURE (top pick or a live
# alternate -- catches the AC's wall-vs-bookshelf doubt), plus every judge
# suspect_box pointer. On-object dependents stay advisory (R4 ruling:
# no exact snap target until real meshes).
DOCKET_CAP = 12
REFIT_MIN_MEMBERS = 3     # MAD needs a majority to exist
REFIT_MAD_K = 3.5
REFIT_ABS_TOL = 0.05      # m -- outlier floor + minimum meaningful change

WALL_AXIS = {"x": 0, "z": 2}
BOUND_NAMES = ("x_lo", "x_hi", "y_lo", "y_hi", "z_lo", "z_hi")

T_ADJ = """\
{firm}You are adjudicating SUSPECT 3D bounding boxes in a reconstructed \
indoor scene. Each numbered case below is an object whose box and its own \
support verdict disagree (it would need a large move to touch its \
support), or that a prior judge pass flagged as oversized. For each case \
pick ONE action:

- ADOPT_REFIT_AND_SNAP: adopt the REFIT box (shown), then snap. The refit \
is mechanical: the box re-measured from the majority of its per-view \
measurements after dropping statistical outliers -- it is safe when the \
evidence says one bad measurement inflated the box.
- SNAP_AS_IS: the box is fine (or no refit exists); the scripted snap \
move is the right correction.
- NO_SNAP: the SUPPORT ATTRIBUTION itself is in doubt (a close alternate \
supporter exists) -- snapping would bake in a possibly-wrong answer. \
Leave the object where observed.
- DEFER_TO_SURGERY: evidence is conflicting or insufficient; leave the \
box AND position untouched as a work order for mesh-time box surgery.

Decision rule for refits: what matters is the MAJORITY, not the \
magnitude. A refit backed by a large majority of per-view measurements \
that agree with each other (e.g. 7 of 8) is STRONG evidence, no matter \
how big the size correction is -- the size of the correction is NEVER \
by itself a reason to doubt the refit. Thin evidence means few TOTAL \
measurements (2-3) or a split vote (4 vs 3), not a large change. \
Prefer DEFER_TO_SURGERY only when the evidence is genuinely \
conflicting or too sparse to call.

Return ONE fenced ```json block, a single JSON OBJECT:
{{"verdicts": [EXACTLY one per case, same order: {{"id": "<the id \
given>", "verdict": "ADOPT_REFIT_AND_SNAP|SNAP_AS_IS|NO_SNAP|\
DEFER_TO_SURGERY", "confidence": 0.0-1.0, "reason": "one sentence"}}]}}
Output ONLY the fenced JSON block.

{cases}"""

FIRM_PREFIX = ("Your previous response was malformed. This time output "
               "ONLY one fenced ```json code block containing exactly "
               "the JSON structure requested, no prose.\n\n")


def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)  # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd, model):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[snap] claude.exe not on PATH")
    r = subprocess.run([exe, "-p", "--model", model], input=prompt,
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


def phys_h(y_raw):
    """Physical height (m, up positive) of a raw y (up = -y frame)."""
    return -y_raw


def load_pool_members(graph, scene):
    """oid -> list of raw per-view lift measurements, via the provenance
    chain resolved.members -> manifest.members -> lift_pool<sfx>. Returns
    {} on any missing link (refit silently unavailable -> degrade)."""
    rec_nodes = {n["id"]: n for n in graph["nodes"]}
    man_name = None
    for n in graph["nodes"]:
        man_name = (n.get("provenance") or {}).get("manifest")
        if man_name:
            break
    if not man_name:
        return {}
    man_path = paths.scene_dir(scene) / man_name
    m = re.search(r"pano2([a-z]*)_", man_name)
    pool_path = (paths.scene_dir(scene) / "rig_sp0"
                 / f"lift_pool{m.group(1) if m else ''}.json")
    if not man_path.exists() or not pool_path.exists():
        return {}
    man = {o["id"]: o for o in json.loads(
        man_path.read_text(encoding="utf-8"))["objects"]}
    pool = json.loads(pool_path.read_text(encoding="utf-8"))["pool"]
    out = {}
    for n in graph["resolved"]["nodes"]:
        idxs = []
        for mid in (n.get("members") or [n["id"]]):
            idxs.extend((man.get(mid) or {}).get("members") or [])
        out[n["id"]] = [pool[i] for i in idxs if 0 <= i < len(pool)]
    return out


def refit_box(members, cur_mn, cur_mx):
    """Per-bound MAD outlier rejection over the raw per-view measurements,
    then union of the survivors (completes partial views; the rejected
    bleed can no longer own a face). Trusted bounds only, group_box-style
    fallback to all. Returns (mn, mx, changes, rejected) or None if too
    few members or nothing changes meaningfully."""
    if len(members) < REFIT_MIN_MEMBERS:
        return None
    mn, mx = list(cur_mn), list(cur_mx)
    changes, rejected = [], []
    for ax in range(3):
        for hi_side in (False, True):
            b = 2 * ax + (1 if hi_side else 0)
            vals = [(m["hi"][ax] if hi_side else m["lo"][ax], m)
                    for m in members if m["trust"][b]]
            if not vals:
                vals = [(m["hi"][ax] if hi_side else m["lo"][ax], m)
                        for m in members]
            if len(vals) < REFIT_MIN_MEMBERS:
                continue
            vs = [v for v, _ in vals]
            med = median(vs)
            mad = median([abs(v - med) for v in vs])
            thr = max(REFIT_MAD_K * mad, REFIT_ABS_TOL)
            kept = [v for v in vs if abs(v - med) <= thr]
            out = [(v, m) for v, m in vals if abs(v - med) > thr]
            if not kept or not out:
                continue
            new = max(kept) if hi_side else min(kept)
            old = mx[ax] if hi_side else mn[ax]
            if abs(new - old) < REFIT_ABS_TOL:
                continue
            if hi_side:
                mx[ax] = new
            else:
                mn[ax] = new
            changes.append({"bound": BOUND_NAMES[b],
                            "from": round(old, 3), "to": round(new, 3)})
            rejected.extend({"bound": BOUND_NAMES[b],
                             "view": m["view"], "score": m["score"],
                             "value": round(v, 3)} for v, m in out)
    if not changes:
        return None
    return mn, mx, changes, rejected


def snap_pass(boxes, top, planes, names, floor_h, ceil_h, holds=frozenset()):
    """The scripted snap (v0 logic, parameterized). holds = oids pinned in
    place (NO_SNAP / DEFER verdicts): recorded, never moved; dependents
    rest on their observed position."""
    def depth(oid, seen=None):
        seen = seen or set()
        if oid.startswith("arch_"):
            return 0
        if oid in seen or len(seen) > CHAIN_MAX:
            return 99                      # cycle guard (audit says none)
        t = top.get(oid)
        if not t:
            return 1
        return 1 + depth(t["supporter"], seen | {oid})

    order = sorted(boxes, key=lambda oid: (depth(oid), oid))
    snapped = {oid: {"mn": list(b["mn"]), "mx": list(b["mx"])}
               for oid, b in boxes.items()}
    records = []
    for oid in order:
        b = snapped[oid]
        t = top.get(oid)
        rec = {"id": oid, "name": names[oid],
               "how": t["how"] if t else None,
               "supporter": t["supporter"] if t else None,
               "delta_raw": [0.0, 0.0, 0.0], "magnitude_m": 0.0,
               "disposition": None}

        def shift(axis, d):
            b["mn"][axis] += d
            b["mx"][axis] += d
            rec["delta_raw"][axis] = round(d, 4)

        if oid in holds:
            rec["disposition"] = "HELD"
        elif t is None:
            rec["disposition"] = "UNRESOLVED"
        else:
            how, sup = t["how"], t["supporter"]
            if how in ("inside", "embedded_in"):
                rec["disposition"] = ("INSIDE_CONTAINER"
                                      if how == "inside" else "EMBEDDED")
            elif sup == "arch_floor":
                # bottom (max raw y) -> floor plane
                d = (-floor_h) - b["mx"][1]
                shift(1, d)
                rec["disposition"] = "SNAPPED_FLOOR"
            elif sup == "arch_ceiling":
                # top (min raw y) -> ceiling plane
                d = (-ceil_h) - b["mn"][1]
                shift(1, d)
                rec["disposition"] = "SNAPPED_CEILING"
            elif sup.startswith("arch_wall"):
                pl = planes[sup]
                ax = WALL_AXIS[pl["axis"]]
                inward = pl["inward_normal_raw"][ax]
                v = pl["value_raw"]
                d = (v - b["mn"][ax]) if inward > 0 else (v - b["mx"][ax])
                shift(ax, d)
                rec["disposition"] = "SNAPPED_WALL_FLUSH"
            else:
                # object supporter (rests_on / leans_on): supporter is
                # already snapped (ordering) -- its top in phys h
                sb2 = snapped.get(sup)
                if sb2 is None:
                    rec["disposition"] = "SUPPORTER_MISSING"
                else:
                    sup_top_h = phys_h(sb2["mn"][1])
                    bottom_h = phys_h(b["mx"][1])
                    if bottom_h < sup_top_h - TOP_TOL:
                        # bottom deep inside the supporter's span: the
                        # real surface is an interior board (bookshelf
                        # shelves) the box model doesn't carry
                        rec["disposition"] = "INTERNAL_SURFACE"
                    else:
                        d = (-sup_top_h) - b["mx"][1]
                        shift(1, d)
                        rec["disposition"] = "SNAPPED_ON_OBJECT"

        rec["magnitude_m"] = round(sum(x * x for x in
                                       rec["delta_raw"]) ** 0.5, 4)
        if oid not in holds and rec["magnitude_m"] > LARGE_CORRECTION:
            rec["flag"] = "LARGE_CORRECTION"
        rec["snapped_aabb"] = {"mn": [round(x, 4) for x in b["mn"]],
                               "mx": [round(x, 4) for x in b["mx"]]}
        records.append(rec)
    return records


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--no-llm", action="store_true",
                    help="pass-A scripted snap only (v0 behavior)")
    ap.add_argument("--fresh", action="store_true",
                    help="ignore the adjudication cache (rulings still "
                         "apply)")
    args = ap.parse_args()

    gpath = paths.scene_dir(args.scene) / "scene_graph.json"
    graph = json.loads(gpath.read_text(encoding="utf-8"))
    res = graph["resolved"]
    boxes = {n["id"]: {"mn": list(n["geometry"]["aabb_min"]),
                       "mx": list(n["geometry"]["aabb_max"])}
             for n in res["nodes"]}
    names = {n["id"]: n["name"] for n in res["nodes"]}
    planes = {n["id"]: n["geometry"]["plane"] for n in graph["nodes"]
              if n["id"].startswith("arch_")}
    floor_h = phys_h(planes["arch_floor"]["value_raw"])
    ceil_h = phys_h(planes["arch_ceiling"]["value_raw"])

    cdir = paths.compose_dir(args.scene)
    sbp = cdir / "supported_by.json"
    if not sbp.exists():
        raise SystemExit("[snap] no supported_by.json -- run "
                         "compose/supported_by.py first")
    sbL = json.loads(sbp.read_text(encoding="utf-8"))
    top, options = {}, {}
    for o in sbL["objects"]:
        sb = o.get("supported_by")
        if sb:
            top[o["id"]] = sb[0]
            options[o["id"]] = sb

    # judge suspect-box pointers riding in the resolved layer
    suspects = {}
    for sec in ("edges", "dropped_edges"):
        for e in res.get(sec, []):
            oid = e.get("suspect_box")
            if oid:
                suspects.setdefault(oid, []).append(
                    e.get("judge_reason") or e.get("reason") or "")

    # ---------------- pass A: scripted proposals -------------------------
    recs_a = snap_pass(boxes, top, planes, names, floor_h, ceil_h)
    by_id_a = {r["id"]: r for r in recs_a}

    # ---------------- docket: which flags earn the agent -----------------
    docket = []
    for r in recs_a:
        if r["id"] in suspects:
            docket.append(r["id"])
            continue
        if not r.get("flag"):
            continue
        if any(str(o.get("supporter", "")).startswith("arch_")
               or str(o.get("against", "")).startswith("arch_")
               for o in (options.get(r["id"]) or [])):
            docket.append(r["id"])
    docket = sorted(set(docket),
                    key=lambda i: -by_id_a[i]["magnitude_m"])
    if len(docket) > DOCKET_CAP:
        print(f"[snap] docket capped {len(docket)} -> {DOCKET_CAP}; "
              f"dropped: {docket[DOCKET_CAP:]}")
        docket = docket[:DOCKET_CAP]
    print(f"[snap] docket: {len(docket)} case(s): "
          + ", ".join(f"{i} ({names[i]})" for i in docket))

    # refit candidates (pure code) for every docket case
    pool_members = load_pool_members(graph, args.scene) if docket else {}
    refits = {}
    for oid in docket:
        mem = pool_members.get(oid) or []
        got = refit_box(mem, boxes[oid]["mn"], boxes[oid]["mx"])
        if got:
            refits[oid] = {"mn": got[0], "mx": got[1],
                           "changes": got[2], "rejected": got[3],
                           "n_members": len(mem)}

    # ---------------- case bodies (also the cache evidence key) ----------
    MENU = ("ADOPT_REFIT_AND_SNAP", "SNAP_AS_IS", "NO_SNAP",
            "DEFER_TO_SURGERY")
    case_body = {}
    for oid in docket:
        r = by_id_a[oid]
        b = boxes[oid]
        size = [round(m2 - m1, 3) for m1, m2 in zip(b["mn"], b["mx"])]
        alt = ""
        opts = options.get(oid) or []
        if len(opts) > 1:
            alt = ("\n  alternate supports: " + "; ".join(
                f'{o.get("how")} {o.get("supporter")} '
                f'({o.get("confidence")})' for o in opts[1:4]))
        if opts and opts[0].get("against"):
            alt += (f'\n  attribution doubt: the ruled-against '
                    f'candidate was {opts[0]["against"]} -- '
                    f'"{str(opts[0].get("reason", ""))[:200]}"')
        jt = ""
        if oid in suspects:
            # direction stated, not inferred (R10b: a verbatim flag got
            # read backwards -- cited as doubt AGAINST the refit)
            jt = ("\n  prior judge pass flagged THIS BOX as suspect "
                  "(i.e. the box itself is likely wrong/oversized -- "
                  "this SUPPORTS correcting the box): "
                  + " | ".join(s[:160] for s in suspects[oid] if s))
        rf = refits.get(oid)
        if rf:
            rsize = [round(m2 - m1, 3)
                     for m1, m2 in zip(rf["mn"], rf["mx"])]
            outliers = {(o["view"], o["score"]) for o in rf["rejected"]}
            agree = rf["n_members"] - len(outliers)
            rtxt = (f"\n  REFIT available: {agree} of {rf['n_members']} "
                    f"per-view measurements AGREE with each other; the "
                    f"box re-measured from that agreeing majority: size "
                    f"{size} -> {rsize}; "
                    + "; ".join(f'{c["bound"]} {c["from"]}->{c["to"]}'
                                for c in rf["changes"])
                    + " | the rejected outlier(s): "
                    + "; ".join(f'{o["view"]} {o["bound"]}={o["value"]} '
                                f'(score {o["score"]})'
                                for o in rf["rejected"][:4]))
        else:
            rtxt = ("\n  REFIT: none (too few measurements or no "
                    "meaningful change) -- ADOPT_REFIT_AND_SNAP invalid")
        case_body[oid] = (
            f'{oid} "{names[oid]}" -- size {size} m, top '
            f'support: {r["how"]} {r["supporter"]} '
            f'({(options.get(oid) or [{}])[0].get("confidence")}), '
            f'scripted snap: {r["disposition"]} move '
            f'{r["magnitude_m"]} m{alt}{jt}{rtxt}')

    # ---------------- rulings + cache + the agent call --------------------
    # precedence: USER RULING (snap_rulings.json, hand-written pins,
    # never expire) > CACHE (snap_cache.json, evidence-keyed like every
    # other judged module -- same evidence, same verdict, every run) >
    # one batched LLM call for what remains.
    rulings_path = cdir / "snap_rulings.json"
    rulings = (json.loads(rulings_path.read_text(encoding="utf-8"))
               if rulings_path.exists() else {})
    cache_path = cdir / "snap_cache.json"
    adj_cache = (json.loads(cache_path.read_text(encoding="utf-8"))
                 if cache_path.exists() and not args.fresh else {})
    ekey = {oid: hashlib.md5((ADJ_PROMPT_VERSION + case_body[oid])
                             .encode()).hexdigest() for oid in docket}

    adjudications = {}
    todo = []
    for oid in docket:
        ru = rulings.get(oid)
        if ru and ru.get("verdict") in MENU:
            verdict, note = ru["verdict"], ru.get("note")
            if verdict == "ADOPT_REFIT_AND_SNAP" and oid not in refits:
                verdict = "SNAP_AS_IS"
                note = (note or "") + " [refit unavailable -> SNAP_AS_IS]"
            adjudications[oid] = {"status": "USER_RULING",
                                  "verdict": verdict, "confidence": None,
                                  "reason": note, "note": None,
                                  "refit": refits.get(oid)}
            continue
        c = adj_cache.get(oid)
        if c and c.get("evidence_hash") == ekey[oid]:
            adjudications[oid] = {**c["adjudication"],
                                  "refit": refits.get(oid)}
            continue
        todo.append(oid)
    n_ruled = sum(1 for a in adjudications.values()
                  if a["status"] == "USER_RULING")
    print(f"[snap] adjudication: {n_ruled} user-ruled, "
          f"{len(adjudications) - n_ruled} cached, {len(todo)} to judge")

    if todo and not args.no_llm:
        cases = [f"CASE {i}: {case_body[oid]}"
                 for i, oid in enumerate(todo, 1)]
        got = None
        for firm in ("", FIRM_PREFIX):
            try:
                out = call_claude(T_ADJ.format(firm=firm,
                                               cases="\n\n".join(cases)),
                                  cdir, args.model)
            except (RuntimeError, subprocess.TimeoutExpired) as ex:
                print(f"[snap] adjudication call failed: {ex}")
                break
            got = parse_object(out)
            if got:
                break
        by_v = {v.get("id"): v for v in (got or {}).get("verdicts", [])
                if isinstance(v, dict)}
        for oid in todo:
            v = by_v.get(oid)
            ok = v and v.get("verdict") in MENU \
                and isinstance(v.get("reason"), str)
            verdict = v["verdict"] if ok else None
            note = None
            if verdict == "ADOPT_REFIT_AND_SNAP" and oid not in refits:
                verdict, note = "SNAP_AS_IS", "refit unavailable -> SNAP_AS_IS"
            adjudications[oid] = {
                "status": "JUDGED" if ok else "CANDIDATE",
                "verdict": verdict,
                "confidence": (round(min(1.0, max(0.0,
                               float(v.get("confidence", 0)))), 2)
                               if ok else None),
                "reason": v["reason"].strip() if ok else None,
                "note": note,
                "refit": refits.get(oid)}
            if ok:
                adj_cache[oid] = {
                    "evidence_hash": ekey[oid],
                    "adjudication": {k: adjudications[oid][k]
                                     for k in ("status", "verdict",
                                               "confidence", "reason",
                                               "note")},
                    "model": args.model, "date": str(date.today())}
        cache_path.write_text(json.dumps(adj_cache, indent=1),
                              encoding="utf-8")
    else:
        for oid in todo:
            adjudications[oid] = {"status": "CANDIDATE", "verdict": None,
                                  "confidence": None, "reason": None,
                                  "note": "--no-llm",
                                  "refit": refits.get(oid)}

    # ---------------- pass B: final snap with verdicts applied -----------
    boxes_b = {oid: {"mn": list(b["mn"]), "mx": list(b["mx"])}
               for oid, b in boxes.items()}
    holds = set()
    for oid, adj in adjudications.items():
        if adj["verdict"] == "ADOPT_REFIT_AND_SNAP":
            boxes_b[oid] = {"mn": list(adj["refit"]["mn"]),
                            "mx": list(adj["refit"]["mx"])}
        elif adj["verdict"] in ("NO_SNAP", "DEFER_TO_SURGERY"):
            holds.add(oid)
    records = snap_pass(boxes_b, top, planes, names, floor_h, ceil_h,
                        holds=holds)
    for r in records:
        adj = adjudications.get(r["id"])
        if adj:
            a = dict(adj)
            if a.get("refit"):
                a["refit"] = {k: ([round(float(x), 4) for x in v]
                                  if k in ("mn", "mx") else v)
                              for k, v in a["refit"].items()}
            r["adjudication"] = a
            r["scripted"] = {k: by_id_a[r["id"]][k] for k in
                             ("disposition", "delta_raw", "magnitude_m",
                              "snapped_aabb")}
            if adj["verdict"] in ("NO_SNAP", "DEFER_TO_SURGERY"):
                r["disposition"] = "HELD_" + adj["verdict"]

    disp = Counter(r["disposition"] for r in records)
    large = sorted((r for r in records if r.get("flag")),
                   key=lambda r: -r["magnitude_m"])
    vc = Counter(a["verdict"] or "unjudged" for a in adjudications.values())
    layer = {
        "scene": args.scene, "built": str(date.today()),
        "elapsed_s": round(time.time() - t0, 1),
        "generated_by": "compose/snap.py",
        "version": "v1-adjudicated",
        "model": None if args.no_llm else args.model,
        "note": ("PH1 v1: scripted snap PROPOSES (pass A); flagged "
                 "anchor-class boxes + judge suspect_box pointers form a "
                 "docket adjudicated by ONE batched agent call over a "
                 "typed menu (adopt-refit/snap/no-snap/defer); refit = "
                 "MAD-outlier re-fuse from raw per-view lift members. "
                 "Pass B re-snaps with verdicts applied. Graph/boxes "
                 "verbatim -- refit + snapped boxes live only here."),
        "params": {"large_correction_m": LARGE_CORRECTION,
                   "top_tol_m": TOP_TOL,
                   "docket_rule": "LARGE + arch in support options, "
                                  "or judge suspect_box",
                   "refit_mad_k": REFIT_MAD_K,
                   "refit_abs_tol_m": REFIT_ABS_TOL},
        "counts": {"objects": len(records), **disp,
                   "large_corrections": len(large),
                   "docket": len(docket), **{f"verdict_{k}": n
                                             for k, n in vc.items()}},
        "objects": records,
    }
    opath = cdir / "snap.json"
    opath.write_text(json.dumps(layer, indent=1), encoding="utf-8")
    print(f"[snap] wrote {opath} "
          f"({time.time() - t0:.0f}s elapsed)")
    print(f"[snap] dispositions: {json.dumps(dict(disp))}")
    print(f"[snap] verdicts: {json.dumps(dict(vc))}")
    for oid in docket:
        adj = adjudications[oid]
        rf = adj.get("refit")
        extra = ""
        if adj["verdict"] == "ADOPT_REFIT_AND_SNAP" and rf:
            extra = " | refit " + "; ".join(
                f'{c["bound"]} {c["from"]}->{c["to"]}' for c in rf["changes"])
        print(f"    {oid} ({names[oid]}): {adj['verdict'] or 'CANDIDATE'} "
              f"[{adj['confidence']}] {adj['reason'] or ''}{extra}")
    print(f"[snap] LARGE corrections remaining (> {LARGE_CORRECTION} m): "
          f"{len(large)}")
    for r in large:
        print(f"    {r['id']} ({r['name']}) {r['how']} -> "
              f"{r['supporter']}: {r['magnitude_m']} m "
              f"[{r['disposition']}]")


if __name__ == "__main__":
    main()
