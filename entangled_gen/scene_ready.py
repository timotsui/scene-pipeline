"""
Idempotent per-scene readiness: make sure a generated scene has everything the
tooling needs, running only the missing (CPU-safe) steps:

  manifest (lift)  ->  package  ->  viewer points (prep_scene)  ->  envelope

GPU steps (view rendering, segmentation) are NOT run here — if views/seg are
missing this reports and skips. Re-runs lift when the manifest predates the
extent_p1 field (envelope needs it).

python scene_ready.py --scene bedroomdim
python scene_ready.py --all          # every out/<scene>/gen_raw.ply
"""
import argparse, json, subprocess, sys
from pathlib import Path

import paths

HERE = Path(__file__).parent
PY = sys.executable


def sh(args):
    print("  $", " ".join(str(a) for a in args), flush=True)
    r = subprocess.run([PY] + [str(a) for a in args], cwd=HERE)
    return r.returncode == 0


def ready(sc):
    print(f"[ready] {sc}", flush=True)
    views = paths.views_dir(sc)
    seg = paths.seg_dir(sc)
    manifest = paths.manifest(sc)
    ok = True

    if not (seg / "detections.json").exists() or not any(views.glob("gpu_yaw*.json")):
        print(f"  !! views/seg missing (GPU steps) — run post-queue chain first; "
              f"skipping lift for {sc}", flush=True)
        seg_ok = False
    else:
        seg_ok = True
        need_lift = not manifest.exists()
        if manifest.exists():
            fr = json.loads(manifest.read_text()).get("frame", {})
            if "extent_p1" not in fr:
                print("  manifest predates extent field -> re-lifting", flush=True)
                need_lift = True
        if need_lift:
            ok &= sh(["lift_views.py", "--scene", sc])

    if manifest.exists():
        pkg = paths.package_dir(sc) / "GUIDE.md"
        if not pkg.exists() or pkg.stat().st_mtime < manifest.stat().st_mtime:
            ok &= sh(["agent_package.py", "--scene", sc])

    ply = paths.ply(sc)
    vbin = HERE / "viewer" / "data" / f"{sc}.bin"
    if ply.exists() and (not vbin.exists() or vbin.stat().st_mtime < ply.stat().st_mtime):
        ok &= sh(["viewer/prep_scene.py", "--scene", sc])

    env = paths.envelope_npz(sc)
    if manifest.exists() and (not env.exists()
                              or env.stat().st_mtime < manifest.stat().st_mtime):
        ok &= sh(["envelope.py", "--scene", sc])

    print(f"[ready] {sc}: {'OK' if ok else 'INCOMPLETE'}"
          + ("" if seg_ok else " (needs GPU seg/views)"), flush=True)
    return ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="")
    ap.add_argument("--all", action="store_true")
    args = ap.parse_args()
    if args.all:
        scenes = paths.gen_scenes()
        print(f"[ready] scenes: {scenes}", flush=True)
        for sc in scenes:
            ready(sc)
    elif args.scene:
        ready(args.scene)
    else:
        ap.error("--scene or --all")


if __name__ == "__main__":
    main()
