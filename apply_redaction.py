# apply_redaction.py
# Generate LOW, MEDIUM, and HIGH redactions in 3 folders in one run.

import json, re
from pathlib import Path

PREDS = "preds_fixed.json"
RTIS = "rtis"
OUT = "redacted_policy"  # base prefix: redacted_policy_LOW, etc.

# ------------------------
# Utility
# ------------------------
def clean(s):
    return "" if s is None else str(s).strip()


# ------------------------
# LOW POLICY
# ------------------------
def mask_low(label, s):
    s = clean(s)

    if label == "PERSON":
        return s

    if label == "ADDRESS":
        return s  # full address allowed

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
        return s  # PIN stays visible in LOW

    return f"[{label} REDACTED]"


# ------------------------
# MEDIUM POLICY
# ------------------------
def mask_medium(label, s):
    s = clean(s)

    if label in ("AADHAAR", "PAN", "PASSPORT", "PHONE", "EMAIL", "VOTER_ID", "PIN"):
        return f"[{label} REDACTED]"

    if label == "PERSON":
        parts = [p for p in s.split() if p]
        if not parts:
            return "[PERSON REDACTED]"
        initials = ".".join(p[0].upper() for p in parts) + "."
        return f"[PERSON {initials}]"

    if label == "ADDRESS":
        # remove house number, keep locality + city
        s2 = re.sub(r"^[A-Za-z0-9\-\s/]+,", "", s)
        parts = [p.strip() for p in s2.split(",") if p.strip()]
        if len(parts) >= 2:
            return f"[ADDRESS {parts[-2]}, {parts[-1]}]"
        return f"[ADDRESS {parts[-1]}]" if parts else "[ADDRESS REDACTED]"

    return f"[{label} REDACTED]"


# ------------------------
# HIGH POLICY
# ------------------------
def mask_high(label, s):
    return f"[{label} REDACTED]"


# ------------------------
# REDACTOR
# ------------------------
def apply_policy_to_text(text, spans, mode):
    s = str(text)
    spans = sorted(spans, key=lambda x: x["start"], reverse=True)

    for sp in spans:
        label = sp["label"]
        st = sp["start"]
        ed = sp["end"]

        if st < 0 or ed > len(s) or st >= ed:
            continue

        snippet = s[st:ed]

        if mode == "LOW":
            repl = mask_low(label, snippet)
        elif mode == "HIGH":
            repl = mask_high(label, snippet)
        else:
            repl = mask_medium(label, snippet)

        s = s[:st] + repl + s[ed:]

    # formatting cleanup
    s = re.sub(r"\]\s*\[", "] [", s)
    return s


# ------------------------
# MAIN: run ALL 3 policies
# ------------------------
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
