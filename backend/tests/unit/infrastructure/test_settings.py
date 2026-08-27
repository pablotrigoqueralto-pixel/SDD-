import pytest
from pydantic import ValidationError

from app.infrastructure.settings import Settings

VALID_SECRET = "x" * 32
DB_URL = "postgresql+asyncpg://crm:crm@localhost:5432/quermed_crm"
ENV_VARS = ("DATABASE_URL", "JWT_SECRET", "CORS_ORIGINS", "ENVIRONMENT", "LOG_LEVEL", "AUTH_RATE_LIMIT")


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Settings tests must not see the real environment (CI exports DATABASE_URL etc.)."""
    for name in ENV_VARS:
        monkeypatch.delenv(name, raising=False)


def build(**overrides: object) -> Settings:
    values: dict[str, object] = {
        "DATABASE_URL": DB_URL,
        "JWT_SECRET": VALID_SECRET,
        "CORS_ORIGINS": "http://localhost:5173,http://*.local:5173",
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)  # type: ignore[arg-type]


def test_settings_load_when_all_required_values_present() -> None:
    settings = build()

    assert settings.database_url == DB_URL
    assert settings.cors_origins == ["http://localhost:5173", "http://*.local:5173"]
    assert settings.environment == "dev"
    assert settings.access_token_ttl_seconds == 900


def test_settings_raise_when_database_url_missing() -> None:
    with pytest.raises(ValidationError, match="DATABASE_URL"):
        Settings(_env_file=None, JWT_SECRET=VALID_SECRET, CORS_ORIGINS="http://a")


def test_settings_raise_when_jwt_secret_too_short() -> None:
    with pytest.raises(ValidationError, match="at least 32"):
        build(JWT_SECRET="short")


def test_cors_origins_are_trimmed_and_empty_entries_dropped() -> None:
    settings = build(CORS_ORIGINS=" http://a , ,http://b ")

    assert settings.cors_origins == ["http://a", "http://b"]


def test_environment_rejects_unknown_value() -> None:
    with pytest.raises(ValidationError):
        build(ENVIRONMENT="qa")
