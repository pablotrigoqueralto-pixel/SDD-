"""Integration fixtures: a real PostgreSQL (compose `db` service or CI service container).

Set TEST_DATABASE_URL to point elsewhere. Tests are skipped with a clear message when the
database is unreachable so the unit suite stays runnable without Docker.
"""

import asyncio
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

BACKEND_DIR = Path(__file__).resolve().parents[2]
DEFAULT_TEST_DATABASE_URL = "postgresql+asyncpg://crm:crm@localhost:5432/quermed_crm_test"
TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", DEFAULT_TEST_DATABASE_URL)

pytestmark = pytest.mark.integration


def _database_reachable(url: str) -> bool:
    async def probe() -> bool:
        engine = create_async_engine(url)
        try:
            async with engine.connect() as connection:
                await connection.execute(text("SELECT 1"))
            return True
        except Exception:
            return False
        finally:
            await engine.dispose()

    return asyncio.run(probe())


def alembic(*args: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "DATABASE_URL": TEST_DATABASE_URL,
        "JWT_SECRET": "integration-secret-integration-secret-0123",
        "CORS_ORIGINS": "http://localhost:5173",
    }
    return subprocess.run(  # noqa: S603 - fixed argv, no shell
        [sys.executable, "-m", "alembic", *args],
        cwd=BACKEND_DIR,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.fixture(scope="session")
def database_url() -> str:
    if not _database_reachable(TEST_DATABASE_URL):
        pytest.skip(
            f"PostgreSQL not reachable at {TEST_DATABASE_URL}; start `docker compose up db`"
        )
    return TEST_DATABASE_URL


@pytest.fixture(scope="session")
def migrated_database(database_url: str) -> Iterator[str]:
    """Schema at head for the whole session (each test rolls back its own transaction)."""
    result = alembic("upgrade", "head")
    assert result.returncode == 0, result.stderr
    yield database_url


@pytest.fixture
async def engine(migrated_database: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(migrated_database)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session(engine: AsyncEngine) -> AsyncIterator[AsyncSession]:
    """A session bound to an outer transaction that is always rolled back."""
    async with engine.connect() as connection:
        transaction = await connection.begin()
        factory = async_sessionmaker(
            connection, expire_on_commit=False, join_transaction_mode="create_savepoint"
        )
        async with factory() as session:
            yield session
        await transaction.rollback()
