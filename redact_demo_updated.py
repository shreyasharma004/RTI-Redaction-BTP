# redact_demo_updated.py
import re
import json
import pathlib
import unicodedata
import sys

# optional: HF model for bilingual inference (only if you downloaded/placed the model)
USE_XLM = True  # set False if you don't want to try loading HF model

# imports with safe fallbacks
try:
    import spacy
except Exception as e:
    print("spacy not installed. Run `pip install spacy` and `python -m spacy download en_core_web_sm`.", file=sys.stderr)
    raise

try:
    from langdetect import detect as lang_detect
except Exception:
    def lang_detect(_): return "en"

# optional transformers pipeline
HF_PIPELINE = None
if USE_XLM:
    try:
        from transformers import pipeline, XLMRobertaTokenizerFast, XLMRobertaForTokenClassification
        MODEL_DIR = pathlib.Path("xlm_rti_ner_final")
        if MODEL_DIR.exists():
            print("Loading XLM-R inference pipeline from", MODEL_DIR)
            try:
                # load tokenizer/model; pipeline will handle id2label if saved, otherwise user may need to set id2label
                HF_PIPELINE = pipeline("token-classification", model=str(MODEL_DIR), tokenizer="xlm-roberta-base", aggregation_strategy="simple", device=0)
            except Exception as e:
                print("Failed to load HF pipeline:", e, file=sys.stderr)
                HF_PIPELINE = None
        else:
            print("No model folder 'xlm_rti_ner_final' found — skipping HF pipeline.")
            HF_PIPELINE = None
    except Exception as e:
        print("transformers not installed or load failed:", e, file=sys.stderr)
        HF_PIPELINE = None

# Load small English spaCy model (used conservatively)
try:
    nlp = spacy.load("en_core_web_sm")
except Exception as e:
    print("spaCy model not found. Try: python -m spacy download en_core_web_sm", file=sys.stderr)
    raise

# India-specific regex patterns (extended)
PATTERNS = {
    "FILE": re.compile(r'\b(?:File\s+No[:\s]*|File[:\s]*|File\s+)\s*([A-Za-z0-9\/\-\_\.]+)', re.I),
    "AADHAAR": re.compile(r'\b(?:\d{4}\s?\d{4}\s?\d{4}|\d{12})\b'),
    "PAN": re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b'),
    "PHONE": re.compile(r'\b(?:\+91[\-\s]?|0)?[6-9]\d{9}\b'),
    "PIN": re.compile(r'\b\d{6}\b'),
    "EMAIL": re.compile(r'\b[\w\.\+\-]+@[\w\.-]+\.\w{2,}\b', re.I),
    "PASSPORT": re.compile(r'\b[A-Z]\d{7}\b'),
    "VOTER_ID": re.compile(r'\b[A-Z]{3}\d{6,7}\b'),
    "DATE": re.compile(
        r'\b(?:'
        r'(?:0?[1-9]|[12][0-9]|3[01])[/-](?:0?[1-9]|1[0-2])[/-](?:19|20)\d{2}|'
        r'(?:0?[1-9]|[12][0-9]|3[01])\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\s+(?:19|20)\d{2}'
        r')\b',
        re.I
    )
}

# address/applicant line heuristics (multi-line)
ADDR_LINE = re.compile(r'(?mi)^(?:Address|Address:|R\/o|R/O|R/o|पता|Add:|Address)\s*[:\-]?\s*(.+)$')
APPLICANT_LINE = re.compile(r'(?mi)^(?:Applicant|APPLICANT|आवेदक)\s*[:\-]?\s*(.+)$')

def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u200c","").replace("\u200d","").replace("\ufeff","")
    s = s.replace("“",'\"').replace("”",'\"').replace("’","'").replace("‘","'")
    s = s.replace("—","-").replace("–","-")
    s = s.replace("\r\n","\n").replace("\r","\n")
    return s

