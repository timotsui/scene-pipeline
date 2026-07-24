"""Step 10 — graph-cut-run: cut one object's Gaussians out of a scene splat.

Drives GaussianCut (WSL env `gaussiancut`, patched repo /root/gaussiancut —
see ENV.md) on the Step-7 dataset + Step-9 masks, producing:

  out/<scene>/cut/<object>/foreground.ply   the object's Gaussians (fine cut)
  out/<scene>/cut/<object>/background.ply   scene minus object, same property
                                            layout as gen_raw.ply
  out/<scene>/cut/<object>/stats.json       counts, threshold + reasoning,
                                            runtimes, GaussianCut metrics
  out/<scene>/cut/<object>/graphcut_dir_listing.txt   raw output dir listing
  out/<scene>/cut/<object>/logs/            coarse sweep + fine run logs
  out/<scene>/cut/<object>/_scaffold/       fabricated cfg_args, runner.sh,
                                            derive_background.py (provenance)

This script is PURE ORCHESTRATION: Windows python, stdlib only (no torch, no
GPU libs). All cutting runs inside WSL via the env python (ENV.md section 2).
wsl.exe is invoked from python subprocess (no MSYS layer, so the Git-Bash
URL-mangling gotcha in ENV.md does not apply).

WSL-side scene assembly (copied local for IO speed, layout per
FEASIBILITY_GAUSSIANCUT.md section 2a):

  /root/cut_scenes/<scene>__<object>/
    source/images/<view>.png            15 views (from out/.../cut/dataset)
    source/sparse/0/{cameras.txt,images.txt,points3D.ply}
    source/multiview_masks/<view>.png   8 masks (only views seeing the object)
    model/cfg_args                      fabricated Namespace(...) text
    model/point_cloud/iteration_1/point_cloud.ply   copy of gen_raw.ply
    logs/                               run logs (also copied back)
    runner_fine.sh, derive_background.py, background.ply, done markers

SEMANTICS PINNED FROM CODE (citations into the reference clone
Research/code/reference/gaussiancut/gaussian-splatting/):

* foreground_threshold denominator: only cameras WITH masks are processed
  (utils/render_utils.py:229-275 iterates over mask files, not cameras).
  The custom kernel accumulates, per Gaussian, cnt += alpha*T and
  weights += mask_pixel*alpha*T over every pixel it covers in those views
  (submodules/diff-gaussian-rasterization/cuda_rasterizer/apply_weights.cu:370-371).
  score = weights/cnt = fraction of the Gaussian's total rendered
  contribution ACROSS THE MASKED VIEWS ONLY that lands inside the masks;
  Gaussians never visible in any masked view get cnt==0 -> score forced 0
  (render_utils.py:327-328) -> background seed.
* The threshold only selects the coarse source/sink SETS (used for the fine
  stage's KMeans cluster centers + mean colors, utils/graphcut.py:105-117);
  the CONTINUOUS scores feed the terminal edges directly
  (utils/graphcut.py:137,149-152). Hence: prefer the strictest threshold
  that keeps a plausible object-sized source set (purity of the cluster
  seed beats completeness; the min-cut can grow the region).
* remove_source.pt: remove[i]=1  <=>  maxflow segment 1 = SINK = BACKGROUND
  (utils/graphcut.py:162-165); the saved foreground gaussians_source.ply
  keeps exactly the remove==0 rows in input order (utils/graphcut.py:169-177,
  no reordering anywhere). background.ply is therefore gen_raw rows where
  remove==1, derived by _scaffold/derive_background.py inside the WSL env.

Usage:
  python run_cut.py --scene bedroom_marble --object obj_004            # all
  python run_cut.py ... --phase assemble|sweep|decide|launch|status|wait|extract
  python run_cut.py ... --thresholds 0.9          # sweep a subset (resumable)
  python run_cut.py ... --threshold 0.6           # skip auto-pick
  python run_cut.py ... --force                   # redo from scratch

Idempotent: finished phases are detected from files on disk and skipped.
Exit codes: 0 ok / 2 sanity-stop (absurd counts, missing inputs) /
3 fine stage exceeded --max-hours / 4 fine stage failed without outputs.
"""
import argparse
import json
import os
import re
import subprocess
import sys
import tempfile
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import paths  # noqa: E402

