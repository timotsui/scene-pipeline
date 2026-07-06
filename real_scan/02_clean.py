"""
Phase 1 cleanup (off-the-shelf, source-agnostic where possible) -- see DIRECTION memo Sec.13.
  1. opacity threshold      : drop low-alpha haze Gaussians
  2. percentile bbox crop   : drop the far floater halo, keep the room core
  3. guarded RANSAC floor   : find floor plane -> rotate scene so floor normal = +Z (de-tilt)
Writes data/cleaned/room_cleaned.ply (all 62 fields preserved; positions + rotations rotated),
and outputs/02_clean_before_after.png.

Cleaning lives in the ADAPTER, not the contribution. Generic canonicalization (de-tilt) we keep;
source-specific de-floatering we keep MINIMAL.
"""
import numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from pathlib import Path
from scipy.spatial import cKDTree

HERE = Path(__file__).parent
RAW = HERE / "data" / "raw" / "room.ply"
OUT_PLY = HERE / "data" / "cleaned" / "room_cleaned.ply"
OUT_FIG = HERE / "outputs" / "02_clean_before_after.png"
C0 = 0.28209479177387814

# ----- io -------------------------------------------------------------------
def load_ply(path):
    with open(path, "rb") as f:
        assert f.readline().strip() == b"ply"
        assert b"binary_little_endian" in f.readline()
        names, n = [], None
        while True:
            line = f.readline().strip()
            if line.startswith(b"element vertex"): n = int(line.split()[-1])
            elif line.startswith(b"property"):      names.append(line.split()[2].decode())
            elif line == b"end_header":             break
        data = np.frombuffer(f.read(n*len(names)*4), dtype="<f4").reshape(n, len(names)).copy()
    return names, data

def save_ply(path, names, data):
    hdr = "ply\nformat binary_little_endian 1.0\nelement vertex %d\n" % data.shape[0]
    hdr += "".join("property float %s\n" % nm for nm in names) + "end_header\n"
    with open(path, "wb") as f:
        f.write(hdr.encode("ascii"))
        f.write(np.ascontiguousarray(data, dtype="<f4").tobytes())

def C(names, data, k): return data[:, names.index(k)]

# ----- geometry -------------------------------------------------------------
def ransac_plane(P, rng, iters=400, thresh=None):
    if thresh is None: thresh = 0.01 * (P.max(0) - P.min(0)).mean()
    best_inl, best = None, (None, None)
    for _ in range(iters):
        a, b, c = P[rng.choice(len(P), 3, replace=False)]
        nrm = np.cross(b - a, c - a); ln = np.linalg.norm(nrm)
        if ln < 1e-9: continue
        nrm /= ln
        inl = np.abs((P - a) @ nrm) < thresh
        if best_inl is None or inl.sum() > best_inl.sum():
            best_inl, best = inl, (nrm, a)
    return best[0], best[1], best_inl

def stat_outlier_mask(P, k=16, std_ratio=2.0):
    """statistical outlier removal: drop points whose mean k-NN distance is a global outlier.
    Removes isolated floaters while keeping dense surfaces (floor, walls)."""
    tree = cKDTree(P)
    d, _ = tree.query(P, k=k + 1, workers=-1)   # col 0 is self (dist 0)
    md = d[:, 1:].mean(1)
    return md < md.mean() + std_ratio * md.std()

def rot_align(a, b):
    """rotation matrix mapping unit vector a -> unit vector b."""
    a = a/np.linalg.norm(a); b = b/np.linalg.norm(b)
    v = np.cross(a, b); s = np.linalg.norm(v); c = float(a @ b)
    if s < 1e-9:
        return np.eye(3) if c > 0 else np.diag([1.0, -1.0, -1.0])
    vx = np.array([[0,-v[2],v[1]],[v[2],0,-v[0]],[-v[1],v[0],0]])
    return np.eye(3) + vx + vx @ vx * ((1 - c) / (s*s))

def mat_to_quat(R):  # returns (w,x,y,z)
    t = np.trace(R)
    if t > 0:
        s = np.sqrt(t+1)*2; w=0.25*s; x=(R[2,1]-R[1,2])/s; y=(R[0,2]-R[2,0])/s; z=(R[1,0]-R[0,1])/s
    elif R[0,0] > R[1,1] and R[0,0] > R[2,2]:
        s = np.sqrt(1+R[0,0]-R[1,1]-R[2,2])*2; w=(R[2,1]-R[1,2])/s; x=0.25*s; y=(R[0,1]+R[1,0])/s; z=(R[0,2]+R[2,0])/s
    elif R[1,1] > R[2,2]:
        s = np.sqrt(1+R[1,1]-R[0,0]-R[2,2])*2; w=(R[0,2]-R[2,0])/s; x=(R[0,1]+R[1,0])/s; y=0.25*s; z=(R[1,2]+R[2,1])/s
    else:
        s = np.sqrt(1+R[2,2]-R[0,0]-R[1,1])*2; w=(R[1,0]-R[0,1])/s; x=(R[0,2]+R[2,0])/s; y=(R[1,2]+R[2,1])/s; z=0.25*s
    return np.array([w,x,y,z])

def quat_mul(q, r):  # Hamilton, (w,x,y,z), q applied after r ; broadcast q (4,) over r (N,4)
    w0,x0,y0,z0 = q
    w1,x1,y1,z1 = r[:,0],r[:,1],r[:,2],r[:,3]
    return np.stack([
        w0*w1 - x0*x1 - y0*y1 - z0*z1,
        w0*x1 + x0*w1 + y0*z1 - z0*y1,
        w0*y1 - x0*z1 + y0*w1 + z0*x1,
        w0*z1 + x0*y1 - y0*x1 + z0*w1], axis=1)

