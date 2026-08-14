"""Evaluation top-down renders — the CLIP/figure product shots.

For every paired scene, four clean images into out/eval_renders/:
    <scene>_ours_ortho.png    <scene>_ours_persp.png
    <scene>_glts_ortho.png    <scene>_glts_persp.png
plus index.html, a contact sheet for the user's review.

SPEC (EVAL_PLAN_2026-08-13; wall experiment + pyrender rebuild both
user-ordered the same day):
- 1024x1024, room-centered. Ortho frame = 1.1 x the room's larger
  dimension (GLTS's own blender_placement.py rule: ORTHO camera,
  ortho_scale = 1.1 * max(room_dim)). Perspective = 60 deg yfov (the
  FOV GLTS's side-view camera uses), eye high enough that the wall
  tops project inside the same frame.
- REAL 3D WALLS, extruded floor -> 2.4 m as mitred prisms (user: "it
  also need to be extrusion from the floor level"), both sides, each
  per its own claim: ours = the measured shell polygon; GLTS = its
  claimed room rectangle.
- BARE floor both sides, assets only, no outlines/labels — annotations
  would contaminate the CLIP input.
- ONE renderer both methods and both projections: pyrender (z-buffered
  — the earlier painter's height-sort could not get inside/outside
  occlusion right and was retired for these shots; compare_methods'
  own inline thumbnails still use it, untouched). pyrender is already
  standard in this pipeline (rotation_check, pick, sub-round pages).

Ours = compose/fitted_preview.glb with its real textures (R-S2-172:
product shots are the MESH, never boxes). GLTS = its scene assembled
by compare_methods.render_glts_composed — its own step-15 recipe —
with the albedo-sampled face colors that assembly produces. A scene
missing either side is reported on the sheet, not skipped silently.

Run:  python eval_renders.py            (all pairs)
      python eval_renders.py --scenes sunlit_office,blue_living
"""
import argparse
import json
import math
from pathlib import Path

import numpy as np
import trimesh
import pyrender
from PIL import Image

import paths
import compare_methods as cm

RES = 1024
FRAME_FACTOR = 1.1          # GLTS's ortho_scale rule
PERSP_FOV_DEG = 60.0        # GLTS's side-view FOV, reused for the experiment
WALL_T = 0.12
WALL_H = 2.4
WALL_RGBA = [120, 120, 126, 255]
OUT_DIR = paths.OUT / "eval_renders"

PAIRS = ["natural_living", "sunlit_office", "blue_living", "panel_bedroom",
         "arch_bedroom", "plaster_bedroom",
         "bedroom_marble", "living_marble", "fresh04", "fresh06"]


# ---------------- walls: mitred prisms from the floor ----------------

def _offset_poly(pts, d):
    """Mitred outward offset of a CCW polygon by d (outward = right of
    each directed edge). Miter limit 4x -> clamped at sharp corners."""
    n = len(pts)
    out = []
    for i in range(n):
        x0, y0 = pts[i - 1]
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % n]
        e0 = (x1 - x0, y1 - y0)
        e1 = (x2 - x1, y2 - y1)
        l0 = math.hypot(*e0) or 1.0
        l1 = math.hypot(*e1) or 1.0
        n0 = (e0[1] / l0, -e0[0] / l0)
        n1 = (e1[1] / l1, -e1[0] / l1)
        mx, my = n0[0] + n1[0], n0[1] + n1[1]
        ml = math.hypot(mx, my)
        if ml < 1e-6:
            out.append((x1 + n0[0] * d, y1 + n0[1] * d))
            continue
        mx, my = mx / ml, my / ml
        scale = d / max(mx * n0[0] + my * n0[1], 0.25)
        out.append((x1 + mx * scale, y1 + my * scale))
    return out


def clean_boundary(poly):
    """Shell polygons are sometimes WEAKLY simple — the trace doubles
    back and revisits corners (fresh06), which breaks per-edge outward
    normals and drops whole walls. buffer(0) resolves the ring into a
    clean simple polygon; on a MultiPolygon the largest part wins
    (reported loudly — that is a trace question, not a render one)."""
    from shapely.geometry import Polygon, MultiPolygon
    p = Polygon([tuple(v[:2]) for v in poly]).buffer(0)
    if isinstance(p, MultiPolygon):
        parts = sorted(p.geoms, key=lambda g: g.area)
        print(f"[eval_renders] WARN weakly-simple boundary split into "
              f"{len(parts)} parts; keeping largest "
              f"({parts[-1].area:.1f} m2, dropping "
              f"{sum(g.area for g in parts[:-1]):.1f} m2)")
        p = parts[-1]
    return [(x, y) for x, y in p.exterior.coords[:-1]]


