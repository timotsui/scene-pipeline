"""Detection vocabulary builder — the closing module of 2.1 OBSERVE.

Two sources, decided 2026-07-25 (the hardcoded per-room dict is retired):
  A. INTENT      — mine the generation prompt (vocab_from_prompt machinery).
  B. OBSERVATION — mine the raw generation images with a fast VLM
                   (claude.exe, subscription): the bundle pano when one
                   exists + a spread of analyzer sweep frames.

Combine: canonicalize every term from every source to one term per concept
(same NORMALIZE/STOP funnel as the prompt path), union with provenance
tags, and emit per-detector query strings (GroundingDINO period-separated
with EXPAND synonyms; OWLv2 comma-separated). The provenance diff is a
free diagnostic: prompt-only terms = asked for but maybe not generated;
image-only terms = generator improvisation the prompt never named.

  python vocab_build.py --scene bedroom_marble
  python vocab_build.py --scene bedroom_marble --skip-vlm   (prompt side only)

Writes OUT/<scene>/vocab.json and prints every per-source list for review.
"""
import argparse
import json
import math
import os
import shutil
import subprocess
import time
from pathlib import Path

import paths
from vocab_from_prompt import (STOP, STAPLES, bundle_prompt_file, canonicalize,
                               expand_terms, extract_vocab)

MODEL = "haiku"            # fast + cheap; open-source tagger is the someday-swap
CALL_TIMEOUT_S = 240
FRAMES_PER_CALL = 4        # images per VLM call (keeps each call attentive)
N_SWEEP_FRAMES = 8         # one level-elevation frame per standpoint

VLM_PROMPT = """Read the image file(s) at the following absolute path(s), then list every distinct TYPE of object visible in them (they show one indoor room).

{files}

Rules:
- lowercase singular common nouns, generic type names only ("desk lamp", not "brass vintage lamp")
- include furniture, appliances, decor, and small movable objects
- EXCLUDE room structure (wall, floor, ceiling), materials, colors, styles, lighting effects, and people
- one entry per TYPE (one "book" even if many books are visible)
- output ONLY the comma-separated list on a single line, nothing else"""


# ---------------- VLM bridge (claude.exe, same contract as describe_nodes) --

def claude_env():
    env = dict(os.environ)
    for k in ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"):
        env.pop(k, None)   # stale-API-key hijack gotcha (project memory)
    return env


def call_claude(prompt, cwd):
    exe = shutil.which("claude")
    if not exe:
        raise SystemExit("[vocab] claude(.exe) not on PATH")
    r = subprocess.run([exe, "-p", prompt, "--model", MODEL],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=claude_env(), cwd=str(cwd),
                       timeout=CALL_TIMEOUT_S)
    out = (r.stdout or "").strip()
    err = (r.stderr or "").strip()
    if r.returncode != 0:
        raise RuntimeError(f"claude exit {r.returncode}: {err[:400] or out[:400]}")
    low = (out + " " + err).lower()
    for bad in ("invalid_api_key", "authentication_error", "credit balance"):
        if bad in low:
            raise RuntimeError(f"claude API-billing/auth error: {out[:400]}")
    return out


def parse_list(raw):
    """Last non-empty line -> comma-split terms (tolerates VLM preamble)."""
    lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
    if not lines:
        return []
    best = max(lines, key=lambda ln: ln.count(","))   # the list line
    terms = [t.strip().lower().rstrip(".") for t in best.split(",") if t.strip()]
    # a real term is short; sentences (permission pleas, refusals) are not
    return [t for t in terms if 0 < len(t.split()) <= 4]


# ---------------- image selection -------------------------------------------

def pick_sweep_frames(job_dir, n=N_SWEEP_FRAMES):
    """One level-elevation frame per standpoint, azimuths staggered."""
    t = json.loads((job_dir / "transforms.json").read_text())
    per_pos = {}
    for f in t["frames"]:
        m = f["transform_matrix"]
        fx, fy, fz = m[0][2], m[1][2], m[2][2]
        el = math.degrees(math.asin(max(-1.0, min(1.0, -fy))))
        if abs(el) > 20:                      # keep the "level" row only
            continue
        az = (math.degrees(math.atan2(fx, fz)) + 360.0) % 360.0
        per_pos.setdefault(f["position_idx"], []).append((az, f["file_path"]))
    picks = []
    for i in sorted(per_pos):
        want = (i * 360.0 / max(1, len(per_pos))) % 360.0   # stagger headings
        az, fp = min(per_pos[i], key=lambda p: min(abs(p[0] - want),
                                                   360 - abs(p[0] - want)))
        picks.append(job_dir / fp)
    return picks[:n]


