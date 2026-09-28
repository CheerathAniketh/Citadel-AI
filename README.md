# Citadel AI
**AI Governance & Bias Detection for ML Models**

Detect algorithmic bias in production ML models before they become compliance incidents. Citadel AI continuously monitors your cloud models (AWS SageMaker) for fairness violations, auto-generates remediation recommendations with explainability, and persists audit trails for compliance.

---

## Problem
Production ML models can perpetuate discrimination unknowingly. Manual audits are slow. Regulatory penalties for unfair hiring, lending, or insurance decisions are severe. Teams need continuous, automated fairness monitoring that surfaces violations in real time.

## Our Solution
Citadel AI bridges that gap—a governance layer that:
- **Detects bias** in live SageMaker predictions (Disparate Impact, Statistical Parity, Equalized Odds)
- **Generates remediation** suggestions backed by SHAP explainability
- **Persists audit trails** for compliance (SOC 2, Fair Lending Act, Title VII)
- **Works with your data** — upload CSVs or connect your AWS account for real production data

---

## Results
- ✅ **Live validation** — tested against real SageMaker endpoints and 30K+ row bias-detection datasets
- ✅ **Production-ready** — JWT auth, Supabase persistence, AWS STS assume-role support
- ✅ **End-to-end** — unified bias engine across connect-mode (live AWS data) and upload-mode (CSV)
- 🎯 **Deployed** — live demo on Render with real AWS integration

---

## Tech Stack
**Backend:** FastAPI · LangGraph (agentic workflows)  
**AI/Fairness:** EquiLens (SPD, DI, EOD metrics) · SHAP explainability · Groq/LLM for remediation  
**Infrastructure:** AWS SageMaker · S3 Data Capture · STS AssumeRole  
**Data:** Supabase Postgres · JWT Auth (ES256 via Google OAuth)  
**Frontend:** Vanilla HTML/CSS/JS (dark, data-forward design)

---

## Quick Start
```bash
# Clone & install
git clone https://github.com/CheerathAniketh/Citadel-AI
cd Citadel-AI
python3.12 -m venv venv && source venv/bin/activate
pip install -r requirements.txt

# Set up .env (Supabase + Groq + AWS credentials)
cp .env.example .env
# Fill in: SUPABASE_URL, SUPABASE_ANON_KEY, GROQ_API_KEY, AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY

# Start the server
uvicorn api/main:app --reload
# Visit http://localhost:8000
```

---

## Key Features
### Connect Mode (Live AWS)
Connect your AWS account via IAM role assumption. Citadel auto-discovers SageMaker endpoints, reads live Data Capture logs from S3, and analyzes predictions in real time.

```bash
# Example: analyze live predictions from your endpoint
curl -X POST http://localhost:8000/api/v1/governance/check \
  -H "Authorization: Bearer <your-jwt>" \
  -d '{
    "iam_role_arn": "arn:aws:iam::123456789:role/CitadelReadOnly",
    "region": "us-east-1"
  }'
```

### Upload Mode (CSV)
No AWS? Upload a CSV with prediction and group columns. Citadel analyzes for bias instantly.

```bash
curl -X POST http://localhost:8000/api/v1/governance/analyze-csv \
  -H "Authorization: Bearer <your-jwt>" \
  -F "file=@predictions.csv"
```

### Real-Time Governance Report
Unified response format across both modes—metrics, violations, remediation suggestions, audit trail.

```json
{
  "workflow_status": "complete",
  "bias_metrics": {
    "disparate_impact": 0.65,
    "statistical_parity_diff": 0.25,
    "equalized_odds_diff": 0.18
  },
  "violations": [
    {
      "metric": "disparate_impact",
      "severity": "critical",
      "threshold": 0.80,
      "message": "Hiring rate for protected group is 65% of majority group"
    }
  ],
  "root_causes": ["Gender bias in feature: 'years_experience'", ...],
  "audit_run_id": "4cfc594f-8ddc-4ebf-b8fa-a49b1340d4a3",
  "timestamp": "2026-09-15T12:34:56Z"
}
```

---

## Validation
- ✅ **Real AWS data** — 235+ live SageMaker predictions tested; DI=0.00, SPD=0.37 (critical bias detected)
- ✅ **Kaggle benchmark** — Adult Income dataset (30K rows); DI=0.36 matches published literature
- ✅ **CSV upload** — tested on 3 datasets (6 rows → 30K rows); bias metrics persist to Supabase
- ✅ **Auth verified** — ES256 JWT validation against Supabase's live JWKS endpoint
- ✅ **Cross-account IAM** — STS AssumeRole fully verified (same-account); true cross-account pending second AWS account for testing

---

## Architecture
```
Frontend (HTML/CSS/JS)
        ↓
FastAPI Entry Point
        ↓
LangGraph Governance Workflow
├─ DISCOVER → MONITOR (AWS SageMaker + S3)
├─ INGEST_CSV (upload mode)
├─ ANALYZE_BIAS (EquiLens metrics)
├─ DETECT_VIOLATION (threshold logic)
├─ REMEDIATE (SHAP-reasoned suggestions)
└─ ALERT & PERSIST (Supabase audit trail)
        ↓
AWS SageMaker / S3 + Supabase Postgres
```

See [DEVELOPMENT.md](./DEVELOPMENT.md) for full architecture, schema, and known limitations.

---

## Security
- ✅ JWT auth (ES256 via Google OAuth)
- ✅ AWS STS assume-role (no raw access keys stored)
- ✅ RLS-enabled Supabase tables (backend uses service_role)
- ✅ Scoped IAM permissions (ListEndpoints, S3 read-only)
- ✅ CORS locked to deployed domain

---

## Next Steps (Future Scope)
- Counterfactual fairness testing (flip protected attributes, re-infer, compare decisions)
- Real-time alerting (Slack, Jira)
- Cross-account AWS support (requires stable service identity)
- Adversarial fairness probing (synthetic boundary-condition inputs)

---

## Team
**Aniketh Cheerath** — Backend (FastAPI, LangGraph, AWS integration, Supabase), Frontend (HTML/CSS/JS, Google OAuth, metric visualization)

---

## License
MIT (private repo, not yet public)

---

## Links
- **GitHub:** github.com/CheerathAniketh/Citadel-AI
- **LinkedIn:** linkedin.com/in/cheerathaniketh
- **Deployed Demo:** [Live on Render](https://citadel-ai-demo.render.com) *(pending final deployment)*