def floor_mesh(poly):
    """White floor plane filling the room polygon (user: "outside just
    black, just cover it" — done by inverting: black BACKGROUND, real
    white floor inside; an offset ring skirt self-intersects on concave
    polygons and was abandoned). z=-0.01 so nothing z-fights."""
    from shapely.geometry import Polygon
    pts = [tuple(p[:2]) for p in poly]
    v2, f = trimesh.creation.triangulate_polygon(Polygon(pts))
    v3 = np.column_stack([v2, np.full(len(v2), -0.01)])
    m = trimesh.Trimesh(vertices=v3, faces=f, process=False)
    m.visual.face_colors = np.tile([250, 250, 250, 255], (len(m.faces), 1))
    return m


def wall_mesh(poly):
    """One trimesh: the wall ring extruded from z=0 to WALL_H — real
    prisms (inner face, outer face, top cap), mitred so adjacent
    segments share corner vertices."""
    pts = [tuple(p[:2]) for p in poly]
    area2 = sum(x0 * y1 - x1 * y0
                for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    if area2 < 0:
        pts = pts[::-1]
    outer = _offset_poly(pts, WALL_T)
    n = len(pts)
    # vertex layout per corner i: [inner z0, inner zH, outer z0, outer zH]
    verts = []
    for i in range(n):
        ix, iy = pts[i]
        ox, oy = outer[i]
        verts += [[ix, iy, 0.0], [ix, iy, WALL_H],
                  [ox, oy, 0.0], [ox, oy, WALL_H]]
    faces = []
    for i in range(n):
        a = 4 * i
        b = 4 * ((i + 1) % n)
        # inner face (a0,a1,b1,b0), outer face, top cap (a1,b1,b3,a3)
        faces += [[a + 0, b + 0, b + 1], [a + 0, b + 1, a + 1],
                  [a + 2, b + 3, b + 2], [a + 2, a + 3, b + 3],
                  [a + 1, b + 1, b + 3], [a + 1, b + 3, a + 3]]
    m = trimesh.Trimesh(vertices=np.array(verts, float),
                        faces=np.array(faces), process=False)
    m.visual.face_colors = np.tile(WALL_RGBA, (len(m.faces), 1))
    return m


# ---------------- per-side scene collection (plan frame, z up) --------

def _floor_upright(scene):
    """The shell's measured floor height in the upright/plan frame.
    Scenes' floors are NOT at 0 (fresh06: -1.336 m) — walls extruded
    from 0 float above the real floor and perspective parallax shows
    it (the user's bench-corner find)."""
    p = paths.scene_dir(scene) / "room_shell.json"
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return 0.0
    v = d.get("floor_upright_m")
    while isinstance(d, dict) and v is None:
        d = next((x for x in d.values() if isinstance(x, dict)), None)
        v = d.get("floor_upright_m") if d else None
    return float(v) if v is not None else 0.0


def _plan_matrix(scene):
    """4x4 raw -> plan metres (x, y horizontal, z up, FLOOR AT 0): the
    same elementwise sign flip + axis swap compare_methods uses, plus a
    lift so the shell's measured floor lands at z=0 — the convention
    the walls, the camera math and the GLTS side all share. trimesh
    flips winding itself when the determinant is negative."""
    s = np.array(cm.ours_frame(scene), dtype=float)
    M = np.zeros((4, 4))
    M[0, 0] = s[0]          # plan x  = raw x * sx
    M[1, 2] = s[2]          # plan y  = raw z * sz
    M[2, 1] = s[1]          # plan up = raw y * sy
    M[2, 3] = -_floor_upright(scene)
    M[3, 3] = 1.0
    return M


#: user ruling (review session): for scenes whose CURRENT dir has no
#: composed product, "we use whatever the best object scene we got" —
#: the newest era that produced one. Provenance shows on the sheet.
GLB_FALLBACKS = {
    "living_marble": Path("archive_2026-08-06_pre_normalization")
    / "compose_prescale_era" / "compose" / "fitted_preview.glb",
}


def ours_scene(scene):
    """(meshes, boundary_poly, note) or (None, why, None)."""
    note = ""
    glb = paths.scene_dir(scene) / "compose" / "fitted_preview.glb"
    if not glb.exists() and scene in GLB_FALLBACKS:
        glb = paths.scene_dir(scene) / GLB_FALLBACKS[scene]
        note = f"fallback GLB: {GLB_FALLBACKS[scene]}"
    if not glb.exists():
        return None, "no composed GLB in any known era", None
    room = cm.load_room_shell(scene)
    poly = room.get("polygon_vertices_upright")
    if not poly and room.get("footprint_bbox_m"):
        # pre-polygon-era shell: walls from the measured bounding rect
        x0, y0, x1, y1 = room["footprint_bbox_m"]
        poly = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        note = (note + "; " if note else "") + "walls from shell bbox (no polygon)"
    if not poly:
        return None, f"no shell polygon or bbox ({room.get('why')})", None
    sc = trimesh.load(str(glb))
    meshes = sc.dump() if hasattr(sc, "dump") else [sc]
    M = _plan_matrix(scene)
    out = []
    for m in meshes:
        m = m.copy()
        m.apply_transform(M)
        out.append(m)
    return out, poly, note


def glts_scene(scene):
    """(meshes, boundary_rect, note) or (None, why, None). The assembled triangles
    (albedo-sampled face colors) are captured from render_glts_composed;
    walls come from GLTS's own claimed room rectangle."""
    root, d0 = cm.glts_dirs(scene)
    fur_p = d0 / "13_furniture_layout.json"
    if not fur_p.exists():
        return None, f"no GLTS run ({fur_p})", None
    dim = json.loads(fur_p.read_text(encoding="utf-8")).get("room_dimension")
    if not dim:
        return None, "13_furniture_layout.json has no room_dimension", None
    captured = {}
    orig = cm._paint_topdown

    def capture(T, C, bb, poly, ppm):
        captured["T"], captured["C"] = T, C
        return "data:,"

    cm._paint_topdown = capture
    try:
        _, why, _ = cm.render_glts_composed({"dir": str(d0)}, 40)
    finally:
        cm._paint_topdown = orig
    if "T" not in captured:
        return None, f"GLTS assembly failed: {why}", None
    T, C = captured["T"], captured["C"]
    soup = trimesh.Trimesh(vertices=T.reshape(-1, 3),
                           faces=np.arange(T.shape[0] * 3).reshape(-1, 3),
                           process=False)
    rgba = np.concatenate([np.clip(C, 0, 255),
                           np.full((len(C), 1), 255.0)], axis=1)
    soup.visual.face_colors = rgba.astype(np.uint8)
    rect = [(0.0, 0.0), (dim[0], 0.0), (dim[0], dim[1]), (0.0, dim[1])]
    return [soup], rect, ""


def clip_to_room(meshes, boundary):
    """Cut away everything OUTSIDE the room volume (user ruling: outside
    the walls nothing is visible). Triangle-level: keep faces whose
    centroid lies inside the polygon dilated by the wall thickness (so
    wall-flush faces survive; the wall band hides the cut seam).
    Fully-outside meshes disappear."""
    from matplotlib.path import Path as MplPath
    pts = [tuple(p[:2]) for p in boundary]
    area2 = sum(x0 * y1 - x1 * y0
                for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]))
    if area2 < 0:
        pts = pts[::-1]
    clip = MplPath(_offset_poly(pts, WALL_T + 0.01))
    out = []
    for m in meshes:
        cen = m.triangles_center
        # inside the polygon AND below the render's ceiling (the wall
        # rim): parts of meshes above it are cut, not drawn floating
        keep = clip.contains_points(cen[:, :2]) & (cen[:, 2] <= WALL_H)
        if keep.all():
            out.append(m)
            continue
        if not keep.any():
            continue
        m = m.copy()
        m.update_faces(keep)
        m.remove_unreferenced_vertices()
        if len(m.faces):
            out.append(m)
    return out


