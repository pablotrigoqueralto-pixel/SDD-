"""Calendar feed: month entries, timeline date semantics and role scoping."""

from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine

from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.seed import reference_id, run_seed
from tests.integration.api.accounts_helpers import VASCULAR_ID, create_account, if_match
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration

CALENDAR = "/api/v1/activities/calendar"
VISIT_TYPE_ID: UUID = reference_id("activity_types", "visit")
JULY = {"year": 2026, "month": 7}


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


@pytest.fixture
async def rep(users: Users, centro: Territory) -> User:
    return await users.create(
        Role.SALES_REP,
        email="cal-rep@quermed.com",
        full_name="Rep Calendario",
        territory_ids=frozenset({centro.id}),
        division_ids=frozenset({VASCULAR_ID}),
    )


@pytest.fixture
async def manager(users: Users) -> User:
    return await users.create(Role.SALES_MANAGER, email="cal-mgr@quermed.com")


async def plan_activity(
    client: AsyncClient,
    headers: dict[str, str],
    account_id: str,
    scheduled_at: str,
    *,
    owner_id: UUID | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "account_id": account_id,
        "activity_type_id": str(VISIT_TYPE_ID),
        "status": "planned",
        "scheduled_at": scheduled_at,
    }
    if owner_id is not None:
        payload["owner_id"] = str(owner_id)
    response = await client.post("/api/v1/activities", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def complete_activity(
    client: AsyncClient, headers: dict[str, str], activity: dict[str, Any], done_at: str
) -> None:
    response = await client.post(
        f"/api/v1/activities/{activity['id']}/complete",
        json={"done_at": done_at, "outcome": "positive"},
        headers={**headers, **if_match(activity["version"])},
    )
    assert response.status_code == 200, response.text


async def test_requires_auth(client: AsyncClient) -> None:
    assert (await client.get(CALENDAR, params=JULY)).status_code == 401


async def test_invalid_month_is_422(client: AsyncClient, users: Users, manager: User) -> None:
    response = await client.get(
        CALENDAR, params={"year": 2026, "month": 13}, headers=users.headers(manager)
    )
    assert response.status_code == 422


async def test_month_entries_with_timeline_semantics(
    client: AsyncClient, users: Users, rep: User
) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers, name="Centro Calendario")

    planned = await plan_activity(client, headers, account["id"], "2026-07-15T10:00:00Z")
    moved = await plan_activity(client, headers, account["id"], "2026-07-13T09:00:00Z")
    await complete_activity(client, headers, moved, "2026-07-14T09:30:00Z")
    cancelled = await plan_activity(client, headers, account["id"], "2026-07-20T12:00:00Z")
    response = await client.post(
        f"/api/v1/activities/{cancelled['id']}/cancel",
        json={"reason": "test"},
        headers={**headers, **if_match(cancelled["version"])},
    )
    assert response.status_code == 200, response.text

    body = (await client.get(CALENDAR, params=JULY, headers=headers)).json()

    assert body["year"] == 2026 and body["month"] == 7
    by_id = {item["id"]: item for item in body["items"]}
    assert body["total"] == 2 and len(by_id) == 2
    assert by_id[planned["id"]]["occurred_on"] == "2026-07-15"
    assert by_id[planned["id"]]["status"] == "planned"
    # Scheduled Monday the 13th, done Tuesday the 14th: the calendar shows Tuesday.
    assert by_id[moved["id"]]["occurred_on"] == "2026-07-14"
    assert by_id[moved["id"]]["status"] == "done"
    assert cancelled["id"] not in by_id

    entry = by_id[planned["id"]]
    assert entry["account_name"] == "Centro Calendario"
    assert entry["owner_name"] == "Rep Calendario"
    assert entry["activity_type"]["code"] == "visit"
    assert entry["activity_type"]["icon"]


async def test_late_night_boundary_lands_in_next_month(
    client: AsyncClient, users: Users, rep: User
) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers, name="Centro Frontera")
    boundary = await plan_activity(client, headers, account["id"], "2026-07-31T10:00:00Z")
    # 22:30 UTC on July 31st is 00:30 on August 1st in Madrid (UTC+2).
    await complete_activity(client, headers, boundary, "2026-07-31T22:30:00Z")

    july = (await client.get(CALENDAR, params=JULY, headers=headers)).json()
    august = (await client.get(CALENDAR, params={"year": 2026, "month": 8}, headers=headers)).json()

    assert all(item["id"] != boundary["id"] for item in july["items"])
    assert any(
        item["id"] == boundary["id"] and item["occurred_on"] == "2026-08-01"
        for item in august["items"]
    )


async def test_scoping_manager_team_filter_and_rep_denial(
    client: AsyncClient, users: Users, rep: User, manager: User
) -> None:
    rep_headers = users.headers(rep)
    account = await create_account(client, rep_headers, name="Centro Scope Cal")
    mine = await plan_activity(client, rep_headers, account["id"], "2026-07-10T10:00:00Z")

    colleague = await users.create(
        Role.SALES_REP, email="cal-colleague@quermed.com", full_name="Colega Calendario"
    )
    manager_headers = users.headers(manager)
    theirs = await plan_activity(
        client, manager_headers, account["id"], "2026-07-11T10:00:00Z", owner_id=colleague.id
    )

    team = (await client.get(CALENDAR, params=JULY, headers=manager_headers)).json()
    team_ids = {item["id"] for item in team["items"]}
    assert {mine["id"], theirs["id"]} <= team_ids

    filtered = (
        await client.get(
            CALENDAR, params={**JULY, "owner_id": str(colleague.id)}, headers=manager_headers
        )
    ).json()
    assert {item["id"] for item in filtered["items"]} == {theirs["id"]}

    own = (await client.get(CALENDAR, params=JULY, headers=rep_headers)).json()
    assert mine["id"] in {item["id"] for item in own["items"]}
    assert theirs["id"] not in {item["id"] for item in own["items"]}

    denied = await client.get(
        CALENDAR, params={**JULY, "owner_id": str(colleague.id)}, headers=rep_headers
    )
    assert denied.status_code == 403

    back_office = await users.create(Role.BACK_OFFICE, email="cal-bo@quermed.com")
    bo = (await client.get(CALENDAR, params=JULY, headers=users.headers(back_office))).json()
    assert {mine["id"], theirs["id"]} <= {item["id"] for item in bo["items"]}