DISTRO = "Ubuntu-24.04"
ENV_PY = "/root/miniconda3/envs/gaussiancut/bin/python"
GS_DIR = "/root/gaussiancut/gaussian-splatting"
WSL_ROOT = "/root/cut_scenes"

DEFAULT_SWEEP = [0.9, 0.6, 0.3]     # candidates, coarse-only (cheap, GPU)
SEED_MIN = 300                      # floor for KMeans-5 source cluster geometry
PURITY_MIN = 0.995                  # required seed fraction within box+0.15 m
FALLBACK_BAND = (300, 40_000)       # only if no manifest box census available
POLL_SECONDS = 60
EXPECT_IMAGES = 15
EXPECT_MASKS = 8


# ---------- small helpers ----------

def to_wsl(p) -> str:
    p = Path(p).resolve()
    drive = p.drive[0].lower()
    return "/mnt/{}/{}".format(drive, p.as_posix()[3:])


def wsl(cmd, timeout=540, check=True):
    """Run a bash command inside the WSL distro, capture output.

    The command is shipped as a script FILE, never inline: `wsl -- bash -c X`
    parses X twice (the distro's default shell expands $()/quotes first, then
    the inner bash re-parses the expansion) — bitten during Step 10.
    """
    fd, tmp = tempfile.mkstemp(suffix=".sh", prefix="runcut_")
    try:
        with os.fdopen(fd, "w", newline="\n") as f:
            f.write(cmd + "\n")
        r = subprocess.run(["wsl", "-d", DISTRO, "--", "bash", to_wsl(tmp)],
                           capture_output=True, text=True, timeout=timeout)
    finally:
        os.unlink(tmp)
    if check and r.returncode != 0:
        raise RuntimeError("WSL command failed ({}):\n{}\nstdout: {}\nstderr: {}"
                           .format(r.returncode, cmd, r.stdout[-2000:], r.stderr[-2000:]))
    return r


def log(msg):
    print("[{}] {}".format(time.strftime("%H:%M:%S"), msg), flush=True)


def read_ply_vertex_count(path):
    """Parse 'element vertex N' from a PLY header (binary-safe, no deps)."""
    with open(path, "rb") as f:
        head = f.read(4096)
    m = re.search(rb"element vertex (\d+)", head)
    if not m or b"end_header" not in head:
        raise RuntimeError("no valid PLY header in {}".format(path))
    return int(m.group(1))


# ---------- per-run path bundle ----------

class P:
    def __init__(self, scene, obj):
        self.scene, self.obj = scene, obj
        self.scene_dir = paths.scene_dir(scene)
        self.gen_raw = paths.ply(scene)
        self.dataset = self.scene_dir / "cut" / "dataset"
        self.out = self.scene_dir / "cut" / obj
        self.logs = self.out / "logs"
        self.scaffold = self.out / "_scaffold"
        self.sweep_json = self.out / "coarse_sweep.json"
        self.stats_json = self.out / "stats.json"
        # WSL side
        self.w = "{}/{}__{}".format(WSL_ROOT, scene, obj)
        self.w_source = self.w + "/source"
        self.w_model = self.w + "/model"
        self.w_logs = self.w + "/logs"
        self.w_pc = self.w_model + "/point_cloud/iteration_1/point_cloud.ply"
        self.w_done = self.w + "/done_" + obj
        self.w_fine_log = self.w_logs + "/fine_{}.log".format(obj)
        self.w_graphcut = self.w_model + "/graphcut_" + obj

    def sweep_id(self, t):
        return "thr{:03d}".format(round(t * 100))

    def sweep_log(self, t):
        return self.logs / "coarse_{}.log".format(self.sweep_id(t))


# ---------- phase: assemble ----------

CFG_ARGS = ("Namespace(sh_degree=0, source_path='{src}', model_path='{mod}', "
            "images='images', resolution=-1, white_background=False, "
            "data_device='cuda', eval=False)")

