# Citadel AI — AI Governance & Bias Detection Platform

**EquiLens at the core. Production-grade governance on top.**

Citadel AI is a governance layer that connects to your cloud ML infrastructure (AWS SageMaker), continuously discovers deployed models, monitors their live predictions for bias, and surfaces violations before they become compliance incidents. The bias-detection engine is powered by EquiLens — a validated, working fairness-metrics library (SPD, Disparate Impact, Equalized Odds, SHAP explainability) — wrapped in a LangGraph-orchestrated governance workflow.

> Status: **Private / in development.** This README doubles as the working architecture doc, build log, and task board ahead of DevThon (Aug 20–21, 2026).
>
> **This file is our shared notes app for the project** — keep it updated with what's done, what's broken, what's next, and who's doing what. Since the repo is private, feel free to be verbose here.

---

## 👥 Team & ownership

| Person | Focus |
|---|---|
| **Aniketh** | Core backend: LangGraph workflow, bias-engine wiring, Supabase persistence, API layer, CSV upload mode |
| **Akanksha** | AWS integration layer (STS AssumeRole, real S3 Data Capture fetch) — new to backend dev, vibecoding with AI assistance. Onboarding notes below. |

**Scope decision:** GCP and Azure connectors are cut entirely for the hackathon — AWS-only, for demo depth over breadth. `gcp_connector.py` / `azure_connector.py` have been deleted from the repo.

**Sequencing decision:** the real AWS integration (STS AssumeRole, real SageMaker/S3 data fetch — currently still mocked) remains intentionally *last* priority. Supabase persistence is now **done and verified**. Current active work: CSV upload mode is done and validated — next up is deciding between `/governance/status`+`/governance/report` (now unblocked by persistence) or the real AWS deploy.

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
        │  • AWS Tool Layer (STS assume-role, SageMaker, S3)     │
        │  • EquiLens Bias Engine (SPD, DI, EOD, SHAP)           │
        │  • Supabase (tenants, endpoints, audit history) ✅ LIVE│
        │  • Scheduler (daily audits per registered endpoint)    │
        │  • Alert Service (Slack / Jira)                        │
        └──────────────────────────────────────────────────────┘
