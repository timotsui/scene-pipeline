"""Merge every anchor's BEST sub-round GLB into one viewer layer.

Per anchor in sub_experiment/: cp7/subs_walked.glb (host-aware pass)
> cp6/subs_jiggled.glb > cp5_final/subs_preview.glb — first that
exists wins; idle anchors contribute nothing. All three are RAW-frame
(fitted_preview.glb convention), so the merge is a straight re-add,
node names preserved (<subId>_t<i>).

Writes compose/subs_preview.glb — served by viewer route
/subs_preview.glb, toggled by the "subs" layer checkbox.

  python build_subs_preview.py [--scene bedroom_marble]
"""
import argparse
import sys
from pathlib import Path

import trimesh

HERE = Path(__file__).parent
EG = HERE.parent
sys.path.insert(0, str(EG))
import paths  # noqa: E402

BEST = ("cp7/subs_walked.glb", "cp6/subs_jiggled.glb",
        "cp5_final/subs_preview.glb")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="bedroom_marble")
    a = ap.parse_args()

    root = paths.compose_dir(a.scene) / "sub_experiment"
    out_sc = trimesh.Scene()
    n_anchor = n_node = 0
    for adir in sorted(root.iterdir()):
        if not adir.is_dir():
            continue
        src = next((adir / rel for rel in BEST
                    if (adir / rel).exists()), None)
        if src is None:
            continue
        gsc = trimesh.load(src, force="scene")
        for node in gsc.graph.nodes_geometry:
            T, gname = gsc.graph[node]
            m = gsc.geometry[gname].copy()
            if T is not None:
                m.apply_transform(T)
            out_sc.add_geometry(m, node_name=f"{node}")
            n_node += 1
        n_anchor += 1
        print(f"  {adir.name}: {src.relative_to(adir)}")
    if not n_node:
        print("[subs_preview] nothing to merge")
        return
    out = paths.compose_dir(a.scene) / "subs_preview.glb"
    out.write_bytes(out_sc.export(file_type="glb"))
    print(f"[subs_preview] {n_anchor} anchors, {n_node} nodes -> {out}")


if __name__ == "__main__":
    main()
