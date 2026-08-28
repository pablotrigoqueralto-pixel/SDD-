import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.users.roles import Role
from app.infrastructure.db.seed import run_seed
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration
JOB_TITLES = "/api/v1/job-titles"
REFERENCE = "/api/v1/reference-data"


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


async def test_job_titles_are_listed_and_bundled(client: AsyncClient, users: Users) -> None:
    rep = await users.create(Role.SALES_REP)

    listed = await client.get(JOB_TITLES, headers=users.headers(rep))
    bundle = await client.get(REFERENCE, headers=users.headers(rep))

    assert listed.status_code == 200
    assert [t["code"] for t in listed.json()][:2] == ["gynaecologist", "embryologist"]
    assert len(bundle.json()["job_titles"]) == 11


async def test_admin_manages_job_titles_and_etag_changes(
    client: AsyncClient, users: Users, admin_headers: dict[str, str]
) -> None:
    rep = await users.create(Role.SALES_REP)
    before = await client.get(REFERENCE, headers=admin_headers)
    etag = before.headers["etag"]

    created = await client.post(
        JOB_TITLES, json={"name": "Farmacia hospitalaria"}, headers=admin_headers
    )
    assert created.status_code == 201
    assert created.json()["code"] == "farmacia_hospitalaria"
    assert created.json()["sort_order"] == 120

    duplicate = await client.post(JOB_TITLES, json={"name": "gerencia"}, headers=admin_headers)
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "job_title_name_already_exists"

    renamed = await client.patch(
        f"{JOB_TITLES}/{created.json()['id']}",
        json={"name": "Farmacia", "is_active": False},
        headers={**admin_headers, "If-Match": "1"},
    )
    assert renamed.status_code == 200
    assert renamed.json()["name_es"] == "Farmacia" and renamed.json()["is_active"] is False

    forbidden = await client.post(JOB_TITLES, json={"name": "X"}, headers=users.headers(rep))
    assert forbidden.status_code == 403

    after = await client.get(REFERENCE, headers={**admin_headers, "If-None-Match": etag})
    assert after.status_code == 200
    assert after.headers["etag"] != etag
