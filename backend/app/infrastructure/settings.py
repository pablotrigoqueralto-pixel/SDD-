"""Application settings loaded from environment variables (fail-fast)."""

from functools import lru_cache
from typing import Annotated, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

MIN_JWT_SECRET_LENGTH = 32


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore", case_sensitive=False)

    database_url: str = Field(alias="DATABASE_URL")
    jwt_secret: str = Field(alias="JWT_SECRET")
    # NoDecode: the value is a comma-separated string, not JSON (see split_cors_origins).
    cors_origins: Annotated[list[str], NoDecode] = Field(alias="CORS_ORIGINS")
    environment: Literal["dev", "test", "staging", "prod"] = Field("dev", alias="ENVIRONMENT")
    log_level: str = Field("info", alias="LOG_LEVEL")

    access_token_ttl_seconds: int = Field(900, alias="ACCESS_TOKEN_TTL_SECONDS")
    refresh_token_ttl_days: int = Field(30, alias="REFRESH_TOKEN_TTL_DAYS")
    max_failed_login_attempts: int = Field(10, alias="MAX_FAILED_LOGIN_ATTEMPTS")
    lockout_minutes: int = Field(15, alias="LOCKOUT_MINUTES")
    # Per-IP limit on /auth/*; raise it only for automated E2E runs (e.g. "1000/minute").
    auth_rate_limit: str = Field("10/minute", alias="AUTH_RATE_LIMIT")

    # Consumables "En riesgo": days without activity before the scan flags a won row,
    # and how often the in-process scheduler runs it (0 disables; production uses cron).
    at_risk_after_days: int = Field(60, alias="AT_RISK_AFTER_DAYS")
    at_risk_scan_interval_hours: int = Field(6, alias="AT_RISK_SCAN_INTERVAL_HOURS")

    @field_validator("jwt_secret")
    @classmethod
    def validate_jwt_secret_length(cls, value: str) -> str:
        if len(value) < MIN_JWT_SECRET_LENGTH:
            msg = f"JWT_SECRET must be at least {MIN_JWT_SECRET_LENGTH} characters"
            raise ValueError(msg)
        return value

    @field_validator("cors_origins", mode="before")
    @classmethod
    def split_cors_origins(cls, value: object) -> list[str]:
        if isinstance(value, str):
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        if isinstance(value, list):
            return [str(origin).strip() for origin in value if str(origin).strip()]
        msg = "CORS_ORIGINS must be a comma-separated string"
        raise ValueError(msg)

    @property
    def is_dev(self) -> bool:
        return self.environment == "dev"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
