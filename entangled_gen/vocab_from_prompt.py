"""Detection vocabulary from a scene's generation prompt (WEEK8_OBJECT_ID_PLAN
stage 1: "intent for searching, observation for describing").

Generic, not job-specific: works on ANY prompt.txt a bundle ships. Extraction
is spaCy noun-chunks (open vocabulary) -> compound-aware object nouns, minus a
stoplist of abstract/structural/material words that aren't detection targets,
plus a small set of indoor staples nearly every room render has. Sub-parts of
furniture (duvet, blanket) are stoplisted: detecting them fragments the parent
object at lift time — they belong to the stage-6 enrichment description.

  python vocab_from_prompt.py --scene bedroom_marble        # via bundle prompt.txt
  python vocab_from_prompt.py --prompt-file some/prompt.txt

Prints the GroundingDINO prompt string (lowercase, period-separated).
Importable: extract_vocab(text) -> [terms], gd_prompt(text) -> "a. b. c."
"""
import argparse
from pathlib import Path

import paths

# nearly-universal indoor objects, cheap to include (extra words ~ free)
STAPLES = ["door", "window", "pillow", "curtain", "ceiling light"]

# not detection targets: abstract, scene-level, materials, room parts, or
# sub-parts that would fragment their parent object
STOP = {
    # scene / abstract
    "scene", "room", "bedroom", "livingroom", "kitchen", "playroom", "study",
    "style", "tone", "atmosphere", "light", "lighting", "environment", "effect",
    "touch", "collection", "assortment", "variety", "gallery", "interior",
    "foreground", "background", "side", "area", "space", "nature", "greenery",
    "items", "item", "essentials", "essential", "mementos", "memento",
    "arrangement",
    # relative positions / geometry words, not objects
    "front", "back", "left", "right", "middle", "center", "corner", "edge",
    # structure / materials / whole-scene words
    "wall", "walls", "floor", "ceiling", "wood", "metal", "glass", "fabric",
    "house", "building", "home",
    # people are not composition assets (faces on wall art are "picture")
    "person", "people", "face", "human face", "man", "woman", "boy", "girl",
    # sub-parts of furniture (enrichment describes these, stage 6)
    "duvet", "blanket", "sheet", "cushion", "frame", "wheel", "wheels", "leg",
    "shelf top", "top",
}

# lemma fixes / normalizations for common detector-friendly terms
NORMALIZE = {
    "photograph": "picture", "photo": "picture", "art": "picture",
    "artwork": "picture", "clipping": "picture", "poster": "picture",
    "couch": "sofa", "tv": "television",
    "bookcase": "bookshelf", "houseplant": "plant", "cabinetry": "cabinet",
    "painting": "picture", "picture frame": "picture", "framed photo": "picture",
    "wall art": "picture",
}

# detector-friendly synonyms for words GroundingDINO scores poorly on its own
# ("picture" is too abstract — it can mean the whole image; "painting" hits the
# same wall art at 0.4+, verified bedroom_marble 2026-07-07). Synonyms go INTO
# the detection prompt; canonicalize() maps detected labels back.
EXPAND = {
    "picture": ["painting", "picture frame", "poster"],
}


def expand_terms(terms):
    out = list(terms)
    for t in terms:
        for s in EXPAND.get(t, []):
            if s not in out:
                out.append(s)
    return out


def canonicalize(label, vocab=None):
    """Detected label -> canonical vocab term. GroundingDINO can emit token
    concatenations ("picture frame photo", "side table desk") — match the
    longest known term contained in the label."""
    label = label.strip().lower()
    if label in NORMALIZE:
        return NORMALIZE[label]
    known = set(NORMALIZE) | (set(vocab) if vocab else set())
    if label in known:
        return NORMALIZE.get(label, label)
    best = ""
    for term in known:
        if term in label and len(term) > len(best):
            best = term
    return NORMALIZE.get(best, best) if best else label


def _spacy_nlp():
    import spacy
    try:
        return spacy.load("en_core_web_sm")
    except OSError as e:
        raise RuntimeError("spaCy model missing: python -m spacy download en_core_web_sm") from e


def extract_vocab(text, staples=True):
    """Prompt text -> ordered unique object terms (compound-aware, lemmatized)."""
    nlp = _spacy_nlp()
    doc = nlp(text)
    terms = []
    for chunk in doc.noun_chunks:
        root = chunk.root
        if root.pos_ not in ("NOUN", "PROPN"):
            continue
        # keep noun-noun compounds attached to the root ("office chair",
        # "computer monitor", "desk lamp", "air conditioner", "yoga mat")
        comps = [t for t in chunk if t.dep_ == "compound" and t.head == root]
        words = [t.lemma_.lower() for t in comps] + [root.lemma_.lower()]
        term = " ".join(words)
        term = NORMALIZE.get(term, term)
        if term in STOP or root.lemma_.lower() in STOP:
            continue
        if len(term) < 3:
            continue
        if term not in terms:
            terms.append(term)
    if staples:
        for s in STAPLES:
            if s not in terms:
                terms.append(s)
    return terms


def gd_prompt(text, staples=True):
    """GroundingDINO wants lowercase, period-separated."""
    return ". ".join(extract_vocab(text, staples)) + "."


def bundle_prompt_file(sc):
    """Scene -> its download-bundle prompt.txt via out/<scene>/bundle_path.txt
    (one line: path to the bundle folder)."""
    bp = paths.scene_dir(sc) / "bundle_path.txt"
    if not bp.exists():
        raise FileNotFoundError(f"{bp} missing — write the bundle folder path into it")
    bundle = Path(bp.read_text().strip())
    pf = bundle / "prompt.txt"
    if not pf.exists():
        raise FileNotFoundError(f"no prompt.txt in bundle {bundle}")
    return pf


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", default="")
    ap.add_argument("--prompt-file", default="")
    ap.add_argument("--no-staples", action="store_true")
    a = ap.parse_args()
    pf = Path(a.prompt_file) if a.prompt_file else bundle_prompt_file(a.scene)
    text = pf.read_text(encoding="utf-8")
    terms = expand_terms(extract_vocab(text, staples=not a.no_staples))
    print(f"# {len(terms)} terms (incl. synonym expansion) from {pf}")
    print(". ".join(terms) + ".")
