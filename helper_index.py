# helper_index.py (FIXED — UNICODE NORMALIZED + FUZZY SEARCH)

import re
import unicodedata

file = "rtis/sample10.txt"   # change this for other files

def normalize(s: str) -> str:
    # NFC normalize, remove zero-width chars, replace fancy quotes/dashes
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u200c", "").replace("\u200d", "").replace("\ufeff", "")
    s = s.replace("“", '"').replace("”", '"')
    s = s.replace("‘", "'").replace("’", "'")
    s = s.replace("—", "-").replace("–", "-")
    return s

# load + normalize
raw_text = open(file, encoding="utf-8", errors="replace").read()
text = normalize(raw_text)

target = input("Enter a keyword or number to search: ").strip()
target_norm = normalize(target)

# 1) Try direct normalized match
idx = text.lower().find(target_norm.lower())
if idx != -1:
    print("\nExact-ish match found after normalization!")
    print(f"Start: {idx}, End: {idx + len(target_norm)}")
    print("Extracted:", repr(text[idx:idx+len(target_norm)]))
    exit()

# 2) Try fuzzy: find anywhere the letters appear in order
pattern = ".*?".join(map(re.escape, target_norm))
fuzzy = re.search(pattern, text, flags=re.IGNORECASE)
if fuzzy:
    print("\nFuzzy match found!")
    print(f"Start: {fuzzy.start()}, End: {fuzzy.end()}")
    print("Extracted:", repr(text[fuzzy.start():fuzzy.end()]))
    exit()

# 3) Fallback: show numeric clusters as before
print("\nNo match found. Showing numeric clusters instead:")
for m in re.finditer(r'[0-9A-Za-z\+\-\.\@]{5,}', text):
    snippet = text[m.start():m.end()]
    if any(ch.isdigit() for ch in snippet):
        print(f"{m.start():>4}-{m.end():<4}: {repr(snippet)}")
