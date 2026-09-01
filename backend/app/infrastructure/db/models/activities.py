"""ORM models: activities and activity_contacts."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    SmallInteger,
    Text,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.activities.entities import ActivityOutcome, ActivityStatus
from app.infrastructure.db.models.base import (
    Base,
    IdentifiedMixin,
    TimestampedMixin,
    VersionedMixin,
)

STATUS_ENUM = Enum(
    ActivityStatus, name="activities_status_enum", values_callable=lambda e: [m.value for m in e]
)
OUTCOME_ENUM = Enum(
    ActivityOutcome,
    name="activities_outcome_enum",
    values_callable=lambda e: [m.value for m in e],
)


class ActivityModel(IdentifiedMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "activities"
    __table_args__ = (
        CheckConstraint(
            "status <> 'done' OR done_at IS NOT NULL", name="ck_activities_done_requires_done_at"
        ),
        CheckConstraint(
            "status <> 'cancelled' OR cancel_reason IS NOT NULL",
            name="ck_activities_cancelled_requires_reason",
        ),
        CheckConstraint("outcome IS NULL OR status = 'done'", name="ck_activities_outcome_done"),
        CheckConstraint(
            "duration_minutes IS NULL OR (duration_minutes BETWEEN 1 AND 1440)",
            name="ck_activities_duration_range",
        ),
        Index("ix_activities_account_timeline", "account_id", text("scheduled_at DESC")),
        Index("ix_activities_owner_agenda", "owner_id", "status", "scheduled_at"),
        Index("ix_activities_activity_type_id", "activity_type_id"),
        Index("ix_activities_status", "status"),
        Index("ix_activities_opportunity_id", "opportunity_id"),
    )

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    opportunity_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("opportunities.id", ondelete="SET NULL"), nullable=True
    )
    activity_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("activity_types.id", ondelete="RESTRICT"), nullable=False
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    status: Mapped[ActivityStatus] = mapped_column(STATUS_ENUM, nullable=False)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    done_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    duration_minutes: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    outcome: Mapped[ActivityOutcome | None] = mapped_column(OUTCOME_ENUM, nullable=True)
    subject: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    cancel_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    contact_links: Mapped[list["ActivityContactModel"]] = relationship(
        cascade="all, delete-orphan", lazy="raise", passive_deletes=True
    )
    attendee_links: Mapped[list["ActivityAttendeeModel"]] = relationship(
        cascade="all, delete-orphan", lazy="raise", passive_deletes=True
    )


class ActivityContactModel(Base):
    __tablename__ = "activity_contacts"

    activity_id: Mapped[UUID] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True
    )
    contact_id: Mapped[UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="RESTRICT"), primary_key=True
    )


class ActivityAttendeeModel(Base):
    """Quermed colleagues coming along — the centre's people live in activity_contacts."""

    __tablename__ = "activity_attendees"
    __table_args__ = (Index("ix_activity_attendees_user_id", "user_id"),)

    activity_id: Mapped[UUID] = mapped_column(
        ForeignKey("activities.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), primary_key=True
    )
