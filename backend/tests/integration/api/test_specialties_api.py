import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.users.roles import Role
from app.infrastructure.db.models import SpecialtyModel
from app.infrastructure.db.seed import run_seed
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration
SPECIALTIES = "/api/v1/specialties"
REFERENCE = "/api/v1/reference-data"


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


async def test_specialties_are_listed_and_bundled(client: AsyncClient, users: Users) -> None:
    rep = await users.create(Role.SALES_REP)

    listed = await client.get(SPECIALTIES, headers=users.headers(rep))
    bundle = await client.get(REFERENCE, headers=users.headers(rep))

    assert listed.status_code == 200
    assert [s["code"] for s in listed.json()][:2] == ["gynaecology", "assisted_reproduction"]
    assert listed.json()[0]["name_es"] == "Ginecología"
    assert len(bundle.json()["specialties"]) == 12


async def test_renaming_a_specialty_changes_the_bundle_etag(
    client: AsyncClient, engine: AsyncEngine, admin_headers: dict[str, str]
) -> None:
    before = await client.get(REFERENCE, headers=admin_headers)
    etag = before.headers["etag"]
    unchanged = await client.get(REFERENCE, headers={**admin_headers, "If-None-Match": etag})
    assert unchanged.status_code == 304

    async with engine.begin() as connection:
        await connection.execute(
            update(SpecialtyModel)
            .where(SpecialtyModel.code == "podiatry")
            .values(name_es="Podología clínica")
        )
    try:
        after = await client.get(REFERENCE, headers={**admin_headers, "If-None-Match": etag})
        assert after.status_code == 200
        assert after.headers["etag"] != etag
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                update(SpecialtyModel)
                .where(SpecialtyModel.code == "podiatry")
                .values(name_es="Podología")
            )


async def test_admin_creates_specialties_and_reuses_existing_names(
    client: AsyncClient, users: Users, admin_headers: dict[str, str]
) -> None:
    rep = await users.create(Role.SALES_REP)
    before = (await client.get(SPECIALTIES, headers=admin_headers)).json()

    created = await client.post(SPECIALTIES, json={"name": "Urología"}, headers=admin_headers)

    assert created.status_code == 201, created.text
    assert created.json()["code"] == "urologia"
    assert created.json()["sort_order"] > max(s["sort_order"] for s in before)
    assert created.json()["outcome"] == "created"

    # A contact can use it immediately.
    listed = await client.get(SPECIALTIES, headers=users.headers(rep))
    assert created.json()["id"] in [s["id"] for s in listed.json()]

    # The seeded "Ginecología" retyped without its accent must not become a twin.
    reused = await client.post(SPECIALTIES, json={"name": "ginecologia"}, headers=admin_headers)
    assert reused.status_code == 201
    assert reused.json()["outcome"] == "reused"
    assert reused.json()["name_es"] == "Ginecología"
    assert len((await client.get(SPECIALTIES, headers=admin_headers)).json()) == len(before) + 1


async def test_specialty_creation_is_admin_only_and_validates(
    client: AsyncClient, users: Users, admin_headers: dict[str, str]
) -> None:
    rep = await users.create(Role.SALES_REP, email="rep-specialty@quermed.com")

    forbidden = await client.post(SPECIALTIES, json={"name": "X"}, headers=users.headers(rep))
    assert forbidden.status_code == 403

    blank = await client.post(SPECIALTIES, json={"name": "   "}, headers=admin_headers)
    assert blank.status_code == 422
