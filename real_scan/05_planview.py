"""
Orthographic top-down PLAN view of a splat (numpy). Reliable: full coverage, correct
framing, no perspective occlusion -- unlike a perspective camera placed by guesswork.

Recipe: project onto floor plane (XZ, Y-up), keep BELOW-CEILING gaussians (drops the
offset ceiling that blocks a top-down render), paint the TOPMOST gaussian per grid cell.
"""
import numpy as np, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from scipy.ndimage import grey_dilation
from pathlib import Path

def plan_view(ply, out, R=560, alpha_min=0.4, ceiling=-0.1, floor=-3.2,
              up_axis=1, brighten=1.25, gamma=0.8):
    f = open(ply, "rb"); f.readline(); f.readline(); names = []; n = None
    while True:
        l = f.readline().strip()
        if l.startswith(b"element vertex"): n = int(l.split()[-1])
        elif l.startswith(b"property"): names.append(l.split()[2].decode())
        elif l == b"end_header": break
    d = np.fromfile(f, dtype="<f4", count=n*len(names)).reshape(n, len(names))
    c = lambda k: d[:, names.index(k)]
    xyz = np.stack([c("x"), c("y"), c("z")], 1)
    al = 1/(1+np.exp(-c("opacity")))
    C0 = 0.28209479177387814
    rgb = np.clip(0.5 + C0*np.stack([c("f_dc_0"), c("f_dc_1"), c("f_dc_2")], 1), 0, 1)
    u = up_axis; ax2 = [a for a in (0,1,2) if a != u]   # the two floor axes
    m = (al > alpha_min) & (xyz[:, u] < ceiling) & (xyz[:, u] > floor)
    A, B, H, Cc = xyz[m, ax2[0]], xyz[m, ax2[1]], xyz[m, u], rgb[m]
    a0, a1 = np.percentile(A, [1, 99]); b0, b1 = np.percentile(B, [1, 99])
    ga = np.clip(((A-a0)/(a1-a0)*(R-1)).astype(int), 0, R-1)
    gb = np.clip(((B-b0)/(b1-b0)*(R-1)).astype(int), 0, R-1)
    order = np.argsort(H)                                # topmost (max up) wins
    img = np.zeros((R*R, 3)); img[gb[order]*R + ga[order]] = Cc[order]
    img = img.reshape(R, R, 3)
    mask = img.sum(2) == 0
    for ch in range(3):
        img[:, :, ch] = np.where(mask, grey_dilation(img[:, :, ch], size=3), img[:, :, ch])
    img = np.clip(img**gamma * brighten, 0, 1)
    fig, axx = plt.subplots(figsize=(9, 9))
    axx.imshow(img, origin="lower"); axx.axis("off")
    axx.set_title(f"PLAN view — {Path(ply).stem}")
    fig.tight_layout(); fig.savefig(out, dpi=120)
    print("saved", out, " gaussians:", int(m.sum()))
    return (a0, a1, b0, b1)   # world extent of the plan, for pixel<->world later

if __name__ == "__main__":
    plan_view("data/superspl/playroom.ply", "outputs/26_plan_clean.png")
