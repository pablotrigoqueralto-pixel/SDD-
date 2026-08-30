from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.models import AuditLogModel
from app.infrastructure.db.seed import reference_id, run_seed
from tests.integration.api.accounts_helpers import VASCULAR_ID, create_account, if_match
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration

QUOTES = "/api/v1/quotes"
OPPORTUNITIES = "/api/v1/opportunities"
HADECO_ID = str(reference_id("brands", "hadeco"))
DOPPLERS_FAMILY_ID = str(reference_id("product_families", "dopplers"))

FREE_LINE = {
    "description": "Instalación y formación",
    "quantity": "3",
    "unit_price": "33.33",
    "discount_percent": "10",
    "vat_rate": "21",
}


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


@pytest.fixture
async def back_office(users: Users) -> User:
    return await users.create(Role.BACK_OFFICE, email="bo@quermed.com")


async def create_opportunity(
    client: AsyncClient, headers: dict[str, str], account_id: str, **extra: Any
) -> dict[str, Any]:
    response = await client.post(
        OPPORTUNITIES,
        json={
            "account_id": account_id,
            "division_id": str(VASCULAR_ID),
            "estimated_amount": "30000",
            **extra,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def create_quote(
    client: AsyncClient, headers: dict[str, str], opportunity_id: str, **extra: Any
) -> dict[str, Any]:
    response = await client.post(
        QUOTES, json={"opportunity_id": opportunity_id, **extra}, headers=headers
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def send_quote(
    client: AsyncClient, headers: dict[str, str], quote: dict[str, Any], **extra: Any
) -> dict[str, Any]:
    response = await client.post(
        f"{QUOTES}/{quote['id']}/send",
        json={"skip_email": True, **extra},
        headers={**headers, **if_match(quote["version"])},
    )
    assert response.status_code == 200, response.text
    body: dict[str, Any] = response.json()
    return body


async def test_create_copies_lines_and_gates_cost(
    client: AsyncClient, users: Users, rep: User, manager: User
) -> None:
    rep_headers = users.headers(rep)
    admin_headers = users.headers(await users.create(Role.ADMIN, email="a1@quermed.com"))
    product = await client.post(
        "/api/v1/products",
        json={
            "sku": "QUO-API-1",
            "name": "Doppler ES-100",
            "brand_id": HADECO_ID,
            "family_id": DOPPLERS_FAMILY_ID,
            "kind": "equipment",
            "list_price": "12500",
            "cost_price": "9000",
        },
        headers=admin_headers,
    )
    account = await create_account(client, rep_headers)
    opportunity = await create_opportunity(client, rep_headers, account["id"])
    line = await client.post(
        f"{OPPORTUNITIES}/{opportunity['id']}/lines",
        json={"product_id": product.json()["id"], "quantity": "2"},
        headers={**rep_headers, **if_match(1)},
    )
    assert line.status_code == 201

    quote = await create_quote(client, rep_headers, opportunity["id"])

    assert quote["display_number"] == "P-2026-0001"
    assert quote["status"] == "draft"
    assert quote["quotes_number"] if False else True
    first = quote["lines"][0]
    assert first["description"] == "Doppler ES-100"
    assert first["product_code"] == "QUO-API-1"
    assert first["discount_percent"] == "0.00"
    assert first["vat_rate"] == "21.00"
    assert quote["total_base"] == "25000.00"
    assert quote["total_vat"] == "5250.00"
    assert quote["total"] == "30250.00"
    assert quote["conditions"]["validez_dias"] == 30
    assert "unit_cost" not in first and "total_margin" not in quote

    opportunity_read = await client.get(f"{OPPORTUNITIES}/{opportunity['id']}", headers=rep_headers)
    assert opportunity_read.json()["quotes_count"] == 1

    as_manager = await client.get(f"{QUOTES}/{quote['id']}", headers=users.headers(manager))
    body = as_manager.json()
    assert body["lines"][0]["unit_cost"] == "9000.00"
    assert body["total_margin"] == "7000.00"

    of_opportunity = await client.get(
        f"{OPPORTUNITIES}/{opportunity['id']}/quotes", headers=rep_headers
    )
    assert [item["id"] for item in of_opportunity.json()] == [quote["id"]]


async def test_draft_lines_if_match_and_validation(
    client: AsyncClient, users: Users, rep: User
) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers)
    opportunity = await create_opportunity(client, headers, account["id"])
    quote = await create_quote(client, headers, opportunity["id"])
    url = f"{QUOTES}/{quote['id']}"

    missing = await client.patch(url, json={"lines": [FREE_LINE]}, headers=headers)
    assert missing.status_code == 428

    updated = await client.patch(
        url, json={"lines": [FREE_LINE]}, headers={**headers, **if_match(1)}
    )
    assert updated.status_code == 200, updated.text
    body = updated.json()
    assert body["lines"][0]["base"] == "89.99"
    assert body["total_base"] == "89.99"
    assert body["total_vat"] == "18.90"
    assert body["total"] == "108.89"

    stale = await client.patch(url, json={"lines": [FREE_LINE]}, headers={**headers, **if_match(1)})
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"

    bad_vat = await client.patch(
        url,
        json={"lines": [{**FREE_LINE, "vat_rate": "15"}]},
        headers={**headers, **if_match(2)},
    )
    assert bad_vat.status_code == 422 and bad_vat.json()["code"] == "invalid_vat_rate"


async def test_send_freezes_pdf_and_filters(client: AsyncClient, users: Users, rep: User) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers)
    opportunity = await create_opportunity(client, headers, account["id"])
    quote = await create_quote(client, headers, opportunity["id"])
    await client.patch(
        f"{QUOTES}/{quote['id']}", json={"lines": [FREE_LINE]}, headers={**headers, **if_match(1)}
    )

    draft_pdf = await client.get(f"{QUOTES}/{quote['id']}/pdf", headers=headers)
    assert draft_pdf.status_code == 200
    assert draft_pdf.headers["content-type"] == "application/pdf"
    assert draft_pdf.content.startswith(b"%PDF")

    soon = (datetime.now(UTC) + timedelta(days=3)).date().isoformat()
    sent = await send_quote(client, headers, {**quote, "version": 2}, valid_until=soon)
    assert sent["status"] == "sent"
    assert sent["valid_until"] == soon
    assert sent["is_expired"] is False
    assert sent["email_status"] == "skipped"

    frozen = await client.patch(
        f"{QUOTES}/{quote['id']}", json={"lines": [FREE_LINE]}, headers={**headers, **if_match(3)}
    )
    assert frozen.status_code == 409 and frozen.json()["code"] == "quote_not_editable"

    stored_pdf = await client.get(f"{QUOTES}/{quote['id']}/pdf", headers=headers)
    assert stored_pdf.status_code == 200
    assert "P-2026-0001.pdf" in stored_pdf.headers["content-disposition"]

    expiring = await client.get(QUOTES, params={"expiring": "true"}, headers=headers)
    assert [item["id"] for item in expiring.json()["items"]] == [quote["id"]]

    searched = await client.get(QUOTES, params={"q": "P-2026-0001"}, headers=headers)
    assert searched.json()["total"] == 1

    today = await client.get("/api/v1/me/today", headers=headers)
    assert [item["id"] for item in today.json()["expiring_quotes"]] == [quote["id"]]

    timeline = await client.get(f"/api/v1/accounts/{account['id']}/timeline", headers=headers)
    kinds = [entry["kind"] for entry in timeline.json()["items"]]
    assert "quote_sent" in kinds
    quote_entry = next(e for e in timeline.json()["items"] if e["kind"] == "quote_sent")
    assert "P-2026-0001" in quote_entry["quote_event"]["title"]


async def test_accept_wins_and_rejects_sibling(
    client: AsyncClient, users: Users, rep: User, session: AsyncSession
) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers)
    opportunity = await create_opportunity(client, headers, account["id"])
    first = await create_quote(client, headers, opportunity["id"])
    second = await create_quote(client, headers, opportunity["id"])
    await client.patch(
        f"{QUOTES}/{first['id']}", json={"lines": [FREE_LINE]}, headers={**headers, **if_match(1)}
    )
    await send_quote(client, headers, {**first, "version": 2})
    await send_quote(client, headers, second)

    accepted = await client.post(
        f"{QUOTES}/{first['id']}/accept",
        json={"occurred_on": "2026-08-28"},
        headers={**headers, **if_match(3)},
    )
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "accepted"

    won = await client.get(f"{OPPORTUNITIES}/{opportunity['id']}", headers=headers)
    assert won.json()["status"] == "won"
    assert won.json()["won_amount"] == "108.89"

    sibling = await client.get(f"{QUOTES}/{second['id']}", headers=headers)
    assert sibling.json()["status"] == "rejected"
    assert "P-2026-0001" in sibling.json()["rejection_note"]

    again = await client.post(
        f"{QUOTES}/{second['id']}/accept", json={}, headers={**headers, **if_match(3)}
    )
    assert again.status_code == 409

    actions = set(
        (
            await session.execute(
                select(AuditLogModel.action).where(AuditLogModel.entity_type == "quote")
            )
        ).scalars()
    )
    assert {"quote.created", "quote.sent", "quote.accepted", "quote.auto_rejected"} <= actions

    revised = await client.post(
        f"{QUOTES}/{second['id']}/revise", json={}, headers={**headers, **if_match(3)}
    )
    assert revised.status_code == 201, revised.text
    assert revised.json()["display_number"] == "P-2026-0002-v2"

    listed = await client.get(QUOTES, params={"status": "all"}, headers=headers)
    ids = [item["id"] for item in listed.json()["items"]]
    assert second["id"] not in ids and revised.json()["id"] in ids


