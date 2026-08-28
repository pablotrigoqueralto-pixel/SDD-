from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.models import AuditLogModel
from app.infrastructure.db.repositories.territories import SqlAlchemyTerritoryRepository
from app.infrastructure.db.seed import run_seed
from tests.integration.api.accounts_helpers import (
    ACCOUNTS,
    HOSPITAL_ID,
    IVF_CLINIC_ID,
    NEUROLOGY_ID,
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
async def norte(session: AsyncSession) -> Territory:
    territory = Territory.create(name="Norte", provinces=frozenset({"48", "20"}))
    await SqlAlchemyTerritoryRepository(session).add(territory)
    await session.commit()
    return territory


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


async def audit_actions(session: AsyncSession, entity_id: str) -> list[str]:
    statement = (
        select(AuditLogModel.action)
        .where(AuditLogModel.entity_id == entity_id)
        .order_by(AuditLogModel.occurred_at, AuditLogModel.id)
    )
    return list((await session.execute(statement)).scalars().all())


async def test_rep_creates_account_with_three_fields(
    client: AsyncClient, users: Users, rep: User, centro: Territory, session: AsyncSession
) -> None:
    body = await create_account(client, users.headers(rep))

    assert body["territory_id"] == str(centro.id)
    assert body["owner_id"] == str(rep.id)
    assert body["version"] == 1
    assert body["territory_mismatch"] is False
    assert body["addresses"] == [] and body["division_ids"] == []
    assert await audit_actions(session, body["id"]) == ["account.created"]


async def test_create_validations(client: AsyncClient, users: Users, rep: User) -> None:
    headers = users.headers(rep)
    first = await create_account(client, headers, tax_id="B12345674")

    duplicate = await client.post(
        ACCOUNTS,
        json={
            "name": "Dup",
            "account_type_id": str(IVF_CLINIC_ID),
            "province_code": "28",
            "tax_id": "b-12345674",
        },
        headers=headers,
    )
    assert duplicate.status_code == 409
    assert duplicate.json()["code"] == "tax_id_already_exists"
    assert duplicate.json()["existing_account_id"] == first["id"]

    invalid = await client.post(
        ACCOUNTS,
        json={
            "name": "Bad",
            "account_type_id": str(IVF_CLINIC_ID),
            "province_code": "28",
            "tax_id": "B1234567X",
            "postal_code": "2800",
            "phone": "abc",
        },
        headers=headers,
    )
    assert invalid.status_code == 422
    assert invalid.json()["code"] == "tax_id_invalid"

    unknown = await client.post(
        ACCOUNTS,
        json={
            "name": "Bad",
            "account_type_id": str(IVF_CLINIC_ID),
            "province_code": "28",
            "division_ids": [str(uuid4())],
        },
        headers=headers,
    )
    assert unknown.status_code == 422
    assert unknown.json()["errors"][0]["code"] == "unknown_reference"


async def test_list_is_scoped_filtered_and_sorted(
    client: AsyncClient,
    users: Users,
    rep: User,
    manager: User,
    centro: Territory,
    norte: Territory,
) -> None:
    manager_headers = users.headers(manager)
    visible = await create_account(
        client, manager_headers, name="Visible", division_ids=[str(VASCULAR_ID)], city="Madrid"
    )
    hidden = await create_account(
        client, manager_headers, name="Hidden division", division_ids=[str(NEUROLOGY_ID)]
    )
    far = await create_account(client, manager_headers, name="Far", province="48", city="Bilbao")
    owned_far = await create_account(client, users.headers(rep), name="Owned far", province="48")
    await create_contact(client, manager_headers, visible["id"], is_primary=True)

    rep_list = await client.get(ACCOUNTS, headers=users.headers(rep))
    assert rep_list.status_code == 200
    assert {i["name"] for i in rep_list.json()["items"]} == {"Visible", "Owned far"}
    assert rep_list.json()["total"] == 2
    visible_row = next(i for i in rep_list.json()["items"] if i["name"] == "Visible")
    assert visible_row["primary_contact_name"] == "Ana Pérez"

    everything = await client.get(ACCOUNTS, headers=manager_headers)
    assert everything.json()["total"] == 4
    assert [i["name"] for i in everything.json()["items"]][:2] == ["Far", "Hidden division"]

    unassigned = await client.get(ACCOUNTS, params={"unassigned": "true"}, headers=manager_headers)
    # No compatible rep for neurology in Centro and none for Norte -> both unassigned.
    assert {i["id"] for i in unassigned.json()["items"]} == {far["id"], hidden["id"]}
    assert visible["owner_id"] == str(rep.id)  # the only vascular rep of Centro
    assert owned_far["owner_id"] == str(rep.id)

    by_territory = await client.get(
        ACCOUNTS, params={"territory_id": str(norte.id), "sort": "-city"}, headers=manager_headers
    )
    assert [i["name"] for i in by_territory.json()["items"]] == ["Far", "Owned far"]
    capped = await client.get(ACCOUNTS, params={"page_size": 150}, headers=manager_headers)
    assert capped.json()["page_size"] == 100
    bad_sort = await client.get(ACCOUNTS, params={"sort": "owner"}, headers=manager_headers)
    assert bad_sort.status_code == 422


async def test_read_and_patch_respect_scope_roles_and_versions(
    client: AsyncClient, users: Users, rep: User, manager: User, session: AsyncSession
) -> None:
    manager_headers = users.headers(manager)
    rep_headers = users.headers(rep)
    far = await create_account(client, manager_headers, name="Far", province="48")
    near = await create_account(client, manager_headers, name="Near")

    assert (await client.get(f"{ACCOUNTS}/{far['id']}", headers=rep_headers)).status_code == 404
    assert (await client.get(f"{ACCOUNTS}/{uuid4()}", headers=manager_headers)).status_code == 404
    detail = await client.get(f"{ACCOUNTS}/{near['id']}", headers=rep_headers)
    assert detail.status_code == 200

    no_precondition = await client.patch(
        f"{ACCOUNTS}/{near['id']}", json={"city": "Madrid"}, headers=rep_headers
    )
    assert no_precondition.status_code == 428
    stale = await client.patch(
        f"{ACCOUNTS}/{near['id']}", json={"city": "Madrid"}, headers={**rep_headers, **if_match(9)}
    )
    assert stale.status_code == 409
    assert stale.json()["code"] == "conflict"

    updated = await client.patch(
        f"{ACCOUNTS}/{near['id']}",
        json={"city": "Madrid", "province_code": "08", "notes": None},
        headers={**rep_headers, **if_match(1)},
    )
    assert updated.status_code == 200
    assert updated.json()["version"] == 2
    assert updated.json()["territory_mismatch"] is True

    forbidden = await client.patch(
        f"{ACCOUNTS}/{near['id']}",
        json={"owner_id": str(rep.id)},
        headers={**manager_headers, **if_match(2)},
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "assignment_forbidden"

    back_office = await users.create(Role.BACK_OFFICE, email="bo@quermed.com")
    denied = await client.patch(
        f"{ACCOUNTS}/{near['id']}",
        json={"notes": "x"},
        headers={**users.headers(back_office), **if_match(2)},
    )
    assert denied.status_code == 403
    allowed = await client.patch(
        f"{ACCOUNTS}/{near['id']}",
        json={"customer_code": "C-001", "tax_id": "B12345674"},
        headers={**users.headers(back_office), **if_match(2)},
    )
    assert allowed.status_code == 200
    assert allowed.json()["customer_code"] == "C-001"

    deactivated = await client.patch(
        f"{ACCOUNTS}/{near['id']}",
        json={"is_active": False},
        headers={**manager_headers, **if_match(3)},
    )
    assert deactivated.status_code == 200
    assert await audit_actions(session, near["id"]) == [
        "account.created",
        "account.updated",
        "account.updated",
        "account.deactivated",
    ]


async def test_assignment_and_addresses(
    client: AsyncClient,
    users: Users,
    rep: User,
    manager: User,
    norte: Territory,
    session: AsyncSession,
) -> None:
    manager_headers = users.headers(manager)
    rep_headers = users.headers(rep)
    account = await create_account(client, rep_headers)
    other_rep = await users.create(
        Role.SALES_REP, email="other@quermed.com", territory_ids=frozenset({norte.id})
    )

    by_rep = await client.put(
        f"{ACCOUNTS}/{account['id']}/assignment",
        json={"owner_id": str(other_rep.id)},
        headers={**rep_headers, **if_match(1)},
    )
    assert by_rep.status_code == 403
    not_rep = await client.put(
        f"{ACCOUNTS}/{account['id']}/assignment",
        json={"owner_id": str(manager.id)},
        headers={**manager_headers, **if_match(1)},
    )
    assert not_rep.status_code == 422
    assert not_rep.json()["code"] == "owner_not_sales_rep"
    assigned = await client.put(
        f"{ACCOUNTS}/{account['id']}/assignment",
        json={"owner_id": str(other_rep.id), "territory_id": str(norte.id)},
        headers={**manager_headers, **if_match(1)},
    )
    assert assigned.status_code == 200
    assert assigned.json()["owner_id"] == str(other_rep.id)
    assert assigned.json()["territory_mismatch"] is True
    assert assigned.json()["version"] == 2
    # The original rep no longer sees it (other territory, not owner).
    assert (await client.get(f"{ACCOUNTS}/{account['id']}", headers=rep_headers)).status_code == 404

    addresses = await client.put(
        f"{ACCOUNTS}/{account['id']}/addresses",
        json={
            "addresses": [
                {
                    "label": "Laboratorio",
                    "street": "C/ Uno 1",
                    "postal_code": "28001",
                    "city": "Madrid",
                    "province_code": "28",
                },
                {
                    "label": "Almacén",
                    "street": "C/ Dos 2",
                    "postal_code": "28002",
                    "city": "Madrid",
                    "province_code": "28",
                    "notes": "Entrega por la mañana",
                },
            ]
        },
        headers={**manager_headers, **if_match(2)},
    )
    assert addresses.status_code == 200
    assert [a["label"] for a in addresses.json()["addresses"]] == ["Laboratorio", "Almacén"]
    reloaded = await client.get(f"{ACCOUNTS}/{account['id']}", headers=manager_headers)
    assert [a["label"] for a in reloaded.json()["addresses"]] == ["Almacén", "Laboratorio"]
    duplicated = await client.put(
        f"{ACCOUNTS}/{account['id']}/addresses",
        json={
            "addresses": [
                {
                    "label": "Sede",
                    "street": "a",
                    "postal_code": "28001",
                    "city": "M",
                    "province_code": "28",
                },
                {
                    "label": "sede",
                    "street": "b",
                    "postal_code": "28001",
                    "city": "M",
                    "province_code": "28",
                },
            ]
        },
        headers={**manager_headers, **if_match(3)},
    )
    assert duplicated.status_code == 422
    assert duplicated.json()["code"] == "address_label_duplicated"
    assert await audit_actions(session, account["id"]) == [
        "account.created",
        "account.assigned",
        "account.addresses_replaced",
    ]


async def test_account_type_filter_uses_seeded_master(
    client: AsyncClient, users: Users, manager: User
) -> None:
    headers = users.headers(manager)
    await create_account(client, headers, name="Clinic")
    hospital = await client.post(
        ACCOUNTS,
        json={"name": "Hospital", "account_type_id": str(HOSPITAL_ID), "province_code": "28"},
        headers=headers,
    )
    assert hospital.status_code == 201

    filtered = await client.get(
        ACCOUNTS, params={"account_type_id": str(HOSPITAL_ID)}, headers=headers
    )
    assert [i["name"] for i in filtered.json()["items"]] == ["Hospital"]
