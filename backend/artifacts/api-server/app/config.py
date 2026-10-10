from functools import lru_cache

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "QuikPatient API"
    mock_mode: bool = True
    database_url: str | None = None
    redis_url: str = "redis://localhost:6379/0"
    session_secret: SecretStr
    access_token_minutes: int = 15
    refresh_token_days: int = 30
    idle_session_minutes: int = 30
    sos_ttl_minutes: int = 10
    sos_otp_ttl_minutes: int = 10
    audit_anchor_interval_minutes: int = 60
    sos_rate_limit_per_doctor_day: int = 10
    sos_abuse_threshold: int = 3
    cors_origins: str = ""


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
