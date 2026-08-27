from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from tests.integration.api.conftest import VASCULAR_ID, Users

pytestmark = pytest.mark.integration

USERS = "/api/v1/users"


def payload(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "email": "Nueva@Quermed.com",
        "full_name": "Nueva Comercial",
        "role": "sales_rep",
        "password": "correct-horse-battery",
        "territory_ids": [],
        "division_ids": [],
    }
    body.update(overrides)
    return body


async def test_admin_creates_user_with_scope(
    client: AsyncClient, admin_headers: dict[str, str], centro: Territory
) -> None:
    response = await client.post(
        USERS,
        json=payload(territory_ids=[str(centro.id)], division_ids=[str(VASCULAR_ID)]),
        headers=admin_headers,
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["email"] == "nueva@quermed.com"
    assert body["territory_ids"] == [str(centro.id)]
    assert body["division_ids"] == [str(VASCULAR_ID)]
    assert body["version"] == 1
    assert "password" not in body and "password_hash" not in body


async def test_create_user_errors(
    client: AsyncClient, admin_headers: dict[str, str], users: Users
) -> None:
    await users.create(Role.SALES_REP, email="nueva@quermed.com")

    duplicate = await client.post(USERS, json=payload(), headers=admin_headers)
    unknown = await client.post(
        USERS,
        json=payload(email="b@quermed.com", territory_ids=[str(uuid4())]),
        headers=admin_headers,
    )
    short = await client.post(
        USERS, json=payload(email="c@quermed.com", password="short"), headers=admin_headers
    )
    bad_email = await client.post(USERS, json=payload(email="not-an-email"), headers=admin_headers)

    assert duplicate.status_code == 409 and duplicate.json()["code"] == "email_already_exists"
    assert unknown.status_code == 422
    assert unknown.json()["errors"][0]["field"] == "territory_ids"
    assert unknown.json()["errors"][0]["code"] == "unknown_reference"
    assert short.status_code == 422 and short.json()["errors"][0]["code"] == "password_too_short"
    assert bad_email.status_code == 422 and bad_email.json()["errors"][0]["code"] == "invalid_email"


async def test_non_admin_cannot_create_users(client: AsyncClient, users: Users) -> None:
    manager = await users.create(Role.SALES_MANAGER)

    response = await client.post(USERS, json=payload(), headers=users.headers(manager))

    assert response.status_code == 403
    assert response.json()["code"] == "forbidden"


async def test_list_users_filters_and_sort(
    client: AsyncClient, users: Users, centro: Territory
) -> None:
    manager = await users.create(Role.SALES_MANAGER, full_name="Marta Manager")
    await users.create(
        Role.SALES_REP,
        email="ana@quermed.com",
        full_name="Ana",
        territory_ids=frozenset({centro.id}),
    )
    await users.create(Role.SALES_REP, email="bea@quermed.com", full_name="Bea", is_active=False)
    headers = users.headers(manager)

    active_reps = await client.get(
        USERS, params={"role": "sales_rep", "is_active": "true"}, headers=headers
    )
    in_centro = await client.get(USERS, params={"territory_id": str(centro.id)}, headers=headers)
    by_prefix = await client.get(USERS, params={"q": "be"}, headers=headers)
    sorted_desc = await client.get(USERS, params={"sort": "-full_name"}, headers=headers)
    bad_sort = await client.get(USERS, params={"sort": "foo"}, headers=headers)

    assert [u["full_name"] for u in active_reps.json()["items"]] == ["Ana"]
    assert active_reps.json()["total"] == 1
    assert [u["full_name"] for u in in_centro.json()["items"]] == ["Ana"]
    assert [u["full_name"] for u in by_prefix.json()["items"]] == ["Bea"]
    assert [u["full_name"] for u in sorted_desc.json()["items"]] == ["Marta Manager", "Bea", "Ana"]
    assert sorted_desc.json()["page_size"] == 50
    assert bad_sort.status_code == 422 and bad_sort.json()["code"] == "invalid_sort_field"


async def test_sales_rep_cannot_list_or_read_users(client: AsyncClient, users: Users) -> None:
    rep = await users.create(Role.SALES_REP)

    listed = await client.get(USERS, headers=users.headers(rep))
    read = await client.get(f"{USERS}/{rep.id}", headers=users.headers(rep))

    assert listed.status_code == 403
    assert read.status_code == 403


async def test_read_user_not_found(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    response = await client.get(f"{USERS}/{uuid4()}", headers=admin_headers)

    assert response.status_code == 404
    assert response.json()["code"] == "not_found"


async def test_patch_user_requires_if_match_and_handles_conflicts(
    client: AsyncClient, admin_headers: dict[str, str], users: Users
) -> None:
    rep = await users.create(Role.SALES_REP)

    missing = await client.patch(
        f"{USERS}/{rep.id}", json={"full_name": "X"}, headers=admin_headers
    )
    ok = await client.patch(
        f"{USERS}/{rep.id}",
        json={"full_name": "Renamed", "role": "sales_manager"},
        headers={**admin_headers, "If-Match": '"1"'},
    )
    stale = await client.patch(
        f"{USERS}/{rep.id}",
        json={"full_name": "Again"},
        headers={**admin_headers, "If-Match": '"1"'},
    )

    assert missing.status_code == 428 and missing.json()["code"] == "precondition_required"
    assert ok.status_code == 200
    assert ok.json()["full_name"] == "Renamed"
    assert ok.json()["role"] == "sales_manager"
    assert ok.json()["version"] == 2
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"


async def test_admin_cannot_demote_self(
    client: AsyncClient, admin: User, admin_headers: dict[str, str]
) -> None:
    response = await client.patch(
        f"{USERS}/{admin.id}", json={"is_active": False}, headers={**admin_headers, "If-Match": "1"}
    )

    assert response.status_code == 400
    assert response.json()["code"] == "cannot_demote_self"


async def test_deactivation_invalidates_existing_tokens(
    client: AsyncClient, admin_headers: dict[str, str], users: Users
) -> None:
    rep = await users.create(Role.SALES_REP)
    rep_headers = users.headers(rep)
    assert (await client.get("/api/v1/me", headers=rep_headers)).status_code == 200

    response = await client.patch(
        f"{USERS}/{rep.id}", json={"is_active": False}, headers={**admin_headers, "If-Match": "1"}
    )

    assert response.status_code == 200
    assert (await client.get("/api/v1/me", headers=rep_headers)).status_code == 401


async def test_me_returns_resolved_scope(
    client: AsyncClient, users: Users, centro: Territory
) -> None:
    rep = await users.create(
        Role.SALES_REP, territory_ids=frozenset({centro.id}), division_ids=frozenset({VASCULAR_ID})
    )

    response = await client.get("/api/v1/me", headers=users.headers(rep))

    assert response.status_code == 200
    body = response.json()
    assert body["role"] == "sales_rep"
    assert [t["name"] for t in body["territories"]] == ["Centro"]
    assert body["territories"][0]["provinces"] == ["28", "45"]
    assert [d["code"] for d in body["divisions"]] == ["vascular"]


async def test_me_patch_only_accepts_full_name(client: AsyncClient, users: Users) -> None:
    rep = await users.create(Role.SALES_REP)
    headers = {**users.headers(rep), "If-Match": "1"}

    renamed = await client.patch("/api/v1/me", json={"full_name": "Ana María"}, headers=headers)
    role_change = await client.patch("/api/v1/me", json={"role": "admin"}, headers=headers)

    assert renamed.status_code == 200 and renamed.json()["full_name"] == "Ana María"
    assert role_change.status_code == 422
