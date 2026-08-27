from collections.abc import AsyncIterator, Awaitable, Callable

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.infrastructure.settings import Settings
from app.main import create_app

TEST_DATABASE_URL = "postgresql+asyncpg://crm:crm@localhost:5432/quermed_crm_test"
TEST_JWT_SECRET = "test-secret-test-secret-test-secret-0123456789"


@pytest.fixture
def settings() -> Settings:
    return Settings(
        _env_file=None,
        DATABASE_URL=TEST_DATABASE_URL,
        JWT_SECRET=TEST_JWT_SECRET,
        CORS_ORIGINS="http://localhost:5173,http://testclient",
        ENVIRONMENT="test",
    )


ReadinessProbe = Callable[[], Awaitable[bool]]


async def _always_ready() -> bool:
    return True


@pytest.fixture
def app_factory(settings: Settings) -> Callable[..., FastAPI]:
    """Build an app with an injectable readiness probe and no real database."""

    def factory(readiness_probe: ReadinessProbe = _always_ready) -> FastAPI:
        return create_app(settings, readiness_probe=readiness_probe)

    return factory


@pytest.fixture
def app(app_factory: Callable[..., FastAPI]) -> FastAPI:
    return app_factory()


@pytest.fixture
async def client(app: FastAPI) -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testclient") as http:
        yield http
