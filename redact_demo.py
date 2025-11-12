import re, json, pathlib
import spacy
from langdetect import detect

# Load NER model
nlp = spacy.load("en_core_web_sm")

# India-specific regex patterns
PATTERNS = {
    "AADHAAR": re.compile(r'\b(?:\d{4}\s?\d{4}\s?\d{4}|\d{12})\b'),
    "PAN": re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b'),
    "PHONE": re.compile(r'\b(?:\+91[\-\s]?|0)?[6-9]\d{9}\b'),
    "PIN": re.compile(r'\b\d{6}\b'),
    "EMAIL": re.compile(r'\b[\w\.-]+@[\w\.-]+\.\w{2,}\b', re.I)
}


def rule_mask(text, level):
    """Rule-based masking for obvious patterns."""
    out = text
    out = PATTERNS["AADHAAR"].sub("[REDACTED]", out)
    out = PATTERNS["PAN"].sub("[REDACTED]", out)
    out = PATTERNS["PHONE"].sub("[REDACTED]", out)
    out = PATTERNS["PIN"].sub("[REDACTED]", out)
    out = PATTERNS["EMAIL"].sub("[REDACTED]", out)
    return out


def ner_mask(text, level):
    """NER-based masking for contextual entities."""
    doc = nlp(text)
    out = text
    spans = []
    for ent in doc.ents:
        if ent.label_ in ("PERSON", "ORG"):  # keep it tighter to avoid false positives
            spans.append((ent.start_char, ent.end_char))
    spans = sorted(spans, reverse=True)
    for s, e in spans:
        out = out[:s] + "[REDACTED]" + out[e:]
    return out


def redact(text, level):
    text = rule_mask(text, level)
    text = ner_mask(text, level)
    return text


def main():
    dpath = pathlib.Path("rtis")
    outdir = pathlib.Path("outputs")
    outdir.mkdir(exist_ok=True)
    examples = sorted(dpath.glob("*.txt"))  # can replace with a single file for demo
    results = []
    preds = {}

    for p in examples:
        text = p.read_text(encoding="utf-8")
        lang = detect(text)
        print(f"{p.name}: detected language -> {lang}")

        # --- Create redacted versions ---
        for level in ("light", "medium", "strong"):
            red = redact(text, level)
            out_file = outdir / f"{p.stem}_{level}.txt"
            out_file.write_text(red, encoding="utf-8")

        # --- Collect regex + NER spans for evaluation ---
        spans = []
        # regex spans
        for label, pat in PATTERNS.items():
            for m in pat.finditer(text):
                spans.append({"start": m.start(), "end": m.end(), "label": label})

        # NER spans with label mapping
        doc = nlp(text)
        LABEL_MAP = {"GPE": "LOC", "LOC": "LOC", "PERSON": "PERSON", "ORG": "ORG"}
        for ent in doc.ents:
            if ent.label_ in ("PERSON", "ORG"):
                label = LABEL_MAP.get(ent.label_, ent.label_)
                spans.append({"start": ent.start_char, "end": ent.end_char, "label": label})

        # --- Remove duplicates / overlaps ---
        unique = []
        for s in spans:
            if not any(abs(s["start"] - u["start"]) < 3 and s["label"] == u["label"] for u in unique):
                unique.append(s)
        preds[p.name] = unique

        # --- Regex presence log ---
        found = {k: bool(v.search(text)) for k, v in PATTERNS.items()}
        results.append({"file": p.name, "found": found})

    # --- Save predictions for evaluation ---
    with open("preds.json", "w", encoding="utf-8") as f:
        json.dump(preds, f, ensure_ascii=False, indent=2)

    print(json.dumps(results, indent=2))
    print("\n✅ Redacted files saved in 'outputs/' folder!")
    print("✅ Predictions saved to preds.json for evaluation.")


if __name__ == "__main__":
    main()