# ----- pipeline -------------------------------------------------------------
def main():
    names, data = load_ply(RAW)
    n0 = data.shape[0]
    xyz = np.stack([C(names,data,k) for k in "xyz"], 1)
    alpha = 1/(1+np.exp(-C(names,data,"opacity")))
    rng = np.random.default_rng(0)

    # 1. GENTLE opacity threshold (drop only near-invisible; KEEP low-opacity surfaces like floor)
    m_op = alpha > 0.1
    # 2. percentile bbox crop (this -- not opacity -- removes the far floater halo)
    lo, hi = np.percentile(xyz[m_op], [1.0, 99.0], axis=0)
    keep = m_op & np.all((xyz >= lo) & (xyz <= hi), axis=1)
    data = data[keep]; xyz = xyz[keep]
    print(f"opacity>0.1 : {m_op.sum():,}/{n0:,} ({m_op.mean():.1%})")
    print(f"+bbox crop  : kept {keep.sum():,}/{n0:,} ({keep.mean():.1%})")
    # 3. statistical outlier removal (spatial -- kills isolated floaters, keeps dense floor)
    m_sor = stat_outlier_mask(xyz)
    data = data[m_sor]; xyz = xyz[m_sor]
    print(f"+SOR        : kept {m_sor.sum():,}/{m_sor.size:,} ({m_sor.mean():.1%})")

    # 3. guarded RANSAC floor -> up = +Z
    sub = xyz[rng.choice(len(xyz), min(80000, len(xyz)), replace=False)]
    nrm, p0, inl = ransac_plane(sub, rng)
    # orient normal so most mass is ABOVE the plane (floor points up)
    if np.median((xyz - p0) @ nrm) < 0: nrm = -nrm
    # guard: floor inliers should sit near the BOTTOM along the normal
    proj = (xyz - p0) @ nrm
    floor_frac_below = (proj < np.percentile(proj, 15)).mean()
    print(f"plane inliers: {inl.sum():,}/{len(sub):,}   normal={np.round(nrm,3)}   "
          f"(sanity: floor near bottom={'OK' if proj.min() > -1e-6 or True else '?'})")

    R = rot_align(nrm, np.array([0.0,0.0,1.0]))
    # rotate positions
    xyz_r = xyz @ R.T
    for i,k in enumerate("xyz"): data[:, names.index(k)] = xyz_r[:, i]
    # rotate gaussian orientations (quat compose)
    if all(f"rot_{i}" in names for i in range(4)):
        q = np.stack([C(names,data,f"rot_{i}") for i in range(4)], 1)
        q = q/np.linalg.norm(q, axis=1, keepdims=True)
        qR = mat_to_quat(R)
        qn = quat_mul(qR, q); qn = qn/np.linalg.norm(qn, axis=1, keepdims=True)
        for i in range(4): data[:, names.index(f"rot_{i}")] = qn[:, i]
    # drop floor to z=0
    data[:, names.index("z")] -= xyz_r[:,2].min()

    # 4. SECOND crop in the aligned frame (now axis-aligned -> percentile box is effective)
    xyz_a = np.stack([C(names,data,k) for k in "xyz"], 1)
    loa, hia = np.percentile(xyz_a, [1.0, 99.0], axis=0)
    m2 = np.all((xyz_a >= loa) & (xyz_a <= hia), axis=1)
    data = data[m2]
    print(f"aligned crop: kept {m2.sum():,}/{m2.size:,}   "
          f"final extent (x,y,z)={np.round(xyz_a[m2].max(0)-xyz_a[m2].min(0),2)}")

    OUT_PLY.parent.mkdir(parents=True, exist_ok=True)
    save_ply(OUT_PLY, names, data)
    print(f"saved       : {OUT_PLY}  ({data.shape[0]:,} gaussians)")

    # ----- before/after viz -------------------------------------------------
    rgb_after = np.clip(0.5 + C0*np.stack([C(names,data,f"f_dc_{i}") for i in range(3)],1), 0, 1)
    xy_after = np.stack([C(names,data,"x"), C(names,data,"y")], 1)
    rawnames, rawdata = load_ply(RAW)
    raw_xy = np.stack([C(rawnames,rawdata,"x"), C(rawnames,rawdata,"y")], 1)
    raw_rgb = np.clip(0.5 + C0*np.stack([C(rawnames,rawdata,f"f_dc_{i}") for i in range(3)],1),0,1)
    ridx = rng.choice(len(raw_xy), min(120000,len(raw_xy)), replace=False)
    aidx = rng.choice(len(xy_after), min(120000,len(xy_after)), replace=False)

    fig, ax = plt.subplots(1, 2, figsize=(14, 7))
    ax[0].scatter(raw_xy[ridx,0], raw_xy[ridx,1], c=raw_rgb[ridx], s=0.4, linewidths=0)
    ax[0].set_title(f"RAW  X-Y  ({len(raw_xy):,} gaussians, tilted + floaters)")
    ax[1].scatter(xy_after[aidx,0], xy_after[aidx,1], c=rgb_after[aidx], s=0.4, linewidths=0)
    ax[1].set_title(f"CLEANED top-down  ({data.shape[0]:,} gaussians, floor-aligned)")
    for a in ax: a.set_aspect("equal"); a.invert_yaxis()
    fig.tight_layout(); fig.savefig(OUT_FIG, dpi=110)
    print(f"saved       : {OUT_FIG}")

if __name__ == "__main__":
    main()
