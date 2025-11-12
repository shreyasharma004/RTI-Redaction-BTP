# RTI PII Redaction Project

## Overview

This project aims to automatically redact personally identifiable information (PII) from Indian RTI responses using a hybrid rule-based and NER-based approach.

## Features

- Detects Aadhaar, PAN, phone numbers, emails, postal PINs.
- NER-based redaction of PERSON, ORG, LOCATION, DATE entities.
- Three redaction levels: light, medium, strong.
- Works on multilingual noisy RTI text.

## Folder Structure

- `rtis/` : Input text files.
- `outputs/` : Generated redacted versions.
- `redact_demo.py` : Main script.
- `requirements.txt` : Dependencies.
- `slides/` : Presentation materials.

## Usage

1. `pip install -r requirements.txt`
2. `python redact_demo.py`
3. Outputs appear in `outputs/`.

### Baseline Evaluation (Hybrid Regex + NER)

| Entity      | Precision | Recall    | F1        |
| ----------- | --------- | --------- | --------- |
| PHONE       | ...       | ...       | ...       |
| EMAIL       | ...       | ...       | ...       |
| PAN         | ...       | ...       | ...       |
| AADHAAR     | ...       | ...       | ...       |
| PERSON      | ...       | ...       | ...       |
| **Overall** | **0.213** | **0.833** | **0.339** |

Dataset size: 3 RTI samples (English + bilingual)

## Next Steps

- Build multilingual model using XLM-RoBERTa.
- Evaluate precision/recall on annotated dataset.
- Draft research paper for IEEE submission.
