"""
InteriorGS adapter: decode a PlayCanvas/SuperSplat *compressed* .ply -> standard uncompressed
3DGS .ply (x,y,z, normals, f_dc_0..2, opacity, scale_0..2, rot_0..3; SH-rest dropped = degree-0).
InteriorGS scenes are already clean + metric + Z-up, so NO 02_clean step is needed.

Compressed format: element chunk (per-256 min/max bounds) + element vertex (4x uint32 packed:
position 11/10/11, rotation smallest-3 quat, scale 11/10/11, color RGBA8) + element sh (uchar).
"""
import sys, numpy as np
from pathlib import Path

def parse_header(f):
    assert f.readline().strip() == b"ply"; f.readline()
    elems, cur = [], None
    while True:
        l = f.readline().strip()
        if l.startswith(b"element"):
            _, nm, c = l.split(); cur = {"name": nm.decode(), "count": int(c), "props": []}; elems.append(cur)
        elif l.startswith(b"property"):
            p = l.split(); cur["props"].append((p[1].decode(), p[2].decode()))
        elif l == b"end_header":
            return elems

def unorm(v, bits):
    return (v & ((1 << bits) - 1)) / float((1 << bits) - 1)

def decompress(src, dst):
    f = open(src, "rb")
    elems = parse_header(f)
    E = {e["name"]: e for e in elems}
    C, N = E["chunk"]["count"], E["vertex"]["count"]
    nsh = E["sh"]["count"] and len(E["sh"]["props"])
    chunks = np.frombuffer(f.read(C*18*4), dtype="<f4").reshape(C, 18)
    vtx = np.frombuffer(f.read(N*4*4), dtype="<u4").reshape(N, 4)
    f.close()

    ci = np.arange(N) // 256
    ck = chunks[ci]                       # (N,18) per-vertex chunk bounds
    def lerp(t, lo, hi): return lo + t*(hi-lo)

    # position 11/10/11
    pp = vtx[:, 0]
    x = lerp(unorm(pp >> 21, 11), ck[:, 0], ck[:, 3])
    y = lerp(unorm(pp >> 11, 10), ck[:, 1], ck[:, 4])
    z = lerp(unorm(pp,        11), ck[:, 2], ck[:, 5])

    # scale 11/10/11 (already log-scale)
    ps = vtx[:, 2]
    sx = lerp(unorm(ps >> 21, 11), ck[:, 6],  ck[:, 9])
    sy = lerp(unorm(ps >> 11, 10), ck[:, 7],  ck[:, 10])
    sz = lerp(unorm(ps,        11), ck[:, 8],  ck[:, 11])

    # color RGBA8 ; r,g,b -> f_dc via chunk range ; a -> opacity (alpha)
    pc = vtx[:, 3]
    r = lerp(unorm(pc >> 24, 8), ck[:, 12], ck[:, 15])
    g = lerp(unorm(pc >> 16, 8), ck[:, 13], ck[:, 16])
    b = lerp(unorm(pc >> 8,  8), ck[:, 14], ck[:, 17])
    alpha = np.clip(unorm(pc, 8), 1e-6, 1-1e-6)
    opacity = np.log(alpha/(1-alpha))     # standard PLY stores logit

    # rotation: smallest-three -> (w,x,y,z)
    pr = vtx[:, 1]; s2 = np.sqrt(2.0)
    a = (unorm(pr >> 20, 10)-0.5)*s2
    bb= (unorm(pr >> 10, 10)-0.5)*s2
    cc= (unorm(pr,       10)-0.5)*s2
    m = np.sqrt(np.clip(1-(a*a+bb*bb+cc*cc), 0, None))
    which = pr >> 30
    # PlayCanvas q=(x,y,z,w); the largest component (m) sits at index `which`, others a,bb,cc in order
    qx = np.select([which==0,which==1,which==2,which==3], [m, a, a, a])
    qy = np.select([which==0,which==1,which==2,which==3], [a, m, bb, bb])
    qz = np.select([which==0,which==1,which==2,which==3], [bb,bb, m, cc])
    qw = np.select([which==0,which==1,which==2,which==3], [cc,cc,cc, m])

    # assemble standard schema (w,x,y,z order for rot)
    zeros = np.zeros(N, dtype="<f4")
    cols = [x, y, z, zeros, zeros, zeros, r, g, b, opacity, sx, sy, sz, qw, qx, qy, qz]
    names = ["x","y","z","nx","ny","nz","f_dc_0","f_dc_1","f_dc_2","opacity",
             "scale_0","scale_1","scale_2","rot_0","rot_1","rot_2","rot_3"]
    out = np.stack([np.asarray(c, dtype="<f4") for c in cols], 1)

    hdr = "ply\nformat binary_little_endian 1.0\nelement vertex %d\n" % N
    hdr += "".join("property float %s\n" % n for n in names) + "end_header\n"
    with open(dst, "wb") as g:
        g.write(hdr.encode("ascii")); g.write(np.ascontiguousarray(out).tobytes())
    print(f"decoded {N:,} gaussians -> {dst}")
    print(f"  bbox  : min {np.round([x.min(),y.min(),z.min()],2)}  max {np.round([x.max(),y.max(),z.max()],2)}")
    print(f"  alpha : mean {alpha.mean():.2f}  frac>0.5 {(alpha>0.5).mean():.1%}")

if __name__ == "__main__":
    src = Path("data/raw/InteriorGS/0062_839922/3dgs_compressed.ply")
    dst = Path("data/raw/InteriorGS/0062_839922/room_uncompressed.ply")
    decompress(src, dst)
