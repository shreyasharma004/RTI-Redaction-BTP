import re, json, pathlib, unicodedata
import spacy
from langdetect import detect

# Load NER model
nlp = spacy.load("en_core_web_sm")

# India-specific regex patterns (extended)
PATTERNS = {
    "FILE": re.compile(r'\b(?:File\s+No[:\s]*|File[:\s]*|File\s+)\s*([A-Za-z0-9\/\-\_\.]+)', re.I),
    "AADHAAR": re.compile(r'\b(?:\d{4}\s?\d{4}\s?\d{4}|\d{12})\b'),
    "PAN": re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b'),
    "PHONE": re.compile(r'\b(?:\+91[\-\s]?|0)?[6-9]\d{9}\b'),
    "PIN": re.compile(r'\b\d{6}\b'),
    "EMAIL": re.compile(r'\b[\w\.\+\-]+@[\w\.-]+\.\w{2,}\b', re.I),
    # passports like A1234567
    "PASSPORT": re.compile(r'\b[A-Z]\d{7}\b'),
    # voter id-ish heuristic (3 letters + 6-7 digits) - rough but helpful
    "VOTER_ID": re.compile(r'\b[A-Z]{3}\d{6,7}\b'),
    "DATE": re.compile(
    r'\b(?:'
    r'(?:0?[1-9]|[12][0-9]|3[01])[/-]'         # day 1–31
    r'(?:0?[1-9]|1[0-2])[/-]'                  # month 1–12
    r'(?:19|20)\d{2}|'                         # year 1900–2099
    r'(?:0?[1-9]|[12][0-9]|3[01])\s+'          # day
    r'(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*'   # month name
    r'\s+(?:19|20)\d{2}'                       # year
    r')\b',
    re.I
)

}

# line-based address + applicant patterns (to produce spans)
ADDR_LINE = re.compile(r'(?mi)^(?:Address|Address:|R\/o|R/O|R/o|पता|Add:|Address)\s*[:\-]?\s*(.+)$')
APPLICANT_LINE = re.compile(r'(?mi)^(?:Applicant|APPLICANT|आवेदक|APpLiCANT|Applica-nt)\s*[:\-]?\s*(.+)$')

# Normalizer helper (useful if files still have weird unicode)
def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u200c","").replace("\u200d","").replace("\ufeff","")
    s = s.replace("“",'\"').replace("”",'\"').replace("’","'").replace("‘","'")
    s = s.replace("—","-").replace("–","-")
    s = s.replace("\r\n","\n").replace("\r","\n")
    return s

def rule_mask(text, level):
    """Rule-based masking for obvious patterns."""
    out = text
    out = PATTERNS["AADHAAR"].sub("[REDACTED]", out)
    out = PATTERNS["PAN"].sub("[REDACTED]", out)
    out = PATTERNS["PHONE"].sub("[REDACTED]", out)
    out = PATTERNS["PIN"].sub("[REDACTED]", out)
    out = PATTERNS["EMAIL"].sub("[REDACTED]", out)
    # keep passport/email/pin detection intact (we mask them above via patterns)
    return out

def ner_mask(text, level):
    """NER-based masking for contextual entities (safer)."""
    doc = nlp(text)
    out = text

    spans = []

    # collect PERSON, GPE/LOC→ADDRESS (with filtering), DATE. Ignore ORG to reduce FP.
    for ent in doc.ents:
     if ent.label_ in ("PERSON", "GPE", "LOC", "DATE"):
        ent_text = text[ent.start_char:ent.end_char]

        # stricter address filter: require comma or digit or reasonably long token
        if ent.label_ in ("GPE", "LOC"):
            if ("," in ent_text) or any(c.isdigit() for c in ent_text) or len(ent_text.strip()) > 12:
                spans.append((ent.start_char, ent.end_char))

        elif ent.label_ == "DATE":
            # Accept DATE from spaCy only if it matches our strict DATE pattern
            if PATTERNS["DATE"].search(ent_text):
                spans.append((ent.start_char, ent.end_char))
        else:
            # PERSON: accept directly
            spans.append((ent.start_char, ent.end_char))


    # apply redactions in reverse order
    spans = sorted(spans, reverse=True)
    for s, e in spans:
        out = out[:s] + "[REDACTED]" + out[e:]
    return out


