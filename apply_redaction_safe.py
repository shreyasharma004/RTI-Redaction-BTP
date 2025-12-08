# apply_redaction_safe.py
import json, re
from pathlib import Path

PREDS = "preds_clean.json"
RTIS = "rtis"
OUT = "redacted_policy"

def clean(s):
    return "" if s is None else str(s).strip()

# ------------------------
# LOW POLICY
# ------------------------
def mask_low(label, s):
    s = clean(s)
    if label == "PERSON":
        return s  # keep names in low
    if label == "ADDRESS":
        return s
    if label == "PHONE":
        d = re.sub(r"\D", "", s)
        return f"[PHONE …{d[-4:]}]"
    if label == "AADHAAR":
        d = re.sub(r"\D", "", s)
        return f"[AADHAAR …{d[-4:]}]"
    if label in ("PAN", "PASSPORT", "VOTER_ID"):
        d = re.sub(r"\s+", "", s)
        return f"[{label} …{d[-4:]}]"
    if label == "PIN":
        return s
    return f"[{label} REDACTED]"

# ------------------------
# MEDIUM POLICY
# ------------------------
def mask_medium(label, s):
    s = clean(s)
    if label in ("AADHAAR", "PAN", "PASSPORT", "PHONE", "EMAIL", "VOTER_ID", "PIN"):
        return f"[{label} REDACTED]"
    if label == "PERSON":
        parts = [p for p in re.split(r'\s+', s) if p]
        if not parts:
            return "[PERSON REDACTED]"
        initials = ".".join((p[0].upper() for p in parts if p)) + "."
        return f"[PERSON {initials}]"
    if label == "ADDRESS":
        # safer: extract last numeric cluster (pin) and last two tokens
        tokens = [t.strip() for t in re.split(r'[,\n]+', s) if t.strip()]
        if tokens:
            # try to keep locality-like last token or last two tokens
            keep = tokens[-1]
            if len(tokens) >= 2:
                keep = tokens[-2] + ", " + tokens[-1]
            return f"[ADDRESS {keep}]"
        return "[ADDRESS REDACTED]"
    return f"[{label} REDACTED]"

# ------------------------
# HIGH POLICY
# ------------------------
def mask_high(label, s):
    return f"[{label} REDACTED]"

# ------------------------
# Apply clean non-overlapping replacements safely
# ------------------------
def apply_policy_to_text(text, spans, mode):
    s = str(text)
    # ensure spans sorted by start ascending
    spans = sorted(spans, key=lambda x: x["start"])
    # defensive: collapse any tiny overlaps (shouldn't exist after cleaning)
    safe_spans = []
    for sp in spans:
        st, ed = int(sp["start"]), int(sp["end"])
        if st < 0 or ed > len(s) or st >= ed:
            continue
        if safe_spans and st < safe_spans[-1]["end"]:
            # overlap with previous -> clip or merge conservatively
            prev = safe_spans[-1]
            if sp["label"] == prev["label"]:
                prev["end"] = max(prev["end"], ed)
            else:
                # clip the earlier one to avoid cross-label mashup: keep larger
                len_prev = prev["end"] - prev["start"]
                len_sp = ed - st
                if len_sp > len_prev:
                    # replace prev with sp
                    safe_spans[-1] = {"start": st, "end": ed, "label": sp["label"], "text": sp.get("text","")}
                else:
                    # drop/clip sp to non-overlapping tail
                    if ed > prev["end"]:
                        sp["start"] = prev["end"]
                        safe_spans.append(sp)
                    # else drop sp
        else:
            safe_spans.append({"start": st, "end": ed, "label": sp["label"], "text": sp.get("text","")})

    # build replacements in reverse order
    repls = []
    for sp in reversed(safe_spans):
        st, ed = sp["start"], sp["end"]
        snippet = s[st:ed]
        if mode == "LOW":
            replacement = mask_low(sp["label"], snippet)
        elif mode == "HIGH":
            replacement = mask_high(sp["label"], snippet)
        else:
            replacement = mask_medium(sp["label"], snippet)
        # keep surrounding spacing tidy
        # if snippet had leading/trailing newline, preserve one newline
        lead = "\n" if snippet[:1] == "\n" else ""
        trail = "\n" if snippet[-1:] == "\n" else ""
        # avoid crushing previous bracket to preceding token
        repls.append((st, ed, lead + replacement + trail))

    # apply
    for st, ed, rep in repls:
        s = s[:st] + rep + s[ed:]
    # final tidy: collapse "][ " into "] ["
    s = re.sub(r"\]\s*\[", "] [", s)
    return s

def main():
    preds = json.loads(Path(PREDS).read_text(encoding="utf-8"))
    modes = ["LOW", "MEDIUM", "HIGH"]
    for mode in modes:
        outdir = Path(f"{OUT}_{mode}")
        outdir.mkdir(exist_ok=True)
        print(f"\n=== Generating {mode} redactions... ===")
        count = 0
        for fname, spans in preds.items():
            src = Path(RTIS) / fname
            if not src.exists():
                continue
            text = src.read_text(encoding="utf-8")
            redacted = apply_policy_to_text(text, spans, mode)
            (outdir / fname).write_text(redacted, encoding="utf-8")
            count += 1
        print(f"✓ {mode}: Saved {count} files → {outdir}")
    print("\nAll policies generated successfully.")

if __name__ == "__main__":
    main()
