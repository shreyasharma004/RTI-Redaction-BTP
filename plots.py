import json
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path
from collections import defaultdict


def load_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))

def overlap(a, b):
    return not (a[1] <= b[0] or b[1] <= a[0])


def compute_metrics_and_confusion(gold, preds):

    # Collect all labels
    labels = set()
    for gspans in gold.values():
        for s in gspans:
            labels.add(s["label"])
    for pspans in preds.values():
        for s in pspans:
            labels.add(s["label"])

    labels = sorted(labels)
    label_to_idx = {l:i for i,l in enumerate(labels)}

    # Initialize counters
    tp = {l:0 for l in labels}
    fp = {l:0 for l in labels}
    fn = {l:0 for l in labels}

    # Confusion matrix: rows = gold, cols = predicted
    cm = np.zeros((len(labels), len(labels)), dtype=int)

    for fname, gspans in gold.items():
        pspans = preds.get(fname, [])

        matched = set()

        for g in gspans:
            g_range = (g["start"], g["end"])
            gl = g["label"]
            matched_pred_label = None

            for i, p in enumerate(pspans):
                if i in matched:
                    continue
                if p["label"] == gl and overlap(g_range, (p["start"], p["end"])):
                    matched.add(i)
                    tp[gl] += 1
                    matched_pred_label = gl
                    break

            if matched_pred_label is None:
                fn[gl] += 1

        # unmatched predictions = FP
        for i, p in enumerate(pspans):
            if i not in matched:
                fp[p["label"]] += 1
                # confusion: predicted p["label"], but true is NONE
                # we won't add to matrix because "NONE" isn't a label

        # confusion matrix fill for matched predictions
        # (we need to re-loop for exact matches)
        for g in gspans:
            g_range = (g["start"], g["end"])
            gl = g["label"]
            for p in pspans:
                if p["label"] == gl and overlap(g_range,(p["start"],p["end"])):
                    gi = label_to_idx[gl]
                    pj = label_to_idx[gl]
                    cm[gi, pj] += 1

    # Compute per-label metrics
    metrics = {}
    for l in labels:
        P = tp[l] / (tp[l] + fp[l]) if (tp[l] + fp[l]) > 0 else 0
        R = tp[l] / (tp[l] + fn[l]) if (tp[l] + fn[l]) > 0 else 0
        F1 = 2 * P * R / (P + R) if (P + R) > 0 else 0
        metrics[l] = (P, R, F1)

    return labels, metrics, cm


# ---------------------------
# Plotting Functions
# ---------------------------

def bar_plot(metrics, index, title, ylabel, outfile):
    labels = list(metrics.keys())
    values = [metrics[l][index] for l in labels]

    plt.figure(figsize=(12,5))
    plt.bar(labels, values, color='teal')
    plt.title(title)
    plt.ylabel(ylabel)
    plt.xticks(rotation=45)
    plt.tight_layout()
    plt.savefig(outfile)
    plt.close()


def confusion_matrix_plot(labels, cm, outfile):
    plt.figure(figsize=(10,8))
    plt.imshow(cm, interpolation='nearest', cmap='Blues')
    plt.title("Confusion Matrix")
    plt.colorbar()

    tick_marks = np.arange(len(labels))
    plt.xticks(tick_marks, labels, rotation=45)
    plt.yticks(tick_marks, labels)

    # numbers on cells
    thresh = cm.max() / 2.
    for i in range(cm.shape[0]):
        for j in range(cm.shape[1]):
            plt.text(
                j, i, format(cm[i, j]),
                ha="center",
                va="center",
                color="white" if cm[i, j] > thresh else "black"
            )

    plt.xlabel("Predicted label")
    plt.ylabel("True (gold) label")
    plt.tight_layout()
    plt.savefig(outfile)
    plt.close()


# ---------------------------
# Main
# ---------------------------

def main():
    gold = load_json("gold.json")
    preds = load_json("preds_fixed.json")

    labels, metrics, cm = compute_metrics_and_confusion(gold, preds)

    Path("plots").mkdir(exist_ok=True)

    # Save bar plots
    bar_plot(metrics, 0, "Precision per Label", "Precision", "plots/precision.png")
    bar_plot(metrics, 1, "Recall per Label", "Recall", "plots/recall.png")
    bar_plot(metrics, 2, "F1 Score per Label", "F1", "plots/f1.png")

    # Save confusion matrix
    confusion_matrix_plot(labels, cm, "plots/confusion_matrix.png")

    print("Saved plots to 'plots/' folder.")

if __name__ == "__main__":
    main()
