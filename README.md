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
| **Aniketh** | Core backend: LangGraph workflow, bias-engine wiring, Supabase persistence, API layer, CSV upload mode, **real AWS S3 Data Capture integration (done)** |
| **Akanksha** | Will connect her own AWS account as a real end user (not a developer) closer to the hackathon, to validate the product from a fresh user's perspective. Onboarding notes below. |

**Scope decision:** GCP and Azure connectors are cut entirely for the hackathon — AWS-only, for demo depth over breadth. `gcp_connector.py` / `azure_connector.py` have been deleted from the repo.

**Sequencing update (Aug 8, day):** the real AWS integration — previously listed as last-priority/Akanksha's task — is **done**. Aniketh deployed the test model to a real SageMaker endpoint, sent real traffic, and wired `get_predictions()` to parse real S3 Data Capture logs end-to-end. Verified live against 235 real predictions (see below).

**Sequencing update (Aug 8, evening):** JWT auth via Supabase (Google sign-in) is also done and verified end-to-end — real `user_id`s now flow through every governance check and persist correctly to Supabase, replacing the hardcoded demo user. Next: Akanksha starts frontend (login + upload/connect screens) against this real, working auth contract.

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
        │  • AWS Tool Layer (STS assume-role, SageMaker, S3) ✅ LIVE│
        │  • EquiLens Bias Engine (SPD, DI, EOD, SHAP)           │
        │  • Supabase (tenants, endpoints, audit history) ✅ LIVE│
        │  • Scheduler (daily audits per registered endpoint)    │
        │  • Alert Service (Slack / Jira)                        │
        └──────────────────────────────────────────────────────┘
