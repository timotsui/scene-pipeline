"""Rebuild rotref_record.json from the replies left on disk (2026-08-04).

fitloop_rotref_test.py writes its record only at the end, so a run stopped
part-way leaves nothing but the per-call artefacts. Those artefacts are the
real evidence anyway: raw_<oid>_cam<X>_<arm>.txt holds each reply verbatim.
This reads them back, takes per-call seconds from rotref_run.log, and emits
the same schema the viewer reads -- marked partial, with the conditions that
never ran simply absent.

Reads only. Writes only rotref_record.json.
"""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from fitloop_rotref_test import best_evidence  # noqa: E402  (loads scene)
from fitloop_rotq_test import parse_json_obj, wrap180  # noqa: E402
sys.path.insert(0, str(HERE.parent))
import paths  # noqa: E402

SCENE = "bedroom_marble"
LOG = HERE / "rotref_run.log"
# [rotref] obj_109 camA arm1 -> 0.0 (47.8s)
LOG_RE = re.compile(r"\[rotref\] (obj_\S+) cam(\w+) (arm\d) -> .*?\(([\d.]+)s\)")


def main():
    sdir = paths.compose_dir(SCENE) / "review_shots"
    odir = sdir / "rotref"
    scene_dir = paths.scene_dir(SCENE)

    graph = json.loads((scene_dir / "scene_graph.json")
                       .read_text(encoding="utf-8"))
    nodes = {n["id"]: n for n in graph["nodes"]}
    names = {p["id"]: p["name"] for p in json.loads(
        (paths.compose_dir(SCENE) / "fitted_preview.json")
        .read_text(encoding="utf-8"))["placed"]}

    # per-call seconds: arm3's two calls share one log line, so its total is
    # split back across arm3a/arm3b only as a sum -- recorded as one number
    secs = {}
    if LOG.exists():
        for m in LOG_RE.finditer(LOG.read_text(encoding="utf-8")):
            secs[(m.group(1), m.group(2), m.group(3))] = float(m.group(4))

    def reply(oid, cam, arm):
        p = odir / f"raw_{oid}_cam{cam}_{arm}.txt"
        if not p.exists():
            return None
        return parse_json_obj(p.read_text(encoding="utf-8")) or {}

    # discover which conditions have any reply at all, in run order
    found = []
    for p in sorted(odir.glob("raw_*_arm1.txt")):
        m = re.match(r"raw_(obj_\S+)_cam(\w+)_arm1\.txt", p.name)
        if m:
            found.append((m.group(1), m.group(2)))
    order = {"obj_109": 0, "obj_008": 1, "obj_022": 2, "obj_025": 3}
    found.sort(key=lambda t: (order.get(t[0], 99), t[1]))

    rec = {"scene": SCENE, "model": "sonnet", "date": "2026-08-04",
           "note": "rotation question WITH the detection photo as reference. "
                   "PARTIAL -- run stopped by the user after ~59 min of model "
                   "time (too slow to be pipeline-applicable); rebuilt from "
                   "the replies on disk. user eyeballs = GT",
           "partial": True, "render_s": 0.0, "runs": []}

    for oid, cam in found:
        mem = best_evidence(nodes.get(oid, {}))
        ref_img = odir / f"{oid}_ref.png"
        run = {"item": oid, "name": names.get(oid, "object"), "cam": cam,
               "mode": "match_reference" if (mem and ref_img.exists())
                       else "plausible_fallback",
               "reference": ({"view": mem["view"], "crop": mem["crop"],
                              "score": mem.get("score"),
                              "truncated": mem.get("truncated"),
                              "sheet": ref_img.name}
                             if mem and ref_img.exists() else None),
               "sheet_rendered": (sdir / f"rotref_sheet_cam{cam}_{oid}.png"
                                  ).exists(),
               "arms": {}}

        j1 = reply(oid, cam, "arm1")
        if j1 is not None:
            d = j1.get("degrees")
            run["arms"]["arm1_direct"] = {
                "degrees": wrap180(d) if isinstance(d, (int, float)) else None,
                "calls": 1,
                "model_s": secs.get((oid, cam, "arm1"), 0.0),
                "call_s": [secs.get((oid, cam, "arm1"), 0.0)],
                "why": j1.get("why"), "confidence": j1.get("confidence")}

        j2 = reply(oid, cam, "arm2")
        if j2 is not None:
            t = j2.get("tile")
            deg = (wrap180((int(t) - 1) * 45)
                   if isinstance(t, (int, float)) and 1 <= int(t) <= 8
                   else None)
            run["arms"]["arm2_tiles"] = {
                "degrees": deg, "calls": 1,
                "model_s": secs.get((oid, cam, "arm2"), 0.0),
                "call_s": [secs.get((oid, cam, "arm2"), 0.0)],
                "tile": t, "why": j2.get("why"),
                "confidence": j2.get("confidence")}

        j3a, j3b = reply(oid, cam, "arm3a"), reply(oid, cam, "arm3b")
        if j3a is not None and j3b is not None:
            d = j3a.get("degrees")
            prop = wrap180(d) if isinstance(d, (int, float)) else 0.0
            ex = j3b.get("extra_degrees")
            ex = float(ex) if isinstance(ex, (int, float)) \
                and not j3b.get("ok") else 0.0
            run["arms"]["arm3_verify"] = {
                "degrees": wrap180(prop + ex), "calls": 2,
                "model_s": secs.get((oid, cam, "arm3"), 0.0),
                "call_s": [secs.get((oid, cam, "arm3"), 0.0)],
                "proposed": prop, "extra": ex,
                "ok_first_try": bool(j3b.get("ok")),
                "why": j3b.get("why"), "confidence": j3b.get("confidence")}

        rec["runs"].append(run)
        got = ", ".join(sorted(run["arms"]))
        print(f"[recover] {oid} cam{cam}: {got or 'nothing'}"
              + ("" if run["sheet_rendered"] else "  (no sheet -- cut off)"))

    rec["wall_s"] = round(sum(a["model_s"] for r in rec["runs"]
                              for a in r["arms"].values()), 1)
    out = odir / "rotref_record.json"
    out.write_text(json.dumps(rec, indent=2), encoding="utf-8")
    print(f"\n[recover] {len(rec['runs'])} conditions, "
          f"{sum(len(r['arms']) for r in rec['runs'])} arm answers, "
          f"{rec['wall_s']:.0f}s of model time -> {out}")


if __name__ == "__main__":
    main()
