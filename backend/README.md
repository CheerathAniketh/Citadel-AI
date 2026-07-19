# Citadel AI - AI Governance & Bias Detection Platform

> **Automated fairness monitoring and remediation for AI models across AWS, GCP, and Azure**

## 🎯 What is Citadel AI?

Citadel AI is a backend system that automatically discovers AI models in your cloud environment, monitors their predictions for bias, detects fairness violations, and recommends remediation actions. It uses LangGraph for orchestration and EquiLens bias metrics (Disparate Impact, Statistical Parity Difference, Equalized Odds) to ensure your ML models comply with fairness regulations like EEOC, EU AI Act, and GDPR.

---

## 🏗️ Architecture Overview

### High-Level Flow

```
User API Request
      ↓
┌─────────────────────────────────────────┐
│   FastAPI Entry Point (main.py)         │
└─────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────────────────────────┐
│          LangGraph Governance Workflow (graph.py)               │
│                                                                 │
│  DISCOVER → MONITOR → ANALYZE → DETECT → REMEDIATE → ALERT    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
      ↓
┌─────────────────────────────────────────────────────────────────┐
│                    Workflow Nodes (nodes.py)                    │
│                                                                 │
│  1. discover_models       - Find all ML models in cloud         │
│  2. monitor_predictions   - Fetch recent predictions            │
│  3. analyze_bias          - Compute fairness metrics            │
│  4. detect_violations     - Check if metrics exceed thresholds  │
│  5. remediate             - Suggest fixes                       │
│  6. alert                 - Send notifications                  │
│  7. complete_workflow     - Log execution time                  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
      ↓
┌──────────────────────────────────────────────────────────────────┐
│               Supporting Modules                                │
│                                                                 │
│  • Cloud Connectors (aws_connector, gcp_connector, ...)        │
│  • Bias Analyzer (disparate_impact, statistical_parity, ...)   │
│  • Database (Supabase for audit logs & historical data)        │
│  • Services (alert_service for Slack/Jira integration)         │
│                                                                 │
└──────────────────────────────────────────────────────────────────┘
      ↓
      Response to Client
```

---

## 📁 Project Structure

```
backend/
├── main.py                          # FastAPI app entry point
├── config.py                        # Environment configuration (Pydantic Settings)
├── requirements.txt                 # Python dependencies
├── .env                             # Environment variables (NOT in git)
│
├── app/
│   ├── __init__.py
│   ├── api/                         # API endpoints (REST)
│   │   ├── governance.py            # POST /api/v1/governance/check
│   │   ├── clouds.py                # Cloud provider endpoints
│   │   └── __init__.py
│   │
│   ├── integrations/                # Cloud provider connectors
│   │   ├── aws_connector.py         # AWS SageMaker, S3 integration
│   │   ├── gcp_connector.py         # GCP Vertex AI integration
│   │   ├── azure_connector.py       # Azure ML integration
│   │   └── __init__.py
│   │
│   ├── modules/                     # ML fairness modules
│   │   ├── bias/
│   │   │   ├── analyzer.py          # compute_spd, compute_di, compute_eod
│   │   │   ├── explainer.py         # SHAP explanations (TODO)
│   │   │   ├── trainer.py           # Debiasing model training (TODO)
│   │   │   └── __init__.py
│   │   └── __init__.py
│   │
│   ├── workflows/                   # LangGraph orchestration
│   │   ├── graph.py                 # Workflow graph definition & run_governance_check()
│   │   ├── nodes.py                 # Individual workflow node implementations
│   │   ├── state.py                 # Workflow state schema (CitadelState)
│   │   └── __init__.py
│   │
│   ├── services/                    # Business logic services
│   │   ├── alert_service.py         # Send alerts to Slack/Jira/GitHub
│   │   └── __init__.py
│   │
│   ├── models.py                    # Pydantic models for API requests/responses
│   ├── db.py                        # Database initialization (Supabase)
│   └── __init__.py
│
└── scripts/
    ├── test_governance.py           # Manual testing script
    └── __init__.py
```

---

## ✅ What's Already Built

### 1. **FastAPI Server** (main.py)
- ✅ Server running on `http://localhost:8000`
- ✅ CORS middleware enabled
- ✅ Health check endpoint (`/health`)
- ✅ API routing setup
- ✅ Logging configured

### 2. **API Endpoints** (app/api/governance.py)
- ✅ `POST /api/v1/governance/check` - Full governance workflow
- ✅ `GET /api/v1/governance/status` - Current model status
- ✅ `POST /api/v1/governance/remediate` - Apply fixes
- ✅ `GET /api/v1/governance/report` - Audit reports
- ⚠️ All endpoints return placeholder responses (need real implementation)

### 3. **LangGraph Workflow Orchestration** (app/workflows/)
- ✅ `graph.py` - Workflow definition with 7 sequential nodes
- ✅ `state.py` - State schema (CitadelState TypedDict)
- ✅ `nodes.py` - Node implementations (discover, monitor, analyze, detect, remediate, alert, complete)
- ✅ Async workflow execution
- ✅ Audit logging through all steps

