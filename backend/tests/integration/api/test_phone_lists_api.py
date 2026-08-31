"""Phone lists, billing notes and the head-of-department flag through the API."""

from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.models import AccountModel, AccountPhoneModel
from app.infrastructure.db.seed import run_seed
from tests.integration.api.accounts_helpers import (
    ACCOUNTS,
    VASCULAR_ID,
    create_account,
    create_contact,
    if_match,
)
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration

SEARCH = "/api/v1/search"
CENTRALITA = {"label": "Centralita", "number": "915550000"}
SECRETARIA = {"label": "Secretaría", "number": "915550001", "extension": "4021"}
SERVICIO = {"label": "Servicio de vascular", "number": "915559876"}


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


@pytest.fixture
async def rep(users: Users, centro: Territory) -> User:
    return await users.create(
        Role.SALES_REP,
        email="phones-rep@quermed.com",
        territory_ids=frozenset({centro.id}),
        division_ids=frozenset({VASCULAR_ID}),
    )


async def test_account_phone_list_round_trip_and_replacement(
    client: AsyncClient, users: Users, rep: User
) -> None:
    headers = users.headers(rep)
    account = await create_account(
        client, headers, name="Hospital Teléfonos", phones=[CENTRALITA, SECRETARIA]
    )

    assert [p["label"] for p in account["phones"]] == ["Centralita", "Secretaría"]
    assert account["phones"][0]["number"] == "+34915550000"
    assert account["phones"][1]["extension"] == "4021"

    # Omitting the list leaves it untouched.
    patched = await client.patch(
        f"{ACCOUNTS}/{account['id']}",
        json={"city": "Madrid"},
        headers={**headers, **if_match(account["version"])},
    )
    assert patched.status_code == 200, patched.text
    assert len(patched.json()["phones"]) == 2

    # Sending a shorter list replaces the whole thing.
    replaced = await client.patch(
        f"{ACCOUNTS}/{account['id']}",
        json={"phones": [SERVICIO]},
        headers={**headers, **if_match(patched.json()["version"])},
    )
    assert replaced.status_code == 200, replaced.text
    assert [p["label"] for p in replaced.json()["phones"]] == ["Servicio de vascular"]


async def test_summary_exposes_the_primary_phone(
    client: AsyncClient, users: Users, rep: User
) -> None:
    headers = users.headers(rep)
    await create_account(client, headers, name="Hospital Resumen", phones=[CENTRALITA, SECRETARIA])

    listed = await client.get(ACCOUNTS, params={"q": "Hospital Resumen"}, headers=headers)

    assert listed.status_code == 200, listed.text
    summary = listed.json()["items"][0]
    assert summary["primary_phone"] == "+34915550000"
    assert "phones" not in summary  # summaries stay light: only the primary number


async def test_duplicate_label_and_number_is_rejected(
    client: AsyncClient, users: Users, rep: User
) -> None:
    headers = users.headers(rep)
    response = await client.post(
        ACCOUNTS,
        json={
            "name": "Centro Duplicado",
            "account_type_id": account_type_id(),
            "province_code": "28",
            "phones": [CENTRALITA, CENTRALITA],
        },
        headers=headers,
    )

    assert response.status_code == 422
    assert response.json()["code"] == "phone_duplicated"


async def test_invalid_phone_rejects_the_whole_payload(
    client: AsyncClient, users: Users, rep: User
) -> None:
    headers = users.headers(rep)
    response = await client.post(
        ACCOUNTS,
        json={
            "name": "Centro Inválido",
            "account_type_id": account_type_id(),
            "province_code": "28",
            "phones": [CENTRALITA, {"label": "Mal", "number": "915550001 ext 4021"}],
        },
        headers=headers,
    )
    assert response.status_code == 422
    body = response.json()
    assert body["code"] == "phone_invalid"
    # The error names the offending row so an API client knows which one to fix.
    assert body["errors"][0]["field"] == "phones.1"

    listed = await client.get(ACCOUNTS, params={"q": "Centro Inválido"}, headers=headers)
    assert listed.json()["total"] == 0


def account_type_id() -> str:
    from tests.integration.api.accounts_helpers import IVF_CLINIC_ID

    return str(IVF_CLINIC_ID)


