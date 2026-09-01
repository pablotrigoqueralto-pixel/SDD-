"""The inbox endpoints: own notices only, read and gone."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.notifications.entities import Notification, NotificationKind
from app.domain.shared.ids import new_id
from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.repositories.notifications import SqlAlchemyNotificationWriter
from app.infrastructure.db.seed import reference_id, run_seed
from tests.integration.api.accounts_helpers import (
    ACCOUNTS,
    VASCULAR_ID,
    create_account,
    if_match,
)
from tests.integration.api.conftest import Users

pytestmark = pytest.mark.integration
NOTIFICATIONS = "/api/v1/notifications"
VISIT_ID = str(reference_id("activity_types", "visit"))


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


async def give(session: AsyncSession, user: User, actor: User, count: int = 1) -> None:
    await SqlAlchemyNotificationWriter(session).write(
        [
            Notification(
                id=new_id(),
                user_id=user.id,
                kind=NotificationKind.ACTIVITY_ASSIGNED,
                entity_type="activity",
                entity_id=new_id(),
                actor_id=actor.id,
                payload={"subject": f"Visita {index}", "account_name": "Clínica"},
            )
            for index in range(count)
        ]
    )


async def test_reads_own_unread_with_the_count(
    client: AsyncClient, users: Users, session: AsyncSession
) -> None:
    rep = await users.create(Role.SALES_REP, email="rep-notif@quermed.com")
    manager = await users.create(Role.SALES_MANAGER, email="mgr-notif@quermed.com")
    await give(session, rep, manager, count=3)

    response = await client.get(NOTIFICATIONS, headers=users.headers(rep))

    assert response.status_code == 200, response.text
    body = response.json()
    assert body["unread_count"] == 3
    assert len(body["items"]) == 3
    assert body["items"][0]["actor_name"] == manager.full_name
    assert body["items"][0]["payload"]["account_name"] == "Clínica"

    # A colleague's inbox is untouched and invisible.
    other = await client.get(NOTIFICATIONS, headers=users.headers(manager))
    assert other.json() == {"items": [], "unread_count": 0}


async def test_nobody_reads_another_inbox(
    client: AsyncClient, users: Users, session: AsyncSession, admin_headers: dict[str, str]
) -> None:
    rep = await users.create(Role.SALES_REP, email="rep-private@quermed.com")
    manager = await users.create(Role.SALES_MANAGER, email="mgr-private@quermed.com")
    await give(session, rep, manager, count=2)

    # Even an admin asking for somebody else gets their own inbox, not the rep's.
    peek = await client.get(NOTIFICATIONS, params={"user_id": str(rep.id)}, headers=admin_headers)

    assert peek.status_code == 200
    assert peek.json()["unread_count"] == 0


async def test_marking_read_one_and_all(
    client: AsyncClient, users: Users, session: AsyncSession
) -> None:
    rep = await users.create(Role.SALES_REP, email="rep-read@quermed.com")
    manager = await users.create(Role.SALES_MANAGER, email="mgr-read@quermed.com")
    await give(session, rep, manager, count=3)
    headers = users.headers(rep)
    listed = (await client.get(NOTIFICATIONS, headers=headers)).json()

    one = await client.post(f"{NOTIFICATIONS}/{listed['items'][0]['id']}/read", headers=headers)
    assert one.status_code == 200
    assert one.json()["unread_count"] == 2

    # Marking it again is idempotent.
    again = await client.post(f"{NOTIFICATIONS}/{listed['items'][0]['id']}/read", headers=headers)
    assert again.status_code == 200 and again.json()["unread_count"] == 2

    everything = await client.post(f"{NOTIFICATIONS}/read-all", headers=headers)
    assert everything.status_code == 200
    assert everything.json() == {"items": [], "unread_count": 0}


async def test_marking_someone_elses_notice_is_a_404(
    client: AsyncClient, users: Users, session: AsyncSession
) -> None:
    """404, never 403: nobody should learn that another user's notice exists."""
    rep = await users.create(Role.SALES_REP, email="rep-404@quermed.com")
    intruder = await users.create(Role.SALES_REP, email="intruder@quermed.com")
    manager = await users.create(Role.SALES_MANAGER, email="mgr-404@quermed.com")
    await give(session, rep, manager)
    mine = (await client.get(NOTIFICATIONS, headers=users.headers(rep))).json()["items"][0]

    refused = await client.post(
        f"{NOTIFICATIONS}/{mine['id']}/read", headers=users.headers(intruder)
    )

    assert refused.status_code == 404
    assert refused.json()["code"] == "not_found"
    still = await client.get(NOTIFICATIONS, headers=users.headers(rep))
    assert still.json()["unread_count"] == 1


async def unread_kinds(client: AsyncClient, headers: dict[str, str]) -> list[str]:
    body = (await client.get(NOTIFICATIONS, headers=headers)).json()
    return [item["kind"] for item in body["items"]]


