from fastapi import APIRouter, HTTPException, Query
from typing import Dict, Any
import logging
from app.workflows.graph import run_governance_check
from app.models import (GovernanceCheckRequest,GovernanceCheckResponse,CloudProvider)
from datetime import datetime


logger = logging.getLogger(__name__)

router = APIRouter()

@router.post("/governance/check", response_model=GovernanceCheckResponse)
async def run_governance_workflow(request: GovernanceCheckRequest):
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
        DEMO_USER_ID = "00000000-0000-0000-0000-000000000001"  # TODO: replace with real auth once JWT lands
        # Execute governance workflow
        final_state = await run_governance_check(
            user_id=DEMO_USER_ID,  # TODO: Get from auth
            cloud_provider=request.cloud_provider.value,
            cloud_credentials=request.credentials
        )
        
        # Build response
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
        
        response = GovernanceCheckResponse(
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
        
        logger.info(f"✅ Governance check complete: {response.status}")
        return response
    
    except Exception as e:
        logger.error(f"❌ Governance check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/governance/status")
async def get_governance_status(
    cloud_provider: CloudProvider = Query(...),
    model_id: str = Query(None)
):
    """
    Get current governance status for a model
    
    Args:
        cloud_provider: Which cloud (aws)
        model_id: Optional model ID filter
    
    Returns:
        Current metrics and alert status
    """
    try:
        # TODO: Implement status retrieval from database
        return {
            "status": "ok",
            "cloud_provider": cloud_provider.value,
            "model_id": model_id,
            "last_check": "2024-01-01T00:00:00Z",
            "metrics": {
                "disparate_impact": 0.75,
                "status": "warning"
            }
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
    start_date: str = Query(None),
    end_date: str = Query(None)
):
    """
    Get detailed audit report for compliance
    
    Args:
        model_id: Optional filter by model
        start_date: Start date (ISO format)
        end_date: End date (ISO format)
    
    Returns:
        Comprehensive audit trail and compliance evidence
    """
    try:
        # TODO: Retrieve from database
        return {
            "report_id": "report_12345",
            "generated_at": "2024-01-01T00:00:00Z",
            "model_id": model_id,
            "period": f"{start_date} to {end_date}",
            "checks_performed": 10,
            "violations_found": 2,
            "violations_resolved": 1,
            "compliance_status": "partial",
            "regulations_covered": ["EEOC", "EU AI Act", "GDPR"],
            "audit_log": []
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))