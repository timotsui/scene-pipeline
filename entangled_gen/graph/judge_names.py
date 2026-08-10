"""
Pass 2 -- JUDGE, sub-pass J3: canonical NAMES for disputed clusters.

Consumes graph["judged"]["naming_queue"] (build_judged.py): every merge
cluster whose members disagree on the label (chair/office-chair,
door/window x3, lamp/ceiling-light, mat/rug/yoga-mat, ...). This is the
fix for the R9 finding -- detector score picked "lamp" for a ceiling
fixture; the score is a detection strength, not a naming authority.

Per cluster the VLM gets: member crops + the candidate labels + cheap
facts a deterministic filler derives from the judged view (size, height
span, wall/ceiling attachment, what it rests on, what it contains).
Batched (BATCH_SIZE clusters per call). It returns the best name --
normally one of the candidates; a different short name is accepted but
flagged "chosen_from_candidates": false (coherence-judge food).

PROMPT SCHEMA: fixed versioned template (PROMPT_VERSION salted into the
cache hash), deterministic filler, nothing authored per case -- the
judge_near.py v2 lesson (REVIEW_LOG R12): code interprets the numbers,
the model interprets the pixels.

WRITE-BACK (additive-only): the judged cluster gets name = the verdict,
name_provisional -> false, plus a "naming" provenance block. The record
nodes keep their original labels untouched. Failures keep the
provisional name and name_provisional: true -- conservative degradation.
Cache: out/<scene>/graph/judge_names_cache.json keyed by cluster id.

Run:
  python graph/judge_names.py --scene bedroom_marble
  python graph/judge_names.py --scene bedroom_marble --smoke  # 1 batch, no write
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
BATCH_SIZE = 5
CROPS_PER_CLUSTER = 2
PROMPT_VERSION = "1"

TEMPLATE = """\
{firm}You are naming objects extracted from a 3D scan of one indoor \
room. Different views of each object were auto-labeled inconsistently; \
for EACH numbered item, open its crop image file(s) (absolute paths \
given), weigh the stated facts, and pick the single best everyday name.

Prefer one of the item's candidate names. Only answer something else if \
the crops clearly show all candidates are wrong; keep any name lowercase \
and at most 3 words.

