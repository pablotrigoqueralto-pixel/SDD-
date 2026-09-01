"""ORM model: notifications (the per-user inbox of what somebody else assigned you)."""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Index, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.db.models.base import Base, IdentifiedMixin


class NotificationModel(IdentifiedMixin, Base):
    __tablename__ = "notifications"
    # The only way this table is ever read: my unread, newest first.
    __table_args__ = (
        Index("ix_notifications_inbox", "user_id", "read_at", text("created_at DESC")),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    kind: Mapped[str] = mapped_column(Text, nullable=False)
    entity_type: Mapped[str] = mapped_column(Text, nullable=False)
    entity_id: Mapped[UUID | None] = mapped_column(nullable=True)
    # The notice still reads correctly when the person who caused it is gone.
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    # A snapshot of what the line renders, not a live join: a notice describes what was
    # done to you then, and must survive a later rename of the record it points at.
    payload: Mapped[dict[str, Any]] = mapped_column(
        JSONB, nullable=False, default=dict, server_default=text("'{}'::jsonb")
    )
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
