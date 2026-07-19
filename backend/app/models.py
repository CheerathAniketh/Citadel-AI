from pydantic import BaseModel, EmailStr
from typing import Optional, List, Dict, Any
from datetime import datetime
from enum import Enum

# ==================== Cloud Providers ====================
class CloudProvider(str, Enum):
    AWS = "aws"
    GCP = "gcp"
    AZURE = "azure"

class AlertType(str, Enum):
    BIAS_CRITICAL = "bias_critical"
    BIAS_WARNING = "bias_warning"
    DRIFT = "drift"
    COMPLIANCE = "compliance"

class AlertSeverity(str, Enum):
    CRITICAL = "critical"
    WARNING = "warning"
    INFO = "info"

# ==================== Cloud Connection ====================
class AWSCredentials(BaseModel):
    account_id: str
    iam_role_arn: str

class GCPCredentials(BaseModel):
    project_id: str
    service_account_json: Dict[str, Any]

class AzureCredentials(BaseModel):
    subscription_id: str
    app_registration_id: str

class ConnectCloudRequest(BaseModel):
    cloud_provider: CloudProvider
    credentials: Dict[str, Any]  # Flexible for different clouds

class CloudAccountResponse(BaseModel):
    id: str
    cloud_provider: CloudProvider
    created_at: datetime

# ==================== Models ====================
class ModelResponse(BaseModel):
    id: str
    model_name: str
    model_id: str
    endpoint_url: Optional[str]
    cloud_provider: CloudProvider
    discovered_at: datetime
    last_monitored: Optional[datetime]
    is_active: bool

class ModelListResponse(BaseModel):
    total: int
    models: List[ModelResponse]

# ==================== Predictions ====================
class PredictionRequest(BaseModel):
    model_id: str
    input_features: Dict[str, Any]
    prediction: str
    actual_label: Optional[str] = None
    group_membership: Optional[str] = None

class PredictionResponse(BaseModel):
    id: int
    model_id: str
    timestamp: datetime
    prediction: str
    group_membership: Optional[str]

# ==================== Bias Metrics ====================
class BiasMetricsResponse(BaseModel):
    disparate_impact: float
    statistical_parity_diff: float
    equalized_odds: float
    samples_count: int
    affected_count: int
    timestamp: datetime
    status: str  # "healthy", "warning", "critical"

# ==================== Alerts ====================
class AlertResponse(BaseModel):
    id: str
    alert_type: AlertType
    severity: AlertSeverity
    message: str
    metric_value: Optional[float]
    threshold: Optional[float]
    created_at: datetime
    status: str

class AlertListResponse(BaseModel):
    total: int
    alerts: List[AlertResponse]

# ==================== Governance ====================
class GovernanceCheckRequest(BaseModel):
    cloud_provider: CloudProvider
    credentials: Dict[str, Any]

class RecommendationResponse(BaseModel):
    action: str  # 'drop_feature', 'retrain', 'quarantine'
    feature: Optional[str]
    reason: str
    expected_impact: str

class GovernanceCheckResponse(BaseModel):
    status: str  # "healthy", "warning", "critical"
    models_discovered: int
    bias_metrics: Dict[str, BiasMetricsResponse]
    alerts: List[AlertResponse]
    recommendations: List[RecommendationResponse]
    audit_log: List[str]
    timestamp: datetime

# ==================== Workflows ====================
class WorkflowStateResponse(BaseModel):
    current_node: str
    discovered_models: int
    predictions_fetched: int
    bias_computed: bool
    alerts_triggered: int
    audit_log: List[str]

# ==================== Health ====================
class HealthResponse(BaseModel):
    status: str
    app: str
    version: str