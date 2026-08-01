# Citadel AI — AI Governance & Bias Detection Platform

**EquiLens at the core. Production-grade governance on top.**

Citadel AI is a governance layer that connects to your cloud ML infrastructure (starting with AWS SageMaker), continuously discovers deployed models, monitors their live predictions for bias, and surfaces violations before they become compliance incidents. The bias-detection engine is powered by EquiLens — a validated, working fairness-metrics library (SPD, Disparate Impact, Equalized Odds, SHAP explainability) — wrapped in a LangGraph-orchestrated, continuously-running governance workflow.

> Status: **Private / in development.** This README doubles as the working architecture doc and build checklist ahead of DevThon (Aug 20–21, 2026).

---

## 🎯 What is Citadel AI?

Most AI governance today is manual and periodic — someone runs a fairness audit once a quarter, on a spreadsheet, after the fact. Citadel flips that: connect your cloud account once, and Citadel autonomously discovers models, watches their real predictions, and flags fairness violations continuously — the way a security monitoring tool watches for intrusions, not the way a compliance team files a report.

Two ways in:

- **Upload mode** — drop a CSV, get an instant pre-production bias audit. (This is EquiLens, unchanged.)
- **Connect mode** — link an AWS account, pick a SageMaker endpoint, and Citadel audits it automatically every day (configurable, default 11:00 AM) — plus an on-demand "Run now" for immediate checks.

---

## 🏗️ Architecture

### High-level flow

```
                    ┌─────────────────────────────┐
                    │   Frontend (Next.js/React)  │
                    │  Upload mode │ Connect mode  │
                    └──────────────┬──────────────┘
                                   ↓
                    ┌─────────────────────────────┐
                    │   FastAPI Entry Point        │
                    └──────────────┬──────────────┘
                                   ↓
        ┌──────────────────────────────────────────────────────┐
        │           LangGraph Governance Workflow                │
        │                                                        │
        │   DISCOVER → MONITOR → ANALYZE ──┬─→ COMPLETE          │
        │                                   │   (no violation)   │
        │                                   ↓                    │
        │                              DETECT                    │
        │                                   ↓                    │
        │                          [violation found]              │
        │                                   ↓                    │
        │              REMEDIATE (SHAP-reasoned) → ALERT          │
        │                                   ↓                    │
        │                              COMPLETE                   │
        └──────────────────────────────────────────────────────┘
                                   ↓
        ┌──────────────────────────────────────────────────────┐
        │                 Supporting Modules                     │
        │  • AWS Tool Layer (STS assume-role, SageMaker, S3)     │
        │  • EquiLens Bias Engine (SPD, DI, EOD, SHAP)           │
        │  • Supabase (tenants, endpoints, audit history)        │
        │  • Scheduler (daily audits per registered endpoint)    │
        │  • Alert Service (Slack / Jira)                        │
        └──────────────────────────────────────────────────────┘
```

Key change from the original design: **DETECT now branches conditionally.** A clean audit short-circuits straight to `COMPLETE` instead of always walking through remediation and alerting — this is the actual reason to use a graph orchestrator instead of a flat function pipeline, and it should stay visible in the code, not be optimized away.

### Node-by-node

| Node | What it does | Status |
|---|---|---|
| `discover_models` | Lists real SageMaker endpoints via a bound AWS **tool** (`list_endpoints`), not a hardcoded connector function | ⏳ to build |
| `monitor_predictions` | Pulls inference input/output from SageMaker **Data Capture** logs in S3 | ⏳ to build |
| `analyze_bias` | Calls EquiLens's existing `analyze_bias()`, `compute_intersectionality()`, SHAP explainer directly | ✅ ported from EquiLens |
| `detect_violations` | Checks metrics against policy thresholds; branches to `complete` (clean) or `remediate` (violation) | ⏳ needs conditional edge |
| `remediate` | Reasons over SHAP feature-importance output to recommend a *specific* fix (e.g. "drop `zip_code` — highest bias contribution"), not a static list | ⏳ to build |
| `alert` | Sends Slack/Jira notification, writes to `audit_logs` | ⏳ to build |
| `complete_workflow` | Records execution time, persists run to Supabase | ⏳ needs Supabase fix |

### AWS connection model

- **Cross-account IAM role assumption** (STS `AssumeRole`) — user creates a read-only role in their account trusting Citadel's account. No raw access keys stored, ever.
- Scoped permissions only: `sagemaker:ListEndpoints`, `sagemaker:DescribeEndpoint`, `s3:GetObject` on the data-capture bucket.
- **Data Capture must be enabled** on the target SageMaker endpoint at creation time — this is the prerequisite for `monitor_predictions` to have anything to read. No default logging exists otherwise.

### Data model (Supabase)

```
users
  └─ connected_accounts (role_arn, region)
       └─ registered_endpoints (endpoint_arn, schedule_time)
            └─ audit_runs (run_id, timestamp, status)
                 └─ bias_metrics (di, spd, eod, severity)
                 └─ alerts
```