def find_pano(scene):
    bp = paths.scene_dir(scene) / "bundle_path.txt"
    if not bp.exists():
        return None
    p = Path(bp.read_text().strip())
    bundle_dir = p if p.is_dir() else p.parent
    panos = sorted(bundle_dir.glob("*_pano.png")) + sorted(bundle_dir.glob("*pano*.jpg"))
    return panos[0] if panos else None


# ---------------- combine ---------------------------------------------------

def funnel(terms, known):
    """Raw terms -> canonical, stoplisted, deduped (order kept)."""
    out = []
    for t in terms:
        c = canonicalize(t, vocab=known) or t
        if c in STOP or not c:
            continue
        if c not in out:
            out.append(c)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--job", default="", help="analyzer job dir name (default: newest job_*)")
    ap.add_argument("--skip-vlm", action="store_true")
    args = ap.parse_args()
    sc = args.scene
    sdir = paths.scene_dir(sc)

    # ---- source A: intent (generation prompt) ----
    pf = bundle_prompt_file(sc)
    prompt_text = pf.read_text(encoding="utf-8", errors="replace") if pf and pf.exists() else ""
    prompt_terms = extract_vocab(prompt_text) if prompt_text else []
    known = set(prompt_terms) | set(STAPLES)

    # ---- source B: observation (pano + sweep frames via VLM) ----
    pano_terms, frame_terms, images_used, vlm_calls = [], [], [], 0
    if not args.skip_vlm:
        pano = find_pano(sc)
        if pano:
            # cwd = the pano's own dir: claude -p auto-allows reads only
            # under its working directory (the frames calls use sdir for
            # the same reason — job frames live inside the scene folder)
            raw = call_claude(VLM_PROMPT.format(files=f'"{pano}"'), pano.parent)
            pano_terms = parse_list(raw)
            images_used.append(str(pano)); vlm_calls += 1
            print(f"[vlm] pano -> {len(pano_terms)} raw terms")
        base = sdir / "analyzer"
        jobs = ([base / args.job] if args.job else
                sorted((d for d in base.glob("job_*") if (d / "transforms.json").exists()),
                       key=lambda d: (d / "transforms.json").stat().st_mtime, reverse=True))
        if jobs and jobs[0].exists():
            frames = pick_sweep_frames(jobs[0])
            for i in range(0, len(frames), FRAMES_PER_CALL):
                chunk = frames[i:i + FRAMES_PER_CALL]
                files = "\n".join(f'"{p}"' for p in chunk)
                raw = call_claude(VLM_PROMPT.format(files=files), sdir)
                frame_terms += parse_list(raw)
                images_used += [str(p) for p in chunk]; vlm_calls += 1
                print(f"[vlm] frames {i}-{i+len(chunk)-1} -> {len(frame_terms)} raw terms so far")

    # ---- combine: canonical union with provenance ----
    A = funnel(prompt_terms, known)
    P = funnel(pano_terms, known)
    F = funnel(frame_terms, known)
    prov = {}
    for src, terms in (("prompt", A), ("pano", P), ("frames", F)):
        for t in terms:
            prov.setdefault(t, []).append(src)
    for st in STAPLES:                       # cheap universal indoor staples
        prov.setdefault(st, []).append("staple")
    final = list(prov)
    image_only = [t for t, s in prov.items() if "prompt" not in s and s != ["staple"]]
    prompt_only = [t for t, s in prov.items() if s == ["prompt"]]

    out = {
        "scene": sc,
        "sources": {"prompt_raw": prompt_terms, "pano_raw": pano_terms,
                    "frames_raw": frame_terms,
                    "prompt": A, "pano": P, "frames": F},
        "canonical": {t: prov[t] for t in final},
        "diff": {"image_only (generator improvisation)": image_only,
                 "prompt_only (asked for, check if generated)": prompt_only},
        "queries": {
            "gdino": ". ".join(expand_terms(final)) + ".",
            "owlv2": ", ".join(expand_terms(final)),
        },
        "meta": {"model": MODEL, "vlm_calls": vlm_calls,
                 "images": images_used,
                 "built": time.strftime("%Y-%m-%d %H:%M:%S")},
    }
    vf = sdir / "vocab.json"
    vf.write_text(json.dumps(out, indent=2), encoding="utf-8")

    print(f"\n=== vocab.json written: {vf}")
    print(f"\nPROMPT ({len(A)}): {', '.join(A) or '-'}")
    print(f"\nPANO ({len(P)}): {', '.join(P) or '-'}")
    print(f"\nFRAMES ({len(F)}): {', '.join(F) or '-'}")
    print(f"\nFINAL UNION ({len(final)}): {', '.join(final)}")
    print(f"\nIMAGE-ONLY (improvisation): {', '.join(image_only) or '-'}")
    print(f"PROMPT-ONLY (verify generated): {', '.join(prompt_only) or '-'}")


if __name__ == "__main__":
    main()