```

**Key design note:** DETECT branches conditionally — a clean audit short-circuits toward `COMPLETE` instead of always walking through remediation and alerting (both nodes early-return harmlessly when there's nothing to do). **Verified today** on real data: `true_unbiased.csv` (DI=0.98) correctly took the clean-audit branch — `remediate`/`alert` both early-returned with `"No remediation needed"` / `"No alerts to send"`, while biased datasets correctly walked the full violation branch. This confirms the conditional-branch design actually works as intended, not just in theory.

**Upload mode vs. Connect mode share everything downstream of ingestion.** `ingest_csv()` populates the same `discovered_models` / `recent_predictions` state shape that `discover_models()` + `monitor_predictions()` populate for AWS — so `analyze_bias`, `detect_violation`, `remediate`, `alert`, and `complete_workflow` (including persistence) run identically regardless of data source. Zero duplicated logic between the two modes.

### Node-by-node — current real status (verified by running the code, not just reading it)

| Node | What it does | Status |
|---|---|---|
| `discover_models` | Lists real SageMaker endpoints via `AWSConnector` | ✅ runs end-to-end; auth currently static keys only — real STS AssumeRole not yet wired (Akanksha) |
| `monitor_predictions` | Pulls prediction data from discovered models | ⚠️ runs, but `get_predictions()` always returns **mock data**, even against real endpoints — real S3 Data Capture parsing not built (Akanksha) |
| `ingest_csv` **(new)** | Upload-mode equivalent of discover+monitor — treats an uploaded CSV as one synthetic model, its rows as predictions | ✅ built and validated today against 3 datasets (see below) |
| `analyze_bias` | Calls EquiLens's real `analyze_bias()` / `compute_eod()` on the DataFrame of predictions | ✅ wired to real EquiLens functions; **validated today** against a real-world dataset with a literature-known bias level (see below) |
| `detect_violation` | Checks DI/SPD/EOD against thresholds, sets `needs_remediation` | ✅ working; both branches (violation / clean) confirmed today |
| `remediate` | Suggests fixes; uses SHAP top-features if available, generic list otherwise | ⚠️ working but generic-only — SHAP explanation is currently unavailable in the live monitoring flow (see note below) |
| `alert` | Logs alerts to `audit_log`; no external notification yet | ⚠️ audit-log only, no Slack/Jira integration yet |
| `complete_workflow` | Records execution time, finalizes `workflow_status`, **persists run to Supabase** | ✅ persistence wired and verified live today — `audit_runs`, `models`, `bias_metrics`, `alerts` all confirmed writing correctly |

**SHAP note:** `get_shap_values(model, X_train, X_test)` in `explainer.py` requires a *trained model artifact*, not just prediction input/output. Neither the AWS monitoring pipeline nor CSV upload mode load a model artifact, so SHAP is currently explicitly marked unavailable (`root_causes.note`) rather than faked. Loading the model artifact for real SHAP explanations is unscoped work — needs a decision on *how* (pull from SageMaker model registry? require user to upload artifact separately?).

### 📄 Upload mode — done and validated

New endpoint: `POST /api/v1/governance/analyze-csv` (multipart file upload, `python-multipart` dependency added).

Required CSV columns: `prediction`, `group` (sensitive attribute). Optional: `actual_label` (enables EOD). Column names must match exactly — no auto-mapping yet, caller renames before upload.

**Test results (today):**

| Dataset | Rows | DI | SPD | Result |
|---|---|---|---|---|
| Synthetic obvious-bias test | 6 | 0.00 | 1.00 | ✅ Critical violation correctly detected, full remediation + alert + persist chain fired |
| Adult Income (Kaggle, `income`→`prediction`, `sex`→`group`) | 30,162 | 0.36 | 0.20 | ✅ Critical violation correctly detected — **DI matches the commonly cited literature value for this exact split**, strong external validation of EquiLens's math. Full pipeline completed in 349ms. |
| `true_unbiased.csv` (`hired`→`prediction`, `gender`→`group`) | 1,000 | 0.98 | 0.013 | ✅ No violation, clean-audit branch taken correctly, `remediate`/`alert` both early-returned as designed |

All three runs persisted correctly to Supabase (`audit_runs` + `models` every time, `bias_metrics` every time, `alerts` only on the two biased runs — exactly as expected).

**Known rough edge:** `analyze_bias` pools all rows into one aggregate DI/SPD/EOD, and `complete_workflow` writes that same aggregate result once per "model" in `discovered_models`. Fine for CSV mode (always exactly one synthetic model) and fine for the AWS demo's single biased endpoint, but if Connect mode ever discovers multiple real endpoints, per-model bias_metrics rows would currently be duplicates of the same pooled number, not independently computed. Flagged, not fixed — conscious tradeoff for hackathon scope.

### AWS connection model (target design — not fully live yet)

- **Cross-account IAM role assumption** (STS `AssumeRole`) — user creates a read-only role in their account trusting Citadel's account. No raw access keys stored, ever.
  - Constructor supports `iam_role_arn` and calls `sts.assume_role()` when present; falls back to static `access_key_id`/`secret_access_key` only for local dev when no role ARN is given.
- Scoped permissions only: `sagemaker:ListEndpoints`, `sagemaker:DescribeEndpoint`, `s3:GetObject` on the data-capture bucket.
- **Data Capture must be enabled** on the target SageMaker endpoint at creation time — prerequisite for `monitor_predictions` to read anything real.
- **Not yet built:** the actual S3 Data Capture log parsing (locating the bucket, listing/reading JSONL objects, mapping captured payloads to the `{prediction, group, actual_label}` shape the bias engine expects). This is real, separately-scoped work — assigned to Akanksha, intentionally last priority.
- Real discovery attempted today with placeholder credentials — correctly rejected with a genuine `UnrecognizedClientException`, confirming auth wiring is real (not stubbed) even though nothing valid has been tested against yet.

### Data model (Supabase) — ✅ **live and persisting**

```
users
  └─ connected_accounts (role_arn, region)
       └─ registered_endpoints (endpoint_arn, schedule_time)
       └─ models (cloud_provider, model_id, model_name, last_monitored)
            └─ audit_runs (id, user_id, cloud_provider, status, models_discovered, execution_time_ms, error)
            └─ bias_metrics (model_id, di, spd, eod, samples_count)
            └─ alerts (model_id, alert_type, severity, message, metric_value, threshold, status)
