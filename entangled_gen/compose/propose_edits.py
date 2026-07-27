"""
STEP 3 COMPOSE+LOOP -- PROPOSE EDITS (adds + deletes). ISOLATED MODULE.

Built 07-27 on the user's directive: "propose add and delete items --
make sure it's isolated so we can test and review tomorrow." NOTHING
consumes its output yet; it earns a wire into the JUDGE loop's
add/delete channel only after review (pipeline_map.html: dashed arrows).

DELETE proposals -- deterministic aggregation of every doubt signal the
pipeline has already produced, then ONE batched LLM confirm/deny pass:
  - none_plausible objects (supported_by: obj_083 "greenery through a
    window")
  - duplicate suspicions (consistency DROP reasons mentioning duplicates)
  - objects whose EVERY support-type edge was DROPped and whose own
    support confidence is weak
  - existence disputes that shipped unresolved (graph provenance)

ADD proposals -- ONE batched LLM call over the room inventory (canonical
names + counts + support tiers + room size): what obviously-expected
items are missing? STAGE RULE: every add DECLARES its support (floor /
wall / ceiling / on-<anchor id>) so it is physically checkable the
moment it is proposed. Conservative by prompt: few, high-confidence.

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
PROMPT_VERSION = "1"
WEAK_TOP_CONF = 0.5      # top-option confidence below this = weak support

SUPPORT_EDGE_TYPES = ("ON", "IN", "IN_WALL", "ATTACHED")

T_DELETE = """\
{firm}You are auditing DELETE candidates in a 3D scene graph of one \
indoor room. Each numbered candidate below was flagged by earlier \
pipeline passes (support attribution / edge consistency / existence \
checks). For each, decide: should this object be REMOVED from the scene \
model, or KEPT? Removal is right when the evidence says the detection is \
not a real standalone object (ghost, duplicate of another object, \
misread background). Keep when doubt is weak or the object is plausibly \
real despite a bad box.

Return ONE fenced ```json block, a JSON ARRAY, EXACTLY one object per \
candidate, same order:
{{"id": "<the id given>", "verdict": "DELETE|KEEP", "confidence": \
0.0-1.0, "reason": "one sentence"}}
Output ONLY the fenced JSON block.

{items}"""

T_ADD = """\
{firm}You are reviewing the object inventory of ONE reconstructed \
indoor room to propose MISSING items. The reconstruction detects most \
large furniture reliably but misses items that are small, occluded, or \
low-contrast. Below: the room's inventory (canonical names, counts, \
what each rests on) and the room dimensions.

Propose the items that are OBVIOUSLY expected in this room but absent \
from the inventory -- things whose absence would make the composed room \
read as wrong or empty. Be CONSERVATIVE: propose few (0-6), only \
high-confidence, everyday items; no decor filler. Every proposal MUST \
declare its support: "floor", "wall", "ceiling", or "on:<id of an \
inventory object>".

Return ONE fenced ```json block, a JSON ARRAY (may be empty):
{{"name": "<lowercase item name>", "support": "floor|wall|ceiling|\
on:<id>", "where": "one short phrase", "confidence": 0.0-1.0, \
"reason": "one sentence"}}
Output ONLY the fenced JSON block.

