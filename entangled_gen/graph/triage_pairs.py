"""
Pass 2 -- JUDGE, sub-pass J0: PAIR TRIAGE (text-only docket clerk).

User design 08-01: lower the bar for CANDIDATES, filter before the
visual judge. The record's nesting facts (build_edges: containment >=
0.90 recorded on the smaller node -- the box-inside-box pairs the
SAME_CANDIDATE IoU >= 0.40 floor deliberately excludes) become
candidates here; ONE batched TEXT call answers, per pair, only:
"is this worth the visual pair judge's time?"

Cost gradient (the module's reason to exist):
    code (free)      record every containment fact       build_edges
    text LLM (cheap) triage worthiness                   THIS MODULE
    VLM (expensive)  rule SAME / DISTINCT with crops     judge_pairs

Why an LLM and not a label whitelist: "shelf inside bookshelf" vs
"book inside bookshelf" is a semantic call ([[automated-pipeline-rule]]:
no hard-coded synonym lists). ASYMMETRIC by prompt: nominate on doubt --
a wrong nomination costs one crop call; a wrong skip ships an
unresolved duplicate to composition.

JUDGE SUB-PASS, NOT RECORD: the record stays deterministic (the nesting
FACTS live there); triage writes its nominations ADDITIVELY like every
judge -- new SAME_CANDIDATE edges tagged nominated_by "triage" with the
triage reason + status "open" for judge_pairs to consume. build_edges
wipes graph["edges"] on rebuild; re-running this module re-applies
nominations from cache (0 calls), same as the other judges.

Skips: pairs already SAME_CANDIDATE (geometric zones), pairs whose
nodes are already same-cluster members (a prior SAME merged them).
Degrade: LLM unavailable -> NO new nominations (conservative; geometric
nominations unaffected).

CACHE: out/<scene>/graph/triage_pairs_cache.json keyed "small|host";
entry stores a facts hash (labels + sizes + containment/iou +
PROMPT_VERSION). Rerun re-applies cached NOMINATE verdicts.

Run:
  python graph/triage_pairs.py --scene bedroom_marble
  python graph/triage_pairs.py --scene bedroom_marble --dry   # no LLM, list candidates
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
sys.path.insert(0, str(HERE))
import paths          # noqa: E402
import scene_state    # noqa: E402

MODEL = "sonnet"
CALL_TIMEOUT_S = 480
BATCH = 80                 # items per call (argv-size safety)
PROMPT_VERSION = "1"       # salted into the facts hash -- edits re-triage

T_TRIAGE = """\
{firm}You are a docket clerk for a 3D scene-graph dedup judge. The room's \
detector produced overlapping 3D boxes; a VISUAL judge (with image crops) \
rules whether two detections are the SAME physical object (including a \
partial detection -- a section/board of a bookshelf IS the bookshelf) or \
DISTINCT objects. Crop calls are expensive, so you filter the docket \
using TEXT ONLY.

Each numbered candidate below is a pair where the smaller box sits \
almost entirely inside the larger (containment >= 0.90). Decide per \
pair: NOMINATE (the visual judge should look -- the two could plausibly \
be the same object or a recorded fragment of it, e.g. a "shelf" fully \
inside a "bookshelf" with similar width) or SKIP (obviously an object \
inside/on another object -- contents, not identity: a book inside a \
bookshelf, a toy on a shelf).

BE ASYMMETRIC: when in doubt, NOMINATE. A wrong nomination costs one \
cheap look; a wrong skip ships a duplicate object into the composed \
scene.

