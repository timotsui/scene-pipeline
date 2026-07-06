"""entangled_gen adapter — one stable interface over swappable text->splat backends.

Downstream (`splat_to_placement`) imports ONLY `generate`. Which generator runs
is an implementation detail behind `backend`. Each backend produces a raw 3DGS
`.ply`; the adapter then canonicalizes it into the frame the placement pipeline
expects (see `_canonicalize`).

Backends:
  - "scenedreamer360" : PanFusion panorama -> enhance -> point-cloud-fusion 3DGS
  - "fastscene"       : Diffusion360 panorama -> PNVI/CVS -> OpenMVG MVP -> 3DGS

Neither backend is wired to run in-process yet: both are heavy conda/CUDA repos
driven by their own CLIs in WSL. `generate` shells out to the per-backend runner
scripts under `runners/` (thin wrappers that activate the right env and call the
repo's entrypoint), then normalizes the output. Runners are added as each repo's
environment comes online.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent
RUNNERS = REPO_ROOT / "runners"

BACKENDS = {"scenedreamer360", "fastscene"}


def generate(prompt: str, out_ply: Path, backend: str = "scenedreamer360",
             seed: int = 1, calibrate: bool = True) -> Path:
    """Text prompt -> canonicalized 3DGS .ply of an entangled room scene.

    Returns the path to the final .ply (== out_ply). Raises if the backend is
    unknown or its runner is not yet available.
    """
    if backend not in BACKENDS:
        raise ValueError(f"unknown backend {backend!r}; choose from {sorted(BACKENDS)}")

    out_ply = Path(out_ply)
    out_ply.parent.mkdir(parents=True, exist_ok=True)

    runner = RUNNERS / f"run_{backend}.sh"
    if not runner.exists():
        raise NotImplementedError(
            f"runner {runner} not created yet — backend env not online. "
            f"See README.md 'Status'."
        )

    raw_ply = out_ply.with_suffix(".raw.ply")
    # Runners take (prompt, out_raw_ply, seed) and drive the repo CLI inside WSL.
    subprocess.run(
        ["wsl", "-d", "Ubuntu-24.04", "-e", "bash", str(runner),
         prompt, _wslpath(raw_ply), str(seed)],
        check=True,
    )

    if calibrate:
        _canonicalize(raw_ply, out_ply, backend)
    else:
        raw_ply.replace(out_ply)
    return out_ply


def _canonicalize(raw_ply: Path, out_ply: Path, backend: str) -> None:
    """Map a raw 3DGS ply into the frame `splat_to_placement` expects.

    OPEN CALIBRATION (see README): week5 hit the PlayCanvas Y-up vs 3DGS Y-down
    transform. These repos emit standard 3DGS; the exact axis map must be
    verified per-backend against the first real output via:
        splat-transform <raw_ply> --summary
    then apply the estimated up-vector / floor-plane / metric-scale
    canonicalization used in splat_to_placement (generic, source-agnostic).

    Until verified on a real .ply, pass through untouched and flag loudly so we
    never silently feed a mis-framed splat downstream.
    """
    raise NotImplementedError(
        f"[{backend}] coord calibration unverified — run "
        f"`splat-transform {raw_ply} --summary`, confirm the axis map against "
        f"splat_to_placement, then implement _canonicalize. Do NOT skip: a "
        f"mis-framed splat silently breaks plan-view + placement."
    )


def _wslpath(p: Path) -> str:
    """Windows path -> /mnt/... path for the WSL side."""
    out = subprocess.run(["wsl", "-d", "Ubuntu-24.04", "-e", "wslpath", "-a", str(p)],
                         capture_output=True, text=True, check=True)
    return out.stdout.strip()


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="text -> entangled room splat")
    ap.add_argument("prompt")
    ap.add_argument("out_ply", type=Path)
    ap.add_argument("--backend", default="scenedreamer360", choices=sorted(BACKENDS))
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--no-calibrate", action="store_true")
    a = ap.parse_args()
    path = generate(a.prompt, a.out_ply, a.backend, a.seed, calibrate=not a.no_calibrate)
    print(f"wrote {path}")
