import json
from collections import defaultdict

# ------------------ Utility Functions ------------------

def load_json(path):
    """Load JSON safely."""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def span_overlap(a, b):
    """Return True if two spans overlap at all."""
    return not (a[1] <= b[0] or b[1] <= a[0])


def metrics(tp, fp, fn):
    """Compute precision, recall, F1."""
    prec = tp / (tp + fp) if tp + fp > 0 else 0.0
    rec = tp / (tp + fn) if tp + fn > 0 else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec > 0 else 0.0
    return prec, rec, f1


# ------------------ Core Evaluation ------------------

def evaluate(gold, preds):
    """Compare gold vs predictions at span level."""
    results = defaultdict(lambda: {"tp": 0, "fp": 0, "fn": 0})
    all_tp, all_fp, all_fn = 0, 0, 0

    for fname, g_spans in gold.items():
        p_spans = preds.get(fname, [])
        matched_pred = set()

        for g in g_spans:
            found = False
            for i, p in enumerate(p_spans):
                if i in matched_pred:
                    continue
                if g["label"] == p["label"] and span_overlap((g["start"], g["end"]), (p["start"], p["end"])):
                    results[g["label"]]["tp"] += 1
                    all_tp += 1
                    matched_pred.add(i)
                    found = True
                    break
            if not found:
                results[g["label"]]["fn"] += 1
                all_fn += 1

        # false positives = preds not matched
        for i, p in enumerate(p_spans):
            if i not in matched_pred:
                results[p["label"]]["fp"] += 1
                all_fp += 1

    # ------------------ Printing Results ------------------

    print("\n🔍  Evaluation Results\n")
    print("{:<12} {:>10} {:>10} {:>10}".format("Label", "Precision", "Recall", "F1"))
    print("-" * 45)
    for label, r in sorted(results.items()):
        p, r_, f1 = metrics(r["tp"], r["fp"], r["fn"])
        print("{:<12} {:>10.3f} {:>10.3f} {:>10.3f}".format(label, p, r_, f1))
    print("-" * 45)
    overall_p, overall_r, overall_f1 = metrics(all_tp, all_fp, all_fn)
    print("{:<12} {:>10.3f} {:>10.3f} {:>10.3f}".format("Overall", overall_p, overall_r, overall_f1))
    print()


# ------------------ Main Entry ------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) != 3:
        print("Usage: python evaluate.py gold.json preds.json")
        sys.exit(1)

    gold_path, pred_path = sys.argv[1], sys.argv[2]
    gold = load_json(gold_path)
    preds = load_json(pred_path)
    evaluate(gold, preds)
