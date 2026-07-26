"""SP1 — self-rendered pano rig from the splat (PLAN_SELF_PANO_RIG.md,
option b rig-direct; user decisions 2026-07-26: standpoint (0, ·, 0), eye
1.6 m above floor).

Renders crop_pano.py's 20-camera rig (8 yaws @ pitch 0 · 8 @ -40 floor ·
4 @ +40 ceiling, FOV 75, 960 px = the pano-crop sharpness benchmark of
12.8 px/deg) DIRECTLY from the splat via the analyzer's WSL gsplat path,
mini-G1 verifies every camera, and writes a contact-sheet review page.
STOPS THERE — SP2 (detect) only after the user passes SP1.

Run:  python pano_rig.py --scene bedroom_marble
Out:  out/<scene>/rig_sp0/sp_*.png + targets.json + sp1_review.html
"""
import argparse, json, math, subprocess, sys
from pathlib import Path
import numpy as np

import paths
from sweep_recenter import c2w_from_eye_aim, corr_check
from analyzer.cams_from_transforms import MatCam, _rows_opencv

r3 = paths.load_r3()
HERE = Path(__file__).parent

RINGS = [(0, 8), (-40, 8), (40, 4)]     # (pitch deg, n yaws) — crop_pano rig
FOV = 75.0
RES = 960
EYE_H = 1.6
CORR_MIN = 0.25


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    a = ap.parse_args()
    sc = a.scene
    sd = paths.scene_dir(sc)
    outd = sd / "rig_sp0"
    outd.mkdir(exist_ok=True)

    # eye: (0, ·, 0) at 1.6 m above the splat floor. RAW up = -y for marble
    # bundles, so "1.6 m up" = floor_y - 1.6.
    man = json.loads((sd / "scene_manifest_sweep.json").read_text())
    floor_y = man["frame"]["floor_y"]
    up_sign = -1 if man["frame"]["up"][1] < 0 else 1
    eye = [0.0, floor_y + up_sign * EYE_H, 0.0]
    print(f"[sp1] eye {eye} (floor_y {floor_y}, up sign {up_sign})", flush=True)

    # rig targets: yaw 0 = +z, yaw 90 = +x; pitch>0 looks UP (toward
    # ceiling = up_sign * y)
    targets = []
    for pitch, nyaw in RINGS:
        for i in range(nyaw):
            yaw = 360.0 * i / nyaw
            ry, rp = math.radians(yaw), math.radians(pitch)
            d = [math.sin(ry) * math.cos(rp),
                 up_sign * math.sin(rp),
                 math.cos(ry) * math.cos(rp)]
            tag = (f"sp_y{int(round(yaw)):03d}_"
                   f"p{'m' if pitch < 0 else 'p'}{abs(pitch):02d}")
            targets.append({"name": tag, "label": tag, "eye": eye,
                            "aim": [eye[0] + d[0], eye[1] + d[1],
                                    eye[2] + d[2]],
                            "fov": FOV, "yaw": yaw, "pitch": pitch})
    tf = outd / "targets.json"
    if not tf.exists():
        tf.write_text(json.dumps(targets, indent=1))
    print(f"[sp1] rig: {len(targets)} cameras", flush=True)

    def to_wsl(p):
        p = str(Path(p).resolve())
        return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")

    if not all((outd / f"{t['name']}.png").exists() for t in targets):
        cmd = ("wsl -d Ubuntu-24.04 -- bash -c \"cd /root/splat_analyzer && "
               "/root/miniconda3/envs/splatanalyzer/bin/python "
               f"'{to_wsl(HERE / 'analyzer' / 'render_targets_wsl.py')}' "
               f"--targets '{to_wsl(tf)}' --ply '{to_wsl(paths.ply(sc))}' "
               f"--out '{to_wsl(outd)}' --res {RES} --prefix sp_\"")
        print("[sp1] rendering rig via WSL gsplat ...", flush=True)
        subprocess.run(cmd, check=True, timeout=1800, shell=True)
    targets = json.loads(tf.read_text())

    # mini-G1: verify every rig camera against its render
    print("[sp1] loading splat for camera verification ...", flush=True)
    xyz, rgb, _a, _r = r3.load_splat(str(paths.ply(sc)), opacity_min=0.3)
    n_ok = 0
    for t in targets:
        t.setdefault("file", t["name"] + ".png")
        if "c2w" not in t:
            t["c2w"] = c2w_from_eye_aim(t["eye"], t["aim"],
                                        [0.0, -1.0, 0.0]).tolist()
        M = np.array(t["c2w"])
        fl = 192 / (2 * math.tan(math.radians(t["fov"]) / 2))
        cam = MatCam(_rows_opencv(M), M[:3, 3], fl, 96, 96, 192, 192)
        corr = corr_check(xyz, rgb, cam, outd / t["file"])
        t["g1_corr"] = round(corr, 3)
        n_ok += corr >= CORR_MIN
        print(f"[sp1] {t['file']}: corr {corr:+.3f} "
              f"{'ok' if corr >= CORR_MIN else 'FAIL'}", flush=True)
    tf.write_text(json.dumps(targets, indent=1))
    print(f"[sp1] verified {n_ok}/{len(targets)}", flush=True)

    # contact sheet, grouped by ring
    rows = []
    for pitch, _ in RINGS:
        cells = "".join(
            f'<div class=crop><a href="{t["file"]}" target=_blank>'
            f'<img src="{t["file"]}" loading=lazy></a>'
            f'<span>{t["name"]} · corr {t["g1_corr"]:+.2f}'
            f'{"" if t["g1_corr"] >= CORR_MIN else " ⚠"}</span></div>'
            for t in targets if t["pitch"] == pitch)
        rows.append(f"<h2>pitch {pitch:+d}°</h2><div class=grid>{cells}</div>")
    html = f"""<!doctype html><meta charset="utf-8">
<title>SP1 — self-rendered pano rig ({sc})</title>
<style>body{{font:14px system-ui;background:#14161a;color:#dfe3ea;margin:20px}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}}
.crop img{{width:100%;border:1px solid #333;border-radius:6px}}
.crop span{{display:block;font-size:12px;color:#9aa3b0;margin-top:2px}}
.note{{color:#9aa3b0;max-width:100ch}}h2{{margin-top:22px}}</style>
<h1>SP1 — self-rendered pano rig · {sc}</h1>
<p class=note><b>What:</b> crop_pano's 20-camera rig (FOV 75, 960 px =
12.8 px/deg, the pano-crop sharpness benchmark) rendered DIRECTLY from the
splat at standpoint (0, ·, 0), eye {EYE_H} m above floor — option (b),
zero registration by construction. Every camera mechanically verified
(corr vs z-buffer model; ⚠ = unverified, excluded downstream).
<b>Look for:</b> (1) right-side-up rooms, (2) pitch 0 ring sweeps the whole
horizon with overlap, (3) pitch −40 shows floor objects / +40 ceiling,
(4) splat render quality vs the Marble pano crops you know — this is the
image-quality axis SP2 will measure with detection stats.</p>
{''.join(rows)}"""
    (outd / "sp1_review.html").write_text(html, encoding="utf-8")
    print(f"[sp1] wrote {outd / 'sp1_review.html'} — AWAITING USER VERDICT",
          flush=True)


if __name__ == "__main__":
    main()
