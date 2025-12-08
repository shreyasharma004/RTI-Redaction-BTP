# clean_preds.py
import json, re, unicodedata
from pathlib import Path

INFILE = "preds_fixed.json.bak"  # change if needed
RTI_DIR = "rtis"
OUTFILE = "preds_clean.json"

# --- normalization helpers ---
def norm_text(s: str) -> str:
    if s is None:
        return ""
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "")
    s = s.replace("\r\n", "\n").replace("\r", "\n")
    s = s.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")
    s = s.replace("—", "-").replace("–", "-")
    # collapse multiple spaces
    s = re.sub(r'[ \t\u00A0]+', " ", s)
    return s

def clean_snippet(s: str) -> str:
    if s is None:
        return ""
    s = norm_text(s).strip()
    # remove noisy prefixes common in your files: "का नाम:", "पता", "Email", "Name:", etc.
    s = re.sub(r'^(?:र\/o|r\/o|r\/o:|r\/o\s+|r\/o\s*[:\-]|\bname[:\-]\s*)', "", s, flags=re.I)
    s = re.sub(r'^[\:\-\|\.\,\/\s]+', "", s)
    s = s.strip()
    return s

# find best match for snippet in normalized text near approx_start
def find_best_match(norm, snippet, approx_start):
    if not snippet:
        return None
    s = snippet.strip()
    if not s:
        return None
    # try exact
    idx = norm.find(s)
    if idx != -1:
        return idx, idx+len(s)
    # try relaxed whitespace collapse
    s2 = re.sub(r'\s+', ' ', s)
    idx = norm.find(s2)
    if idx != -1:
        return idx, idx + len(s2)
    # try fuzzy by prefix windows around approx_start
    for w in range(min(len(s), 40), 3, -1):
        piece = s[:w]
        lo = max(0, approx_start - 120)
        hi = min(len(norm), approx_start + 120)
        idx = norm.find(piece, lo, hi)
        if idx != -1:
            # extend right as long as characters match
            j = idx + w
            # try to extend to full best match by greedy extension
            while j < len(norm) and len(s) > (j-idx) and norm[j] == s[j-idx]:
                j += 1
            return idx, j
    return None

def overlaps(a,b):
    return not (a[1] <= b[0] or b[1] <= a[0])

# label priority (higher = more authoritative). adjust as needed.
LABEL_PRIORITY = {
    "AADHAAR": 9, "PAN": 9, "PASSPORT": 9, "VOTER_ID": 8, "PHONE": 8, "EMAIL": 8,
    "PIN": 7, "FILE": 7, "DATE": 6, "ADDRESS": 5, "PERSON": 4, "ORG": 3, "OTHER":1
}

# noise heuristics for PERSON - drop if true
PERSON_NOISE_PATTERNS = [
    re.compile(r'^\s*$', re.I),
    re.compile(r'^[\d\W_]{1,4}$', re.I),
    re.compile(r'^(?:pata|पता|का नाम|की जिम्मेदारी|करे|करेin|karein|अनुरोध|Details|karamchariyon|attendance)$', re.I),
]

def is_person_noise(txt):
    t = txt.strip()
    if len(t) <= 2:
        return True
    # if contains keywords or unnatural punctuation-only
    for p in PERSON_NOISE_PATTERNS:
        if p.search(t):
            return True
    # if includes newline with non-name tokens or contains 'pincode' etc.
    if '\n' in t and len(t.splitlines())>1 and any(len(line.strip())>25 for line in t.splitlines()):
        return True
    return False

# MAIN
preds = json.loads(Path(INFILE).read_text(encoding="utf-8"))
cleaned = {}

