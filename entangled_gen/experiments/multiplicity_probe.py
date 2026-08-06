"""MULTIPLICITY PROBE — can the agent carry the k decision? (isolated
experiment, 08-07 nits session; no pipeline stage touched)

Two one-look questions, each 3 REPEAT RUNS per case — stability across
runs is the measurement, not just accuracy (the rotation-experiment
lesson: tail verdicts that flip between runs are noise, one lucky
right answer is not a capability):

  PROBE A (the graph-stage question): detection crop -> "ONE instance
     or a ROW/GROUP of near-identical ones, roughly how many?"
     Test set = this scene's real cases: the books (true rows), the
     lamp + monitor that the tiler wrongly duplicated (true singles),
     and unambiguous singles as controls.
  PROBE B (the pick-time question): observed crop + a rendered k-tile
     row of a library asset -> "would this composition read as the
     observed object?"  Cases: shelf stood in by 2 shelf units
     (modular composability), the k=3 lamp row and k=2 monitor twins
     (the 08-07 fabrications), a k=3 book row (the convention that
     reads right).

User judges ground truth from the review page (Claude never concludes
from images).  Writes out/<scene>/compose/sub_experiment/
_multiplicity_probe/ -- per-call folders, record.json, index.html.

  python multiplicity_probe.py [--scene bedroom_marble] [--runs 3]
"""
import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image

HERE = Path(__file__).parent
EG = HERE.parent
sys.path.insert(0, str(EG))
sys.path.insert(0, str(EG / "compose"))
sys.path.insert(0, str(HERE))

import paths                                     # noqa: E402
sys.path.insert(0, str(paths.REPO_ROOT / "composition"))
from assets_thor import load_asset               # noqa: E402
from sub_round_cp5 import align_upright          # noqa: E402
import sub_round_cp6 as cp6                      # noqa: E402

CONCURRENCY = 6      # independent calls run concurrently (08-04 rule)
TIMEOUT = 150
RES = 640
GAP = 0.005          # m between tiles in the B renders

# ---- Probe A test set: id -> expected slot for the record only; the
# user rules truth on the page.  Books = the true rows; lamp/monitor =
# the 08-07 wrongly-tiled singles; the rest = unambiguous controls.
A_SET = ["obj_005", "obj_010", "obj_012", "obj_018", "obj_028",
         "obj_034", "obj_041", "obj_049", "obj_050", "obj_065",
         "obj_072", "obj_130"]

# ---- Probe B cases: (label, observed-crop object, asset uid, k).
# The lamp/monitor uids are the PRE-GATE picks that actually got tiled
# (92aa31b6 two-glass-ball lamp k=3, ace1b257 sci-fi monitor k=2);
# the shelf uid = obj_022's placed stand-in, tiled 2x for the modular-
# composability question.  Book uid read from the current picks.
B_CASES = [
    ("shelf_2x", "obj_022", "5f680fa2341c4d36810dff2007955289", 2),
    ("lamp_3x", "obj_010", "92aa31b6796e4ca3b3ee58a95d578c40", 3),
    ("monitor_2x", "obj_005", "ace1b257e2c24ec184662d69e4befca1", 2),
    ("books_3x", "obj_034", None, 3),     # uid filled from picks.json
]


def _judge(prompt, cwd, timeout=TIMEOUT):
    """One-look judge call (claude -p, sonnet) — cp4's pattern."""
    exe = shutil.which("claude")
    if not exe:
        raise RuntimeError("claude not on PATH")
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)
    t0 = time.time()
    r = subprocess.run([exe, "-p", "--model", "sonnet",
                        "--output-format", "json"],
                       input=prompt, capture_output=True, text=True,
                       encoding="utf-8", errors="replace",
                       env=env, cwd=str(cwd), timeout=timeout)
    out = (r.stdout or "").strip()
    m = re.search(r"\{.*\}", out, re.DOTALL)
    envl = json.loads(m.group(0)) if m else {}
    text = envl.get("result") if isinstance(envl.get("result"), str) \
        else out
    m2 = re.search(r"\{[^{}]*\}", text or "", re.DOTALL)
    return (json.loads(m2.group(0)) if m2 else {}), round(
        time.time() - t0, 1)


def best_crop(scene, oid):
    """Largest crop file for the object = the most readable one."""
    crops = sorted((paths.scene_dir(scene) / "graph" / "crops").glob(
        f"{oid}_*.png"), key=lambda p: p.stat().st_size)
    return crops[-1] if crops else None


