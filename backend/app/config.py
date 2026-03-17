"""Application settings loaded from environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    app_name: str = "GetVul"
    debug: bool = False
    environment: str = "production"
    database_url: str = "postgresql+asyncpg://getvul:getvul@localhost:5432/getvul"
    redis_url: str = "redis://localhost:6379/0"
    jwt_secret_key: str = "CHANGE-ME-IN-PRODUCTION"
    jwt_algorithm: str = "HS256"
    jwt_access_token_expire_minutes: int = 15
    jwt_refresh_token_expire_days: int = 7
    google_client_id: str = ""
    google_client_secret: str = ""
    google_redirect_uri: str = "https://app.getvul.app/auth/callback/google"
    azure_client_id: str = ""
    azure_client_secret: str = ""
    azure_redirect_uri: str = "https://app.getvul.app/auth/callback/azure"
    sync_interval_minutes: int = 15
    aws_region: str = "us-east-1"
    secrets_manager_prefix: str = "getvul/"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


settings = Settings()
