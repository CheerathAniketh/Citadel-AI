from typing import TypedDict, List, Dict, Any, Optional
from datetime import datetime

class CitadelState(TypedDict, total=False):
    """
    State that flows through Citadel's governance workflow.
    Tracks all data from discovery → monitoring → analysis → remediation.
    """
    
    # ==================== User & Cloud Context ====================
    user_id: str
    cloud_provider: str #aws only
    cloud_credentials: Dict[str, Any]
    
    # ==================== Discovery Phase ====================
    discovered_models: List[Dict[str, Any]]
    discovered_count: int
    discovery_error: Optional[str]
    
    # ==================== Monitoring Phase ====================
    recent_predictions: List[Dict[str, Any]]
    predictions_count: int
    monitoring_error: Optional[str]
    
    # ==================== Analysis Phase ====================
    bias_metrics: Dict[str, Any]  # {disparate_impact, spd, equalized_odds, ...}
    root_causes: Dict[str, Any]  # SHAP explanations
    analysis_error: Optional[str]
    
    # ==================== Detection Phase ====================
    alerts: List[Dict[str, Any]]
    needs_remediation: bool
    detection_error: Optional[str]
    
    # ==================== Remediation Phase ====================
    recommended_fixes: List[Dict[str, Any]]
    remediation_error: Optional[str]
    
    # ==================== Alerting Phase ====================
    alert_status: str  # "pending", "sent", "failed"
    alerted_to: List[str]  # ["slack", "jira", "github"]
    alerting_error: Optional[str]
    
    # ==================== Audit Trail ====================
    audit_log: List[str]
    workflow_start_time: datetime
    workflow_end_time: Optional[datetime]
    total_execution_time_ms: Optional[int]
    
    # ==================== Overall Status ====================
    workflow_status: str  # "running", "completed", "failed"
    error: Optional[str]

def create_initial_state(
    user_id: str,
    cloud_provider: str,
    cloud_credentials: Dict[str, Any]
) -> CitadelState:
    """Create initial state for a new governance check"""
    return CitadelState(
        user_id=user_id,
        cloud_provider=cloud_provider,
        cloud_credentials=cloud_credentials,
        discovered_models=[],
        discovered_count=0,
        discovery_error=None,
        recent_predictions=[],
        predictions_count=0,
        monitoring_error=None,
        bias_metrics={},
        root_causes={},
        analysis_error=None,
        alerts=[],
        needs_remediation=False,
        detection_error=None,
        recommended_fixes=[],
        remediation_error=None,
        alert_status="pending",
        alerted_to=[],
        alerting_error=None,
        audit_log=[],
        workflow_start_time=datetime.now(),
        workflow_end_time=None,
        total_execution_time_ms=None,
        workflow_status="running",
        error=None,
    )