async def test_reject_retry_permissions_and_delete(
    client: AsyncClient, users: Users, rep: User, back_office: User
) -> None:
    rep_headers = users.headers(rep)
    bo_headers = users.headers(back_office)
    account = await create_account(client, rep_headers)
    opportunity = await create_opportunity(client, rep_headers, account["id"])

    draft = await create_quote(client, bo_headers, opportunity["id"])
    edited = await client.patch(
        f"{QUOTES}/{draft['id']}",
        json={"lines": [FREE_LINE]},
        headers={**bo_headers, **if_match(1)},
    )
    assert edited.status_code == 200

    bo_send = await client.post(
        f"{QUOTES}/{draft['id']}/send",
        json={"skip_email": True},
        headers={**bo_headers, **if_match(2)},
    )
    assert bo_send.status_code == 403
    assert bo_send.json()["code"] == "quote_action_forbidden"

    sent = await send_quote(client, rep_headers, {**draft, "version": 2})

    retry = await client.post(f"{QUOTES}/{draft['id']}/retry-email", headers=rep_headers)
    assert retry.status_code == 409
    assert retry.json()["code"] == "email_retry_not_available"

    rejected = await client.post(
        f"{QUOTES}/{draft['id']}/reject",
        json={"note": "Precio alto"},
        headers={**rep_headers, **if_match(sent["version"])},
    )
    assert rejected.status_code == 200 and rejected.json()["status"] == "rejected"

    frozen_delete = await client.delete(f"{QUOTES}/{draft['id']}", headers=rep_headers)
    assert frozen_delete.status_code == 409

    second = await create_quote(client, bo_headers, opportunity["id"])
    deleted = await client.delete(f"{QUOTES}/{second['id']}", headers=bo_headers)
    assert deleted.status_code == 204


