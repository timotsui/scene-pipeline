"""
EXPERIMENT (2026-07-26): re-pose the ALREADY-RESOLVED existence cases
with the v2 evidence pack -- zoomed-out red-box context tile +
truncation facts + the PART_OF_STRUCTURE verdict (judge_cases
PROMPT_VERSION 2). Motivating case: obj_138, a truncated single-view
detection whose tight crop reads "picture frame" but whose context
view shows it is the door's frame.

READ-ONLY: scene_graph.json is NOT modified and no judge caches are
touched. Uses jc.build_exist_job -- the exact code path the J6 phase-A
pipeline now runs -- so the result transfers.

Outputs (out/<scene>/graph/case_sheets_v2/):
  cases_existence.png   the new-style contact sheet (review artifact)
  retry_report.json     old verdict vs new verdict per case

--apply (user approval 2026-07-26 "these are better"): write the
verdicts ALREADY IN retry_report.json into scene_graph.json -- no new
model call -- mirroring describe_nodes' write-back (REAL -> confirmed
+ short-name, NOT_REAL -> rejected, PART_OF_STRUCTURE -> structure).
A pre-apply backup is saved as graph/scene_graph_pre_ctxretry.json.

Run:
  python graph/retry_cases_context.py --scene bedroom_marble --sheets-only
  python graph/retry_cases_context.py --scene bedroom_marble
  python graph/retry_cases_context.py --scene bedroom_marble --apply
"""
import argparse
import json
import re
import shutil
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
sys.path.insert(0, str(HERE))
import paths  # noqa: E402
import judge_cases as jc  # noqa: E402


