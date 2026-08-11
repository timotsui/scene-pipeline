"""
Pass 3 -- RESOLVED layer (user directive 2026-07-26: "allow the judge's
comment to affect the boxes"): materialize the J4/J6 verdicts into the
box/edge set downstream stages actually consume.

Design (user rulings 2026-07-26):
  - Output = a THIRD additive layer in scene_graph.json:
    record -> judged -> resolved. Record and judged stay immutable
    audit trails; the compose stage reads graph["resolved"].
  - RELATIONS ONLY: no box geometry surgery here. suspect_box work
    orders ride along untouched for the compose/placement stage.

What it does:
  NODES  every shipping judged cluster is copied through (id, name,
         geometry); existence rejected / structure / disputed nodes are
         REMOVED from the shipping set and listed in resolved.removed
         with their verdict provenance.
  EDGES  judged edges are copied through, except:
           endpoint removed        -> dropped (reason recorded)
           case_verdict REJECT     -> dropped (judge: boxes merely
                                      overlap, no real relationship)
           case_verdict REINTERPRET-> the free-text true_arrangement is
                                      mapped by ONE batched LLM call
                                      into the closed edge vocabulary
                                      {ON, IN, ATTACHED, NEAR, NONE};
                                      NONE drops the edge, otherwise the
                                      edge is rewritten (old type +
                                      sentence kept as provenance).
  Degradation (standing rule): if the LLM bridge is unavailable or the
  reply is malformed after one firmer retry, REINTERPRET edges keep
  their original type with status "unresolved_reinterpret" -- honest,
  nothing fabricated. Mapping calls are cached (resolve_cache.json,
  PROMPT_VERSION-salted) so reruns are free.

SHRINK PHASE -- RETIRED FROM THIS STAGE (user contract ruling
2026-07-26: "shrinking is too much of a problem before the next
stage; the scene-graph stage stops here and hands off the graph
WITHOUT the shrink"). The machinery below stays runnable behind
--shrink (off by default) as the donor code for placement-stage box
surgery, with its debugged lessons on record:
  - the curtain trace (2026-07-26): the geometrically-minimal cut was
    "hover the curtain 1.37 m off the floor"; the executed x-cut was
    rationalized as "room-facing" but x was the along-wall WIDTH; the
    truly correct cut (slim the z depth against the wall) was
    inexpressible because the lamp's own box -- which J4 had already
    hypothesized was mis-sized -- spanned the curtain's whole depth.
  - fixes identified for the placement-stage version: a BAD_MENU
    verdict distinct from KEEP; partner-box cuts on the same menu;
    wall orientation from the shell in the cut descriptions; no
    pattern-matchable concrete examples in the template.
Without --shrink, resolved nodes carry judged geometry VERBATIM and
suspect_box work orders ship untouched -- that is the contract.

Run:
  python graph/materialize_verdicts.py --scene bedroom_marble --dry-run
  python graph/materialize_verdicts.py --scene bedroom_marble
"""
import argparse
import hashlib
import json
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import paths  # noqa: E402
import judge_cases as jc  # noqa: E402
import scene_state  # noqa: E402

PROMPT_VERSION = "1"
SHRINK_PROMPT_VERSION = "1"
RELATIONS = ("ON", "IN", "ATTACHED", "NEAR", "NONE")
REMOVE_STATES = ("rejected", "structure", "disputed")
SHRINK_CLEAR_M = 0.005     # clearance left after a face pull
SHRINK_MAX_LOSS = 0.75     # refuse cuts removing more than this volume

T_MAP = """\
{firm}A scene-understanding judge re-examined physically implausible \
object relationships and wrote, for each pair, one sentence stating \
what is actually true. Convert each sentence into ONE machine edge \
from this closed vocabulary:
  "ON"       -- subject rests on / is supported by the object
  "IN"       -- subject is genuinely inside the object
  "ATTACHED" -- subject is fixed to the object (mounted, clipped)
  "NEAR"     -- real spatial adjacency worth keeping, but no support
                or containment
  "NONE"     -- no meaningful relationship; the edge should be deleted
Pick the closest fit to the SENTENCE (not to the old edge). "a"/"b" \
below name the two objects; return which is the subject.
Return ONE fenced ```json block, a JSON ARRAY, one object per case, \
same order:
{{"case": <n>, "type": "ON|IN|ATTACHED|NEAR|NONE", \
"subject": "<id or null for NONE>", "object": "<id or null>", \
"confidence": 0.0-1.0}}
Output ONLY the fenced JSON block.

{items}"""


