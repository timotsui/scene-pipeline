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
PROMPT_VERSION = "2"
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
        "note": ("S3 IN-LANE MODULE -- proposals only; adds/deletes land "
                 "at S4 SCREENING (not built yet), the same door as the "
                 "judge's add/delete/replace re-entry. reopen_petitions "
                 "are referrals to the step-2 pair judge (SAME_CANDIDATE) "
                 "+ future screening hold-inputs -- unwired, review-only."),
        "counts": {"delete_candidates": len(cand),
                   "delete_proposed": sum(1 for d in deletes
                                          if d.get("verdict") == "DELETE"),
                   "adds_proposed": len(adds),
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
        print(f"    ADD {a['name']} ({a['support']}) "
              f"[{a['confidence']}]: {a['reason'][:100]}")
    for p in petitions:
        print(f"    PETITION {p['pair'][0]}+{p['pair'][1]} "
              f"({p['names'][0]}/{p['names'][1]}) [{p['confidence']}]: "
              f"{p['evidence'][:100]}")


if __name__ == "__main__":
    main()