Return ONE fenced ```json block, a JSON ARRAY, EXACTLY one object per \
candidate, same order:
{{"idx": <candidate number>, "verdict": "NOMINATE|SKIP", "confidence": \
0.0-1.0, "reason": "one short sentence"}}
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
        raise SystemExit("[triage] claude.exe not on PATH")
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
        return None
    try:
        return json.loads(raw)
    except ValueError:
        return None


def facts_hash(item_txt):
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode())
    h.update(item_txt.encode("utf-8"))
    return h.hexdigest()


def size_txt(n):
    s = n["geometry"]["size"]
    return f'{s[0]:.2f}x{s[1]:.2f}x{s[2]:.2f} m'


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--dry", action="store_true",
                    help="list candidates only; no LLM, no write")
    ap.add_argument("--edges-from", choices=("record", "voted", "voted_edges"),
                    default="record",
                    help="which layer to triage: the record (default, "
                         "lifted boxes) or `voted` (the Phase-B2 "
                         "loop-back, on the boxes the vote elected). "
                         "`voted_edges` is retired and refuses.")
    args = ap.parse_args()

    sdir = paths.scene_dir(args.scene)
    gpath = sdir / "scene_graph.json"
    graph = json.loads(gpath.read_text(encoding="utf-8"))

    # WHICH LAYER'S EDGES. The record's, or a later layer's own — every
    # layer is whole, so its edges live inside it beside its nodes.
    #
    # `voted_edges` WAS a third option and is RETIRED (user ruling
    # 2026-08-11: the map is right, and it draws the half-layer as a
    # tombstone). It is still accepted here only so an old command line
    # out of a handoff fails with this sentence instead of an argparse
    # "invalid choice" that does not say what to do.
    if args.edges_from == "voted_edges":
        raise SystemExit(
            "[triage] --edges-from voted_edges is RETIRED (user ruling "
            "2026-08-11). The Phase-B2 loop-back still runs; it reads the "
            "voted LAYER's own edges now. Use --edges-from voted.")
    view = scene_state.judge_view(graph, args.edges_from)
    det, edges_list, nesting_src = view.nodes, view.edges, view.nesting

    # pairs already before the judge (any source) -- skip
    have = {frozenset((e["a"], e["b"])) for e in edges_list
            if e["type"] == "SAME_CANDIDATE"}
    # pairs already merged into one cluster by a prior SAME -- skip
    same_cluster = set()
    for jn in (graph.get("judged") or {}).get("nodes", []):
        ms = jn.get("members") or []
        for i in range(len(ms)):
            for j in range(i + 1, len(ms)):
                same_cluster.add(frozenset((ms[i], ms[j])))

    cands = []
    for nid, nests in nesting_src.items():
        n = det.get(nid)
        if not n:
            continue
        for nest in nests:
            pair = frozenset((n["id"], nest["host"]))
            if pair in have or pair in same_cluster:
                continue
            host = det.get(nest["host"])
            if not host:
                continue
            item = (f'{n["id"]} "{n["label"]}" ({size_txt(n)}) INSIDE '
                    f'{host["id"]} "{host["label"]}" ({size_txt(host)}) '
                    f'-- containment {nest["containment"]}, '
                    f'iou {nest["iou"]}')
            cands.append({"small": n["id"], "host": nest["host"],
                          "item": item, "nest": nest})

    print(f"[triage] nesting candidates not yet before the judge: "
          f"{len(cands)}")
    if args.dry:
        for c in cands:
            print("   ", c["item"])
        return

    cpath = sdir / "graph" / "triage_pairs_cache.json"
    cache = (json.loads(cpath.read_text(encoding="utf-8"))
             if cpath.exists() else {})

    todo, verdicts = [], {}
    for c in cands:
        key = f'{c["small"]}|{c["host"]}'
        h = facts_hash(c["item"])
        ent = cache.get(key)
        if ent and ent.get("hash") == h:
            verdicts[key] = ent["verdict"]
        else:
            todo.append((key, h, c))
    print(f"[triage] {len(verdicts)} cache hits, {len(todo)} to triage")

    failed = False
    for i0 in range(0, len(todo), BATCH):
        chunk = todo[i0:i0 + BATCH]
        items = "\n".join(f"CANDIDATE {i + 1}: {c['item']}"
                          for i, (_, _, c) in enumerate(chunk))
        got = None
        for firm in ("", FIRM_PREFIX):
            try:
                out = call_claude(T_TRIAGE.format(firm=firm, items=items),
                                  sdir, args.model)
            except (RuntimeError, subprocess.TimeoutExpired) as ex:
                print(f"[triage] call failed: {ex}")
                break
            got = parse_array(out)
            if got:
                break
        if not got:
            failed = True
            continue
        by_idx = {e.get("idx"): e for e in got if isinstance(e, dict)}
        for i, (key, h, c) in enumerate(chunk):
            e = by_idx.get(i + 1)
            ok = (e and e.get("verdict") in ("NOMINATE", "SKIP")
                  and isinstance(e.get("reason"), str))
            if not ok:
                failed = True
                continue
            v = {"verdict": e["verdict"],
                 "confidence": round(min(1.0, max(0.0,
                     float(e.get("confidence") or 0.0))), 2),
                 "reason": e["reason"].strip(),
                 "model": args.model, "date": str(date.today())}
            verdicts[key] = v
            cache[key] = {"hash": h, "verdict": v}

    cpath.parent.mkdir(parents=True, exist_ok=True)
    cpath.write_text(json.dumps(cache, indent=1), encoding="utf-8")

    # ---- write nominations additively (judge-style; idempotent) ----
    nom = 0
    for c in cands:
        key = f'{c["small"]}|{c["host"]}'
        v = verdicts.get(key)
        if not v or v["verdict"] != "NOMINATE":
            continue
        nom += 1
        edges_list.append({
            "type": "SAME_CANDIDATE",
            "a": c["small"], "b": c["host"],
            "evidence": {"iou": c["nest"]["iou"],
                         "containment": c["nest"]["containment"],
                         "zone": "semantic",
                         "center_height_diff_m": round(abs(
                             det[c["small"]]["geometry"]["center"][1]
                             - det[c["host"]]["geometry"]["center"][1]), 3),
                         "labels": [det[c["small"]]["label"],
                                    det[c["host"]]["label"]]},
            "caveats": [], "status": "open",
            "nominated_by": "triage",
            "triage": v})
    skips = sum(1 for v in verdicts.values() if v["verdict"] == "SKIP")
    meta = {"date": str(date.today()), "prompt_version": PROMPT_VERSION,
            "candidates": len(cands), "nominated": nom, "skipped": skips,
            "degraded": failed}
    # the meta rides with the layer that was triaged, so a loop-back pass
    # never overwrites what the record's own pass reported
    view.meta_into["triage_meta"] = meta
    paths.write_atomic(gpath, json.dumps(graph, indent=1))
    print(f"[triage] wrote {gpath} -- {nom} nominated, {skips} skipped"
          + (", DEGRADED (some candidates unjudged)" if failed else ""))
    for c in cands:
        v = verdicts.get(f'{c["small"]}|{c["host"]}')
        if v and v["verdict"] == "NOMINATE":
            print(f'    NOMINATE {c["small"]}+{c["host"]} '
                  f'[{v["confidence"]}]: {v["reason"][:100]}')


if __name__ == "__main__":
    main()
