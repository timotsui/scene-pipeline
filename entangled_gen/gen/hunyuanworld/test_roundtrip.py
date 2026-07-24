"""Round-trip check: mesh_to_splat.write_gs_ply -> rendertools load_splat.

Verifies the DRAFT adapter's ply output is readable by the lift pipeline's
reader and preserves xyz/rgb/radius. CPU-only, ~seconds.
"""
import importlib.util
import os
import sys
import tempfile

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(os.path.dirname(HERE)))  # entangled_gen/
import paths  # noqa: E402


def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def main():
    m2s = load_module("m2s", os.path.join(HERE, "mesh_to_splat.py"))
    r03 = paths.load_r3()

    rng = np.random.default_rng(0)
    n = 5000
    xyz = rng.uniform(-3, 3, (n, 3)).astype(np.float32)
    rgb = rng.uniform(0.05, 0.95, (n, 3)).astype(np.float32)
    rad = rng.uniform(0.01, 0.05, n).astype(np.float32)

    with tempfile.TemporaryDirectory() as td:
        p = os.path.join(td, "rt.ply")
        m2s.write_gs_ply(p, xyz, rgb, rad, opacity=0.95)
        lx, lrgb, lalpha, lrad = r03.load_splat(p)

    assert lx.shape == (n, 3), f"xyz shape {lx.shape}"
    assert np.allclose(lx, xyz, atol=1e-5), "xyz mismatch"
    assert np.allclose(lrgb, rgb, atol=2e-3), f"rgb mismatch max={np.abs(lrgb-rgb).max()}"
    assert np.allclose(lalpha, 0.95, atol=1e-3), f"alpha {lalpha[:3]}"
    assert np.allclose(lrad, rad, atol=1e-5), "radius mismatch"
    print(f"ROUNDTRIP OK: {n} pts, rgb err {np.abs(lrgb-rgb).max():.2e}, "
          f"alpha {lalpha[0]:.3f}, radius err {np.abs(lrad-rad).max():.2e}")


if __name__ == "__main__":
    main()