{inventory}"""

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

    dup_re = re.compile(r"duplicat", re.IGNORECASE)
    for e in coL["edges"]:
        if e["verdict"] == "DROP" and dup_re.search(e.get("reason", "")):
            for oid in (e["a"], e["b"]):
                if str(oid).startswith("obj_"):
                    flag(oid, f"consistency: possible duplicate "
                              f"({e['a']} -{e['type']}- {e['b']}): "
                              + e["reason"][:140])

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

    for jn in graph["judged"]["nodes"]:
        if jn.get("existence") == "disputed":
            flag(jn["id"], "existence still disputed at graph handoff")

    print(f"[propose_edits] delete candidates: {len(cand)}")
    for oid, sigs in sorted(cand.items()):
        print(f"    {oid} ({names.get(oid, '?')}): {len(sigs)} signal(s)")

    # ---------------- LLM passes ----------------------------------------
    deletes, adds = [], []
    if args.no_llm:
        deletes = [{"id": oid, "name": names.get(oid),
                    "signals": sigs, "status": "CANDIDATE",
                    "verdict": None}
                   for oid, sigs in sorted(cand.items())]
        print("[propose_edits] --no-llm: candidates written unconfirmed, "
              "no adds proposed")
    else:
        # delete confirm/deny
        if cand:
            items = []
            for i, (oid, sigs) in enumerate(sorted(cand.items()), 1):
                o = sb.get(oid, {})
                top = (o.get("supported_by") or [{}])[0]
                items.append(
                    f'CANDIDATE {i}: {oid} "{names.get(oid, "?")}" -- '
                    f'current support: {top.get("how")} '
                    f'{top.get("supporter")} ({top.get("confidence")})\n'
                    + "\n".join(f"  signal: {s}" for s in sigs))
            got = None
            for firm in ("", FIRM_PREFIX):
                try:
                    out = call_claude(
                        T_DELETE.format(firm=firm, items="\n\n".join(items)),
                        cdir, args.model)
                except (RuntimeError, subprocess.TimeoutExpired) as ex:
                    print(f"[propose_edits] delete pass failed: {ex}")
                    break
                got = parse_array(out)
                if got:
                    break
            by_id = {e.get("id"): e for e in (got or [])
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
        # add proposals
        inv = {}
        for o in sbL["objects"]:
            top = (o.get("supported_by") or [{}])[0]
            key = names.get(o["id"], "?")
            inv.setdefault(key, []).append(
                f'{o["id"]} ({top.get("how")} {top.get("supporter")})')
        shell = {n["id"]: n["geometry"]["plane"]["value_raw"]
                 for n in graph["nodes"] if n["id"].startswith("arch_")}
        dims = (f'room ~{abs(shell["arch_wall_x_low"] - shell["arch_wall_x_high"]):.1f} x '
                f'{abs(shell["arch_wall_z_low"] - shell["arch_wall_z_high"]):.1f} m, '
                f'height {abs(shell["arch_ceiling"] - shell["arch_floor"]):.1f} m')
        lines = [dims, "", "INVENTORY (name x count -- members):"]
        for k in sorted(inv):
            lines.append(f"  {k} x{len(inv[k])}: {'; '.join(inv[k][:6])}")
        got = None
        for firm in ("", FIRM_PREFIX):
            try:
                out = call_claude(
                    T_ADD.format(firm=firm, inventory="\n".join(lines)),
                    cdir, args.model)
            except (RuntimeError, subprocess.TimeoutExpired) as ex:
                print(f"[propose_edits] add pass failed: {ex}")
                break
            got = parse_array(out)
            if got is not None:
                break
        valid_ids = set(names)
        for e in (got or []):
            if not isinstance(e, dict):
                continue
            name = e.get("name")
            sup = str(e.get("support", ""))
            sup_ok = sup in ("floor", "wall", "ceiling") or (
                sup.startswith("on:") and sup[3:] in valid_ids)
            if not isinstance(name, str) or not name.strip() or not sup_ok:
                continue
            adds.append({"name": name.strip().lower(), "support": sup,
                         "where": str(e.get("where", "")).strip(),
                         "confidence": conf_of(e.get("confidence")),
                         "reason": str(e.get("reason", "")).strip()})

    layer = {
        "scene": args.scene, "built": str(date.today()),
        "generated_by": "compose/propose_edits.py",
        "model": None if args.no_llm else args.model,
        "prompt_version": PROMPT_VERSION,
        "note": ("ISOLATED MODULE -- proposals only, nothing consumes "
                 "this yet (map: dashed arrows). Intended landing: the "
                 "JUDGE loop's add/delete channel."),
        "counts": {"delete_candidates": len(cand),
                   "delete_proposed": sum(1 for d in deletes
                                          if d.get("verdict") == "DELETE"),
                   "adds_proposed": len(adds)},
        "deletes": deletes,
        "adds": adds,
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
        print(f"    ADD {a['name']} ({a['support']}) "
              f"[{a['confidence']}]: {a['reason'][:100]}")


if __name__ == "__main__":
    main()