def frame_of(boundary):
    xs = [p[0] for p in boundary]
    ys = [p[1] for p in boundary]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    half = max(max(xs) - min(xs), max(ys) - min(ys)) * FRAME_FACTOR / 2
    return (cx, cy), half


# ---------------- the pyrender shot ----------------

def render(meshes, mask_meshes, center, half, persp, out_png):
    # black background = everything outside the walls reads black; the
    # room interior is a real white floor mesh. (floats, not ints:
    # pyrender divides INTEGER color vectors by 255)
    scene = pyrender.Scene(bg_color=[0.0, 0.0, 0.0, 1.0],
                           ambient_light=[0.45] * 3)
    for m in meshes:
        pm = pyrender.Mesh.from_trimesh(m, smooth=False)
        for prim in pm.primitives:
            if prim.material is not None:
                prim.material.doubleSided = True
        scene.add(pm)

    cx, cy = center
    if persp:
        t = math.tan(math.radians(PERSP_FOV_DEG) / 2)
        half = half + WALL_H * t        # wall tops project inside the frame
        eye_h = half / t
        cam = pyrender.PerspectiveCamera(
            yfov=math.radians(PERSP_FOV_DEG), znear=0.1, zfar=eye_h + 10)
    else:
        eye_h = 30.0
        cam = pyrender.OrthographicCamera(
            xmag=half, ymag=half, znear=0.1, zfar=eye_h + 10)
    pose = np.eye(4)                     # -Z looks straight down, +Y is up
    pose[:3, 3] = [cx, cy, eye_h]
    scene.add(cam, pose=pose)

    key = np.eye(4)                      # straight-down key light
    key[:3, 3] = [cx, cy, eye_h]
    scene.add(pyrender.DirectionalLight(intensity=3.0), pose=key)
    side = trimesh.transformations.rotation_matrix(
        math.radians(35), [1, 0, 0], point=[cx, cy, 0])
    side[:3, 3] += [cx, cy, eye_h]
    scene.add(pyrender.DirectionalLight(intensity=1.5), pose=side)

    # mask pass: walls+floor only, same camera — pixels where that pass
    # has NO depth are outside the room silhouette and get painted
    # black, which removes triangle parts the centroid clip let through
    mscene = pyrender.Scene(bg_color=[0.0, 0.0, 0.0, 1.0],
                            ambient_light=[1.0] * 3)
    for m in mask_meshes:
        pm = pyrender.Mesh.from_trimesh(m, smooth=False)
        for prim in pm.primitives:
            if prim.material is not None:
                prim.material.doubleSided = True
        mscene.add(pm)
    mscene.add(cam, pose=pose)

    r = pyrender.OffscreenRenderer(RES, RES)
    try:
        color, _ = r.render(scene)
        _, depth = r.render(mscene)
    finally:
        r.delete()
    out = np.asarray(color).copy()
    out[depth <= 0.0] = 0
    Image.fromarray(out).save(out_png)


