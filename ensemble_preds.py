import json
from pathlib import Path

hf = json.load(open("preds_from_xlmr.json", encoding="utf-8"))
sp = json.load(open("preds.json", encoding="utf-8"))  # your spaCy+regex preds
out = {}
for k in set(list(hf.keys()) + list(sp.keys())):
    items = []
    seen = set()
    for s in (hf.get(k,[]) + sp.get(k,[])):
        key = (s["start"], s["end"], s["label"])
        if key in seen:
            continue
        seen.add(key)
        items.append(s)
    out[k] = items
Path("preds_ensemble.json").write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
print("wrote preds_ensemble.json")
