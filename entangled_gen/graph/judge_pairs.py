"""
Pass 2 -- JUDGE, sub-pass J1: same-vs-part over the SAME_CANDIDATE queue.

Visits ONLY the SAME_CANDIDATE edges the record's build_edges.py computed
from geometry (PLAN_SCENE_GRAPH.md 0a.7 J1). One cached VLM call per edge:
both nodes' evidence crops + label lists + the edge's numbers + each node's
structural edges (the cheap facts the record already holds). Verdict per
edge, ADDITIVE -- the record is never rewritten, nodes are never merged
here (merging is materialized by graph/build_judged.py, J2):

    SAME      the two nodes are one physical object detected twice --
              INCLUDING a partial detection of it (a fragment/section is
              still that object)
    DISTINCT  genuinely two objects (their spatial relation, if any, is
              already carried by the record's IN/ON/ATTACHED edges)

PART_OF REMOVED (user ruling 08-01, prompt v2): "component or sub-region"
was a vague middle category -- it let spatial answers wear an ontological
label (the books-cluster was ruled PART_OF its shelf and needed a
downstream REINTERPRET to fix). A fragment of the host = SAME (merge; the
host's appearance description covers its components -- "a table with a
drawer"); contents/attachments = DISTINCT + the existing edges. If it is
not a separately shoppable object, it must not stay a node.

WRITE-BACK (additive-only): each judged edge gains
    "verdict": {verdict, part, confidence, reason, model, date,
                evidence_hash, source: "judge_pairs"}
and status "open" -> "judged". Top-level "judge_pairs_meta" accumulates
call counts. A failed edge (malformed twice) keeps status "open" and gets
NO verdict -- conservative degradation, never a guessed merge; reruns
retry it.

VLM ROUTE: claude.exe subscription bridge -- the describe_nodes.py pattern
verbatim (ANTHROPIC_API_KEY/AUTH_TOKEN stripped from the child env, cwd =
the crops dir, strict fenced-JSON contract, malformed -> ONE firmer retry).
Calls run CONCURRENTLY (default 3 processes).

CACHE / IDEMPOTENCY: out/<scene>/graph/judge_pairs_cache.json keyed
"a|b"; entry stores an evidence hash = sha256(crop bytes of both nodes +
the edge's evidence json). Rerun skips edges whose hash matches a cached
verdict (and re-applies the cached verdict to the graph, so the cache can
rebuild scene_graph.json from scratch).

Prompts contain ONLY node-local facts (labels, sizes, heights, this edge's
numbers, the nodes' own edges) -- nothing scene-specific (automated-
pipeline rule).

Run:
  python graph/judge_pairs.py --scene bedroom_marble            # full queue
  python graph/judge_pairs.py --scene bedroom_marble --smoke    # 1 edge, no write
  python graph/judge_pairs.py --scene bedroom_marble --pair obj_007^|obj_057
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
sys.path.insert(0, str(HERE))
import paths  # noqa: E402
from rederive_voted_edges import (layer_of,          # noqa: E402
                                   overlay_voted_geometry)

MODEL = "sonnet"
CALL_TIMEOUT_S = 480
CONCURRENCY = 8   # 3 until 2026-08-04; compute is cloud-side, local lanes are couriers (user ruling; measured 2.5x at 6 lanes, contention not crash risk)
CROPS_PER_NODE = 2
VERDICTS = ("SAME", "DISTINCT")
PROMPT_VERSION = "2"       # bump on ANY prompt change -- salted into the
                           # cache hash so template edits re-judge (the
                           # v1 judge_near lesson, REVIEW_LOG R12)
                           # v2 (08-01): PART_OF removed from the verdict
                           # menu -- fragments are SAME, contents DISTINCT


# --------------------------------------------------------------------------
# claude bridge (describe_nodes.py pattern)
# --------------------------------------------------------------------------

def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)  # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd, model):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[judge_pairs] claude.exe not on PATH")
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


def parse_verdict(text, a, b):
    """Extract one JSON object; None if malformed/invalid."""
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
    if not isinstance(v, dict) or v.get("verdict") not in VERDICTS:
        return None
    if not isinstance(v.get("reason"), str) or not v["reason"].strip():
        return None
    try:
        conf = float(v.get("confidence"))
    except (TypeError, ValueError):
        return None
    return {"verdict": v["verdict"], "part": None,
            "confidence": round(min(1.0, max(0.0, conf)), 2),
            "reason": v["reason"].strip()}


# --------------------------------------------------------------------------
# evidence assembly (node-local facts only)
# --------------------------------------------------------------------------

def node_crops(node, crops_dir):
    """Up to CROPS_PER_NODE member crops, highest det score first."""
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


def node_facts(node, edges_list, floor_y):
    g = node["geometry"]
    s = g["size"]
    bottom = round(floor_y - g["aabb_max"][1], 2)   # height above floor
    top = round(floor_y - g["aabb_min"][1], 2)
    labels = sorted({(m.get("label"), round(m.get("score", 0), 2))
                     for m in node["evidence"].get("members", [])},
                    key=lambda t: -t[1])
    own, contains = [], 0
    for e in edges_list:
        if e["type"] in ("ON", "IN", "IN_WALL", "ATTACHED"):
            if e["a"] == node["id"]:
                own.append(f'{e["type"]} {e["b"]}')
            elif e["b"] == node["id"] and e["type"] == "IN":
                contains += 1
    facts = [f'detected as: ' + ", ".join(
                 f'"{l}" (score {sc})' for l, sc in labels),
             f'box W×D×H = {s[0]:.2f}×{s[2]:.2f}×{s[1]:.2f} m, spans '
             f'{bottom:.2f}–{top:.2f} m above the floor',
             f'seen in {node["evidence"].get("n_detections", 0)} views']
    if own:
        facts.append("its edges: " + "; ".join(sorted(set(own))[:6]))
    if contains:
        facts.append(f"contains {contains} smaller detected objects")
    return facts


def pair_prompt(edge, na, nb, crops_a, crops_b, floor_y, edges_list,
                firm=False):
    ev = edge["evidence"]
    lines = []
    if firm:
        lines.append(
            "Your previous response was malformed. This time output ONLY one "
            "fenced ```json code block containing ONE JSON object, no prose.")
    lines += [
        "Two object detections from a 3D scan of one indoor room overlap "
        "heavily and may be the same thing. Look at the crop images "
        "(absolute paths below), then decide.",
        "",
        f"Overlap numbers: 3D-box IoU {ev['iou']}, the smaller box is "
        f"{ev['containment']:.0%} inside the larger, box-center height "
        f"difference {ev['center_height_diff_m']} m.",
        "",
        f"Detection A = {edge['a']}:",
    ]
    lines += ["  " + f for f in node_facts(na, edges_list, floor_y)]
    lines += ["  crop image(s):"] + [f"    {p}" for p in crops_a]
    lines += ["", f"Detection B = {edge['b']}:"]
    lines += ["  " + f for f in node_facts(nb, edges_list, floor_y)]
    lines += ["  crop image(s):"] + [f"    {p}" for p in crops_b]
    lines += [
        "",
        "Verdicts:",
        '  "SAME"     -- one physical object detected twice: different '
        "views, different labels, OR a partial detection (a section/"
        "fragment of an object IS that object -- e.g. the upper half of "
        "a bookshelf detected separately is SAME as the bookshelf)",
        '  "DISTINCT" -- genuinely two different objects. Contents and '
        "attachments are DISTINCT, never the same thing (books inside a "
        "shelf are their own objects; their spatial relation is already "
        "recorded elsewhere)",
        "",
        "Crops are small low-resolution renders; judge from what you can "
        "actually see plus the numbers. Return ONE fenced ```json block:",
        '{"pair": "%s|%s", "verdict": "SAME|DISTINCT", '
        '"confidence": 0.0-1.0, '
        '"reason": "one sentence"}' % (edge["a"], edge["b"]),
        "Output ONLY the fenced JSON block.",
    ]
    return "\n".join(lines)


def evidence_hash(crop_paths, edge_evidence):
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode())      # template edits re-judge
    for p in sorted(str(p) for p in crop_paths):
        h.update(Path(p).read_bytes())
    h.update(json.dumps(edge_evidence, sort_keys=True).encode())
    return h.hexdigest()[:32]


# --------------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--concurrency", type=int, default=CONCURRENCY)
    ap.add_argument("--smoke", action="store_true",
                    help="judge the first edge only, print, no write-back")
    ap.add_argument("--pair", default=None,
                    help='re-judge one edge, e.g. "obj_007|obj_057" '
                         "(cache entry overwritten)")
    ap.add_argument("--edges-from", choices=("record", "voted_edges"),
                    default="record",
                    help="which layer to judge: the record (default, "
                         "lifted boxes) or graph['voted_edges'] (the "
                         "Phase-B2 loop-back re-derive on voted boxes)")
    args = ap.parse_args()

    gdir = paths.scene_dir(args.scene)
    gpath = gdir / "scene_graph.json"
    crops_dir = gdir / "graph" / "crops"
    cache_path = gdir / "graph" / "judge_pairs_cache.json"
    graph = json.loads(gpath.read_text())
    nodes = {n["id"]: n for n in graph["nodes"]}
    floor_y = nodes["arch_floor"]["geometry"]["plane"]["value_raw"]

    # LAYER: the record's edges, or the voted loop-back layer's (node
    # facts then quote the voted boxes those edges were derived from).
    layer = layer_of(graph, args.edges_from)
    if layer is None:
        edges_list = graph["edges"]
    else:
        edges_list = layer.setdefault("edges", [])
        nodes = overlay_voted_geometry(nodes, gdir, layer)

    queue = [e for e in edges_list if e["type"] == "SAME_CANDIDATE"]
    if args.pair:
        a, b = args.pair.split("|")
        queue = [e for e in queue if {e["a"], e["b"]} == {a, b}]
        if not queue:
            raise SystemExit(f"[judge_pairs] no SAME_CANDIDATE edge {args.pair}")
    if args.smoke:
        queue = queue[:1]

    cache = (json.loads(cache_path.read_text())
             if cache_path.exists() else {"meta": {"calls": 0}, "pairs": {}})

    jobs = []          # (edge, key, ehash) needing a live call
    hits = 0
    for e in queue:
        key = f'{e["a"]}|{e["b"]}'
        ca = node_crops(nodes[e["a"]], crops_dir)
        cb = node_crops(nodes[e["b"]], crops_dir)
        ehash = evidence_hash(ca + cb, e["evidence"])
        ent = cache["pairs"].get(key)
        if (ent and ent.get("evidence_hash") == ehash and not args.pair):
            e["verdict"] = ent["verdict"]
            e["status"] = "judged"
            hits += 1
            continue
        jobs.append((e, key, ehash, ca, cb))

    print(f"[judge_pairs] queue {len(queue)} edges: {hits} cache hits, "
          f"{len(jobs)} live calls (model {args.model}, "
          f"x{args.concurrency} concurrent)")

    def judge(job):
        e, key, ehash, ca, cb = job
        na, nb = nodes[e["a"]], nodes[e["b"]]
        for attempt, firm in ((1, False), (2, True)):
            prompt = pair_prompt(e, na, nb, ca, cb, floor_y, edges_list,
                                firm=firm)
            try:
                out = call_claude(prompt, crops_dir, args.model)
            except (RuntimeError, subprocess.TimeoutExpired) as ex:
                print(f"[judge_pairs]   {key}: call failed ({ex})")
                continue
            v = parse_verdict(out, e["a"], e["b"])
            if v:
                return key, ehash, v
            print(f"[judge_pairs]   {key}: malformed (attempt {attempt})")
        return key, ehash, None

    results = []
    if jobs:
        with ThreadPoolExecutor(max_workers=args.concurrency) as ex:
            results = list(ex.map(judge, jobs))

    calls = len(jobs)
    failed = []
    for (e, key, ehash, _, _), (k2, h2, v) in zip(jobs, results):
        if v is None:
            failed.append(key)
            continue          # stays status "open", no verdict -- degradation
        v_full = {**v, "model": args.model, "date": date.today().isoformat(),
                  "evidence_hash": ehash, "source": "judge_pairs"}
        e["verdict"] = v_full
        e["status"] = "judged"
        cache["pairs"][key] = {"evidence_hash": ehash, "verdict": v_full}

    for e in queue:
        tag = e.get("verdict", {}).get("verdict", "UNRESOLVED")
        part = e.get("verdict", {}).get("part")
        why = e.get("verdict", {}).get("reason", "")
        print(f'  {e["a"]} <-> {e["b"]} [{e["evidence"]["zone"]:9s}] '
              f'{e["evidence"]["labels"]}: {tag}'
              + (f" (part={part})" if part else "") + f" -- {why}")

    if args.smoke:
        print("[judge_pairs] SMOKE -- no write-back")
        return

    cache["meta"]["calls"] = cache["meta"].get("calls", 0) + calls
    cache_path.write_text(json.dumps(cache, indent=1))
    # meta rides with the layer that was judged (the record's stays put)
    meta = (graph if layer is None else layer).setdefault(
        "judge_pairs_meta", {})
    meta.update({"model": args.model, "last_run": date.today().isoformat(),
                 "cumulative_calls": cache["meta"]["calls"],
                 "judged": sum(1 for e in queue if "verdict" in e),
                 "unresolved": len(failed)})
    gpath.write_text(json.dumps(graph, indent=1))
    print(f"[judge_pairs] wrote {gpath} -- {meta['judged']}/{len(queue)} "
          f"judged, {len(failed)} unresolved"
          + (f" (FAILED: {failed})" if failed else ""))


if __name__ == "__main__":
    main()
