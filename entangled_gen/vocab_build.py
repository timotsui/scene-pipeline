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
import hashlib
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

#: Bump on ANY change to the four prompts below. It is salted into every
#: cache key, so an edited prompt re-asks instead of serving an answer to
#: a question that is no longer being asked. Same rule the judges use
#: (graph/judge_pairs.py, graph/triage_pairs.py).
PROMPT_VERSION = "1"


# ==========================================================================
# THE CACHES — this stage was the funnel's most expensive, and had none
# ==========================================================================
#
# Measured on the first fresh scene (2026-08-11): `vocab` took 293.5 s of
# an 872.7 s funnel — 34%, the single most expensive stage — across four
# model calls. A bare call round-trips in ~3 s, so almost none of that is
# process overhead; it is the model thinking. And NOTHING was cached, so
# every re-run of a scene paid the full 293 s for a byte-identical answer.
#
# TWO CACHES, BECAUSE THERE ARE TWO KINDS OF QUESTION HERE, and conflating
# them would either leak one room's answer into another or throw away the
# reuse that matters.
#
#   SHARED, ACROSS EVERY SCENE — the three TEXT legs. "Is 'ladder' a
#   concrete object?", "what else is a ladder called?", "does 'ladder'
#   denote something visible?" None of those depend on the room. Keyed
#   PER TERM, which is the load-bearing detail: measured across three
#   genuinely different rooms, 31-48% of terms are shared and 66% of all
#   distinct terms appear in more than one room, so a per-term cache
#   starts paying on scene two and approaches that 66% ceiling as the
#   ordinary furniture vocabulary saturates.
#   ⚠ NOT keyed on the whole list. scene_scale.py caches by hashing its
#   sorted label list, which is right there (one prior per scene) and
#   would be near-useless here: no two rooms have the same word list, so
#   a whole-list key would hit ~never.
#
#   PER SCENE — the pano look-pass, which reads THIS room's photograph.
#   Keyed on the image's content hash, so it survives re-runs (this
#   scene's funnel was re-run four times today) and correctly re-asks if
#   the pano is ever re-rendered.
#
#: Shared cache, deliberately at the OUT root rather than in any scene.
TERM_CACHE = paths.OUT / "vocab_term_cache.json"


def _load_term_cache():
    """The shared per-term answers, or an empty book. A cache written
    under a different PROMPT_VERSION is DISCARDED, not migrated."""
    if TERM_CACHE.exists():
        try:
            d = json.loads(TERM_CACHE.read_text(encoding="utf-8"))
            if isinstance(d, dict) and d.get("prompt_version") == PROMPT_VERSION:
                for k in ("concrete", "synonym", "imageword"):
                    d.setdefault(k, {})
                return d
        except (ValueError, OSError):
            pass                       # unreadable cache is a cold cache
    return {"prompt_version": PROMPT_VERSION,
            "concrete": {}, "synonym": {}, "imageword": {}}


def _save_term_cache(cache):
    """Persist, MERGING under whatever is on disk now.

    run_fleet runs scenes one at a time, so this is not a hot race — but
    a plain overwrite would silently drop another run's entries, and a
    cache that loses answers is worse than no cache because the loss is
    invisible. Merge-then-write costs nothing."""
    disk = _load_term_cache()
    for bucket in ("concrete", "synonym", "imageword"):
        merged = dict(disk.get(bucket) or {})
        merged.update(cache.get(bucket) or {})
        cache[bucket] = merged
    try:
        TERM_CACHE.parent.mkdir(parents=True, exist_ok=True)
        paths.write_atomic(TERM_CACHE, json.dumps(cache, indent=1))
    except OSError as e:               # noqa: BLE001
        print(f"[vocab] could not write the shared term cache ({e}) — "
              f"this run still worked, the next one just re-asks")