def redact(text, level):
    text = rule_mask(text, level)
    text = ner_mask(text, level)
    return text

def extract_line_spans(text, fname):
    """
    Return list of address/applicant spans found via line heuristics.
    Useful to add to 'preds' for evaluation.
    """
    spans = []
    for m in APPLICANT_LINE.finditer(text):
        s = m.start(1); e = m.end(1)
        # strip common trailing punctuation
        spans.append({"start": s, "end": e, "label": "PERSON"})
    for m in ADDR_LINE.finditer(text):
        s = m.start(1); e = m.end(1)
        # identify PIN inside address line
        pin_m = re.search(r'\b\d{6}\b', m.group(1))
        spans.append({"start": s, "end": e, "label": "ADDRESS"})
        if pin_m:
            pin_start = s + pin_m.start()
            pin_end = s + pin_m.end()
            spans.append({"start": pin_start, "end": pin_end, "label": "PIN"})
    return spans

def _regex_span_bounds(m):
    """Return span for a match; prefer first capturing group if present."""
    try:
        # if group(1) exists, use it (useful for FILE pattern)
        if m.lastindex and m.lastindex >= 1:
            return m.start(1), m.end(1)
    except Exception:
        pass
    return m.start(), m.end()

def main():
    dpath = pathlib.Path("rtis")
    outdir = pathlib.Path("outputs")
    outdir.mkdir(exist_ok=True)
    examples = sorted(dpath.glob("*.txt"))
    results = []
    preds = {}

    for p in examples:
        raw = p.read_text(encoding="utf-8")
        text = normalize_text(raw)
        lang = detect(text)
        print(f"{p.name}: detected language -> {lang}")

        # --- Create redacted versions ---
        for level in ("light", "medium", "strong"):
            red = redact(text, level)
            out_file = outdir / f"{p.stem}_{level}.txt"
            out_file.write_text(red, encoding="utf-8")

        # --- Collect regex + NER spans for evaluation ---
        spans = []
        # regex spans (with small label-specific filters)
        for label, pat in PATTERNS.items():
            for m in pat.finditer(text):
                st, ed = _regex_span_bounds(m)
                # PIN filter: ensure matched token is exactly 6 digits
                if label == "PIN":
                    token = text[st:ed].strip()
                    if not re.fullmatch(r'\d{6}', token):
                        continue
                spans.append({"start": st, "end": ed, "label": label})

        # add Applicant + Address line spans (heuristic)
        #spans += extract_line_spans(text, p.name)

        # NER spans with improved label mapping (conservative for ADDRESS)
        doc = nlp(text)
        LABEL_MAP = {"GPE": "ADDRESS", "LOC": "ADDRESS", "PERSON": "PERSON", "ORG": "ORG", "DATE": "DATE"}
        for ent in doc.ents:
          if ent.label_ in ("PERSON", "GPE", "LOC", "DATE"):
           ent_text = text[ent.start_char:ent.end_char]
           label = LABEL_MAP.get(ent.label_, ent.label_)

        # ADDRESS: conservative acceptance
           if label == "ADDRESS":
            if ("," in ent_text) or any(ch.isdigit() for ch in ent_text) or len(ent_text.strip()) > 12:
                spans.append({"start": ent.start_char, "end": ent.end_char, "label": label})

           elif label == "DATE":
            # Only accept if it matches strict DATE regex
            if PATTERNS["DATE"].search(ent_text):
                spans.append({"start": ent.start_char, "end": ent.end_char, "label": label})

           else:
            # PERSON
            spans.append({"start": ent.start_char, "end": ent.end_char, "label": label})


        # --- Remove duplicates / overlaps (conservative) ---
        
        unique = []
        for s in spans:
            st, ed = s.get("start"), s.get("end")
            if not (isinstance(st,int) and isinstance(ed,int) and 0 <= st < ed <= len(text)):
                continue
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
