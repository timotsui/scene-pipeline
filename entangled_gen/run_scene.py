"""run_scene.py — thin E2E orchestrator for the Marble object-ID pipeline.

Chains the module CLIs via subprocess; each module stays independently runnable
(the orchestrator only calls their command-line interfaces, it imports none of
their internals). This is the verified Session-A geometric core:

    bundle (out/<scene>/bundle_path.txt)
      -> crop_pano        pinhole crops from the equirect pano
      -> vocab_from_prompt detection vocab (prompt nouns + synonym expansion)
      -> seg_views         GroundingDINO + SAM over the crops
      -> seg_pano_overlay  gate artifacts (pano overlay + crop montage)
      -> lift_pano         mask rays ∩ collider -> 3D boxes -> scene_manifest_pano.json
      -> manifest_pano_to_raw  raw-frame variants (panoraw_{a,b,c}) for the viewer

Module-4 audit/enrichment (VLM inventory diff, per-object description) is NOT in
this path — that stage uses a VLM surrogate and is run separately.

  python run_scene.py --scene bedroom_marble
  python run_scene.py --scene bedroom_marble --skip crop,seg   # reuse GPU outputs
  python run_scene.py --scene bedroom_marble --box-thr 0.35

Stops on the first failing stage. Prints a per-stage summary + the viewer command.
"""
import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

import paths

HERE = Path(__file__).parent
PY = sys.executable


def run(argv, capture=False):
    """Run a module CLI in the repo dir. capture=True returns stdout text."""
    printable = " ".join(str(a) for a in argv)
    print(f"\n$ {printable}", flush=True)
    if capture:
        r = subprocess.run(argv, cwd=HERE, text=True,
                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        print(r.stdout, end="", flush=True)
        if r.returncode != 0:
            raise SystemExit(f"stage failed (rc={r.returncode}): {printable}")
        return r.stdout
    r = subprocess.run(argv, cwd=HERE)
    if r.returncode != 0:
        raise SystemExit(f"stage failed (rc={r.returncode}): {printable}")
    return ""


def stage_crop(sc):
    run([PY, "crop_pano.py", "--scene", sc])
    n = len(list(paths.pano_crops_dir(sc).glob("pano_*.webp")))
    return {"crops": n}


def stage_vocab(sc):
    """vocab_from_prompt prints '# N terms ...' then the GD prompt on the last
    line. Capture it, persist to seg_pano/vocab.txt, return the prompt string."""
    out = run([PY, "vocab_from_prompt.py", "--scene", sc], capture=True)
    lines = [ln for ln in out.splitlines() if ln.strip()]
    vocab = lines[-1].strip()
    seg = paths.seg_pano_dir(sc)
    seg.mkdir(parents=True, exist_ok=True)
    (seg / "vocab.txt").write_text(vocab + "\n", encoding="utf-8")
    n_terms = len([t for t in vocab.split(".") if t.strip()])
    return {"vocab": vocab, "terms": n_terms}


def stage_seg(sc, vocab, box_thr):
    run([PY, "seg_views.py", "--scene", sc,
         "--views-dir", str(paths.pano_crops_dir(sc)),
         "--glob", "pano_*.webp",
         "--out-dir", str(paths.seg_pano_dir(sc)),
         "--prompt", vocab,
         "--box-thr", str(box_thr)])
    dets = json.loads((paths.seg_pano_dir(sc) / "detections.json").read_text())
    return {"detections": sum(len(v) for v in dets.values()),
            "views_with_dets": sum(1 for v in dets.values() if v)}


def stage_overlay(sc):
    run([PY, "seg_pano_overlay.py", "--scene", sc])
    return {}


def stage_lift(sc):
    run([PY, "lift_pano.py", "--scene", sc])
    man = json.loads((paths.scene_dir(sc) / "scene_manifest_pano.json").read_text())
    return {"objects": len(man.get("objects", []))}


def stage_variants(sc):
    run([PY, "manifest_pano_to_raw.py", "--scene", sc])
    variants = sorted(p.name for p in paths.scene_dir(sc).glob("scene_manifest_panoraw_*.json"))
    return {"variants": variants}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--box-thr", type=float, default=0.35)
    ap.add_argument("--skip", default="",
                    help="comma-separated stages to skip: crop,vocab,seg,overlay,lift,variants")
    a = ap.parse_args()
    sc = a.scene
    skip = {s.strip() for s in a.skip.split(",") if s.strip()}

    # bundle presence is the one precondition
    bp = paths.scene_dir(sc) / "bundle_path.txt"
    if not bp.exists():
        raise SystemExit(f"missing {bp} — write the Marble bundle folder path into it")
    print(f"[run_scene] scene={sc}  bundle={bp.read_text().strip()}  box_thr={a.box_thr}"
          f"  skip={sorted(skip) or 'none'}")

    summary = {}
    vocab = None
    t0 = time.time()

    if "crop" not in skip:
        summary["crop"] = stage_crop(sc)
    if "vocab" not in skip:
        summary["vocab"] = stage_vocab(sc)
        vocab = summary["vocab"]["vocab"]
    else:
        vf = paths.seg_pano_dir(sc) / "vocab.txt"
        vocab = vf.read_text(encoding="utf-8").strip() if vf.exists() else None
    if "seg" not in skip:
        if not vocab:
            raise SystemExit("seg stage needs a vocab (run the vocab stage or provide seg_pano/vocab.txt)")
        summary["seg"] = stage_seg(sc, vocab, a.box_thr)
    if "overlay" not in skip:
        summary["overlay"] = stage_overlay(sc)
    if "lift" not in skip:
        summary["lift"] = stage_lift(sc)
    if "variants" not in skip:
        summary["variants"] = stage_variants(sc)

    dt = time.time() - t0
    print("\n" + "=" * 60)
    print(f"[run_scene] DONE  scene={sc}  {dt:.1f}s")
    if "crop" in summary:
        print(f"  crops         : {summary['crop']['crops']}")
    if "vocab" in summary:
        print(f"  vocab terms   : {summary['vocab']['terms']}")
        print(f"  vocab         : {summary['vocab']['vocab']}")
    if "seg" in summary:
        print(f"  detections    : {summary['seg']['detections']}"
              f" (in {summary['seg']['views_with_dets']} crops)")
    if "lift" in summary:
        print(f"  objects       : {summary['lift']['objects']}  -> scene_manifest_pano.json")
    if "variants" in summary:
        print(f"  raw variants  : {summary['variants']['variants']}")
    sd = paths.seg_pano_dir(sc)
    print("\n  gate artifacts (USER judges):")
    for p in [sd / "pano_overlay.png", sd / "crops_boxes.png",
              sd / "manifest_overlay_pano.png", sd / "manifest_plan_pano.png"]:
        print(f"    {'OK ' if p.exists() else '?? '}{p}")
    print(f"\n  viewer: python viewer/serve.py --scene {sc} --port 8321")
    print(f"          http://localhost:8321/?scene={sc}&man=panoraw_c")
    print("=" * 60)


if __name__ == "__main__":
    main()