```

**Key design note:** DETECT branches conditionally — a clean audit short-circuits toward `COMPLETE` instead of always walking through remediation and alerting (both nodes early-return harmlessly when there's nothing to do). Verified on real data: `true_unbiased.csv` (DI=0.98) correctly took the clean-audit branch, while biased datasets and the real AWS endpoint both correctly walked the full violation branch.

**Upload mode vs. Connect mode share everything downstream of ingestion.** `ingest_csv()` populates the same `discovered_models` / `recent_predictions` state shape that `discover_models()` + `monitor_predictions()` populate for AWS — so `analyze_bias`, `detect_violation`, `remediate`, `alert`, and `complete_workflow` (including persistence) run identically regardless of data source. Zero duplicated logic between the two modes.

### Node-by-node — current real status (verified by running the code, not just reading it)

| Node | What it does | Status |
|---|---|---|
| `discover_models` | Lists real SageMaker endpoints via `AWSConnector` | ✅ runs end-to-end against a real account; auth currently static keys only — real STS AssumeRole not yet tested end-to-end |
| `monitor_predictions` | Pulls prediction data from discovered models | ✅ **real S3 Data Capture parsing done and verified** — `get_predictions()` no longer returns mock data; pulls, lists, and parses real `.jsonl` objects straight from S3 |
| `ingest_csv` | Upload-mode equivalent of discover+monitor — treats an uploaded CSV as one synthetic model, its rows as predictions | ✅ built and validated against 3 datasets (see below) |
| `analyze_bias` | Calls EquiLens's real `analyze_bias()` / `compute_eod()` on the DataFrame of predictions | ✅ wired to real EquiLens functions; validated against a real-world dataset with a literature-known bias level, **and against real live AWS traffic** |
| `detect_violation` | Checks DI/SPD/EOD against thresholds, sets `needs_remediation` | ✅ working; both branches (violation / clean) confirmed on real data |
| `remediate` | Suggests fixes; uses SHAP top-features if available, generic list otherwise | ⚠️ working but generic-only — SHAP explanation is currently unavailable in the live monitoring flow (see note below) |
| `alert` | Logs alerts to `audit_log`; no external notification yet | ⚠️ audit-log only, no Slack/Jira integration yet |
| `complete_workflow` | Records execution time, finalizes `workflow_status`, persists run to Supabase | ✅ persistence wired and verified live — `audit_runs`, `models`, `bias_metrics`, `alerts` all confirmed writing correctly, including from real AWS runs |

**SHAP note:** `get_shap_values(model, X_train, X_test)` in `explainer.py` requires a *trained model artifact*, not just prediction input/output. Neither the AWS monitoring pipeline nor CSV upload mode load a model artifact, so SHAP is currently explicitly marked unavailable (`root_causes.note`) rather than faked. Loading the model artifact for real SHAP explanations is unscoped work — needs a decision on *how* (pull from SageMaker model registry? require user to upload artifact separately?).

### 📄 Upload mode — done and validated

New endpoint: `POST /api/v1/governance/analyze-csv` (multipart file upload, `python-multipart` dependency added).

Required CSV columns: `prediction`, `group` (sensitive attribute). Optional: `actual_label` (enables EOD). Column names must match exactly — no auto-mapping yet, caller renames before upload.

**Test results:**

| Dataset | Rows | DI | SPD | Result |
|---|---|---|---|---|
| Synthetic obvious-bias test | 6 | 0.00 | 1.00 | ✅ Critical violation correctly detected, full remediation + alert + persist chain fired |
| Adult Income (Kaggle, `income`→`prediction`, `sex`→`group`) | 30,162 | 0.36 | 0.20 | ✅ Critical violation correctly detected — DI matches the commonly cited literature value for this exact split, strong external validation of EquiLens's math. Full pipeline completed in 349ms. |
| `true_unbiased.csv` (`hired`→`prediction`, `gender`→`group`) | 1,000 | 0.98 | 0.013 | ✅ No violation, clean-audit branch taken correctly, `remediate`/`alert` both early-returned as designed |

All three runs persisted correctly to Supabase (`audit_runs` + `models` every time, `bias_metrics` every time, `alerts` only on the two biased runs — exactly as expected).

**Known rough edge:** `analyze_bias` pools all rows into one aggregate DI/SPD/EOD, and `complete_workflow` writes that same aggregate result once per "model" in `discovered_models`. Fine for CSV mode (always exactly one synthetic model) and fine for a single connected endpoint, but if Connect mode ever discovers multiple real endpoints, per-model `bias_metrics` rows would currently be duplicates of the same pooled number, not independently computed. Flagged, not fixed — conscious tradeoff for hackathon scope.

### 🔌 Connect mode — real S3 Data Capture integration (done, verified Aug 8)

**What changed:** `get_predictions()` in `aws_connector.py` previously always returned hardcoded mock predictions, even against a real endpoint. It now:

1. Calls `describe_endpoint()` → `describe_endpoint_config()` on the live endpoint to **dynamically discover** its `DataCaptureConfig.DestinationS3Uri` — no bucket name is ever hardcoded, so this works for any user's account/endpoint, not just one AWS account.
2. Lists and reads the real `.jsonl` Data Capture objects directly from S3 (`list_objects_v2` + `get_object`, no local disk writes).
3. Parses SageMaker's double-JSON-encoded capture envelope — `captureData.endpointInput.data` and `captureData.endpointOutput.data` are themselves JSON strings that need a second `json.loads()`.
4. Maps the numeric `gender: 0/1` field to human-readable `'Female'/'Male'` strings before handing rows to the bias engine, so results display cleanly without touching `analyzer.py`.

**Real capture envelope shape** (one line per request, confirmed from a live sample):
```json
{
  "captureData": {
    "endpointInput":  {"data": "{\"instances\": [{\"years_experience\": 7.2, \"education_level\": 2, \"test_score\": 56.6, \"num_previous_companies\": 2, \"age\": 42, \"gender\": 1}]}"},
    "endpointOutput": {"data": "{\"predictions\": [{\"hired\": 0, \"probability\": 0.0857}]}"}
  },
  "eventMetadata": {"eventId": "...", "inferenceTime": "2026-08-08T02:35:17Z"},
  "eventVersion": "0"
}
```

**Live end-to-end test result (Aug 8, real curl → real endpoint → real S3 → real Supabase):**

```json
{
  "status": "completed",
  "models_discovered": 1,
  "bias_metrics": {
    "citadel-biased-hiring-endpoint/AllTraffic": {
      "disparate_impact": 0.0,
      "statistical_parity_diff": 0.3694,
      "equalized_odds": null,
      "samples_count": 235,
      "status": "high"
    }
  },
  "alerts": [{"alert_type": "bias_critical", "severity": "critical", "message": "Critical: Disparate Impact 0.00 below legal threshold (0.8)"}]
}
```

This matches the raw `traffic.py` findings from the model-deployment side (male hire rate 0.369, female hire rate 0.000, DI 0.000) — independent confirmation that the full chain (S3 → parser → EquiLens → Supabase) computes correctly on real data, not just mock data.

**Bug found during this test:** first attempt returned `models_discovered: 0` with real, valid credentials. Root cause was a **region mismatch** — the request body specified `us-east-1` while the endpoint was actually deployed in `ap-south-1`. SageMaker endpoint discovery is region-scoped; nothing was wrong with the connector code. Lesson: `credentials.region` in Connect-mode requests must match the region the target endpoint is actually deployed in — worth surfacing a clearer error for this later (currently just silently returns 0 models) rather than looking like an auth or discovery bug.

### AWS connection model (target design)

- **Cross-account IAM role assumption** (STS `AssumeRole`) — user creates a read-only role in their account trusting Citadel's account. No raw access keys stored, ever.
  - Constructor supports `iam_role_arn` and calls `sts.assume_role()` when present; falls back to static `access_key_id`/`secret_access_key` only for local dev when no role ARN is given.
- Scoped permissions needed: `sagemaker:ListEndpoints`, `sagemaker:DescribeEndpoint`, `sagemaker:DescribeEndpointConfig`, `s3:GetObject` + `s3:ListBucket` on the data-capture bucket.
- **Data Capture must be enabled** on the target SageMaker endpoint at creation time — prerequisite for `monitor_predictions` to read anything real.
- Real discovery tested with both placeholder credentials (correctly rejected with `UnrecognizedClientException`) and real credentials (correctly discovers endpoints + real prediction data), confirming auth wiring is genuinely live, not stubbed.
- **Still not tested end-to-end:** real STS AssumeRole flow (cross-account). Everything validated so far used static access keys for the same account. Needs a second AWS account (e.g. Akanksha's) + a real trust-policy role to fully validate before the demo.

### 🔐 Auth — JWT via Supabase (done, verified Aug 8)

**What changed:** every write-triggering governance route now requires a real, verified identity instead of the hardcoded `demo_user` UUID.

- Frontend flow (for whoever builds the UI): `supabase.auth.signInWithOAuth({ provider: 'google' })` → Supabase handles the OAuth dance → returns a session with a real JWT. Attach it as `Authorization: Bearer <token>` on every API call.
- Backend: `app/auth.py` exposes a `get_current_user` FastAPI dependency, added to `/governance/check` and `/governance/analyze-csv`. It verifies the incoming JWT and returns the real `user_id` (`sub` claim), which then flows into `run_governance_check`/`run_csv_governance_check` → `insert_audit_run`, replacing the old hardcoded constant everywhere it mattered.
- **Important gotcha, worth knowing if this ever needs debugging again:** this Supabase project issues **asymmetric `ES256`-signed JWTs** (via Supabase's newer JWT signing-keys system), not the legacy shared-secret `HS256` tokens. Verification is done against Supabase's public JWKS endpoint (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`) via `PyJWKClient`, not against a `SUPABASE_JWT_SECRET`. If you see `alg: "ES256"` in a decoded token header, that confirms which path applies — trying to verify it with a shared HS256 secret will fail every time, not because anything's broken, just the wrong method for this project's config.
- `/governance/status` and `/governance/report` are currently **not** behind auth — they're read-only, filtered by `cloud_provider`/`model_id` rather than by user, and nothing public-facing depends on them yet. Worth revisiting before this is public.