MASK_CHECK = r"""
import glob, json, os, sys
from PIL import Image
import numpy as np
src = sys.argv[1]
masks = sorted(glob.glob(os.path.join(src, 'multiview_masks', '*')))
imgs = {os.path.basename(p).split('.')[0] for p in glob.glob(os.path.join(src, 'images', '*'))}
rep = []
ok = True
for mp in masks:
    im = Image.open(mp)
    a = np.array(im)
    vals = sorted(int(v) for v in np.unique(a))
    stem = os.path.basename(mp).split('.')[0]
    good = im.mode == 'L' and set(vals) <= {0, 255} and stem in imgs
    ok &= good
    rep.append({'mask': os.path.basename(mp), 'mode': im.mode, 'size': im.size,
                'values': vals, 'stem_matches_image': stem in imgs, 'ok': good})
print(json.dumps({'ok': ok, 'n_masks': len(masks), 'masks': rep}))
"""


def phase_assemble(p, force):
    if force:
        wsl("rm -rf {}".format(p.w))
    marker = p.w + "/.assembled"
    if wsl("test -f {} && echo yes || echo no".format(marker)).stdout.strip() == "yes":
        log("assemble: already done (marker present), skipping")
        return
    for d in (p.out, p.logs, p.scaffold):
        d.mkdir(parents=True, exist_ok=True)
    if not p.dataset.exists() or not p.gen_raw.exists():
        log("FATAL: dataset or gen_raw.ply missing"); sys.exit(2)

    log("assemble: copying dataset + splat into {}".format(p.w))
    ds, raw = to_wsl(p.dataset), to_wsl(p.gen_raw)
    wsl("set -e; mkdir -p {w}/source {w}/logs {w}/model/point_cloud/iteration_1; "
        "rm -rf {w}/source/images {w}/source/sparse {w}/source/multiview_masks; "
        "cp -r {ds}/images {w}/source/; "
        "cp -r {ds}/sparse {w}/source/; "
        "cp -r {ds}/multiview_masks {w}/source/; "
        "cp {raw} {w}/model/point_cloud/iteration_1/point_cloud.ply"
        .format(w=p.w, ds=ds, raw=raw), timeout=540)

    # fabricate cfg_args (authored Windows-side for provenance, LF endings)
    cfg = CFG_ARGS.format(src=p.w_source, mod=p.w_model)
    with open(p.scaffold / "cfg_args", "w", newline="\n") as f:
        f.write(cfg + "\n")
    wsl("cp {} {}/cfg_args".format(to_wsl(p.scaffold / "cfg_args"), p.w_model))

    # verify the copy
    checks = wsl(
        "echo IMAGES $(ls {w}/source/images | wc -l); "
        "echo MASKS $(ls {w}/source/multiview_masks | wc -l); "
        "echo SPARSE $(ls {w}/source/sparse/0 | wc -l); "
        "echo PLYBYTES $(stat -c %s {w}/model/point_cloud/iteration_1/point_cloud.ply); "
        "echo CFG $(cat {w}/model/cfg_args | head -c 60)".format(w=p.w)).stdout
    log("assemble checks:\n" + checks.strip())
    got = dict(re.findall(r"(IMAGES|MASKS|SPARSE|PLYBYTES) (\d+)", checks))
    if int(got.get("IMAGES", 0)) != EXPECT_IMAGES or int(got.get("MASKS", 0)) != EXPECT_MASKS \
            or int(got.get("SPARSE", 0)) != 3 or int(got.get("PLYBYTES", 0)) != p.gen_raw.stat().st_size:
        log("FATAL: assembled scene dir failed verification"); sys.exit(2)

    # mask contract check (L-mode, {0,255}, stems match) inside the env
    mc = (p.scaffold / "check_masks.py")
    with open(mc, "w", newline="\n") as f:
        f.write(MASK_CHECK)
    out = wsl("{} {} {}".format(ENV_PY, to_wsl(mc), p.w_source)).stdout.strip()
    rep = json.loads(out.splitlines()[-1])
    (p.out / "mask_contract_check.json").write_text(json.dumps(rep, indent=2))
    if not rep["ok"] or rep["n_masks"] != EXPECT_MASKS:
        log("FATAL: mask contract check failed — see mask_contract_check.json")
        sys.exit(2)
    wsl("touch {}".format(marker))
    log("assemble: OK ({} images, {} masks, splat {} bytes)"
        .format(got["IMAGES"], got["MASKS"], got["PLYBYTES"]))


# ---------- phase: coarse sweep ----------

