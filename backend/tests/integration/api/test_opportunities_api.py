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

OPPORTUNITIES = "/api/v1/opportunities"
EQUIPMENT_ID = str(reference_id("pipelines", "equipment"))
CONSUMABLES_ID = str(reference_id("pipelines", "consumables"))
HOSPITAL_TYPE_ID = str(reference_id("account_types", "public_hospital"))
CONSUMABLES_DIVISION = str(reference_id("divisions", "consumables"))
COMPETITOR_REASON_ID = str(reference_id("loss_reasons", "competitor"))
PRICE_REASON_ID = str(reference_id("loss_reasons", "price"))
HADECO_ID = str(reference_id("brands", "hadeco"))
DOPPLERS_FAMILY_ID = str(reference_id("product_families", "dopplers"))
VISIT_ID = str(reference_id("activity_types", "visit"))


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


async def stage_id_of(client: AsyncClient, headers: dict[str, str], code: str) -> str:
    pipelines = await client.get("/api/v1/pipelines", headers=headers)
    for pipeline in pipelines.json():
        for stage in pipeline["stages"]:
            if pipeline["id"] == EQUIPMENT_ID and stage["code"] == code:
                return str(stage["id"])
    raise AssertionError(f"stage {code} not found")


async def test_create_defaults_and_detail(client: AsyncClient, users: Users, rep: User) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers)

    body = await create_opportunity(client, headers, account["id"])

    assert body["pipeline_name"] == "Equipos" and body["stage_name"] == "Contacto"
    assert body["estimated_amount"] == "30000.00" and body["amount"] == "30000.00"
    assert body["owner_id"] == str(rep.id) and body["owner_name"].startswith("Sales Rep")
    assert body["status"] == "open" and body["is_tender"] is False
    assert body["days_in_stage"] == 0 and len(body["stage_history"]) == 1
    assert "agosto 2026" in body["name"] or "· " in body["name"]

    detail = await client.get(f"{OPPORTUNITIES}/{body['id']}", headers=headers)
    assert detail.status_code == 200 and detail.json()["account_name"] == account["name"]


async def test_create_tender_defaults_and_permissions(
    client: AsyncClient, users: Users, rep: User, manager: User, back_office: User
) -> None:
    rep_headers = users.headers(rep)
    hospital = await create_account(
        client, rep_headers, name="H. La Paz", account_type_id=HOSPITAL_TYPE_ID
    )
    tender = await create_opportunity(client, rep_headers, hospital["id"])
    assert tender["is_tender"] is True

    colleague = await users.create(Role.SALES_REP, email="colleague@quermed.com")
    forbidden = await client.post(
        OPPORTUNITIES,
        json={
            "account_id": hospital["id"],
            "division_id": str(VASCULAR_ID),
            "estimated_amount": "1",
            "owner_id": str(colleague.id),
        },
        headers=rep_headers,
    )
    assert forbidden.status_code == 403
    assert forbidden.json()["code"] == "assignment_forbidden"

    as_back_office = await client.post(
        OPPORTUNITIES,
        json={
            "account_id": hospital["id"],
            "division_id": str(VASCULAR_ID),
            "estimated_amount": "1",
        },
        headers=users.headers(back_office),
    )
    assert as_back_office.status_code == 403

    out_of_scope = await users.create(
        Role.SALES_REP, email="far@quermed.com", division_ids=frozenset({VASCULAR_ID})
    )
    missing = await client.post(
        OPPORTUNITIES,
        json={
            "account_id": hospital["id"],
            "division_id": str(VASCULAR_ID),
            "estimated_amount": "1",
        },
        headers=users.headers(out_of_scope),
    )
    assert missing.status_code == 404