async def test_billing_notes_editable_by_back_office(
    client: AsyncClient, users: Users, rep: User
) -> None:
    rep_headers = users.headers(rep)
    account = await create_account(client, rep_headers, name="Hospital Facturación")
    back_office = await users.create(Role.BACK_OFFICE, email="bo-phones@quermed.com")
    bo_headers = users.headers(back_office)

    allowed = await client.patch(
        f"{ACCOUNTS}/{account['id']}",
        json={
            "billing_notes": (
                "Factura por FACe. Contabilidad: Marta Gil, contabilidad@hospital.example"
            ),
            "phones": [CENTRALITA],
        },
        headers={**bo_headers, **if_match(account["version"])},
    )
    assert allowed.status_code == 200, allowed.text
    assert "FACe" in allowed.json()["billing_notes"]

    forbidden = await client.patch(
        f"{ACCOUNTS}/{account['id']}",
        json={"notes": "no puedo"},
        headers={**bo_headers, **if_match(allowed.json()["version"])},
    )
    assert forbidden.status_code == 403


async def test_head_of_department_flag_and_filter(
    client: AsyncClient, users: Users, rep: User
) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers, name="Hospital Jefaturas")

    boss: dict[str, Any] = await create_contact(
        client,
        headers,
        account["id"],
        first_name="Miguel",
        last_name="Serrano",
        is_head_of_department=True,
    )
    await create_contact(client, headers, account["id"], first_name="Rosa", last_name="Delgado")

    assert boss["is_head_of_department"] is True

    heads = await client.get(
        f"{ACCOUNTS}/{account['id']}/contacts",
        params={"is_head_of_department": "true"},
        headers=headers,
    )
    assert [c["first_name"] for c in heads.json()] == ["Miguel"]


async def test_search_finds_a_centre_by_its_non_primary_phone(
    client: AsyncClient, users: Users, rep: User
) -> None:
    headers = users.headers(rep)
    account = await create_account(
        client, headers, name="Hospital Búsqueda Teléfono", phones=[CENTRALITA, SERVICIO]
    )

    found = await client.get(SEARCH, params={"q": "915 55 98 76"}, headers=headers)

    assert found.status_code == 200, found.text
    assert any(item["id"] == account["id"] for item in found.json()["accounts"]["items"])


async def test_anonymisation_deletes_contact_phones_only(
    client: AsyncClient, users: Users, rep: User
) -> None:
    manager = await users.create(Role.SALES_MANAGER, email="mgr-phones@quermed.com")
    headers = users.headers(rep)
    account = await create_account(client, headers, name="Hospital Anonimiza", phones=[CENTRALITA])
    contact = await create_contact(
        client,
        headers,
        account["id"],
        first_name="Elena",
        last_name="Navarro",
        phones=[{"label": "Móvil", "number": "612345678"}],
    )

    response = await client.post(
        f"/api/v1/contacts/{contact['id']}/anonymise",
        headers={**users.headers(manager), **if_match(contact["version"])},
    )
    assert response.status_code == 200, response.text
    assert response.json()["phones"] == []

    still_there = await client.get(f"{ACCOUNTS}/{account['id']}", headers=headers)
    assert [p["label"] for p in still_there.json()["phones"]] == ["Centralita"]


async def test_deleting_the_account_row_cascades_its_phones(
    client: AsyncClient, users: Users, rep: User, session: AsyncSession
) -> None:
    """The app deactivates rather than deletes, but the FK must still clean up."""
    headers = users.headers(rep)
    account = await create_account(
        client, headers, name="Hospital Cascada", phones=[CENTRALITA, SECRETARIA]
    )
    account_id = UUID(account["id"])

    before = await session.execute(
        select(func.count())
        .select_from(AccountPhoneModel)
        .where(AccountPhoneModel.account_id == account_id)
    )
    assert before.scalar_one() == 2

    await session.execute(delete(AccountModel).where(AccountModel.id == account_id))
    await session.flush()

    after = await session.execute(
        select(func.count())
        .select_from(AccountPhoneModel)
        .where(AccountPhoneModel.account_id == account_id)
    )
    assert after.scalar_one() == 0
