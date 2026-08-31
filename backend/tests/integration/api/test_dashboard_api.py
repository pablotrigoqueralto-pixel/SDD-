"""Dashboard endpoint: KPI aggregation, comparison, breakdowns, activity and scoping."""

import time as time_module
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.application.dashboard.periods import DashboardPeriod, resolve_period
from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.models import AccountModel
from app.infrastructure.db.seed import reference_id, run_seed
from tests.integration.api.accounts_helpers import (
    NEUROLOGY_ID,
    VASCULAR_ID,
    create_account,
    if_match,
)
from tests.integration.api.conftest import Users
from tests.integration.api.test_opportunities_api import create_opportunity, stage_id_of

pytestmark = pytest.mark.integration

DASHBOARD = "/api/v1/dashboard"
VISIT_TYPE_ID: UUID = reference_id("activity_types", "visit")
CALL_TYPE_ID: UUID = reference_id("activity_types", "call")


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


async def win(
    client: AsyncClient,
    headers: dict[str, str],
    opportunity: dict[str, Any],
    *,
    won_amount: str,
    won_at: datetime | None = None,
) -> None:
    payload: dict[str, Any] = {"won_amount": won_amount}
    if won_at is not None:
        payload["won_at"] = won_at.isoformat()
    response = await client.post(
        f"/api/v1/opportunities/{opportunity['id']}/win",
        json=payload,
        headers={**headers, **if_match(opportunity["version"])},
    )
    assert response.status_code == 200, response.text


async def lose(client: AsyncClient, headers: dict[str, str], opportunity: dict[str, Any]) -> None:
    reasons = await client.get("/api/v1/loss-reasons", headers=headers)
    response = await client.post(
        f"/api/v1/opportunities/{opportunity['id']}/lose",
        json={"loss_reason_id": reasons.json()[0]["id"], "note": "lost for dashboard test"},
        headers={**headers, **if_match(opportunity["version"])},
    )
    assert response.status_code == 200, response.text


async def record_visit(
    client: AsyncClient,
    headers: dict[str, str],
    account_id: str,
    *,
    type_id: UUID = VISIT_TYPE_ID,
    owner_id: UUID | None = None,
) -> None:
    payload: dict[str, Any] = {
        "account_id": account_id,
        "activity_type_id": str(type_id),
        "status": "done",
    }
    if owner_id is not None:
        payload["owner_id"] = str(owner_id)
    response = await client.post("/api/v1/activities", json=payload, headers=headers)
    assert response.status_code == 201, response.text


async def stage_probability(client: AsyncClient, headers: dict[str, str], code: str) -> int:
    pipelines = await client.get("/api/v1/pipelines", headers=headers)
    for pipeline in pipelines.json():
        for stage in pipeline["stages"]:
            if stage["code"] == code:
                return int(stage["probability"])
    raise AssertionError(f"stage {code} not found")


def in_current_period(day_offset: int = 0) -> str:
    resolved = resolve_period(DashboardPeriod.MONTH)
    return (resolved.current_start + timedelta(days=day_offset)).isoformat()


# --- Task 2.1: endpoint contract -------------------------------------------------


async def test_requires_auth(client: AsyncClient) -> None:
    assert (await client.get(DASHBOARD)).status_code == 401


async def test_invalid_period_is_422(client: AsyncClient, users: Users, manager: User) -> None:
    response = await client.get(
        DASHBOARD, params={"period": "week"}, headers=users.headers(manager)
    )
    assert response.status_code == 422


async def test_empty_dashboard_default_month(
    client: AsyncClient, users: Users, manager: User
) -> None:
    response = await client.get(DASHBOARD, headers=users.headers(manager))
    assert response.status_code == 200, response.text
    body = response.json()

    expected = resolve_period(DashboardPeriod.MONTH)
    assert body["period"] == {
        "period": "month",
        "start": expected.current_start.isoformat(),
        "end": expected.current_end.isoformat(),
        "previous_start": expected.previous_start.isoformat(),
        "previous_end": expected.previous_end.isoformat(),
    }
    assert body["summary"]["won"] == {
        "amount": "0.00",
        "count": 0,
        "previous_amount": "0.00",
        "previous_count": 0,
    }
    conversion = body["summary"]["conversion"]
    assert conversion["rate"] is None and conversion["won"] == 0 and conversion["closed"] == 0
    assert conversion["previous_rate"] is None
    assert body["summary"]["forecast"] == {"amount": "0.00", "count": 0}
    assert body["summary"]["open_pipeline"] == {"amount": "0.00", "count": 0}
    assert body["pipeline_by_stage"] == []
    assert body["by_division"] == []
    assert body["by_rep"] == []
    assert body["activity"] == []
    assert body["neglected_accounts"] == {"total": 0, "items": []}


# --- Task 1.2: summary KPIs and previous-period comparison -----------------------


