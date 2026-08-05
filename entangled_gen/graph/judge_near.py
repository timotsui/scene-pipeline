"""
Pass 2 -- JUDGE, sub-pass J5: resolve the NEAR fallback edges (floaters).

The record's no-floater invariant gives every otherwise-isolated detection
node ONE caveated NEAR edge carrying the geometrically nearest candidate
plus ranked alternatives (build_edges.py). This pass asks the VLM which
relationship is physically real -- but the division of labor is strict
(user ruling 2026-07-26, after the v1 plant miss):

    CODE interprets the numbers.  The deterministic menu builder below
    classifies every candidate from fixed thresholds (plausible contact /
    floating gap / RULED OUT by geometry), dedupes candidates that J1
    judged the SAME object, and words each fact unambiguously. No raw
    sign conventions ever reach the model. (v1 defect: a prose gloss
    said "negative gap = box overlaps it", and the judge read a -1.32 m
    gap as the plant resting on a shelf top 1.3 m above its base.)

    The MODEL interprets the pixels.  Given the crops and only the
    non-ruled-out menu, it answers what geometry cannot: which plausible
    option is true, and does an occluded base / undetected thin mount
    ("box_underreach") explain the gap?

Verdict relations: ON (resting, incl. via underreach) / IN_WALL (wall or
its parallel surfaces) / ATTACHED (ceiling) / NEAR (undecidable -- stays
unresolved, honest).

PROMPT SCHEMA: the template text below is FIXED and versioned
(PROMPT_VERSION, salted into the cache's evidence hash -- editing the
template automatically re-judges). A deterministic filler populates it
from scene_graph.json; nothing is authored per case. Pipelines run this
unattended over any number of scenes.

ACCEPTANCE TEST (user ground truth, REVIEW_LOG R10, 2026-07-26):
    obj_001 plant   -> ON arch_floor    (base occluded; 2/4 truncated)
    obj_005 monitor -> ON obj_039 desk  (undetected mounting arm)
    obj_096 picture -> IN_WALL          (wall/curtain-plane mounted)
Zero-LLM regression test for the v1 miss: --selftest asserts the
classifier rules the shelf candidates out of the plant's menu.

WRITE-BACK (additive-only): the NEAR edge gains "verdict" {relation,
target, box_underreach, confidence, reason, model, date, evidence_hash,
source: "judge_near"}; status "unresolved" -> "judged" (stays
"unresolved" on a NEAR verdict or a failed call). Edge TYPE is not
rewritten -- build_judged.py (J2) materializes resolved edges. The chosen
target must be on the offered menu (validated).

Bridge/cache pattern = judge_pairs.py / describe_nodes.py:
out/<scene>/graph/judge_near_cache.json keyed by node id.

Run:
  python graph/judge_near.py --scene bedroom_marble
  python graph/judge_near.py --scene bedroom_marble --smoke   # 1 edge, no write
  python graph/judge_near.py --selftest                       # classifier only
"""
import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

MODEL = "sonnet"
CALL_TIMEOUT_S = 480
CONCURRENCY = 8   # 3 until 2026-08-04; compute is cloud-side, local lanes are couriers (user ruling; measured 2.5x at 6 lanes, contention not crash risk)
CROPS_PER_NODE = 3
RELATIONS = ("ON", "IN_WALL", "ATTACHED", "NEAR")
HINT2REL = {"support": "ON", "floor": "ON", "wall": "IN_WALL",
            "ceiling": "ATTACHED"}

PROMPT_VERSION = "2"       # bump on ANY template/classifier change --
                           # salted into the cache hash, re-judges all
CONTACT_GAP_M = 0.25       # |gap| within this = plausible resting contact
RULE_OUT_BELOW_M = 0.25    # bottom this far below a top = cannot rest on it
PLANE_TOUCH_M = 0.05       # within this of a plane = touching
PLANE_NEAR_M = 0.25        # within this = plausibly mounted; beyond = out

TEMPLATE = """\
{firm}An object detected in a 3D scan of an indoor room is not touching \
anything -- its 3D box passed no contact test. Real objects rest on or \
hang from something. Look at the crop images and decide what actually \
holds it.

The object: {node_id}, detected as "{label}", box WxDxH = {w:.2f}x{d:.2f}\
x{ht:.2f} m, spanning {bottom:.2f}-{top:.2f} m above the floor, seen in \
{n_views} views.
IMPORTANT: {n_trunc} of {n_members} of its detections were cut off at a \
view edge -- the box may UNDER-REACH the real object (an occluded base, \
or a thin stand/arm/cable too small to detect, can close a small gap).
  crop image(s):
{crop_lines}

Candidate relationships. Geometry has already been checked by the \
pipeline; each line below states its meaning in plain words. Choose ONE \
candidate (or NEAR if the images make none of them believable):
{menu_lines}
{ruled_out_block}
Return ONE fenced ```json block:
{{"node": "{node_id}", "relation": "ON|IN_WALL|ATTACHED|NEAR", \
"target": "<a candidate target id, or null for NEAR>", \
"box_underreach": true or false, "confidence": 0.0-1.0, \
"reason": "one sentence"}}
Output ONLY the fenced JSON block."""

