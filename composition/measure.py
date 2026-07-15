"""Measure TRUE mesh extents for shortlisted/picked assets.

The thor_metadata bbox lies for a fat minority of assets (open window
shutters: annotation z=14cm, mesh z=54cm — found 2026-07-14 when placements
blew out of their boxes). This walks a scene's shortlists2 uids, loads each
pkl mesh once, and records the real y-up extents (cm) in a dataset-level
cache; retrieve.catalog() overrides size_yup_cm from it, so fit/FITS/scale
are scored on geometry that placement will actually realize.

Run: python measure.py --scene <sc>   (only cache misses are loaded)
Chain note: run BEFORE retrieve2 for full effect; newly-shortlisted uids are
unmeasured until the next pass (annotation is the recall filter, the cache
the precision upgrade).
"""
import json

from assets_thor import load_asset
from comp_paths import paths
from thumbs import THUMBS

SIZES = THUMBS / "_mesh_sizes.json"


def load_cache():
    return json.loads(SIZES.read_text()) if SIZES.exists() else {}


def ensure(uids):
    THUMBS.mkdir(exist_ok=True)
    cache = load_cache()
    todo = [u for u in dict.fromkeys(uids) if u not in cache]
    fail = 0
    for i, uid in enumerate(todo):
        try:
            m = load_asset(uid)
            lo, hi = m.bounds
            cache[uid] = [round(float(v) * 100, 1) for v in (hi - lo)]
        except Exception as e:
            fail += 1
            print(f"[measure] FAIL {uid}: {e}", flush=True)
        if (i + 1) % 50 == 0:
            print(f"[measure] {i + 1}/{len(todo)}", flush=True)
    if todo:
        SIZES.write_text(json.dumps(cache))
    print(f"[measure] measured {len(todo) - fail}, failed {fail}, "
          f"total cached {len(cache)}", flush=True)
    return cache


def scene_uids(sc):
    pkg = paths.package_dir(sc)
    sl = json.loads((pkg / "shortlists2.json").read_text())
    return [c["uid"] for b in sl["boxes"] for c in b["candidates"]]


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    args = ap.parse_args()
    ensure(scene_uids(args.scene))
