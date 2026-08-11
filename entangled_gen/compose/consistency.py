"""
STEP 3 COMPOSE+LOOP, module 2 -- CONSISTENCY (the self-consistency pass).

DOWNSTREAM of compose/supported_by.py -- its first consumer (user 07-26G:
supported_by does NOT fully supersede the contact edges; containment /
attachment / adjacency are ARRANGEMENT facts composition will consume,
so every edge gets a consistency verdict instead of blanket archiving).

Part A -- supported_by SELF-AUDIT, pure code: support cycles (A rests on
B rests on A via top options), supporters that are themselves flagged
none_plausible (dependents inherit the doubt), supporters NEEDS_REVIEW.

Part B -- every resolved contact edge classified against BOTH endpoints'
supported_by verdicts, code first:
  CONFIRMED_SUPPORT  edge matches the subject's TOP option (the support's
                     own evidence) -- SUPPORTER slot only (v7 fix, 08-01
                     late, the AC IN_WALL case: an AGAINST-slot hit is
                     DISAGREEMENT, not confirmation -- those edges fall
                     through to the LLM leftovers, whose docket now shows
                     the against ruling)
  SUPPORT_ALT        matches a live alternate option
  TRANSITIVE         target sits in the subject's support CHAIN
                     (book IN shelf, shelf inside bookshelf ->
                      book IN bookshelf is fine)
  KEPT_ARRANGEMENT   NEAR -- adjacency fact, no consistency question
  KEPT_GEOMETRIC     INTERPENETRATES -- box-surgery food
  KEPT_STRUCTURAL    PART_OF
  (leftovers)        support-type edges no verdict explains -> ONE batched
                     LLM call: KEEP (real arrangement fact) vs DROP
                     (artifact: wall graze, in-two-shelves loser), reason.
                     Conservative degrade -> NEEDS_REVIEW.

Nothing is removed from the graph -- verdicts are PROPOSALS
(compose/consistency.json), same contract as the rest of the stage.

Run:
  python compose/consistency.py --scene bedroom_marble --no-llm  # code only
  python compose/consistency.py --scene bedroom_marble
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
# scene_state lives in the sibling graph/ package, not beside us, so its
# directory has to go on the path too (same two-step the other compose
# modules use, e.g. uniform_instances.py).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "graph"))
import scene_state  # noqa: E402

MODEL = "sonnet"
CALL_TIMEOUT_S = 480
BATCH_SIZE = 25
PROMPT_VERSION = "1"

SUPPORT_EDGE_TYPES = ("ON", "IN", "IN_WALL", "ATTACHED")
CHAIN_MAX = 12

TEMPLATE = """\
{firm}You are auditing relation edges in a 3D scene graph of ONE indoor \
room. Each object's SUPPORT was already judged (what holds it up, given \
measured boxes; sizes are noisy -- centimeter-level error is normal). \
The edges below are the LEFTOVERS: contact/containment relations that no \
support verdict explains. For each, decide whether it is a REAL \
arrangement fact worth keeping (genuine containment, attachment, or \
meaningful flush contact between neighbors) or a measurement ARTIFACT to \
drop (a box graze misread as containment, or the losing duplicate when \
one object was recorded inside two different containers).

Return ONE fenced ```json block containing a JSON ARRAY with EXACTLY one \
object per numbered item, same order:
{{"i": <item number>, "verdict": "KEEP|DROP", "confidence": 0.0-1.0, \
"reason": "one sentence"}}
Output ONLY the fenced JSON block.

{items}"""

FIRM_PREFIX = ("Your previous response was malformed. This time output "
               "ONLY one fenced ```json code block containing the JSON "
               "array, no prose.\n\n")


def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)  # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd, model):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[consistency] claude.exe not on PATH")
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


