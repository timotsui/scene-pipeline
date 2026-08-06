"""Self-rendered equirect pano from the splat (PLAN_SELF_PANO_RIG option-b+
addendum: pano as the canonical per-standpoint artifact — GPU once, then all
crops/strips are CPU resamples).

Renders 6 cube faces (fov 95 for margin, 2048 px) via the analyzer's WSL
gsplat path at the chosen standpoint, then stitches them into an equirect
png in crop_pano.py's EXACT convention (pano frame: +y up, image center =
+Z, theta toward +X). Pano frame <-> RAW is a pure rotation by construction
(rot 180 about z: d_raw = (-x_p, -y_p, z_p)), recorded in the meta sidecar —
NO mirror (unlike Marble's pano), NO registration, NO scale.

Mechanical verification (house rule): a pinhole crop resampled from the
stitched pano is correlated against the SAME view rendered directly from
the splat (the SP1 rig renders) — the full stitch+convention chain must
reproduce the direct render.

Run:  python pano_stitch.py --scene bedroom_marble
Out:  out/<scene>/rig_sp0/pano_selfrender.png (8192x4096) + _meta.json
"""
import argparse, json, math, subprocess
from pathlib import Path
import numpy as np
from PIL import Image

import paths
from sweep_recenter import c2w_from_eye_aim
from crop_pano import sample_equirect, crop_dirs

r3 = paths.load_r3()
HERE = Path(__file__).parent

FACE_RES = 2048
FACE_FOV = 95.0          # 90 + margin so face borders overlap
PANO_W, PANO_H = 8192, 4096   # 22.8 px/deg at the equator
EYE_H = 1.6