T_SHRINK = """\
{firm}A scene judge re-examined implausible object relationships in a \
3D scan and, per case, named ONE bounding box as suspect (likely \
oversized / inflated with empty volume). For each case below you get \
the judge's sentence, both boxes' numbers, and a lettered menu of \
CANDIDATE CUTS (computed deterministically -- each pulls exactly one \
face of the suspect box just far enough to fully clear the other \
object). Decide:
  - a cut letter -- the suspect box is genuinely inflated AND that cut \
matches physical reality (e.g. a thin curtain whose box bulges into \
the room: retract its room-facing face). Pick the cut that leaves a \
PHYSICALLY SENSIBLE box, not merely the smallest cut -- e.g. never \
hover a floor-length curtain off the floor, never cut a chair off at \
the knees.
  - "KEEP" -- the box's extent is legitimate even though the other \
object sits inside it (e.g. a chair whose box rightly spans the open \
space between its legs, with a basket in that space). Overlap is \
tolerated downstream.
When genuinely unsure, prefer KEEP (a wrong cut destroys measured \
extent; a kept overlap is only noise).
Return ONE fenced ```json block, a JSON ARRAY, one object per case, \
same order:
{{"case": <n>, "choice": "<cut letter or KEEP>", \
"confidence": 0.0-1.0, "reason": "one sentence"}}
Output ONLY the fenced JSON block.

{items}"""


def overlap_volume(a, b):
    v = 1.0
    for i in range(3):
        lo = max(a["aabb_min"][i], b["aabb_min"][i])
        hi = min(a["aabb_max"][i], b["aabb_max"][i])
        if hi <= lo:
            return 0.0
        v *= hi - lo
    return v


def volume(g):
    return max(0.0, (g["aabb_max"][0] - g["aabb_min"][0])
               * (g["aabb_max"][1] - g["aabb_min"][1])
               * (g["aabb_max"][2] - g["aabb_min"][2]))


def candidate_trims(sus, oth, floor_y):
    """Every valid single-face pull of `sus` that fully clears `oth`
    (+SHRINK_CLEAR_M), each with a plain-language description built
    from the RAW frame convention (physical up = -y, floor at the
    numeric MAX y). Code computes the numbers; the model only PICKS.
    Returns [{geometry, face, loss, desc}] sorted by loss."""
    v0 = volume(sus)
    if v0 <= 0:
        return []
    axes = ("x", "y", "z")
    out = []
    for i in range(3):
        for side, new_lo, new_hi in (
                ("max", sus["aabb_min"][i],
                 oth["aabb_min"][i] - SHRINK_CLEAR_M),
                ("min", oth["aabb_max"][i] + SHRINK_CLEAR_M,
                 sus["aabb_max"][i])):
            if new_hi - new_lo <= 0.01:      # degenerate box
                continue
            g = {"aabb_min": list(sus["aabb_min"]),
                 "aabb_max": list(sus["aabb_max"])}
            g["aabb_min"][i], g["aabb_max"][i] = new_lo, new_hi
            if overlap_volume(g, oth) > 0:
                continue
            loss = 1.0 - volume(g) / v0
            if loss > SHRINK_MAX_LOSS:
                continue
            g["center"] = [(g["aabb_min"][k] + g["aabb_max"][k]) / 2
                           for k in range(3)]
            g["size"] = [g["aabb_max"][k] - g["aabb_min"][k]
                         for k in range(3)]
            if i == 1:      # vertical axis: describe in floor terms
                if side == "max":
                    desc = (f"RAISE its BOTTOM off the floor: box would "
                            f"start {floor_y - g['aabb_max'][1]:.2f} m "
                            f"above the floor, ENTIRELY ABOVE the other "
                            f"object")
                else:
                    desc = (f"LOWER its TOP: box would end "
                            f"{floor_y - g['aabb_min'][1]:.2f} m above "
                            f"the floor, ENTIRELY BELOW the other "
                            f"object")
            else:
                desc = (f"RETRACT it horizontally along {axes[i]} "
                        f"(remove the {'far' if side == 'max' else 'near'}"
                        f"-{axes[i]} slab) so it stops beside the other "
                        f"object; {axes[i]} extent becomes "
                        f"[{g['aabb_min'][i]:.2f},{g['aabb_max'][i]:.2f}]"
                        f" ({g['size'][i]:.2f} m thick)")
            desc += (f" -- removes {loss:.0%} of the volume, box becomes "
                     f"{g['size'][0]:.2f}x{g['size'][1]:.2f}x"
                     f"{g['size'][2]:.2f} m")
            out.append({"geometry": g,
                        "face": f'{"-" if side == "min" else "+"}'
                                f'{axes[i]}',
                        "loss": loss, "desc": desc})
    return sorted(out, key=lambda t: t["loss"])


