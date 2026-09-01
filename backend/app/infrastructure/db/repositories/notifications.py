"""The per-user notification inbox: writes queued by the collector, reads for the block."""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.notifications.entities import Notification, NotificationKind
from app.infrastructure.db.models import NotificationModel, UserModel


def notification_to_entity(row: NotificationModel, actor_name: str | None = None) -> Notification:
    return Notification(
        id=row.id,
        user_id=row.user_id,
        kind=NotificationKind(row.kind),
        entity_type=row.entity_type,
        entity_id=row.entity_id,
        actor_id=row.actor_id,
        payload=dict(row.payload or {}),
        read_at=row.read_at,
        created_at=row.created_at,
        actor_name=actor_name,
    )


class SqlAlchemyNotificationWriter:
    """Notices share the transaction with the change that caused them."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def write(self, notifications: list[Notification]) -> None:
        if not notifications:
            return
        self._session.add_all(
            NotificationModel(
                id=notification.id,
                user_id=notification.user_id,
                kind=notification.kind.value,
                entity_type=notification.entity_type,
                entity_id=notification.entity_id,
                actor_id=notification.actor_id,
                payload=notification.payload,
                created_at=notification.created_at or datetime.now(UTC),
            )
            for notification in notifications
        )
        await self._session.flush()


class SqlAlchemyNotificationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def unread_for(self, user_id: UUID, *, limit: int) -> list[Notification]:
        statement = (
            select(NotificationModel, UserModel.full_name)
            .outerjoin(UserModel, UserModel.id == NotificationModel.actor_id)
            .where(NotificationModel.user_id == user_id, NotificationModel.read_at.is_(None))
            # UUIDv7 ids are time-ordered, so the tiebreak is newest-first too: two
            # notices created in the same instant (two attendees at once) must not flip.
            .order_by(NotificationModel.created_at.desc(), NotificationModel.id.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(statement)).all()
        return [notification_to_entity(row[0], row[1]) for row in rows]

    async def unread_count(self, user_id: UUID) -> int:
        total = await self._session.scalar(
            select(func.count())
            .select_from(NotificationModel)
            .where(NotificationModel.user_id == user_id, NotificationModel.read_at.is_(None))
        )
        return int(total or 0)

    async def mark_read(self, notification_id: UUID, *, user_id: UUID) -> bool:
        """False when the notice is not this user's: the caller gets a 404, never a 403 —
        nobody should learn that somebody else's notification exists."""
        owned = await self._session.scalar(
            select(NotificationModel.id).where(
                NotificationModel.id == notification_id, NotificationModel.user_id == user_id
            )
        )
        if owned is None:
            return False
        await self._session.execute(
            update(NotificationModel)
            .where(NotificationModel.id == notification_id, NotificationModel.read_at.is_(None))
            .values(read_at=datetime.now(UTC))
        )
        return True

    async def mark_all_read(self, user_id: UUID) -> None:
        await self._session.execute(
            update(NotificationModel)
            .where(NotificationModel.user_id == user_id, NotificationModel.read_at.is_(None))
            .values(read_at=datetime.now(UTC))
        )
