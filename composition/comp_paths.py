"""Shared locations + entangled_gen interop for the composition module."""
import importlib.util
import sys
from pathlib import Path

HERE = Path(__file__).parent
EG = HERE.parent / "entangled_gen"
sys.path.insert(0, str(EG))
import paths  # noqa: E402  (entangled_gen's paths.py: scene dirs from local_paths.json)

OBJATHOR = Path("D:/T/Documents/GeorgiaTech/Summer2026/Research/objathor-assets/2023_09_23")
ANNOTATIONS = OBJATHOR / "annotations.json.gz"
ASSETS = OBJATHOR / "assets"

BRIDGE_DIR = Path("C:/Users/T/AppData/Local/Temp/treesearch_claude_bridge")

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