### Scheduling

- In-process scheduler (APScheduler) triggers `run_governance_check()` per registered endpoint at its configured daily time.
- Same function is exposed via a manual `POST /governance/run-now` endpoint for on-demand checks and demos.
- First connect triggers an immediate run so the user isn't waiting until the next scheduled slot to see value.

---

## 💎 Differentiator features (beyond baseline monitoring)

These are what separate Citadel from "just another dashboard + alerts" tool:

- [ ] **Counterfactual flip testing** — take a real prediction, flip only the protected attribute (same applicant, different gender/race), re-infer live, show the decision change side-by-side. Single most legible, memorable feature in the whole product.
- [ ] **Adversarial fairness probing** — generate synthetic boundary-condition inputs near decision thresholds across protected groups, rather than only watching organic traffic. Reframes Citadel from passive monitor to active red-teamer.
- [ ] **Fairness policy-as-code** — versioned, declarative thresholds (e.g. `DI >= 0.8 for gender`) enforceable in CI/CD, able to block a model deployment on violation. Borrows credibility from an already-trusted pattern (Terraform/OPA-style policy enforcement).
- [ ] **Fleet-wide risk posture view** — all registered models ranked by risk in one screen, security-dashboard style.

---

## 🖥️ Frontend

Dark, dense, data-forward — governance/security tool aesthetic (Linear / Datadog / Wiz), not a playful consumer dashboard.

- [ ] Live-streaming audit log (SSE/websocket) rendering the existing `audit_log` array as it's generated, not as a single end-of-run blob — turns backend data we already produce into a demo-visible "something is happening" moment
- [ ] Counterfactual flip panel as the hero visual
- [ ] Severity color language (green/amber/red) readable at a glance
- [ ] Upload-mode and Connect-mode as two clear entry paths from login
- [ ] Historical bias trend chart per endpoint (DI over time, from `audit_runs`)

---

## ✅ What's already built (from EquiLens / earlier work)

- `calculate_spd()`, `calculate_di()`, `compute_eod()` — real fairness math
- `compute_intersectionality()` — cross-group (e.g. gender × race) analysis
- SHAP-based feature importance
- FastAPI server, CORS, health check, base routing
- LangGraph 7-node sequential skeleton (`graph.py`, `nodes.py`, `state.py`)
- Pydantic Settings config supporting AWS/GCP/Azure/Supabase credentials

## ⏳ To-do (prioritized for Aug 20 build)

### High priority — core loop
- [ ] Real AWS tool layer: `list_endpoints`, `describe_endpoint`, S3 data-capture log fetch — via STS assume-role, not stored keys
- [ ] Fix Supabase connection; create schema (`users`, `connected_accounts`, `registered_endpoints`, `audit_runs`, `bias_metrics`, `alerts`)
- [ ] Conditional edge in graph: skip remediate/alert on clean audits
- [ ] Deploy the intentionally biased hiring model (synthetic data) to a SageMaker endpoint with Data Capture enabled — this is the demo's ground truth
- [ ] Scheduler for daily audits + manual "run now" endpoint
- [ ] End-to-end test: connect → discover → monitor → analyze → detect real violation

### Medium priority — differentiators
- [ ] Counterfactual flip testing node
- [ ] SHAP-reasoned remediation (specific fix, not static list)
- [ ] Slack webhook alert integration

### Frontend
- [ ] Login + two-mode entry (upload / connect AWS)
- [ ] Live audit-log stream UI
- [ ] Counterfactual flip visual
- [ ] Historical trend chart

### Lower priority / post-hackathon
- [ ] GCP / Azure connectors (deliberately deprioritized — AWS-only for demo depth over breadth)
- [ ] Adversarial probing node
- [ ] Fairness policy-as-code + CI/CD gate
- [ ] Jira/GitHub alert integrations
- [ ] Pydantic field renames (`model_id` → `model_identifier`)
- [ ] Unit/integration test suite
- [ ] API authentication (JWT)

---

## 🎓 Key concepts

**Disparate Impact (DI)** — ratio of minority approval rate to majority approval rate. Legal threshold ≥ 0.80 (EEOC 4/5ths rule).

**Statistical Parity Difference (SPD)** — max approval rate minus min approval rate across groups. Flag if > 0.10.

**Equalized Odds Difference (EOD)** — largest gap in true/false positive rate across groups. Flag if > 0.10.

**Intersectionality** — bias analysis across combinations of protected attributes (e.g. gender × race) — a model can look fair on each attribute alone while being unfair for a specific subgroup.

**Counterfactual fairness** — a model is unfair if changing only a protected attribute (holding everything else constant) changes its decision for an otherwise-identical input.

---

## 📚 Stack

FastAPI · LangGraph · LangChain · boto3 (AWS) · Supabase (Postgres) · SHAP · scikit-learn · pandas · React/Next.js frontend

---

## 📄 License

MIT — private repo, not yet public.
