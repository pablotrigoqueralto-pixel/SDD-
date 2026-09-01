"""Notifications: what somebody else put on your plate.

A notice is personal, gets read and then leaves the screen — which is exactly what the
audit log must never do, so the two live apart.
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.domain.shared.audit import JsonValue


class NotificationKind(StrEnum):
    """The four events, all of them "another person assigned this to you"."""

    ACTIVITY_ASSIGNED = "activity_assigned"
    ACTIVITY_ATTENDING = "activity_attending"
    ACCOUNT_ASSIGNED = "account_assigned"
    OPPORTUNITY_ASSIGNED = "opportunity_assigned"


@dataclass(frozen=True)
class Notification:
    id: UUID
    user_id: UUID
    kind: NotificationKind
    entity_type: str
    entity_id: UUID | None
    actor_id: UUID | None
    # A snapshot of what the line renders, taken when the event happened: a notice
    # describes what was done to you then, not what the record looks like now.
    payload: dict[str, JsonValue] = field(default_factory=dict)
    read_at: datetime | None = None
    created_at: datetime | None = None
    actor_name: str | None = None