for fname, spans in preds.items():
    txtpath = Path(RTI_DIR)/fname
    if not txtpath.exists():
        # keep existing spans but can't realign
        cleaned[fname] = spans
        continue
    raw = txtpath.read_text(encoding="utf-8", errors="replace")
    ntext = norm_text(raw)

    # normalize input spans
    rows = []
    for s in spans:
        lab = s.get("label")
        st = int(s.get("start",0))
        ed = int(s.get("end",0))
        snippet = s.get("text") or (raw[st:ed] if 0<=st<ed<=len(raw) else "")
        snippet = clean_snippet(snippet)
        if not snippet:
            # fallback: take substring from original indices and normalize
            try:
                snippet = clean_snippet(raw[st:ed])
            except:
                snippet = ""
        if not snippet:
            # extreme fallback: skip
            continue
        found = find_best_match(ntext, snippet, st)
        if found:
            nst,ned = found
            real = ntext[nst:ned].strip()
        else:
            # fallback to given indices (clamped)
            nst = max(0, min(len(ntext), st))
            ned = max(nst+1, min(len(ntext), ed if ed>nst else nst+len(snippet)))
            real = ntext[nst:ned].strip()
        rows.append({"start": nst, "end": ned, "label": lab, "text": real})

    # ---------- merge & dedupe per label ----------
    rows = sorted(rows, key=lambda x: (x["label"], x["start"], - (x["end"]-x["start"])))
    merged = []
    for r in rows:
        if not merged:
            merged.append(r.copy()); continue
        u = merged[-1]
        # same label merging: if overlap or gap <=2 merge
        if r["label"] == u["label"] and (r["start"] <= u["end"] or (r["start"] - u["end"]) <= 2):
            u["end"] = max(u["end"], r["end"])
            u["text"] = ntext[u["start"]:u["end"]].strip()
        else:
            merged.append(r.copy())

    # ---------- remove contained spans and prefer high-priority label ----------
    final = []
    for s in merged:
        contained = False
        for t in merged:
            if t is s: continue
            if t["start"] <= s["start"] and t["end"] >= s["end"]:
                # if container label has >= priority, drop s
                if LABEL_PRIORITY.get(t["label"],0) >= LABEL_PRIORITY.get(s["label"],0):
                    contained = True
                    break
        if not contained:
            final.append(s)

    # ---------- filter PERSON noise and very short junk ----------
    filtered = []
    for s in final:
        if s["label"] == "PERSON":
            if is_person_noise(s["text"]):
                # try trimming whitespace and punctuation
                t = re.sub(r'^[\:\-\.,\s]+|[\:\-\.,\s]+$', '', s["text"]).strip()
                if is_person_noise(t):
                    continue
                else:
                    s["text"] = t
                    # re-calc start/end by search
                    found = ntext.find(t, max(0, s["start"]-20), min(len(ntext), s["end"]+20))
                    if found!=-1:
                        s["start"] = found; s["end"] = found+len(t)
            # drop if too short after cleaning
            if len(s["text"]) <= 2:
                continue
        # drop PIN-like strings without digits or short non-digit matches
        if s["label"] == "PIN":
            if not re.search(r'\d{5,6}', s["text"]):
                continue
        filtered.append(s)

    # ---------- final pass: ensure no overlaps across labels: resolve by priority ----------
    # sort by start; for overlaps keep span with higher LABEL_PRIORITY, or longer span if equal
    filtered = sorted(filtered, key=lambda x: (x["start"], - (x["end"]-x["start"])))
    nonover = []
    for s in filtered:
        conflict = None
        for i,u in enumerate(nonover):
            if overlaps((s["start"], s["end"]), (u["start"], u["end"])):
                conflict = (i,u); break
        if not conflict:
            nonover.append(s)
            continue
        i,u = conflict
        # compare priority
        p_s = LABEL_PRIORITY.get(s["label"],0)
        p_u = LABEL_PRIORITY.get(u["label"],0)
        if p_s > p_u:
            # replace existing
            nonover[i] = s
        elif p_s < p_u:
            # keep existing, maybe trim s if possible
            # if s partly outside, keep outside portion by clipping
            if s["end"] <= u["end"] and s["start"] >= u["start"]:
                # fully inside lower priority -> drop
                pass
            else:
                # clip s to non-overlapping region(s) - prefer left piece
                if s["start"] < u["start"]:
                    s2 = s.copy()
                    s2["end"] = u["start"]
                    s2["text"] = ntext[s2["start"]:s2["end"]].strip()
                    nonover.append(s2)
                elif s["end"] > u["end"]:
                    s2 = s.copy()
                    s2["start"] = u["end"]
                    s2["text"] = ntext[s2["start"]:s2["end"]].strip()
                    nonover.append(s2)
        else:
            # equal priority: keep longer span
            len_s = s["end"]-s["start"]
            len_u = u["end"]-u["start"]
            if len_s > len_u:
                nonover[i] = s
            # else keep existing

    # final sort by start
    nonover = sorted(nonover, key=lambda x: x["start"])
    cleaned[fname] = [{"start": int(x["start"]), "end": int(x["end"]), "label": x["label"], "text": x["text"]} for x in nonover]

# write output
Path(OUTFILE).write_text(json.dumps(cleaned, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"WROTE {OUTFILE} — {len(cleaned)} files cleaned.")