FIRM_PREFIX = ("Your previous response was malformed. This time output "
               "ONLY one fenced ```json code block containing ONE JSON "
               "object, no prose.\n\n")


# --------------------------------------------------------------------------
# deterministic menu builder (code interprets the numbers)
# --------------------------------------------------------------------------

def classify(cand):
    """(status, plain-English sentence) for one recorded candidate.
    status: 'plausible' | 'floating' (choosable) | 'ruled_out'."""
    rel = HINT2REL[cand["relation_hint"]]
    if rel == "ON":
        g = cand["gap_m"]
        frac = cand.get("overlap_frac_of_a")
        fr = (f", {frac:.0%} of its footprint over it"
              if frac is not None else "")
        if g < -RULE_OUT_BELOW_M:
            return "ruled_out", (f"the object's bottom sits {-g:.2f} m "
                                 f"BELOW this surface's top -- it cannot "
                                 f"be resting on it")
        if g > CONTACT_GAP_M:
            return "floating", (f"there is {g:.2f} m of air below the "
                                f"object's bottom{fr} -- only real if "
                                f"the box under-reaches that far")
        return "plausible", (f"the object's bottom is within {abs(g):.2f} "
                             f"m of this surface's top{fr} -- plausible "
                             f"resting contact")
    dist = cand["distance_m"]
    via = (" (a wall-parallel surface: curtain plane / visible wall face)"
           if "via_parallel_surface_raw" in cand else "")
    if dist <= PLANE_TOUCH_M:
        return "plausible", f"the box touches this plane{via}"
    if dist <= PLANE_NEAR_M:
        return "plausible", (f"the box is {dist:.2f} m from this "
                             f"plane{via} -- plausibly mounted")
    return "ruled_out", (f"the box is {dist:.2f} m from this plane{via} "
                         f"-- too far to be mounted on it")


def same_canonical(graph):
    """target id -> canonical id, folding pairs J1 judged SAME (so one
    physical object detected twice cannot occupy two menu slots)."""
    parent = {}

    def find(x):
        while parent.get(x, x) != x:
            x = parent[x]
        return x

    for e in graph["edges"]:
        if (e["type"] == "SAME_CANDIDATE"
                and e.get("verdict", {}).get("verdict") == "SAME"):
            ra, rb = find(e["a"]), find(e["b"])
            if ra != rb:
                parent[rb] = ra
    return find


def build_menu(edge, nodes, graph):
    """Deterministic fill: returns (menu_lines, ruled_out_block,
    allowed {(relation, target)})."""
    ev = edge["evidence"]
    cands = [{"relation_hint": ev["relation_hint"], "target": edge["b"],
              **{k: v for k, v in ev.items()
                 if k in ("gap_m", "distance_m", "overlap_frac_of_a",
                          "via_parallel_surface_raw")}}]
    cands += ev.get("alternatives", [])

    canon = same_canonical(graph)
    RANK = {"plausible": 0, "floating": 1, "ruled_out": 2}
    best = {}                       # (relation, canonical target) -> entry
    for c in cands:
        rel = HINT2REL[c["relation_hint"]]
        status, sentence = classify(c)
        key = (rel, canon(c["target"]))
        metric = abs(c.get("gap_m", c.get("distance_m", 0.0)))
        ent = {"rel": rel, "target": c["target"], "status": status,
               "sentence": sentence, "metric": metric, "dups": []}
        prev = best.get(key)
        if prev is None:
            best[key] = ent
        elif (RANK[status], metric) < (RANK[prev["status"]],
                                       prev["metric"]):
            ent["dups"] = prev["dups"] + [prev["target"]]
            best[key] = ent
        else:
            prev["dups"].append(c["target"])

    def label_of(t):
        return (nodes[t]["label"] if nodes[t]["source"] == "detection"
                else t.replace("arch_", "").replace("_", " "))

    entries = sorted(best.values(),
                     key=lambda e: (RANK[e["status"]], e["metric"]))
    choosable = [e for e in entries if e["status"] != "ruled_out"]
    ruled = [e for e in entries if e["status"] == "ruled_out"]
    if not choosable:               # degenerate: nothing plausible --
        choosable, ruled = entries, []  # offer all, sentences say why

    menu, allowed = [], set()
    for i, e in enumerate(choosable, 1):
        dup = (" [also detected as "
               + ", ".join(f"{d} ({label_of(d)})" for d in e["dups"])
               + " -- judged the same object]" if e["dups"] else "")
        menu.append(f'  {i}. {e["rel"]} {e["target"]} '
                    f'({label_of(e["target"])}) -- {e["sentence"]}{dup}')
        allowed.add((e["rel"], e["target"]))
    ruled_block = ""
    if ruled:
        ruled_block = ("Ruled out by geometry (NOT choosable):\n" + "\n".join(
            f'  - {e["rel"]} {e["target"]} ({label_of(e["target"])}) -- '
            f'{e["sentence"]}' for e in ruled) + "\n")
    return menu, ruled_block, allowed


