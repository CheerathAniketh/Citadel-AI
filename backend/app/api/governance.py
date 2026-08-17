from fastapi import APIRouter, HTTPException, Query, UploadFile, File, Depends
from app.auth import get_current_user
from typing import Dict, Any
import logging
from app.workflows.graph import run_governance_check, run_csv_governance_check
from app.models import (GovernanceCheckRequest, GovernanceCheckResponse, CloudProvider)
from datetime import datetime, timedelta
import pandas as pd
import io
from app.db import (
    get_latest_audit_run,
    get_model_uuid_by_external_id,
    get_latest_bias_metrics,
    get_audit_runs_in_range,
    get_alerts_in_range,
)


logger = logging.getLogger(__name__)

router = APIRouter()


def build_governance_response(final_state: dict) -> GovernanceCheckResponse:
    """
    Single source of truth for turning a raw workflow-graph final_state into
    the API's GovernanceCheckResponse shape. Both Connect mode (run_governance_check)
    and Upload mode (run_csv_governance_check) produce the same final_state shape
    (discovered_models / bias_metrics / alerts / recommended_fixes / audit_log —
    see graph.py docstring), so this is the one place that reshapes it into the
    response contract. Neither route should build this dict by hand — if the
    response shape ever needs to change, it changes here once, for both modes.
    """
    bias_metrics_raw = final_state.get('bias_metrics') or {}
    timestamp_str = bias_metrics_raw.get('timestamp')
    response_timestamp = (
        datetime.fromisoformat(timestamp_str) if timestamp_str
        else final_state.get('workflow_end_time') or datetime.now()
    )

    alerts = [
        {
            'id': f"alert_{i}",
            'alert_type': a.get('type', 'bias_warning'),
            'severity': a.get('severity', 'warning'),
            'message': a.get('message', ''),
            'metric_value': a.get('value'),
            'threshold': a.get('threshold'),
            'created_at': response_timestamp,
            'status': 'active'
        }
        for i, a in enumerate(final_state.get('alerts', []))
    ]

    recommendations = [
        {
            'action': r.get('action', ''),
            'feature': r.get('feature'),
            'reason': r.get('reason', ''),
            'expected_impact': r.get('expected_impact', '')
        }
        for r in final_state.get('recommended_fixes', [])
    ]

    return GovernanceCheckResponse(
        status=final_state.get('workflow_status', 'failed'),
        models_discovered=final_state.get('discovered_count', 0),
        bias_metrics={
            model_id: {
                'disparate_impact': bias_metrics_raw.get('disparate_impact'),
                'statistical_parity_diff': bias_metrics_raw.get('statistical_parity_diff'),
                'equalized_odds': bias_metrics_raw.get('equalized_odds'),
                'samples_count': bias_metrics_raw.get('samples_count', 0),
                'affected_count': 0,  # TODO: Calculate
                'timestamp': response_timestamp,
                'status': bias_metrics_raw.get('status', 'unknown')
            }
            for model_id in [m['id'] for m in final_state.get('discovered_models', [])]
        },
        alerts=alerts,
        recommendations=recommendations,
        audit_log=final_state.get('audit_log', []),
        timestamp=response_timestamp
    )


@router.post("/governance/analyze-csv", response_model=GovernanceCheckResponse)
async def analyze_csv_upload(
    file: UploadFile = File(...),
    user_id: str = Depends(get_current_user)
):
    """
    Upload-mode governance check. Same bias analysis as Connect mode, run on a
    user-supplied CSV instead of live AWS predictions. Response shape is
    identical to /governance/check — both go through build_governance_response.

    Required columns: 'prediction', 'group'. Optional: 'actual_label' (enables EOD).
    """
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a .csv")

    try:
        contents = await file.read()
        df = pd.read_csv(io.BytesIO(contents))
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not parse CSV: {e}")

    missing = [c for c in ('prediction', 'group') if c not in df.columns]
    if missing:
        raise HTTPException(status_code=400, detail=f"CSV missing required column(s): {missing}")

    try:
        final_state = await run_csv_governance_check(user_id=user_id, filename=file.filename, df=df)
        response = build_governance_response(final_state)
        logger.info(f"✅ CSV governance check complete: {response.status}")
        return response
    except Exception as e:
        logger.error(f"❌ CSV governance check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/governance/check", response_model=GovernanceCheckResponse)
async def run_governance_workflow(request: GovernanceCheckRequest, user_id: str = Depends(get_current_user)):
    """
    Execute full governance workflow on connected cloud

    Flow:
    1. DISCOVER: Auto-find all models in cloud
    2. MONITOR: Fetch recent predictions
    3. ANALYZE: Compute bias metrics using EquiLens
    4. DETECT: Check fairness violations
    5. REMEDIATE: Suggest fixes (if needed)
    6. ALERT: Trigger notifications

    Args:
        request: Cloud provider and credentials

    Returns:
        Governance report with metrics, alerts, and recommendations

Example:
        POST /api/v1/governance/check
        {
            "cloud_provider": "aws",
            "credentials": {
                "account_id": "123456789",
                "iam_role_arn": "arn:aws:iam::123456789:role/CitadelRole"
            }
        }
    """
    try:
        logger.info(f"🎯 Starting governance check for {request.cloud_provider}...")

        final_state = await run_governance_check(
            user_id=user_id,
            cloud_provider=request.cloud_provider,
            cloud_credentials=request.credentials
        )

        response = build_governance_response(final_state)

        logger.info(f"✅ Governance check complete: {response.status}")
        return response

    except Exception as e:
        logger.error(f"❌ Governance check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/governance/status")