def _regex_span_bounds(m):
    """Return span for a match; prefer first capturing group if present."""
    try:
        if m.lastindex and m.lastindex >= 1:
            return m.start(1), m.end(1)
    except Exception:
        pass
    return m.start(), m.end()

def rule_spans(text):
    """Return regex-based spans (list of dicts)."""
    spans = []
    for label, pat in PATTERNS.items():
        for m in pat.finditer(text):
            st, ed = _regex_span_bounds(m)
            # PIN filter: ensure matched token is exactly 6 digits
            if label == "PIN":
                token = text[st:ed].strip()
                if not re.fullmatch(r'\d{6}', token):
                    continue
            spans.append({"start": st, "end": ed, "label": label})
    return spans

def line_spans(text):
    spans = []
    for m in APPLICANT_LINE.finditer(text):
        s = m.start(1); e = m.end(1)
        spans.append({"start": s, "end": e, "label": "PERSON"})
    for m in ADDR_LINE.finditer(text):
        s = m.start(1); e = m.end(1)
        spans.append({"start": s, "end": e, "label": "ADDRESS"})
        pin_m = re.search(r'\b\d{6}\b', m.group(1))
        if pin_m:
            pin_start = s + pin_m.start()
            pin_end = s + pin_m.end()
            spans.append({"start": pin_start, "end": pin_end, "label": "PIN"})
    return spans

def spacy_spans(text):
    """Use spaCy NER conservatively (PERSON, GPE/LOC->ADDRESS, DATE)."""
    doc = nlp(text)
    LABEL_MAP = {"GPE": "ADDRESS", "LOC": "ADDRESS", "PERSON": "PERSON", "ORG": "ORG", "DATE": "DATE"}
    spans = []
    for ent in doc.ents:
        if ent.label_ not in ("PERSON", "GPE", "LOC", "DATE"):
            continue
        ent_text = text[ent.start_char:ent.end_char]
        label = LABEL_MAP.get(ent.label_, ent.label_)
        if label == "ADDRESS":
            if ("," in ent_text) or any(ch.isdigit() for ch in ent_text) or len(ent_text.strip()) > 12:
                spans.append({"start": ent.start_char, "end": ent.end_char, "label": label})
        elif label == "DATE":
            if PATTERNS["DATE"].search(ent_text):
                spans.append({"start": ent.start_char, "end": ent.end_char, "label": label})
        else:
            spans.append({"start": ent.start_char, "end": ent.end_char, "label": label})
    return spans

def hf_spans(text):
    """Use HF pipeline (if loaded) to extract spans. Map entity_group to label if possible."""
    if HF_PIPELINE is None:
        return []
    try:
        res = HF_PIPELINE(text)
    except Exception as e:
        print("HF pipeline error:", e, file=sys.stderr)
        return []
    out = []
    for ent in res:
        # aggregation_strategy returns entity_group like 'PERSON' or 'LABEL_0'
        label = ent.get("entity_group") or ent.get("entity")
        if isinstance(label, str) and label.startswith("LABEL_"):
            # try to convert numeric LABEL_ to model labels if possible
            try:
                idx = int(label.split("_",1)[1])
                cfg_map = getattr(HF_PIPELINE.model.config, "id2label", {})
                label = cfg_map.get(idx, label)
            except Exception:
                pass
        # Normalize label to a small set if needed
        # We expect labels like B-PERSON/I-PERSON or PERSON depending on checkpoint saving.
        if label and label.startswith("B-"):
            label = label.split("-",1)[1]
        if label and label.startswith("I-"):
            label = label.split("-",1)[1]
        out.append({"start": ent["start"], "end": ent["end"], "label": label if label else "O"})
    return out