```

**Persistence is done.** `complete_workflow` writes a real `audit_runs` row every run, plus `models`/`bias_metrics`/`alerts` rows whenever a model was discovered (AWS or CSV). Verified via direct Supabase table checks and live HTTP `201 Created` responses in server logs across 5 separate test runs today (2 Connect-mode, 3 upload-mode).

**Bugs found and fixed today, en route to working persistence:**
- `insert_audit_run()` targeted a table called `audit_runs`, but `INIT_SQL` only ever created `audit_logs` (different table, different schema) — `audit_runs` never actually existed in Supabase. Every persist attempt failed silently (caught by the `except persist_err` block) until the table was created manually.
- `insert_audit_run()` didn't accept a `user_id`, so `/governance/status` and `/governance/report` (both still TODO) would have had no way to filter runs per tenant later. Added the param.
- The API layer hardcoded `user_id="demo_user"` — not a valid UUID, and the `audit_runs.user_id` column is a UUID FK to `users(id)`. Every persist attempt failed with `invalid input syntax for type uuid`. Fixed by creating a real demo user row (`00000000-...-000000000001`) and referencing it via a named constant instead of a literal.

### Scheduling — not started

- In-process scheduler (APScheduler) to trigger `run_governance_check()` per registered endpoint at its configured daily time.
- Manual `POST /governance/run-now` endpoint for on-demand checks/demos — **note:** actual route ended up being `POST /governance/check`, not `/governance/run-now` as originally planned; update anything referencing the old name.
- First connect should trigger an immediate run.

---

## 💎 Differentiator features (beyond baseline monitoring)

- [ ] **Counterfactual flip testing** — flip only the protected attribute on a real prediction, re-infer, show the decision change side-by-side. Most legible, memorable feature in the product.
- [ ] **Adversarial fairness probing** — synthetic boundary-condition inputs near decision thresholds across protected groups, not just organic traffic.
- [ ] **Fairness policy-as-code** — versioned, declarative thresholds (e.g. `DI >= 0.8 for gender`) enforceable in CI/CD.
- [ ] **Fleet-wide risk posture view** — all registered models ranked by risk, security-dashboard style.

---

## 🖥️ Frontend — not started

Dark, dense, data-forward — governance/security tool aesthetic (Linear / Datadog / Wiz).

Intentionally not started yet — waiting until both backend data paths (Connect mode, Upload mode) are solid so UI isn't built against a moving target. Upload mode is now done; this is close to unblocked.

- [ ] Live-streaming audit log (SSE/websocket) rendering `audit_log` as it's generated
- [ ] Counterfactual flip panel as the hero visual
- [ ] Severity color language (green/amber/red)
- [ ] Upload-mode and Connect-mode as two clear entry paths from login
- [ ] Historical bias trend chart per endpoint (DI over time, from `audit_runs`) — **now genuinely buildable**, real historical data exists in Supabase for the first time as of today

---

## ✅ What's actually working right now (verified by running it, not just reading code)

- FastAPI app imports and starts cleanly; CORS scoped to real allowed origins (not `*`) + health check live
- Real Supabase connection confirmed (`GET .../users?select=count` → `200 OK` against live hosted project)
- Governance workflow executes fully async end-to-end for **both** Connect mode (`discover → monitor → analyze → detect → remediate → alert → complete`) and Upload mode (`ingest_csv → analyze → detect → remediate → alert → complete`) without crashing
- Real AWS auth attempted on `discover_models` (correctly rejects invalid/test credentials with a real `UnrecognizedClientException`)
- `workflow_status` correctly reflects failure vs. success
- EquiLens's real `calculate_spd`, `calculate_di`, `compute_eod` are actually called by `analyze_bias` — **validated against Kaggle Adult dataset, DI result matches known literature value**
- **Persistence fully working**: `audit_runs`, `models`, `bias_metrics`, `alerts` all confirmed writing to live Supabase across both modes
- **CSV upload mode fully working**: `POST /governance/analyze-csv`, tested against 3 datasets covering both the violation branch and the clean-audit branch
- Conditional graph branching (clean audit short-circuits past remediation/alerting) confirmed working on real data, not just by reading the code
- AWS-only: `CloudProvider` enum, request/response models, and all node branching now AWS-only; GCP/Azure code deleted

## ⏳ To-do (prioritized for Aug 20 build)

### High priority — core loop (Aniketh, active)
- [x] ~~Persist governance workflow runs to Supabase~~ ✅ **done, verified today**
- [x] ~~Build CSV upload mode~~ ✅ **done, verified today against 3 datasets**
- [ ] End-to-end test with real (even free-tier/limited) AWS credentials — confirm real `list_endpoints()` behavior against an actual account
- [ ] `/governance/status`, `/governance/remediate`, `/governance/report` endpoints — currently hardcoded placeholder responses; **now unblocked** — real `audit_runs`/`bias_metrics`/`alerts` data exists to query
- [ ] `clouds.py` — `connect`/`list`/`disconnect`/`test` endpoints are placeholder-only; need real Supabase reads/writes to `cloud_accounts`
- [ ] Add `_safe_uuid()` guard in `db.py` around all UUID-typed inserts — cheap insurance so a bad ID never silently kills a whole persistence block again (the `user_id` bug today was a preview of this class of issue)
- [ ] Optional: column auto-mapping / friendlier error for CSV upload (currently requires exact `prediction`/`group` column names, caller renames manually)

### High priority — AWS integration (Akanksha, last priority by design)
- [ ] Real STS AssumeRole flow end-to-end (constructor support already exists; needs a real IAM role + testing)
- [ ] Real S3 Data Capture log fetch in `get_predictions()` — replace mock data with real parsing of captured SageMaker inference logs
- [ ] Deploy the intentionally biased hiring model (synthetic data) to a SageMaker endpoint with Data Capture enabled — this is the demo's ground truth

### Medium priority — differentiators
- [ ] Counterfactual flip testing node
- [ ] SHAP-reasoned remediation — needs the model-artifact-loading decision above resolved first
- [ ] Slack webhook alert integration
- [ ] Scheduler (APScheduler) + manual "run now" endpoint

### Frontend
- [ ] Login + two-mode entry (upload / connect AWS)
- [ ] Live audit-log stream UI
- [ ] Counterfactual flip visual
- [ ] Historical trend chart

### Lower priority / post-hackathon
- [ ] Adversarial probing node
- [ ] Fairness policy-as-code + CI/CD gate
- [ ] Jira/GitHub alert integrations
- [ ] Pydantic field renames (`model_id` → `model_identifier`, silences the protected-namespace warning)
- [ ] Unit/integration test suite
- [x] ~~CORS hole~~ ✅ **fixed today** — `allow_origins` scoped via `ALLOWED_ORIGINS` env var, `allow_credentials=False` until real auth exists
- [ ] **API authentication (JWT)** — still not implemented; all writes currently attribute to a single hardcoded demo user UUID. Must-fix before anything public-facing.
- [ ] RLS policies on Supabase tables (currently off — fine for now, needed before any real user data touches this)

---

## 🐛 Known bugs fixed so far (log, so we don't reintroduce them)

- `graph.py` was calling `.invoke()` (sync) against all-async nodes → every workflow run failed at the first node. Fixed: `await governance_graph.ainvoke(...)`.
- `complete_workflow` unconditionally set `workflow_status = 'completed'`, silently overwriting real failures from earlier nodes.
- `nodes.py` imported `analyze_bias` from `analyzer.py` directly, which got shadowed by the locally-defined `async def analyze_bias` in the same file — the real EquiLens function was never actually reachable.
- F-string crash in the old `analyze_bias`: `f"DI={di:.2f if di else 'N/A'}"` is invalid Python (conditional inside a format spec).
- `db.py` had the Supabase client instantiation commented out while `init_db()`/`get_supabase()` still referenced it → `NameError` on first real use.
- `config.py`'s `.env` path was relative to CWD, not to the file itself → only worked when run from inside `backend/`.
- `analyzer.py`'s `analyze_bias()` would raise `IndexError` on an empty/all-null target column.
- Dependency cascade: `supabase==2.4.0` pinned an old `httpx`, which itself was too old for `gotrue`'s `proxy` kwarg usage; upgrading `supabase` then needed a `websockets` bump, which overshot `realtime`'s own pin. Resolved by aligning versions; `requirements.txt` regenerated from the working environment via `pip freeze`.
- **(new)** `CORSMiddleware` used `allow_origins=["*"]` + `allow_credentials=True` simultaneously — invalid combination per spec, and a real open-CORS hole. Fixed via `ALLOWED_ORIGINS` env var + `allow_credentials=False` until JWT auth exists.
- **(new)** `config.py` edit landed a `ALLOWED_ORIGINS` field + `allowed_origins_list` property at **module level**, outside the `Settings` class entirely — silent no-op until `main.py` tried to access `settings.allowed_origins_list` and hit `AttributeError`. Indentation/placement issue, not a logic bug.
- **(new)** `insert_audit_run()` wrote to `audit_runs`, a table `INIT_SQL` never actually created (only `audit_logs`, a different table/schema, existed). Silent failure caught by the persistence try/except — no crash, but nothing ever actually saved. Fixed by creating the missing table directly in Supabase.
- **(new)** API layer hardcoded `user_id="demo_user"` (not a valid UUID) against a UUID-typed FK column → every persist attempt failed with `invalid input syntax for type uuid`. Fixed with a real demo user row + a named UUID constant.
- **(new)** `ingest_csv` was accidentally pasted into `state.py` instead of `nodes.py` during the upload-mode build, type-hinted with `CitadelState` before that class was defined later in the same file → circular self-import (`state.py` trying to import from itself). Fixed by moving the function to `nodes.py`, which already imports `CitadelState` from `state.py` in the correct direction.
- **(new)** `python-multipart` wasn't installed — required by FastAPI for any `UploadFile`/`File(...)` endpoint, silent until the CSV upload endpoint was actually added. `pip install python-multipart`.

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