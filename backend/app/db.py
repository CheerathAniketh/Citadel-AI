from supabase import create_client, Client
from config import settings
import logging
from datetime import datetime
from typing import Dict, Any

logger = logging.getLogger(__name__)

# Initialize Supabase client
supabase: Client = create_client(
    settings.SUPABASE_URL,
    settings.SUPABASE_KEY
)

async def init_db():
    """Initialize database tables if they don't exist"""
    try:
        # Test connection
        result = supabase.table("users").select("count").execute()
        logger.info("✅ Connected to Supabase")
        
    except Exception as e:
        logger.error(f"❌ Supabase connection failed: {e}")
        raise

def get_supabase() -> Client:
    """Get Supabase client"""
    return supabase


def upsert_model(cloud_provider: str, model_id: str, model_name: str, endpoint_url: str = None) -> str:
    """Find or create a row in `models` for this discovered model, returning its UUID."""
    existing = (
        supabase.table("models")
        .select("id")
        .eq("cloud_provider", cloud_provider)
        .eq("model_id", model_id)
        .limit(1)
        .execute()
    )
    if existing.data:
        model_uuid = existing.data[0]["id"]
        supabase.table("models").update({
            "last_monitored": datetime.utcnow().isoformat()
        }).eq("id", model_uuid).execute()
        return model_uuid

    result = supabase.table("models").insert({
        "cloud_provider": cloud_provider,
        "model_id": model_id,
        "model_name": model_name,
        "endpoint_url": endpoint_url,
        "last_monitored": datetime.utcnow().isoformat(),
    }).execute()
    return result.data[0]["id"]


def insert_audit_run(cloud_provider: str, status: str, models_discovered: int,
                      execution_time_ms: int, error: str = None) -> str:
    """Record one governance check run, returning its UUID."""
    result = supabase.table("audit_runs").insert({
        "cloud_provider": cloud_provider,
        "status": status,
        "models_discovered": models_discovered,
        "execution_time_ms": execution_time_ms,
        "error": error,
    }).execute()
    return result.data[0]["id"]


def insert_bias_metrics(model_uuid: str, metrics: Dict[str, Any]) -> None:
    """Record one bias-metrics snapshot for a model."""
    supabase.table("bias_metrics").insert({
        "model_id": model_uuid,
        "disparate_impact": metrics.get("disparate_impact"),
        "statistical_parity_diff": metrics.get("statistical_parity_diff"),
        "equalized_odds": metrics.get("equalized_odds"),
        "samples_count": metrics.get("samples_count", 0),
        "affected_count": 0,
    }).execute()


def insert_alert(model_uuid: str, alert: Dict[str, Any]) -> None:
    """Record one detected violation for a model."""
    supabase.table("alerts").insert({
        "model_id": model_uuid,
        "alert_type": alert.get("type", "bias_warning"),
        "severity": alert.get("severity", "warning"),
        "message": alert.get("message", ""),
        "metric_value": alert.get("value"),
        "threshold": alert.get("threshold"),
        "status": "active",
    }).execute()

# SQL to create tables (run manually in Supabase SQL editor if needed)
INIT_SQL = """
-- Users table
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Cloud accounts (AWS/GCP/Azure credentials)
CREATE TABLE IF NOT EXISTS cloud_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    cloud_provider VARCHAR NOT NULL, -- 'aws', 'gcp', 'azure'
    
    -- AWS
    aws_account_id VARCHAR,
    aws_iam_role_arn VARCHAR,
    
    -- GCP
    gcp_project_id VARCHAR,
    gcp_service_account_json JSONB,
    
    -- Azure
    azure_subscription_id VARCHAR,
    azure_app_registration_id VARCHAR,
    
    created_at TIMESTAMP DEFAULT NOW(),
    last_sync TIMESTAMP
);

-- Discovered models
CREATE TABLE IF NOT EXISTS models (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    cloud_provider VARCHAR NOT NULL,
    model_name VARCHAR NOT NULL,
    model_id VARCHAR NOT NULL,
    endpoint_url VARCHAR,
    discovered_at TIMESTAMP DEFAULT NOW(),
    last_monitored TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE
);

-- Predictions (streaming data)
CREATE TABLE IF NOT EXISTS predictions (
    id BIGSERIAL PRIMARY KEY,
    model_id UUID REFERENCES models(id) ON DELETE CASCADE,
    timestamp TIMESTAMP DEFAULT NOW(),
    input_features JSONB,
    prediction VARCHAR,
    actual_label VARCHAR,
    group_membership VARCHAR, -- e.g., 'gender=F', 'age=65+'
    confidence FLOAT
);

-- Bias metrics (time-series)
CREATE TABLE IF NOT EXISTS bias_metrics (
    id BIGSERIAL PRIMARY KEY,
    model_id UUID REFERENCES models(id) ON DELETE CASCADE,
    timestamp TIMESTAMP DEFAULT NOW(),
    disparate_impact FLOAT,
    statistical_parity_diff FLOAT,
    equalized_odds FLOAT,
    samples_count INTEGER,
    affected_count INTEGER
);

-- Alerts
CREATE TABLE IF NOT EXISTS alerts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    model_id UUID REFERENCES models(id) ON DELETE CASCADE,
    alert_type VARCHAR NOT NULL, -- 'bias_critical', 'drift', 'compliance'
    severity VARCHAR NOT NULL, -- 'critical', 'warning', 'info'
    message TEXT,
    metric_value FLOAT,
    threshold FLOAT,
    created_at TIMESTAMP DEFAULT NOW(),
    status VARCHAR DEFAULT 'active', -- 'active', 'resolved', 'ignored'
    resolved_at TIMESTAMP
);

-- Governance audit log
CREATE TABLE IF NOT EXISTS audit_logs (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    action VARCHAR NOT NULL,
    resource_type VARCHAR,
    resource_id VARCHAR,
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_models_user ON models(user_id);
CREATE INDEX IF NOT EXISTS idx_predictions_model ON predictions(model_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_bias_metrics_model ON bias_metrics(model_id, timestamp);
CREATE INDEX IF NOT EXISTS idx_alerts_model ON alerts(model_id, created_at);
CREATE INDEX IF NOT EXISTS idx_audit_logs_user ON audit_logs(user_id, created_at);
"""