"""Outbound mail records for quote sending."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from uuid import UUID

from app.domain.shared.ids import new_id


class OutboxStatus(StrEnum):
    SENT = "sent"
    FAILED = "failed"
    SKIPPED = "skipped"


@dataclass(frozen=True)
class MailRecipient:
    email: str
    name: str | None = None


@dataclass
class OutboxEntry:
    quote_id: UUID
    recipients: list[MailRecipient]
    subject: str
    body: str
    status: OutboxStatus
    error: str | None = None
    sent_at: datetime | None = None
    created_at: datetime | None = None
    id: UUID = field(default_factory=new_id)