def apply_report(sdir):
    """Write retry_report.json's verdicts into scene_graph.json
    (describe_nodes write-back logic, additive, with backup)."""
    gpath = sdir / "scene_graph.json"
    rpath = sdir / "graph" / "case_sheets_v2" / "retry_report.json"
    report = json.loads(rpath.read_text())
    graph = json.loads(gpath.read_text())
    judged = graph["judged"]
    jn_by_id = {jn["id"]: jn for jn in judged["nodes"]}
    bak = sdir / "graph" / "scene_graph_pre_ctxretry.json"
    if not bak.exists():
        shutil.copy2(gpath, bak)
        print(f"[retry] backup: {bak}")
    cache_path = sdir / "graph" / "judge_cases_cache.json"
    cache = json.loads(cache_path.read_text())
    prov = {"model": report["model"], "date": date.today().isoformat(),
            "prompt_version": report["prompt_version"],
            "source": "judge_cases_v2_retry"}
    summary = {"confirmed": [], "rejected": [], "structure": [],
               "unclear": []}
    for row in report["cases"]:
        jn = jn_by_id.get(row["id"])
        new = row["new"]
        if jn is None or new.get("verdict") not in jc.EXIST_VERDICTS:
            continue
        v = {**new, **prov}
        jn["existence_verdict"] = v
        if new["verdict"] == "REAL":
            jn["existence"] = "confirmed"
            wi = new.get("what_it_is")
            if isinstance(wi, str) and wi.strip():
                short = re.split(r"\b(?:or|on|in|with|near|beside)\b",
                                 wi.strip().lower())[0]
                short = " ".join(short.split()[:3]).strip(" ,;-")
                if short and short != jn["name"]:
                    jn["name"] = short
                    jn["naming"] = {**prov, "reason": new.get("reason"),
                                    "what_it_is_full": wi.strip(),
                                    "via": "existence_verdict"}
            summary["confirmed"].append(f'{row["id"]}={jn["name"]}')
        elif new["verdict"] == "NOT_REAL":
            jn["existence"] = "rejected"
            summary["rejected"].append(row["id"])
        elif new["verdict"] == "PART_OF_STRUCTURE":
            jn["existence"] = "structure"
            summary["structure"].append(
                f'{row["id"]} -> part of {new.get("what_it_is") or "?"}')
        else:
            summary["unclear"].append(row["id"])
        cache["cases"][f'exist:{row["id"]}'] = v
    judged["retry_v2_meta"] = {**prov,
                               "applied_from": str(rpath),
                               "summary": summary}
    cache_path.write_text(json.dumps(cache, indent=1))
    gpath.write_text(json.dumps(graph, indent=1))
    print(f"[retry] APPLIED to {gpath}\n[retry] {summary}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--model", default=jc.MODEL)
    ap.add_argument("--sheets-only", action="store_true",
                    help="build sheet + print prompt; NO model call")
    ap.add_argument("--apply", action="store_true",
                    help="write retry_report.json verdicts into "
                         "scene_graph.json (no model call)")
    a = ap.parse_args()

    sdir = paths.scene_dir(a.scene)
    if a.apply:
        apply_report(sdir)
        return
    graph = json.loads((sdir / "scene_graph.json").read_text())
    judged = graph["judged"]
    det = {n["id"]: n for n in graph["nodes"]
           if n["source"] == "detection"}
    floor_y = next(n for n in graph["nodes"]
                   if n["id"] == "arch_floor")[
        "geometry"]["plane"]["value_raw"]
    jn_by_id = {jn["id"]: jn for jn in judged["nodes"]}
    crops_dir = sdir / "graph" / "crops"
    frames_dir = Path(graph.get("lineage", {}).get("crop_source")
                      or (sdir / "rig_sp0" / "crops"))
    out_dir = sdir / "graph" / "case_sheets_v2"
    out_dir.mkdir(parents=True, exist_ok=True)

    q_exist = []
    for f in judged.get("coherence_flags", []):
        if f["suggested_action"] != "existence_disputed":
            continue
        jn = jn_by_id.get(f["target"].split("->")[0])
        if jn is not None:
            q_exist.append((jn, f))
    if not q_exist:
        raise SystemExit("[retry] no existence cases in the graph")
    print(f"[retry] {len(q_exist)} existence cases: "
          + ", ".join(jn["id"] for jn, _ in q_exist))

    sheet, items = jc.build_exist_job(q_exist, det, crops_dir,
                                      frames_dir, out_dir, floor_y)
    print(f"[retry] sheet: {sheet}")
    if a.sheets_only:
        print(jc.T_EXIST.format(firm="", sheet=sheet, items=items))
        return

    arr = None
    for attempt, firm in ((1, False), (2, True)):
        prompt = jc.T_EXIST.format(firm=jc.FIRM if firm else "",
                                   sheet=sheet, items=items)
        txt = jc.call_claude(prompt, out_dir, a.model)
        arr = jc.parse_array(txt)
        if arr:
            break
        print(f"[retry] malformed (attempt {attempt})")
    if not arr:
        raise SystemExit("[retry] both attempts malformed")

    by_id = {e.get("id"): e for e in arr if isinstance(e, dict)}
    keys = ("verdict", "what_it_is", "confidence", "reason")
    rows = []
    for jn, f in q_exist:
        old = jn.get("existence_verdict", {})
        new = by_id.get(jn["id"], {})
        rows.append({"id": jn["id"], "name": jn["name"],
                     "flag_issue": f["issue"],
                     "old": {k: old.get(k) for k in keys},
                     "new": {k: new.get(k) for k in keys}})
        print(f'\n[retry] {jn["id"]} ({jn["name"]})\n'
              f'  OLD: {old.get("verdict")} / {old.get("what_it_is")} '
              f'(conf {old.get("confidence")})\n'
              f'       {old.get("reason")}\n'
              f'  NEW: {new.get("verdict")} / {new.get("what_it_is")} '
              f'(conf {new.get("confidence")})\n'
              f'       {new.get("reason")}')

    report = out_dir / "retry_report.json"
    report.write_text(json.dumps(
        {"scene": a.scene, "model": a.model,
         "prompt_version": jc.PROMPT_VERSION,
         "note": "read-only experiment; scene_graph.json untouched",
         "cases": rows}, indent=1))
    print(f"\n[retry] report: {report}")


if __name__ == "__main__":
    main()