def render_row(uid, k, out_png):
    """k aligned copies of the asset side by side, neutral 3/4 shot."""
    mesh, _ = align_upright(load_asset(uid))
    w = float(mesh.bounds[1][0] - mesh.bounds[0][0])
    meshes = []
    for i in range(k):
        m = mesh.copy()
        m.apply_translation([i * (w + GAP), 0.0, 0.0])
        meshes.append(m)
    allb = np.vstack([m.bounds for m in meshes])
    lo, hi = allb.min(0), allb.max(0)
    ctr = (lo + hi) / 2
    span = float(max(hi - lo))
    eye = ctr + np.array([0.55, 0.4, 1.5]) * span * 1.25
    rgba = cp6.meshes_rgba(meshes, eye, ctr, np.array([0., 1., 0.]),
                           45.0, RES, alpha=1.0)
    img = Image.new("RGBA", rgba.size, (32, 32, 32, 255))
    img.alpha_composite(rgba)
    img.convert("RGB").save(out_png)


def prompt_a(name, crop_local):
    return (f"IMAGE (detection crop from a real room photo, detector "
            f"label '{name}'):\n{crop_local}\n\n"
            f"QUESTION: inside the crop, is there ONE instance of "
            f"'{name}', or a ROW/GROUP of several near-identical "
            f"instances side by side? Count only what is VISIBLY "
            f"there — do not guess beyond the pixels.\n\n"
            'Reply with ONLY a JSON object, no other text:\n'
            '{"multiplicity": "single"|"row", '
            '"count": <int — 1 if single, the visible count if row>, '
            '"confidence": "high"|"medium"|"low", '
            '"why": "<one short sentence>"}')


def prompt_b(name, crop_local, row_local, k):
    return (f"IMAGE 1 (OBSERVED — detection crop of the real room's "
            f"'{name}'):\n{crop_local}\n\n"
            f"IMAGE 2 (PROPOSED STAND-IN — {k} copies of one library "
            f"asset placed side by side):\n{row_local}\n\n"
            f"QUESTION: in a rebuilt version of this room, would the "
            f"proposed composition READ AS the observed object — or "
            f"would it read as {k} separate objects where the room "
            f"has one?\n\n"
            'Reply with ONLY a JSON object, no other text:\n'
            '{"reads_as_observed": true|false, '
            '"confidence": "high"|"medium"|"low", '
            '"why": "<one short sentence>"}')