def _cached_ask(cache, bucket, terms, ask, default):
    """Answers for every term, asking only about the ones not on file.

    `ask(missing)` returns {term: answer} and may raise — the caller owns
    degradation, exactly as it did before there was a cache. Returns
    (answers, n_asked) so the log can say how much the cache saved."""
    book = cache.setdefault(bucket, {})
    missing = [t for t in terms if t not in book]
    if missing:
        got = ask(missing)
        for t in missing:
            book[t] = got.get(t, default)
    return {t: book[t] for t in terms if t in book}, len(missing)

VLM_PROMPT = """Read the image file(s) at the following absolute path(s), then list every distinct TYPE of object visible in them (they show one indoor room).

{files}

Rules:
- lowercase singular common nouns, generic type names only ("desk lamp", not "brass vintage lamp")
- include furniture, appliances, decor, and small movable objects
- EXCLUDE room structure (wall, floor, ceiling), materials, colors, styles, lighting effects, and people
- one entry per TYPE (one "book" even if many books are visible)
- output ONLY the comma-separated list on a single line, nothing else"""

CONCRETE_PROMPT = """From this list of terms mined from a room-description prompt, keep ONLY the ones that name a concrete physical OBJECT or FIXTURE one could point at in a room (furniture, appliances, decor, openings like door/window). Drop abstractions (elegance, warmth, focus), materials, styles, qualities, effects, and spatial/scene words (view, line, color palette).

{terms}

Output ONLY the kept terms as a comma-separated list on a single line, nothing else."""

# Detector-friendly phrasing pass (2026-08-06): open-vocab detectors respond
# to common caption words — formal terms can fail where casual ones fire
# ("painting" fires where "picture" doesn't, 07-26; a formal-only term can
# miss its object entirely). Same doctrine as the concreteness pass: cheap
# LLM judgment applied to EVERY term, never a curated list, no scene
# knowledge. Alternatives ride the query set in different batches (the
# round-robin) and map back to their canonical term via vocab.json.
SYNONYM_PROMPT = """You write alternative query words for an open-vocabulary object detector. Detectors respond to common caption words; formal terms can fail where casual ones fire. For each term below, give up to 2 alternative words/phrases a photo captioner would commonly use for the SAME type of object in an indoor photo (e.g. a formal term's everyday word, or a very common variant). Skip terms that need no alternative. NEVER output a broader category, a part, or a different object — only true same-object alternative names. NEVER output a word that could be read as denoting the image itself rather than an object in it (e.g. "photo", "image", "shot", "view", "scene" — such queries make the detector box the whole frame); prefer an unambiguous compound instead ("picture frame", not "photo").

{terms}

Output ONLY lines of the form "term: alt1, alt2" for terms that have alternatives, nothing else."""

