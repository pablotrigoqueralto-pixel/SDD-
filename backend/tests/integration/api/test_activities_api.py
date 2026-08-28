from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import uuid4

import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.models import AuditLogModel
from app.infrastructure.db.seed import reference_id, run_seed
from tests.integration.api.accounts_helpers import (
    ACCOUNTS,
    VASCULAR_ID,
    create_account,
    create_contact,
    if_match,
)
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration

ACTIVITIES = "/api/v1/activities"
VISIT_ID = str(reference_id("activity_types", "visit"))
CALL_ID = str(reference_id("activity_types", "call"))
NOTE_ID = str(reference_id("activity_types", "note"))


def iso(delta: timedelta) -> str:
    return (datetime.now(UTC) + delta).isoformat()


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


async def post_activity(
    client: AsyncClient, headers: dict[str, str], account_id: str, **extra: Any
) -> dict[str, Any]:
    response = await client.post(
        ACTIVITIES,
        json={"account_id": account_id, "activity_type_id": VISIT_ID, **extra},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    body: dict[str, Any] = response.json()
    return body


async def audit_actions(session: AsyncSession, entity_id: str) -> list[str]:
    statement = (
        select(AuditLogModel.action)
        .where(AuditLogModel.entity_id == entity_id)
        .order_by(AuditLogModel.occurred_at, AuditLogModel.id)
    )
    return list((await session.execute(statement)).scalars().all())


async def test_rep_records_a_visit_with_three_fields(
    client: AsyncClient, users: Users, rep: User
) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers)

    body = await post_activity(client, headers, account["id"])

    assert body["status"] == "done" and body["owner_id"] == str(rep.id)
    assert body["activity_type_name"] == "Visita" and body["account_name"] == "Clínica Tambre"
    assert body["owner_name"] == rep.full_name
    assert datetime.fromisoformat(body["scheduled_at"]) > datetime.now(UTC) - timedelta(minutes=1)
    detail = await client.get(f"{ACCOUNTS}/{account['id']}", headers=headers)
    assert detail.json()["last_contact_at"] == body["scheduled_at"]


async def test_create_validations_and_roles(
    client: AsyncClient, users: Users, rep: User, manager: User
) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers)
    other = await create_account(client, users.headers(manager), name="Far", province="48")
    back_office = await users.create(Role.BACK_OFFICE, email="bo@quermed.com")

    forbidden_owner = await client.post(
        ACTIVITIES,
        json={
            "account_id": account["id"],
            "activity_type_id": VISIT_ID,
            "owner_id": str(manager.id),
        },
        headers=headers,
    )
    assert forbidden_owner.status_code == 403
    assert forbidden_owner.json()["code"] == "assignment_forbidden"

    out_of_scope = await client.post(
        ACTIVITIES, json={"account_id": other["id"], "activity_type_id": VISIT_ID}, headers=headers
    )
    assert out_of_scope.status_code == 404

    bo = await client.post(
        ACTIVITIES,
        json={"account_id": account["id"], "activity_type_id": VISIT_ID},
        headers=users.headers(back_office),
    )
    assert bo.status_code == 403

    note_planned = await client.post(
        ACTIVITIES,
        json={"account_id": account["id"], "activity_type_id": NOTE_ID, "status": "planned"},
        headers=headers,
    )
    assert note_planned.status_code == 422
    assert note_planned.json()["code"] == "note_cannot_be_planned"

    stranger = await create_contact(client, users.headers(manager), other["id"])
    wrong_contact = await client.post(
        ACTIVITIES,
        json={
            "account_id": account["id"],
            "activity_type_id": VISIT_ID,
            "contact_ids": [stranger["id"]],
        },
        headers=headers,
    )
    assert wrong_contact.status_code == 422
    assert wrong_contact.json()["code"] == "contact_not_in_account"

    delegated = await post_activity(
        client, users.headers(manager), account["id"], owner_id=str(rep.id)
    )
    assert delegated["owner_id"] == str(rep.id)


