"""
Pass 2 -- JUDGE, sub-pass J4: the COHERENCE judge ("does it make sense").

User-designed pass (2026-07-26): TEXT-ONLY, no images. A deterministic
digest builder flattens the JUDGED view (post-merge clusters with their
canonical names, the architecture, every edge with its numbers) into a
plain-text inventory of the room -- and ONE call asks the model to flag
every fact that could not be true of a real room:

    relation        physically implausible relation (a picture INSIDE a
                    door's volume)
    existence       a flagged relation + feeble evidence (single weak
                    detection) => the node may not exist at all
                    (motivating case: obj_138 "picture", 1 view @ 0.32,
                    100% inside the door/window pair)
    label_geometry  name vs measurements clash (a 0.3 m-wide "bed")

Because the digest is the WHOLE room in text, this costs 1-2 calls per
scene regardless of object count -- the cheap graph-level complement to
the per-object crop judges.

FLAGS, NEVER DELETIONS (write-back additive-only): each flag carries
target / kind / issue / hypotheses / suggested_action. A node flagged
"existence_disputed" gets existence: "disputed" on its judged cluster --
the record keeps everything; downstream consumers skip disputed nodes.
Flags whose target id doesn't exist are dropped (logged). Failures =>
no flags => nothing disputed (conservative degradation).
"reexamine_with_crops" flags are the v2 escalation hook (targeted vision
calls) -- recorded, not yet consumed.

PROMPT SCHEMA: fixed versioned template + deterministic digest filler
(PROMPT_VERSION salted into the cache hash; cache keyed by digest hash --
any change to the judged view re-judges). Nothing scene-specific: the
prompt is the graph's own facts plus room common sense.

Run:
  python graph/judge_coherence.py --scene bedroom_marble
  python graph/judge_coherence.py --scene bedroom_marble --digest-only
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
PROMPT_VERSION = "3"   # v2: digest carries case resolutions; v3: names
                       # marked pixel-checked + historical notes are not
                       # authoritative over current names
KINDS = ("relation", "existence", "label_geometry")
ACTIONS = ("existence_disputed", "rename_candidate",
           "reexamine_with_crops", "none")

TEMPLATE = """\
{firm}Below is the complete extracted inventory of ONE real indoor room, \
from a 3D scan: every object (with its measured size, height above the \
floor, and detection strength) and every spatial relationship (with its \
measured numbers). The extraction is imperfect: boxes can be wrong, \
labels can be wrong, and some detections may not be real objects at all.

Read the WHOLE inventory and flag every fact that does not make sense \
for a real room. Kinds of nonsense to look for:
- "relation": a physically implausible relationship (e.g. a picture \
INSIDE a door's volume, an object resting on something implausible)
- "existence": an implausible relation on an object with feeble evidence \
(one weak-detection view) -- the object may not exist at all
- "label_geometry": a name that clashes with the measurements (e.g. a \
0.3 m-wide "bed", a "rug" floating at 2 m height)

Do NOT flag facts that are merely unusual but possible. Weigh detection \
strength: an object seen in many views with high scores exists; one \
weak single-view detection inside another object's volume is suspect.
Facts annotated [resolved: ...] or [pixel-check ...] were ALREADY \
adjudicated with image evidence -- do not re-flag them unless they \
contradict something else in the inventory. [resolved: ...] notes are \
HISTORICAL adjudication records; the node's CURRENT name is \
authoritative -- do not flag a name merely for disagreeing with old \
note prose. Names annotated [name pixel-checked] were chosen or \
confirmed by looking at the object's actual crops -- do not second-\
guess them from measurements alone.

Return ONE fenced ```json block containing a JSON ARRAY (possibly \
empty) of flags:
{{"target": "<node id, or 'a->b' for an edge>", \
"kind": "relation|existence|label_geometry", \
"issue": "one sentence", \
"hypotheses": ["short strings"], \
"suggested_action": "existence_disputed|rename_candidate|\
reexamine_with_crops|none", \
"confidence": 0.0-1.0}}
Output ONLY the fenced JSON block.

ROOM:
{room}

OBJECTS (id, name, width x depth x height in meters, vertical span above \
the floor, evidence):
{nodes}

RELATIONSHIPS:
{edges}"""

FIRM_PREFIX = ("Your previous response was malformed. This time output "
               "ONLY one fenced ```json code block containing the JSON "
               "array, no prose.\n\n")


# --------------------------------------------------------------------------
# deterministic digest
# --------------------------------------------------------------------------

