# fix_preds.py  (final patched: aggressive-clean + merge addrs + PERSON filter + strict DATE + strict PIN/FILE)
import json
import re
import unicodedata
from pathlib import Path

# -------------------- STRICT REGEX VALIDATORS --------------------
RE_PHONE = re.compile(r'(?:\+91[-\s]?)?[6-9]\d{9}\b')
RE_EMAIL = re.compile(r'[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}')
RE_PAN = re.compile(r'\b[A-Z]{5}\d{4}[A-Z]\b', re.I)
RE_AADHAAR = re.compile(r'\b\d{4}[\s-]?\d{4}[\s-]?\d{4}\b')
RE_PIN = re.compile(r'\b[1-9]\d{5}\b')
RE_PASSPORT = re.compile(r'\b[A-PR-WYa-pr-wy]\d{7}\b')
RE_FILE = re.compile(r'\bRTI\/[A-Za-z0-9\-_\/]+\b', re.I)

# Strict-ish date patterns (dd/mm/yyyy, 12 June 2023, June 12, 2023, etc.)
RE_DATE = re.compile(
    r'(\b\d{1,2}[\/\-\.\s]\d{1,2}[\/\-\.\s]\d{2,4}\b)'
    r'|(\b(?:\d{1,2}\s+(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{2,4})\b)'
    r'|(\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Sept|Oct|Nov|Dec)[a-z]*\s+\d{1,2},?\s+\d{2,4}\b)',
    re.I
)

# -------------------- NORMALIZATION --------------------
def normalize_text(t):
    t = unicodedata.normalize('NFKC', t)
    t = t.replace('\r\n', '\n')
    t = re.sub(r'[ \t\u00A0]+', ' ', t)
    t = re.sub(r'[\u200B-\u200F\uFEFF]', '', t)
    return t

# -------------------- CLEAN PREFIXES / EDGES (AGGRESSIVE) --------------------
CLEAN_PREFIXES = [
    r'^(?:r\/o\s+)', r'^(?:r/o\s+)', r'^(?:r\.\/o\s+)',
    r'^(?:an[:\-]\s*)', r'^(?:an[:]\s*)',
    r'^(?:mail[:\-]\s*)', r'^(?:email[:\-]\s*)',
    r'^(?:phone[:\-]\s*)', r'^(?:mob[:\-]\s*)',
    r'^(?:tel[:\-]\s*)', r'^(?:name[:\-]\s*)',
    r'^(?:ref[:\-]\s*)', r'^(?:re[:\-]\s*)', r'^(?:no[:\-]\s*)'
]
CLEAN_PREFIXES = [re.compile(p, re.I) for p in CLEAN_PREFIXES]
GENERIC_PREFIX = re.compile(r'^[A-Za-z]{1,3}[\:\-\.\s\/]{1,4}', re.I)
CONTENT_RE = re.compile(r'[\w@\.\%\+\-\u0900-\u097F]', re.I)

def clean_snippet(snip):
    if not snip:
        return snip
    s = snip.strip()
    for p in CLEAN_PREFIXES:
        if p.match(s):
            s = p.sub('', s).lstrip()
    s = GENERIC_PREFIX.sub('', s).lstrip()
    start, end = 0, len(s)
    while start < end and not CONTENT_RE.search(s[start]):
        start += 1
    while end > start and not CONTENT_RE.search(s[end-1]):
        end -= 1
    s = s[start:end].strip()
    s = re.sub(r'^[\:\-\s]+', '', s)
    return s

# -------------------- BEST MATCH FINDER --------------------
def find_best_match(norm_text, snippet, approx_start):
    if not snippet:
        return None
    idx = norm_text.find(snippet)
    if idx != -1:
        return idx, idx + len(snippet)
    s = snippet.strip()
    if not s:
        return None
    s2 = re.sub(r'\s+', ' ', s)
    idx = norm_text.find(s2)
    if idx != -1:
        return idx, idx + len(s2)
    L = len(s)
    for w in range(min(30, L), 3, -1):
        piece = s[:w]
        lo = max(0, approx_start - 60)
        hi = min(len(norm_text), approx_start + 60)
        idx = norm_text.find(piece, lo, hi)
        if idx != -1:
            return idx, idx + w
    return None

