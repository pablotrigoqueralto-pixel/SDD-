import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.users.roles import Role
from app.infrastructure.db.models import AuditLogModel
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
    assert created.json()["outcome"] == "created"

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


async def test_creating_an_existing_name_reuses_it_instead_of_failing(
    client: AsyncClient, admin_headers: dict[str, str], session: AsyncSession
) -> None:
    """An admin adding an option mid-form must never get a second spelling of one entry."""
    listed = await client.get(JOB_TITLES, headers=admin_headers)
    before = len(listed.json())
    # The seeded code is English ("management"), the name Spanish: the lookup must
    # match the NAME here, which is what an administrator retypes.
    management = next(t for t in listed.json() if t["name_es"] == "Gerencia")

    # Same name in another spelling: accents, case and punctuation fold into one code.
    reused = await client.post(JOB_TITLES, json={"name": "GERENCIA"}, headers=admin_headers)

    assert reused.status_code == 201
    assert reused.json()["id"] == management["id"]
    assert reused.json()["name_es"] == management["name_es"]  # the stored spelling wins
    assert reused.json()["outcome"] == "reused"
    assert len((await client.get(JOB_TITLES, headers=admin_headers)).json()) == before

    events = (
        (
            await session.execute(
                select(AuditLogModel.action).where(AuditLogModel.entity_type == "job_title")
            )
        )
        .scalars()
        .all()
    )
    assert list(events) == []  # nothing changed, nothing recorded


async def test_creating_a_deactivated_name_brings_it_back(
    client: AsyncClient, admin_headers: dict[str, str], session: AsyncSession
) -> None:
    """Change 12 deactivated "Jefe de servicio": recreating it must revive that row."""
    listed = await client.get(JOB_TITLES, headers=admin_headers)
    victim = next(t for t in listed.json() if t["is_active"])
    deactivated = await client.patch(
        f"{JOB_TITLES}/{victim['id']}",
        json={"is_active": False},
        headers={**admin_headers, "If-Match": str(victim["version"])},
    )
    assert deactivated.status_code == 200

    revived = await client.post(JOB_TITLES, json={"name": victim["name_es"]}, headers=admin_headers)

    assert revived.status_code == 201
    assert revived.json()["id"] == victim["id"]
    assert revived.json()["is_active"] is True
    assert revived.json()["outcome"] == "reactivated"

    events = (
        (
            await session.execute(
                select(AuditLogModel.action).where(AuditLogModel.entity_type == "job_title")
            )
        )
        .scalars()
        .all()
    )
    assert "job_title.reactivated" in list(events)
