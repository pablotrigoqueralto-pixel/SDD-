import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.models import AuditLogModel, PersonalDataAccessLogModel
from app.infrastructure.db.seed import run_seed
from tests.integration.api.accounts_helpers import (
    ACCOUNTS,
    CONTACTS,
    GYNAECOLOGIST_ID,
    VASCULAR_ID,
    create_account,
    create_contact,
    if_match,
)
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration


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


@pytest.fixture
async def manager(users: Users) -> User:
    return await users.create(Role.SALES_MANAGER, email="manager@quermed.com")


async def access_rows(session: AsyncSession) -> list[tuple[str, str]]:
    rows = (await session.execute(select(PersonalDataAccessLogModel))).scalars().all()
    return [(str(r.user_id), str(r.contact_id)) for r in rows]


async def test_contact_lifecycle_primary_swap_and_consent(
    client: AsyncClient, users: Users, rep: User, session: AsyncSession
) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers)
    ana = await create_contact(
        client,
        headers,
        account["id"],
        is_primary=True,
        job_title_id=str(GYNAECOLOGIST_ID),
        email="Ana@Clinica.es",
        mobile="612 345 678",
        preferred_channel="mobile",
        consent={"status": "granted", "at": "2026-08-28T10:00:00Z", "source": "verbal"},
    )
    assert ana["is_primary"] is True
    assert ana["email"] == "ana@clinica.es" and ana["mobile"] == "+34612345678"
    assert ana["consent"]["recorded_by"] == str(rep.id)

    missing_value = await client.post(
        f"{ACCOUNTS}/{account['id']}/contacts",
        json={"first_name": "X", "last_name": "Y", "preferred_channel": "email"},
        headers=headers,
    )
    assert missing_value.status_code == 422
    assert missing_value.json()["code"] == "preferred_channel_missing_value"
    incomplete = await client.post(
        f"{ACCOUNTS}/{account['id']}/contacts",
        json={"first_name": "X", "last_name": "Y", "consent": {"status": "granted"}},
        headers=headers,
    )
    assert incomplete.status_code == 422
    assert incomplete.json()["code"] == "consent_incomplete"

    bea = await create_contact(client, headers, account["id"], first_name="Bea", last_name="Ruiz")
    listed = await client.get(f"{ACCOUNTS}/{account['id']}/contacts", headers=headers)
    assert [c["first_name"] for c in listed.json()] == ["Ana", "Bea"]

    promoted = await client.patch(
        f"{CONTACTS}/{bea['id']}",
        json={"is_primary": True, "landline": "91 123 45 67"},
        headers={**headers, **if_match(1)},
    )
    assert promoted.status_code == 200
    assert promoted.json()["is_primary"] is True and promoted.json()["version"] == 2
    demoted = await client.get(f"{CONTACTS}/{ana['id']}", headers=headers)
    assert demoted.json()["is_primary"] is False and demoted.json()["version"] == 2
    assert demoted.json()["account_name"] == "Clínica Tambre"

    stale = await client.patch(
        f"{CONTACTS}/{bea['id']}", json={"notes": "x"}, headers={**headers, **if_match(1)}
    )
    assert stale.status_code == 409

    actions = (
        (
            await session.execute(
                select(AuditLogModel.action)
                .where(AuditLogModel.entity_type == "contact")
                .order_by(AuditLogModel.occurred_at, AuditLogModel.id)
            )
        )
        .scalars()
        .all()
    )
    assert list(actions) == [
        "contact.created",
        "contact.consent_changed",
        "contact.created",
        "contact.primary_changed",
        "contact.updated",
    ]


async def test_visibility_and_access_log(
    client: AsyncClient, users: Users, rep: User, manager: User, session: AsyncSession
) -> None:
    rep_headers = users.headers(rep)
    account = await create_account(client, rep_headers)
    contact = await create_contact(client, rep_headers, account["id"])
    back_office = await users.create(Role.BACK_OFFICE, email="bo@quermed.com")
    stranger = await users.create(Role.SALES_REP, email="stranger@quermed.com")

    assert (await client.get(f"{CONTACTS}/{contact['id']}", headers=rep_headers)).status_code == 200
    assert (
        await client.get(f"{CONTACTS}/{contact['id']}", headers=users.headers(manager))
    ).status_code == 200
    assert await access_rows(session) == []

    by_back_office = await client.get(
        f"{CONTACTS}/{contact['id']}", headers=users.headers(back_office)
    )
    assert by_back_office.status_code == 200
    listed = await client.get(
        f"{ACCOUNTS}/{account['id']}/contacts", headers=users.headers(back_office)
    )
    assert listed.status_code == 200
    assert await access_rows(session) == [
        (str(back_office.id), contact["id"]),
        (str(back_office.id), contact["id"]),
    ]

    hidden = await client.get(f"{CONTACTS}/{contact['id']}", headers=users.headers(stranger))
    assert hidden.status_code == 404
    hidden_list = await client.get(
        f"{ACCOUNTS}/{account['id']}/contacts", headers=users.headers(stranger)
    )
    assert hidden_list.status_code == 404
    cannot_write = await client.post(
        f"{ACCOUNTS}/{account['id']}/contacts",
        json={"first_name": "X", "last_name": "Y"},
        headers=users.headers(back_office),
    )
    assert cannot_write.status_code == 403

    admin_log = await client.get(
        "/api/v1/audit-log/personal-data-access",
        params={"contact_id": contact["id"]},
        headers=users.headers(await users.create(Role.ADMIN, email="admin2@quermed.com")),
    )
    assert admin_log.status_code == 200
    assert admin_log.json()["total"] == 2
    assert admin_log.json()["items"][0]["user_name"] == back_office.full_name
    assert (
        await client.get("/api/v1/audit-log/personal-data-access", headers=rep_headers)
    ).status_code == 403


async def test_anonymisation(
    client: AsyncClient, users: Users, rep: User, manager: User, session: AsyncSession
) -> None:
    rep_headers = users.headers(rep)
    account = await create_account(client, rep_headers)
    contact = await create_contact(
        client, rep_headers, account["id"], email="secret@x.es", notes="VIP"
    )

    by_rep = await client.post(
        f"{CONTACTS}/{contact['id']}/anonymise", headers={**rep_headers, **if_match(1)}
    )
    assert by_rep.status_code == 403
    done = await client.post(
        f"{CONTACTS}/{contact['id']}/anonymise",
        headers={**users.headers(manager), **if_match(1)},
    )
    assert done.status_code == 200
    body = done.json()
    assert body["first_name"] == "Contacto" and body["last_name"] == "anonimizado"
    assert body["email"] is None and body["notes"] is None
    assert body["is_active"] is False and body["anonymised_at"] is not None
    assert body["consent"]["status"] == "denied"

    again = await client.patch(
        f"{CONTACTS}/{contact['id']}",
        json={"notes": "x"},
        headers={**users.headers(manager), **if_match(2)},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "contact_anonymised"

    rows = (
        (
            await session.execute(
                select(AuditLogModel).where(AuditLogModel.action == "contact.anonymised")
            )
        )
        .scalars()
        .all()
    )
    assert len(rows) == 1
    assert "secret@x.es" not in str(rows[0].changes)
    assert rows[0].changes["fields"]["cleared"] == [
        "first_name",
        "last_name",
        "email",
        "mobile",
        "landline",
        "notes",
    ]