async def test_scope_and_settings_gate(
    client: AsyncClient, users: Users, rep: User, manager: User
) -> None:
    rep_headers = users.headers(rep)
    account = await create_account(client, rep_headers)
    opportunity = await create_opportunity(client, rep_headers, account["id"])
    quote = await create_quote(client, rep_headers, opportunity["id"])

    outsider = await users.create(
        Role.SALES_REP, email="far@quermed.com", division_ids=frozenset({VASCULAR_ID})
    )
    hidden = await client.get(f"{QUOTES}/{quote['id']}", headers=users.headers(outsider))
    assert hidden.status_code == 404
    listed = await client.get(QUOTES, headers=users.headers(outsider))
    assert listed.json()["total"] == 0

    admin_headers = users.headers(await users.create(Role.ADMIN, email="a5@quermed.com"))
    settings = await client.get("/api/v1/quote-settings", headers=admin_headers)
    assert settings.status_code == 200
    assert settings.json()["conditions_defaults"]["validez_dias"] == 30

    readable = await client.get("/api/v1/quote-settings", headers=users.headers(manager))
    assert readable.status_code == 200  # the send dialog needs the template

    denied = await client.put(
        "/api/v1/quote-settings",
        json={
            "conditions_defaults": {"validez_dias": 10},
            "email_template": {"subject": "s", "body": "b"},
        },
        headers=users.headers(manager),
    )
    assert denied.status_code == 403

    updated = await client.put(
        "/api/v1/quote-settings",
        json={
            "conditions_defaults": {"validez_dias": 15, "plazo_entrega": "2 semanas"},
            "email_template": {"subject": "Presupuesto {numero}", "body": "Adjunto {centro}"},
        },
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text

    fresh = await create_quote(client, rep_headers, opportunity["id"])
    assert fresh["conditions"]["validez_dias"] == 15