# -------------------- IOU --------------------
def iou(a, b):
    inter = max(0, min(a[1], b[1]) - max(a[0], b[0]))
    union = (a[1]-a[0]) + (b[1]-b[0]) - inter
    return inter/union if union > 0 else 0

# -------------------- MAIN --------------------
PROJECT_RTI = "rtis"
preds = json.load(open("preds.json", encoding="utf-8"))
fixed = {}

for fname, spans in preds.items():
    path = Path(PROJECT_RTI) / fname
    if not path.exists():
        print("Missing text file:", path)
        continue

    raw = path.read_text(encoding="utf-8")
    ntext = normalize_text(raw)
    new_spans = []

    for s in spans:
        lab = s.get("label")
        st = int(s.get("start", 0))
        ed = int(s.get("end", 0))
        st = max(0, st)
        ed = max(st, ed)

        snippet = s.get("text") or raw[st:ed]
        snippet = normalize_text(snippet)
        snippet = clean_snippet(snippet)

        if len(snippet) < 2:
            sn2 = raw[st:ed].strip()
            if len(sn2) < 2:
                continue
            snippet = clean_snippet(sn2)

        found = find_best_match(ntext, snippet, st)
        if found:
            nst, ned = found
        else:
            nst = st
            ned = min(len(ntext), st + len(snippet))

        real = ntext[nst:ned].strip()

        # ---------- CLEAN AFTER MATCH (re-align if cleaned substring found) ----------
        cleaned = clean_snippet(real)
        if cleaned and cleaned != real:
            loc = ntext.find(cleaned, max(0, nst-10), min(len(ntext), ned+10))
            if loc != -1:
                nst, ned = loc, loc + len(cleaned)
                real = ntext[nst:ned].strip()
            else:
                real = cleaned

        # defensive strip of short leftover prefixes
        real = re.sub(r'^[A-Za-z][\:\-\.\s]+', '', real).strip()

        # ---------- STRICT VALIDATION ----------
        if lab == "PHONE" and not RE_PHONE.search(real):
            m = RE_PHONE.search(ntext, max(0, nst-20), min(len(ntext), ned+20))
            if m:
                nst, ned = m.start(), m.end()
                real = ntext[nst:ned]
            else:
                continue

        if lab == "EMAIL" and not RE_EMAIL.search(real):
            m = RE_EMAIL.search(ntext, max(0, nst-30), min(len(ntext), ned+30))
            if m:
                nst, ned = m.start(), m.end()
                real = ntext[nst:ned]
            else:
                continue

        # ---------- DATE validation: only keep sensible date-like spans ----------
        if lab == "DATE":
            if not RE_DATE.search(real):
                m = RE_DATE.search(ntext, max(0, nst-30), min(len(ntext), ned+30))
                if m:
                    nst, ned = m.start(), m.end()
                    real = ntext[nst:ned]
                else:
                    continue

        # ---------- FILE validation: require RTI/like pattern ----------
        if lab == "FILE":
            if not RE_FILE.search(real):
                m = RE_FILE.search(ntext, max(0, nst-20), min(len(ntext), ned+20))
                if m:
                    nst, ned = m.start(), m.end()
                    real = ntext[nst:ned]
                else:
                    continue

        if lab == "PAN" and not RE_PAN.search(real):
            m = RE_PAN.search(ntext, max(0, nst-10), min(len(ntext), ned+10))
            if m:
                nst, ned = m.start(), m.end()
                real = ntext[nst:ned]

        if lab == "AADHAAR" and not RE_AADHAAR.search(real):
            m = RE_AADHAAR.search(ntext, max(0, nst-20), min(len(ntext), ned+20))
            if m:
                nst, ned = m.start(), m.end()
                real = ntext[nst:ned]

        # ---------- PIN: require exact 6-digit + contextual cue or explicit nearby match ----------
        if lab == "PIN":
            # try to find a 6-digit inside the matched text first
            m = RE_PIN.search(real)
            if m:
                # align to the exact 6-digit match (convert to global indices)
                nst = nst + m.start()
                ned = nst + (m.end() - m.start())
                real = ntext[nst:ned]
            else:
                # try to find a 6-digit near the region
                m = RE_PIN.search(ntext, max(0, nst-12), min(len(ntext), ned+12))
                if m:
                    nst, ned = m.start(), m.end()
                    real = ntext[nst:ned]
                else:
                    # no 6-digit found -> drop
                    continue

            # require a contextual cue near the PIN (left or right)
            left = ntext[max(0, nst-20):nst].lower()
            right = ntext[ned:min(len(ntext), ned+20)].lower()
            if not re.search(r'\b(pin|pincode|pincode:|pin:|postcode|zip|pin-)\b', left + " " + right):
                # allow PIN if it appears at very end of a line (likely part of address)
                # check a small window around the pin for a newline right after or before
                window = ntext[max(0, nst-6):min(len(ntext), ned+6)]
                if not re.search(r'\n', window):
                    # no context -> drop noisy PIN
                    continue

        if len(real) < 2:
            continue

        new_spans.append({
            "start": nst, "end": ned,
            "label": lab, "text": real
        })

    # -------------------- MERGE ADDRESS SUB-SPANS & FILTER PERSONS --------------------
    addr_spans = [x for x in new_spans if x['label'] == 'ADDRESS']
    addr_spans = sorted(addr_spans, key=lambda a: (a['start'], a['end']))
    merged_addr = []
    for a in addr_spans:
        if not merged_addr:
            merged_addr.append(a.copy())
            continue
        last = merged_addr[-1]
        if a['start'] <= last['end'] or (a['start'] - last['end']) <= 3:
            last['end'] = max(last['end'], a['end'])
            last['text'] = ntext[last['start']:last['end']].strip()
        else:
            merged_addr.append(a.copy())

    non_addr = [x for x in new_spans if x['label'] != 'ADDRESS']
    new_spans = non_addr + merged_addr

    ADDRESS_KEYWORDS = {
        'apt','apartment','colony','col','road','rd','street','st','vihar',
        'village','flat','block','sector','enclave','layout','nagar','kalan',
        'residency','residences','bazar','bazaar','housing','lane','gali',
        'near','opp','opposite','behind','phase','mandir','park','meadow','heights'
    }
    filtered = []
    addr_ranges = [(a['start'], a['end']) for a in merged_addr]

    for s in new_spans:
        if s['label'] == 'PERSON':
            txt = s['text'].lower()
            if any(kw in txt for kw in ADDRESS_KEYWORDS):
                continue
            inside = any(s['start'] >= a0 and s['end'] <= a1 for (a0,a1) in addr_ranges)
            if inside:
                continue
            if len(txt) <= 3:
                left = ntext[max(0, s['start']-4):s['start']].strip()
                right = ntext[s['end']:s['end']+4].strip()
                if re.search(r'[:\-\|,]', left + right):
                    continue
        filtered.append(s)

    new_spans = filtered
    # -------------------- END MERGE+FILTER --------------------

    # -------------------- REMOVE DUPES --------------------
    unique = []
    for s in sorted(new_spans, key=lambda x: (x['label'], x['start'])):
        dup = False
        for u in unique:
            if s['label'] == u['label'] and iou((s['start'], s['end']), (u['start'], u['end'])) > 0.5:
                if (s['end'] - s['start']) > (u['end'] - u['start']):
                    u.update(s)
                dup = True
                break
        if not dup:
            unique.append(s)

    fixed[fname] = unique

open("preds_fixed.json", "w", encoding="utf-8").write(
    json.dumps(fixed, ensure_ascii=False, indent=2)
)

print("wrote preds_fixed.json — now run:")
print("python debug_preds_gold.py gold.json preds_fixed.json rtis")