async def get_governance_status(
    cloud_provider: str = Query(...),
    model_id: str = Query(None)
):
    """
    Get current governance status — real data from Supabase.

    Without model_id: latest overall audit run for this cloud provider.
    With model_id: latest bias metrics recorded for that specific model.
    """
    try:
        if model_id:
            model_uuid = get_model_uuid_by_external_id(cloud_provider, model_id)
            if not model_uuid:
                return {
                    "status": "no_data",
                    "cloud_provider": cloud_provider,
                    "model_id": model_id,
                    "message": "No governance checks found for this model yet"
                }

            metrics = get_latest_bias_metrics(model_uuid)
            if not metrics:
                return {
                    "status": "no_data",
                    "cloud_provider": cloud_provider,
                    "model_id": model_id,
                    "message": "Model discovered but no bias metrics recorded yet"
                }

            di = metrics.get("disparate_impact")
            metric_status = "critical" if di is not None and di < 0.8 else "ok"

            return {
                "status": "ok",
                "cloud_provider": cloud_provider,
                "model_id": model_id,
                "last_check": metrics.get("timestamp"),
                "metrics": {
                    "disparate_impact": di,
                    "statistical_parity_diff": metrics.get("statistical_parity_diff"),
                    "equalized_odds": metrics.get("equalized_odds"),
                    "status": metric_status
                }
            }

        run = get_latest_audit_run(cloud_provider)
        if not run:
            return {
                "status": "no_data",
                "cloud_provider": cloud_provider,
                "model_id": None,
                "message": "No governance checks have been run yet for this cloud provider"
            }

        return {
            "status": run.get("status"),
            "cloud_provider": cloud_provider,
            "model_id": None,
            "last_check": run.get("created_at"),
            "models_discovered": run.get("models_discovered"),
            "execution_time_ms": run.get("execution_time_ms")
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/governance/remediate")
async def apply_remediation(
    model_id: str,
    action: str,
    feature: str = None
):
    """
    Apply a remediation action to a model

    Args:
        model_id: Target model
        action: 'drop_feature', 'retrain', 'quarantine'
        feature: Feature to drop (if action is drop_feature)

    Returns:
        Remediation status and expected impact
    """
    try:
        if action == 'drop_feature' and not feature:
            raise ValueError("feature required for drop_feature action")

        # TODO: Implement remediation logic
        return {
            "status": "applied",
            "action": action,
            "feature": feature,
            "expected_impact": "DI improves from 0.45 to 0.82",
            "model_id": model_id
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/governance/report")
async def get_audit_report(
    model_id: str = Query(None),
    cloud_provider: str = Query(None),
    start_date: str = Query(None, description="ISO date, defaults to 30 days ago"),
    end_date: str = Query(None, description="ISO date, defaults to now")
):
    """
    Get detailed audit report for compliance — real data from Supabase.

    Filters by cloud_provider and/or model_id (model_id requires cloud_provider
    to resolve to an internal model UUID). Defaults to the last 30 days.
    """
    try:
        end_dt = datetime.fromisoformat(end_date) if end_date else datetime.utcnow()
        start_dt = datetime.fromisoformat(start_date) if start_date else end_dt - timedelta(days=30)

        cp_value = cloud_provider

        runs = get_audit_runs_in_range(start_dt.isoformat(), end_dt.isoformat(), cp_value)
        checks_performed = len(runs)

        model_uuid = None
        if model_id and cloud_provider:
            model_uuid = get_model_uuid_by_external_id(cloud_provider, model_id)

        alerts = get_alerts_in_range(start_dt.isoformat(), end_dt.isoformat(), model_uuid)
        violations_found = len(alerts)
        violations_resolved = len([a for a in alerts if a.get("status") == "resolved"])

        if violations_found == 0:
            compliance_status = "compliant"
        elif violations_resolved == violations_found:
            compliance_status = "compliant"
        elif violations_resolved > 0:
            compliance_status = "partial"
        else:
            compliance_status = "non_compliant"

        return {
            "report_id": f"report_{int(datetime.utcnow().timestamp())}",
            "generated_at": datetime.utcnow().isoformat(),
            "model_id": model_id,
            "cloud_provider": cp_value,
            "period": f"{start_dt.isoformat()} to {end_dt.isoformat()}",
            "checks_performed": checks_performed,
            "violations_found": violations_found,
            "violations_resolved": violations_resolved,
            "compliance_status": compliance_status,
            "regulations_covered": ["EEOC", "EU AI Act", "GDPR"],
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))