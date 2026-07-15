"""Purge + refill every cache that baked in a uid's old geometry — run after
adding a _mesh_fixups.json entry or dropping a hand-edited override at
<OBJATHOR>/_fixups/<uid>.glb (Blender cleanup; export .glb, canonical frame,
no _TOEDIT suffix). Purges: measured size, robust-census entry, thumbnails,
viewer GLB, CLIP image embeddings. Then re-measures the size and re-censuses
so the viewer is immediately truthful; thumbs re-render on the next
`thumbs.py --scene` (or lazily stay missing until then).

Run: python fixup.py <uid> [<uid> ...]
Chain note: sizes changed here only reach fit/picks/placement on the next
chain re-run (retrieve2 -> ... -> place2).
"""
import json
import sys

import numpy as np

from assets_thor import load_asset
from comp_paths import OBJATHOR
from measure import ROBUST, SIZES, census
from relevance import CACHE
from thumbs import THUMBS


def purge(uid):
    m = load_asset(uid)
    lo, hi = m.bounds

    sizes = json.loads(SIZES.read_text()) if SIZES.exists() else {}
    old = sizes.get(uid)
    sizes[uid] = [round(float(v) * 100, 1) for v in (hi - lo)]
    SIZES.write_text(json.dumps(sizes))
    print(f"[fixup] {uid} size {old} -> {sizes[uid]}", flush=True)

    if ROBUST.exists():
        rob = json.loads(ROBUST.read_text())
        if rob.pop(uid, None) is not None:
            ROBUST.write_text(json.dumps(rob))

    n = 0
    for f in THUMBS.glob(f"{uid}*.png"):
        f.unlink()
        n += 1
    g = 0
    for f in (OBJATHOR / "_glb").glob(f"{uid}.glb"):
        f.unlink()
        g += 1
    e = 0
    if CACHE.exists():
        with np.load(CACHE) as f:
            cache = {k: f[k] for k in f.files}
        keep = {k: v for k, v in cache.items()
                if k.startswith("txt_") or not k.startswith(uid)}
        e = len(cache) - len(keep)
        if e:
            np.savez(CACHE, **keep)
    print(f"[fixup] purged {n} thumbs, {g} glb, {e} clip embeddings", flush=True)


if __name__ == "__main__":
    uids = sys.argv[1:]
    if not uids:
        sys.exit("usage: python fixup.py <uid> [<uid> ...]")
    for uid in uids:
        purge(uid)
    census(uids)
