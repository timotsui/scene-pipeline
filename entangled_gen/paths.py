"""Canonical out/ layout — one folder per scene (reorganized 2026-07-05).

    out/<scene>/
        gen_raw.ply           the splat (realplayroom's lives in week5, see ply())
        scene_manifest.json   lifted objects (RAW ply space, physical up = frame.up
                              = -y under rot180; see frame.raw_to_render + the
                              2026-07-05C handoff for the frame contract)
        views/                GPU yaw renders + camera sidecars
        seg/                  GroundingDINO+SAM outputs + manifest overlays/plan
        package/              LLM composition package (GUIDE.md, proposals)
        pano_frames/          panorama sweep frames
        panorama.png  envelope.npz  envelope_heatmap.png  live_placement.json

Shared (not per scene): out/report.html, out/cache, out/archive, out/logs,
out/viewer_caps, out/_debug. Every script builds paths through here.
"""
import json as _json
from pathlib import Path

HERE = Path(__file__).parent

# Data lives OUTSIDE the repo (out/ is ~15 GB): machine-local roots come from a
# gitignored local_paths.json next to this file (see local_paths.json.example).
# Fallback: repo-local out/ + sibling week5 checkout, the old in-tree layout.
if (HERE / "local_paths.json").exists():
    _cfg = _json.loads((HERE / "local_paths.json").read_text())
    OUT = Path(_cfg["out"])
    W5 = Path(_cfg["week5"])
else:
    _cfg = {}
    OUT = HERE / "out"
    W5 = HERE.parent.parent / "week5" / "splat_to_placement"   # realplayroom data

CFG = _cfg                 # full parsed config — comp_paths.py reads its keys here
REPO_ROOT = HERE.parent    # scene-pipeline/ (launch_*.bat live here)

# local copies of the week5 render tools (2026-07-05) — edit these, not week5
RENDERTOOLS = HERE / "rendertools"
SHOT = RENDERTOOLS / "shot.py"
RENDER03 = RENDERTOOLS / "03_render.py"


def load_r3():
    """Import the numpy renderer (Cam/load_splat) from the local copy."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("render03", RENDER03)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def scene_dir(sc):
    return OUT / sc


def ply(sc):
    if sc == "realplayroom":
        # the week5 real-scan splat (real leg), not a generated one
        return W5 / "data" / "superspl" / "playroom_centered.ply"
    return scene_dir(sc) / "gen_raw.ply"


def views_dir(sc):
    return scene_dir(sc) / "views"


def seg_dir(sc):
    return scene_dir(sc) / "seg"


def pano_crops_dir(sc):
    """Pinhole crops sliced from a bundle equirect (crop_pano.py, week8)."""
    return scene_dir(sc) / "pano_crops"


def seg_pano_dir(sc):
    """seg_views outputs on the pano crops (week8 object-ID path)."""
    return scene_dir(sc) / "seg_pano"


def package_dir(sc):
    return scene_dir(sc) / "package"


def compose_dir(sc):
    """STEP 3 COMPOSE+LOOP outputs (supported_by.json, ...). 2026-07-26."""
    return scene_dir(sc) / "compose"


def manifest(sc):
    return scene_dir(sc) / "scene_manifest.json"


def frame_block(sc):
    """The scene's frame record: legacy sweep manifest (bedroom-era) ->
    frame_bootstrap.json (fresh scenes; same schema since 2026-08-06 —
    intake writes the full block incl. raw_to_render + extents)."""
    import json
    legacy = manifest(sc)
    if legacy.exists():
        return json.loads(legacy.read_text())["frame"]
    boot = scene_dir(sc) / "frame_bootstrap.json"
    if boot.exists():
        return json.loads(boot.read_text())
    raise SystemExit(f"[paths] no frame info for {sc}: run "
                     f"frame_bootstrap.py --scene {sc} (fresh scene), or "
                     f"provide the legacy sweep manifest")


def graph_fingerprint(sc):
    """Content hashes of the two graph slices compose layers consume:
    'geometry' (resolved boxes + names + arch planes) and 'testimony'
    (per-node witness words: description + support_view). Compose
    modules stamp this into their output; the viewer's staleness gate
    compares the stamp against the CURRENT graph, so a graph rewrite
    only stales layers whose real inputs changed. (The old mtime gate
    staled every layer on any graph write — e.g. the additive facing
    field, 08-02C.) Returns None if the graph doesn't exist."""
    import hashlib
    p = scene_dir(sc) / "scene_graph.json"
    if not p.exists():
        return None
    g = _json.loads(p.read_text(encoding="utf-8"))
    geo = sorted(
        [(n["id"], n.get("name"),
          n["geometry"]["aabb_min"], n["geometry"]["aabb_max"])
         for n in g.get("resolved", {}).get("nodes", [])]
        + [(n["id"], "arch", n["geometry"]["plane"]["value_raw"], None)
           for n in g.get("nodes", []) if n["id"].startswith("arch_")])
    tes = sorted(
        (n["id"], (n.get("appearance") or {}).get("description"),
         _json.dumps((n.get("appearance") or {}).get("support_view"),
                     sort_keys=True))
        for n in g.get("judged", {}).get("nodes", []))
    h = lambda obj: hashlib.sha256(   # noqa: E731
        _json.dumps(obj, sort_keys=True).encode()).hexdigest()[:16]
    return {"geometry": h(geo), "testimony": h(tes)}


def envelope_npz(sc):
    return scene_dir(sc) / "envelope.npz"


def envelope_heatmap(sc):
    return scene_dir(sc) / "envelope_heatmap.png"


def live_placement(sc):
    return scene_dir(sc) / "live_placement.json"


def panorama(sc):
    return scene_dir(sc) / "panorama.png"


def pano_frames(sc):
    return scene_dir(sc) / "pano_frames"


def spots(sc):
    return scene_dir(sc) / "spots.png"


def gen_scenes():
    """Scenes with a generated splat on disk (excludes realplayroom)."""
    return sorted(d.name for d in OUT.iterdir()
                  if d.is_dir() and (d / "gen_raw.ply").exists())


def all_scenes():
    """Every scene folder (has a manifest or a splat)."""
    return sorted(d.name for d in OUT.iterdir() if d.is_dir()
                  and ((d / "gen_raw.ply").exists() or (d / "scene_manifest.json").exists()))
