"""Retro-count OUR LLM calls per scene from on-disk receipts.

EVAL_PLAN_2026-08-13 metric 3. There is no call ledger (18 call_claude
sites, none logs) — so this counts what the receipts prove: every
judge/compose stage caches or records its answered calls per item.
Two counting rules, per file:

  1. VERDICT RULE: recursively count dicts carrying a verdict-ish key
     ('verdict', 'answer', 'decision', 'ruling', 'winner') — each is
     one answered model call recorded with its evidence.
  2. CACHE RULE (fallback when a file has no verdict-ish dicts): the
     size of the file's largest dict/list container — cache files are
     keyed one-entry-per-call.

This is a LOWER BOUND and says so: retries and malformed-answer
re-asks are not recorded; vocab (~6 uncached calls, per its stage
note), pano_bearings and the single batched compose-head calls
(supported_by / consistency / snap / propose_edits count via their
caches) may be under-represented. The per-file breakdown prints so the
count is auditable. Same recount-from-record spirit as GLTS's own
glts_run._count_calls.

Run:  python eval_llm_calls.py
"""
import json
from pathlib import Path

import paths

SCENES = ["natural_living", "sunlit_office", "blue_living", "panel_bedroom",
          "arch_bedroom", "plaster_bedroom",
          "bedroom_marble", "living_marble", "fresh04", "fresh06"]

RECEIPTS = [
    "scale_priors_cache.json",
    "graph/appearance_cache_v2.json",
    "graph/judge_cases_cache.json",
    "graph/judge_coherence_cache.json",
    "graph/judge_multiplicity_cache.json",
    "graph/judge_names_cache.json",
    "graph/judge_near_cache.json",
    "graph/judge_pairs_cache.json",
    "graph/judge_same_product_cache.json",
    "graph/triage_pairs_cache.json",
    "graph/split_cuts_cache.json",
    "graph/resolve_cache.json",
    "vote/slicevote_report.json",
    "compose/supported_by_cache.json",
    "compose/consistency_cache.json",
    "compose/snap_cache.json",
    "compose/propose_edits_call_cache.json",
    "compose/pick_cache.json",
    "compose/rotation_check.json",
]

VERDICT_KEYS = {"verdict", "answer", "decision", "ruling", "winner"}
UNCOUNTED_NOTE = ("plus uncounted: vocab (~6 uncached calls), "
                  "pano_bearings, sub-round checkpoint calls, retries")


def count_verdicts(obj):
    n = 0
    if isinstance(obj, dict):
        if VERDICT_KEYS & set(obj.keys()):
            n += 1
        for v in obj.values():
            n += count_verdicts(v)
    elif isinstance(obj, list):
        for v in obj:
            n += count_verdicts(v)
    return n


def largest_container(obj):
    best = 0
    if isinstance(obj, dict):
        best = max(best, len(obj))
        for v in obj.values():
            best = max(best, largest_container(v))
    elif isinstance(obj, list):
        best = max(best, len(obj))
        for v in obj:
            best = max(best, largest_container(v))
    return best


def main():
    table = {}
    for sc in SCENES:
        sdir = paths.scene_dir(sc)
        per_file, total = {}, 0
        for rel in RECEIPTS:
            f = sdir / rel
            if not f.exists():
                continue
            try:
                j = json.loads(f.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            n = count_verdicts(j)
            how = "verdicts"
            if n == 0:
                n = largest_container(j)
                how = "cache-entries"
            if n:
                per_file[rel] = {"count": n, "rule": how}
                total += n
        table[sc] = {"total": total, "per_file": per_file,
                     "note": UNCOUNTED_NOTE}
        print(f"[calls] {sc:18s} {total:5d}")
        for rel, d in sorted(per_file.items(), key=lambda kv: -kv[1]["count"]):
            print(f"          {d['count']:5d}  {rel} ({d['rule']})")

    out = paths.OUT / "eval_renders" / "llm_calls.json"
    out.write_text(json.dumps(
        {"scenes": table, "method": "receipts recount (see script header)",
         "bound": "lower"}, indent=1), encoding="utf-8")
    print(f"[calls] -> {out}")


if __name__ == "__main__":
    main()
