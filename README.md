# Citadel AI — AI Governance & Bias Detection Platform

**EquiLens at the core. Production-grade governance on top.**

Citadel AI is a governance layer that connects to your cloud ML infrastructure (AWS SageMaker), continuously discovers deployed models, monitors their live predictions for bias, and surfaces violations before they become compliance incidents. The bias-detection engine is powered by EquiLens — a validated, working fairness-metrics library (SPD, Disparate Impact, Equalized Odds, SHAP explainability) — wrapped in a LangGraph-orchestrated governance workflow.

> Status: **Private / in development.** This README doubles as the working architecture doc, build log, and task board ahead of DevThon (Aug 20–21, 2026).
>
> **This file is our shared notes app for the project** — keep it updated with what's done, what's broken, what's next, and who's doing what.

---

## 👋 New here? Start with this section (Akanksha)

Welcome to the team. Backend, infra, AWS integration, and auth are **fully built and tested** — you don't need to touch any of that. Your job is frontend, and you have two tasks to get started tonight. Read this whole section before doing anything else.

### Task 1 — Deploy the test model (mechanical, no coding)

Clone the `Test-Model` repo (separate repo from this one — ask Aniketh for the link if you don't have it). Follow its README top to bottom:

```bash
python deploy.py
```

This deploys the demo hiring model to AWS SageMaker. A few things to expect:

- **You'll probably hit dependency issues** (numpy/scipy/sklearn version mismatches). Don't panic — the `Test-Model` README has the exact fix already documented from when this exact error happened before. Just match the versions pinned in `requirements1.txt`.
- **If you get `Cannot create already existing endpoint configuration`** — that means a leftover config from a previous attempt. Delete it with the AWS CLI command already in that README, then retry.
- **Ping Aniketh if you're stuck for more than 15 minutes** on any one error — most of what you'll hit has already been solved once and is documented.

You are not writing any new code for this task — just running commands and following documented fixes if something breaks.

### Task 2 — Start frontend (this is your real ownership piece)

**Auth is done on the backend.** You don't need to build or understand any backend code — just call it.

```js
import { createClient } from '@supabase/supabase-js'

const supabase = createClient(SUPABASE_URL, SUPABASE_ANON_KEY)

// Login button:
await supabase.auth.signInWithOAuth({ provider: 'google' })

// On every API call to the backend, attach the session token:
const { data: { session } } = await supabase.auth.getSession()
fetch('http://localhost:8000/api/v1/governance/check', {
  headers: { 'Authorization': `Bearer ${session.access_token}` },
  ...
})
```

Ask Aniketh for the real `SUPABASE_URL` and `SUPABASE_ANON_KEY` values (safe to share, they're meant to be public-facing).

**Start with just two screens:**
1. A login page (the Google sign-in button above)
2. A CSV upload page that hits `POST /api/v1/governance/analyze-csv` (multipart file upload, needs the `Authorization` header above) and displays the returned DI/SPD results

Keep it ugly/functional for now — styling and polish come later, once the core loop is visibly working end to end. See the **Frontend** section further down for the fuller screen list and the API shapes you'll be calling.

### 🤖 Using Claude (or another AI assistant) to help you build

You're welcome to paste this entire README into Claude (or ChatGPT, etc.) and ask it to help you build the frontend — that's exactly what it's for. A good first prompt is something like: *"Here's my project's README. I need to build a login page and a CSV upload page in [React/Next.js/whatever you're using] that call the API described here. Help me scaffold this."*

**One important boundary — read this before you start:**

- 🚫 **Do not modify any files inside `backend/`.** That includes `app/`, `config.py`, `main.py`, all of it. Everything backend-side is built, tested, and documented in this README already — it doesn't need touching, and unrelated changes there risk breaking things that are currently working and demo-ready.
- ✅ **Your scope is the `frontend/` folder** (create it if it doesn't exist yet) — anything inside it is yours to build freely.
- If you think something backend-side needs to change to support what you're building (a new endpoint, a different response shape, etc.) — **don't change it yourself, message Aniketh first.** It's a quick conversation, and it avoids two people editing the same backend code at once.
- If Claude (or any AI tool) suggests editing a backend file to "fix" something for you, that's a sign to stop and ask a human on the team first, not a sign to proceed.

---

## 👥 Team & ownership

| Person | Focus |
|---|---|
| **Aniketh** | Everything backend: LangGraph workflow, bias-engine wiring, Supabase persistence, API layer, CSV upload mode, real AWS S3 Data Capture integration, JWT auth via Supabase. All of this is done and verified against real infrastructure (see below) — not mocked. |
| **Akanksha** | Frontend (login, upload mode, connect mode screens) + deploying/running the demo AWS model as a real end user closer to the hackathon, to validate the product from a fresh user's perspective. Onboarding above. |

**Scope decision:** GCP and Azure connectors are cut entirely for the hackathon — AWS-only, for demo depth over breadth. `gcp_connector.py` / `azure_connector.py` have been deleted from the repo.

**Where things stand (Aug 8):** the entire backend governance pipeline — AWS discovery, real S3 Data Capture parsing, bias analysis, Supabase persistence, and JWT authentication — is built and verified end-to-end against real cloud infrastructure, not mocks. What remains is almost entirely the product surface: frontend, and (separately, backend-side, not blocking frontend) real cross-account STS AssumeRole testing.

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
        │  • Auth (Supabase JWT, Google sign-in) ✅ LIVE          │
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
| `monitor_predictions` | Pulls prediction data from discovered models | ✅ real S3 Data Capture parsing done and verified — `get_predictions()` pulls, lists, and parses real `.jsonl` objects straight from S3 |
| `ingest_csv` | Upload-mode equivalent of discover+monitor — treats an uploaded CSV as one synthetic model, its rows as predictions | ✅ built and validated against 3 datasets (see below) |
| `analyze_bias` | Calls EquiLens's real `analyze_bias()` / `compute_eod()` on the DataFrame of predictions | ✅ wired to real EquiLens functions; validated against a real-world dataset with a literature-known bias level, and against real live AWS traffic |
| `detect_violation` | Checks DI/SPD/EOD against thresholds, sets `needs_remediation` | ✅ working; both branches (violation / clean) confirmed on real data |
| `remediate` | Suggests fixes; uses SHAP top-features if available, generic list otherwise | ⚠️ working but generic-only — SHAP explanation is currently unavailable in the live monitoring flow (see note below) |
| `alert` | Logs alerts to `audit_log`; no external notification yet | ⚠️ audit-log only, no Slack/Jira integration yet |
| `complete_workflow` | Records execution time, finalizes `workflow_status`, persists run to Supabase under the real authenticated user | ✅ persistence wired and verified live — `audit_runs`, `models`, `bias_metrics`, `alerts` all confirmed writing correctly, including from real AWS runs and real Google-authenticated users |

**SHAP note:** `get_shap_values(model, X_train, X_test)` in `explainer.py` requires a *trained model artifact*, not just prediction input/output. Neither the AWS monitoring pipeline nor CSV upload mode load a model artifact, so SHAP is currently explicitly marked unavailable (`root_causes.note`) rather than faked. Loading the model artifact for real SHAP explanations is unscoped work — needs a decision on *how* (pull from SageMaker model registry? require user to upload artifact separately?).

### 📄 Upload mode — done and validated

Endpoint: `POST /api/v1/governance/analyze-csv` (multipart file upload, requires `Authorization: Bearer <token>` header).

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

**What it does:** `get_predictions()` in `aws_connector.py` no longer returns mock data. It now:

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
- **Still not tested end-to-end:** real STS AssumeRole flow (cross-account). Everything validated so far used static access keys for the same account. Needs a second AWS account (e.g. Akanksha's) + a real trust-policy role to fully validate before the demo. **This is backend/infra work — not part of frontend scope.**

### 🔐 Auth — JWT via Supabase (done, verified Aug 8)

**What it does:** every write-triggering governance route requires a real, verified identity instead of a hardcoded demo user.

- Frontend flow: `supabase.auth.signInWithOAuth({ provider: 'google' })` → Supabase handles the OAuth dance → returns a session with a real JWT. Attach it as `Authorization: Bearer <token>` on every API call.
- Backend: `app/auth.py` exposes a `get_current_user` FastAPI dependency, added to `/governance/check` and `/governance/analyze-csv`. It verifies the incoming JWT and returns the real `user_id` (`sub` claim), which flows into persistence — every `audit_runs` row now has the real user who triggered it.
- **Gotcha worth knowing:** this Supabase project issues **asymmetric `ES256`-signed JWTs** (Supabase's newer JWT signing-keys system), not legacy shared-secret `HS256` tokens. Verification is done against Supabase's public JWKS endpoint (`{SUPABASE_URL}/auth/v1/.well-known/jwks.json`), not a shared secret.
- `/governance/status` and `/governance/report` are currently **not** behind auth — read-only, filtered by `cloud_provider`/`model_id` rather than by user, nothing public-facing depends on them yet.

**Live end-to-end test (Aug 8):** signed in with Google → got a real Supabase session/JWT → curled `/governance/check` with it → backend correctly extracted the real `user_id` and persisted under it, confirmed directly in Supabase's `audit_runs` table. No more hardcoded demo-user rows going forward.

Google OAuth setup: Google Cloud Console → OAuth consent screen (User type: **External**, Publishing status: **Testing**, team members added as test users) → OAuth Client (Web application) → Authorized redirect URI `https://qxsyscrbnbrzzvctozht.supabase.co/auth/v1/callback` → Client ID + Secret pasted into Supabase's Google provider settings, toggled on.

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

**Persistence is done.** `complete_workflow` writes a real `audit_runs` row every run, plus `models`/`bias_metrics`/`alerts` rows whenever a model was discovered (AWS or CSV), tied to the real authenticated user.

**RLS is enabled** — backend uses the `service_role` key so it bypasses RLS by design and persistence is unaffected. Real per-user RLS policies (`user_id = auth.uid()`) are a defense-in-depth item for later — not needed for frontend to work, since frontend should always go through the FastAPI backend, never talk to Supabase directly.

### Scheduling — not started

- In-process scheduler (APScheduler) to trigger `run_governance_check()` per registered endpoint at its configured daily time.
- Manual on-demand check endpoint — **note:** actual route is `POST /governance/check`, not `/governance/run-now` as originally planned.
- First connect should trigger an immediate run.

---

## 💎 Differentiator features (beyond baseline monitoring)

- [ ] **Counterfactual flip testing** — flip only the protected attribute on a real prediction, re-infer, show the decision change side-by-side. Most legible, memorable feature in the product.
- [ ] **Adversarial fairness probing** — synthetic boundary-condition inputs near decision thresholds across protected groups, not just organic traffic.
- [ ] **Fairness policy-as-code** — versioned, declarative thresholds (e.g. `DI >= 0.8 for gender`) enforceable in CI/CD.
- [ ] **Fleet-wide risk posture view** — all registered models ranked by risk, security-dashboard style.

---

## 🖥️ Frontend — Akanksha's scope, starting now

Dark, dense, data-forward — governance/security tool aesthetic (Linear / Datadog / Wiz). Build minimal-and-working first, layer frameworks/polish later — don't go deep on styling until the core loop is visible end to end.

**Plan, in order:**
- [ ] Login — Google sign-in via Supabase Auth (see snippet in onboarding section above). Backend is done and tested; nothing to build backend-side.
- [ ] Upload-mode screen — CSV upload → `POST /governance/analyze-csv` → display DI/SPD/EOD results. Build against this first, it's the most stable backend path.
- [ ] Connect-mode screen — form for AWS credentials/region → `POST /governance/check` → discovered endpoints + live bias results. Backend validated end-to-end, safe to build against.
- [ ] Audit history view, pulling real `audit_runs`/`bias_metrics`/`alerts` (via backend endpoints, not direct Supabase queries)
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
- **Real JWT auth confirmed end-to-end** — Google sign-in via Supabase issues a real `ES256` JWT, backend verifies it against Supabase's public JWKS, extracts the real `user_id`, and that identity flows through the full governance workflow into Supabase
- `workflow_status` correctly reflects failure vs. success
- EquiLens's real `calculate_spd`, `calculate_di`, `compute_eod` are actually called by `analyze_bias` — validated against Kaggle Adult dataset (matches literature value) **and** against real live AWS traffic (matches the model's known bias pattern)
- Persistence fully working: `audit_runs`, `models`, `bias_metrics`, `alerts` all confirmed writing to live Supabase across both modes, including real AWS runs and real authenticated users
- CSV upload mode fully working: `POST /governance/analyze-csv`, tested against 3 datasets covering both the violation branch and the clean-audit branch
- Conditional graph branching (clean audit short-circuits past remediation/alerting) confirmed working on real data, not just by reading the code
- AWS-only: `CloudProvider` enum, request/response models, and all node branching now AWS-only; GCP/Azure code deleted

## ⏳ To-do (prioritized for Aug 20 build)

### High priority — core loop (backend, Aniketh)
- [x] ~~Persist governance workflow runs to Supabase~~ ✅ done
- [x] ~~Build CSV upload mode~~ ✅ done, verified against 3 datasets
- [x] ~~Real S3 Data Capture log fetch in `get_predictions()`~~ ✅ done, verified against 235 real predictions
- [x] ~~End-to-end test with real AWS credentials~~ ✅ done
- [x] ~~JWT auth via Supabase (Google sign-in)~~ ✅ done, verified end-to-end
- [x] ~~RLS enabled on Supabase tables~~ ✅ done
- [ ] Real STS AssumeRole flow, tested cross-account (needed before Akanksha connects as a separate real user — backend/infra, not frontend)
- [ ] Real per-user RLS policies (`user_id = auth.uid()`) — defense-in-depth, not blocking
- [ ] Investigate `.env` parse warnings — didn't break anything, worth cleaning up
- [ ] Decide whether `/governance/status` and `/governance/report` should require auth too
- [ ] `/governance/remediate` — currently a stub, needs real logic
- [ ] `clouds.py` — `connect`/`list`/`disconnect`/`test` endpoints are placeholder-only
- [ ] Add `_safe_uuid()` guard in `db.py` around all UUID-typed inserts
- [ ] Clearer error when Connect-mode `region` doesn't match the target endpoint's actual region (currently silently returns 0 models discovered)
- [ ] Optional: column auto-mapping / friendlier error for CSV upload

### High priority — frontend (Akanksha, starting now)
- [ ] Login (Google via Supabase Auth)
- [ ] Upload-mode screen
- [ ] Connect-mode screen
- [ ] Audit history view
- [ ] Live audit-log stream UI
- [ ] Counterfactual flip visual
- [ ] Historical trend chart

### Medium priority — differentiators
- [ ] Counterfactual flip testing node
- [ ] SHAP-reasoned remediation — needs the model-artifact-loading decision resolved first
- [ ] Slack webhook alert integration
- [ ] Scheduler (APScheduler) + manual "run now" endpoint

### Lower priority / post-hackathon
- [ ] Adversarial probing node
- [ ] Fairness policy-as-code + CI/CD gate
- [ ] Jira/GitHub alert integrations
- [ ] Pydantic field renames (`model_id` → `model_identifier`)
- [ ] Unit/integration test suite
- [x] ~~CORS hole~~ ✅ fixed

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
- `CORSMiddleware` used `allow_origins=["*"]` + `allow_credentials=True` simultaneously — invalid combination per spec, and a real open-CORS hole. Fixed via `ALLOWED_ORIGINS` env var + `allow_credentials=False` until JWT auth existed.
- `config.py` edit landed an `ALLOWED_ORIGINS` field + `allowed_origins_list` property at **module level**, outside the `Settings` class entirely — silent no-op until `main.py` tried to access `settings.allowed_origins_list` and hit `AttributeError`.
- `insert_audit_run()` wrote to `audit_runs`, a table `INIT_SQL` never actually created (only `audit_logs`, a different table/schema, existed). Silent failure caught by the persistence try/except — no crash, but nothing ever actually saved. Fixed by creating the missing table directly in Supabase.
- API layer hardcoded `user_id="demo_user"` (not a valid UUID) against a UUID-typed FK column → every persist attempt failed with `invalid input syntax for type uuid`. Fixed with a real demo user row + a named UUID constant, later replaced entirely by real JWT auth.
- `ingest_csv` was accidentally pasted into `state.py` instead of `nodes.py`, type-hinted with `CitadelState` before that class was defined later in the same file → circular self-import. Fixed by moving the function to `nodes.py`.
- `python-multipart` wasn't installed — required by FastAPI for any `UploadFile`/`File(...)` endpoint, silent until the CSV upload endpoint was actually added.
- First draft of the real `get_predictions()` rewrite got pasted back into the file with broken indentation — several methods landed at module level instead of indented inside `class AWSConnector`. Would have raised `AttributeError` at call time. Fixed by rewriting the full file with correct indentation.
- First live Connect-mode test with real credentials returned `models_discovered: 0`. Not an auth or discovery bug — the request specified the wrong region (`us-east-1` instead of `ap-south-1`, where the endpoint actually lives). SageMaker endpoint listing is region-scoped. Fixed by correcting the region in the request.
- Enabling RLS on Supabase tables immediately broke persistence (`42501`, "new row violates row-level security policy") because the backend was using the `anon` key, which *is* subject to RLS, with zero policies defined yet (default-deny). Fixed by switching to the `service_role` key, which bypasses RLS by design — correct for a trusted backend, not a workaround.
- After the `service_role` key swap, uvicorn logged repeated `Python-dotenv could not parse statement` warnings on startup. Didn't break anything, flagged for later cleanup — likely an unescaped/unquoted `.env` value.
- `run_governance_workflow`'s function *signature* wasn't updated when auth was added to its body — `user_id` was referenced before it was ever declared as a parameter, which would have raised `NameError` on every call. Fixed by adding `user_id: str = Depends(get_current_user)` to the signature.
- A standalone local test page (used to grab a real JWT before frontend existed) threw `Uncaught SyntaxError: Identifier 'supabase' has already been declared` — a naming collision between the Supabase CDN's global `window.supabase` and a locally-declared `const supabase`. Fixed by renaming the local variable.
- First `auth.py` implementation verified JWTs using `HS256` against a shared secret — the *legacy* Supabase auth method. A real token's header showed `"alg":"ES256"` — this project uses Supabase's newer **asymmetric JWT signing keys**. Fixed by rewriting `auth.py` to verify against Supabase's public JWKS endpoint instead, no shared secret needed. Confirmed working end-to-end with a real Google-authenticated user.

---

## 🔧 Useful AWS commands (Test-Model repo, reusable for future sessions)

These live in the sibling `Test-Model` repo (the intentionally-biased hiring model used as Citadel's demo ground truth).

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

**Reminder — region matters everywhere:** the endpoint lives in `ap-south-1`. Any AWS CLI command, and any Connect-mode request to Citadel's API, must use the matching region or it'll silently find nothing.

---

## 📜 Contribution guidelines

- **`backend/`** — owned by Aniketh. Fully built, tested against real infrastructure. Do not edit unless discussed first — a quick message beats two people touching the same working code at once.
- **`frontend/`** — owned by Akanksha. Build freely here.
- If a frontend need implies a backend change (new endpoint, different response shape, etc.), raise it as a conversation, not a direct edit.
- Keep this README updated as things change — it's the shared source of truth for the team and for AI tools either of us pastes it into.

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