Return ONE fenced ```json block containing a JSON ARRAY with EXACTLY one \
object per item, same order:
{{"id": "<the id given>", "name": "<chosen name>", "confidence": 0.0-1.0, \
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
        raise SystemExit("[judge_names] claude.exe not on PATH")
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


def parse_response(text, want_ids):
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
        if not isinstance(e, dict) or e.get("id") not in want_ids:
            continue
        name = e.get("name")
        if not isinstance(name, str) or not name.strip() \
                or len(name.split()) > 3:
            continue
        try:
            conf = float(e.get("confidence"))
        except (TypeError, ValueError):
            continue
        if not isinstance(e.get("reason"), str) or not e["reason"].strip():
            continue
        good[e["id"]] = {"name": name.strip().lower(),
                         "confidence": round(min(1.0, max(0.0, conf)), 2),
                         "reason": e["reason"].strip()}
    return good


def cluster_crops(jn, det, crops_dir):
    """Best-scoring crop of each member (diversity), cap CROPS_PER_CLUSTER."""
    per_member = []
    for mid in jn["members"]:
        ms = sorted(det[mid]["evidence"].get("members", []),
                    key=lambda m: -m.get("score", 0.0))
        for m in ms:
            p = crops_dir / m.get("crop", "")
            if m.get("crop") and p.exists():
                per_member.append((m.get("score", 0.0), p))
                break
    per_member.sort(key=lambda t: -t[0])
    return [p for _, p in per_member[:CROPS_PER_CLUSTER]]


def cluster_facts(jn, judged, floor_y):
    g = jn["geometry"]
    s = g["size"]
    bottom = floor_y - g["aabb_max"][1]
    top = floor_y - g["aabb_min"][1]
    facts = [f"size WxDxH = {s[0]:.2f}x{s[2]:.2f}x{s[1]:.2f} m, spans "
             f"{bottom:.2f}-{top:.2f} m above the floor"]
    contains = 0
    for e in judged["edges"]:
        if e["a"] == jn["id"]:
            if e["type"] == "ON":
                tgt = e["b"].replace("arch_", "")
                facts.append(f"rests on {tgt}")
            elif e["type"] == "IN_WALL":
                facts.append("mounted in/on a wall")
            elif e["type"] == "ATTACHED":
                facts.append("attached to the ceiling")
        elif e["b"] == jn["id"] and e["type"] == "IN":
            contains += 1
    if contains:
        facts.append(f"contains {contains} smaller detected objects")
    return facts


def item_block(i, jn, crops, facts):
    lines = [f'Item {i}: id={jn["id"]}, candidate names: '
             + ", ".join(f'"{l}"' for l in jn["distinct_labels"])]
    lines += [f"  fact: {f}" for f in facts]
    lines += ["  crop file(s):"] + [f"    {p}" for p in crops]
    return "\n".join(lines)


def evidence_hash(crop_paths, jn):
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode())
    for p in sorted(str(p) for p in crop_paths):
        h.update(Path(p).read_bytes())
    h.update(json.dumps({"labels": jn["distinct_labels"],
                         "geometry": jn["geometry"]},
                        sort_keys=True).encode())
    return h.hexdigest()[:32]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    gdir = paths.scene_dir(args.scene)
    gpath = gdir / "scene_graph.json"
    crops_dir = gdir / "graph" / "crops"
    cache_path = gdir / "graph" / "judge_names_cache.json"
    graph = json.loads(gpath.read_text())
    judged = graph.get("judged")
    if not judged:
        raise SystemExit("[judge_names] no judged view -- run "
                         "build_judged.py first")
    det = {n["id"]: n for n in graph["nodes"] if n["source"] == "detection"}
    floor_y = next(n for n in graph["nodes"] if n["id"] == "arch_floor")[
        "geometry"]["plane"]["value_raw"]
    jn_by_id = {n["id"]: n for n in judged["nodes"]}
    queue = [jn_by_id[r] for r in judged.get("naming_queue", [])]

    cache = (json.loads(cache_path.read_text())
             if cache_path.exists() else {"meta": {"calls": 0}, "nodes": {}})

    todo, hits = [], 0
    for jn in queue:
        crops = cluster_crops(jn, det, crops_dir)
        ehash = evidence_hash(crops, jn)
        ent = cache["nodes"].get(jn["id"])
        if ent and ent.get("evidence_hash") == ehash:
            jn["name"] = ent["verdict"]["name"]
            jn["name_provisional"] = False
            jn["naming"] = ent["verdict"]
            hits += 1
            continue
        todo.append((jn, ehash, crops))

    print(f"[judge_names] queue {len(queue)} clusters: {hits} cache hits, "
          f"{len(todo)} to judge (model {args.model}, prompt v"
          f"{PROMPT_VERSION}, batches of {BATCH_SIZE})")

    batches = [todo[i:i + BATCH_SIZE]
               for i in range(0, len(todo), BATCH_SIZE)]
    if args.smoke:
        batches = batches[:1]
    calls = 0
    failed = []
    for batch in batches:
        want = {jn["id"] for jn, _, _ in batch}
        got = {}
        for attempt, firm in ((1, False), (2, True)):
            items = "\n\n".join(
                item_block(i + 1, jn,
                           crops, cluster_facts(jn, judged, floor_y))
                for i, (jn, _, crops) in enumerate(batch))
            prompt = TEMPLATE.format(
                firm=FIRM_PREFIX if firm else "", items=items)
            try:
                out = call_claude(prompt, crops_dir, args.model)
                calls += 1
            except (RuntimeError, subprocess.TimeoutExpired) as ex:
                print(f"[judge_names]   batch failed ({ex})")
                continue
            got = parse_response(out, want)
            if len(got) == len(want):
                break
            print(f"[judge_names]   batch returned {len(got)}/{len(want)} "
                  f"valid (attempt {attempt})")
        for jn, ehash, crops in batch:
            v = got.get(jn["id"])
            if v is None:
                failed.append(jn["id"])   # provisional name stands
                continue
            v_full = {**v,
                      "chosen_from_candidates":
                          v["name"] in [l.lower()
                                        for l in jn["distinct_labels"]],
                      "model": args.model,
                      "date": date.today().isoformat(),
                      "prompt_version": PROMPT_VERSION,
                      "evidence_hash": ehash, "source": "judge_names"}
            jn["name"] = v["name"]
            jn["name_provisional"] = False
            jn["naming"] = v_full
            cache["nodes"][jn["id"]] = {"evidence_hash": ehash,
                                        "verdict": v_full}

    for jn in queue:
        tag = ("PROVISIONAL" if jn.get("name_provisional")
               else jn["naming"].get("reason", ""))
        print(f'  {jn["id"]} {jn["distinct_labels"]} -> "{jn["name"]}" '
              f'-- {tag}')

    if args.smoke:
        print("[judge_names] SMOKE -- no write-back")
        return

    cache["meta"]["calls"] = cache["meta"].get("calls", 0) + calls
    cache_path.write_text(json.dumps(cache, indent=1))
    named = sum(1 for jn in queue if not jn.get("name_provisional"))
    judged["naming_meta"] = {"model": args.model,
                             "last_run": date.today().isoformat(),
                             "prompt_version": PROMPT_VERSION,
                             "cumulative_calls": cache["meta"]["calls"],
                             "named": named,
                             "provisional": len(queue) - named}
    gpath.write_text(json.dumps(graph, indent=1))
    print(f"[judge_names] wrote {gpath} -- {named}/{len(queue)} named"
          + (f" (PROVISIONAL kept: {failed})" if failed else ""))


if __name__ == "__main__":
    main()
