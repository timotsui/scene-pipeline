"""Load an objathor THOR-format asset (.pkl.gz + albedo.jpg) as a textured
trimesh, canonical y-up. Swap point: replace with a GLB loader for other
catalogs."""
import gzip
import pickle

import numpy as np
import trimesh
from PIL import Image

from comp_paths import ASSETS


def _vec3(rows):
    if rows and isinstance(rows[0], dict):
        return np.array([[r["x"], r["y"], r["z"]] for r in rows], np.float32)
    return np.asarray(rows, np.float32).reshape(-1, 3)


def _vec2(rows):
    if rows and isinstance(rows[0], dict):
        return np.array([[r["x"], r["y"]] for r in rows], np.float32)
    return np.asarray(rows, np.float32).reshape(-1, 2)


def load_asset(uid):
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
    return mesh
