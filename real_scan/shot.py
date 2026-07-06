"""
shot.py - manual splat view probe.
Render one view of the splat via splat-transform (GPU), then open it.
Tweak the vectors by eye and re-run. ~5s per shot.

USAGE
  python shot.py 0,0,3   0,0,0                       # eye, target
  python shot.py -4,0,0  0,0,0   --fov 40            # zoom in
  python shot.py 0,3,0   0,0,0   --up 0,0,-1         # top-down (Y-up scene)
  python shot.py 0,0,3   0,0,0   --box -1,-3,-5,3,0,-1   # clip box (min corner,max corner)
  python shot.py 0,0,3   0,0,0   --sphere 0,0,-2,3      # clip sphere (x,y,z,radius)
  python shot.py 0,0,4   0,0,0   --near 2.5          # near clip plane
  python shot.py 0,0,3   0,0,0   --html              # interactive mouse-orbit viewer instead
  python shot.py --preset interior                   # known-good interior view (cam/look/fov preset)

  --no-open    render but don't pop the result
"""
import argparse, csv, json, os, subprocess, sys, time
from pathlib import Path

HERE = Path(__file__).parent

# Known-good camera presets, in CENTERED-PLY space (playroom_centered.ply, the default).
# 2026-06-22 we baked the recenter into the geometry: translated the original ST-space PLY
# by T=(1.5,-1.2,2.7) so the 'center' standpoint sits at the origin -> 'center' = 0,0,0.
# (To recover the old ST-space coords for the un-centered playroom.ply, subtract T.)
# 'center':   the canonical standpoint; origin, looking -z. Playroom behind, staircase ahead.
# 'interior': original by-eye view; 0.7 behind center along +z (we stepped forward 0.7 to get center).
PRESETS = {
    "center":   {"cam": "0,0,0",   "look": "0,0,-3",   "fov": 90.0},
    "interior": {"cam": "0,0,0.7", "look": "0,0,-2.3", "fov": 90.0},
}

def open_file(p):
    if sys.platform.startswith("win"): os.startfile(p)            # noqa
    elif sys.platform == "darwin":     subprocess.run(["open", p])
    else:                              subprocess.run(["xdg-open", p])

# the rendered webp is anonymous on disk, so stamp every shot with the exact camera that
# made it: a per-file <name>.json sidecar + an appended row in views/shots.csv (one browsable
# manifest of every shot). CSV is properly quoted because the coords themselves contain commas.
META_COLS = ["file", "time", "preset", "cam", "look", "up", "fov", "near", "box", "sphere", "res", "ply"]

def record_shot(out, a, preset_name=""):
    meta = {"file": out.name, "time": time.strftime("%Y-%m-%d %H:%M:%S"), "preset": preset_name,
            "cam": a.cam, "look": a.look, "up": a.up, "fov": a.fov, "near": a.near,
            "box": a.box, "sphere": a.sphere, "res": a.res, "ply": a.ply}
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2))
    manifest = out.parent / "shots.csv"
    write_header = not manifest.exists()
    with manifest.open("a", newline="") as f:
        w = csv.writer(f)
        if write_header: w.writerow(META_COLS)
        w.writerow([meta[c] for c in META_COLS])
    return out.with_suffix(".json"), manifest