def parse_coarse_log(text):
    d = {}
    for key, pat in [("kept", r"Number of gaussians kept:\s+(\d+)"),
                     ("removed", r"Number of gaussians removed:\s+(\d+)"),
                     ("total", r"Number of gaussians before:\s+(\d+)"),
                     ("processed_images", r"Processed images \(multiview\):\s+(\d+)")]:
        m = re.search(pat, text)
        d[key] = int(m.group(1)) if m else None
    return d


def load_sweep(p):
    if p.sweep_json.exists():
        return json.loads(p.sweep_json.read_text())
    return {"scene": p.scene, "object": p.obj, "runs": {}}


def phase_sweep(p, thresholds, force):
    sweep = load_sweep(p)
    for t in thresholds:
        key = "{:.2f}".format(t)
        lg = p.sweep_log(t)
        if not force and key in sweep["runs"] and sweep["runs"][key].get("kept") is not None:
            log("sweep {}: already done (kept={}), skipping".format(key, sweep["runs"][key]["kept"]))
            continue
        ident = p.sweep_id(t)
        wlog = "{}/coarse_{}.log".format(p.w_logs, ident)
        log("sweep {}: running coarse-only (identifier {})".format(key, ident))
        t0 = time.time()
        # --skip_gc 1 -> True (argparse type=bool quirk: any non-empty string)
        wsl("cd {gs} && {py} -u segment_render.py -m {mod} --scene_path {src} "
            "--identifier {id} --mask_type multiview --foreground_threshold {t} "
            "--skip_gc 1 > {lg} 2>&1".format(
                gs=GS_DIR, py=ENV_PY, mod=p.w_model, src=p.w_source,
                id=ident, t=t, lg=wlog), timeout=540)
        dt = time.time() - t0
        wsl("cp {} {}".format(wlog, to_wsl(lg)))
        parsed = parse_coarse_log(lg.read_text(errors="replace"))
        parsed["seconds"] = round(dt, 1)
        parsed["identifier"] = ident
        sweep["runs"][key] = parsed
        p.sweep_json.write_text(json.dumps(sweep, indent=2))
        log("sweep {}: kept={} removed={} total={} images={} ({}s)".format(
            key, parsed["kept"], parsed["removed"], parsed["total"],
            parsed["processed_images"], parsed["seconds"]))
        if parsed["processed_images"] != EXPECT_MASKS:
            log("FATAL: coarse processed {} images, expected {} masks"
                .format(parsed["processed_images"], EXPECT_MASKS))
            sys.exit(2)
    return sweep


# ---------- phase: decide threshold ----------
#
# The threshold's ONLY downstream effect is which Gaussians form the coarse
# source/sink SETS seeding the fine stage's KMeans cluster centers + mean
# colors (graphcut.py:105-117); the continuous per-Gaussian scores drive the
# terminal edges regardless of threshold (graphcut.py:137,149-152). So the
# decision is measured, not guessed:
#   1. census: count gen_raw Gaussians inside the object's manifest AABB
#      (calibrates what "object-sized" means for THIS splat's density);
#   2. purity: fraction of each candidate's coarse seeds within AABB+0.15 m
#      (a contaminated seed puts KMeans centers off-object — the real risk);
#   3. choose the LOWEST candidate with purity >= PURITY_MIN and
#      seeds >= SEED_MIN (lowest maximizes seed coverage for cluster
#      geometry, per upstream's own 0.3-for-inward-scenes guidance; the
#      purity gate is what upstream lacks and what protects the known
#      lamp-window contact zone).
# Final-output plausibility band (gates nothing, flagged in stats):
#   [max(SEED_MIN, census/4), 4*census].

CENSUS_PURITY = r"""
import json, sys
import numpy as np
from plyfile import PlyData
model, aabb_json, idents = sys.argv[1], sys.argv[2], sys.argv[3:]
aabb = json.loads(aabb_json)
mn, mx = np.array(aabb["min"]), np.array(aabb["max"])
v = PlyData.read(model + "/point_cloud/iteration_1/point_cloud.ply")["vertex"].data
xyz = np.stack([v["x"], v["y"], v["z"]], axis=1)
out = {"census_in_box": int(np.all((xyz >= mn) & (xyz <= mx), axis=1).sum()),
       "candidates": {}}
for ident in idents:
    sv = PlyData.read("{}/graphcut_{}/gaussians_source_multiview.ply"
                      .format(model, ident))["vertex"].data
    sxyz = np.stack([sv["x"], sv["y"], sv["z"]], axis=1)
    inb = np.all((sxyz >= mn - 0.15) & (sxyz <= mx + 0.15), axis=1)
    out["candidates"][ident] = {
        "n_seeds": len(sxyz),
        "purity_m0.15": round(float(inb.mean()), 4) if len(sxyz) else 0.0,
        "n_outliers": int((~inb).sum())}
print(json.dumps(out))
"""


