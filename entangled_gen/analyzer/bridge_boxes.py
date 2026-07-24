"""
Step 6 -- format-bridge: splat_analyzer interactions.json -> manifest-style boxes.

Reads the splat_analyzer output (out/<scene>/analyzer/<job>/interactions.json,
positions in the RAW gen_raw.ply frame -- the SAME frame scene_manifest.json
uses, no transform applied anywhere) and emits:

    out/<scene>/analyzer/bridged_boxes.json   manifest-style object list
                                              (ids ana_000..., axis-aligned,
                                              identity rotation per the tool's
                                              convention) + caveat metadata
    out/<scene>/analyzer/match_report.json    numeric manifest<->analyzer
                                              matching (nearest compatible
                                              label within DIST_M) + the
                                              reverse analyzer-only list

NEVER writes scene_manifest.json. Standalone + idempotent (pure file->file).
Prints a sanity report: totals, per-label counts, and how many box centers /
extents fall outside the room envelope (envelope.npz). A frame mismatch would
show up there -- this script only REPORTS it, it never "fixes" coordinates.

Carried caveats (from analyzer/FEASIBILITY_SPLAT_ANALYZER.md):
  1. centers are score-weighted centroids of FRONT-SURFACE lift points
     (median 5x5 depth patch at the 2D box center) -- biased toward the
     camera-visible surface, not the volumetric center;
  2. the box depth extent (local z) is FABRICATED as (width+height)/2,
     floored at 0.1 -- never measured;
  3. boxes are axis-aligned with identity rotation -- orientation is never
     estimated.

Run:  python analyzer/bridge_boxes.py --scene bedroom_marble --job job_high
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

DIST_M = 0.75          # match threshold: center distance, meters (RAW frame)

CAVEATS = {
    "surface_bias": (
        "position = score-weighted centroid of front-surface lift points "
        "(median 5x5 depth patch at each 2D box center) -- systematically "
        "biased toward the camera-visible surface, NOT the volumetric box "
        "center the manifest uses"),
    "fabricated_z_extent": (
        "the box's depth extent is fabricated as (width+height)/2, floored "
        "at 0.1 -- it is never measured; only the two image-plane extents "
        "come from pixels"),
    "axis_aligned": (
        "all boxes are axis-aligned with identity rotation -- the tool never "
        "estimates orientation (rotation quaternion is always 0,0,0,1)"),
}

# ---- label-synonym map (documented; also copied into match_report.json) ----
# Compatible = same canonical group. Any label NOT listed here is its own
# group (exact-match only). "poter" is the manifest's typo label for a poster
# (obj_017) -- mapped into the picture group on purpose.
SYNONYM_GROUPS = {
    "lamp":    ["lamp", "desk lamp", "floor lamp", "table lamp"],
    "chair":   ["chair", "office chair", "armchair"],
    "shelf":   ["shelf", "bookshelf", "bookcase", "shelves"],
    "picture": ["painting", "picture", "picture frame", "poster", "poter",
                "framed picture"],
    "plant":   ["potted planter", "potted plant", "plant", "planter"],
    "table":   ["side table", "table", "nightstand", "end table",
                "bedside table"],
}
_LABEL2GROUP = {m: g for g, ms in SYNONYM_GROUPS.items() for m in ms}


def canon(label):
    return _LABEL2GROUP.get(label.strip().lower(), label.strip().lower())


def r3(v):
    return [round(float(x), 3) for x in v]


def bridge_objects(inter):
    """interactions.json objects -> manifest-style object dicts."""
    out = []
    for i, o in enumerate(inter["objects"]):
        c = [o["position"]["x"], o["position"]["y"], o["position"]["z"]]
        s = [o["scale"]["x"], o["scale"]["y"], o["scale"]["z"]]
        scores = [f["score"] for f in o["frames"]]
        rot = o.get("rotation", {})
        out.append({
            "id": f"ana_{i:03d}",
            "label": o["label"],
            "score": round(max(scores), 3),          # peak single-frame score
            "aabb_min": r3([c[k] - s[k] / 2 for k in range(3)]),
            "aabb_max": r3([c[k] + s[k] / 2 for k in range(3)]),
            "center": r3(c),
            "size": r3(s),
            # tool convention: ALWAYS identity (axis-aligned) -- see caveats
            "rotation_quat_xyzw": [rot.get("x", 0.0), rot.get("y", 0.0),
                                   rot.get("z", 0.0), rot.get("w", 1.0)],
            "votes": len(o["frames"]),               # supporting 2D detections
            "peak_score": round(max(scores), 3),
            "n_detections": len(o["frames"]),
        })
    return out


def envelope_sanity(scene, objs):
    """Count centers/extents outside the room envelope. REPORT ONLY."""
    envf = paths.envelope_npz(scene)
    if not envf.exists():
        return {"note": f"no envelope.npz for {scene} -- check skipped"}
    z = np.load(envf)
    x0, z0, cell = float(z["x0"]), float(z["z0"]), float(z["cell"])
    nx, nz = int(z["nx"]), int(z["nz"])
    x1, z1 = x0 + nx * cell, z0 + nz * cell
    fy, cy = float(z["floor_y"]), float(z["ceil_y"])
    ylo, yhi = min(fy, cy), max(fy, cy)   # raw frame: up = -y, floor_y > ceil_y

    def in_xz(x, zz):
        return x0 <= x <= x1 and z0 <= zz <= z1

    center_out, extent_out, worst = [], [], []
    for o in objs:
        c, lo, hi = o["center"], o["aabb_min"], o["aabb_max"]
        c_ok = in_xz(c[0], c[2]) and ylo <= c[1] <= yhi
        e_ok = (in_xz(lo[0], lo[2]) and in_xz(hi[0], hi[2])
                and ylo <= lo[1] and hi[1] <= yhi)
        if not c_ok:
            center_out.append(o["id"])
        if not e_ok:
            extent_out.append(o["id"])
            # how far does the box poke out (worst axis, meters)?
            over = max(x0 - lo[0], lo[2] * 0 + z0 - lo[2], hi[0] - x1,
                       hi[2] - z1, ylo - lo[1], hi[1] - yhi)
            worst.append((round(float(over), 3), o["id"], o["label"]))
    worst.sort(reverse=True)
    return {
        "envelope_bounds": {"x": [round(x0, 3), round(x1, 3)],
                            "y_physical": [round(ylo, 3), round(yhi, 3)],
                            "z": [round(z0, 3), round(z1, 3)]},
        "centers_outside": len(center_out),
        "centers_outside_ids": center_out,
        "extents_partially_outside": len(extent_out),
        "extents_partially_outside_ids": extent_out,
        "worst_overhangs_m": [{"over_m": w, "id": i, "label": l}
                              for w, i, l in worst[:10]],
        "note": ("report only -- a large centers_outside count would indicate "
                 "a frame mismatch; nothing was corrected. The envelope grid "
                 "covers the splat's p1..p99 extent, so small overhangs from "
                 "wall-flush boxes are expected"),
    }


def dist3(a, b):
    return float(np.linalg.norm(np.asarray(a, float) - np.asarray(b, float)))


def build_match_report(scene, man, objs):
    """Nearest compatible-label analyzer box per manifest object (<= DIST_M)
    + the reverse analyzer-only list. Pure numeric, no quality judgment."""
    man_objs = man["objects"]
    m2a = []
    matched_ana = set()
    for mo in man_objs:
        g = canon(mo["label"])
        cands = [(dist3(mo["center"], ao["center"]), ao)
                 for ao in objs if canon(ao["label"]) == g]
        cands.sort(key=lambda t: t[0])
        row = {"manifest_id": mo["id"], "manifest_label": mo["label"],
               "manifest_center": mo["center"], "group": g}
        if cands and cands[0][0] <= DIST_M:
            d, ao = cands[0]
            row.update({"matched": True, "analyzer_id": ao["id"],
                        "analyzer_label": ao["label"],
                        "distance_m": round(d, 3),
                        "analyzer_votes": ao["votes"],
                        "analyzer_peak_score": ao["peak_score"]})
            matched_ana.add(ao["id"])
        else:
            row["matched"] = False
            if cands:
                row["nearest_compatible"] = {
                    "analyzer_id": cands[0][1]["id"],
                    "analyzer_label": cands[0][1]["label"],
                    "distance_m": round(cands[0][0], 3)}
            else:
                row["nearest_compatible"] = None
        m2a.append(row)

    # reverse: analyzer clusters with NO compatible manifest object <= DIST_M
    analyzer_only, by_label = [], {}
    for ao in objs:
        g = canon(ao["label"])
        cands = [(dist3(mo["center"], ao["center"]), mo)
                 for mo in man_objs if canon(mo["label"]) == g]
        cands.sort(key=lambda t: t[0])
        if cands and cands[0][0] <= DIST_M:
            continue
        entry = {"id": ao["id"], "label": ao["label"], "center": ao["center"],
                 "votes": ao["votes"], "peak_score": ao["peak_score"]}
        if cands:
            entry["nearest_compatible_manifest"] = {
                "manifest_id": cands[0][1]["id"],
                "distance_m": round(cands[0][0], 3)}
        analyzer_only.append(entry)
        by_label.setdefault(ao["label"], []).append(ao["id"])

    n_matched = sum(1 for r in m2a if r["matched"])
    return {
        "scene": scene,
        "threshold_m": DIST_M,
        "distance_metric": "3D euclidean between box centers, RAW frame",
        "synonym_groups": SYNONYM_GROUPS,
        "synonym_note": ("compatible = same canonical group; labels not "
                         "listed are exact-match-only groups of their own. "
                         "manifest label 'poter' (obj_017) is a known typo "
                         "for 'poster' and is mapped into the picture group"),
        "caveat": ("analyzer centers are front-surface-biased (see "
                   "bridged_boxes.json caveats), so distances carry a "
                   "systematic toward-the-camera offset; matching is numeric "
                   "only, no quality judgment"),
        "manifest_total": len(man_objs),
        "matched": n_matched,
        "unmatched": len(man_objs) - n_matched,
        "manifest_to_analyzer": m2a,
        "analyzer_total": len(objs),
        "analyzer_matched_to_manifest": len(matched_ana),
        "analyzer_only_count": len(analyzer_only),
        "analyzer_only_by_label": {k: by_label[k] for k in sorted(by_label)},
        "analyzer_only": analyzer_only,
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--job", default="job_high",
                    help="analyzer job dir name under out/<scene>/analyzer/")
    args = ap.parse_args()

    adir = paths.scene_dir(args.scene) / "analyzer"
    interf = adir / args.job / "interactions.json"
    inter = json.loads(interf.read_text())
    man = json.loads(paths.manifest(args.scene).read_text())

    objs = bridge_objects(inter)
    env_report = envelope_sanity(args.scene, objs)

    bridged = {
        "scene": args.scene,
        "source_interactions": str(interf),
        "source_job": args.job,
        "generated_by": "analyzer/bridge_boxes.py (Step 6 -- format-bridge)",
        "frame": {
            "space": "raw",
            "note": ("positions passed through UNCHANGED from "
                     "interactions.json: splat_analyzer outputs boxes in the "
                     "input PLY's native frame, and the input was gen_raw.ply "
                     "-- the SAME RAW frame scene_manifest.json uses. "
                     "No transform was applied by this bridge."),
        },
        "caveats": CAVEATS,
        "envelope_sanity": env_report,
        "count": len(objs),
        "objects": objs,
    }
    outf = adir / "bridged_boxes.json"
    outf.write_text(json.dumps(bridged, indent=1))

    match = build_match_report(args.scene, man, objs)
    matchf = adir / "match_report.json"
    matchf.write_text(json.dumps(match, indent=1))

    # ---------------- sanity report (stdout) ----------------
    labels = {}
    for o in objs:
        labels[o["label"]] = labels.get(o["label"], 0) + 1
    print(f"[bridge] {len(objs)} analyzer boxes <- {interf}")
    print("[bridge] per-label counts:")
    for k in sorted(labels, key=lambda k: (-labels[k], k)):
        print(f"           {labels[k]:3d}  {k}")
    if "centers_outside" in env_report:
        print(f"[bridge] envelope check (REPORT ONLY, nothing fixed): "
              f"{env_report['centers_outside']}/{len(objs)} centers outside, "
              f"{env_report['extents_partially_outside']}/{len(objs)} boxes "
              f"partially outside")
        for w in env_report["worst_overhangs_m"][:5]:
            print(f"           overhang {w['over_m']:+.3f} m  {w['id']} "
                  f"({w['label']})")
    else:
        print(f"[bridge] envelope check: {env_report['note']}")
    print(f"[match] {match['matched']}/{match['manifest_total']} manifest "
          f"objects matched (<= {DIST_M} m, compatible label); "
          f"{match['analyzer_only_count']} analyzer-only clusters")
    for r in match["manifest_to_analyzer"]:
        if r["matched"]:
            print(f"           {r['manifest_id']} {r['manifest_label']:<16} -> "
                  f"{r['analyzer_id']} {r['analyzer_label']:<14} "
                  f"{r['distance_m']:.3f} m")
        else:
            nc = r.get("nearest_compatible")
            extra = (f" (nearest compatible {nc['analyzer_id']} at "
                     f"{nc['distance_m']:.3f} m)" if nc
                     else " (no compatible label at all)")
            print(f"           {r['manifest_id']} {r['manifest_label']:<16} -> "
                  f"UNMATCHED{extra}")
    print(f"[bridge] wrote {outf}")
    print(f"[bridge] wrote {matchf}")
    print("[bridge] scene_manifest.json NOT touched (by design)")


if __name__ == "__main__":
    main()
