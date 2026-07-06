"""Decode a tiled-LOD SOG zip (SuperSplat export) -> standard 3DGS PLY.
Uses only the finest LOD level (the '0_*' tiles, which spatially partition the scene),
concatenating them. Ignores coarser redundant levels. Reads webps directly from the zip."""
import sys, io, json, zipfile, numpy as np
from PIL import Image
from pathlib import Path

ZIP = Path(sys.argv[1]) if len(sys.argv) > 1 else Path("data/superspl/Playroom.zip")
OUTDIR = ZIP.parent / ZIP.stem.split(" (")[0].replace(" ", "_")
OUTDIR.mkdir(exist_ok=True)
zf = zipfile.ZipFile(ZIP)

def decode_tile(tile):
    meta = json.loads(zf.read(f"{tile}/meta.json")); N = meta["count"]
    def im(name):
        return np.asarray(Image.open(io.BytesIO(zf.read(f"{tile}/{name}"))).convert("RGBA"),
                          np.uint8).reshape(-1, 4)[:N]
    ml, mu, sc, qt, s0 = (im("means_l.webp"), im("means_u.webp"),
                          im("scales.webp"), im("quats.webp"), im("sh0.webp"))
    mins = np.array(meta["means"]["mins"]); maxs = np.array(meta["means"]["maxs"])
    v16 = (mu[:, :3].astype(np.uint32) << 8) | ml[:, :3].astype(np.uint32)
    pos = mins + (v16 / 65535.0) * (maxs - mins)
    scale = np.array(meta["scales"]["codebook"], np.float32)[sc[:, :3]]
    fdc = np.array(meta["sh0"]["codebook"], np.float32)[s0[:, :3]]
    alpha = np.clip(s0[:, 3].astype(np.float32) / 255, 1e-6, 1 - 1e-6)
    opacity = np.log(alpha / (1 - alpha))
    c = (qt[:, :3].astype(np.float32) / 255 - 0.5) * np.sqrt(2.0)
    m = np.sqrt(np.clip(1 - (c**2).sum(1), 0, None)); idx = qt[:, 3].astype(np.int32) % 4
    q = np.zeros((N, 4), np.float32)
    order = [[0,1,2,3],[1,0,2,3],[2,0,1,3],[3,0,1,2]]
    for k in range(4):
        s = idx == k; o = order[k]
        q[s,o[0]]=m[s]; q[s,o[1]]=c[s,0]; q[s,o[2]]=c[s,1]; q[s,o[3]]=c[s,2]
    zeros = np.zeros(N, np.float32)
    return np.stack([pos[:,0],pos[:,1],pos[:,2],zeros,zeros,zeros,fdc[:,0],fdc[:,1],fdc[:,2],
                     opacity,scale[:,0],scale[:,1],scale[:,2],q[:,0],q[:,1],q[:,2],q[:,3]],1).astype(np.float32)

tiles = sorted({n.split("/")[0] for n in zf.namelist() if n.startswith("0_") and n.endswith("meta.json")})
print("finest-LOD tiles:", tiles)
parts = [decode_tile(t) for t in tiles]
out = np.concatenate(parts, 0); N = out.shape[0]
names = ["x","y","z","nx","ny","nz","f_dc_0","f_dc_1","f_dc_2","opacity",
         "scale_0","scale_1","scale_2","rot_0","rot_1","rot_2","rot_3"]
dst = OUTDIR / "room_uncompressed.ply"
hdr = "ply\nformat binary_little_endian 1.0\nelement vertex %d\n" % N + \
      "".join("property float %s\n" % n for n in names) + "end_header\n"
open(dst,"wb").write(hdr.encode()+np.ascontiguousarray(out).tobytes())
print(f"decoded {N:,} gaussians -> {dst}")

# render 3 projections to find the top-down axis
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
col=lambda k: out[:,names.index(k)]
xyz=np.stack([col("x"),col("y"),col("z")],1); al=1/(1+np.exp(-col("opacity")))
C0=0.28209479177387814; rgb=np.clip(0.5+C0*np.stack([col("f_dc_0"),col("f_dc_1"),col("f_dc_2")],1),0,1)
m=al>0.6; ii=np.where(m)[0]; ii=np.random.default_rng(0).choice(ii,min(600000,ii.size),replace=False)
print("bbox:", np.round(xyz.min(0),2),"->",np.round(xyz.max(0),2)," opaque frac:",round(float((al>0.5).mean()),3))
fig,ax=plt.subplots(1,3,figsize=(18,6))
for a,(i,j,t) in zip(ax,[(0,1,"X-Y"),(0,2,"X-Z"),(1,2,"Y-Z")]):
    a.scatter(xyz[ii,i],xyz[ii,j],c=rgb[ii],s=0.7,linewidths=0); a.set_title(t); a.set_aspect("equal")
fig.suptitle(f"{ZIP.stem} decoded (finest LOD, {N:,} gaussians)")
fig.tight_layout(); fig.savefig("outputs/14_playroom_decoded.png",dpi=110); print("saved outputs/14_playroom_decoded.png")