# Query-side screen (2026-08-06, living scene #2): a query word that can
# denote the PHOTOGRAPH ITSELF ("photo" -> the detector boxed the entire
# crop, 20/31 degenerate detections) is removed from the DETECTOR QUERIES
# only — canonical vocab and label-mapping keep it, so any detector output
# still canonicalizes. Same doctrine as the concreteness pass: cheap LLM
# judgment over every term, never a curated list. Degrades conservatively:
# judge unavailable -> queries unchanged (the lift's whole-frame guard is
# the second line of defense).
IMAGE_WORD_PROMPT = """An open-vocabulary object detector is given query words and finds matching regions in an indoor photo. A query word that can be read as denoting the PHOTOGRAPH ITSELF rather than an object inside the room (like "photo", "image", "picture", "view") makes the detector box the entire image. From this list, output ONLY the terms with that failure mode, as a comma-separated list on a single line. If none, output exactly NONE.

{terms}"""


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
    # old manual bundles: "<title>_pano.png"; harvest bundles: pano_rgb_0.png
    panos = (sorted(bundle_dir.glob("*pano*.png"))
             + sorted(bundle_dir.glob("*pano*.jpg")))
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
    term_cache = _load_term_cache()
    pano_cache_f = sdir / "vocab_pano_cache.json"
    if not args.skip_vlm:
        pano = find_pano(sc)
        if pano:
            # PER-SCENE, KEYED ON THE IMAGE'S CONTENT. This answer is
            # about THIS room, so it cannot be shared — but it is also
            # the same answer every time the same picture is read, and
            # this scene's funnel was re-run four times on 08-11. The key
            # is the file's hash, not its path, so a re-rendered pano
            # correctly re-asks.
            key = (hashlib.sha256(pano.read_bytes()).hexdigest()[:16]
                   + "|" + PROMPT_VERSION)
            cached = None
            if pano_cache_f.exists():
                try:
                    pc = json.loads(pano_cache_f.read_text(encoding="utf-8"))
                    cached = pc.get(key)
                except (ValueError, OSError):
                    cached = None
            if cached is not None:
                pano_terms = cached
                print(f"[vlm] pano -> {len(pano_terms)} raw terms (cache hit, "
                      f"0 calls)")
            else:
                # cwd = the pano's own dir: claude -p auto-allows reads
                # only under its working directory (the frames calls use
                # sdir for the same reason — job frames live inside the
                # scene folder)
                raw = call_claude(VLM_PROMPT.format(files=f'"{pano}"'),
                                  pano.parent)
                pano_terms = parse_list(raw)
                vlm_calls += 1
                try:
                    paths.write_atomic(pano_cache_f,
                                       json.dumps({key: pano_terms}, indent=1))
                except OSError:
                    pass               # a missed cache costs time, not truth
                print(f"[vlm] pano -> {len(pano_terms)} raw terms")
            images_used.append(str(pano))
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
    # Concreteness pass on the PROMPT leg only (2026-08-06, scene #2:
    # flowery prompts leak abstractions — "elegance", "warmth", "sense" —
    # through the noun funnel; doctrine fix = cheap LLM judgment, never a
    # curated list). Image legs skip it: a VLM only names what it sees.
    # Degrades conservatively: judge unavailable -> keep everything.
    dropped_abstract = []
    if A and not args.skip_vlm:
        try:
            def _ask_concrete(missing):
                raw = call_claude(
                    CONCRETE_PROMPT.format(terms=", ".join(missing)), sdir)
                keep = set(parse_list(raw))
                return {t: (t in keep) for t in missing}

            ans, asked = _cached_ask(term_cache, "concrete", A,
                                     _ask_concrete, True)
            if asked:
                vlm_calls += 1         # this leg never counted itself before
            dropped_abstract = [t for t in A if not ans.get(t, True)]
            A = [t for t in A if ans.get(t, True)]
            print(f"[vlm] concreteness: kept {len(A)}  dropped "
                  f"{dropped_abstract}  ({asked} asked, "
                  f"{len(ans) - asked} from cache)")
        except Exception as e:  # noqa: BLE001
            print(f"[vlm] concreteness pass unavailable ({e}) — keeping all")
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

    # ---- detector-friendly phrasing pass (generic, every term) ----
    # Degrades conservatively: judge unavailable -> no alternatives.
    llm_syn = {}
    if final and not args.skip_vlm:
        try:
            def _ask_synonyms(missing):
                raw = call_claude(
                    SYNONYM_PROMPT.format(terms=", ".join(missing)), sdir)
                got = {t: [] for t in missing}
                asked = set(missing)
                for ln in raw.splitlines():
                    if ":" not in ln:
                        continue
                    term, alts = ln.split(":", 1)
                    term = term.strip().lower().lstrip("-• ").strip('"')
                    if term not in asked:
                        continue
                    got[term] = [a.strip().lower()
                                 for a in alts.split(",") if a.strip()]
                return got

            ans, asked = _cached_ask(term_cache, "synonym", final,
                                     _ask_synonyms, [])
            if asked:
                vlm_calls += 1
            # THE ACCEPTANCE RULES STAY OUT OF THE CACHE. What is stored
            # is the model's raw answer per term; whether an alternative
            # SURVIVES depends on this scene's own `prov` and on what
            # other alternatives were already taken, so it must be
            # recomputed per scene or one room's vocabulary would decide
            # another's.
            for term in final:
                for alt in ans.get(term) or []:
                    if (alt and alt not in prov and alt not in STOP
                            and alt not in llm_syn and len(alt.split()) <= 4):
                        llm_syn[alt] = term
            print(f"[vlm] detector synonyms ({len(llm_syn)}) "
                  f"[{asked} asked, {len(ans) - asked} from cache]: "
                  + (", ".join(f"{a}->{t}" for a, t in llm_syn.items()) or "-"))
        except Exception as e:  # noqa: BLE001
            print(f"[vlm] synonym pass unavailable ({e}) — none added")

    q_terms = expand_terms(final)
    q_terms += [s for s in llm_syn if s not in q_terms]

    # ---- image-denoting-word screen over the FINAL query list ----
    query_dropped = []
    if q_terms and not args.skip_vlm:
        try:
            def _ask_imageword(missing):
                raw = call_claude(
                    IMAGE_WORD_PROMPT.format(terms=", ".join(missing)), sdir)
                lines = [ln.strip() for ln in raw.splitlines() if ln.strip()]
                last = lines[-1] if lines else "NONE"
                if last.strip().upper() == "NONE":
                    return {t: False for t in missing}
                flagged = {t.strip().lower()
                           for t in last.split(",") if t.strip()}
                return {t: (t in flagged) for t in missing}

            ans, asked = _cached_ask(term_cache, "imageword", q_terms,
                                     _ask_imageword, False)
            if asked:
                vlm_calls += 1
            query_dropped = [t for t in q_terms if ans.get(t)]
            q_terms = [t for t in q_terms if not ans.get(t)]
            print(f"[vlm] image-word screen dropped from queries: "
                  f"{query_dropped or '-'}  ({asked} asked, "
                  f"{len(ans) - asked} from cache)")
        except Exception as e:  # noqa: BLE001
            print(f"[vlm] image-word screen unavailable ({e}) — queries unchanged")

    out = {
        "scene": sc,
        "sources": {"prompt_raw": prompt_terms, "pano_raw": pano_terms,
                    "frames_raw": frame_terms,
                    "prompt": A, "pano": P, "frames": F},
        "canonical": {t: prov[t] for t in final},
        "diff": {"image_only (generator improvisation)": image_only,
                 "prompt_only (asked for, check if generated)": prompt_only,
                 "dropped_abstract (concreteness pass)": dropped_abstract,
                 "query_dropped_image_words (image-word screen)": query_dropped},
        "synonyms": llm_syn,
        "queries": {
            "gdino": ". ".join(q_terms) + ".",
            "owlv2": ", ".join(q_terms),
        },
        "meta": {"model": MODEL, "vlm_calls": vlm_calls,
                 "images": images_used,
                 "built": time.strftime("%Y-%m-%d %H:%M:%S")},
    }
    # PERSIST THE SHARED BOOK BEFORE THE OUTPUT, so a crash writing
    # vocab.json still banks the answers this run paid for.
    _save_term_cache(term_cache)
    vf = sdir / "vocab.json"
    paths.write_atomic(vf, json.dumps(out, indent=2))

    print(f"\n=== vocab.json written: {vf}")
    print(f"\nPROMPT ({len(A)}): {', '.join(A) or '-'}")
    print(f"\nPANO ({len(P)}): {', '.join(P) or '-'}")
    print(f"\nFRAMES ({len(F)}): {', '.join(F) or '-'}")
    print(f"\nFINAL UNION ({len(final)}): {', '.join(final)}")
    print(f"\nIMAGE-ONLY (improvisation): {', '.join(image_only) or '-'}")
    print(f"PROMPT-ONLY (verify generated): {', '.join(prompt_only) or '-'}")


if __name__ == "__main__":
    main()
