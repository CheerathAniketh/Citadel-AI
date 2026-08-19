# Citadel AI — AI Governance & Bias Detection Platform

**EquiLens at the core. Production-grade governance on top.**

Citadel AI is a governance layer that connects to your cloud ML infrastructure (AWS SageMaker), continuously discovers deployed models, monitors their live predictions for bias, and surfaces violations before they become compliance incidents. The bias-detection engine is powered by EquiLens — a validated, working fairness-metrics library (SPD, Disparate Impact, Equalized Odds, SHAP explainability) — wrapped in a LangGraph-orchestrated governance workflow.

> Status: **Private / in development.** DevThon is **Aug 20–21, 2026** — this doc is the architecture reference, build log, and task board. Keep it updated as things change.

---

## 🚨 Right now — what's actually blocking the demo

Backend and frontend are both feature-complete and verified end-to-end through the real UI (see [What's working](#-whats-working-verified-end-to-end) below). The only thing standing between here and a live demo is **deployment**:

- [ ] **Render deploy** — static AWS access keys as env vars (Render has no local `~/.aws/credentials`), `ALLOWED_ORIGINS` set to the deployed frontend's real domain, Supabase OAuth redirect URI updated for that domain
- [ ] **Google OAuth consent screen** — still in "Testing" mode; either add judges as test users or publish the app, or a judge signing in with their own Google account gets rejected
- [ ] **Full smoke test against the deployed URL** — login → upload-mode → connect-mode → status/report, not just localhost

Everything else below (RLS policies, `upsert_model` user scoping, `/governance/remediate`, `clouds.py`, counterfactual flip node) is real but **non-blocking** — parked deliberately, don't touch before the demo.

---

## 👥 Team & ownership

| Person | Focus |
|---|---|
| **Aniketh** | Backend (LangGraph workflow, bias-engine wiring, Supabase persistence, API layer, AWS integration, JWT auth) **and**, as of Aug 13, frontend as well — both fully built and verified against real infrastructure, not mocks. |
| **Akanksha** | Original frontend owner (login, upload, connect screens) and demo-day plan: connecting her own AWS account as a genuine end user to show the product from a fresh user's perspective. Became unavailable Aug 13; Aniketh absorbed frontend from that point. Re-confirm her role/availability before the demo. |

**Scope decision:** AWS-only for the hackathon — GCP/Azure connectors deleted (`gcp_connector.py`, `azure_connector.py` removed).

**Demo split plan (pending Akanksha availability):** Aniketh shows terminal + Supabase (technical depth); Akanksha connects her own AWS account and demos the live UI as a real end user — two angles on the same real product, not a scripted mock. If she's not available, fall back to a single-presenter demo covering both.

---

## 🏗️ Architecture

### High-level flow

```
                    ┌─────────────────────────────┐
                    │   Frontend (HTML/CSS/JS)     │
                    │  Upload mode │ Connect mode  │
                    └──────────────┬──────────────┘
                                   ↓
                    ┌─────────────────────────────┐
                    │   FastAPI Entry Point        │
                    └──────────────┬──────────────┘
                                   ↓
        ┌──────────────────────────────────────────────────────┐
        │           LangGraph-style Governance Workflow          │
        │                                                        │
        │  Connect mode: DISCOVER → MONITOR ─┐                   │
        │  Upload mode:  INGEST_CSV ──────────┤                  │
        │                                     ↓                  │
        │                                ANALYZE ──┬─→ COMPLETE  │
        │                                           │ (no violation)│
        │                                           ↓             │
        │                                      DETECT             │
        │                                           ↓             │
        │                                  [violation found]      │
        │                                           ↓             │
        │                      REMEDIATE (SHAP-reasoned) → ALERT  │
        │                                           ↓             │
        │                                      COMPLETE           │
        └──────────────────────────────────────────────────────┘
                                   ↓
        ┌──────────────────────────────────────────────────────┐
        │                 Supporting Modules                     │
        │  • AWS Tool Layer (STS assume-role, SageMaker, S3) ✅ LIVE│
        │  • EquiLens Bias Engine (SPD, DI, EOD, SHAP)           │
        │  • Supabase (tenants, endpoints, audit history) ✅ LIVE│
        │  • Auth (Supabase JWT, Google sign-in) ✅ LIVE          │
        │  • Scheduler (daily audits per registered endpoint) — not started│
        │  • Alert Service (Slack / Jira) — not started           │
        └──────────────────────────────────────────────────────┘
```

**Key design note:** DETECT branches conditionally — a clean audit short-circuits toward `COMPLETE` instead of always walking through remediation and alerting. Verified on real data: `true_unbiased.csv` (DI=0.98) took the clean-audit branch; biased datasets and the real AWS endpoint both walked the full violation branch.

**Upload mode and Connect mode share everything downstream of ingestion.** `ingest_csv()` populates the same `discovered_models` / `recent_predictions` state shape that `discover_models()` + `monitor_predictions()` populate for AWS — so `analyze_bias`, `detect_violation`, `remediate`, `alert`, and `complete_workflow` (including persistence) run identically regardless of data source. Zero duplicated logic between the two modes.

### Node status

| Node | What it does | Status |
|---|---|---|
| `discover_models` | Lists real SageMaker endpoints via `AWSConnector` | ✅ verified, both static keys and STS AssumeRole (same-account) |
| `monitor_predictions` | Pulls prediction data from discovered models | ✅ real S3 Data Capture parsing — `get_predictions()` pulls, lists, parses real `.jsonl` objects from S3 |
| `ingest_csv` | Upload-mode equivalent of discover+monitor — treats an uploaded CSV as one synthetic model | ✅ validated against 3 datasets |
| `analyze_bias` | Calls EquiLens's real `analyze_bias()` / `compute_eod()` | ✅ validated against a literature-known dataset and real live AWS traffic |
| `detect_violation` | Checks DI/SPD/EOD against thresholds, sets `needs_remediation` | ✅ both branches confirmed on real data |
| `remediate` | Suggests fixes; SHAP top-features if available, generic otherwise | ⚠️ generic-only — SHAP unavailable in the live flow (see below) |
| `alert` | Logs to `audit_log`; no external notification yet | ⚠️ audit-log only, no Slack/Jira |
| `complete_workflow` | Records execution time, finalizes `workflow_status`, persists to Supabase under the real user | ✅ verified live across both modes |

**SHAP note:** `get_shap_values(model, X_train, X_test)` needs a *trained model artifact*, not just prediction input/output. Neither pipeline loads one, so SHAP is explicitly marked unavailable (`root_causes.note`) rather than faked. Unscoped: pull from SageMaker model registry, or require a separate artifact upload? Needs a decision — not happening before the hackathon.

### 📄 Upload mode

`POST /api/v1/governance/analyze-csv` — multipart file upload, `Authorization: Bearer <token>` required.

Required columns: `prediction`, `group`. Optional: `actual_label` (enables EOD). The frontend's column picker (added Aug 17) lets users map their real headers to these canonical names client-side before upload — no backend change needed.

**Validated against:**

| Dataset | Rows | DI | SPD | Result |
|---|---|---|---|---|
| Synthetic obvious-bias | 6 | 0.00 | 1.00 | ✅ critical violation, full remediation+alert+persist chain |
| Adult Income (Kaggle) | 30,162 | 0.36 | 0.20 | ✅ matches literature DI for this split — external validation of EquiLens's math. 349ms. |
| `true_unbiased.csv` | 1,000 | 0.98 | 0.013 | ✅ clean-audit branch, remediate/alert correctly early-return |

All three persisted correctly to Supabase (`audit_runs`+`models` every run, `bias_metrics` every run, `alerts` only on the two biased runs).

**Known, accepted tradeoff:** `analyze_bias` pools all rows into one aggregate DI/SPD/EOD; CSV mode is always exactly one synthetic model so this is fine, but if Connect mode ever discovers multiple real endpoints, per-model `bias_metrics` would currently duplicate the same pooled number rather than compute independently. Flagged, not fixed.

### 🔌 Connect mode

`get_predictions()` in `aws_connector.py` reads real data, not mocks:

1. `describe_endpoint()` → `describe_endpoint_config()` dynamically discovers `DataCaptureConfig.DestinationS3Uri` — no hardcoded bucket, works for any account/endpoint.
2. Lists + reads real `.jsonl` Data Capture objects from S3 directly (no local disk writes).
3. Parses SageMaker's double-JSON-encoded capture envelope (`captureData.endpointInput.data` / `endpointOutput.data` are themselves JSON strings needing a second `json.loads()`).
4. Maps numeric `gender: 0/1` to `'Female'/'Male'` before handing rows to the bias engine.

**Live test (Aug 8, real curl → real endpoint → real S3 → real Supabase):** discovered `citadel-biased-hiring-endpoint/AllTraffic`, 235 samples, DI=0.00, SPD=0.3694, `high` status, critical alert fired for DI below the 0.8 legal threshold. Independently confirmed against `traffic.py`'s raw findings (male hire rate 0.369, female 0.000).

**Bug found + fixed:** first attempt returned `models_discovered: 0` with valid credentials — root cause was a region mismatch (`us-east-1` in the request vs. `ap-south-1` where the endpoint actually lives). SageMaker discovery is region-scoped. Still returns a silent `0` rather than a clear error on mismatch — flagged, not fixed.

### AWS connection model

- **Cross-account IAM role assumption (STS AssumeRole)** is the target design — user creates a read-only role trusting Citadel's account, no raw access keys stored. Falls back to static keys only for local dev when no `iam_role_arn` given.
- Scoped permissions: `sagemaker:ListEndpoints`, `DescribeEndpoint`, `DescribeEndpointConfig`, `s3:GetObject`+`ListBucket` on the data-capture bucket.
- Data Capture must be enabled on the target endpoint at creation time.
- **✅ Same-account AssumeRole fully verified** (Aug 13) — real handshake, real `AWSConnector` call with only `iam_role_arn`, and a full real API → JWT → STS → S3 → EquiLens → Supabase run (audit_run `4cfc594f-8ddc-4ebf-b8fa-a49b1340d4a3`).
- **⚠️ True cross-account still unverified.** Needs a second AWS account (Akanksha's) with its own trust-policy role. Depends on Akanksha's availability — see [demo split plan](#-team--ownership).
- **⚠️ "Who is Citadel" identity gap:** right now AssumeRole works because the backend inherits Aniketh's local `~/.aws/credentials`. A real external user's trust policy needs a stable, known Citadel service identity — not "whoever's laptop is running uvicorn." Explicitly parked post-hackathon; not blocking the two-account demo, blocking genuine public use.

### 🔐 Auth — JWT via Supabase

- Frontend: `supabase.auth.signInWithOAuth({ provider: 'google' })` → session with a real JWT → attached as `Authorization: Bearer <token>` on every call.
- Backend: `app/auth.py`'s `get_current_user` dependency verifies the JWT and returns the real `user_id`, which flows into persistence.
- **Gotcha:** this Supabase project issues asymmetric **ES256**-signed JWTs (newer signing-keys system), not legacy shared-secret HS256. Verified against Supabase's public JWKS endpoint (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`).
- `/governance/check`, `/governance/analyze-csv`, `/governance/status`, `/governance/report` are all behind auth now (status/report added Aug 13). None are yet scoped *by owner* — see `upsert_model` note below.

**Google OAuth setup:** Google Cloud Console → OAuth consent screen (External, currently "Testing", team added as test users) → OAuth Client (Web) → redirect URI `https://qxsyscrbnbrzzvctozht.supabase.co/auth/v1/callback` → Client ID/Secret into Supabase's Google provider settings.

### Data model (Supabase)

```
users
  └─ connected_accounts (role_arn, region)
       └─ registered_endpoints (endpoint_arn, schedule_time)
       └─ models (cloud_provider, model_id, model_name, last_monitored)
            └─ audit_runs (id, user_id, cloud_provider, status, models_discovered, execution_time_ms, error)
            └─ bias_metrics (model_id, di, spd, eod, samples_count)
            └─ alerts (model_id, alert_type, severity, message, metric_value, threshold, status)
```

`complete_workflow` writes a real `audit_runs` row every run, plus `models`/`bias_metrics`/`alerts` whenever a model was discovered, tied to the real authenticated user.

RLS is enabled on all tables; backend uses the `service_role` key so it bypasses RLS by design. Real per-user RLS policies (`user_id = auth.uid()`) are deferred defense-in-depth — not needed for frontend correctness since frontend never talks to Supabase directly.

**Known gap, deliberately not fixed:** `upsert_model()` doesn't set `user_id`, and the table's uniqueness key is still `(cloud_provider, model_id)`, not `(cloud_provider, model_id, user_id)`. Two users reusing the same `model_id` string would silently reassign the row rather than create separate ones. A fix was prototyped Aug 13 but not landed — needs the composite-key change done properly.

---

## 💎 Differentiator features (not built)

- [ ] **Counterfactual flip testing** — flip only the protected attribute on a real prediction, re-infer, show the decision change side-by-side. Most legible, memorable feature in the product — currently just a planned frontend panel, no backend node exists yet.
- [ ] **Adversarial fairness probing** — synthetic boundary-condition inputs near decision thresholds.
- [ ] **Fairness policy-as-code** — versioned, declarative thresholds enforceable in CI/CD.
- [ ] **Fleet-wide risk posture view** — all registered models ranked by risk.

---

## 🖥️ Frontend

Vanilla HTML/CSS/JS, no build step, in `frontend/`: `index.html`, `style.css`, `config.js`, `app.js`. Dark, dense, data-forward aesthetic (Linear / Datadog / Wiz).

**Done, verified through the real UI (not just curl):**
- [x] Login — Google sign-in via Supabase Auth
- [x] Upload-mode screen — CSV upload with column picker (maps real headers → `prediction`/`group`/`actual_label` client-side) → renders DI/SPD/EOD metric cards, color-coded status badges, alerts, recommendations
- [x] Connect-mode screen — AWS account ID / region / IAM role ARN form → real STS AssumeRole → real S3 predictions → same rendering path as upload mode (`renderGovernanceResponse` in `app.js`)
- [x] Status & Reports tab — proper metric cards + badges (`renderStatusResponse`, `renderReportResponse`), collapsible raw-JSON view for debugging

**Not built:**
- [ ] Audit history view (`audit_runs`/`bias_metrics`/`alerts`, via backend endpoints)
- [ ] Live-streaming audit log (SSE/websocket)
- [ ] Counterfactual flip panel (hero visual — blocked on the backend node not existing)
- [ ] Historical bias trend chart per endpoint (DI over time)

`config.js` isolates `SUPABASE_URL`/`SUPABASE_ANON_KEY`/`API_BASE_URL` — the one file to edit when moving from `localhost:8000` to the deployed Render URL.

---

## ✅ What's working (verified end-to-end)

- FastAPI starts cleanly; CORS scoped to real allowed origins; health check live
- Real Supabase connection confirmed against the live hosted project
- Governance workflow runs fully async end-to-end for both modes without crashing
- Real AWS auth confirmed both ways (rejects bad creds, succeeds with real creds)
- Real S3 Data Capture parsing — 235+ real predictions fetched, parsed, analyzed from a live endpoint
- Real JWT auth end-to-end — Google sign-in → ES256 JWT → verified against Supabase JWKS → real `user_id` flows through the full workflow into Supabase
- EquiLens's real `calculate_spd`, `calculate_di`, `compute_eod` validated against a literature-matching Kaggle dataset and real live AWS traffic
- Persistence fully working across both modes, including real AWS runs and real authenticated users
- Conditional graph branching (clean-audit short-circuit) confirmed on real data
- Same-account STS AssumeRole fully verified end-to-end through the real API
- `bias_metrics` response shape unified across `/governance/check` and `/governance/analyze-csv` via one shared `build_governance_response()` — the two routes can no longer structurally diverge
- AWS-only: GCP/Azure code fully deleted

---

## ⏳ To-do

### Blocking the demo
- [ ] Render deployment: static AWS keys as env vars, `ALLOWED_ORIGINS` → deployed frontend domain, Supabase redirect URI → deployed domain
- [ ] Google OAuth consent screen out of "Testing" mode (or judges added as test users)
- [ ] Full smoke test against the deployed URL, all three flows

### Worth doing if time allows (non-blocking, low risk)
- [ ] Route the CSV column-mismatch hard-fail through `_resolve_columns()`'s `did_you_mean`/`available_columns` (currently the hard-fail check runs before that function ever gets called)
- [ ] Clean up `.env` parse warnings (cosmetic, harmless)

### Deliberately parked — do not touch before the demo
- [ ] Real STS AssumeRole cross-account (needs Akanksha's second AWS account)
- [ ] Real per-user RLS policies
- [ ] `upsert_model()` user_id + composite uniqueness key fix
- [ ] `/governance/remediate` — still a stub
- [ ] `clouds.py` — connect/list/disconnect/test all placeholder-only
- [ ] Clearer error for Connect-mode region mismatch (currently silently returns 0 models)
- [ ] `INIT_SQL` doc drift (`audit_runs` missing from the doc, matches an already-fixed live bug)
- [ ] Counterfactual flip node + panel
- [ ] SHAP-reasoned remediation (blocked on model-artifact-loading decision)
- [ ] Slack/Jira alert integrations
- [ ] Scheduler (APScheduler) + manual "run now"
- [ ] Adversarial probing, fairness-policy-as-code, `model_id`→`model_identifier` rename, test suite

---

## 🎓 Key concepts

**Disparate Impact (DI)** — ratio of minority approval rate to majority approval rate. Legal threshold ≥ 0.80 (EEOC 4/5ths rule).

**Statistical Parity Difference (SPD)** — max approval rate minus min approval rate across groups. Flag if > 0.10.

**Equalized Odds Difference (EOD)** — largest gap in true/false positive rate across groups. Flag if > 0.10.

**Intersectionality** — bias across combinations of protected attributes (e.g. gender × race) — a model can look fair on each attribute alone while being unfair for a specific subgroup.

**Counterfactual fairness** — a model is unfair if changing only a protected attribute (holding everything else constant) changes its decision for an otherwise-identical input.

---

## 🔧 Useful AWS commands (Test-Model repo)

Live in the sibling `Test-Model` repo — the intentionally-biased hiring model used as Citadel's demo ground truth.

```bash
# Check what's running / billing
aws sagemaker list-endpoints --region ap-south-1 --query 'Endpoints[*].{Name:EndpointName,Status:EndpointStatus}' --output table

# Deploy the model
python deploy.py

# Send synthetic traffic (fresh Data Capture logs)
python traffic.py

# Delete endpoint + config — always clean up before/after a session
aws sagemaker delete-endpoint --endpoint-name citadel-biased-hiring-endpoint --region ap-south-1
aws sagemaker delete-endpoint-config --endpoint-config-name citadel-biased-hiring-endpoint --region ap-south-1

# List captured Data Capture files
aws s3 ls s3://citadel-ai-demo-aniketh-447788060954-v1/citadel-demo/data-capture/citadel-biased-hiring-endpoint/AllTraffic/ --recursive

# Pull one capture file to inspect format
aws s3 cp s3://citadel-ai-demo-aniketh-447788060954-v1/citadel-demo/data-capture/citadel-biased-hiring-endpoint/AllTraffic/<path>.jsonl ./sample_capture.jsonl
head -n 2 sample_capture.jsonl

# CloudWatch logs (container-side failures)
aws logs describe-log-streams \
  --log-group-name /aws/sagemaker/Endpoints/citadel-biased-hiring-endpoint \
  --region ap-south-1 --order-by LastEventTime --descending --max-items 5 \
  --query "logStreams[*].{Name:logStreamName,LastEvent:lastEventTimestamp}" --output table

aws logs get-log-events \
  --log-group-name /aws/sagemaker/Endpoints/citadel-biased-hiring-endpoint \
  --log-stream-name "<paste-stream-name>" \
  --region ap-south-1 --limit 100

# IAM role trust + policies (if permission errors come back)
aws iam get-role --role-name CitadelSageMakerExecutionRole --query 'Role.AssumeRolePolicyDocument'
aws iam list-attached-role-policies --role-name CitadelSageMakerExecutionRole
aws iam list-role-policies --role-name CitadelSageMakerExecutionRole
aws iam get-role-policy --role-name CitadelSageMakerExecutionRole --policy-name CitadelS3BucketAccess

# SageMaker instance quotas (before requesting a larger instance)
aws service-quotas list-service-quotas \
  --service-code sagemaker --region ap-south-1 \
  --query "Quotas[?contains(QuotaName, 'endpoint usage')].{Name:QuotaName,Code:QuotaCode,Value:Value}" \
  --output table
```

**Recurring gotcha:** after any interrupted/failed `deploy.py`, delete the leftover endpoint config before retrying or you'll hit `Cannot create already existing endpoint configuration`.

**Region matters everywhere:** the endpoint lives in `ap-south-1`. Any CLI command or Connect-mode request must match that region or it'll silently find nothing.

---

## 📜 Contribution guidelines

- `backend/` — owned by Aniketh. Do not edit unless discussed first.
- `frontend/` — currently also Aniketh (Akanksha's original scope, absorbed Aug 13 pending her availability).
- Raise backend-shape changes as a conversation, not a direct edit.
- Keep this README updated — it's the shared source of truth for the team and for AI tools either of us pastes it into.

---

## 📅 Session log (condensed)

**Aug 8** — Full backend pipeline verified end-to-end against real infra: S3 Data Capture parsing, JWT auth (ES256/JWKS), Supabase persistence, CSV upload mode (3 datasets), Connect mode (region-mismatch bug found + fixed). Frontend not yet started.

**Aug 13** (Aniketh solo) — STS AssumeRole verified same-account, end-to-end through the real API. `_safe_uuid()` guard confirmed in place, hardened to log on silent NULL conversion. Auth added to `/governance/status` and `/governance/report` (not yet owner-scoped). CSV column matching made case-insensitive with `did_you_mean` suggestions. Frontend built from scratch (vanilla HTML/CSS/JS): login, upload, connect, status/report tabs. Identified and deliberately parked: `upsert_model` user-scoping, cross-account identity problem, Render deployment gaps, `INIT_SQL` doc drift.

**Aug 17** — Column picker added to upload-mode UI (maps real CSV headers to canonical names client-side). Found and fixed a real response-shape divergence between `/governance/check` and `/governance/analyze-csv` (caught by UI testing, not curl) — unified into one `build_governance_response()` function, both routes now share `response_model=GovernanceCheckResponse`. Connect-mode and Status/Reports screens verified fully working through the real UI. Stray `.env` keys removed. New dev tool: `get-jwt.html` for grabbing a real JWT without the full frontend flow.

For the full bug-by-bug history (root causes, exact fixes), see git blame / commit log — trimmed here to keep this doc scannable going into the hackathon.

---

## 📚 Stack

FastAPI · LangGraph · LangChain · boto3 (AWS) · Supabase (Postgres, Auth) · SHAP · scikit-learn · pandas · Vanilla HTML/CSS/JS frontend

---

## 📄 License

MIT — private repo, not yet public.