"""The notification inbox: written with the change that caused it, read unread-first."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.unit_of_work import NotificationCollector
from app.domain.notifications.entities import NotificationKind
from app.infrastructure.db.models import NotificationModel
from app.infrastructure.db.repositories.notifications import (
    SqlAlchemyNotificationRepository,
    SqlAlchemyNotificationWriter,
)
from tests.integration.repositories.conftest import World

pytestmark = pytest.mark.integration


async def collect(world: World, **overrides: object) -> NotificationCollector:
    collector = NotificationCollector()
    collector.notify(
        user_id=overrides.get("user_id", world.rep.id),  # type: ignore[arg-type]
        kind=NotificationKind.ACTIVITY_ASSIGNED,
        entity_type="activity",
        entity_id=None,
        actor_id=overrides.get("actor_id", world.manager.id),  # type: ignore[arg-type]
        payload={"subject": "Visita", "account_name": "Clínica"},
    )
    return collector


async def test_unread_reads_newest_first_and_marking_leaves_the_row(
    session: AsyncSession, world: World
) -> None:
    writer = SqlAlchemyNotificationWriter(session)
    inbox = SqlAlchemyNotificationRepository(session)

    first = NotificationCollector()
    first.notify(
        user_id=world.rep.id,
        kind=NotificationKind.ACCOUNT_ASSIGNED,
        entity_type="account",
        entity_id=None,
        actor_id=world.manager.id,
        payload={"account_name": "Uno"},
    )
    second = NotificationCollector()
    second.notify(
        user_id=world.rep.id,
        kind=NotificationKind.ACTIVITY_ASSIGNED,
        entity_type="activity",
        entity_id=None,
        actor_id=world.manager.id,
        payload={"subject": "Dos"},
    )
    await writer.write(first.drain())
    await writer.write(second.drain())

    unread = await inbox.unread_for(world.rep.id, limit=20)
    assert [n.payload.get("subject") or n.payload.get("account_name") for n in unread] == [
        "Dos",
        "Uno",
    ]
    assert unread[0].actor_name == world.manager.full_name
    assert await inbox.unread_count(world.rep.id) == 2

    assert await inbox.mark_read(unread[0].id, user_id=world.rep.id) is True
    assert await inbox.unread_count(world.rep.id) == 1
    # Read means gone from the block, never deleted: the row is still there with its date.
    row = await session.get(NotificationModel, unread[0].id)
    assert row is not None and row.read_at is not None

    # Marking it again is idempotent and keeps the first date.
    first_read_at = row.read_at
    assert await inbox.mark_read(unread[0].id, user_id=world.rep.id) is True
    await session.refresh(row)
    assert row.read_at == first_read_at

    await inbox.mark_all_read(world.rep.id)
    assert await inbox.unread_count(world.rep.id) == 0
    assert await inbox.unread_for(world.rep.id, limit=20) == []


async def test_marking_someone_elses_notice_is_refused(session: AsyncSession, world: World) -> None:
    writer = SqlAlchemyNotificationWriter(session)
    inbox = SqlAlchemyNotificationRepository(session)
    collector = await collect(world)
    await writer.write(collector.drain())
    mine = (await inbox.unread_for(world.rep.id, limit=20))[0]

    assert await inbox.mark_read(mine.id, user_id=world.other_rep.id) is False
    assert await inbox.unread_count(world.rep.id) == 1


async def test_the_actor_never_notifies_themselves(world: World) -> None:
    collector = NotificationCollector()

    nothing = collector.notify(
        user_id=world.rep.id,
        kind=NotificationKind.ACTIVITY_ASSIGNED,
        entity_type="activity",
        entity_id=None,
        actor_id=world.rep.id,
        payload={},
    )

    assert nothing is None
    assert collector.drain() == []