def combine_and_dedupe(spans, text_len):
    """Combine list of spans (dicts) and remove duplicates/invalids conservatively."""
    good = []
    for s in spans:
        st, ed = s.get("start"), s.get("end")
        label = s.get("label", "O")
        if not (isinstance(st,int) and isinstance(ed,int) and 0 <= st < ed <= text_len):
            continue
        good.append({"start": st, "end": ed, "label": label})
    # sort by start then -length so longer spans keep precedence
    good = sorted(good, key=lambda x: (x["start"], -(x["end"]-x["start"])))
    unique = []
    for s in good:
        st, ed, lab = s["start"], s["end"], s["label"]
        overlap = False
        for u in unique:
            # if same label close to existing, skip (merge-like)
            if not (ed <= u["start"] or st >= u["end"]):  # overlap
                # allow containing span to replace smaller if same label
                if lab == u["label"] and (abs(st - u["start"]) < 3 or abs(ed - u["end"]) < 3):
                    overlap = True
                    break
                # otherwise prefer existing larger span -> skip
                if (u["end"]-u["start"]) >= (ed-st):
                    overlap = True
                    break
        if not overlap:
            unique.append(s)
    return unique

def apply_redactions(text, spans):
    """Apply redactions replacing exact char spans with [REDACTED-LABEL]."""
    out = []
    last = 0
    for s in sorted(spans, key=lambda x: x["start"]):
        st, ed, lab = s["start"], s["end"], s["label"]
        out.append(text[last:st])
        out.append(f"[REDACTED-{lab}]")
        last = ed
    out.append(text[last:])
    return "".join(out)

def redact_text_levels(text):
    """
    Returns dict of {'light': text, 'medium': text, 'strong': text}
    - light: regex only
    - medium: regex + spaCy (conservative)
    - strong: regex + spaCy + HF (if available)
    Also returns preds dict for evaluation using strong (or medium if HF not available).
    """
    text_len = len(text)
    r_spans = rule_spans(text)
    l_spans = line_spans(text)
    s_spans = spacy_spans(text)

    combined_light = combine_and_dedupe(r_spans + l_spans, text_len)
    combined_medium = combine_and_dedupe(r_spans + l_spans + s_spans, text_len)

    if HF_PIPELINE:
        hf_s = hf_spans(text)
        combined_strong = combine_and_dedupe(r_spans + l_spans + s_spans + hf_s, text_len)
    else:
        combined_strong = combined_medium  # fallback if no HF model

    red_light = apply_redactions(text, combined_light)
    red_medium = apply_redactions(text, combined_medium)
    red_strong = apply_redactions(text, combined_strong)

    # choose preds for evaluation (strong if available else medium)
    preds_for_eval = combined_strong if HF_PIPELINE else combined_medium

    return {"light": red_light, "medium": red_medium, "strong": red_strong}, preds_for_eval

def main():
    dpath = pathlib.Path("rtis")
    outdir = pathlib.Path("outputs")
    outdir.mkdir(exist_ok=True)
    examples = sorted(dpath.glob("*.txt"))
    results = []
    preds = {}

    if not examples:
        print("No .txt files found in ./rtis. Put demo files there and re-run.")
        return

    for p in examples:
        raw = p.read_text(encoding="utf-8")
        text = normalize_text(raw)
        try:
            lang = lang_detect(text)
        except Exception:
            lang = "en"
        print(f"{p.name}: detected language -> {lang}")

        redacted_map, preds_for_eval = redact_text_levels(text)

        # save redacted files per level
        for level, out_text in redacted_map.items():
            out_file = outdir / f"{p.stem}_{level}.txt"
            out_file.write_text(out_text, encoding="utf-8")

        # attach preds (convert spans to simple dicts)
        preds[p.name] = preds_for_eval

        # quick presence log
        found = {k: bool(v.search(text)) for k, v in PATTERNS.items()}
        results.append({"file": p.name, "found": found})

    # Save predictions for evaluation
    with open("preds.json", "w", encoding="utf-8") as f:
        json.dump(preds, f, ensure_ascii=False, indent=2)

    print(json.dumps(results, indent=2))
    print("\n✅ Redacted files saved in 'outputs/' folder!")
    print("✅ Predictions saved to preds.json for evaluation.")
    if HF_PIPELINE:
        print("✅ XLM-R pipeline was used for 'strong' level (if model loaded).")

if __name__ == "__main__":
    main()
