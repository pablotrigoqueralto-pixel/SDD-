import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.seed import run_seed
from tests.integration.api.accounts_helpers import VASCULAR_ID, create_account
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration

SEARCH = "/api/v1/search"


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


@pytest.fixture
async def rep(users: Users, centro: Territory) -> User:
    return await users.create(
        Role.SALES_REP,
        email="rep@quermed.com",
        territory_ids=frozenset({centro.id}),
        division_ids=frozenset({VASCULAR_ID}),
    )


async def test_requires_auth(client: AsyncClient) -> None:
    response = await client.get(SEARCH, params={"q": "tambre"})
    assert response.status_code == 401


async def test_grouped_shape_and_short_query(client: AsyncClient, users: Users, rep: User) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers, name="Clínica Búsqueda")

    short = await client.get(SEARCH, params={"q": "a"}, headers=headers)
    assert short.status_code == 200
    assert short.json() == {
        "q": "a",
        "accounts": {"items": [], "total": 0, "has_more": False},
        "contacts": {"items": [], "total": 0, "has_more": False},
        "opportunities": {"items": [], "total": 0, "has_more": False},
        "quotes": {"items": [], "total": 0, "has_more": False},
    }

    found = await client.get(SEARCH, params={"q": "busqueda"}, headers=headers)
    assert found.status_code == 200, found.text
    body = found.json()
    assert [item["id"] for item in body["accounts"]["items"]] == [account["id"]]
    assert body["accounts"]["total"] == 1 and body["accounts"]["has_more"] is False
    assert body["contacts"]["items"] == []


async def test_scope_hides_foreign_accounts(client: AsyncClient, users: Users, rep: User) -> None:
    manager = await users.create(Role.SALES_MANAGER, email="mgr@quermed.com")
    manager_headers = users.headers(manager)
    admin_headers = users.headers(await users.create(Role.ADMIN, email="a9@quermed.com"))
    other = await client.post(
        "/api/v1/territories",
        json={"name": "Norte búsqueda", "provinces": ["48"]},
        headers=admin_headers,
    )
    assert other.status_code == 201
    foreign = await create_account(
        client, manager_headers, name="Centro Norte Búsqueda", province="48"
    )

    as_rep = await client.get(SEARCH, params={"q": "norte búsqueda"}, headers=users.headers(rep))
    assert all(item["id"] != foreign["id"] for item in as_rep.json()["accounts"]["items"])

    as_manager = await client.get(SEARCH, params={"q": "norte búsqueda"}, headers=manager_headers)
    assert any(item["id"] == foreign["id"] for item in as_manager.json()["accounts"]["items"])
