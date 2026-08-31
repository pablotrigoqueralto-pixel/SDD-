"""The global contacts list: account visibility, summary shape and cumulative filters."""

from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.seed import reference_id, run_seed
from tests.integration.api.accounts_helpers import (
    GYNAECOLOGIST_ID,
    VASCULAR_ID,
    create_account,
    create_contact,
)
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration
CONTACTS = "/api/v1/contacts"

GYNAECOLOGY = reference_id("specialties", "gynaecology")
VASCULAR_SURGERY = reference_id("specialties", "vascular_surgery")
NEUROLOGY = reference_id("specialties", "neurology")


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


@pytest.fixture
async def rep(users: Users, centro: Territory) -> User:
    return await users.create(
        Role.SALES_REP,
        email="rep-list@quermed.com",
        territory_ids=frozenset({centro.id}),
        division_ids=frozenset({VASCULAR_ID}),
    )


async def test_list_is_scoped_to_visible_accounts(
    client: AsyncClient, users: Users, rep: User
) -> None:
    rep_headers = users.headers(rep)
    mine = await create_account(client, rep_headers, name="Hospital Propio")
    await create_contact(client, rep_headers, mine["id"], first_name="Ana", last_name="Serrano")

    manager = await users.create(Role.SALES_MANAGER, email="manager-list@quermed.com")
    manager_headers = users.headers(manager)
    other = await create_account(client, manager_headers, name="Hospital Ajeno", province="15")
    await create_contact(client, manager_headers, other["id"], first_name="Luis", last_name="Otro")

    scoped = await client.get(CONTACTS, headers=rep_headers)
    assert scoped.status_code == 200, scoped.text
    names = [c["last_name"] for c in scoped.json()["items"]]
    assert "Serrano" in names and "Otro" not in names

    everything = await client.get(CONTACTS, headers=manager_headers)
    listed = [c["last_name"] for c in everything.json()["items"]]
    assert "Serrano" in listed and "Otro" in listed


async def test_summary_carries_the_account_specialty_and_primary_phone(
    client: AsyncClient, users: Users, rep: User
) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers, name="Clínica Resumen")
    await create_contact(
        client,
        headers,
        account["id"],
        first_name="Marta",
        last_name="Vidal",
        job_title_id=str(GYNAECOLOGIST_ID),
        specialty_id=str(GYNAECOLOGY),
        is_head_of_department=True,
        email="marta@clinica.es",
        phones=[
            {"label": "Móvil", "number": "612 345 678"},
            {"label": "Centralita", "number": "913 456 789"},
        ],
    )

    listed = await client.get(CONTACTS, params={"q": "vidal"}, headers=headers)
    row = listed.json()["items"][0]
    assert row["account_name"] == "Clínica Resumen"
    assert row["specialty_id"] == str(GYNAECOLOGY)
    assert row["job_title_id"] == str(GYNAECOLOGIST_ID)
    assert row["is_head_of_department"] is True
    assert row["primary_phone"] == "+34612345678"
    assert row["email"] == "marta@clinica.es"
    assert row["is_active"] is True


async def test_filters_are_cumulative(client: AsyncClient, users: Users, rep: User) -> None:
    headers = users.headers(rep)
    first = await create_account(client, headers, name="Centro Uno")
    second = await create_account(client, headers, name="Centro Dos")
    await create_contact(
        client, headers, first["id"], last_name="Gine", specialty_id=str(GYNAECOLOGY)
    )
    await create_contact(
        client,
        headers,
        first["id"],
        last_name="Vascular",
        specialty_id=str(VASCULAR_SURGERY),
        is_head_of_department=True,
    )
    await create_contact(
        client, headers, second["id"], last_name="GineDos", specialty_id=str(GYNAECOLOGY)
    )
    await create_contact(
        client, headers, second["id"], last_name="Neuro", specialty_id=str(NEUROLOGY)
    )

    async def last_names(**params: object) -> list[str]:
        response = await client.get(CONTACTS, params=params, headers=headers)
        assert response.status_code == 200, response.text
        return sorted(c["last_name"] for c in response.json()["items"])

    # Two values of the same filter add up (OR).
    both = await last_names(specialty_id=[str(GYNAECOLOGY), str(VASCULAR_SURGERY)])
    assert both == ["Gine", "GineDos", "Vascular"]

    # A different filter narrows (AND).
    narrowed = await last_names(
        specialty_id=[str(GYNAECOLOGY), str(VASCULAR_SURGERY)], account_id=str(first["id"])
    )
    assert narrowed == ["Gine", "Vascular"]

    heads = await last_names(is_head_of_department=True)
    assert heads == ["Vascular"]

    # An unknown value is an empty page, never an error.
    empty = await client.get(CONTACTS, params={"specialty_id": str(uuid4())}, headers=headers)
    assert empty.status_code == 200
    assert empty.json()["items"] == [] and empty.json()["total"] == 0


async def test_search_is_accent_insensitive_and_sorted_by_last_name(
    client: AsyncClient, users: Users, rep: User
) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers, name="Centro Orden")
    await create_contact(client, headers, account["id"], first_name="Ana", last_name="Zamora")
    await create_contact(client, headers, account["id"], first_name="Bea", last_name="Álvarez")

    listed = await client.get(CONTACTS, params={"q": "alvarez"}, headers=headers)
    assert [c["last_name"] for c in listed.json()["items"]] == ["Álvarez"]

    ordered = await client.get(CONTACTS, params={"account_id": str(account["id"])}, headers=headers)
    assert [c["last_name"] for c in ordered.json()["items"]] == ["Álvarez", "Zamora"]