async def test_patch_rules(client: AsyncClient, users: Users, rep: User) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers)
    body = await create_opportunity(client, headers, account["id"])
    url = f"{OPPORTUNITIES}/{body['id']}"

    missing = await client.patch(url, json={"name": "X"}, headers=headers)
    assert missing.status_code == 428

    updated = await client.patch(
        url,
        json={"name": "Doppler Tambre", "is_tender": True, "tender_reference": "EXP-1"},
        headers={**headers, **if_match(1)},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["tender_reference"] == "EXP-1"

    stage_refused = await client.patch(
        url, json={"stage_id": EQUIPMENT_ID}, headers={**headers, **if_match(2)}
    )
    assert stage_refused.status_code == 422

    stale = await client.patch(url, json={"name": "Y"}, headers={**headers, **if_match(1)})
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"

    deadline_without_tender = await client.patch(
        url,
        json={"is_tender": False, "tender_deadline": "2026-09-15"},
        headers={**headers, **if_match(2)},
    )
    assert deadline_without_tender.status_code == 422
    assert deadline_without_tender.json()["code"] == "tender_fields_require_tender"


async def test_lifecycle_flow_and_permissions(
    client: AsyncClient, users: Users, rep: User, manager: User, back_office: User
) -> None:
    rep_headers = users.headers(rep)
    manager_headers = users.headers(manager)
    account = await create_account(client, rep_headers)
    body = await create_opportunity(client, rep_headers, account["id"])
    url = f"{OPPORTUNITIES}/{body['id']}"
    demo = await stage_id_of(client, rep_headers, "demo")
    won_stage = await stage_id_of(client, rep_headers, "won")

    to_won = await client.post(
        f"{url}/stage", json={"stage_id": won_stage}, headers={**rep_headers, **if_match(1)}
    )
    assert to_won.status_code == 409
    assert to_won.json()["code"] == "invalid_opportunity_transition"

    as_bo = await client.post(
        f"{url}/stage",
        json={"stage_id": demo},
        headers={**users.headers(back_office), **if_match(1)},
    )
    assert as_bo.status_code == 403

    moved = await client.post(
        f"{url}/stage", json={"stage_id": demo}, headers={**rep_headers, **if_match(1)}
    )
    assert moved.status_code == 200 and moved.json()["stage_name"] == "Demo"

    no_brand = await client.post(
        f"{url}/lose",
        json={"loss_reason_id": COMPETITOR_REASON_ID},
        headers={**rep_headers, **if_match(2)},
    )
    assert no_brand.status_code == 422
    assert no_brand.json()["code"] == "loss_reason_requires_brand"

    won = await client.post(
        f"{url}/win", json={"won_amount": "24000"}, headers={**rep_headers, **if_match(2)}
    )
    assert won.status_code == 200
    assert won.json()["status"] == "won" and won.json()["won_amount"] == "24000.00"

    closed = await client.post(
        f"{url}/stage", json={"stage_id": demo}, headers={**rep_headers, **if_match(3)}
    )
    assert closed.status_code == 409 and closed.json()["code"] == "opportunity_closed"

    rep_reopen = await client.post(
        f"{url}/reopen", json={"stage_id": demo}, headers={**rep_headers, **if_match(3)}
    )
    assert rep_reopen.status_code == 403 and rep_reopen.json()["code"] == "reopen_forbidden"
    reopened = await client.post(
        f"{url}/reopen", json={"stage_id": demo}, headers={**manager_headers, **if_match(3)}
    )
    assert reopened.status_code == 200 and reopened.json()["status"] == "open"

    lost = await client.post(
        f"{url}/lose",
        json={
            "loss_reason_id": COMPETITOR_REASON_ID,
            "competitor_brand_id": HADECO_ID,
        },
        headers={**rep_headers, **if_match(4)},
    )
    assert lost.status_code == 200 and lost.json()["status"] == "lost"

    at_risk = await client.post(
        f"{url}/at-risk", json={"flag": True}, headers={**manager_headers, **if_match(5)}
    )
    assert at_risk.status_code == 422 and at_risk.json()["code"] == "at_risk_not_supported"

    colleague = await users.create(Role.SALES_REP, email="colleague2@quermed.com")
    rep_assign = await client.put(
        f"{url}/assignment",
        json={"owner_id": str(colleague.id)},
        headers={**rep_headers, **if_match(5)},
    )
    assert rep_assign.status_code == 403
    assigned = await client.put(
        f"{url}/assignment",
        json={"owner_id": str(colleague.id)},
        headers={**manager_headers, **if_match(5)},
    )
    assert assigned.status_code == 200 and assigned.json()["owner_id"] == str(colleague.id)

    # The new owner is told; nobody else is, because nothing was put on their plate.
    notices = await client.get("/api/v1/notifications", headers=users.headers(colleague))
    assert [n["kind"] for n in notices.json()["items"]] == ["opportunity_assigned"]
    assert (await client.get("/api/v1/notifications", headers=manager_headers)).json()[
        "unread_count"
    ] == 0

    detail = await client.get(url, headers=manager_headers)
    assert len(detail.json()["stage_history"]) == 5


async def test_lines_endpoints(
    client: AsyncClient, users: Users, rep: User, manager: User, back_office: User
) -> None:
    rep_headers = users.headers(rep)
    account = await create_account(client, rep_headers)
    body = await create_opportunity(client, rep_headers, account["id"])
    url = f"{OPPORTUNITIES}/{body['id']}"
    admin_headers = users.headers(await users.create(Role.ADMIN, email="a2@quermed.com"))
    product = await client.post(
        "/api/v1/products",
        json={
            "sku": "OPP-API-1",
            "name": "Doppler ES-100",
            "brand_id": HADECO_ID,
            "family_id": DOPPLERS_FAMILY_ID,
            "kind": "equipment",
            "list_price": "12500",
        },
        headers=admin_headers,
    )
    retired = await client.post(
        "/api/v1/products",
        json={
            "sku": "OPP-API-2",
            "name": "Viejo",
            "brand_id": HADECO_ID,
            "family_id": DOPPLERS_FAMILY_ID,
            "kind": "equipment",
            "list_price": "10",
        },
        headers=admin_headers,
    )
    await client.post(
        f"/api/v1/products/{retired.json()['id']}/deactivate",
        headers={**admin_headers, **if_match(1)},
    )

    line = await client.post(
        f"{url}/lines",
        json={"product_id": product.json()["id"], "quantity": "2"},
        headers={**rep_headers, **if_match(1)},
    )
    assert line.status_code == 201, line.text
    assert line.json()["amount"] == "25000.00"
    assert line.json()["lines"][0]["unit_price"] == "12500.00"

    estimate_locked = await client.patch(
        url, json={"estimated_amount": "1"}, headers={**rep_headers, **if_match(2)}
    )
    assert estimate_locked.status_code == 409
    assert estimate_locked.json()["code"] == "opportunity_has_lines"

    duplicated = await client.post(
        f"{url}/lines",
        json={"product_id": product.json()["id"], "quantity": "1"},
        headers={**rep_headers, **if_match(2)},
    )
    assert duplicated.status_code == 409 and duplicated.json()["code"] == "line_duplicated"

    inactive = await client.post(
        f"{url}/lines",
        json={"product_id": retired.json()["id"], "quantity": "1"},
        headers={**rep_headers, **if_match(2)},
    )
    assert inactive.status_code == 422 and inactive.json()["code"] == "line_product_inactive"

    line_id = line.json()["lines"][0]["id"]
    updated = await client.patch(
        f"{url}/lines/{line_id}", json={"quantity": "3"}, headers={**rep_headers, **if_match(2)}
    )
    assert updated.status_code == 200 and updated.json()["amount"] == "37500.00"

    removed = await client.delete(f"{url}/lines/{line_id}", headers={**rep_headers, **if_match(3)})
    assert removed.status_code == 204
    final = await client.get(url, headers=rep_headers)
    assert final.json()["amount"] == "30000.00" and final.json()["lines"] == []

    bo_line = await client.post(
        f"{url}/lines",
        json={"product_id": product.json()["id"], "quantity": "1"},
        headers={**users.headers(back_office), **if_match(4)},
    )
    assert bo_line.status_code == 403


async def test_lists_account_view_and_board(
    client: AsyncClient, users: Users, rep: User, manager: User, session: AsyncSession
) -> None:
    rep_headers = users.headers(rep)
    manager_headers = users.headers(manager)
    account = await create_account(client, rep_headers)
    await create_opportunity(client, rep_headers, account["id"])
    await create_opportunity(
        client, rep_headers, account["id"], estimated_amount="10000", name="Pequeña"
    )
    won = await create_opportunity(
        client, rep_headers, account["id"], estimated_amount="5000", name="Ganada ya"
    )
    await client.post(
        f"{OPPORTUNITIES}/{won['id']}/win", json={}, headers={**rep_headers, **if_match(1)}
    )

    other_territory = await client.post(
        "/api/v1/territories",
        json={"name": "Norte", "provinces": ["48"]},
        headers=users.headers(await users.create(Role.ADMIN, email="a3@quermed.com")),
    )
    assert other_territory.status_code == 201
    foreign_account = await create_account(
        client, manager_headers, name="Centro Bilbao", province="48"
    )
    await create_opportunity(
        client, manager_headers, foreign_account["id"], estimated_amount="70000"
    )

    listed = await client.get(OPPORTUNITIES, headers=rep_headers)
    assert listed.json()["total"] == 2  # open + in scope only
    everything = await client.get(OPPORTUNITIES, params={"status": "all"}, headers=manager_headers)
    assert everything.json()["total"] == 4
    searched = await client.get(OPPORTUNITIES, params={"q": "pequeña"}, headers=rep_headers)
    assert searched.json()["total"] == 1
    by_amount = await client.get(OPPORTUNITIES, params={"sort": "-amount"}, headers=manager_headers)
    assert by_amount.json()["items"][0]["amount"] == "70000.00"
    bad_sort = await client.get(OPPORTUNITIES, params={"sort": "loss_note"}, headers=rep_headers)
    assert bad_sort.status_code == 422

    of_account = await client.get(
        f"/api/v1/accounts/{account['id']}/opportunities", headers=rep_headers
    )
    assert [item["status"] for item in of_account.json()] == ["open", "open", "won"]

    board = await client.get(
        f"{OPPORTUNITIES}/board", params={"pipeline_id": EQUIPMENT_ID}, headers=manager_headers
    )
    assert board.status_code == 200, board.text
    columns = {column["stage"]["code"]: column for column in board.json()["columns"]}
    assert set(columns) == {"contact", "demo", "quote", "negotiation"}
    assert columns["contact"]["count"] == 3
    assert columns["contact"]["total_amount"] == "110000.00"
    assert board.json()["closed_this_month"]["won_count"] == 1
    assert board.json()["closed_this_month"]["won_amount"] == "5000.00"

    scoped_board = await client.get(
        f"{OPPORTUNITIES}/board", params={"pipeline_id": EQUIPMENT_ID}, headers=rep_headers
    )
    assert {c["stage"]["code"]: c["count"] for c in scoped_board.json()["columns"]}["contact"] == 2

    missing = await client.get(
        f"{OPPORTUNITIES}/board", params={"pipeline_id": str(VASCULAR_ID)}, headers=rep_headers
    )
    assert missing.status_code == 404


async def test_activity_link_timeline_and_today(
    client: AsyncClient, users: Users, rep: User, session: AsyncSession
) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers)
    body = await create_opportunity(
        client,
        headers,
        account["id"],
        is_tender=True,
        tender_deadline=(datetime.now(UTC) + timedelta(days=3)).date().isoformat(),
    )
    url = f"{OPPORTUNITIES}/{body['id']}"
    demo = await stage_id_of(client, headers, "demo")
    await client.post(f"{url}/stage", json={"stage_id": demo}, headers={**headers, **if_match(1)})

    other_account = await create_account(client, headers, name="Otro centro")
    wrong = await client.post(
        "/api/v1/activities",
        json={
            "account_id": other_account["id"],
            "activity_type_id": VISIT_ID,
            "opportunity_id": body["id"],
        },
        headers=headers,
    )
    assert wrong.status_code == 422 and wrong.json()["code"] == "opportunity_not_in_account"

    activity = await client.post(
        "/api/v1/activities",
        json={
            "account_id": account["id"],
            "activity_type_id": VISIT_ID,
            "opportunity_id": body["id"],
        },
        headers=headers,
    )
    assert activity.status_code == 201, activity.text
    assert activity.json()["opportunity_name"] == body["name"]

    by_opportunity = await client.get(
        "/api/v1/activities", params={"opportunity_id": body["id"]}, headers=headers
    )
    assert by_opportunity.json()["total"] == 1

    timeline = await client.get(f"/api/v1/accounts/{account['id']}/timeline", headers=headers)
    kinds = [entry["kind"] for entry in timeline.json()["items"]]
    assert "opportunity_stage" in kinds and "activity" in kinds
    stage_entry = next(
        entry for entry in timeline.json()["items"] if entry["kind"] == "opportunity_stage"
    )
    assert stage_entry["stage_change"]["to_stage_name"] in {"Demo", "Contacto"}
    assert stage_entry["activity"] is None

    only_activities = await client.get(
        f"/api/v1/accounts/{account['id']}/timeline",
        params={"kind": "activity"},
        headers=headers,
    )
    assert {entry["kind"] for entry in only_activities.json()["items"]} == {"activity"}

    today = await client.get("/api/v1/me/today", headers=headers)
    assert today.status_code == 200, today.text
    assert [item["id"] for item in today.json()["tenders_due"]] == [body["id"]]
    assert today.json()["at_risk"] == []

    audit_rows = (
        await session.execute(
            select(AuditLogModel.action).where(AuditLogModel.entity_type == "opportunity")
        )
    ).scalars()
    assert "opportunity.stage_changed" in set(audit_rows)
