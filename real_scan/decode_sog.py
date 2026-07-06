"""Decode a SOG v2 bundle (splat-transform: meta.json + means_l/u, scales, quats, sh0 webp)
-> standard uncompressed 3DGS PLY. Position = 16-bit split; scale/sh0 = 256-codebook index;
opacity = sh0 alpha; quats = smallest-three (best-effort)."""
import json, numpy as np
from PIL import Image
from pathlib import Path

D = Path("data/superspl")
meta = json.load(open(D/"meta.json"))
N = meta["count"]

def img(name):
    a = np.asarray(Image.open(D/name).convert("RGBA"), dtype=np.uint8)
    return a.reshape(-1, 4)[:N]

ml, mu = img("means_l.webp"), img("means_u.webp")
sc, qt, s0 = img("scales.webp"), img("quats.webp"), img("sh0.webp")

print("channel probe:")
print("  means_u rgb max:", mu[:, :3].max(0), " (high byte; nonzero => 16-bit used)")
print("  scales idx range:", sc[:, :3].min(), sc[:, :3].max())
print("  sh0 idx range:", s0[:, :3].min(), s0[:, :3].max(), " alpha range:", s0[:, 3].min(), s0[:, 3].max())
print("  quats alpha uniq (first 8):", np.unique(qt[:, 3])[:8], " n_uniq:", len(np.unique(qt[:, 3])))

# --- positions: 16-bit (hi<<8 | lo) per axis, normalize, lerp mins..maxs ---
mins = np.array(meta["means"]["mins"]); maxs = np.array(meta["means"]["maxs"])
v16 = (mu[:, :3].astype(np.uint32) << 8) | ml[:, :3].astype(np.uint32)
pos = mins + (v16 / 65535.0) * (maxs - mins)

# --- scales: index into codebook (log-scale) ---
sc_cb = np.array(meta["scales"]["codebook"], dtype=np.float32)
scale = sc_cb[sc[:, :3]]

# --- sh0: index into codebook (f_dc) ; alpha = opacity ---
s0_cb = np.array(meta["sh0"]["codebook"], dtype=np.float32)
fdc = s0_cb[s0[:, :3]]
alpha = np.clip(s0[:, 3].astype(np.float32) / 255.0, 1e-6, 1 - 1e-6)
opacity = np.log(alpha / (1 - alpha))

# --- quats: smallest-three (best-effort; RGB=3 comps, A=largest index) ---
c = (qt[:, :3].astype(np.float32) / 255.0 - 0.5) * np.sqrt(2.0)
m = np.sqrt(np.clip(1 - (c**2).sum(1), 0, None))
idx = (qt[:, 3].astype(np.int32) % 4)
q = np.zeros((N, 4), np.float32)  # (w,x,y,z)
order = [[0,1,2,3],[1,0,2,3],[2,0,1,3],[3,0,1,2]]  # position of m, then c0,c1,c2
for k in range(4):
    sel = idx == k
    o = order[k]
    q[sel, o[0]] = m[sel]; q[sel, o[1]] = c[sel,0]; q[sel, o[2]] = c[sel,1]; q[sel, o[3]] = c[sel,2]
bad = q.sum(1) == 0; q[bad] = [1,0,0,0]

zeros = np.zeros(N, np.float32)
cols = [pos[:,0],pos[:,1],pos[:,2], zeros,zeros,zeros, fdc[:,0],fdc[:,1],fdc[:,2],
        opacity, scale[:,0],scale[:,1],scale[:,2], q[:,0],q[:,1],q[:,2],q[:,3]]
names = ["x","y","z","nx","ny","nz","f_dc_0","f_dc_1","f_dc_2","opacity",
         "scale_0","scale_1","scale_2","rot_0","rot_1","rot_2","rot_3"]
out = np.stack([np.asarray(x, np.float32) for x in cols], 1)
dst = D/"room_uncompressed.ply"
hdr = "ply\nformat binary_little_endian 1.0\nelement vertex %d\n" % N + \
      "".join("property float %s\n" % n for n in names) + "end_header\n"
open(dst,"wb").write(hdr.encode()+np.ascontiguousarray(out).tobytes())
print(f"\ndecoded {N:,} gaussians -> {dst}")
print("  bbox:", np.round(pos.min(0),2), "->", np.round(pos.max(0),2))
print("  alpha mean:", round(float(alpha.mean()),3), " frac>0.5:", round(float((alpha>0.5).mean()),3))

# --- render top-down + side to identify the scene (which axis is up? try all) ---
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
C0=0.28209479177387814; rgb=np.clip(0.5+C0*fdc,0,1)
keep=alpha>0.5; ii=np.where(keep)[0]
ii=np.random.default_rng(0).choice(ii,min(150000,ii.size),replace=False)
P,Cc=pos[ii],rgb[ii]
fig,ax=plt.subplots(1,3,figsize=(18,6))
for a,(i,j,t) in zip(ax,[(0,1,"X-Y"),(0,2,"X-Z"),(1,2,"Y-Z")]):
    a.scatter(P[:,i],P[:,j],c=Cc,s=0.5,linewidths=0); a.set_title(t); a.set_aspect("equal")
fig.suptitle("SOG decoded — homestay? (find the top-down view)")
fig.tight_layout(); fig.savefig("outputs/11_sog_decoded.png",dpi=100); print("saved outputs/11_sog_decoded.png")