async def test_the_four_events_notify_the_person_they_land_on(
    client: AsyncClient, users: Users, centro: Territory, admin_headers: dict[str, str]
) -> None:
    rep = await users.create(
        Role.SALES_REP,
        email="rep-events@quermed.com",
        territory_ids=frozenset({centro.id}),
        division_ids=frozenset({VASCULAR_ID}),
    )
    rep_headers = users.headers(rep)
    account = await create_account(client, admin_headers, name="Centro Avisos")

    # 1) A centre assigned to somebody else. The territory's smart default already gave
    # this centre to `rep`, so hand it to a colleague: an assignment that changes nothing
    # notifies nobody, which is the behaviour we want.
    colleague = await users.create(
        Role.SALES_REP,
        email="colleague-events@quermed.com",
        territory_ids=frozenset({centro.id}),
        division_ids=frozenset({VASCULAR_ID}),
    )
    assigned = await client.put(
        f"{ACCOUNTS}/{account['id']}/assignment",
        json={"owner_id": str(colleague.id)},
        headers={**admin_headers, **if_match(account["version"])},
    )
    assert assigned.status_code == 200, assigned.text

    # 2) An activity created with them as owner, 3) with them as attendee.
    visit = await client.post(
        "/api/v1/activities",
        json={
            "account_id": account["id"],
            "activity_type_id": VISIT_ID,
            "owner_id": str(rep.id),
        },
        headers=admin_headers,
    )
    assert visit.status_code == 201, visit.text
    invited = await client.post(
        "/api/v1/activities",
        json={
            "account_id": account["id"],
            "activity_type_id": VISIT_ID,
            "attendee_ids": [str(colleague.id)],
        },
        headers=admin_headers,
    )
    assert invited.status_code == 201, invited.text

    assert await unread_kinds(client, rep_headers) == ["activity_assigned"]
    assert sorted(await unread_kinds(client, users.headers(colleague))) == [
        "account_assigned",
        "activity_attending",
    ]

    # The actor never notifies themselves.
    assert await unread_kinds(client, admin_headers) == []


async def test_a_failed_write_leaves_no_notice(
    client: AsyncClient, users: Users, centro: Territory, admin_headers: dict[str, str]
) -> None:
    """A notice must never announce something that was rolled back."""
    rep = await users.create(
        Role.SALES_REP,
        email="rep-rollback@quermed.com",
        territory_ids=frozenset({centro.id}),
        division_ids=frozenset({VASCULAR_ID}),
    )
    account = await create_account(client, admin_headers, name="Centro Rollback")

    # The activity is refused because one attendee cannot see the centre; the notice that
    # would have gone to the valid owner must go with it.
    outsider = await users.create(Role.SALES_REP, email="outsider-rollback@quermed.com")
    refused = await client.post(
        "/api/v1/activities",
        json={
            "account_id": account["id"],
            "activity_type_id": VISIT_ID,
            "owner_id": str(rep.id),
            "attendee_ids": [str(outsider.id)],
        },
        headers=admin_headers,
    )

    assert refused.status_code == 422
    assert (await client.get(NOTIFICATIONS, headers=users.headers(rep))).json()["unread_count"] == 0


async def test_the_payload_is_a_snapshot_of_what_happened(
    client: AsyncClient, users: Users, centro: Territory, admin_headers: dict[str, str]
) -> None:
    """A notice describes what was done to you then, not what the record looks like now."""
    rep = await users.create(
        Role.SALES_REP,
        email="rep-snapshot@quermed.com",
        territory_ids=frozenset({centro.id}),
        division_ids=frozenset({VASCULAR_ID}),
    )
    account = await create_account(client, admin_headers, name="Centro Snapshot")
    created = await client.post(
        "/api/v1/activities",
        json={
            "account_id": account["id"],
            "activity_type_id": VISIT_ID,
            "owner_id": str(rep.id),
            "subject": "Visita inicial",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text

    renamed = await client.patch(
        f"/api/v1/activities/{created.json()['id']}",
        json={"subject": "Otra cosa"},
        headers={**admin_headers, **if_match(created.json()["version"])},
    )
    assert renamed.status_code == 200, renamed.text

    notice = (await client.get(NOTIFICATIONS, headers=users.headers(rep))).json()["items"][0]
    assert notice["payload"]["subject"] == "Visita inicial"


async def test_removing_an_attendee_notifies_nobody(
    client: AsyncClient, users: Users, centro: Territory, admin_headers: dict[str, str]
) -> None:
    guest = await users.create(
        Role.SALES_REP,
        email="guest-removed@quermed.com",
        territory_ids=frozenset({centro.id}),
        division_ids=frozenset({VASCULAR_ID}),
    )
    account = await create_account(client, admin_headers, name="Centro Quitado")
    visit = await client.post(
        "/api/v1/activities",
        json={
            "account_id": account["id"],
            "activity_type_id": VISIT_ID,
            "attendee_ids": [str(guest.id)],
        },
        headers=admin_headers,
    )
    assert visit.status_code == 201, visit.text

    removed = await client.patch(
        f"/api/v1/activities/{visit.json()['id']}",
        json={"attendee_ids": []},
        headers={**admin_headers, **if_match(visit.json()["version"])},
    )

    assert removed.status_code == 200, removed.text
    # Still exactly one notice: the invitation was announced, its withdrawal is not news,
    # and the record of what was announced stays.
    inbox = (await client.get(NOTIFICATIONS, headers=users.headers(guest))).json()
    assert inbox["unread_count"] == 1
    assert [n["kind"] for n in inbox["items"]] == ["activity_attending"]