def main():
    ap = argparse.ArgumentParser(
        description="manual splat view probe",
        usage="shot.py <cam x,y,z> <look x,y,z> [--box ...] [--fov ...] ...")
    # cam/look are taken as the first two argv tokens (below) so leading '-' in a
    # negative coord like -1,2,4 isn't mistaken for a flag. argparse only sees the rest.
    ap.add_argument("--box",    default="", help="clip box  xmin,ymin,zmin,xmax,ymax,zmax")
    ap.add_argument("--sphere", default="", help="clip sphere x,y,z,radius")
    ap.add_argument("--near", type=float, default=0.2, help="near clip plane (default 0.2)")
    ap.add_argument("--fov",  type=float, default=60,  help="vertical FOV deg (default 60)")
    ap.add_argument("--up",   default="0,1,0", help="world up (default 0,1,0; scene is Y-up)")
    ap.add_argument("--res",  default="900x900", help="WxH (default 900x900)")
    ap.add_argument("--out",  default="", help="output path (default: views/shot_<HHMMSS>.webp, unique so an open viewer can't lock it)")
    ap.add_argument("--ply",  default="data/superspl/playroom_centered.ply",
                    help="default is the recentered PLY (fwd07 standpoint = origin); pass playroom.ply for old ST-space coords")
    ap.add_argument("--gpu",  default="0", help="GPU index (0=RTX 4080) or 'cpu'")
    ap.add_argument("--html", action="store_true", help="interactive mouse-orbit viewer instead")
    ap.add_argument("--preset", default="", help=f"named camera preset ({', '.join(PRESETS)}); supplies cam/look/fov")
    ap.add_argument("--no-open", dest="open", action="store_false")

    argv = sys.argv[1:]
    if "-h" in argv or "--help" in argv:
        ap.parse_args(["-h"])

    # pull --preset out first so it can stand in for the positional cam/look coords
    preset, preset_name = None, ""
    if "--preset" in argv:
        i = argv.index("--preset")
        name = argv[i + 1] if i + 1 < len(argv) else ""
        if name not in PRESETS:
            ap.error(f"unknown preset {name!r}; known: {', '.join(PRESETS)}")
        preset, preset_name = PRESETS[name], name
        del argv[i:i + 2]

    # leading positional coords = cam, look. argparse flags all start with '--', while
    # negative coords start with a single '-' (e.g. -1.5,1.2,-2), so they don't collide.
    pos = []
    while argv and not argv[0].startswith("--"):
        pos.append(argv.pop(0))

    if preset:
        cam  = pos[0] if len(pos) > 0 else preset["cam"]
        look = pos[1] if len(pos) > 1 else preset["look"]
    else:
        if len(pos) < 2:
            ap.error("need first two args: <cam x,y,z> <look x,y,z>  (or use --preset)")
        cam, look = pos[0], pos[1]

    a = ap.parse_args(argv)                 # argparse handles only the optional flags
    if preset and "--fov" not in argv:      # preset fov unless the user overrode it
        a.fov = preset["fov"]
    a.cam, a.look = cam, look

    os.chdir(HERE)
    out = Path(a.out) if a.out else Path("views") / f"shot_{time.strftime('%H%M%S')}.webp"
    out.parent.mkdir(parents=True, exist_ok=True)

    if a.html:
        h = out.with_suffix(".html")
        print(f"building viewer on gpu {a.gpu} (first run can take ~1 min cold)...", flush=True)
        subprocess.run(["splat-transform", "-w", "-g", a.gpu, a.ply, str(h)],
                       check=True, shell=True, timeout=600)
        print("wrote", h)
        if a.open: open_file(h)
        return

    cmd = ["splat-transform", "-w", "-g", a.gpu, a.ply]   # no -q: show the progress bar
    if a.box:    cmd += ["-B", a.box]
    if a.sphere: cmd += ["-S", a.sphere]
    cmd += ["--camera", a.cam, "--look-at", a.look, "--up", a.up,
            "--fov", str(a.fov), "--near", str(a.near),
            "--resolution", a.res, "--background", "0.08,0.08,0.1", str(out)]

    print(f"rendering on gpu {a.gpu} (first run can take ~1 min cold, then ~5s)...", flush=True)
    subprocess.run(cmd, check=True, shell=True, timeout=600)
    print(f"eye={a.cam}  look={a.look}  fov={a.fov}  near={a.near}  "
          f"box={a.box or '-'}  sphere={a.sphere or '-'}  -> {out}")
    sidecar, manifest = record_shot(out, a, preset_name)
    print(f"coords -> {sidecar.name}  (+ appended to {manifest.name})")
    if a.open: open_file(out)

if __name__ == "__main__":
    main()