def geom_facts(gid, name, g):
    return (f'{gid} "{name}": x [{g["aabb_min"][0]:.2f},'
            f'{g["aabb_max"][0]:.2f}] y [{g["aabb_min"][1]:.2f},'
            f'{g["aabb_max"][1]:.2f}] z [{g["aabb_min"][2]:.2f},'
            f'{g["aabb_max"][2]:.2f}] '
            f'({g["size"][0]:.2f}x{g["size"][1]:.2f}x{g["size"][2]:.2f} m)')


def shrink_hash(c, sus_g, oth_g):
    h = hashlib.sha256()
    h.update(SHRINK_PROMPT_VERSION.encode())
    h.update(f'{c["suspect"]}|{c["other"]}|{c["sentence"]}'.encode())
    for g in (sus_g, oth_g):    # candidate menu derives from geometry
        h.update(str([round(v, 3) for v in
                      list(g["aabb_min"]) + list(g["aabb_max"])]).encode())
    return h.hexdigest()[:32]


def map_hash(e):
    h = hashlib.sha256()
    h.update(PROMPT_VERSION.encode())
    h.update(f'{e["a"]}|{e["b"]}|'
             f'{e["case_verdict"]["true_arrangement"]}'.encode())
    return h.hexdigest()[:32]


def llm_map(queue, names, cache, model, cwd):
    """queue: judged edges with REINTERPRET verdicts. Returns
    {edge_index_in_queue: mapping or None}; consults/updates cache."""
    todo = [(i, e) for i, e in enumerate(queue)
            if map_hash(e) not in cache]
    out = {i: cache.get(map_hash(e)) for i, e in enumerate(queue)}
    if not todo:
        return out
    items = []
    for n, (i, e) in enumerate(todo, 1):
        items.append(
            f'Case {n}: a={e["a"]} "{names.get(e["a"], "?")}", '
            f'b={e["b"]} "{names.get(e["b"], "?")}" '
            f'(old edge: {e["type"]})\n'
            f'  sentence: {e["case_verdict"]["true_arrangement"]}')
    arr = None
    for firm in (False, True):
        prompt = T_MAP.format(firm=jc.FIRM if firm else "",
                              items="\n\n".join(items))
        try:
            txt = jc.call_claude(prompt, cwd, model)
        except Exception as ex:  # noqa: BLE001 -- degrade, don't die
            print(f"[resolve] LLM call failed ({ex}); degrading")
            return out
        arr = jc.parse_array(txt)
        if arr:
            break
        print("[resolve] malformed mapping reply, retrying firmer")
    if not arr:
        return out
    by_case = {m.get("case"): m for m in arr if isinstance(m, dict)}
    for n, (i, e) in enumerate(todo, 1):
        m = by_case.get(n)
        if not m or m.get("type") not in RELATIONS:
            continue
        if m["type"] != "NONE" and m.get("subject") not in (e["a"], e["b"]):
            continue          # unusable subject id -> leave unresolved
        cache[map_hash(e)] = m
        out[i] = m
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--model", default=jc.MODEL)
    ap.add_argument("--dry-run", action="store_true",
                    help="print the plan; no LLM call, no write")
    ap.add_argument("--shrink", action="store_true",
                    help="RETIRED from this stage (user contract "
                         "2026-07-26): run the suspect-box shrink "
                         "adjudication anyway (placement-stage donor "
                         "code)")
    a = ap.parse_args()

    sdir = paths.scene_dir(a.scene)
    gpath = sdir / "scene_graph.json"
    graph = json.loads(gpath.read_text())
    judged = graph.get("judged")
    if not judged:
        raise SystemExit("[resolve] no judged layer -- run the judge "
                         "passes first")
    names = {jn["id"]: jn["name"] for jn in judged["nodes"]}

    removed, nodes = [], []
    for jn in sorted(judged["nodes"], key=lambda n: n["id"]):
        st = jn.get("existence") or "shipping"
        if st in REMOVE_STATES:
            removed.append({
                "id": jn["id"], "name": jn["name"], "state": st,
                "host": (jn.get("existence_verdict") or {}).get(
                    "what_it_is") if st == "structure" else None,
                "reason": (jn.get("existence_verdict") or {}).get(
                    "reason")})
        else:
            nodes.append({"id": jn["id"], "name": jn["name"],
                          "geometry": jn["geometry"],
                          "members": jn["members"], "from": "judged"})
    gone = {r["id"] for r in removed}

    kept_edges, dropped, queue = [], [], []
    for e in judged.get("edges", []):
        if e["a"] in gone or e["b"] in gone:
            dropped.append({**{k: e[k] for k in ("a", "b", "type")},
                            "reason": "endpoint_removed"})
            continue
        v = e.get("case_verdict") or {}
        if v.get("edge_verdict") == "REJECT":
            dropped.append({**{k: e[k] for k in ("a", "b", "type")},
                            "reason": "judge_reject",
                            "judge_reason": v.get("reason")})
            continue
        if v.get("edge_verdict") == "REINTERPRET":
            queue.append(e)
            continue
        kept_edges.append({k: e[k] for k in ("a", "b", "type")})

    floor_y = next(n for n in graph["nodes"] if n["id"] == "arch_floor")[
        "geometry"]["plane"]["value_raw"]
    node_by = {n["id"]: n for n in nodes}
    shrink_q = []
    for e in queue:
        sus_id = e["case_verdict"].get("suspect_box")
        if not sus_id or sus_id not in node_by:
            continue
        oth_id = e["b"] if e["a"] == sus_id else e["a"]
        if oth_id not in node_by:
            continue
        sus, oth = node_by[sus_id], node_by[oth_id]
        if overlap_volume(sus["geometry"], oth["geometry"]) <= 0:
            continue      # boxes don't even overlap -- nothing to cut
        shrink_q.append({"suspect": sus_id, "other": oth_id,
                         "sentence":
                             e["case_verdict"]["true_arrangement"],
                         "cands": candidate_trims(sus["geometry"],
                                                  oth["geometry"],
                                                  floor_y)})

    print(f"[resolve] nodes: {len(nodes)} shipping, "
          f"{len(removed)} removed ({[r['id'] for r in removed]})")
    print(f"[resolve] edges: {len(kept_edges)} pass-through, "
          f"{len(dropped)} dropped, {len(queue)} to reinterpret")
    print(f"[resolve] suspect-box work orders (still overlapping, "
          f"ship untouched): {[c['suspect'] for c in shrink_q]}")
    if a.dry_run:
        for e in queue:
            print(f'  REINTERPRET {e["a"]} -[{e["type"]}]- {e["b"]}: '
                  f'{e["case_verdict"]["true_arrangement"]}')
        for c in (shrink_q if a.shrink else []):
            sus, oth = node_by[c["suspect"]], node_by[c["other"]]
            print(f'  SHRINK? {c["suspect"]} ({sus["name"]}) vs '
                  f'{c["other"]} ({oth["name"]}):')
            for k, t in enumerate(c["cands"]):
                print(f'    {"abcdef"[k]}) [{t["face"]}] {t["desc"]}')
            if not c["cands"]:
                print(f'    no valid cut (every option loses '
                      f'>{SHRINK_MAX_LOSS:.0%})')
        return

    cache_path = sdir / "graph" / "resolve_cache.json"
    cache = (json.loads(cache_path.read_text())
             if cache_path.exists() else {})
    mapped = llm_map(queue, names, cache, a.model, sdir / "graph")
    cache_path.write_text(json.dumps(cache, indent=1))

    n_rewritten = n_unres = 0
    for i, e in enumerate(queue):
        m = mapped.get(i)
        base = {"was": e["type"],
                "true_arrangement": e["case_verdict"]["true_arrangement"],
                "suspect_box": e["case_verdict"].get("suspect_box"),
                "source": "reinterpret"}
        if m is None:
            kept_edges.append({"a": e["a"], "b": e["b"],
                               "type": e["type"],
                               "status": "unresolved_reinterpret",
                               **base})
            n_unres += 1
        elif m["type"] == "NONE":
            dropped.append({"a": e["a"], "b": e["b"], "type": e["type"],
                            "reason": "reinterpret_none", **base})
        else:
            kept_edges.append({"a": m["subject"], "b": m["object"],
                               "type": m["type"],
                               "confidence": m.get("confidence"),
                               **base})
            n_rewritten += 1

    # ---------------- shrink phase (RETIRED here; --shrink only) -------
    # code computes the lettered candidate-cut menu; the model only
    # picks a letter or KEEP (semantics with the model, numbers with
    # the code -- the +y curtain-hover lesson from the first dry run)
    box_ops = []
    def c_hash(c):
        return shrink_hash(c, node_by[c["suspect"]]["geometry"],
                           node_by[c["other"]]["geometry"])
    if not a.shrink:
        shrink_q = []
    askable = [c for c in shrink_q if c["cands"]]
    if askable:
        todo = [c for c in askable if c_hash(c) not in cache]
        if todo:
            items = []
            for n, c in enumerate(todo, 1):
                sus, oth = node_by[c["suspect"]], node_by[c["other"]]
                menu = "\n".join(
                    f'    {"abcdef"[k]}) {t["desc"]}'
                    for k, t in enumerate(c["cands"]))
                items.append(
                    f'Case {n}: suspect box '
                    f'{geom_facts(c["suspect"], sus["name"], sus["geometry"])}\n'
                    f'  other object '
                    f'{geom_facts(c["other"], oth["name"], oth["geometry"])}\n'
                    f'  judge sentence: {c["sentence"]}\n'
                    f'  candidate cuts:\n{menu}')
            arr = None
            for firm in (False, True):
                prompt = T_SHRINK.format(firm=jc.FIRM if firm else "",
                                         items="\n\n".join(items))
                try:
                    txt = jc.call_claude(prompt, sdir / "graph", a.model)
                except Exception as ex:  # noqa: BLE001 -- degrade
                    print(f"[resolve] shrink LLM failed ({ex}); "
                          f"boxes untouched")
                    txt = None
                    break
                arr = jc.parse_array(txt)
                if arr:
                    break
                print("[resolve] malformed shrink reply, retrying")
            if arr:
                by_case = {m.get("case"): m for m in arr
                           if isinstance(m, dict)}
                for n, c in enumerate(todo, 1):
                    m = by_case.get(n)
                    ch = str(m.get("choice", "")).strip().lower() \
                        if m else ""
                    if ch == "keep" or ch in "abcdef"[:len(c["cands"])]:
                        cache[c_hash(c)] = m
            cache_path.write_text(json.dumps(cache, indent=1))
    for c in shrink_q:
        op = {"suspect": c["suspect"], "other": c["other"],
              "sentence": c["sentence"]}
        m = cache.get(c_hash(c)) if c["cands"] else None
        ch = str(m.get("choice", "")).strip().lower() if m else None
        if not c["cands"]:
            op.update({"op": "NO_VALID_CUT",
                       "note": f"every cut loses >{SHRINK_MAX_LOSS:.0%}"
                               " -- box untouched"})
        elif m is None:
            op.update({"op": "UNRESOLVED",
                       "note": "no adjudication -- box untouched"})
        elif ch == "keep":
            op.update({"op": "KEEP", "confidence": m.get("confidence"),
                       "reason": m.get("reason")})
        else:
            t = c["cands"]["abcdef".index(ch)]
            sus = node_by[c["suspect"]]
            sus["geometry_preshrink"] = sus["geometry"]
            sus["geometry"] = t["geometry"]
            op.update({"op": "TRIM", "choice": ch, "face": t["face"],
                       "cut_desc": t["desc"],
                       "volume_loss": round(t["loss"], 3),
                       "confidence": m.get("confidence"),
                       "reason": m.get("reason")})
        box_ops.append(op)
        print(f'[resolve] shrink {c["suspect"]}: {op["op"]}'
              + (f' [{op.get("face")}] -{op.get("volume_loss", 0):.0%}'
                 if op["op"] == "TRIM" else ""))

    n_trim = sum(1 for o in box_ops if o["op"] == "TRIM")
    graph["resolved"] = {
        "built": date.today().isoformat(),
        "built_from": "judged",
        "note": ("verdicts materialized, BOXES VERBATIM FROM JUDGED -- "
                 "the scene-graph stage contract (user 2026-07-26): no "
                 "box surgery here; suspect_box entries + open flags "
                 "ship untouched as next-stage work orders"
                 if not a.shrink else
                 "verdicts materialized; suspect boxes adjudicated "
                 "TRIM/KEEP (--shrink, retired-here donor mode)"),
        "model": a.model, "prompt_version": PROMPT_VERSION,
        "shrink_prompt_version": SHRINK_PROMPT_VERSION,
        "nodes": nodes, "removed": removed,
        "edges": kept_edges, "dropped_edges": dropped,
        "box_ops": box_ops,
        "counts": {"nodes": len(nodes), "removed": len(removed),
                   "edges": len(kept_edges), "dropped": len(dropped),
                   "rewritten": n_rewritten,
                   "unresolved_reinterpret": n_unres,
                   "boxes_trimmed": n_trim}}
    # We just rewrote `resolved`, so say so in the file. The stamp also
    # marks every LATER layer stale, because each of them was built from
    # the resolved boxes that no longer exist. Without it the file keeps
    # claiming a newer layer is current and the next stage reads geometry
    # from a run that has been superseded.
    scene_state.stamp(graph, "resolved")
    gpath.write_text(json.dumps(graph, indent=1))
    print(f"[resolve] wrote {gpath}")
    print(f"[resolve] {graph['resolved']['counts']}")


if __name__ == "__main__":
    main()
