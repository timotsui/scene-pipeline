"""Size-match metric — how well the asset library fits our measured
boxes (EVAL_PLAN follow-on, user 08-13: "some metric about matching
sizes... the story of: if more stuff fit, it would be even better").

All from existing receipts, per scene:

  chosen_fit_pct     placed anchors whose CHOSEN asset natively fits
                     the measured box within the fit canon's own 15%
                     (picks.json `fits` on the chosen candidate)
  no_fit_option_pct  placed anchors where NO candidate in the whole
                     shortlist fit — the library had nothing at the
                     right size and we placed the best wrong-size one
  size_dev_pct       mean |native size - measured box| / box, averaged
                     over the three sorted dims of the chosen asset
                     (sorted = orientation-free)
  out_of_box_mm      per-placement protrusion beyond the measured box
                     recorded by the fit (median / max per scene)

READING for the paper: this measures native-size fidelity among direct
placements with comparable main-pass pick receipts.  It establishes how often
the shortlist offers a size match; it does not score color, material, style,
or the accuracy of the measured box itself.

Run:  python eval_size_match.py
"""
import json
import numpy as np
from pathlib import Path

import paths

SCENES = ["natural_living", "sunlit_office", "blue_living", "panel_bedroom",
          "arch_bedroom", "plaster_bedroom",
          "bedroom_marble", "fresh04", "fresh06"]


def _load(p):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def main():
    table = {}
    raw_counts = {}
    for sc in SCENES:
        cdir = paths.scene_dir(sc) / "compose"
        fp = _load(cdir / "fitted_preview.json")
        pk = _load(cdir / "picks.json")
        if not fp or not pk:
            table[sc] = {"available": False}
            print(f"[size] {sc:18s} — missing receipts")
            continue
        ranked_by_id = {it["id"]: it.get("style_ranked") or []
                        for it in pk.get("items", [])}
        chosen_fit, no_option, devs, oob = [], [], [], []
        for e in fp.get("placed") or []:
            oobmm = e.get("out_of_box_mm")
            if oobmm is not None:
                oob.append(float(oobmm))
            ranked = ranked_by_id.get(e.get("id"))
            if not ranked:
                continue                      # swap-ins etc: no pick record
            chosen = next((c for c in ranked
                           if c.get("uid") == e.get("uid")), None)
            if chosen is None:
                continue
            chosen_fit.append(bool(chosen.get("fits")))
            no_option.append(not any(c.get("fits") for c in ranked))
            box = e.get("fit_box") or {}
            if box:
                lo = np.array(box["aabb_min"], float)
                hi = np.array(box["aabb_max"], float)
                bdims = np.sort(hi - lo)
                adims = np.sort(np.array(chosen["size_cm"], float) / 100.0)
                dev = np.abs(adims - bdims) / np.maximum(bdims, 1e-6)
                devs.append(float(dev.mean()))
        n = len(chosen_fit)
        rec = {
            "available": True,
            "n_scored": n,
            "chosen_fit_count": sum(chosen_fit),
            "chosen_fit_pct": round(100.0 * sum(chosen_fit) / n) if n else None,
            "no_fit_option_count": sum(no_option),
            "no_fit_option_pct": round(100.0 * sum(no_option) / n) if n else None,
            "size_dev_pct_mean": round(100.0 * float(np.mean(devs)), 1)
            if devs else None,
            "out_of_box_mm_median": round(float(np.median(oob)), 1)
            if oob else None,
            "out_of_box_mm_max": round(float(np.max(oob)), 1) if oob else None,
        }
        table[sc] = rec
        raw_counts[sc] = (n, sum(chosen_fit), sum(no_option))
        print(f"[size] {sc:18s} n={n:3d}  chosen-fit {rec['chosen_fit_pct']}%"
              f"  no-option {rec['no_fit_option_pct']}%  "
              f"dev {rec['size_dev_pct_mean']}%  oob med/max "
              f"{rec['out_of_box_mm_median']}/{rec['out_of_box_mm_max']} mm")

    current_six = SCENES[:6]
    n_scored = sum(raw_counts[sc][0] for sc in current_six)
    n_fit = sum(raw_counts[sc][1] for sc in current_six)
    n_no_option = sum(raw_counts[sc][2] for sc in current_six)
    summary = {
        "scenes": current_six,
        "n_scored_direct_placements": n_scored,
        "chosen_fit_count": n_fit,
        "chosen_fit_pct": round(100.0 * n_fit / n_scored, 1),
        "no_fit_option_count": n_no_option,
        "no_fit_option_pct": round(100.0 * n_no_option / n_scored, 1),
        "note": ("Direct placements with comparable main-pass pick receipts; "
                 "does not include replacements or unscored sub-round items."),
    }
    out = paths.OUT / "eval_renders" / "size_match.json"
    out.write_text(json.dumps({"summary_current_six": summary,
                               "scenes": table}, indent=1), encoding="utf-8")
    print(f"[size] -> {out}")


if __name__ == "__main__":
    main()
