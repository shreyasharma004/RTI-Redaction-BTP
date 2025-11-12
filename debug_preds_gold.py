# debug_preds_gold.py
# Usage: python debug_preds_gold.py gold.json preds.json rtis/
import json, sys, os
from collections import defaultdict

def load_json(p): return json.load(open(p, 'r', encoding='utf-8'))

def read_text_file(folder, fname):
    p = os.path.join(folder, fname)
    return open(p, 'r', encoding='utf-8').read()

def extract(span, text):
    s,e = span['start'], span['end']
    return text[s:e] if 0 <= s < e <= len(text) else None

def report_mismatch_examples(gold, preds, rtis_folder, n=5):
    print("\n--- FILES SUMMARY ---")
    for fname in sorted(set(list(gold.keys()) + list(preds.keys()))):
        gcount = len(gold.get(fname, []))
        pcount = len(preds.get(fname, []))
        print(f"{fname}: gold={gcount}, preds={pcount}")
    print()

    # Common label mapping problems:
    print("Checking for label differences (spaCy vs our labels)...")
    labels_gold = set([a['label'] for v in gold.values() for a in v])
    labels_pred = set([a['label'] for v in preds.values() for a in v])
    print("Gold labels:", labels_gold)
    print("Pred labels:", labels_pred)
    diff = labels_pred - labels_gold
    if diff:
        print("Labels in preds but not in gold (possible mapping problem):", diff)
    else:
        print("No obvious label set mismatch.")
    print()

    # For each file, show examples where predicted span text != gold span text (or invalid spans)
    for fname in sorted(set(list(gold.keys()) + list(preds.keys()))):
        text = read_text_file(rtis_folder, fname)
        print(f"--- Inspecting {fname} (len={len(text)}) ---")
        g_spans = gold.get(fname, [])
        p_spans = preds.get(fname, [])
        # quick validity
        bad_g = [g for g in g_spans if not (0 <= g['start'] < g['end'] <= len(text))]
        bad_p = [p for p in p_spans if not (0 <= p['start'] < p['end'] <= len(text))]
        if bad_g:
            print(f"  INVALID gold spans (out of bounds): {bad_g}")
        if bad_p:
            print(f"  INVALID pred spans (out of bounds): {bad_p}")

        # show first few gold spans and their text
        print("  Example gold spans -> text:")
        for g in g_spans[:n]:
            txt = extract(g, text)
            print(f"    {g} -> '{txt}'")
        print("  Example pred spans -> text:")
        for p in p_spans[:n]:
            txt = extract(p, text)
            print(f"    {p} -> '{txt}'")
        print()

    # Show overlapping matches (very literal) to see why none matched
    print("--- Checking literal overlaps between gold and preds (quick) ---")
    for fname in sorted(set(list(gold.keys()) + list(preds.keys()))):
        g_spans = gold.get(fname, [])
        p_spans = preds.get(fname, [])
        matches = 0
        for g in g_spans:
            for p in p_spans:
                # label must exactly match
                same_label = (g['label'] == p['label'])
                overlap = not (g['end'] <= p['start'] or p['end'] <= g['start'])
                if same_label and overlap:
                    matches += 1
        print(f"{fname}: overlapping matches (label+span overlap) = {matches} / gold={len(g_spans)} preds={len(p_spans)}")
    print()

    # If nothing overlaps, give clues
    all_matches = sum(1 for f in gold for g in gold[f] for p in preds.get(f, []) if (g['label']==p['label'] and not (g['end'] <= p['start'] or p['end'] <= g['start'])))
    if all_matches == 0:
        print("No overlaps found at all. Likely causes (in order):")
        print("  1) Off-by-one / end-inclusive vs exclusive indexing mismatch.")
        print("  2) Different text used for gold vs preds (extra spaces/newlines/BOM).")
        print("  3) Labels differ (e.g., spaCy uses 'GPE' but gold uses 'LOC').")
        print("  4) Character encoding differences or CRLF vs LF newlines.")
        print("\nSuggested immediate checks:")
        print("  * Open rtis/sample1.txt and check a sample gold span by slicing in python or using the helper script to confirm the exact substring.")
        print("  * Print the exact substring your preds point to (we already printed examples above).")
        print("  * Confirm both gold.json and preds.json were created from the SAME raw files (no edits).")
    else:
        print("Some overlaps found — inspect the printed examples above to see which labels/positions matched.")
    print("\n--- Debug run complete ---\n")

if __name__ == "__main__":
    if len(sys.argv) < 4:
        print("Usage: python debug_preds_gold.py gold.json preds.json rtis_folder")
        sys.exit(1)
    gold_path, preds_path, rtis_folder = sys.argv[1], sys.argv[2], sys.argv[3]
    gold = load_json(gold_path)
    preds = load_json(preds_path)
    report_mismatch_examples(gold, preds, rtis_folder)