FACES = [("f_pz", [0, 0, 1]), ("f_px", [1, 0, 0]), ("f_nz", [0, 0, -1]),
         ("f_nx", [-1, 0, 0]), ("f_py", [0, 1, 0]), ("f_ny", [0, -1, 0])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    a = ap.parse_args()
    sc = a.scene
    sd = paths.scene_dir(sc)
    outd = sd / "rig_sp0"
    outd.mkdir(exist_ok=True)

    # Frame info source: legacy sweep manifest (bedroom-era scenes) ->
    # frame_bootstrap.json (fresh scenes, written by the intake module).
    # Both speak the SAME convention since 2026-08-06: the bundle frame
    # (y-down) — intake un-rotates the spz->ply converter's frame change,
    # so there is exactly one pano mapping pipeline-wide (A2 below).
    legacy = sd / "scene_manifest_sweep.json"
    boot = sd / "frame_bootstrap.json"
    if legacy.exists():
        fr = json.loads(legacy.read_text())["frame"]
    elif boot.exists():
        fr = json.loads(boot.read_text())
    else:
        raise SystemExit("[stitch] no frame info: run frame_bootstrap.py "
                         "--scene first (fresh scene), or provide the "
                         "legacy sweep manifest")
    signs = np.array([1.0, -1.0, 1.0])          # the A2 readability mirror
    floor_y = fr["floor_y"]
    up_sign = -1 if fr["up"][1] < 0 else 1
    eye = [0.0, floor_y + up_sign * EYE_H, 0.0]
    print(f"[stitch] eye {eye}", flush=True)

    # ---------- render the 6 faces (GPU, WSL, resumable) ----------
    tf = outd / "faces_targets.json"
    if not tf.exists():
        targets = [{"name": n, "label": n, "eye": eye,
                    "aim": [eye[0] + d[0], eye[1] + d[1], eye[2] + d[2]],
                    "fov": FACE_FOV} for n, d in FACES]
        tf.write_text(json.dumps(targets, indent=1))

    def to_wsl(p):
        p = str(Path(p).resolve())
        return "/mnt/" + p[0].lower() + p[2:].replace("\\", "/")

    if not all((outd / f"{n}.png").exists() for n, _ in FACES):
        cmd = ("wsl -d Ubuntu-24.04 -- bash -c \"cd /root/splat_analyzer && "
               "/root/miniconda3/envs/splatanalyzer/bin/python "
               f"'{to_wsl(HERE / 'analyzer' / 'render_targets_wsl.py')}' "
               f"--targets '{to_wsl(tf)}' --ply '{to_wsl(paths.ply(sc))}' "
               f"--out '{to_wsl(outd)}' --res {FACE_RES}\"")
        print("[stitch] rendering 6 cube faces via WSL gsplat ...", flush=True)
        subprocess.run(cmd, check=True, timeout=1800, shell=True)

    # ---------- stitch ----------
    f = FACE_RES / (2 * math.tan(math.radians(FACE_FOV) / 2))
    cxy = FACE_RES / 2
    face_img, face_R = {}, {}
    for n, d in FACES:
        face_img[n] = np.asarray(Image.open(outd / f"{n}.png").convert("RGB"),
                                 np.float32)
        M = c2w_from_eye_aim(eye, np.array(eye) + np.array(d, float),
                             [0.0, -1.0, 0.0])
        # rows: right, up, forward in RAW (opencv cols -> our row convention)
        face_R[n] = np.stack([M[:3, 0], -M[:3, 1], M[:3, 2]])

    # equirect pixel grid -> pano-frame dirs -> RAW dirs.
    # Pano frame = MIRROR-Y of raw (d_raw = (x_p, -y_p, z_p)) — deliberately
    # improper, same convention as Marble's pano export, because a flat
    # equirect only READS correctly (pan right across the image = turn right
    # in the world) when the pano frame flips handedness. The first stitch
    # used a pure rotation and the user immediately spotted the left-right
    # flip. Unlike Marble's, this mirror is DEFINED not estimated — still
    # zero registration risk; crops/lift invert the exact same mapping.
    uu, vv = np.meshgrid(np.arange(PANO_W) + 0.5, np.arange(PANO_H) + 0.5)
    theta = (uu / PANO_W) * 2 * np.pi - np.pi
    phi = (0.5 - vv / PANO_H) * np.pi
    d_p = np.stack([np.cos(phi) * np.sin(theta), np.sin(phi),
                    np.cos(phi) * np.cos(theta)], axis=-1).reshape(-1, 3)
    # sign class per scene vintage: y-down raws mirror y (the original A2
    # convention), y-up raws mirror x — either way det=-1, the readability
    # mirror, and the meta records which (crops/lift invert the same signs)
    d_raw = d_p * signs

    axes = {n: np.array(d, float) for n, d in FACES}
    comp = np.stack([d_raw @ axes[n] for n, _ in FACES], axis=1)
    face_pick = comp.argmax(axis=1)

    pano = np.zeros((PANO_H * PANO_W, 3), np.float32)
    for fi, (n, _) in enumerate(FACES):
        sel = face_pick == fi
        if not sel.any():
            continue
        rel = d_raw[sel] @ face_R[n].T          # RAW -> face cam (right,up,fwd)
        with np.errstate(divide="ignore", invalid="ignore"):
            pu = cxy + f * rel[:, 0] / rel[:, 2]
            pv = cxy - f * rel[:, 1] / rel[:, 2]
        pu = np.clip(pu, 0, FACE_RES - 1.001)
        pv = np.clip(pv, 0, FACE_RES - 1.001)
        u0 = pu.astype(np.int64); v0 = pv.astype(np.int64)
        du = (pu - u0)[:, None]; dv = (pv - v0)[:, None]
        img = face_img[n]
        pano[sel] = (img[v0, u0] * (1 - du) * (1 - dv)
                     + img[v0, u0 + 1] * du * (1 - dv)
                     + img[v0 + 1, u0] * (1 - du) * dv
                     + img[v0 + 1, u0 + 1] * du * dv)
    pano = pano.reshape(PANO_H, PANO_W, 3)
    pf = outd / "pano_selfrender.png"
    Image.fromarray(np.clip(pano, 0, 255).astype(np.uint8)).save(pf)
    print(f"[stitch] wrote {pf} ({PANO_W}x{PANO_H})", flush=True)
    (outd / "pano_selfrender_meta.json").write_text(json.dumps(
        {"scene": sc, "eye_raw": eye, "eye_height_m": EYE_H,
         "pano_to_raw_signs": signs.tolist(),
         "pano_to_raw": "d_raw = signs * d_p + eye offset — improper "
                        "(det -1) by DESIGN, the readability mirror (user "
                        "2026-07-26): mirror-y for y-down raws (A2), "
                        "mirror-x for y-up raws (frame_bootstrap vintage). "
                        "DEFINED not estimated; no scale, no registration",
         "convention": "crop_pano A2: +y up, center=+Z, theta toward +X",
         "width": PANO_W, "height": PANO_H,
         "px_per_deg_equator": round(PANO_W / 360.0, 1),
         "faces": {"res": FACE_RES, "fov": FACE_FOV}}, indent=2))

    # ---------- mechanical verification vs the SP1 direct renders ----------
    # Pano frame = mirror-y of raw, so a pano-resampled crop at (yaw θ,
    # pitch p) shows the SAME physical view as the direct rig render at raw
    # yaw θ — as its MIRROR IMAGE (that's the readability mirror working as
    # intended; Marble's crops were mirrored the same way and detected
    # fine). So: correlate crop vs np.fliplr(direct render), same yaw.
    checks = [("sp_y000_pp00", 0, 0), ("sp_y135_pp00", 135, 0),
              ("sp_y270_pm40", 270, -40), ("sp_y090_pp40", 90, 40)]
    print("[stitch] verify: pano crop vs MIRRORED direct render", flush=True)
    for tag, yaw, pitch in checks:
        ref_f = outd / f"{tag}.png"
        if not ref_f.exists():
            continue
        ry, rp = np.radians(yaw), np.radians(pitch)
        fwd = np.array([np.cos(rp) * np.sin(ry), np.sin(rp),
                        np.cos(rp) * np.cos(ry)])
        cam = r3.Cam([0, 0, 0], fwd, [0, 1, 0], 75.0, 256, 256)
        crop = sample_equirect(pano, crop_dirs(cam, 256), PANO_W, PANO_H)
        crop = crop.reshape(256, 256, 3).mean(axis=2)
        ref = np.asarray(Image.open(ref_f).convert("L").resize((256, 256)),
                         np.float32)[:, ::-1]      # mirror: see note above
        cn = (crop - crop.mean()) / (crop.std() + 1e-6)
        rn = (ref - ref.mean()) / (ref.std() + 1e-6)
        print(f"[stitch]   {tag} (mirrored): corr {float((cn * rn).mean()):+.3f}",
              flush=True)


if __name__ == "__main__":
    main()
