from pydantic_settings import BaseSettings
from typing import Optional
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

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
    
    # Gemini API (for explanations)
    GEMINI_API_KEY: Optional[str] = None
    
    # Slack (for alerts)
    SLACK_WEBHOOK_URL: Optional[str] = None
    
    # CORS
    ALLOWED_ORIGINS: str = "http://localhost:3000"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    class Config:
        env_file = str(BASE_DIR / ".env")
        case_sensitive = True
    
    @property
    def allowed_origins_list(self) -> list[str]:
        return [o.strip() for o in self.ALLOWED_ORIGINS.split(",") if o.strip()]

settings = Settings()