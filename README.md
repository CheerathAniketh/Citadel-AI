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
| **Aniketh** | Core backend: LangGraph workflow, bias-engine wiring, Supabase persistence, API layer |
| **Akanksha** | AWS integration layer (STS AssumeRole, real S3 Data Capture fetch) — new to backend dev, vibecoding with AI assistance. Onboarding notes below. |

**Scope decision:** GCP and Azure connectors are cut entirely for the hackathon — AWS-only, for demo depth over breadth. `gcp_connector.py` / `azure_connector.py` have been deleted from the repo.

**Sequencing decision:** the real AWS integration (STS AssumeRole, real SageMaker/S3 data fetch — currently still mocked) has been intentionally pushed to *last* priority. Supabase persistence of workflow runs is the current active work.

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

**Key design note:** DETECT branches conditionally — a clean audit short-circuits toward `COMPLETE` instead of always walking through remediation and alerting (both nodes early-return harmlessly when there's nothing to do). This is the actual reason to use a graph orchestrator instead of a flat function pipeline.

### Node-by-node — current real status (verified by running the code, not just reading it)

| Node | What it does | Status |
|---|---|---|
| `discover_models` | Lists real SageMaker endpoints via `AWSConnector` | ✅ runs end-to-end; auth currently static keys only — real STS AssumeRole not yet wired (Akanksha) |
| `monitor_predictions` | Pulls prediction data from discovered models | ⚠️ runs, but `get_predictions()` always returns **mock data**, even against real endpoints — real S3 Data Capture parsing not built (Akanksha) |
| `analyze_bias` | Calls EquiLens's real `analyze_bias()` / `compute_eod()` on the DataFrame of predictions | ✅ wired to real EquiLens functions (was previously silently reimplemented inline + shadowed import — fixed) |
| `detect_violation` | Checks DI/SPD/EOD against thresholds, sets `needs_remediation` | ✅ working |
| `remediate` | Suggests fixes; uses SHAP top-features if available, generic list otherwise | ⚠️ working but generic-only — SHAP explanation is currently unavailable in the live monitoring flow (see note below) |
| `alert` | Logs alerts to `audit_log`; no external notification yet | ⚠️ audit-log only, no Slack/Jira integration yet |
| `complete_workflow` | Records execution time, finalizes `workflow_status` | ✅ fixed — previously always overwrote status to `'completed'` even after an earlier node failure; now preserves `'failed'` correctly |

**SHAP note:** `get_shap_values(model, X_train, X_test)` in `explainer.py` requires a *trained model artifact*, not just prediction input/output. The monitoring pipeline only has prediction I/O from SageMaker — it doesn't load the model itself. So SHAP is currently explicitly marked unavailable (`root_causes.note`) rather than faked. Loading the model artifact for real SHAP explanations is unscoped work — needs a decision on *how* (pull from SageMaker model registry? require user to upload artifact separately?).

### AWS connection model (target design — not fully live yet)

- **Cross-account IAM role assumption** (STS `AssumeRole`) — user creates a read-only role in their account trusting Citadel's account. No raw access keys stored, ever.
  - Constructor supports `iam_role_arn` and calls `sts.assume_role()` when present; falls back to static `access_key_id`/`secret_access_key` only for local dev when no role ARN is given.
- Scoped permissions only: `sagemaker:ListEndpoints`, `sagemaker:DescribeEndpoint`, `s3:GetObject` on the data-capture bucket.
- **Data Capture must be enabled** on the target SageMaker endpoint at creation time — prerequisite for `monitor_predictions` to read anything real.
- **Not yet built:** the actual S3 Data Capture log parsing (locating the bucket, listing/reading JSONL objects, mapping captured payloads to the `{prediction, group, actual_label}` shape the bias engine expects). This is real, separately-scoped work — assigned to Akanksha, intentionally last priority.

### Data model (Supabase) — **schema created, nothing persists yet**

Tables exist live in Supabase (created via `INIT_SQL` in `db.py`, RLS off for now — no auth system yet, fine for hackathon demo, **not fine if this goes anywhere near production**):

```
users
  └─ connected_accounts (role_arn, region)
       └─ registered_endpoints (endpoint_arn, schedule_time)
            └─ audit_runs (run_id, timestamp, status)
                 └─ bias_metrics (di, spd, eod, severity)
                 └─ alerts
```

**Current gap (active work):** `db.py` connects successfully (verified — real HTTP round-trip confirmed against live project), but **no node writes anything to these tables**. Every governance check is currently fully stateless — close the app, lose the run. Wiring real persistence into `complete_workflow` (or a dedicated node) is next up.

### Scheduling — not started

- In-process scheduler (APScheduler) to trigger `run_governance_check()` per registered endpoint at its configured daily time.
- Manual `POST /governance/run-now` endpoint for on-demand checks/demos.
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

- [ ] Live-streaming audit log (SSE/websocket) rendering `audit_log` as it's generated
- [ ] Counterfactual flip panel as the hero visual
- [ ] Severity color language (green/amber/red)
- [ ] Upload-mode and Connect-mode as two clear entry paths from login
- [ ] Historical bias trend chart per endpoint (DI over time, from `audit_runs`)

---

## ✅ What's actually working right now (verified by running it, not just reading code)

- FastAPI app imports and starts cleanly; CORS + health check live
- Real Supabase connection confirmed (`GET .../users?select=count` → `200 OK` against live hosted project)
- LangGraph workflow executes fully async end-to-end (`discover → monitor → analyze → detect → remediate → alert → complete`) without crashing
- Real AWS auth attempted on `discover_models` (correctly rejects invalid/test credentials with a real `UnrecognizedClientException`)
- `workflow_status` correctly reflects failure vs. success (previously always reported `"completed"` even on a real discovery failure — fixed)
- EquiLens's real `calculate_spd`, `calculate_di`, `compute_eod` are actually called by `analyze_bias` (previously imported but shadowed/unused — an inline reimplementation ran instead)
- AWS-only: `CloudProvider` enum, request/response models, and all node branching now AWS-only; GCP/Azure code deleted

## ⏳ To-do (prioritized for Aug 20 build)

### High priority — core loop (Aniketh, active)
- [ ] **Persist governance workflow runs to Supabase** — `audit_runs`, `bias_metrics`, `alerts` tables currently unused; nothing survives past the request. *(current focus)*
- [ ] End-to-end test with real (even free-tier/limited) AWS credentials — confirm real `list_endpoints()` behavior against an actual account
- [ ] `/governance/status`, `/governance/remediate`, `/governance/report` endpoints — currently hardcoded placeholder responses; need real DB-backed queries once persistence lands
- [ ] `clouds.py` — `connect`/`list`/`disconnect`/`test` endpoints are placeholder-only; need real Supabase reads/writes to `cloud_accounts`

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
- [ ] **API authentication (JWT)** — currently no auth anywhere; `allow_origins=["*"]` + `allow_credentials=True` in CORS is a real hole. Fine for hackathon demo, must-fix before anything public-facing.
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