**Live end-to-end test (Aug 8):** signed in with Google via a throwaway local test page → got a real Supabase session/JWT → curled `/governance/check` with it → backend correctly extracted the real `user_id` and logged/persisted under it:
```
"🚀 Governance check initiated by 06b0e979-0bbe-4678-82b7-02bd4bd6bd50"
```
confirmed in Supabase's `audit_runs` table as well — no more `00000000-...-0001` rows going forward.

Google OAuth setup itself: Google Cloud Console → OAuth consent screen (User type: **External**, Publishing status: **Testing**, both team members added as test users) → OAuth Client (Web application) → Authorized redirect URI set to `https://qxsyscrbnbrzzvctozht.supabase.co/auth/v1/callback` → Client ID + Secret pasted into Supabase's Google provider settings, toggled on.

### Data model (Supabase) — ✅ live and persisting



```
users
  └─ connected_accounts (role_arn, region)
       └─ registered_endpoints (endpoint_arn, schedule_time)
       └─ models (cloud_provider, model_id, model_name, last_monitored)
            └─ audit_runs (id, user_id, cloud_provider, status, models_discovered, execution_time_ms, error)
            └─ bias_metrics (model_id, di, spd, eod, samples_count)
            └─ alerts (model_id, alert_type, severity, message, metric_value, threshold, status)
```

