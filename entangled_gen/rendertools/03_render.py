"""
Stage 03 - CPU Gaussian-splat renderer + pixel->world bridge.

render_view(pos, look_at, fov, w, h) -> (rgb, depth, cam)
  Real alpha-blended splat render (projects each gaussian, splats an opacity-weighted
  footprint, depth-sorts back-to-front, composites). NOT a CUDA-exact 3DGS rasterizer,
  but a true blended image -- night and day vs point-scatter, and enough for VLM perception.

unproject(cam, u, v, depth) -> world xyz     # THE pixel->world bridge (geometry for "where")

Scene is used RAW (Y-up, tilted). Camera is free, so orientation is handled per-view.
"""
import numpy as np

C0 = 0.28209479177387814

# ---------- io ----------
def load_splat(path, opacity_min=0.05):
    f = open(path, "rb"); f.readline(); f.readline(); names = []; n = None
    while True:
        l = f.readline().strip()
        if l.startswith(b"element vertex"): n = int(l.split()[-1])
        elif l.startswith(b"property"): names.append(l.split()[2].decode())
        elif l == b"end_header": break
    d = np.fromfile(f, dtype="<f4", count=n*len(names)).reshape(n, len(names))
    col = {nm: i for i, nm in enumerate(names)}
    xyz = d[:, [col["x"], col["y"], col["z"]]].astype(np.float32)
    fdc = d[:, [col["f_dc_0"], col["f_dc_1"], col["f_dc_2"]]].astype(np.float32)
    rgb = np.clip(0.5 + C0*fdc, 0, 1)
    alpha = 1/(1+np.exp(-d[:, col["opacity"]]))
    scale = np.exp(d[:, [col["scale_0"], col["scale_1"], col["scale_2"]]]).astype(np.float32)
    radius = scale.mean(1)            # isotropic approx of gaussian size
    m = alpha > opacity_min
    return xyz[m], rgb[m], alpha[m].astype(np.float32), radius[m]

# ---------- camera ----------
class Cam:
    def __init__(s, pos, look_at, up, fov_deg, w, h):
        s.pos = np.asarray(pos, np.float32); s.w = w; s.h = h
        fwd = np.asarray(look_at, np.float32) - s.pos; fwd /= np.linalg.norm(fwd)
        right = np.cross(fwd, np.asarray(up, np.float32)); right /= np.linalg.norm(right)
        true_up = np.cross(right, fwd)
        s.R = np.stack([right, true_up, fwd], 0)          # world->cam rows
        s.f = (w/2) / np.tan(np.radians(fov_deg)/2)
        s.cx, s.cy = w/2, h/2
    def project(s, pts):
        cam = (pts - s.pos) @ s.R.T                       # (N,3) in camera space
        z = cam[:, 2]
        u = s.cx + s.f * cam[:, 0] / z
        v = s.cy - s.f * cam[:, 1] / z
        return u, v, z

def unproject(cam, u, v, depth):
    """pixel (u,v) + metric depth -> world xyz.  THE bridge: 2D point -> 3D location."""
    x = (u - cam.cx) / cam.f * depth
    y = -(v - cam.cy) / cam.f * depth
    z = depth
    return cam.pos + np.array([x, y, z], np.float32) @ cam.R   # cam->world

# ---------- render ----------
def render_view(xyz, rgb, alpha, radius, pos, look_at, up=(0,1,0), fov=60, w=800, h=800,
                bg=1.0):
    cam = Cam(pos, look_at, up, fov, w, h)
    u, v, z = cam.project(xyz)
    vis = (z > 0.05) & (u > -20) & (u < w+20) & (v > -20) & (v < h+20)
    u, v, z = u[vis], v[vis], z[vis]; rgb_v, a_v, rad_v = rgb[vis], alpha[vis], radius[vis]
    # projected pixel radius of each gaussian (clamped)
    pr = np.clip(cam.f * rad_v / z, 0.6, 14).astype(np.int32)
    order = np.argsort(-z)                                 # far -> near (painter's)
    color = np.full((h, w, 3), bg, np.float32)
    depth = np.full((h, w), np.inf, np.float32)
    accA  = np.zeros((h, w), np.float32)
    for i in order:
        cu, cv, r = int(round(u[i])), int(round(v[i])), int(pr[i])
        x0, x1 = max(cu-r, 0), min(cu+r+1, w); y0, y1 = max(cv-r, 0), min(cv+r+1, h)
        if x0 >= x1 or y0 >= y1: continue
        yy, xx = np.mgrid[y0:y1, x0:x1]
        d2 = ((xx-cu)**2 + (yy-cv)**2) / (r*r + 1e-6)
        wgt = np.exp(-2.5*d2) * a_v[i]                     # gaussian falloff * opacity
        wgt = wgt[..., None]
        patch = color[y0:y1, x0:x1]
        color[y0:y1, x0:x1] = patch*(1-wgt) + rgb_v[i]*wgt
        # nearest-surface depth where this splat contributes meaningfully
        msk = (wgt[..., 0] > 0.25) & (z[i] < depth[y0:y1, x0:x1])
        dd = depth[y0:y1, x0:x1]; dd[msk] = z[i]; depth[y0:y1, x0:x1] = dd
        accA[y0:y1, x0:x1] = np.maximum(accA[y0:y1, x0:x1], wgt[..., 0])
    return np.clip(color, 0, 1), depth, cam


if __name__ == "__main__":
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    from pathlib import Path
    P = "data/superspl/playroom.ply"
    xyz, rgb, alpha, radius = load_splat(P)
    c = xyz.mean(0); ext = xyz.max(0) - xyz.min(0)
    print(f"loaded {len(xyz):,} visible gaussians  center {np.round(c,2)}  extent {np.round(ext,2)}")
    # orbit camera: stand back along -Z of the scene, eye-height, look at center
    cams = {
        "front": (c + np.array([0, 0, -ext[2]*1.3]), c),
        "left":  (c + np.array([-ext[0]*1.3, 0, 0]), c),
        "high":  (c + np.array([ext[0]*0.9, ext[1]*1.1, -ext[2]*0.9]), c),
    }
    fig, ax = plt.subplots(1, 3, figsize=(20, 7))
    for a, (name, (eye, tgt)) in zip(ax, cams.items()):
        img, depth, cam = render_view(xyz, rgb, alpha, radius, eye, tgt, up=(0,1,0),
                                      fov=60, w=700, h=700)
        a.imshow(img); a.set_title(f"render_view: {name}"); a.axis("off")
    fig.suptitle("Stage 03 - CPU splat render (alpha-blended, full scene)")
    fig.tight_layout(); fig.savefig("outputs/18_render_first.png", dpi=110)
    print("saved outputs/18_render_first.png")
