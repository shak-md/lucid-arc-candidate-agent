from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # Azure Bot registration
    MICROSOFT_APP_ID: str
    MICROSOFT_APP_PASSWORD: str

    # Agent core service base URL
    AGENT_SERVICE_URL: str = "http://localhost:8000/api/v1"

    # Max file size in MB
    MAX_FILE_SIZE_MB: int = 10

    class Config:
        env_file = ".env"


settings = Settings()