# --------------------------------------------------------------------------
# claude bridge (judge_pairs.py / describe_nodes.py pattern)
# --------------------------------------------------------------------------

def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)  # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd, model):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[judge_near] claude.exe not on PATH")
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


def parse_verdict(text, allowed):
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    raw = m.group(1) if m else None
    if raw is None:
        i = text.find("{")
        if i >= 0:
            try:
                obj, _ = json.JSONDecoder().raw_decode(text[i:])
                raw = json.dumps(obj)
            except ValueError:
                raw = None
    if raw is None:
        return None
    try:
        v = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(v, dict) or v.get("relation") not in RELATIONS:
        return None
    if not isinstance(v.get("reason"), str) or not v["reason"].strip():
        return None
    try:
        conf = float(v.get("confidence"))
    except (TypeError, ValueError):
        return None
    rel, tgt = v["relation"], v.get("target")
    if rel != "NEAR" and (rel, tgt) not in allowed:
        return None
    return {"relation": rel, "target": tgt if rel != "NEAR" else None,
            "box_underreach": bool(v.get("box_underreach")),
            "confidence": round(min(1.0, max(0.0, conf)), 2),
            "reason": v["reason"].strip()}


def node_crops(node, crops_dir):
    members = sorted(node["evidence"].get("members", []),
                     key=lambda m: -m.get("score", 0.0))
    out = []
    for m in members:
        p = crops_dir / m.get("crop", "")
        if m.get("crop") and p.exists():
            out.append(p)
        if len(out) == CROPS_PER_NODE:
            break
    return out


def fill_template(edge, node, crops, floor_y, menu, ruled_block, firm):
    g = node["geometry"]
    s = g["size"]
    nt = edge["evidence"].get("members_truncated", [0, 0])
    return TEMPLATE.format(
        firm=FIRM_PREFIX if firm else "",
        node_id=edge["a"], label=node["label"],
        w=s[0], d=s[2], ht=s[1],
        bottom=floor_y - g["aabb_max"][1], top=floor_y - g["aabb_min"][1],
        n_views=node["evidence"].get("n_detections", 0),
        n_trunc=nt[0], n_members=nt[1],
        crop_lines="\n".join(f"    {p}" for p in crops),
        menu_lines="\n".join(menu),
        ruled_out_block=ruled_block)


def evidence_hash(crop_paths, edge_evidence):
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode())      # template edits re-judge
    for p in sorted(str(p) for p in crop_paths):
        h.update(Path(p).read_bytes())
    h.update(json.dumps(edge_evidence, sort_keys=True).encode())
    return h.hexdigest()[:32]


# --------------------------------------------------------------------------