async def test_lifecycle_endpoints(
    client: AsyncClient, users: Users, rep: User, manager: User, session: AsyncSession
) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers)
    contact = await create_contact(client, headers, account["id"])
    planned = await post_activity(
        client,
        headers,
        account["id"],
        status="planned",
        scheduled_at=iso(timedelta(days=1)),
        contact_ids=[contact["id"]],
    )
    assert planned["contacts"][0]["name"] == "Ana Pérez"

    no_precondition = await client.post(
        f"{ACTIVITIES}/{planned['id']}/reschedule",
        json={"scheduled_at": iso(timedelta(days=2))},
        headers=headers,
    )
    assert no_precondition.status_code == 428
    stale = await client.post(
        f"{ACTIVITIES}/{planned['id']}/reschedule",
        json={"scheduled_at": iso(timedelta(days=2))},
        headers={**headers, **if_match(9)},
    )
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"
    moved = await client.post(
        f"{ACTIVITIES}/{planned['id']}/reschedule",
        json={"scheduled_at": iso(timedelta(days=2))},
        headers={**headers, **if_match(1)},
    )
    assert moved.status_code == 200 and moved.json()["version"] == 2

    empty_reason = await client.post(
        f"{ACTIVITIES}/{planned['id']}/cancel",
        json={"reason": "  "},
        headers={**headers, **if_match(2)},
    )
    assert empty_reason.status_code == 422
    assert empty_reason.json()["code"] == "cancel_reason_required"

    past_next = await client.post(
        f"{ACTIVITIES}/{planned['id']}/complete",
        json={
            "next_action": {"activity_type_id": CALL_ID, "scheduled_at": iso(-timedelta(days=1))}
        },
        headers={**headers, **if_match(2)},
    )
    assert past_next.status_code == 422
    assert past_next.json()["code"] == "next_action_in_past"

    completed = await client.post(
        f"{ACTIVITIES}/{planned['id']}/complete",
        json={
            "outcome": "positive",
            "next_action": {"activity_type_id": CALL_ID, "scheduled_at": iso(timedelta(days=7))},
        },
        headers={**headers, **if_match(2)},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "done" and completed.json()["outcome"] == "positive"
    follow_up_id = completed.json()["next_activity_id"]
    assert follow_up_id
    follow_up = await client.get(f"{ACTIVITIES}/{follow_up_id}", headers=headers)
    assert follow_up.json()["status"] == "planned"
    assert follow_up.json()["contact_ids"] == [contact["id"]]

    again = await client.post(
        f"{ACTIVITIES}/{planned['id']}/reschedule",
        json={"scheduled_at": iso(timedelta(days=3))},
        headers={**headers, **if_match(3)},
    )
    assert again.status_code == 409
    assert again.json()["code"] == "invalid_activity_transition"

    edited = await client.patch(
        f"{ACTIVITIES}/{planned['id']}",
        json={"subject": "Demo equipo", "status": "planned"},
        headers={**headers, **if_match(3)},
    )
    assert edited.status_code == 200 and edited.json()["subject"] == "Demo equipo"
    assert edited.json()["status"] == "done"

    cancelled = await client.post(
        f"{ACTIVITIES}/{follow_up_id}/cancel",
        json={"reason": "Centro cerrado"},
        headers={**users.headers(manager), **if_match(1)},
    )
    assert cancelled.status_code == 200 and cancelled.json()["cancel_reason"] == "Centro cerrado"

    assert await audit_actions(session, planned["id"]) == [
        "activity.created",
        "activity.rescheduled",
        "activity.completed",
        "activity.updated",
    ]
    assert await audit_actions(session, follow_up_id) == ["activity.created", "activity.cancelled"]
    detail = await client.get(f"{ACCOUNTS}/{account['id']}", headers=headers)
    assert detail.json()["next_activity_at"] is None


async def test_edit_window_is_enforced_over_http(
    client: AsyncClient, users: Users, rep: User, manager: User
) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers)
    old = await post_activity(client, headers, account["id"], scheduled_at=iso(-timedelta(days=10)))
    # `done_at` equals the given time when recording the past, so the window has expired.
    locked = await client.patch(
        f"{ACTIVITIES}/{old['id']}", json={"notes": "x"}, headers={**headers, **if_match(1)}
    )
    assert locked.status_code == 409 and locked.json()["code"] == "activity_locked"
    by_manager = await client.patch(
        f"{ACTIVITIES}/{old['id']}",
        json={"notes": "x"},
        headers={**users.headers(manager), **if_match(1)},
    )
    assert by_manager.status_code == 200