def build_digest(graph):
    judged = graph["judged"]
    env = {n["id"]: n for n in graph["nodes"] if n["source"] == "envelope"}
    floor_y = env["arch_floor"]["geometry"]["plane"]["value_raw"]
    ceil_y = env["arch_ceiling"]["geometry"]["plane"]["value_raw"]
    xs, zs = [], []
    for nid, n in env.items():
        p = n["geometry"].get("plane", {})
        if nid.startswith("arch_wall"):
            (xs if p.get("axis") == "x" else zs).append(p["value_raw"])
    room = (f"{abs(max(xs) - min(xs)):.1f} x {abs(max(zs) - min(zs)):.1f} m "
            f"floor area, ceiling height {abs(ceil_y - floor_y):.2f} m. "
            f"Architecture ids: arch_floor, arch_ceiling, "
            + ", ".join(sorted(nid for nid in env
                               if nid.startswith("arch_wall"))) + ".")

    rejected = {jn["id"] for jn in judged["nodes"]
                if jn.get("existence") == "rejected"}
    node_lines = []
    for jn in sorted(judged["nodes"], key=lambda n: n["id"]):
        if jn["id"] in rejected:
            continue          # pixel-checked NOT_REAL: out of the digest
        g = jn["geometry"]
        s = g["size"]
        bottom = floor_y - g["aabb_max"][1]
        top = floor_y - g["aabb_min"][1]
        extras = []
        if len(jn["members"]) > 1:
            extras.append(f"merged from {len(jn['members'])} duplicate "
                          f"detections")
        if jn.get("name_provisional"):
            extras.append("name provisional")
        if jn.get("existence") == "disputed":
            extras.append("existence disputed -- unresolved")
        elif jn.get("existence") == "confirmed":
            extras.append("pixel-check REAL: "
                          + jn.get("existence_verdict", {})
                              .get("reason", "")[:90])
        if jn.get("naming", {}).get("source") in ("judge_names",
                                                  "judge_cases"):
            extras.append("name pixel-checked")
        node_lines.append(
            f'{jn["id"]}  {jn["name"]}  '
            f'{s[0]:.2f}x{s[2]:.2f}x{s[1]:.2f} m, spans '
            f'{bottom:.2f}-{top:.2f} m, seen in '
            f'{jn["n_detections"]} views (peak score '
            f'{jn["peak_score"]:.2f})'
            + (f' [{"; ".join(extras)}]' if extras else ""))

    name_of = {jn["id"]: jn["name"] for jn in judged["nodes"]}
    confirmed_reason = {jn["id"]: jn.get("existence_verdict", {})
                        .get("reason", "")
                        for jn in judged["nodes"]
                        if jn.get("existence") == "confirmed"}

    def nm(x):
        return name_of.get(x, x.replace("arch_", ""))

    edge_lines = []
    for e in sorted(judged["edges"],
                    key=lambda e: (e["type"], e["a"], e["b"])):
        ev = e["evidence"]
        t = e["type"]
        a, b = e["a"], e["b"]
        if a in rejected or b in rejected:
            continue          # edges of pixel-rejected nodes die with them
        if t == "ON":
            d = f'gap {ev.get("gap_m", 0):+.2f} m'
        elif t == "IN":
            d = f'{ev.get("frac_of_smaller", 0):.0%} of it inside'
        elif t == "IN_WALL":
            d = f'{ev.get("wall_distance_m", 0):.2f} m from the wall plane'
        elif t == "ATTACHED":
            d = f'{ev.get("ceiling_distance_m", 0):.2f} m from the ceiling'
        elif t == "INTERPENETRATES":
            d = (f'boxes overlap {ev.get("frac_of_smaller", 0):.0%} of '
                 f'the smaller')
        elif t == "PART_OF":   # legacy edge type (retired 08-01)
            d = "judged a component of it"
        else:
            d = "unresolved fallback"
        cv = e.get("case_verdict")
        if cv:
            d += (f' [resolved: {cv.get("edge_verdict")} -- '
                  f'{cv.get("true_arrangement", "")[:100]}]')
        elif e.get("resolved_by") == "judge_near":
            jv = e.get("verdict", {})
            d += (" [pixel-check: contact is real"
                  + ("; the detected box UNDER-REACHES the true object "
                     "(occluded base / thin mount) -- the gap is a box "
                     "artifact" if jv.get("box_underreach") else "")
                  + "]")
        else:
            for x in (a, b):
                if x in confirmed_reason:
                    d += (f' [pixel-check: {x} is a real object; '
                          f'box overlap judged a measurement artifact]')
                    break
        edge_lines.append(f'{a} ({nm(a)}) {t} {b} ({nm(b)}) -- {d}')

    return room, "\n".join(node_lines), "\n".join(edge_lines)


# --------------------------------------------------------------------------
# claude bridge (project pattern)
# --------------------------------------------------------------------------

def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)  # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd, model):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[judge_coherence] claude.exe not on PATH")
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


