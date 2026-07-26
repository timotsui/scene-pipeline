"""G1 — adapt splat_analyzer job cameras (transforms.json) to our r3.Cam and
VERIFY the 4x4 convention mechanically (PLAN_SPLAT_RECENTER.md gate G1).

The tool writes a c2w `transform_matrix` per frame, but the axis convention
(OpenCV y-down/z-forward vs OpenGL y-up/z-backward) and even the c2w-vs-w2c
direction are unverified. Wrong guesses fail SILENTLY (boxes land nowhere),
so — house rule for every frame crossing — we measure instead of assume:
color z-buffer the splat means through each candidate camera and correlate
against the tool's actual rendered frame png. The right convention lights up;
the wrong ones produce scrambled images with ~zero correlation.

Run:  python analyzer/cams_from_transforms.py --scene bedroom_marble
Import: cams_for_job(scene, job) -> {frame_idx: r3.Cam} using the WINNING
convention (asserts the stored G1 winner exists in the job dir).
"""
import argparse, json
from pathlib import Path
import sys

import numpy as np

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE.parent))
import paths

r3 = paths.load_r3()

# candidate interpretations of transform_matrix
# name -> (direction, rows-of-R builder). Our r3.Cam frame: world = pos +
# [x_right, y_up, z_fwd] @ R, i.e. R rows = camera right/up/forward in world.
def _rows_opencv(M):    # x right, y DOWN, z forward
    return np.stack([M[:3, 0], -M[:3, 1], M[:3, 2]])

def _rows_opengl(M):    # x right, y up, z BACKWARD
    return np.stack([M[:3, 0], M[:3, 1], -M[:3, 2]])

CANDIDATES = {
    "c2w_opencv": ("c2w", _rows_opencv),
    "c2w_opengl": ("c2w", _rows_opengl),
    "w2c_opencv": ("w2c", _rows_opencv),
    "w2c_opengl": ("w2c", _rows_opengl),
}


class MatCam:
    """r3.Cam-compatible camera built directly from R rows + pos + intrinsics
    (r3.Cam wants pos/look/up/fov; going through those loses nothing but this
    is more direct and avoids degenerate up/look cases)."""

    def __init__(self, R, pos, f, cx, cy, w, h):
        self.R = R.astype(np.float32)          # rows: right, up, forward (world)
        self.pos = pos.astype(np.float32)
        self.f = float(f); self.cx = float(cx); self.cy = float(cy)
        self.w = int(w); self.h = int(h)

    def project(self, xyz):
        rel = (xyz - self.pos) @ self.R.T      # world -> cam (right, up, fwd)
        x, y, z = rel[:, 0], rel[:, 1], rel[:, 2]
        with np.errstate(divide="ignore", invalid="ignore"):
            u = self.cx + self.f * x / z
            v = self.cy - self.f * y / z       # image v grows downward
        return u, v, z


def load_job(scene, job=""):
    base = paths.scene_dir(scene) / "analyzer"
    if job:
        jd = base / job
    else:
        cands = sorted(base.glob("job_*/transforms.json"),
                       key=lambda f: f.stat().st_mtime, reverse=True)
        if not cands:
            raise SystemExit("no analyzer job with transforms.json")
        jd = cands[0].parent
    return jd, json.loads((jd / "transforms.json").read_text())


def build_cam(tj, frame, conv):
    direction, rows = CANDIDATES[conv]
    M = np.array(frame["transform_matrix"], np.float64)
    if direction == "w2c":
        M = np.linalg.inv(M)
    R = rows(M)
    pos = M[:3, 3]
    return MatCam(R, pos, tj["fl_x"], tj["cx"], tj["cy"], tj["w"], tj["h"])


def g1_table(scene, job="", n_sample=8, size=192):
    """Correlation of color-z-buffer renders vs the tool's frame pngs, per
    candidate convention. Returns (winner, {conv: mean corr}, per-frame wins)."""
    from PIL import Image
    jd, tj = load_job(scene, job)
    frames = tj["frames"]
    idxs = np.linspace(0, len(frames) - 1, n_sample).astype(int)
    xyz, rgb, _a, _r = r3.load_splat(str(paths.ply(scene)), opacity_min=0.3)
    scale = size / tj["w"]
    sums = {c: 0.0 for c in CANDIDATES}
    wins = {c: 0 for c in CANDIDATES}
    for i in idxs:
        fr = frames[i]
        ref = Image.open(jd / fr["file_path"]).convert("L").resize((size, size))
        ref = np.asarray(ref, np.float32)
        ref = (ref - ref.mean()) / (ref.std() + 1e-6)
        row = {}
        for conv in CANDIDATES:
            cam = build_cam(tj, fr, conv)
            cam = MatCam(cam.R, cam.pos, cam.f * scale, cam.cx * scale,
                         cam.cy * scale, size, size)
            u, v, z = cam.project(xyz)
            ok = (z > 0.2) & np.isfinite(u) & np.isfinite(v)
            ui = np.round(u[ok]).astype(np.int64)
            vi = np.round(v[ok]).astype(np.int64)
            order = np.argsort(-z[ok])          # painter: near overwrites far
            img = np.zeros((size, size), np.float32)
            uu, vv = ui[order], vi[order]
            inb = (uu >= 0) & (uu < size) & (vv >= 0) & (vv < size)
            img[vv[inb], uu[inb]] = rgb[ok][order][inb].mean(axis=1)
            img = (img - img.mean()) / (img.std() + 1e-6)
            row[conv] = float((img * ref).mean())
            sums[conv] += row[conv]
        wins[max(row, key=row.get)] += 1
        print(f"  frame {fr['file_path']}: "
              + "  ".join(f"{c}={row[c]:+.3f}" for c in CANDIDATES), flush=True)
    means = {c: s / len(idxs) for c, s in sums.items()}
    return max(means, key=means.get), means, wins


def cams_for_job(scene, job="", conv=None):
    """All frame cams under the G1-winning convention (stored in the job dir
    by the CLI run; pass conv explicitly to override)."""
    jd, tj = load_job(scene, job)
    if conv is None:
        conv = json.loads((jd / "g1_convention.json").read_text())["winner"]
    return {int(Path(fr["file_path"]).stem.split("_")[-1]):
            build_cam(tj, fr, conv) for fr in tj["frames"]}, jd, tj, conv


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--job", default="")
    a = ap.parse_args()
    print(f"[g1] {a.scene}: correlating 4 conventions x 8 frames ...", flush=True)
    winner, means, wins = g1_table(a.scene, a.job)
    print("[g1] mean corr: "
          + "  ".join(f"{c}={m:+.3f}" for c, m in means.items()), flush=True)
    print(f"[g1] per-frame wins: {wins}", flush=True)
    jd, _ = load_job(a.scene, a.job)
    (jd / "g1_convention.json").write_text(json.dumps(
        {"winner": winner, "mean_corr": {c: round(m, 4) for c, m in means.items()},
         "frame_wins": wins}, indent=2))
    print(f"[g1] winner: {winner}  (wrote {jd / 'g1_convention.json'})", flush=True)
