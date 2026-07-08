"""Open-ended object tagging of the pano crops (WEEK8_OBJECT_ID_PLAN stage 1,
the observation half of the vocab: "what did the generator actually build?").

Florence-2 <OD> (no vocabulary needed — it names what it sees) over every
crop; names are lemma-normalized, stoplist-filtered, and unioned with the
prompt-derived vocab. The output is a WORD LIST — localization stays
GroundingDINO+SAM's job (one detector, one convention, one merge).

Generic: for marble scenes this tops up prompt.txt; for backends with no
prompt bundle it is the PRIMARY name source (run on views/ via --crops-dir).

  python tag_crops.py --scene bedroom_marble            # tags + union printed
  python tag_crops.py --scene bedroom_marble --tags-only

Outputs: out/<scene>/seg_pano/tags.json  {name: n_crops_seen}
Stdout last line: the combined GroundingDINO prompt string.
"""
import argparse, json
from collections import Counter
from pathlib import Path
import torch
from PIL import Image

import paths
from vocab_from_prompt import (STOP, NORMALIZE, extract_vocab,
                               bundle_prompt_file, expand_terms)

# the florence-community conversions are the transformers-5.x-native format
# (microsoft/'s hub repo ships stale remote code that breaks on 5.x)
MODEL = "florence-community/Florence-2-base"


def load_florence():
    from transformers import AutoProcessor, Florence2ForConditionalGeneration
    proc = AutoProcessor.from_pretrained(MODEL)
    model = Florence2ForConditionalGeneration.from_pretrained(
        MODEL, torch_dtype=torch.float16).to("cuda").eval()
    return proc, model


def tag_image(proc, model, img, task="<OD>"):
    inputs = proc(text=task, images=img, return_tensors="pt").to("cuda", torch.float16)
    with torch.no_grad():
        ids = model.generate(input_ids=inputs["input_ids"],
                             pixel_values=inputs["pixel_values"],
                             max_new_tokens=512, num_beams=3, do_sample=False)
    text = proc.batch_decode(ids, skip_special_tokens=False)[0]
    res = proc.post_process_generation(text, task=task, image_size=img.size)
    return res.get(task, {}).get("labels", [])


def normalize_names(names, nlp):
    """lowercase, singular head lemma, stoplist + NORMALIZE — same rules as
    the prompt vocab so the union is consistent."""
    out = []
    for name in names:
        name = name.strip().lower()
        if not name or len(name) < 3:
            continue
        doc = nlp(name)
        toks = [t.lemma_.lower() for t in doc if t.pos_ in ("NOUN", "PROPN", "ADJ")]
        if not toks:
            continue
        term = " ".join(toks[-2:]) if len(toks) >= 2 else toks[0]
        # try full term, then head noun only
        for cand in (NORMALIZE.get(term, term), NORMALIZE.get(toks[-1], toks[-1])):
            if cand not in STOP and len(cand) >= 3:
                out.append(cand)
                break
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scene", required=True)
    ap.add_argument("--crops-dir", default="", help="default: out/<scene>/pano_crops")
    ap.add_argument("--glob", default="pano_*.webp")
    ap.add_argument("--min-crops", type=int, default=2,
                    help="keep a tag only if seen in >= this many crops (1-crop tags are often hallucinations)")
    ap.add_argument("--tags-only", action="store_true", help="skip the prompt-vocab union")
    a = ap.parse_args()

    crops_dir = Path(a.crops_dir) if a.crops_dir else paths.pano_crops_dir(a.scene)
    crops = sorted(crops_dir.glob(a.glob))
    print(f"tagging {len(crops)} crops with {MODEL} ...", flush=True)

    import spacy
    nlp = spacy.load("en_core_web_sm")
    proc, model = load_florence()

    seen = Counter()
    for f in crops:
        img = Image.open(f).convert("RGB")
        names = set(normalize_names(tag_image(proc, model, img), nlp))
        for n in names:
            seen[n] += 1
        print(f"  {f.stem}: {sorted(names)}", flush=True)

    tags = {n: c for n, c in seen.most_common() if c >= a.min_crops}
    dropped = {n: c for n, c in seen.items() if c < a.min_crops}
    outd = paths.seg_pano_dir(a.scene)
    outd.mkdir(parents=True, exist_ok=True)
    (outd / "tags.json").write_text(json.dumps(
        {"model": MODEL, "kept": tags, "dropped_single_crop": dropped}, indent=2))
    print(f"\nkept tags (>= {a.min_crops} crops): {tags}")
    print(f"dropped 1-crop tags: {sorted(dropped)}")

    if a.tags_only:
        return
    base = extract_vocab(bundle_prompt_file(a.scene).read_text(encoding="utf-8"))
    # drop tags whose words are a subset of an existing term ("table" when
    # "side table" is already there): the specific term finds the object, a
    # second generic label would double-detect it under a different name
    def subsumed(tag):
        tw = set(tag.split())
        return any(tw <= set(b.split()) and tag != b for b in base)
    extra = [t for t in tags if t not in base and not subsumed(t)]
    combined = expand_terms(base + extra)
    print(f"\nprompt vocab {len(base)} terms + {len(extra)} new from tags: {extra}"
          f" (+ synonym expansion -> {len(combined)})")
    print(". ".join(combined) + ".")


if __name__ == "__main__":
    main()
