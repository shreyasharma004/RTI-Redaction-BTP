# validate_gold.py
import json
import os
import unicodedata
import argparse
import textwrap

def normalize_text(s: str) -> str:
    s = unicodedata.normalize("NFKC", s)
    s = s.replace("\u200c","").replace("\u200d","").replace("\ufeff","")
    s = s.replace("“",'\"').replace("”",'\"').replace("’","'").replace("‘","'")
    s = s.replace("—","-").replace("–","-")
    s = s.replace("\r\n","\n").replace("\r","\n")
    return s

def load_gold(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def inspect(gold_path="gold.json", rtis_dir="rtis", write_bad="bad_spans.json", max_show=50):
    report = {"missing_files": [], "files_checked": 0, "total_spans": 0, "invalid_spans": []}

    if not os.path.exists(gold_path):
        print(f"ERROR: gold.json not found at {gold_path}")
        return report

    gold = load_gold(gold_path)

    for fname, spans in gold.items():
        report["files_checked"] += 1
        txt_path = os.path.join(rtis_dir, fname)
        if not os.path.exists(txt_path):
            report["missing_files"].append(fname)
            continue

        raw = open(txt_path, "r", encoding="utf-8", errors="replace").read()
        norm = normalize_text(raw)
        L = len(norm)

        for i, s in enumerate(spans):
            report["total_spans"] += 1
            st = s.get("start")
            ed = s.get("end")
            lab = s.get("label")
            # basic checks
            if not isinstance(st, int) or not isinstance(ed, int):
                report["invalid_spans"].append({
                    "file": fname, "idx": i, "start": st, "end": ed, "label": lab,
                    "reason": "non-int indices"
                })
                continue
            if st < 0 or ed < 0 or st >= ed or ed > L:
                snippet = None
                try:
                    snippet = norm[ max(0, st-30) : min(L, ed+30) ]
                except Exception:
                    snippet = None
                report["invalid_spans"].append({
                    "file": fname, "idx": i, "start": st, "end": ed, "label": lab,
                    "reason": f"out-of-bounds (file len={L})", "snippet": snippet
                })

    # summary
    print("="*80)
    print("GOLD VALIDATION REPORT")
    print("="*80)
    print(f"gold.json path : {os.path.abspath(gold_path)}")
    print(f"rtis dir       : {os.path.abspath(rtis_dir)}")
    print()
    print(f"Files referenced in gold.json : {len(gold.keys())}")
    print(f"Files checked (exist in rtis)  : {report['files_checked']}")
    print(f"Missing files reported         : {len(report['missing_files'])}")
    if report['missing_files']:
        print(" -> Missing files (first 20):")
        for f in report['missing_files'][:20]:
            print("    ", f)
    print()
    print(f"Total spans in gold.json       : {report['total_spans']}")
    print(f"Invalid spans found            : {len(report['invalid_spans'])}")
    if report['invalid_spans']:
        print("\nTop invalid spans (max {})".format(max_show))
        for idx, bad in enumerate(report['invalid_spans'][:max_show]):
            print("-"*40)
            print(f"[{idx+1}] file: {bad['file']}  span# {bad['idx']}  label: {bad.get('label')}")
            print(f"      start: {bad.get('start')}  end: {bad.get('end')}  reason: {bad.get('reason')}")
            if bad.get("snippet") is not None:
                snip = bad["snippet"]
                # show with escapes so whitespace/newlines visible
                print("      context snippet (≈60 chars around span):")
                print("         ", repr(snip))
        # write out bad list for easier editing
        try:
            with open(write_bad, "w", encoding="utf-8") as out:
                json.dump(report['invalid_spans'], out, ensure_ascii=False, indent=2)
            print("\nWrote invalid span details to:", write_bad)
        except Exception as e:
            print("Couldn't write bad_spans.json:", e)
    else:
        print("No invalid spans found. Nice.")

    print("\nNext steps:")
    if report['missing_files']:
        print("  1) Fix missing files: either move those rtis/*.txt into the 'rtis' folder, or remove entries from gold.json for test files you don't have.")
    if report['invalid_spans']:
        print("  2) For each invalid span, open the corresponding rtis file and inspect the snippet printed above; then update gold.json with correct start/end for that file (or re-run your annotation helper).")
        print("     Tip: open the file in a text editor, copy the exact substring you want to tag, then in Python compute its index with text.index(substring) against the normalized text.")
        print("     Example (python REPL):")
        print(textwrap.indent("""\
python
from pathlib import Path
s = Path('rtis/sample1.txt').read_text(encoding='utf-8')
import unicodedata
def norm(x): return unicodedata.normalize('NFKC', x).replace('\\u200c','').replace('\\u200d','').replace('\\ufeff','')
s2 = norm(s)
sub = 'THE EXACT SUBSTRING YOU WANT'
print(s2.index(sub), s2.index(sub)+len(sub))
""", "    "))
    else:
        print("  2) All spans look in-bounds. If evaluation still looks off, run your eval and inspect specific low-scoring label examples using debug_preds_gold.py")

    return report

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Validate gold.json spans against rtis/*.txt (with normalization).")
    parser.add_argument("--gold", default="gold.json")
    parser.add_argument("--rtis", default="rtis")
    parser.add_argument("--out", default="bad_spans.json")
    args = parser.parse_args()
    inspect(gold_path=args.gold, rtis_dir=args.rtis, write_bad=args.out)
