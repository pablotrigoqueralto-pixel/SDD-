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
