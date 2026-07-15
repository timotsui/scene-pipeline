"""Load an objathor THOR-format asset (.pkl.gz + albedo.jpg) as a textured
trimesh, canonical y-up. Applies the measure.py canonical-yaw fix (many
meshes are authored 45-deg rotated in their own frame) and any curated
per-uid fixup from _mesh_fixups.json (user-gated geometry cleanup, e.g.
pruning junk components that stick out of the body — the obj_013
triangle-shelf case); raw=True skips both (measure itself, and before/after
comparison). Swap point: replace with a GLB loader for other catalogs."""
import gzip
import json
import pickle

import numpy as np
import trimesh
from PIL import Image

from comp_paths import ASSETS, MESH_FIXUPS, MESH_YAW

_YAWS = None
_FIXUPS = None


def _yaw(uid):
    global _YAWS
    if _YAWS is None:
        _YAWS = json.loads(MESH_YAW.read_text()) if MESH_YAW.exists() else {}
    return _YAWS.get(uid, 0.0)


def _fixup(uid):
    global _FIXUPS
    if _FIXUPS is None:
        _FIXUPS = (json.loads(MESH_FIXUPS.read_text())
                   if MESH_FIXUPS.exists() else {})
    return _FIXUPS.get(uid)


def prune_protruding(mesh, tol=0.03, max_share=0.15):
    """Drop connected components that stick out past the body's density-edge
    (robust) bounds by more than tol meters. Guard: a component carrying
    more than max_share of the surface area is never dropped (that would be
    real geometry, not junk) — it is reported instead. Only ever runs on
    uids a user put in _mesh_fixups.json after eyeballing them."""
    from measure import robust_extents          # lazy: measure imports us
    lo, hi = robust_extents(mesh)
    labels = trimesh.graph.connected_component_labels(
        mesh.face_adjacency, node_count=len(mesh.faces))
    tri = mesh.vertices[mesh.faces]                       # (F, 3, 3)
    n = int(labels.max()) + 1
    cmin = np.full((n, 3), np.inf)
    cmax = np.full((n, 3), -np.inf)
    for ax in range(3):
        np.minimum.at(cmin[:, ax], labels, tri[:, :, ax].min(1))
        np.maximum.at(cmax[:, ax], labels, tri[:, :, ax].max(1))
    protrude = ((cmin < lo - tol) | (cmax > hi + tol)).any(1)
    share = np.bincount(labels, weights=mesh.area_faces, minlength=n)
    share /= max(share.sum(), 1e-12)
    blocked = protrude & (share > max_share)
    if blocked.any():
        print(f"[fixup] guard: {int(blocked.sum())} protruding component(s) "
              f"carry >{max_share:.0%} area each — NOT dropped", flush=True)
    drop = protrude & (share <= max_share)
    if drop.any():
        mesh.update_faces(~drop[labels])
        mesh.remove_unreferenced_vertices()
    return mesh


def _vec3(rows):
    if rows and isinstance(rows[0], dict):
        return np.array([[r["x"], r["y"], r["z"]] for r in rows], np.float32)
    return np.asarray(rows, np.float32).reshape(-1, 3)


def _vec2(rows):
    if rows and isinstance(rows[0], dict):
        return np.array([[r["x"], r["y"]] for r in rows], np.float32)
    return np.asarray(rows, np.float32).reshape(-1, 2)


def load_asset(uid, raw=False):
    # hand-edited override (Blender cleanup): <OBJATHOR>/_fixups/<uid>.glb,
    # already in the canonical yaw-fixed frame — replaces the pkl AND all
    # automatic fixes. raw=True still shows the original for comparison.
    if not raw:
        override = ASSETS.parent / "_fixups" / f"{uid}.glb"
        if override.exists():
            m = trimesh.load(override, force="mesh")
            return m
    d = ASSETS / uid
    obj = pickle.load(gzip.open(d / f"{uid}.pkl.gz"))
    v = _vec3(obj["vertices"])
    f = np.asarray(obj["triangles"], np.int64).reshape(-1, 3)
    uv = _vec2(obj["uvs"]) if obj.get("uvs") else None
    mesh = trimesh.Trimesh(vertices=v, faces=f, process=False)
    tex = d / "albedo.jpg"
    if uv is not None and tex.exists():
        img = Image.open(tex).convert("RGB")
        mesh.visual = trimesh.visual.TextureVisuals(
            uv=uv, material=trimesh.visual.material.SimpleMaterial(image=img))
    if not raw:
        yaw = _yaw(uid)
        if yaw:
            mesh.apply_transform(trimesh.transformations.rotation_matrix(
                np.deg2rad(yaw), [0, 1, 0]))
        fx = _fixup(uid)
        if fx and "prune_protruding" in fx:
            p = fx["prune_protruding"] or {}
            mesh = prune_protruding(mesh, tol=p.get("tol_cm", 3) / 100.0)
    return mesh
