# Citadel AI

Bias monitoring for ML models. Citadel reads predictions from a deployed AWS SageMaker endpoint (or an uploaded CSV), computes fairness metrics, flags threshold violations, explains them in plain language, and stores an audit trail.

## What it does

- **Detects bias** in model predictions: disparate impact, statistical parity difference, equalized odds difference.
- **Two input modes:** connect an AWS account (assume-role, read SageMaker Data Capture logs from S3) or upload a CSV with prediction and group columns.
- **Explains results:** SHAP-based analysis plus a plain-language summary generated with Gemini.
- **Stores audit runs** in Supabase Postgres.

## How it works

```
Frontend (HTML/CSS/JS)
        |
FastAPI
        |
LangGraph governance workflow
  discover -> monitor (SageMaker + S3)   or   ingest CSV
  analyze bias -> detect violations -> remediate -> alert + persist
        |
AWS (SageMaker, S3)  +  Supabase Postgres
```

The workflow is in `backend/app/workflows/`, the bias engine in `backend/app/modules/bias/`, and the AWS connector in `backend/app/integrations/`.

## Tech stack

FastAPI, LangGraph, SHAP, Gemini, AWS (SageMaker, S3, STS AssumeRole), Supabase Postgres, JWT auth (ES256, validated against Supabase's JWKS), vanilla HTML/CSS/JS frontend.

## Results

| Test | Result |
|------|--------|
| Live SageMaker endpoint traffic (235 predictions, from [Citadel-Demo-Model](https://github.com/CheerathAniketh/Citadel-Demo-Model)) | Disparate impact 0.00 against a 0.80 threshold; the model is intentionally biased and Citadel flagged it |
| Adult Income dataset (about 30K rows, CSV upload) | Disparate impact 0.36 |
| CSV upload on three datasets (6 to 30K rows) | Metrics computed and saved to Supabase |
| STS AssumeRole | Verified within one AWS account |

## Run locally

Requires Python 3.12.

```bash
git clone git@github.com:CheerathAniketh/Citadel-AI.git
cd Citadel-AI/backend
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
```

Create a `.env` with the Supabase, Gemini and AWS settings read in `backend/config.py`, then start the API:

```bash
uvicorn main:app --reload
```

## Known limitations

- Cross-account AWS access is untested; it needs a second AWS account.
- There is no hosted demo at the moment.
- Counterfactual fairness testing is not implemented.
