"""Account types stop being seed-only: an administrator can add one from the form."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.users.roles import Role
from app.infrastructure.db.seed import run_seed
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration
ACCOUNT_TYPES = "/api/v1/account-types"
ACCOUNTS = "/api/v1/accounts"
REFERENCE = "/api/v1/reference-data"


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


async def test_admin_creates_a_tendering_type_and_uses_it(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    before = await client.get(REFERENCE, headers=admin_headers)
    etag = before.headers["etag"]
    seeded_types = (await client.get(ACCOUNT_TYPES, headers=admin_headers)).json()

    created = await client.post(
        ACCOUNT_TYPES,
        json={"name": "Consorcio sanitario", "buys_via_tender": True},
        headers=admin_headers,
    )

    assert created.status_code == 201, created.text
    assert created.json()["code"] == "consorcio_sanitario"
    assert created.json()["buys_via_tender"] is True
    assert created.json()["is_active"] is True
    assert created.json()["sort_order"] > max(t["sort_order"] for t in seeded_types)
    assert created.json()["outcome"] == "created"

    # Usable at once, and the bundle notices.
    account = await client.post(
        ACCOUNTS,
        json={
            "name": "Consorcio de prueba",
            "account_type_id": created.json()["id"],
            "province_code": "28",
        },
        headers=admin_headers,
    )
    assert account.status_code == 201, account.text
    after = await client.get(REFERENCE, headers={**admin_headers, "If-None-Match": etag})
    assert after.status_code == 200 and after.headers["etag"] != etag


async def test_tender_flag_defaults_to_false_and_names_are_reused(
    client: AsyncClient, admin_headers: dict[str, str]
) -> None:
    plain = await client.post(ACCOUNT_TYPES, json={"name": "Residencia"}, headers=admin_headers)
    assert plain.status_code == 201
    assert plain.json()["buys_via_tender"] is False

    # The seeded "Hospital público" retyped without its accent must not become a twin.
    reused = await client.post(
        ACCOUNT_TYPES, json={"name": "hospital publico"}, headers=admin_headers
    )
    assert reused.status_code == 201
    assert reused.json()["outcome"] == "reused"
    assert reused.json()["name_es"] == "Hospital público"
    assert reused.json()["buys_via_tender"] is True  # the stored flag is not overwritten


async def test_account_type_creation_is_admin_only(client: AsyncClient, users: Users) -> None:
    back_office = await users.create(Role.BACK_OFFICE, email="bo-types@quermed.com")

    forbidden = await client.post(
        ACCOUNT_TYPES, json={"name": "X"}, headers=users.headers(back_office)
    )

    assert forbidden.status_code == 403
