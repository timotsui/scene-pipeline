"""
FIT DRY-LIST FEEDBACK (canon rule 9, 2026-08-04 night -- the wardrobe
lesson; user: "the wardrobe should be abandoned and instead we go back
and shop for something that fits"): scan shopping.json for items whose
BEST candidate is still hopelessly far from the slot (worst-axis fit
score > DRY_SCORE) and write the walk-back verdicts shopping.py
consumes on its next run:

  swap-ins   -> reject the SWAP: out-items restored to the fit set
                (the proposal box, usually a clamped swap envelope,
                was the lie -- box_source estimated_prior)
  adds       -> drop the add entirely
  detections -> complaint record only (the object is real; it stands
                with its least-bad candidate and a flag)

DRY_SCORE 0.65 sits in the measured gap on bedroom_marble: the two
clamped swap envelopes score 9.94 / 0.71 while every detection's best
is <= 0.61. FLAGGED CONSTANT -- re-measure on scene #2.

Run:  python compose/fit_feedback.py --scene <scene>
Out:  compose/fit_feedback.json (consumed by shopping.py)
"""
import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

DRY_SCORE = 0.65


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()

    cdir = paths.compose_dir(args.scene)
    sl = json.loads((cdir / "shopping.json").read_text(encoding="utf-8"))

    rejected_swaps, rejected_adds, complaints = {}, {}, []
    for it in sl["items"]:
        cands = it.get("candidates") or []
        if not cands:
            continue
        best = min(c["score"] for c in cands)
        if best <= DRY_SCORE:
            continue
        entry = {"item": it["id"], "name": it["name"],
                 "best_score": round(best, 3),
                 "why": f"best candidate {best * 100:.0f}% off on its "
                        f"worst axis (> {DRY_SCORE * 100:.0f}%)"}
        src = it.get("source", "detected")
        if src == "swap_in":
            sid = it["id"].rsplit("_in", 1)[0]
            rejected_swaps[sid] = entry
        elif src == "add":
            rejected_adds[it["id"]] = entry
        else:
            complaints.append(entry)

    out = {"scene": args.scene, "built": str(date.today()),
           "generated_by": "compose/fit_feedback.py",
           "graph_fingerprint": paths.graph_fingerprint(args.scene),
           "note": "dry-list walk-back verdicts (canon rule 9): "
                   "rejected swaps revert to their out-items, rejected "
                   "adds drop, detection complaints are advisory. "
                   "shopping.py consumes this on its next run.",
           "params": {"dry_score": DRY_SCORE},
           "rejected_swaps": rejected_swaps,
           "rejected_adds": rejected_adds,
           "complaints": complaints,
           "elapsed_s": round(time.time() - t0, 1)}
    (cdir / "fit_feedback.json").write_text(json.dumps(out, indent=1),
                                            encoding="utf-8")
    print(f"[feedback] {len(rejected_swaps)} swaps rejected, "
          f"{len(rejected_adds)} adds dropped, {len(complaints)} "
          f"complaints ({time.time() - t0:.1f}s)")
    for sid, e in sorted(rejected_swaps.items()):
        print(f"  WALK-BACK {sid}: {e['name']} -- {e['why']}")
    for aid, e in sorted(rejected_adds.items()):
        print(f"  DROP      {aid}: {e['name']} -- {e['why']}")


if __name__ == "__main__":
    main()