async def test_summary_won_conversion_and_forecast(
    client: AsyncClient, users: Users, manager: User
) -> None:
    headers = users.headers(manager)
    account = await create_account(client, headers, name="Hospital Dashboard")
    resolved = resolve_period(DashboardPeriod.MONTH)

    won_now = await create_opportunity(client, headers, account["id"], estimated_amount="2000")
    await win(client, headers, won_now, won_amount="2000.00")

    won_before = await create_opportunity(client, headers, account["id"], estimated_amount="1500")
    previous_mid = datetime.combine(
        resolved.previous_start + timedelta(days=10), datetime.min.time(), tzinfo=UTC
    )
    await win(client, headers, won_before, won_amount="1500.00", won_at=previous_mid)

    lost_now = await create_opportunity(client, headers, account["id"], estimated_amount="900")
    await lose(client, headers, lost_now)

    await create_opportunity(  # open, closing inside the period → forecast
        client,
        headers,
        account["id"],
        estimated_amount="10000",
        expected_close_date=in_current_period(1),
    )
    await create_opportunity(  # open, closing far away → pipeline only
        client,
        headers,
        account["id"],
        estimated_amount="5000",
        expected_close_date=(resolved.current_end + timedelta(days=40)).isoformat(),
    )

    body = (await client.get(DASHBOARD, headers=headers)).json()

    assert body["summary"]["won"] == {
        "amount": "2000.00",
        "count": 1,
        "previous_amount": "1500.00",
        "previous_count": 1,
    }
    conversion = body["summary"]["conversion"]
    assert conversion["won"] == 1 and conversion["closed"] == 2
    assert conversion["rate"] == pytest.approx(0.5)
    assert conversion["previous_rate"] == pytest.approx(1.0)

    contact_probability = await stage_probability(client, headers, "contact")
    expected_forecast = (Decimal("10000") * contact_probability / 100).quantize(Decimal("0.01"))
    assert body["summary"]["forecast"] == {"amount": str(expected_forecast), "count": 1}
    assert body["summary"]["open_pipeline"] == {"amount": "15000.00", "count": 2}


# --- Task 1.3: stage snapshot and breakdowns -------------------------------------


async def test_pipeline_by_stage_in_stage_order(
    client: AsyncClient, users: Users, manager: User
) -> None:
    headers = users.headers(manager)
    account = await create_account(client, headers, name="Centro Etapas")

    await create_opportunity(client, headers, account["id"], estimated_amount="1000")
    moved = await create_opportunity(client, headers, account["id"], estimated_amount="3000")
    demo_stage = await stage_id_of(client, headers, "demo")
    response = await client.post(
        f"/api/v1/opportunities/{moved['id']}/stage",
        json={"stage_id": demo_stage},
        headers={**headers, **if_match(moved["version"])},
    )
    assert response.status_code == 200, response.text

    rows = (await client.get(DASHBOARD, headers=headers)).json()["pipeline_by_stage"]
    assert [(row["name"], row["amount"], row["count"]) for row in rows] == [
        ("Contacto", "1000.00", 1),
        ("Demo", "3000.00", 1),
    ]


async def test_breakdowns_by_division_and_rep(
    client: AsyncClient, users: Users, manager: User, rep: User
) -> None:
    headers = users.headers(manager)
    colleague = await users.create(
        Role.SALES_REP, email="colleague-dash@quermed.com", full_name="Colega Panel"
    )
    vascular_account = await create_account(client, headers, name="Centro Vascular")
    neuro_account = await create_account(
        client, headers, name="Centro Neuro", division_ids=[str(NEUROLOGY_ID)]
    )

    big = await create_opportunity(
        client,
        headers,
        vascular_account["id"],
        estimated_amount="30000",
        owner_id=str(colleague.id),
    )
    await win(client, headers, big, won_amount="30000.00")
    small = await create_opportunity(
        client,
        headers,
        neuro_account["id"],
        division_id=str(NEUROLOGY_ID),
        estimated_amount="12000",
        owner_id=str(colleague.id),
    )
    await win(client, headers, small, won_amount="12000.00")

    rep_deal = await create_opportunity(
        client,
        users.headers(rep),
        (await create_account(client, users.headers(rep), name="Centro Del Rep"))["id"],
        estimated_amount="4000",
    )
    await win(client, users.headers(rep), rep_deal, won_amount="4000.00")

    body = (await client.get(DASHBOARD, headers=headers)).json()

    divisions = [(row["name"], row["won_amount"], row["won_count"]) for row in body["by_division"]]
    assert divisions[0][1] == "34000.00"  # vascular: 30000 manager + 4000 rep
    assert ("Neurología", "12000.00", 1) in divisions or divisions[1][1] == "12000.00"

    reps = {row["name"]: row for row in body["by_rep"]}
    assert reps[colleague.full_name]["won_amount"] == "42000.00"
    assert reps[rep.full_name]["won_amount"] == "4000.00"
    assert list(reps) == [colleague.full_name, rep.full_name]  # ordered by won € desc


