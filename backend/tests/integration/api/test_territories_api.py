from uuid import uuid4

import pytest
from httpx import AsyncClient

from app.domain.territories.entities import Territory
from app.domain.users.roles import Role
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration

TERRITORIES = "/api/v1/territories"


async def test_admin_creates_territory(client: AsyncClient, admin_headers: dict[str, str]) -> None:
    response = await client.post(
        TERRITORIES, json={"name": "Sur", "provinces": ["41", "11", "29"]}, headers=admin_headers
    )

    assert response.status_code == 201, response.text
    body = response.json()
    assert body["name"] == "Sur"
    assert body["provinces"] == ["11", "29", "41"]
    assert body["user_count"] == 0
    assert body["is_active"] is True


async def test_create_territory_errors(
    client: AsyncClient, admin_headers: dict[str, str], centro: Territory
) -> None:
    taken = await client.post(
        TERRITORIES, json={"name": "Sur", "provinces": ["28"]}, headers=admin_headers
    )
    invalid = await client.post(
        TERRITORIES, json={"name": "Sur", "provinces": ["99"]}, headers=admin_headers
    )
    duplicate_name = await client.post(
        TERRITORIES, json={"name": "centro", "provinces": ["41"]}, headers=admin_headers
    )

    assert taken.status_code == 409
    assert taken.json()["code"] == "province_already_assigned"
    assert "Centro" in taken.json()["detail"]
    assert invalid.status_code == 422
    assert invalid.json()["errors"][0]["code"] == "invalid_province"
    assert duplicate_name.status_code == 409
    assert duplicate_name.json()["code"] == "territory_name_already_exists"


async def test_list_and_read_with_user_count(
    client: AsyncClient, users: Users, centro: Territory
) -> None:
    manager = await users.create(Role.SALES_MANAGER)
    await users.create(Role.SALES_REP, territory_ids=frozenset({centro.id}))
    headers = users.headers(manager)

    listed = await client.get(TERRITORIES, params={"q": "cen"}, headers=headers)
    read = await client.get(f"{TERRITORIES}/{centro.id}", headers=headers)
    missing = await client.get(f"{TERRITORIES}/{uuid4()}", headers=headers)

    assert listed.status_code == 200
    assert listed.json()["total"] == 1
    assert listed.json()["items"][0]["user_count"] == 1
    assert read.json()["user_count"] == 1
    assert missing.status_code == 404


async def test_sales_rep_cannot_list_territories(client: AsyncClient, users: Users) -> None:
    rep = await users.create(Role.SALES_REP)

    response = await client.get(TERRITORIES, headers=users.headers(rep))

    assert response.status_code == 403


async def test_patch_territory_and_deactivate_guard(
    client: AsyncClient, admin_headers: dict[str, str], users: Users, centro: Territory
) -> None:
    await users.create(Role.SALES_REP, territory_ids=frozenset({centro.id}))

    renamed = await client.patch(
        f"{TERRITORIES}/{centro.id}",
        json={"name": "Centro y Toledo", "provinces": ["28", "45", "19"]},
        headers={**admin_headers, "If-Match": "1"},
    )
    in_use = await client.patch(
        f"{TERRITORIES}/{centro.id}",
        json={"is_active": False},
        headers={**admin_headers, "If-Match": "2"},
    )

    assert renamed.status_code == 200
    assert renamed.json()["provinces"] == ["19", "28", "45"]
    assert renamed.json()["version"] == 2
    assert in_use.status_code == 400
    assert in_use.json()["code"] == "territory_in_use"
    assert "1 active user" in in_use.json()["detail"]


async def test_divisions_listed_for_every_role(client: AsyncClient, users: Users) -> None:
    rep = await users.create(Role.SALES_REP)

    response = await client.get("/api/v1/divisions", headers=users.headers(rep))

    assert response.status_code == 200
    codes = [d["code"] for d in response.json()]
    assert codes == [
        "assisted_reproduction",
        "consumables",
        "gynaecology",
        "vascular",
        "neurology",
        "equipment",
        "carts_and_arms",
    ]
    assert response.json()[0]["name_es"] == "Reproducción asistida"