def manifest_aabb(p):
    mf = paths.manifest(p.scene)
    for o in json.loads(mf.read_text()).get("objects", []):
        if o.get("id") == p.obj:
            return {"min": o["aabb_min"], "max": o["aabb_max"]}
    return None


def phase_decide(p, forced_threshold):
    sweep = load_sweep(p)
    if forced_threshold is not None:
        sweep["chosen_threshold"] = forced_threshold
        sweep["reasoning"] = "manually forced via --threshold"
        p.sweep_json.write_text(json.dumps(sweep, indent=2))
        log("decide: threshold forced to {}".format(forced_threshold))
        return forced_threshold
    runs = {float(k): v for k, v in sweep["runs"].items() if v.get("kept") is not None}
    if not runs:
        log("FATAL: no sweep results to decide from"); sys.exit(2)
    counts = {t: runs[t]["kept"] for t in sorted(runs)}

    aabb = manifest_aabb(p)
    if aabb is None:
        log("WARNING: no manifest AABB for {}; falling back to band {}".format(
            p.obj, FALLBACK_BAND))
        sweep["final_band"] = list(FALLBACK_BAND)
        ok = [t for t, v in runs.items()
              if FALLBACK_BAND[0] <= v["kept"] <= FALLBACK_BAND[1]]
        chosen = max(ok) if ok else None
        purity = None
    else:
        script = p.scaffold / "census_purity.py"
        with open(script, "w", newline="\n") as f:
            f.write(CENSUS_PURITY)
        idents = [runs[t]["identifier"] for t in sorted(runs)]
        r = wsl("{} {} {} '{}' {}".format(
            ENV_PY, to_wsl(script), p.w_model,
            json.dumps(aabb).replace(" ", ""), " ".join(idents)))
        cp = json.loads(r.stdout.strip().splitlines()[-1])
        census = cp["census_in_box"]
        purity = cp["candidates"]
        sweep["box_census"] = census
        sweep["seed_purity"] = purity
        sweep["final_band"] = [max(SEED_MIN, census // 4), 4 * census]
        eligible = [t for t in sorted(runs)
                    if purity[runs[t]["identifier"]]["purity_m0.15"] >= PURITY_MIN
                    and runs[t]["kept"] >= SEED_MIN]
        chosen = min(eligible) if eligible else None

    if chosen is None:
        log("FATAL sanity-stop: no eligible threshold. counts={} purity={}"
            .format(counts, purity))
        sweep["chosen_threshold"] = None
        sweep["reasoning"] = ("SANITY STOP: no candidate passed the "
                              "purity/size gates; counts {}".format(counts))
        p.sweep_json.write_text(json.dumps(sweep, indent=2))
        sys.exit(2)

    sweep["chosen_threshold"] = chosen
    sweep["reasoning"] = (
        "Score semantics (apply_weights.cu:370-371, render_utils.py:229-275,"
        "327-329): score = in-mask fraction of the Gaussian's rendered "
        "contribution over the {n} MASKED views only (unmasked views never "
        "dilute; invisible-in-masked-views => score 0 => background). "
        "Threshold only seeds the fine stage's KMeans clusters/colors "
        "(graphcut.py:105-117); continuous scores drive terminal edges "
        "(graphcut.py:137,149-152). Decision: manifest-box census = {c} "
        "Gaussians => final band {band}; candidate counts {counts}; seed "
        "purity vs box+0.15m {pur}; rule = lowest threshold with purity >= "
        "{pm} and seeds >= {sm} => {ch}. Upstream's 0.3 hint targets "
        "360-inward dilution our mask setup does not have; the purity gate "
        "protects the known lamp-window contact zone."
        .format(n=EXPECT_MASKS, c=sweep.get("box_census"),
                band=sweep.get("final_band"), counts=counts, pur=purity,
                pm=PURITY_MIN, sm=SEED_MIN, ch=chosen))
    p.sweep_json.write_text(json.dumps(sweep, indent=2))
    log("decide: counts={} census={} -> chosen threshold {}".format(
        counts, sweep.get("box_census"), chosen))
    return chosen


# ---------- phase: launch fine (coarse+fine full run, nohup + heartbeat) ----------

RUNNER = """#!/bin/bash
exec >> {lg} 2>&1 < /dev/null
echo "RUN_START $(date -Is) epoch=$(date +%s)"
( while true; do echo "HB $(date -Is)"; sleep 60; done ) &
HB=$!
cd {gs}
{py} -u segment_render.py -m {mod} --scene_path {src} --identifier {id} \
  --mask_type multiview --foreground_threshold {thr}
code=$?
kill $HB 2>/dev/null
echo "RUN_EXIT code=$code $(date -Is) epoch=$(date +%s)"
echo $code > {done}
"""


def phase_launch(p, threshold, force):
    """Launch the fine run as a DETACHED WINDOWS wsl.exe process.

    WSL kills the whole session's process tree when the launching wsl.exe
    exits — nohup and even setsid do NOT survive (verified during Step 10).
    A detached Windows process keeps its wsl.exe (and thus the WSL session)
    alive until the runner script finishes; completion is detected from the
    done-marker file, never from process events.
    """
    if wsl("test -f {} && echo yes || echo no".format(p.w_done)).stdout.strip() == "yes" and not force:
        log("launch: done marker already present; skipping (use --force to redo)")
        return
    if force:
        wsl("rm -f {}; rm -rf {}".format(p.w_done, p.w_graphcut))
    runner = p.scaffold / "runner_fine.sh"
    with open(runner, "w", newline="\n") as f:
        f.write(RUNNER.format(gs=GS_DIR, py=ENV_PY, mod=p.w_model, src=p.w_source,
                              id=p.obj, thr=threshold, done=p.w_done, lg=p.w_fine_log))
    wsl("cp {} {}/runner_fine.sh".format(to_wsl(runner), p.w))
    flags = (subprocess.DETACHED_PROCESS | subprocess.CREATE_NEW_PROCESS_GROUP
             | getattr(subprocess, "CREATE_NO_WINDOW", 0))
    proc = subprocess.Popen(
        ["wsl", "-d", DISTRO, "--", "bash", "{}/runner_fine.sh".format(p.w)],
        creationflags=flags, stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    log("launch: fine run started at threshold {} (detached wsl.exe, windows "
        "pid {}); log {}".format(threshold, proc.pid, p.w_fine_log))


def fine_status(p):
    """One short poll: (done_code or None, last tqdm/log fragment)."""
    r = wsl("test -f {done} && echo DONE $(cat {done}) || echo RUNNING; "
            "test -f {lg} && tail -c 3000 {lg} | tr '\\r' '\\n' | "
            "grep -v '^$' | tail -n 4 || echo NO_LOG"
            .format(done=p.w_done, lg=p.w_fine_log), check=False)
    lines = r.stdout.strip().splitlines()
    code = None
    if lines and lines[0].startswith("DONE"):
        parts = lines[0].split()
        code = int(parts[1]) if len(parts) > 1 else -1
    tail = "\n".join(lines[1:])
    return code, tail


def phase_wait(p, max_hours):
    t0 = time.time()
    while True:
        code, tail = fine_status(p)
        log("fine status: {}\n{}".format("EXIT {}".format(code) if code is not None
                                         else "running", tail))
        if code is not None:
            return code
        if time.time() - t0 > max_hours * 3600:
            log("STOP: fine stage exceeded {} h budget — leaving it running, "
                "report to orchestrator".format(max_hours))
            sys.exit(3)
        time.sleep(POLL_SECONDS)


# ---------- phase: extract ----------

DERIVE = r'''"""Derive background.ply from remove_source.pt (runs in the WSL env).

Semantics verified in gaussiancut/gaussian-splatting/utils/graphcut.py:
  remove[i] = 1  <=>  maxflow.get_segment(i) == 1  == SINK  == BACKGROUND
  (lines 162-165); gaussians_source.ply (FOREGROUND) keeps remove==0 rows in
  input order (lines 169-177; no reordering of the loaded model anywhere).
"""
import json, sys
import numpy as np
import torch
from plyfile import PlyData, PlyElement

remove_pt, input_ply, fg_ply, out_ply = sys.argv[1:5]
rem = torch.load(remove_pt, map_location="cpu")
rem = rem.numpy() if torch.is_tensor(rem) else np.asarray(rem)
uniq = sorted(float(v) for v in np.unique(rem))
assert set(uniq) <= {0.0, 1.0}, "unexpected values in remove_source.pt: {}".format(uniq)

ply = PlyData.read(input_ply)
v = ply["vertex"].data
n = len(v)
assert rem.shape[0] == n, "remove length {} != vertex count {}".format(rem.shape[0], n)

bg_mask = rem > 0.5                      # 1 = sink = background
bg = v[bg_mask]                          # preserves gen_raw property layout
PlyData([PlyElement.describe(bg, "vertex")], text=False).write(out_ply)

fg_count = int((~bg_mask).sum())
bg_count = int(bg_mask.sum())
fg_vertices = len(PlyData.read(fg_ply)["vertex"].data)
assert fg_vertices == fg_count, \
    "gaussians_source.ply has {} vertices but remove==0 count is {}".format(fg_vertices, fg_count)
print(json.dumps({"total": n, "fg_count": fg_count, "bg_count": bg_count,
                  "fg_ply_vertices": fg_vertices,
                  "remove_unique_values": uniq,
                  "cross_check": "fg_ply_vertices == (remove==0).sum() PASSED"}))
'''


def parse_fine_log(text):
    d = {}
    m = re.search(r"Maximum flow:\s*([0-9.eE+-]+)", text)
    d["max_flow"] = float(m.group(1)) if m else None
    m = re.search(r"number of components in each cluster:\s*\[\s*(\d+)\s+(\d+)\s*\]", text)
    d["maxflow_segment_counts"] = {"source_fg": int(m.group(1)),
                                   "sink_bg": int(m.group(2))} if m else None
    d["coarse"] = parse_coarse_log(text)
    starts = re.findall(r"RUN_START .* epoch=(\d+)", text)
    exits = re.findall(r"RUN_EXIT code=(-?\d+) .* epoch=(\d+)", text)
    d["run_seconds"] = (int(exits[0][1]) - int(starts[0])) if starts and exits else None
    d["exit_code"] = int(exits[0][0]) if exits else None
    frags = re.findall(r"Processing Gaussians:\s*(\d+%[^\n]*)", text.replace("\r", "\n"))
    d["fine_loop_last_progress"] = frags[-1].strip() if frags else None
    return d


def phase_extract(p, force):
    have = all((p.out / f).exists() for f in ("foreground.ply", "background.ply", "stats.json"))
    if have and not force:
        log("extract: outputs already present, skipping"); return
    code, _ = fine_status(p)
    if code is None:
        log("extract: fine run not finished yet"); sys.exit(2)
    exist = wsl("test -f {g}/gaussians_source.ply && test -f {g}/remove_source.pt "
                "&& echo yes || echo no".format(g=p.w_graphcut)).stdout.strip()
    if exist != "yes":
        log("FATAL: fine outputs missing in {} (exit code {})".format(p.w_graphcut, code))
        sys.exit(4)
    if code != 0:
        log("WARNING: run exit code {} but graph-cut outputs exist (post-cut "
            "render step is allowed to fail; outputs are saved before it)".format(code))

    derive = p.scaffold / "derive_background.py"
    with open(derive, "w", newline="\n") as f:
        f.write(DERIVE)
    log("extract: deriving background.ply inside WSL env")
    r = wsl("{py} {sc} {g}/remove_source.pt {pc} {g}/gaussians_source.ply {w}/background.ply"
            .format(py=ENV_PY, sc=to_wsl(derive), g=p.w_graphcut, pc=p.w_pc, w=p.w),
            timeout=600)
    counts = json.loads(r.stdout.strip().splitlines()[-1])
    log("extract: derive says {}".format(counts))

    log("extract: copying artifacts back to {}".format(p.out))
    wsl("set -e; cp {g}/gaussians_source.ply {o}/foreground.ply; "
        "cp {w}/background.ply {o}/background.ply; "
        "ls -la {g}/ > {o}/graphcut_dir_listing.txt; "
        "cp {lg} {o}/logs/fine_{id}.log"
        .format(g=p.w_graphcut, w=p.w, o=to_wsl(p.out), lg=p.w_fine_log, id=p.obj),
        timeout=600)

    # independent Windows-side header checks
    fg_n = read_ply_vertex_count(p.out / "foreground.ply")
    bg_n = read_ply_vertex_count(p.out / "background.ply")
    total = read_ply_vertex_count(p.gen_raw)
    assert fg_n == counts["fg_count"] and bg_n == counts["bg_count"], \
        "copied PLY headers disagree with derive counts"
    assert fg_n + bg_n == total == counts["total"], \
        "fg {} + bg {} != total {}".format(fg_n, bg_n, total)

    sweep = load_sweep(p)
    band = sweep.get("final_band", list(FALLBACK_BAND))
    band_ok = band[0] <= fg_n <= band[1]
    fine = parse_fine_log((p.out / "logs" / "fine_{}.log".format(p.obj))
                          .read_text(errors="replace"))
    stats = {
        "scene": p.scene, "object": p.obj,
        "created": time.strftime("%Y-%m-%d %H:%M:%S"),
        "total_gaussians": total,
        "foreground_gaussians": fg_n,
        "background_gaussians": bg_n,
        "fg_plausible_band": band,
        "fg_in_plausible_band": band_ok,
        "threshold_used": sweep.get("chosen_threshold"),
        "threshold_reasoning": sweep.get("reasoning"),
        "coarse_sweep": sweep.get("runs"),
        "fine_run": fine,
        "remove_source_semantics": (
            "remove==1 -> maxflow sink -> BACKGROUND (graphcut.py:162-165); "
            "foreground gaussians_source.ply keeps remove==0 rows in input order "
            "(graphcut.py:169-177). Cross-checked at derive time: {}"
            .format(counts["cross_check"])),
        "derive_counts": counts,
        "outputs": {"foreground_ply": str(p.out / "foreground.ply"),
                    "background_ply": str(p.out / "background.ply")},
        "wsl_scene_dir": p.w,
    }
    p.stats_json.write_text(json.dumps(stats, indent=2))
    log("extract: DONE  fg={} bg={} total={} band_ok={}  -> {}".format(
        fg_n, bg_n, total, band_ok, p.stats_json))
    if not band_ok:
        log("WARNING: foreground count outside plausible band {} — flag for review".format(band))


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--scene", required=True)
    ap.add_argument("--object", required=True, dest="obj")
    ap.add_argument("--phase", default="all",
                    choices=["assemble", "sweep", "decide", "launch", "status",
                             "wait", "extract", "all"])
    ap.add_argument("--thresholds", default=None,
                    help="comma list of coarse sweep candidates (default {})"
                    .format(DEFAULT_SWEEP))
    ap.add_argument("--threshold", type=float, default=None,
                    help="skip auto-pick; force this fine-run threshold")
    ap.add_argument("--max-hours", type=float, default=3.0)
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()

    p = P(a.scene, a.obj)
    thresholds = ([float(x) for x in a.thresholds.split(",")]
                  if a.thresholds else list(DEFAULT_SWEEP))

    if a.phase in ("assemble", "all"):
        phase_assemble(p, a.force)
    if a.phase in ("sweep", "all"):
        phase_sweep(p, thresholds, a.force and a.phase == "sweep")
    if a.phase in ("decide", "all"):
        chosen = phase_decide(p, a.threshold)
    elif a.phase == "launch":
        chosen = a.threshold if a.threshold is not None else \
            load_sweep(p).get("chosen_threshold")
        if chosen is None:
            log("FATAL: no chosen threshold (run decide first)"); sys.exit(2)
    if a.phase in ("launch", "all"):
        phase_launch(p, chosen, a.force and a.phase == "launch")
    if a.phase == "status":
        code, tail = fine_status(p)
        log("fine status: {}\n{}".format(
            "EXIT {}".format(code) if code is not None else "running", tail))
        return
    if a.phase in ("wait", "all"):
        phase_wait(p, a.max_hours)
    if a.phase in ("extract", "all", "wait"):
        phase_extract(p, a.force and a.phase == "extract")


if __name__ == "__main__":
    main()