# --- Task 1.4: activity metrics and neglected accounts ---------------------------


async def test_activity_per_rep_and_type(
    client: AsyncClient, users: Users, manager: User, rep: User
) -> None:
    rep_headers = users.headers(rep)
    account = await create_account(client, rep_headers, name="Centro Actividad")
    for _ in range(3):
        await record_visit(client, rep_headers, account["id"])
    for _ in range(2):
        await record_visit(client, rep_headers, account["id"], type_id=CALL_TYPE_ID)

    body = (await client.get(DASHBOARD, headers=users.headers(manager))).json()

    row = next(entry for entry in body["activity"] if entry["name"] == rep.full_name)
    assert row["total"] == 5
    by_type = {item["name"]: item["count"] for item in row["by_type"]}
    assert by_type == {"Visita": 3, "Llamada": 2}


async def test_neglected_accounts_order_and_never(
    client: AsyncClient,
    users: Users,
    manager: User,
    session: AsyncSession,
) -> None:
    headers = users.headers(manager)
    stale = await create_account(client, headers, name="Centro Olvidado")
    never = await create_account(client, headers, name="Centro Nunca")
    fresh = await create_account(client, headers, name="Centro Reciente")
    await record_visit(client, headers, fresh["id"])

    now = datetime.now(tz=UTC)
    await session.execute(
        update(AccountModel)
        .where(AccountModel.id == UUID(stale["id"]))
        .values(last_contact_at=now - timedelta(days=90))
    )
    await session.execute(
        update(AccountModel)
        .where(AccountModel.id.in_([UUID(stale["id"]), UUID(never["id"])]))
        .values(created_at=now - timedelta(days=120))
    )
    await session.commit()

    body = (await client.get(DASHBOARD, headers=headers)).json()["neglected_accounts"]

    assert body["total"] == 2
    assert [item["name"] for item in body["items"]] == ["Centro Nunca", "Centro Olvidado"]
    assert body["items"][0]["days_since_contact"] is None
    assert body["items"][1]["days_since_contact"] == 90
    assert all(item["name"] != "Centro Reciente" for item in body["items"])


# --- Task 1.5: role scoping ------------------------------------------------------


async def test_rep_sees_only_their_portfolio_and_no_by_rep(
    client: AsyncClient, users: Users, manager: User, rep: User
) -> None:
    manager_headers = users.headers(manager)
    foreign = await create_account(client, manager_headers, name="Centro Ajeno")
    # New opportunities default to the territory rep as owner, and only active sales reps
    # can own one — pin a second rep explicitly so the deal is foreign to `rep`.
    colleague = await users.create(Role.SALES_REP, email="foreign-dash@quermed.com")
    foreign_deal = await create_opportunity(
        client, manager_headers, foreign["id"], estimated_amount="9000", owner_id=str(colleague.id)
    )
    await win(client, manager_headers, foreign_deal, won_amount="9000.00")

    rep_headers = users.headers(rep)
    own = await create_account(client, rep_headers, name="Centro Propio")
    own_deal = await create_opportunity(client, rep_headers, own["id"], estimated_amount="1000")
    await win(client, rep_headers, own_deal, won_amount="1000.00")

    body = (await client.get(DASHBOARD, headers=rep_headers)).json()

    assert own_deal["owner_id"] == str(rep.id)
    assert body["summary"]["won"]["amount"] == "1000.00"
    assert body["by_rep"] is None
    assert [row["won_amount"] for row in body["by_division"]] == ["1000.00"]


async def test_back_office_sees_company_panel(
    client: AsyncClient, users: Users, manager: User
) -> None:
    manager_headers = users.headers(manager)
    account = await create_account(client, manager_headers, name="Centro BO")
    deal = await create_opportunity(client, manager_headers, account["id"], estimated_amount="7000")
    await win(client, manager_headers, deal, won_amount="7000.00")

    back_office = await users.create(Role.BACK_OFFICE, email="bo-dash@quermed.com")
    body = (await client.get(DASHBOARD, headers=users.headers(back_office))).json()

    assert body["summary"]["won"]["amount"] == "7000.00"
    assert body["by_rep"] is not None and len(body["by_rep"]) == 1


# --- Task 2.2: performance budget ------------------------------------------------


async def test_responds_within_budget(client: AsyncClient, users: Users, manager: User) -> None:
    headers = users.headers(manager)
    account = await create_account(client, headers, name="Centro Presupuesto Tiempo")
    for index in range(10):
        deal = await create_opportunity(
            client, headers, account["id"], estimated_amount=str(1000 + index)
        )
        if index % 2 == 0:
            await win(client, headers, deal, won_amount=str(1000 + index))

    started = time_module.perf_counter()
    response = await client.get(DASHBOARD, headers=headers)
    elapsed = time_module.perf_counter() - started

    assert response.status_code == 200
    assert elapsed < 0.5, f"dashboard took {elapsed:.3f}s"