**Persistence is done.** `complete_workflow` writes a real `audit_runs` row every run, plus `models`/`bias_metrics`/`alerts` rows whenever a model was discovered (AWS or CSV). Verified via direct Supabase table checks and live HTTP `201 Created` responses across multiple Connect-mode and upload-mode test runs, including today's real AWS run.

**RLS is enabled** (Aug 8) — backend uses the `service_role` key so it bypasses RLS by design and persistence is unaffected. Real per-user RLS policies (`user_id = auth.uid()`) are still needed before any client talks to Supabase with the `anon` key (i.e. before frontend queries Supabase directly, if it ever does — right now everything should route through the FastAPI backend).

### Scheduling — not started

- In-process scheduler (APScheduler) to trigger `run_governance_check()` per registered endpoint at its configured daily time.
- Manual on-demand check endpoint — **note:** actual route is `POST /governance/check`, not `/governance/run-now` as originally planned; update anything referencing the old name.
- First connect should trigger an immediate run.

---

## 💎 Differentiator features (beyond baseline monitoring)

- [ ] **Counterfactual flip testing** — flip only the protected attribute on a real prediction, re-infer, show the decision change side-by-side. Most legible, memorable feature in the product.
- [ ] **Adversarial fairness probing** — synthetic boundary-condition inputs near decision thresholds across protected groups, not just organic traffic.
- [ ] **Fairness policy-as-code** — versioned, declarative thresholds (e.g. `DI >= 0.8 for gender`) enforceable in CI/CD.
- [ ] **Fleet-wide risk posture view** — all registered models ranked by risk, security-dashboard style.

---

## 🖥️ Frontend — starting now

Dark, dense, data-forward — governance/security tool aesthetic (Linear / Datadog / Wiz). Building minimal-and-working first, layering frameworks/polish later — not going deep on styling until the core loop is visible end to end.

**Plan:**
- [ ] Login — via Supabase Auth (Google sign-in). Backend auth is done and tested; frontend just needs `supabase.auth.signInWithOAuth({ provider: 'google' })` and to attach `session.access_token` as `Authorization: Bearer <token>` on every API call. No backend work blocking this.
- [ ] Upload-mode screen (CSV upload → DI/SPD/EOD results) — backend already stable, build against this first
- [ ] Connect-mode screen (enter AWS credentials/role → discovered endpoints → run check → live results) — backend now validated end-to-end, safe to build against
- [ ] Audit history view, pulling real `audit_runs`/`bias_metrics`/`alerts` from Supabase
- [ ] Live-streaming audit log (SSE/websocket) rendering `audit_log` as it's generated
- [ ] Counterfactual flip panel as the hero visual
- [ ] Severity color language (green/amber/red)
- [ ] Historical bias trend chart per endpoint (DI over time, from `audit_runs`)

