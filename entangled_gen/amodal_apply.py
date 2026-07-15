"""Promote one amodal method's boxes into the scene manifest (stage 4.5).

amodal_boxes.py only COMPARES methods; nothing downstream reads its output.
This applies a chosen method to scene_manifest.json so every consumer (the
composition chain, the viewer, agent_package) picks it up with no code change
— the PIPELINE.md file-contract rule: same file, same format, new content.

Reversible by construction: the untouched modal manifest is copied to
scene_manifest_modal.json before the first write, and `--revert` puts it back.
The manifest gains `amodal: {method, n_changed}` so a reader can always tell
which boxes it is looking at; `objects[].amodal_extended` flags the changed
ones.

  python amodal_apply.py --scene bedroom_marble --method splat
  python amodal_apply.py --scene bedroom_marble --revert

Method choice (bedroom_marble, 2026-07-15): `splat` — the only method that
MEASURES. `prior` floor-snaps by label and wrongly floors the wall shelf
obj_014; `collider` agrees with splat on 5/6 boxes but adds nothing of its own
and misses the lamp (it is a mesh derived from the splat — see PIPELINE.md).
"""
import argparse
import json
import shutil

import paths

MODAL = "scene_manifest_modal.json"


def revert(sc):
    src = paths.scene_dir(sc) / MODAL
    if not src.exists():
        print(f"[amodal-apply] no {MODAL} — nothing to revert", flush=True)
        return
    shutil.copy(src, paths.manifest(sc))
    print(f"[amodal-apply] restored modal manifest from {MODAL}", flush=True)


def apply(sc, method):
    amo_f = paths.scene_dir(sc) / "amodal_boxes.json"
    if not amo_f.exists():
        raise SystemExit("no amodal_boxes.json; run amodal_boxes.py first")
    amo = json.loads(amo_f.read_text())
    if method not in amo["methods"]:
        raise SystemExit(f"method {method!r} not in {list(amo['methods'])}")

    # snapshot the modal manifest ONCE (re-applying must not overwrite it with
    # an already-extended manifest)
    modal_f = paths.scene_dir(sc) / MODAL
    if not modal_f.exists():
        shutil.copy(paths.manifest(sc), modal_f)
        print(f"[amodal-apply] snapshot -> {MODAL}", flush=True)
    man = json.loads(modal_f.read_text())      # always extend from MODAL

    boxes = {b["id"]: b for b in amo["methods"][method]}
    n = 0
    for o in man["objects"]:
        b = boxes.get(o["id"])
        if not b or not b.get("changed"):
            o["amodal_extended"] = False
            continue
        o["aabb_min"], o["aabb_max"] = b["aabb_min"], b["aabb_max"]
        o["center"] = [round((lo + hi) / 2, 3)
                       for lo, hi in zip(b["aabb_min"], b["aabb_max"])]
        o["size"] = [round(hi - lo, 3)
                     for lo, hi in zip(b["aabb_min"], b["aabb_max"])]
        o["amodal_extended"] = True
        n += 1
    man["amodal"] = {"method": method, "n_changed": n,
                     "source": "amodal_boxes.json"}
    paths.manifest(sc).write_text(json.dumps(man, indent=1))
    print(f"[amodal-apply] method={method}: {n}/{len(man['objects'])} boxes "
          f"extended -> {paths.manifest(sc).name}", flush=True)
    for o in man["objects"]:
        if o.get("amodal_extended"):
            print(f"    {o['id']} {o['label']:16s} size {o['size']}", flush=True)
    print("\n[amodal-apply] downstream is now STALE — re-run the composition "
          "chain (retrieve2 -> measure -> retrieve2 -> thumbs -> relevance -> "
          "pick -> place2): box sizes drive fit scores and picks.", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--method", default="splat",
                    choices=["splat", "collider", "prior"])
    ap.add_argument("--revert", action="store_true")
    a = ap.parse_args()
    revert(a.scene) if a.revert else apply(a.scene, a.method)
