"""In-memory notification inbox for unit tests."""

from copy import deepcopy
from datetime import UTC, datetime
from uuid import UUID

from app.domain.notifications.entities import Notification


class InMemoryNotificationRepository:
    def __init__(self) -> None:
        self.rows: list[Notification] = []

    async def unread_for(self, user_id: UUID, *, limit: int) -> list[Notification]:
        unread = [n for n in self.rows if n.user_id == user_id and n.read_at is None]
        unread.sort(key=lambda n: (n.created_at or datetime.min, n.id), reverse=True)
        return [deepcopy(n) for n in unread[:limit]]

    async def unread_count(self, user_id: UUID) -> int:
        return sum(1 for n in self.rows if n.user_id == user_id and n.read_at is None)

    async def mark_read(self, notification_id: UUID, *, user_id: UUID) -> bool:
        for index, row in enumerate(self.rows):
            if row.id == notification_id and row.user_id == user_id:
                if row.read_at is None:
                    self.rows[index] = replace_read_at(row)
                return True
        return False

    async def mark_all_read(self, user_id: UUID) -> None:
        self.rows = [
            replace_read_at(row) if row.user_id == user_id and row.read_at is None else row
            for row in self.rows
        ]


def replace_read_at(row: Notification) -> Notification:
    from dataclasses import replace

    return replace(row, read_at=datetime.now(UTC))