def parse_response(text, n_items):
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
        if not isinstance(e, dict):
            continue
        try:
            i = int(e.get("i"))
            conf = round(min(1.0, max(0.0, float(e.get("confidence")))), 2)
        except (TypeError, ValueError):
            continue
        v = e.get("verdict")
        reason = e.get("reason")
        if not (1 <= i <= n_items) or v not in ("KEEP", "DROP") \
                or not isinstance(reason, str) or not reason.strip():
            continue
        good[i] = {"verdict": v, "confidence": conf,
                   "reason": reason.strip()}
    return good


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--no-llm", action="store_true")
    ap.add_argument("--fresh", action="store_true", help="ignore cache")
    args = ap.parse_args()

    gpath = paths.scene_dir(args.scene) / "scene_graph.json"
    graph = json.loads(gpath.read_text(encoding="utf-8"))
    # THE CURRENT LAYER, not `resolved`. `resolved` is where identity was
    # settled, but it is PRE-VOTE: every stage after it re-elected boxes,
    # split nodes and moved edges with them. Auditing `resolved` edges
    # would rule on relations the scene no longer has, and name them from
    # an inventory that is missing the pieces the judges created.
    _layer, res = scene_state.current(graph)
    edges = res["edges"]
    names = {n["id"]: n["name"] for n in res["nodes"]}

    cdir = paths.compose_dir(args.scene)
    sbpath = cdir / "supported_by.json"
    if not sbpath.exists():
        raise SystemExit("[consistency] no supported_by.json -- run "
                         "compose/supported_by.py first (this module is "
                         "downstream of it)")
    sbL = json.loads(sbpath.read_text(encoding="utf-8"))
    sb = {o["id"]: o for o in sbL["objects"]}

    def options(oid):
        return (sb.get(oid) or {}).get("supported_by") or []

    flagged = {o["id"] for o in sbL["objects"] if o.get("none_plausible")}
    unresolved = {o["id"] for o in sbL["objects"]
                  if o["status"] != "ok"}

    # ---- Part A: supported_by self-audit (pure code) ----
    audit = []

    def top_supporter(oid):
        op = options(oid)
        return op[0]["supporter"] if op else None

    def chain(oid):
        """Support chain from oid upward via top options (excl. oid)."""
        seen, out, cur = {oid}, [], top_supporter(oid)
        while cur and len(out) < CHAIN_MAX:
            out.append(cur)
            if cur.startswith("arch_") or cur in seen:
                break
            seen.add(cur)
            cur = top_supporter(cur)
        return out

    for oid in sb:
        ch = chain(oid)
        # cycle: chain re-enters a non-arch node it already holds
        seen = set()
        for c in ch:
            if c in seen:
                audit.append({"kind": "support_cycle", "object": oid,
                              "chain": ch,
                              "note": f"support chain revisits {c}"})
                break
            seen.add(c)
        ts = top_supporter(oid)
        if ts and ts in flagged:
            audit.append({"kind": "supporter_flagged", "object": oid,
                          "supporter": ts,
                          "note": (f"top supporter {ts} "
                                   f"({names.get(ts, '?')}) is "
                                   f"none_plausible -- doubt inherited")})
        if ts and not ts.startswith("arch_") and ts in unresolved:
            audit.append({"kind": "supporter_unresolved", "object": oid,
                          "supporter": ts,
                          "note": f"top supporter {ts} is NEEDS_REVIEW"})

    # ---- Part B: classify every resolved edge (code first) ----
    def cand_text(oid, partner):
        """The metrics line supported_by showed for (oid, partner)."""
        for line in (sb.get(oid) or {}).get("candidates", []):
            if f"({partner})" in line:
                return re.sub(r"^\[c\d+\] ", "", line)
        return None

    verdicts = []       # parallel to edges
    leftovers = []      # (edge_index, item_text)
    for e in edges:
        a, b, t = e["a"], e["b"], e["type"]
        if t == "NEAR":
            verdicts.append({"verdict": "KEPT_ARRANGEMENT",
                             "by": "code", "reason": "adjacency fact"})
            continue
        if t == "INTERPENETRATES":
            verdicts.append({"verdict": "KEPT_GEOMETRIC", "by": "code",
                             "reason": "box overlap -- box-surgery food"})
            continue
        if t == "PART_OF":
            # LEGACY (retired 08-01, judge_pairs v2: fragments merge as
            # SAME) -- fires only on graphs resolved before the re-judge;
            # after the rebuild no PART_OF edge exists
            verdicts.append({"verdict": "KEPT_STRUCTURAL", "by": "code",
                             "reason": "structural membership"})
            continue
        # support-type edge: subject a, target b. SUPPORTER slot only --
        # an against-slot hit means the ruling REJECTED this candidate;
        # that edge is the record disagreeing with the ruling, exactly
        # what the leftover judge exists to read (v7, the AC case).
        matched = None
        for i, opt in enumerate(options(a)):
            if opt["supporter"] == b:
                matched = "CONFIRMED_SUPPORT" if i == 0 else "SUPPORT_ALT"
                break
        if matched:
            verdicts.append({"verdict": matched, "by": "code",
                             "reason": "matches supported_by option"})
            continue
        if b in chain(a):
            verdicts.append({"verdict": "TRANSITIVE", "by": "code",
                             "reason": "target is in the support chain"})
            continue
        if a in unresolved or (not b.startswith("arch_") and b in unresolved):
            verdicts.append({"verdict": "NEEDS_REVIEW", "by": "code",
                             "reason": "an endpoint is unresolved"})
            continue
        verdicts.append(None)   # leftover -> LLM
        leftovers.append(len(verdicts) - 1)

    def vsum(oid):
        op = options(oid)
        if oid.startswith("arch_"):
            return oid
        if not op:
            return (f"{oid} ({names.get(oid, '?')}): "
                    + ("judged NOT a real object"
                       if oid in flagged else "unresolved"))
        o = op[0]
        ag = (f", ruled AGAINST {o['against']}" if o.get("against") else "")
        return (f"{oid} ({names.get(oid, '?')}): {o['how']} "
                f"{o['supporter']} ({o['confidence']}){ag}")

    def item_text(i, ei):
        e = edges[ei]
        m = cand_text(e["a"], e["b"]) or "(no metrics line)"
        return (f"ITEM {i} · edge {e['a']} -{e['type']}- {e['b']}\n"
                f"  measured: {m}\n"
                f"  support verdicts: {vsum(e['a'])} | {vsum(e['b'])}")

    cache_path = cdir / "consistency_cache.json"
    cache = (json.loads(cache_path.read_text(encoding="utf-8"))
             if cache_path.exists() and not args.fresh else {})

    def ekey(ei):
        e = edges[ei]
        blob = PROMPT_VERSION + item_text(0, ei)
        return (f"{e['a']}|{e['type']}|{e['b']}|"
                + hashlib.md5(blob.encode()).hexdigest()[:12])

    todo = []
    for ei in leftovers:
        c = cache.get(ekey(ei))
        if c:
            verdicts[ei] = c
        else:
            todo.append(ei)

    if args.no_llm:
        for ei in todo:
            verdicts[ei] = {"verdict": "NEEDS_REVIEW", "by": "degrade",
                            "reason": "LLM pass not run"}
        print(f"[consistency] --no-llm: {len(todo)} leftover edges left "
              f"NEEDS_REVIEW")
    else:
        print(f"[consistency] {len(leftovers)} leftover edges "
              f"({len(leftovers) - len(todo)} cached, {len(todo)} to judge, "
              f"model {args.model}, prompt v{PROMPT_VERSION})")
        batches = [todo[i:i + BATCH_SIZE]
                   for i in range(0, len(todo), BATCH_SIZE)]
        for bi, batch in enumerate(batches):
            items = "\n\n".join(item_text(i + 1, ei)
                                for i, ei in enumerate(batch))
            got = {}
            for firm in ("", FIRM_PREFIX):
                try:
                    out = call_claude(TEMPLATE.format(firm=firm, items=items),
                                      cdir, args.model)
                except (RuntimeError, subprocess.TimeoutExpired) as ex:
                    print(f"[consistency] batch {bi}: call failed: {ex}")
                    break
                got = parse_response(out, len(batch))
                if got:
                    break
            print(f"[consistency] batch {bi}: {len(got)}/{len(batch)} "
                  f"verdicts")
            for i, ei in enumerate(batch):
                g = got.get(i + 1)
                v = ({"verdict": g["verdict"], "by": "llm",
                      "confidence": g["confidence"], "reason": g["reason"],
                      "model": args.model, "date": str(date.today())}
                     if g else
                     {"verdict": "NEEDS_REVIEW", "by": "degrade",
                      "reason": "no/invalid LLM verdict"})
                verdicts[ei] = v
                if g:
                    cache[ekey(ei)] = v
            cache_path.write_text(json.dumps(cache, indent=1),
                                  encoding="utf-8")

    out_edges = [{**e, **v} for e, v in zip(edges, verdicts)]
    from collections import Counter
    counts = Counter(v["verdict"] for v in verdicts)
    drops = [oe for oe in out_edges if oe["verdict"] == "DROP"]
    layer = {
        "scene": args.scene, "built": str(date.today()),
        "elapsed_s": round(time.time() - t0, 1),
        "generated_by": "compose/consistency.py",
        "graph_fingerprint": paths.graph_fingerprint(args.scene),
        "model": None if args.no_llm else args.model,
        "prompt_version": PROMPT_VERSION,
        "note": ("Per-edge consistency verdicts vs the supported_by layer. "
                 "PROPOSALS ONLY -- the graph is untouched; DROP = artifact "
                 "edge proposed for removal at the cleaning step."),
        "counts": dict(counts),
        "audit": audit,
        "edges": out_edges,
    }
    opath = cdir / "consistency.json"
    opath.write_text(json.dumps(layer, indent=1), encoding="utf-8")
    print(f"[consistency] wrote {opath} "
          f"({time.time() - t0:.0f}s elapsed)")
    print(f"[consistency] edge verdicts: {json.dumps(dict(counts))}")
    print(f"[consistency] audit flags ({len(audit)}):")
    for f in audit:
        print(f"    {f['kind']}: {f['object']} -- {f['note']}")
    if drops:
        print(f"[consistency] DROP proposals ({len(drops)}):")
        for d in drops:
            print(f"    {d['a']} ({names.get(d['a'], '?')}) -{d['type']}- "
                  f"{d['b']} ({names.get(d['b'], '?')}): "
                  f"{d['reason'][:90]}")


if __name__ == "__main__":
    main()
