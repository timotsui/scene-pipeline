"""Stage 4: VLM feedback loop — the GLTS-style "render, critique, adjust"
refinement, with the surrogate agent as the critic.

Each round: show the composite views + current object state -> the agent
returns per-object adjustments (dx, dz, dyaw_deg, scale) or approves ->
apply (with AABB re-check via the stage-1 verifier) -> re-render. Stops on
approve or MAX_ROUNDS. History -> jiggle_history.jsonl.

USER CHECKPOINT lives BEFORE this module runs (compose_scene.py --until place).
"""
import json

from comp_paths import paths
from bridge import call_agent_json
from place import composite_views
import propose

MAX_ROUNDS = 3
MAX_STEP = 0.5   # m, clamp per-round translation


def _loop_prompt(sc, state, views):
    img_lines = "\n".join(f"- {v}" for v in views)
    objs = json.dumps([{k: o[k] for k in ("label", "center", "size", "yaw_deg", "mount")}
                       for o in state["objects"]], indent=1)
    return f"""You are refining furniture placement in a 3D scene. The green/textured
objects below were newly inserted at planned positions; everything else is the
original scene.

Use the Read tool to view the current composite views:
{img_lines}

Current inserted objects (index order, RAW frame — up sign may be -y):
{objs}

Judge the layout like an interior designer: objects should sit naturally
(against walls where appropriate, not floating, not intersecting furniture,
plausible orientation facing into the room). If everything looks right, approve.
Otherwise give small corrective adjustments per object that needs one
(dx/dz in meters RAW frame <= {MAX_STEP}, dyaw_deg, scale multiplier 0.7-1.3).

Reply with ONLY a JSON object:
{{"approve": false, "adjustments": [{{"index": 0, "dx": 0.0, "dz": 0.0,
  "dyaw_deg": 0, "scale": 1.0, "why": "one line"}}]}}
or {{"approve": true, "adjustments": []}}"""


def _apply(state, adjustments):
    for a in adjustments:
        o = state["objects"][a["index"]]
        dx = max(-MAX_STEP, min(MAX_STEP, float(a.get("dx", 0))))
        dz = max(-MAX_STEP, min(MAX_STEP, float(a.get("dz", 0))))
        s = max(0.7, min(1.3, float(a.get("scale", 1.0))))
        o["center"][0] += dx
        o["center"][2] += dz
        o["yaw_deg"] = (o.get("yaw_deg") or 0) + float(a.get("dyaw_deg", 0))
        o["size"] = [d * s for d in o["size"]]


def _sync_proposal(sc, state):
    """Mirror state back into compose_proposal.json so the stage-1 verifier
    checks the adjusted layout."""
    pkg = paths.package_dir(sc)
    prop = json.loads((pkg / "compose_proposal.json").read_text())
    for p, o in zip(prop["placements"], state["objects"]):
        p["center"], p["size"], p["yaw_deg"] = o["center"], o["size"], o.get("yaw_deg", 0)
    (pkg / "compose_proposal.json").write_text(json.dumps(prop, indent=1))


def run(sc, model="sonnet"):
    pkg = paths.package_dir(sc)
    state = json.loads((pkg / "composed_state.json").read_text())
    hist = open(pkg / "jiggle_history.jsonl", "a", encoding="utf-8")
    views = sorted(pkg.glob("composed_view_gpu_yaw*.png"))
    for rnd in range(1, MAX_ROUNDS + 1):
        def _val(o):
            if "approve" not in o:
                raise ValueError("missing 'approve'")
            for a in o.get("adjustments", []):
                if not 0 <= a.get("index", -1) < len(state["objects"]):
                    raise ValueError("adjustment index out of range")
        fb = call_agent_json(_loop_prompt(sc, state, views), validate=_val,
                             model=model, tag=f"jiggle_r{rnd}")
        hist.write(json.dumps({"round": rnd, "feedback": fb}) + "\n")
        hist.flush()
        if fb["approve"]:
            print(f"[jiggle] approved at round {rnd}", flush=True)
            break
        _apply(state, fb["adjustments"])
        if state.get("mode") != "recreate":   # v0: constraint re-check is augment-only
            _sync_proposal(sc, state)
            ok, report = propose.verify(sc)
            if not ok:
                fails = [l for l in report.splitlines() if l.startswith("FAIL")]
                print(f"[jiggle] round {rnd}: adjusted layout fails constraints "
                      f"({len(fails)}) — keeping adjustment, logged", flush=True)
                hist.write(json.dumps({"round": rnd, "constraint_fails": fails}) + "\n")
        state["round"] = rnd
        (pkg / "composed_state.json").write_text(json.dumps(state, indent=1))
        views = composite_views(sc, state)
    hist.close()
    return state


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()
    run(args.scene)
