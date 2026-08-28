"""Search sanity at scale: trigram index used and list under 500 ms with 5 000 accounts."""

import time
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.users.roles import Role
from app.infrastructure.db.seed import run_seed
from tests.integration.api.accounts_helpers import ACCOUNTS, IVF_CLINIC_ID
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration
ROWS = 5_000


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


async def test_name_search_uses_trigram_index_and_is_fast(
    client: AsyncClient, users: Users, session: AsyncSession
) -> None:
    manager = await users.create(Role.SALES_MANAGER)
    await session.execute(
        text(
            "INSERT INTO accounts (id, name, account_type_id, province_code, city) "
            "SELECT gen_random_uuid(), 'Centro ' || g || ' ' || md5(g::text), :type_id, '28', "
            "'Ciudad ' || (g % 100) FROM generate_series(1, :rows) AS g"
        ),
        {"type_id": IVF_CLINIC_ID, "rows": ROWS},
    )
    await session.execute(
        text(
            "INSERT INTO accounts (id, name, account_type_id, province_code) "
            "VALUES (:id, 'Clínica Tambre', :type_id, '28')"
        ),
        {"id": uuid4(), "type_id": IVF_CLINIC_ID},
    )
    await session.execute(text("ANALYZE accounts"))
    await session.commit()

    # With a few thousand rows the planner may still prefer a sequential scan; forcing
    # index usage proves the trigram index is applicable to the ILIKE predicate.
    await session.execute(text("SET enable_seqscan = off"))
    plan = await session.execute(
        text("EXPLAIN SELECT id FROM accounts WHERE name ILIKE '%tambre%'")
    )
    plan_text = "\n".join(row[0] for row in plan.all())
    await session.execute(text("SET enable_seqscan = on"))
    assert "ix_accounts_name_trgm" in plan_text, plan_text

    started = time.perf_counter()
    response = await client.get(ACCOUNTS, params={"q": "tambre"}, headers=users.headers(manager))
    elapsed = time.perf_counter() - started
    assert response.status_code == 200
    assert [i["name"] for i in response.json()["items"]] == ["Clínica Tambre"]
    assert elapsed < 0.5, f"search took {elapsed:.3f}s"
