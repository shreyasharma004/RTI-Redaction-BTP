# inference_model.py
from transformers import pipeline, XLMRobertaTokenizerFast, XLMRobertaForTokenClassification
import sys, pathlib, json

MODEL_DIR = "xlm_rti_ner_final_more"  # folder you downloaded/unzipped
tokenizer = XLMRobertaTokenizerFast.from_pretrained("xlm-roberta-base")
model = XLMRobertaForTokenClassification.from_pretrained(MODEL_DIR)

# Replace LABELS with the same list you used during training (B/I + O)
LABELS = ["O","B-PERSON","I-PERSON","B-ADDRESS","I-ADDRESS","B-PHONE","I-PHONE","B-EMAIL","I-EMAIL","B-AADHAAR","I-AADHAAR","B-PAN","I-PAN","B-PIN","I-PIN","B-DATE","I-DATE","B-FILE","I-FILE"]
model.config.id2label = {i: LABELS[i] for i in range(len(LABELS))}
model.config.label2id = {v:k for k,v in model.config.id2label.items()}

ner = pipeline("token-classification", model=model, tokenizer=tokenizer, aggregation_strategy="simple", device=-1) # device=-1 uses CPU

def infer_text(text):
    return ner(text)

if __name__ == "__main__":
    import sys
    s = "राहुल वर्मा, फोन 9876543210, email rahul@example.com, Address: 12 MG Road"
    print("Input:", s)
    print("NER:", infer_text(s))
