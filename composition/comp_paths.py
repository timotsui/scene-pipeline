"""Shared locations + entangled_gen interop for the composition module.

The ONLY sanctioned cross-module code edge: composition reaches entangled_gen
exclusively through this file (the `import paths` below). Machine-local roots
come from entangled_gen/local_paths.json (gitignored — see the .example);
no machine-specific paths live in code.
"""
import shutil
import sys
import tempfile
from pathlib import Path

HERE = Path(__file__).parent
EG = HERE.parent / "entangled_gen"
sys.path.insert(0, str(EG))
import paths  # noqa: E402  (entangled_gen's paths.py: scene dirs from local_paths.json)


def _require(key):
    try:
        return Path(paths.CFG[key])
    except KeyError:
        raise SystemExit(
            f"entangled_gen/local_paths.json is missing '{key}' — add it "
            f"(see local_paths.json.example)") from None


OBJATHOR = _require("objathor")
ANNOTATIONS = OBJATHOR / "annotations.json.gz"
ASSETS = OBJATHOR / "assets"
MESH_YAW = OBJATHOR / "_thumbs" / "_mesh_yaw.json"   # measure.py canonical-yaw cache
MESH_FIXUPS = OBJATHOR / "_thumbs" / "_mesh_fixups.json"   # curated per-uid cleanups

# claude.exe bridge (bridge.py): scratch dir + binary, both config-overridable
BRIDGE_DIR = Path(paths.CFG.get("bridge_dir")
                  or Path(tempfile.gettempdir()) / "treesearch_claude_bridge")
CLAUDE_EXE = str(paths.CFG.get("claude_exe") or shutil.which("claude")
                 or Path.home() / ".local" / "bin" / "claude.exe")


def load_r3():
    return paths.load_r3()


def scene_prompt_file(sc):
    """The generation prompt behind a scene (bundle_path.txt -> <bundle>/prompt.txt)."""
    bp = paths.scene_dir(sc) / "bundle_path.txt"
    if bp.exists():
        cand = Path(bp.read_text().strip()) / "prompt.txt"
        if cand.exists():
            return cand
    return None