### 4. **Bias Analysis Module** (app/modules/bias/analyzer.py)
- ✅ `calculate_spd()` - Statistical Parity Difference
- ✅ `calculate_di()` - Disparate Impact (EEOC 4/5ths rule)
- ✅ `compute_eod()` - Equalized Odds Difference
- ✅ `analyze_bias()` - Full bias analysis on dataframe
- ✅ `compute_intersectionality()` - Cross-group analysis (gender × race, etc.)
- ✅ Group statistics computation
- ✅ Severity classification

### 5. **Configuration** (config.py)
- ✅ Pydantic Settings for environment variables
- ✅ Support for AWS, GCP, Azure credentials
- ✅ Supabase configuration
- ✅ API key management (Gemini, Slack)

---

## ⏳ What Still Needs to Be Built

### 1. **Cloud Connectors** (HIGH PRIORITY)
Currently placeholders — need real implementations:

**AWS Connector** (app/integrations/aws_connector.py)
- [ ] `discover_models()` - List SageMaker endpoints
- [ ] `get_predictions()` - Fetch prediction logs from S3/CloudWatch
- [ ] Authentication with boto3

**GCP Connector** (app/integrations/gcp_connector.py)
- [ ] `discover_models()` - List Vertex AI models
- [ ] `get_predictions()` - Fetch from BigQuery prediction logs
- [ ] Authentication with google-cloud

**Azure Connector** (app/integrations/azure_connector.py)
- [ ] `discover_models()` - List Azure ML models
- [ ] `get_predictions()` - Fetch from Azure Synapse/CosmosDB
- [ ] Authentication with azure-identity

### 2. **Database Integration** (HIGH PRIORITY)
- [ ] Fix Supabase connection in `app/db.py`
- [ ] Create tables: `models`, `predictions`, `bias_metrics`, `audit_logs`, `alerts`
- [ ] Implement CRUD operations
- [ ] Store historical bias metrics for trending

### 3. **Bias Explainer** (MEDIUM PRIORITY)
Currently returns placeholder — implement SHAP explanations:
- [ ] `explain_bias()` in `app/modules/bias/explainer.py`
- [ ] Use SHAP to identify which features drive bias
- [ ] Return top N contributing features

### 4. **Alert Service** (MEDIUM PRIORITY)
Currently logs to audit trail only — add real integrations:
- [ ] Slack webhook integration (app/services/alert_service.py)
- [ ] Jira ticket creation
- [ ] GitHub issue creation
- [ ] Email notifications

### 5. **Models & Validation** (LOW PRIORITY)
Fix Pydantic model warnings:
- [ ] Rename `model_id` → `model_identifier` (avoid pydantic protected namespace)
- [ ] Rename `model_name` → `model_display_name`
- [ ] Add proper validation for all request/response schemas

### 6. **Testing** (LOW PRIORITY)
- [ ] Unit tests for bias metrics (pytest)
- [ ] Integration tests for workflows
- [ ] Mock cloud connector tests
- [ ] API endpoint tests

---

## 🚀 Current Status

**Server is running!** ✅

```bash
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Application startup complete
```

**Test it:**
```bash
curl http://localhost:8000/health
# {"status":"healthy","app":"Citadel AI","version":"0.1.0"}
```

**Access API docs:**
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 🔧 Local Setup & Running

### Prerequisites
- Python 3.10+
- pip & virtualenv

### Installation

1. **Clone and navigate to backend:**
```bash
cd backend
```

2. **Create virtual environment:**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. **Install dependencies:**
```bash
pip install -r requirements.txt
```

4. **Create `.env` file** (in backend/ directory):
```env
APP_NAME=Citadel AI
APP_VERSION=0.1.0
DEBUG=True

SUPABASE_URL=http://localhost:54321
SUPABASE_KEY=test_key_12345

AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
AWS_REGION=us-east-1

GCP_PROJECT_ID=
GCP_CREDENTIALS_JSON=

AZURE_SUBSCRIPTION_ID=
AZURE_TENANT_ID=
AZURE_CLIENT_ID=
AZURE_CLIENT_SECRET=

GEMINI_API_KEY=
SLACK_WEBHOOK_URL=

HOST=0.0.0.0
PORT=8000
```

5. **Run the server:**
```bash
python main.py
```

Server starts on `http://localhost:8000`

---

## 📝 Data Flow Example

### When you POST to `/api/v1/governance/check`:

```
1. Request arrives at governance.py endpoint
   ↓
2. Calls run_governance_check() from graph.py
   ↓
3. Creates initial CitadelState with:
   - user_id, cloud_provider, cloud_credentials
   - empty discovered_models, bias_metrics, alerts
   ↓
4. LangGraph executes nodes sequentially:
   
   [DISCOVER] 
   → Calls AWS/GCP/Azure connector
   → Discovers 5 models (e.g., "credit_classifier", "loan_approver")
   → Sets state['discovered_models'] = [...]
   ↓
   
   [MONITOR]
   → For each model, fetches last 1000 predictions
   → Sets state['recent_predictions'] = [...]
   ↓
   
   [ANALYZE]
   → Computes bias metrics on predictions:
     • Disparate Impact (DI) = 0.72 (VIOLATION: <0.8)
     • Statistical Parity Diff (SPD) = 0.15
     • Equalized Odds Diff (EOD) = 0.22
   → Sets state['bias_metrics'] = {...}
   ↓
   
   [DETECT]
   → Checks: DI < 0.8? YES → CRITICAL VIOLATION
   → Creates alert: "DI 0.72 below legal threshold"
   → Sets state['alerts'] = [...] & state['needs_remediation'] = True
   ↓
   
   [REMEDIATE]
   → Analyzes root causes (would use SHAP if implemented)
   → Suggests 3 fixes:
     1. Retrain model with balanced data
     2. Drop feature 'zip_code' (proxy for race)
     3. Collect more minority group data
   → Sets state['recommended_fixes'] = [...]
   ↓
   
   [ALERT]
   → Logs alerts to audit_log
   → TODO: Send to Slack/Jira
   ↓
   
   [COMPLETE]
   → Records execution time: 2345ms
   → Sets workflow_status = "completed"
   ↓
5. Returns response to client with full state:
{
  "workflow_status": "completed",
  "discovered_count": 5,
  "bias_metrics": {"disparate_impact": 0.72, ...},
  "alerts": [{"type": "bias_critical", "message": "..."}],
  "recommended_fixes": [...],
  "audit_log": [
    "🚀 Governance check initiated",
    "✅ Discovered 5 models",
    "✅ Fetched 5000 predictions",
    "✅ Bias analysis: DI=0.72, Status=critical",
    "🔴 1 violation detected",
    ...
  ],
  "execution_time_ms": 2345
}
```

---

## 🎓 Key Concepts

### **Disparate Impact (DI)**
- Ratio: minority_approval_rate / majority_approval_rate
- **Legal threshold:** ≥ 0.80 (EEOC 4/5ths rule)
- **Example:** If 80% of majority group approved vs 60% of minority → DI = 0.75 (ILLEGAL)

### **Statistical Parity Difference (SPD)**
- Difference: max_approval_rate - min_approval_rate
- **Red flag:** > 0.10 (10% difference)
- **Example:** 80% vs 70% approval → SPD = 0.10 (borderline)

### **Equalized Odds Difference (EOD)**
- Max difference in True Positive Rate & False Positive Rate across groups
- **Red flag:** > 0.10
- **Ensures:** Model makes mistakes equally across all groups

### **Intersectionality**
- Bias analysis across multiple sensitive attributes simultaneously
- **Example:** Analyze bias for (gender × race) combinations
- **Why:** A model can be fair on gender alone but unfair for Black women specifically

---

## 🔌 Next Steps (Priority Order)

### Phase 1: Make It Work (This Week)
1. Implement AWS connector (most common cloud platform)
2. Fix Supabase connection & create database schema
3. Add mock cloud data for local testing
4. Test full workflow end-to-end

### Phase 2: Expand Coverage (Next Week)
1. Implement GCP and Azure connectors
2. Implement SHAP bias explainer
3. Build alert_service (Slack/Jira)
4. Add comprehensive error handling

### Phase 3: Production Ready (Week After)
1. Write unit & integration tests
2. Add API authentication (JWT)
3. Deploy to staging environment
4. Performance optimization (caching, DB indexing)

---

## 📚 Dependencies Overview

```
FastAPI 0.109.0         → REST API framework
uvicorn 0.27.0          → ASGI server
LangGraph 0.1.14        → Workflow orchestration
LangChain 0.2.0         → LLM integrations (future use)
SQLAlchemy 2.0.25       → ORM for database
Supabase 2.4.0          → PostgreSQL serverless DB
Pydantic 2.5.0          → Data validation
boto3 1.28.85           → AWS SDK
google-cloud-*          → GCP SDKs
azure-*                 → Azure SDKs
pandas 2.1.3            → Data analysis
scikit-learn 1.3.2      → ML utilities
SHAP 0.49.1             → Model explainability
```

---

## 🛠️ Troubleshooting

### Server won't start: "Invalid API key"
**Solution:** Comment out Supabase init in `app/db.py`, use dummy credentials in `.env`

### Import errors: "cannot import name X"
**Solution:** Check function names match between files (e.g., `calculate_spd` vs `compute_spd`)

### Workflow hangs
**Solution:** Cloud connectors are placeholders — they'll timeout. Add error handling.

### Pydantic warnings about "model_"
**Solution:** Rename fields in models.py (model_id → model_identifier)

---

## 📞 Questions?

- **How do I add a new cloud provider?** → Create new connector in `app/integrations/`, implement `discover_models()` and `get_predictions()`
- **How do I add a new bias metric?** → Add function to `app/modules/bias/analyzer.py`, call from `analyze_bias` node
- **How do I customize thresholds?** → Edit detect_violation() node logic in `app/workflows/nodes.py`
- **How do I integrate with Slack?** → Implement in `app/services/alert_service.py`, call from alert node

---

## 📄 License

MIT

---

**Built with ❤️ for fairness in AI**