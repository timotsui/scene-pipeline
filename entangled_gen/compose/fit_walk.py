"""
FIT CANDIDATE WALK (canon: the loop's mechanical core; approved
2026-08-04 night): for every item implicated in a fit_check finding,
step DOWN its style list (picks.json final_candidates = the k=3 baton)
to the best-FITTING candidate when the current pick overshoots its box
beyond the margin. The style judge ranked looks and ignored fit; the
walk is where fit gets its vote -- from data already in the lists.

Rules:
  - walk only implicated items (fit_check bounds finding, or a clip
    pair whose partner is not FLAT -- rug-pile pairs never trigger)
  - walk only when the CURRENT candidate's worst-axis fit score
    exceeds MARGIN (0.15, the strict mark) AND a sibling in the
    style top-3 scores meaningfully better (> 0.02)
  - all 3 dry (every score > the fit_feedback DRY threshold) -> no
    change, complaint recorded (rule 9's escape hatch)
  - choices accumulate in fit_walk.json; fit_preview applies them
    over the style #1 (pick_source: "walk"); rotation check is NOT
    re-triggered (canon rule 10)

Run:  python compose/fit_walk.py --scene <scene>
Out:  compose/fit_walk.json (consumed by fit_preview.py)
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

MARGIN = 0.15
GAIN = 0.02
DRY_SCORE = 0.65
FLAT_Y = 0.06


def main():
    t0 = time.time()
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()

    cdir = paths.compose_dir(args.scene)
    fp = json.loads((cdir / "fitted_preview.json").read_text(
        encoding="utf-8"))
    fc = json.loads((cdir / "fit_check.json").read_text(
        encoding="utf-8"))
    pk = json.loads((cdir / "picks.json").read_text(encoding="utf-8"))
    sl = json.loads((cdir / "shopping.json").read_text(
        encoding="utf-8"))
    place = {p["id"]: p for p in fp["placed"]}
    pools = {}
    for it in pk.get("items", []):
        if it.get("final_candidates"):
            pools[it["id"]] = it["final_candidates"]
    for it in sl["items"]:   # fallback pool = size-fit top 3
        pools.setdefault(it["id"], (it.get("candidates") or [])[:3])

    def is_flat(iid):
        pl = place.get(iid)
        if not pl:
            return False
        fb = pl["fit_box"]
        return abs(fb["aabb_max"][1] - fb["aabb_min"][1]) < FLAT_Y

    implicated = {it["id"] for it in fc["items"] if it["bounds"]}
    for p in fc["clips"]:
        if not (is_flat(p["a"]) or is_flat(p["b"])):
            implicated.add(p["a"])
            implicated.add(p["b"])

    wpath = cdir / "fit_walk.json"
    prev = (json.loads(wpath.read_text(encoding="utf-8"))
            if wpath.exists() else {})
    choices = prev.get("choices", {})
    complaints = []
    changed = 0
    for iid in sorted(implicated):
        pool = pools.get(iid) or []
        pl = place.get(iid)
        if not pool or not pl:
            continue
        cur_uid = pl["uid"]
        cur = next((c for c in pool if c["uid"] == cur_uid), None)
        cur_score = (cur["score"] if cur else
                     next((c["score"] for c in
                           next((it.get("candidates") or [] for it in
                                 sl["items"] if it["id"] == iid), [])
                           if c["uid"] == cur_uid), None))
        if cur_score is None:
            continue
        best = min(pool, key=lambda c: c["score"])
        if min(c["score"] for c in pool) > DRY_SCORE:
            complaints.append({"item": iid, "name": pl["name"],
                               "why": "all style candidates dry"})
            continue
        if (cur_score > MARGIN and best["uid"] != cur_uid
                and best["score"] < cur_score - GAIN):
            choices[iid] = {
                "candidate": best,
                "from_uid": cur_uid,
                "from_score": round(cur_score, 3),
                "to_score": round(best["score"], 3),
                "why": (f"finding-implicated, current fit "
                        f"{cur_score * 100:.0f}% off -> walked to "
                        f"style#{pool.index(best) + 1} at "
                        f"{best['score'] * 100:.0f}%")}
            changed += 1
            print(f"  WALK {iid:12s} {pl['name']:20s} "
                  f"{cur_score:.2f} -> {best['score']:.2f} "
                  f"(style#{pool.index(best) + 1})")

    out = {"scene": args.scene, "built": str(date.today()),
           "generated_by": "compose/fit_walk.py",
           "graph_fingerprint": paths.graph_fingerprint(args.scene),
           "note": "candidate-walk choices; fit_preview applies these "
                   "over the style #1 (pick_source walk). Margin "
                   f"{MARGIN}, gain {GAIN}, dry {DRY_SCORE}.",
           "choices": choices, "complaints": complaints,
           "changed_this_run": changed,
           "elapsed_s": round(time.time() - t0, 1)}
    wpath.write_text(json.dumps(out, indent=1), encoding="utf-8")
    print(f"[walk] {changed} new walks ({len(choices)} total), "
          f"{len(complaints)} complaints ({time.time() - t0:.1f}s)")


if __name__ == "__main__":
    main()
