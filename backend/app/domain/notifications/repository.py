"""Repository protocol for the per-user notification inbox."""

from typing import Protocol
from uuid import UUID

from app.domain.notifications.entities import Notification


class NotificationRepository(Protocol):
    async def unread_for(self, user_id: UUID, *, limit: int) -> list[Notification]: ...

    async def unread_count(self, user_id: UUID) -> int: ...

    async def mark_read(self, notification_id: UUID, *, user_id: UUID) -> bool: ...

    async def mark_all_read(self, user_id: UUID) -> None: ...


class NotificationWriter(Protocol):
    async def write(self, notifications: list[Notification]) -> None: ...