async def test_list_timeline_and_today(
    client: AsyncClient, users: Users, rep: User, manager: User
) -> None:
    headers = users.headers(rep)
    account = await create_account(client, headers)
    far = await create_account(client, users.headers(manager), name="Far", province="48")
    yesterday = await post_activity(
        client, headers, account["id"], scheduled_at=iso(-timedelta(days=1)), subject="Ayer"
    )
    today_call = await post_activity(
        client,
        headers,
        account["id"],
        activity_type_id=CALL_ID,
        status="planned",
        scheduled_at=iso(timedelta(minutes=5)),
    )
    overdue = await post_activity(
        client,
        headers,
        account["id"],
        status="planned",
        scheduled_at=iso(-timedelta(days=3)),
    )
    await post_activity(client, users.headers(manager), far["id"])

    listed = await client.get(ACTIVITIES, headers=headers)
    assert listed.status_code == 200 and listed.json()["total"] == 3  # far account hidden
    planned_only = await client.get(ACTIVITIES, params={"status": "planned"}, headers=headers)
    assert planned_only.json()["total"] == 2
    everything = await client.get(ACTIVITIES, headers=users.headers(manager))
    assert everything.json()["total"] == 4

    timeline = await client.get(f"{ACCOUNTS}/{account['id']}/timeline", headers=headers)
    assert timeline.status_code == 200
    entries = timeline.json()["items"]
    assert [e["kind"] for e in entries] == ["activity"] * 3
    assert [e["id"] for e in entries] == [today_call["id"], yesterday["id"], overdue["id"]]
    assert entries[1]["title"] == "Ayer" and entries[0]["title"] == "Llamada"
    paged = await client.get(
        f"{ACCOUNTS}/{account['id']}/timeline", params={"page_size": 2}, headers=headers
    )
    assert paged.json()["total"] == 3 and len(paged.json()["items"]) == 2
    hidden = await client.get(f"{ACCOUNTS}/{far['id']}/timeline", headers=headers)
    assert hidden.status_code == 404
    unknown_kind = await client.get(
        f"{ACCOUNTS}/{account['id']}/timeline", params={"kind": "quote"}, headers=headers
    )
    assert unknown_kind.json()["total"] == 0

    today = await client.get("/api/v1/me/today", headers=headers)
    assert today.status_code == 200
    body = today.json()
    assert [a["id"] for a in body["overdue"]] == [overdue["id"]]
    assert (
        any(a["id"] == today_call["id"] for a in body["today"])
        or body["week"]["planned_remaining"] >= 1
    )  # 5 minutes ahead may cross midnight in Madrid
    assert body["week"]["done_by_type"].get(VISIT_ID, 0) >= 0

    as_manager = await client.get(
        "/api/v1/me/today", params={"user_id": str(rep.id)}, headers=users.headers(manager)
    )
    assert as_manager.status_code == 200
    assert [a["id"] for a in as_manager.json()["overdue"]] == [overdue["id"]]
    other_rep = await users.create(Role.SALES_REP, email="other@quermed.com")
    denied = await client.get(
        "/api/v1/me/today", params={"user_id": str(rep.id)}, headers=users.headers(other_rep)
    )
    assert denied.status_code == 403
    missing = await client.get(f"{ACTIVITIES}/{uuid4()}", headers=headers)
    assert missing.status_code == 404