**Demo split plan:** Aniketh shows terminal + Supabase (technical depth), Akanksha connects her own AWS account as a genuine end user and demos the live UI — two angles on the same real product, not a scripted mock.

---

## ✅ What's actually working right now (verified by running it, not just reading code)

- FastAPI app imports and starts cleanly; CORS scoped to real allowed origins (not `*`) + health check live
- Real Supabase connection confirmed (`GET .../users?select=count` → `200 OK` against live hosted project)
- Governance workflow executes fully async end-to-end for **both** Connect mode (`discover → monitor → analyze → detect → remediate → alert → complete`) and Upload mode (`ingest_csv → analyze → detect → remediate → alert → complete`) without crashing
- Real AWS auth confirmed both ways: rejects invalid/test credentials with a real `UnrecognizedClientException`, and succeeds with real credentials against a real account
- **Real S3 Data Capture parsing confirmed** — 235 real predictions fetched, parsed, and correctly analyzed from a live SageMaker endpoint's capture logs
- `workflow_status` correctly reflects failure vs. success
- EquiLens's real `calculate_spd`, `calculate_di`, `compute_eod` are actually called by `analyze_bias` — validated against Kaggle Adult dataset (matches literature value) **and against real live AWS traffic** (matches the model's known bias pattern)
- Persistence fully working: `audit_runs`, `models`, `bias_metrics`, `alerts` all confirmed writing to live Supabase across both modes, including real AWS runs
- **Real JWT auth confirmed end-to-end** — Google sign-in via Supabase issues a real `ES256` JWT, backend verifies it against Supabase's public JWKS (no shared secret), extracts the real `user_id`, and that identity flows through the full governance workflow into Supabase — confirmed via a live test with a real Google account, replacing the hardcoded demo user entirely
- CSV upload mode fully working: `POST /governance/analyze-csv`, tested against 3 datasets covering both the violation branch and the clean-audit branch
- Conditional graph branching (clean audit short-circuits past remediation/alerting) confirmed working on real data, not just by reading the code
- AWS-only: `CloudProvider` enum, request/response models, and all node branching now AWS-only; GCP/Azure code deleted

## ⏳ To-do (prioritized for Aug 20 build)