def selftest():
    """Zero-LLM regression test for the v1 plant miss (REVIEW_LOG R12):
    the recorded menu numbers for obj_001 -- the shelf candidates MUST be
    ruled out, floor and wall MUST stay choosable."""
    cases = [
        ({"relation_hint": "wall", "distance_m": 0.0,
          "via_parallel_surface_raw": -1.506}, "plausible"),
        ({"relation_hint": "floor", "gap_m": 0.191}, "plausible"),
        ({"relation_hint": "support", "gap_m": -1.315,
          "overlap_frac_of_a": 0.203}, "ruled_out"),
        ({"relation_hint": "support", "gap_m": -1.4,
          "overlap_frac_of_a": 0.203}, "ruled_out"),
        # obj_005 monitor's desk candidate must stay plausible
        ({"relation_hint": "support", "gap_m": 0.185,
          "overlap_frac_of_a": 1.0}, "plausible"),
        # a mid-air gap: choosable but flagged floating
        ({"relation_hint": "support", "gap_m": 0.5,
          "overlap_frac_of_a": 0.9}, "floating"),
    ]
    bad = []
    for cand, want in cases:
        got, sentence = classify(cand)
        ok = got == want
        print(f"  {'PASS' if ok else '*** FAIL ***'} {cand} -> {got} "
              f"({sentence})")
        if not ok:
            bad.append((cand, want, got))
    if bad:
        sys.exit(1)
    print("[judge_near] selftest PASS "
          f"(prompt version {PROMPT_VERSION})")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY)
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--selftest", action="store_true")
    args = ap.parse_args()
    if args.selftest:
        selftest()
        return

    gdir = paths.scene_dir(args.scene)
    gpath = gdir / "scene_graph.json"
    crops_dir = gdir / "graph" / "crops"
    cache_path = gdir / "graph" / "judge_near_cache.json"
    graph = json.loads(gpath.read_text())
    nodes = {n["id"]: n for n in graph["nodes"]}
    floor_y = nodes["arch_floor"]["geometry"]["plane"]["value_raw"]

    queue = [e for e in graph["edges"] if e["type"] == "NEAR"]
    if args.smoke:
        queue = queue[:1]
    cache = (json.loads(cache_path.read_text())
             if cache_path.exists() else {"meta": {"calls": 0}, "nodes": {}})

    jobs, hits = [], 0
    for e in queue:
        crops = node_crops(nodes[e["a"]], crops_dir)
        ehash = evidence_hash(crops, e["evidence"])
        ent = cache["nodes"].get(e["a"])
        if ent and ent.get("evidence_hash") == ehash:
            e["verdict"] = ent["verdict"]
            if ent["verdict"]["relation"] != "NEAR":
                e["status"] = "judged"
            hits += 1
            continue
        jobs.append((e, ehash, crops))

    print(f"[judge_near] queue {len(queue)} NEAR edges: {hits} cache hits, "
          f"{len(jobs)} live calls (model {args.model}, prompt v"
          f"{PROMPT_VERSION})")

    def judge(job):
        e, ehash, crops = job
        menu, ruled_block, allowed = build_menu(e, nodes, graph)
        for attempt, firm in ((1, False), (2, True)):
            prompt = fill_template(e, nodes[e["a"]], crops, floor_y, menu,
                                   ruled_block, firm)
            try:
                out = call_claude(prompt, crops_dir, args.model)
            except (RuntimeError, subprocess.TimeoutExpired) as ex:
                print(f'[judge_near]   {e["a"]}: call failed ({ex})')
                continue
            v = parse_verdict(out, allowed)
            if v:
                return ehash, v
            print(f'[judge_near]   {e["a"]}: malformed (attempt {attempt})')
        return ehash, None

    results = []
    if jobs:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            results = list(ex.map(judge, jobs))

    failed = []
    for (e, ehash, _), (h2, v) in zip(jobs, results):
        if v is None:
            failed.append(e["a"])
            continue          # stays unresolved -- degradation
        v_full = {**v, "model": args.model, "date": date.today().isoformat(),
                  "prompt_version": PROMPT_VERSION,
                  "evidence_hash": ehash, "source": "judge_near"}
        e["verdict"] = v_full
        if v["relation"] != "NEAR":
            e["status"] = "judged"
        cache["nodes"][e["a"]] = {"evidence_hash": ehash, "verdict": v_full}

    for e in queue:
        v = e.get("verdict")
        if v:
            print(f'  {e["a"]} ({nodes[e["a"]]["label"]}): {v["relation"]} '
                  f'{v.get("target") or ""} '
                  f'underreach={v["box_underreach"]} -- {v["reason"]}')
        else:
            print(f'  {e["a"]} ({nodes[e["a"]]["label"]}): UNRESOLVED')

    if args.smoke:
        print("[judge_near] SMOKE -- no write-back")
        return

    cache["meta"]["calls"] = cache["meta"].get("calls", 0) + len(jobs)
    cache_path.write_text(json.dumps(cache, indent=1))
    meta = graph.setdefault("judge_near_meta", {})
    judged = sum(1 for e in queue if e.get("status") == "judged")
    meta.update({"model": args.model, "last_run": date.today().isoformat(),
                 "prompt_version": PROMPT_VERSION,
                 "cumulative_calls": cache["meta"]["calls"],
                 "judged": judged, "unresolved": len(queue) - judged})
    gpath.write_text(json.dumps(graph, indent=1))
    print(f"[judge_near] wrote {gpath} -- {judged}/{len(queue)} resolved"
          + (f" (FAILED: {failed})" if failed else ""))


if __name__ == "__main__":
    main()
