"""Schemas for the per-user notification inbox."""

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.domain.notifications.entities import Notification, NotificationKind
from app.domain.shared.audit import JsonValue


class NotificationRead(BaseModel):
    id: UUID
    kind: NotificationKind
    entity_type: str
    entity_id: UUID | None
    actor_id: UUID | None
    actor_name: str | None
    payload: dict[str, JsonValue]
    created_at: datetime | None

    @classmethod
    def from_entity(cls, notification: Notification) -> "NotificationRead":
        return cls(
            id=notification.id,
            kind=notification.kind,
            entity_type=notification.entity_type,
            entity_id=notification.entity_id,
            actor_id=notification.actor_id,
            actor_name=notification.actor_name,
            payload=notification.payload,
            created_at=notification.created_at,
        )


class NotificationsRead(BaseModel):
    """One payload for the bell and the block, so they cannot disagree."""

    items: list[NotificationRead]
    unread_count: int
