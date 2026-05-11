from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    # Anthropic
    ANTHROPIC_API_KEY: str

    # Workday - supports both auth modes
    WORKDAY_TENANT_URL: str
    WORKDAY_AUTH_MODE: str = "basic"  # "basic" or "oauth2"

    # Basic auth (ISU)
    WORKDAY_ISU_USERNAME: str = ""
    WORKDAY_ISU_PASSWORD: str = ""

    # OAuth 2.0
    WORKDAY_CLIENT_ID: str = ""
    WORKDAY_CLIENT_SECRET: str = ""
    WORKDAY_TOKEN_URL: str = ""

    # App
    ALLOWED_ORIGINS: List[str] = ["*"]
    AUDIT_LOG_DB_URL: str = "sqlite:///./audit.db"

    # Pool cache TTL in seconds
    POOL_CACHE_TTL: int = 300

    class Config:
        env_file = ".env"


settings = Settings()
