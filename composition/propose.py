"""Stage 1: propose layout boxes -> verify (render_proposal.py) -> revise loop.

run(scene) -> True when ALL CONSTRAINTS PASS; compose_proposal.json + the
proposal_* renders land in out/<scene>/package/. The verifier is the existing
entangled_gen/render_proposal.py run as a subprocess (swap point: any checker
that reads compose_proposal.json and prints PASS/FAIL lines).
"""
import json
import subprocess
import sys

import comp_paths
from comp_paths import paths
from bridge import call_agent_json

MAX_ROUNDS = 3


def _validate(prop):
    for p in prop["placements"]:
        for k in ("label", "center", "size"):
            if k not in p:
                raise ValueError(f"placement missing key {k!r}")
        if len(p["center"]) != 3 or len(p["size"]) != 3:
            raise ValueError("center/size must be [x,y,z]")


def build_prompt(sc, n_min=3, n_max=6):
    pkg = paths.package_dir(sc)
    guide = (pkg / "GUIDE.md").read_text(encoding="utf-8")
    overlays = sorted(pkg.glob("manifest_overlay_*.png"))
    pf = comp_paths.scene_prompt_file(sc)
    scene_prompt = pf.read_text(encoding="utf-8").strip() if pf else "(no generation prompt on file)"
    img_lines = "\n".join(f"- {f}" for f in overlays)
    return f"""You are composing object placements for a real 3D scene.

First, use the Read tool to view these annotated views of the scene:
{img_lines}

== SCENE GUIDE (follow its Frame section and OUTPUT CONTRACT exactly) ==
{guide}

== TASK ==
The scene was generated from this description:
{scene_prompt}

Propose {n_min} to {n_max} NEW object placements for items this description calls
for that are missing from the existing-object table (verify against the views).
Respect every hard constraint in the OUTPUT CONTRACT, including the floor
formula (mind the up sign) and the mount field. Reply with ONLY the
compose_proposal.json object - no markdown fences, no commentary."""


def verify(sc):
    """Run the constraint checker; returns (ok, report_text)."""
    r = subprocess.run([sys.executable, str(comp_paths.EG / "render_proposal.py"),
                        "--scene", sc], capture_output=True, text=True,
                       cwd=comp_paths.EG)
    report = (r.stdout + r.stderr)
    ok = "ALL CONSTRAINTS PASS" in report
    return ok, report


def run(sc, model="sonnet"):
    pkg = paths.package_dir(sc)
    base = build_prompt(sc)
    prompt = base
    for rnd in range(1, MAX_ROUNDS + 1):
        prop = call_agent_json(prompt, validate=_validate, model=model,
                               tag=f"propose_r{rnd}")
        (pkg / "compose_proposal.json").write_text(json.dumps(prop, indent=1))
        ok, report = verify(sc)
        fails = "\n".join(l for l in report.splitlines() if l.startswith("FAIL"))
        print(f"[propose] round {rnd}: {'PASS' if ok else 'FAIL'}", flush=True)
        if ok:
            return True
        kept = [p for p in prop["placements"]]
        prompt = (f"{base}\n\n== VERIFIER FEEDBACK (round {rnd + 1}) ==\n"
                  f"Your previous proposal was checked; these placements failed:\n{fails}\n"
                  f"Previous proposal was:\n{json.dumps({'placements': kept})}\n"
                  "Keep passing placements EXACTLY as they were; fix or drop the "
                  "failing ones. Reply with ONLY the full corrected "
                  "compose_proposal.json object.")
    return False


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()
    sys.exit(0 if run(args.scene) else 1)