# ---------------- main ----------------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenes", default="",
                    help="comma-separated subset (default: the ten pairs)")
    a = ap.parse_args()
    scenes = ([s.strip() for s in a.scenes.split(",") if s.strip()]
              or PAIRS)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    rows, gaps = [], []
    for sc in scenes:
        row = {"scene": sc}
        for side, getter in (("ours", ours_scene), ("glts", glts_scene)):
            meshes, boundary, note = getter(sc)
            if meshes is None:
                gaps.append(f"{sc} {side}: {boundary}")
                row[side] = None
                continue
            boundary = clean_boundary(boundary)
            center, half = frame_of(boundary)
            walls = wall_mesh(boundary)
            floor = floor_mesh(boundary)
            meshes = clip_to_room(meshes, boundary) + [walls, floor]
            for proj, persp in (("ortho", False), ("persp", True)):
                f = OUT_DIR / f"{sc}_{side}_{proj}.png"
                render(meshes, [walls, floor], center, half, persp, f)
                print(f"[eval_renders] {f.name}"
                      + (f"  ({note})" if note else ""))
            row[side] = True
            row[side + "_note"] = note
        rows.append(row)

    cells = []
    for r in rows:
        sc = r["scene"]
        cells.append(f"<h2>{sc}</h2><div class='row'>")
        for side in ("ours", "glts"):
            for proj in ("ortho", "persp"):
                f = f"{sc}_{side}_{proj}.png"
                if r[side]:
                    note = r.get(side + "_note") or ""
                    cap = f"{side} · {proj}" + (
                        f" <span class='warn'>⚠ {note}</span>" if note else "")
                    cells.append(
                        f"<figure><img src='{f}' loading='lazy'>"
                        f"<figcaption>{cap}</figcaption></figure>")
                else:
                    cells.append(
                        f"<figure><div class='missing'>missing</div>"
                        f"<figcaption>{side} · {proj}</figcaption></figure>")
        cells.append("</div>")
    gap_html = ("<h2>gaps</h2><ul>" +
                "".join(f"<li>{g}</li>" for g in gaps) + "</ul>") if gaps else ""
    (OUT_DIR / "index.html").write_text(
        "<!doctype html><meta charset='utf-8'>"
        "<title>eval renders — review sheet</title><style>"
        "body{font-family:sans-serif;margin:20px;background:#fafafa}"
        ".row{display:flex;gap:10px;flex-wrap:wrap}"
        "figure{margin:0}img{width:340px;border:1px solid #ccc}"
        ".missing{width:340px;height:340px;display:flex;align-items:center;"
        "justify-content:center;background:#eee;color:#999;border:1px dashed #bbb}"
        "figcaption{text-align:center;color:#555;font-size:13px}"
        ".warn{color:#b26a00}"
        "</style><h1>eval renders — pyrender, 3D walls from the floor, "
        "bare floor, assets only (ortho = GLTS camera spec; persp = 60° "
        "experiment)</h1>"
        + "".join(cells) + gap_html, encoding="utf-8")
    print(f"[eval_renders] sheet -> {OUT_DIR / 'index.html'}")
    if gaps:
        print("[eval_renders] GAPS:")
        for g in gaps:
            print("  ", g)


if __name__ == "__main__":
    main()
