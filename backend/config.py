from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Environment variables and configuration"""
    
    # FastAPI
    APP_NAME: str = "Citadel AI"
    APP_VERSION: str = "0.1.0"
    DEBUG: bool = True
    
    # Database (Supabase)
    SUPABASE_URL: str
    SUPABASE_KEY: str
    
    # AWS
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    AWS_REGION: str = "us-east-1"
    
    # GCP
    GCP_PROJECT_ID: Optional[str] = None
    GCP_CREDENTIALS_JSON: Optional[str] = None
    
    # Azure
    AZURE_SUBSCRIPTION_ID: Optional[str] = None
    AZURE_TENANT_ID: Optional[str] = None
    AZURE_CLIENT_ID: Optional[str] = None
    AZURE_CLIENT_SECRET: Optional[str] = None
    
    # Gemini API (for explanations)
    GEMINI_API_KEY: Optional[str] = None
    
    # Slack (for alerts)
    SLACK_WEBHOOK_URL: Optional[str] = None
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    class Config:
        env_file = ".env"
        case_sensitive = True

settings = Settings()