def run_call(folder, prompt):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "prompt.txt").write_text(prompt, encoding="utf-8")
    try:
        ans, dt = _judge(prompt, folder)
    except Exception as ex:
        ans, dt = {"error": str(ex)[:150]}, None
    ans["wall_s"] = dt
    (folder / "reply.json").write_text(json.dumps(ans, indent=1),
                                       encoding="utf-8")
    return ans


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    ap.add_argument("--runs", type=int, default=3)
    a = ap.parse_args()

    cdir = paths.compose_dir(a.scene)
    root = cdir / "sub_experiment" / "_multiplicity_probe"
    root.mkdir(parents=True, exist_ok=True)
    sh = json.loads((cdir / "shopping.json").read_text("utf-8"))
    names = {s["id"]: s["name"] for s in sh["subs_deferred"]}
    names.update({it["id"]: it["name"] for it in sh["items"]})

    # book uid for B from the current obj_022 picks
    pk = json.loads((cdir / "sub_experiment" / "obj_022" /
                     "cp4_aligned" / "picks.json").read_text("utf-8"))
    book_uid = next(r["pick"]["uid"] for r in pk["subs"]
                    if r["id"] == "obj_034" and r.get("pick"))
    b_cases = [(lab, oid, uid or book_uid, k)
               for lab, oid, uid, k in B_CASES]

    # ---- stimuli
    jobs = []          # (kind, label, folder, prompt)
    for oid in A_SET:
        cp = best_crop(a.scene, oid)
        if cp is None:
            print(f"[probe] {oid}: no crop, skipped")
            continue
        for r in range(1, a.runs + 1):
            folder = root / f"A_{oid}_r{r}"
            folder.mkdir(parents=True, exist_ok=True)
            local = folder / "crop.png"
            shutil.copyfile(cp, local)
            jobs.append(("A", f"{oid}", folder,
                         prompt_a(names.get(oid, oid), local.name)))
    for lab, oid, uid, k in b_cases:
        cp = best_crop(a.scene, oid)
        row_png = root / f"row_{lab}.png"
        if not row_png.exists():
            render_row(uid, k, row_png)
        for r in range(1, a.runs + 1):
            folder = root / f"B_{lab}_r{r}"
            folder.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(cp, folder / "crop.png")
            shutil.copyfile(row_png, folder / "row.png")
            jobs.append(("B", lab, folder,
                         prompt_b(names.get(oid, oid), "crop.png",
                                  "row.png", k)))

    print(f"[probe] {len(jobs)} calls, concurrency {CONCURRENCY}")
    t0 = time.time()
    with ThreadPoolExecutor(CONCURRENCY) as ex:
        answers = list(ex.map(lambda j: run_call(j[2], j[3]), jobs))
    print(f"[probe] done in {time.time() - t0:.0f}s")

    # ---- record + page
    rec = {"scene": a.scene, "runs": a.runs, "a": {}, "b": {}}
    for (kind, lab, folder, _), ans in zip(jobs, answers):
        rec.setdefault(kind.lower(), {}).setdefault(lab, []).append(
            {k: ans.get(k) for k in
             ("multiplicity", "count", "reads_as_observed",
              "confidence", "why", "error", "wall_s")})
    (root / "record.json").write_text(json.dumps(rec, indent=1),
                                      encoding="utf-8")

    css = ("body{margin:0;background:#141414;color:#e8e8e8;font:15px/"
           "1.5 'Segoe UI',system-ui}.wrap{max-width:1400px;margin:0 "
           "auto;padding:24px 28px 100px}table{border-collapse:"
           "collapse;font-size:13px;margin:14px 0}th,td{border:1px "
           "solid #2e2e2e;padding:5px 9px;text-align:left;"
           "vertical-align:top}th{background:#1c1c1c}img{max-height:"
           "110px;display:block}.ok{color:#3fbf6f}.mix{color:#ff9d3d;"
           "font-weight:600}.note{background:#1c1c1c;border-left:3px "
           "solid #ffd479;padding:10px 16px;margin:14px 0}")
    h = ['<!doctype html><meta charset="utf-8">',
         '<title>multiplicity probe</title>',
         f'<style>{css}</style><div class="wrap">',
         '<h1>Multiplicity probe — can the agent carry the k '
         'decision?</h1>',
         '<div class="note"><b>What this gets:</b> detection crops '
         '(probe A) and crop + rendered k-tile stand-in pairs (probe '
         'B). <b>What it decides:</b> nothing — it measures whether '
         'the judged answers are right AND stable across '
         f'{a.runs} identical runs. <b>A mistake looks like:</b> '
         'verdicts flipping between runs (tail noise), a single '
         'called a row (fabrication license), a row called single '
         '(books collapse).</div>']
    for kind, title, cols in (
            ("a", "Probe A — one instance or a row? (graph-stage "
             "question)", ("multiplicity", "count")),
            ("b", "Probe B — does the k-tile stand-in read as the "
             "observed object? (pick-time question)",
             ("reads_as_observed",))):
        h.append(f"<h2>{title}</h2><table><tr><th>case</th>"
                 "<th>stimulus</th>"
                 + "".join(f"<th>run {i+1}</th>" for i in range(a.runs))
                 + "<th>stable?</th></tr>")
        for lab, rr in rec[kind].items():
            key = cols[0]
            vals = [str(x.get(key)) + (f" ×{x.get('count')}"
                    if kind == "a" and x.get("multiplicity") == "row"
                    else "") for x in rr]
            stable = ("<span class=ok>YES</span>"
                      if len(set(vals)) == 1
                      else "<span class=mix>FLIPS</span>")
            if kind == "a":
                stim = f'<img src="A_{lab}_r1/crop.png">'
            else:
                stim = (f'<img src="B_{lab}_r1/crop.png">'
                        f'<img src="row_{lab}.png">')
            cells = "".join(
                f"<td>{html.escape(v)}<br><small>{html.escape(str(x.get('confidence')))}"
                f" — {html.escape(str(x.get('why'))[:90])}</small></td>"
                for v, x in zip(vals, rr))
            h.append(f"<tr><td><b>{lab}</b></td><td>{stim}</td>"
                     f"{cells}<td>{stable}</td></tr>")
        h.append("</table>")
    h.append("</div>")
    (root / "index.html").write_text("\n".join(h), encoding="utf-8")
    print(f"[probe] review page: {root / 'index.html'}")


if __name__ == "__main__":
    main()
