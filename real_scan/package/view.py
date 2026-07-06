"""
view.py - the simplest way to make more images of the playroom.

Run from this package directory. All the camera/clip/coordinate details are handled
for you; you just say where to look. Images land in views/ and print their path.

LOOK AROUND FROM THE STANDPOINT (eye-level, fov 90):
  python view.py north          # also: n ne e se s sw w nw  (compass headings)
  python view.py 135            # or any compass angle in degrees (0=N, 90=E, 180=S, 270=W)

TOP-DOWN PLAN:
  python view.py plan           # clean near-orthographic floor plan (recommended)
  python view.py plan90         # fov-90 oblique plan (matches eye-level fov)

ANYTHING ELSE (full control, same frame):
  python view.py eye=0,0,-1 look=0,0,2          # stand elsewhere, look somewhere
  python view.py east fov=60                     # zoom a heading
  python view.py from=1,0,0 north                # move the standpoint, keep the heading
  python view.py east out=explore/east_zoom      # name the output file (else auto-named)

Frame: origin = standpoint, North=-z, East=+x, South=+z, West=-x, up=+y (floor at -y).
"""
import math, subprocess, sys
from pathlib import Path

HERE = Path(__file__).parent
SHOT = HERE.parent / "shot.py"                       # the real renderer, one level up
OUT  = HERE / "views"
PLAN_BOX = "-4.3,-5,-3.3,2.5,0,2.5"                  # ceiling clipped at standpoint plane

COMPASS = {"n": 0, "ne": 45, "e": 90, "se": 135, "s": 180, "sw": 225, "w": 270, "nw": 315,
           "north": 0, "east": 90, "south": 180, "west": 270,
           "northeast": 45, "southeast": 135, "southwest": 225, "northwest": 315}

def run(args, name):
    out = OUT / f"{name}.webp"
    cmd = [sys.executable, str(SHOT)] + args + [f"--out={out}", "--no-open"]
    subprocess.run(cmd, check=True)
    print(f"\n-> {out}")

def vec(s): return [float(x) for x in s.split(",")]

def main():
    a = sys.argv[1:]
    if not a or a[0] in ("-h", "--help"):
        print(__doc__); return

    # collect key=value options (eye=, look=, from=, fov=) and leave the bare word/number
    opt, word = {}, None
    for tok in a:
        if "=" in tok:
            k, v = tok.split("=", 1); opt[k] = v
        else:
            word = tok
    fov = opt.get("fov", "90")
    eye = opt.get("from", opt.get("eye", "0,0,0"))    # standpoint (origin by default)
    forced = opt.get("out")                            # optional output name (no extension)

    # 1) plan views -------------------------------------------------------------
    if word in ("plan", "plan90"):
        if word == "plan":
            run(["0.5,16,0.0", "0.5,-1,0.0", "--up=0,0,-1", "--fov", "17", f"--box={PLAN_BOX}"], forced or "plan_ortho")
        else:
            run(["0.5,1.2,0.0", "0.5,-1,0.0", "--up=0,0,-1", "--fov", "90", f"--box={PLAN_BOX}"], forced or "plan_fov90")
        return

    # 2) explicit eye/look ------------------------------------------------------
    if "look" in opt:
        run([eye, opt["look"], "--fov", fov], forced or "shot")
        return

    # 3) compass heading (name or degrees) from the standpoint ------------------
    if word is None:
        print("say a direction (north/e/135), 'plan', or eye=..,look=..  (see --help)"); return
    deg = COMPASS[word.lower()] if word.lower() in COMPASS else float(word)
    ex, ey, ez = vec(eye)
    r = math.radians(deg)
    look = f"{ex + 3*math.sin(r):.3f},{ey},{ez - 3*math.cos(r):.3f}"   # 0=N(-z), 90=E(+x)
    name = word.lower() if word.lower() in COMPASS else f"deg{int(deg)}"
    run([eye, look, "--fov", fov], forced or name)

if __name__ == "__main__":
    main()