### High priority — core loop
- [x] ~~Persist governance workflow runs to Supabase~~ ✅ done
- [x] ~~Build CSV upload mode~~ ✅ done, verified against 3 datasets
- [x] ~~Real S3 Data Capture log fetch in `get_predictions()`~~ ✅ done, verified against 235 real predictions
- [x] ~~End-to-end test with real AWS credentials~~ ✅ done
- [ ] Real STS AssumeRole flow, tested cross-account (needed before Akanksha connects as a separate real user)
- [x] ~~JWT auth via Supabase (Google sign-in)~~ ✅ **done Aug 8** — replaced hardcoded `demo_user` UUID with real `user_id` extracted from a verified Supabase JWT on every protected route. See auth details below.
- [x] ~~RLS enabled on Supabase tables~~ ✅ enabled Aug 8 — backend confirmed still writing correctly using the `service_role` key (see bug log below). Real per-user RLS *policies* (`user_id = auth.uid()`) still worth writing as defense-in-depth, though the backend itself now enforces per-user identity at the API layer via JWT verification, not just at the DB layer.
- [ ] Investigate `.env` parse warnings (`Python-dotenv could not parse statement starting at line 7-21`) — didn't break anything today, but worth cleaning up before it silently hides a real config issue later
- [ ] Decide whether `/governance/status` and `/governance/report` should also require auth — currently open/unauthenticated, fine for now since nothing public-facing depends on them yet
- [ ] `/governance/status`, `/governance/remediate`, `/governance/report` endpoints — currently hardcoded placeholder responses; unblocked by persistence, needs real queries
- [ ] `clouds.py` — `connect`/`list`/`disconnect`/`test` endpoints are placeholder-only; need real Supabase reads/writes to `cloud_accounts`
- [ ] Add `_safe_uuid()` guard in `db.py` around all UUID-typed inserts
- [ ] Clearer error when Connect-mode `region` doesn't match the target endpoint's actual region (currently silently returns 0 models discovered, easy to mistake for an auth bug — see today's incident above)
- [ ] Optional: column auto-mapping / friendlier error for CSV upload (currently requires exact `prediction`/`group` column names)

### Medium priority — differentiators
- [ ] Counterfactual flip testing node
- [ ] SHAP-reasoned remediation — needs the model-artifact-loading decision resolved first
- [ ] Slack webhook alert integration
- [ ] Scheduler (APScheduler) + manual "run now" endpoint

### Frontend
- [ ] Login (Google via Supabase Auth) + two-mode entry (upload / connect AWS)
- [ ] Upload-mode screen
- [ ] Connect-mode screen
- [ ] Live audit-log stream UI
- [ ] Counterfactual flip visual
- [ ] Historical trend chart

### Lower priority / post-hackathon
- [ ] Adversarial probing node
- [ ] Fairness policy-as-code + CI/CD gate
- [ ] Jira/GitHub alert integrations
- [ ] Pydantic field renames (`model_id` → `model_identifier`, silences the protected-namespace warning)
- [ ] Unit/integration test suite
- [x] ~~CORS hole~~ ✅ fixed — `allow_origins` scoped via `ALLOWED_ORIGINS` env var, `allow_credentials=False` until real auth exists

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
- `CORSMiddleware` used `allow_origins=["*"]` + `allow_credentials=True` simultaneously — invalid combination per spec, and a real open-CORS hole. Fixed via `ALLOWED_ORIGINS` env var + `allow_credentials=False` until JWT auth exists.
- `config.py` edit landed an `ALLOWED_ORIGINS` field + `allowed_origins_list` property at **module level**, outside the `Settings` class entirely — silent no-op until `main.py` tried to access `settings.allowed_origins_list` and hit `AttributeError`.
- `insert_audit_run()` wrote to `audit_runs`, a table `INIT_SQL` never actually created (only `audit_logs`, a different table/schema, existed). Silent failure caught by the persistence try/except — no crash, but nothing ever actually saved. Fixed by creating the missing table directly in Supabase.
- API layer hardcoded `user_id="demo_user"` (not a valid UUID) against a UUID-typed FK column → every persist attempt failed with `invalid input syntax for type uuid`. Fixed with a real demo user row + a named UUID constant.
- `ingest_csv` was accidentally pasted into `state.py` instead of `nodes.py`, type-hinted with `CitadelState` before that class was defined later in the same file → circular self-import. Fixed by moving the function to `nodes.py`.
- `python-multipart` wasn't installed — required by FastAPI for any `UploadFile`/`File(...)` endpoint, silent until the CSV upload endpoint was actually added.
- **(new)** First draft of the real `get_predictions()` rewrite got pasted back into the file with broken indentation — `async def get_predictions`, `_parse_s3_uri`, `_fetch_and_parse_capture_logs`, and `_parse_capture_line` all landed at module level (column 0) instead of indented inside `class AWSConnector`. Would have raised `AttributeError: 'AWSConnector' object has no attribute 'get_predictions'` at call time. Fixed by rewriting the full file with correct indentation.
- **(new)** First live Connect-mode test with real credentials returned `models_discovered: 0`. Not an auth or discovery bug — the request specified `region: "us-east-1"` while the endpoint was actually deployed in `ap-south-1`. SageMaker endpoint listing is region-scoped, so the search legitimately found nothing. Fixed by correcting the region in the request.
- **(new)** Enabled RLS on Supabase tables — immediately after, every governance-check run started failing to persist with `code: '42501', "new row violates row-level security policy for table \"audit_runs\""` (Supabase itself returned `401 Unauthorized`). Root cause: the backend's `SUPABASE_KEY` was the `anon` key, which *is* subject to RLS, and zero policies existed yet (default-deny). The workflow itself ran fine end-to-end — only the final persistence step broke. Fixed by switching `SUPABASE_KEY` in `.env` to the `service_role` key, which bypasses RLS by design — the correct pattern for a trusted backend service, not a workaround. Confirmed fixed: re-ran the same check, got `201 Created` on `audit_runs`/`bias_metrics`/`alerts` again. Real per-row RLS policies (`user_id = auth.uid()`) still need writing before any browser/frontend code talks to Supabase directly with the `anon` key.
- **(new)** Enabled RLS on Supabase tables — immediately after, every governance-check run started failing to persist with `code: '42501', "new row violates row-level security policy for table \"audit_runs\""` (Supabase itself returned `401 Unauthorized`). Root cause: the backend's `SUPABASE_KEY` was the `anon` key, which *is* subject to RLS, and zero policies existed yet (default-deny). The workflow itself ran fine end-to-end — only the final persistence step broke. Fixed by switching `SUPABASE_KEY` in `.env` to the `service_role` key, which bypasses RLS by design — the correct pattern for a trusted backend service, not a workaround. Confirmed fixed: re-ran the same check, got `201 Created` on `audit_runs`/`bias_metrics`/`alerts` again. Real per-row RLS policies (`user_id = auth.uid()`) still need writing before any browser/frontend code talks to Supabase directly with the `anon` key.
- **(new)** After the `service_role` key swap, uvicorn logged 12x `Python-dotenv could not parse statement starting at line N` on startup. Didn't break anything (app started, Supabase connected, workflow persisted fine), but flagged as a real `.env` formatting issue to track down before it masks something that actually matters — likely an unescaped/unquoted value or stray line format somewhere around lines 7–21.
- **(new)** `run_governance_workflow` in `governance.py` was updated to reference `user_id` (from the new auth dependency) inside the function body, but the function *signature* wasn't updated to actually declare `user_id: str = Depends(get_current_user)` as a parameter — would have raised `NameError: name 'user_id' is not defined` on every call. Two passes were needed to fully catch this since the first "fix" only updated the body, not the signature. Fixed by adding the parameter to the signature.
- **(new)** First version of a standalone local test page (used to grab a real JWT for curl testing before frontend existed) threw `Uncaught SyntaxError: Identifier 'supabase' has already been declared`. Cause: the Supabase CDN script exposes a global `window.supabase`, and the test page's own code also declared `const supabase = window.supabase.createClient(...)` in the same scope — a naming collision, not a real logic bug. Fixed by renaming the local client variable to `sb`.
- **(new)** First `auth.py` implementation verified JWTs using `HS256` against a shared `SUPABASE_JWT_SECRET` — the legacy Supabase auth signing method. Once a real token was obtained and inspected, its header showed `"alg":"ES256"` — this Supabase project uses the newer **asymmetric JWT signing keys** system, not the legacy shared secret. `HS256` verification would have failed on every real token. Fixed by rewriting `auth.py` to verify against Supabase's public JWKS endpoint (`/auth/v1/.well-known/jwks.json`) via `PyJWKClient` instead — no shared secret needed at all. `SUPABASE_JWT_SECRET` is now unused and can be removed from `.env`/`config.py`. Confirmed working end-to-end: real Google-authenticated `user_id` (`06b0e979-...`) correctly extracted and persisted to `audit_runs`.

---

## 🔧 Useful AWS commands (Test-Model repo, reusable for future sessions)

These live in the sibling `Test-Model` repo (the intentionally-biased hiring model used as Citadel's demo ground truth). Keeping them here too since they'll be needed again before every demo/redeploy cycle.

**Check what's running / billing:**
```bash
aws sagemaker list-endpoints --region ap-south-1 --query 'Endpoints[*].{Name:EndpointName,Status:EndpointStatus}' --output table
```

**Deploy the model:**
```bash
python deploy.py
```

**Send synthetic traffic (to generate fresh Data Capture logs):**
```bash
python traffic.py
```

**Delete endpoint (stop billing) + its config — always clean up before/after a session:**
```bash
aws sagemaker delete-endpoint --endpoint-name citadel-biased-hiring-endpoint --region ap-south-1
aws sagemaker delete-endpoint-config --endpoint-config-name citadel-biased-hiring-endpoint --region ap-south-1
```

**List captured Data Capture files in S3:**
```bash
aws s3 ls s3://citadel-ai-demo-aniketh-447788060954-v1/citadel-demo/data-capture/citadel-biased-hiring-endpoint/AllTraffic/ --recursive
```

**Pull one real capture file to inspect its format:**
```bash
aws s3 cp s3://citadel-ai-demo-aniketh-447788060954-v1/citadel-demo/data-capture/citadel-biased-hiring-endpoint/AllTraffic/<path>.jsonl ./sample_capture.jsonl
head -n 2 sample_capture.jsonl
```

**Find + read latest CloudWatch logs for the endpoint (source of truth for container-side failures):**
```bash
aws logs describe-log-streams \
  --log-group-name /aws/sagemaker/Endpoints/citadel-biased-hiring-endpoint \
  --region ap-south-1 --order-by LastEventTime --descending --max-items 5 \
  --query "logStreams[*].{Name:logStreamName,LastEvent:lastEventTimestamp}" --output table

aws logs get-log-events \
  --log-group-name /aws/sagemaker/Endpoints/citadel-biased-hiring-endpoint \
  --log-stream-name "<paste-stream-name>" \
  --region ap-south-1 --limit 100
```

**Check IAM role trust + policies (if permission errors come back):**
```bash
aws iam get-role --role-name CitadelSageMakerExecutionRole --query 'Role.AssumeRolePolicyDocument'
aws iam list-attached-role-policies --role-name CitadelSageMakerExecutionRole
aws iam list-role-policies --role-name CitadelSageMakerExecutionRole
aws iam get-role-policy --role-name CitadelSageMakerExecutionRole --policy-name CitadelS3BucketAccess
```

**Check SageMaker instance quotas (before requesting a larger instance type):**
```bash
aws service-quotas list-service-quotas \
  --service-code sagemaker --region ap-south-1 \
  --query "Quotas[?contains(QuotaName, 'endpoint usage')].{Name:QuotaName,Code:QuotaCode,Value:Value}" \
  --output table
```

**Reminder — recurring gotcha:** after any interrupted/failed `deploy.py` run, always check for and delete a leftover endpoint config before retrying, or you'll hit `Cannot create already existing endpoint configuration`:
```bash
aws sagemaker delete-endpoint-config --endpoint-config-name citadel-biased-hiring-endpoint --region ap-south-1
```

**Reminder — region matters everywhere:** the endpoint lives in `ap-south-1`. Any AWS CLI command, and any Connect-mode request to Citadel's API, must use the matching region or it'll silently find nothing (see bug log above).

---

## 🎓 Key concepts

**Disparate Impact (DI)** — ratio of minority approval rate to majority approval rate. Legal threshold ≥ 0.80 (EEOC 4/5ths rule).

**Statistical Parity Difference (SPD)** — max approval rate minus min approval rate across groups. Flag if > 0.10.

**Equalized Odds Difference (EOD)** — largest gap in true/false positive rate across groups. Flag if > 0.10.

**Intersectionality** — bias analysis across combinations of protected attributes (e.g. gender × race) — a model can look fair on each attribute alone while being unfair for a specific subgroup.

**Counterfactual fairness** — a model is unfair if changing only a protected attribute (holding everything else constant) changes its decision for an otherwise-identical input.

---

## 📚 Stack

FastAPI · LangGraph · LangChain · boto3 (AWS) · Supabase (Postgres, Auth) · SHAP · scikit-learn · pandas · React/Next.js frontend

---

## 📄 License

MIT — private repo, not yet public.