def parse_flags(text, node_ids, edge_keys):
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
        return None
    try:
        arr = json.loads(raw)
    except ValueError:
        return None
    if not isinstance(arr, list):
        return None
    good, dropped = [], []
    for f in arr:
        if not isinstance(f, dict):
            continue
        tgt = f.get("target", "")
        known = (tgt in node_ids
                 or tuple(tgt.split("->")) in edge_keys)
        if not known:
            dropped.append(tgt)
            continue
        if f.get("kind") not in KINDS \
                or f.get("suggested_action") not in ACTIONS:
            dropped.append(tgt)
            continue
        if not isinstance(f.get("issue"), str) or not f["issue"].strip():
            dropped.append(tgt)
            continue
        try:
            conf = float(f.get("confidence"))
        except (TypeError, ValueError):
            conf = 0.0
        hyp = f.get("hypotheses")
        good.append({"target": tgt, "kind": f["kind"],
                     "issue": f["issue"].strip(),
                     "hypotheses": [str(x) for x in hyp][:5]
                     if isinstance(hyp, list) else [],
                     "suggested_action": f["suggested_action"],
                     "confidence": round(min(1.0, max(0.0, conf)), 2)})
    return {"flags": good, "dropped_targets": dropped}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--model", default=MODEL)
    ap.add_argument("--digest-only", action="store_true",
                    help="print the digest, no LLM call, no write")
    args = ap.parse_args()

    gdir = paths.scene_dir(args.scene)
    gpath = gdir / "scene_graph.json"
    cache_path = gdir / "graph" / "judge_coherence_cache.json"
    graph = json.loads(gpath.read_text())
    judged = graph.get("judged")
    if not judged:
        raise SystemExit("[judge_coherence] no judged view -- run "
                         "build_judged.py first")

    room, nodes_txt, edges_txt = build_digest(graph)
    if args.digest_only:
        print(f"ROOM:\n{room}\n\nOBJECTS:\n{nodes_txt}\n\n"
              f"RELATIONSHIPS:\n{edges_txt}")
        return

    digest_hash = hashlib.sha256(
        (PROMPT_VERSION + room + nodes_txt + edges_txt).encode()
    ).hexdigest()[:32]
    cache = (json.loads(cache_path.read_text())
             if cache_path.exists() else {"meta": {"calls": 0}})

    node_ids = ({jn["id"] for jn in judged["nodes"]}
                | set(judged.get("arch_nodes", [])))
    edge_keys = {(e["a"], e["b"]) for e in judged["edges"]}

    if cache.get("digest_hash") == digest_hash:
        result = cache["result"]
        print(f"[judge_coherence] cache hit ({digest_hash})")
    else:
        result = None
        for attempt, firm in ((1, False), (2, True)):
            prompt = TEMPLATE.format(firm=FIRM_PREFIX if firm else "",
                                     room=room, nodes=nodes_txt,
                                     edges=edges_txt)
            try:
                out = call_claude(prompt, gdir, args.model)
                cache["meta"]["calls"] = cache["meta"].get("calls", 0) + 1
            except (RuntimeError, subprocess.TimeoutExpired) as ex:
                print(f"[judge_coherence] call failed ({ex})")
                continue
            result = parse_flags(out, node_ids, edge_keys)
            if result is not None:
                break
            print(f"[judge_coherence] malformed (attempt {attempt})")
        if result is None:
            print("[judge_coherence] FAILED -- no flags written "
                  "(conservative: nothing disputed)")
            sys.exit(1)
        cache.update({"digest_hash": digest_hash, "result": result,
                      "model": args.model,
                      "date": date.today().isoformat()})
        cache_path.write_text(json.dumps(cache, indent=1))

    # ---- apply (additive) ----
    jn_by_id = {jn["id"]: jn for jn in judged["nodes"]}
    disputed = []
    for f in result["flags"]:
        if f["suggested_action"] != "existence_disputed":
            continue
        # an edge-targeted existence flag disputes the edge's SUBJECT
        # (the "a" side -- "picture inside door" suspects the picture).
        # Pixel verdicts outrank text: confirmed/rejected are final here
        # (a text re-flag of a pixel-checked node is surfaced in the
        # flags list but does NOT flip the status).
        tgt = f["target"].split("->")[0]
        if tgt in jn_by_id and jn_by_id[tgt].get("existence") not in (
                "confirmed", "rejected"):
            jn_by_id[tgt]["existence"] = "disputed"
            disputed.append(tgt)
    judged["coherence_flags"] = result["flags"]
    judged["coherence_meta"] = {
        "model": args.model, "last_run": date.today().isoformat(),
        "prompt_version": PROMPT_VERSION, "digest_hash": digest_hash,
        "cumulative_calls": cache["meta"]["calls"],
        "flags": len(result["flags"]),
        "existence_disputed": disputed,
        "dropped_targets": result["dropped_targets"]}
    gpath.write_text(json.dumps(graph, indent=1))

    print(f"[judge_coherence] {len(result['flags'])} flags "
          f"(digest {digest_hash}):")
    for f in result["flags"]:
        print(f'  [{f["kind"]:14s}] {f["target"]}: {f["issue"]} '
              f'-> {f["suggested_action"]} (conf {f["confidence"]}) '
              f'hyp={f["hypotheses"]}')
    if result["dropped_targets"]:
        print(f"[judge_coherence] dropped unknown targets: "
              f"{result['dropped_targets']}")
    print(f"[judge_coherence] existence disputed: {disputed or 'none'}")
    print(f"[judge_coherence] wrote {gpath}")


if __name__ == "__main__":
    main()
