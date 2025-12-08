✨ RTI PII Redaction Pipeline (Hindi + English)

A hybrid NLP system for automated, policy-aware redaction of personally identifiable information (PII) in RTI documents.
Supports Hindi + English, three redaction modes, and full evaluation using a gold-annotated dataset.

⭐ 1. Features

Text Normalization
Fixes unicode, punctuation, spacing, and aligns spans.

Regex Layer (High Precision)
Detects Aadhaar, PAN, Phone, Email, PIN, Passport, Dates.

spaCy NER Layer (English)
Identifies PERSON, ADDRESS, DATE for English segments.

XLM-RoBERTa Fine-Tuned Model (Hindi + English)
Custom-trained transformer for bilingual PII detection.

Span Merging & Policy Logic
Resolves overlaps + prioritizes high-risk PII categories.

Redaction Levels

Light → Regex only

Medium → Regex + spaCy

Strong → Regex + spaCy + XLM-R

Evaluation
Label-wise F1 using seqeval, via eval_script.py.

⭐ 2. Project Structure
RTI-Redaction-BTP/
│
├── rtis/ # Input RTI text files
├── outputs/ # Generated redacted files
├── gold.json # Manually annotated spans
├── preds.json # Model predictions for eval
│
├── normalize_rtis.py # Text cleanup script
├── redact_demo_updated.py # Main redaction pipeline
├── inference_model.py # Local XLM-R inference script
├── fix_preds.py # Cleans token-level outputs
├── eval_script.py # Evaluates preds vs gold
│
├── xlm_rti_ner_final_more/ # Fine-tuned transformer (folder)
│
└── README.md

⭐ 3. Installation
Create environment
python -m venv .venv
.venv\Scripts\activate # Windows

Install dependencies
pip install torch transformers sentencepiece spacy langdetect evaluate
python -m spacy download en_core_web_sm

⭐ 4. Running the Pipeline

1. Normalize RTI files
   python normalize_rtis.py

2. Generate redactions (light/medium/strong)
   python redact_demo_updated.py

Outputs saved to outputs/.

3. Run XLM-R inference
   python inference_model.py

4. Evaluate
   python eval_script.py gold.json preds.json

⭐ 5. Redaction Modes Explained
🔹 Light Mode (Regex)

Aadhaar

PAN

Phone

Email

PIN

Passport

Strong identifiers only

High precision

No language dependency

🔹 Medium Mode (Regex + spaCy)

Adds PERSON, ADDRESS, DATE (English only)

Good contextual coverage

🔹 Strong Mode (Regex + spaCy + XLM-R)

Full bilingual detection

Best for mixed Hindi-English PII

Captures names, addresses, contextual info

⭐ 6. Evaluation Results (Example)
Entity F1 Score
EMAIL 0.97
PAN 1.00
AADHAAR 0.889
ADDRESS 0.864
PHONE 0.773
OVERALL 0.763

Weak classes (DATE, PIN, VOTER_ID) due to low training examples.

⭐ 7. Future Work

Better BIO alignment using word-id mapping

Data augmentation for rare entity types

Confidence thresholding

UI for uploading & redacting RTIs

Deploy as API (FastAPI/Flask)

⭐ 8. Demo Commands
python inference_model.py
python redact_demo_updated.py

Show:

Before text

LIGHT redaction

MEDIUM redaction

STRONG redaction
