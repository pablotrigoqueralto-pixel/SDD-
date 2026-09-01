"""Activity aggregate: one record per interaction with an explicit lifecycle."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.domain.activities.errors import (
    ActivityLockedError,
    CancelReasonRequiredError,
    InvalidActivityTransitionError,
    NextActionInPastError,
    NoteCannotBePlannedError,
    OwnerCannotAttendError,
)
from app.domain.shared.errors import ValidationFailedError
from app.domain.shared.ids import new_id
from app.domain.users.entities import User
from app.domain.users.roles import Role

EDIT_WINDOW = timedelta(days=7)
MAX_SUBJECT_LENGTH = 120
MIN_DURATION = 1
MAX_DURATION = 1440


class ActivityStatus(StrEnum):
    PLANNED = "planned"
    DONE = "done"
    CANCELLED = "cancelled"


class ActivityOutcome(StrEnum):
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    NO_CONTACT = "no_contact"


@dataclass(frozen=True)
class ActivityKind:
    """The slice of an activity type the aggregate needs (looked up by the service)."""

    id: UUID
    is_note: bool
    counts_as_contact: bool


@dataclass(frozen=True)
class NextAction:
    activity_type_id: UUID
    scheduled_at: datetime
    subject: str | None = None

    def validate(self, *, now: datetime, is_note: bool) -> None:
        if self.scheduled_at <= now:
            raise NextActionInPastError()
        if is_note:
            raise NoteCannotBePlannedError()


DETAIL_FIELDS: frozenset[str] = frozenset(
    {
        "activity_type_id",
        "contact_ids",
        "attendee_ids",
        "duration_minutes",
        "outcome",
        "subject",
        "notes",
    }
)


@dataclass
class Activity:
    id: UUID
    account_id: UUID
    activity_type_id: UUID
    owner_id: UUID
    created_by: UUID
    status: ActivityStatus
    scheduled_at: datetime
    done_at: datetime | None = None
    duration_minutes: int | None = None
    outcome: ActivityOutcome | None = None
    subject: str | None = None
    notes: str | None = None
    cancel_reason: str | None = None
    contact_ids: frozenset[UUID] = field(default_factory=frozenset)
    # Quermed colleagues coming along. The centre's people stay in contact_ids: one
    # table per meaning, so no query has to guess which half it wants.
    attendee_ids: frozenset[UUID] = field(default_factory=frozenset)
    opportunity_id: UUID | None = None
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # --- creation ---------------------------------------------------------

    @classmethod
    def record_done(
        cls,
        *,
        account_id: UUID,
        kind: ActivityKind,
        owner_id: UUID,
        created_by: UUID,
        now: datetime,
        scheduled_at: datetime | None = None,
        details: Mapping[str, Any] | None = None,
    ) -> "Activity":
        """The 30-second path: it happened (by default right now) and it is done."""
        when = scheduled_at or now
        activity = cls(
            id=new_id(),
            account_id=account_id,
            activity_type_id=kind.id,
            owner_id=owner_id,
            created_by=created_by,
            status=ActivityStatus.DONE,
            scheduled_at=when,
            done_at=when if scheduled_at else now,
        )
        activity._apply_details(details or {})
        return activity

    @classmethod
    def plan(
        cls,
        *,
        account_id: UUID,
        kind: ActivityKind,
        owner_id: UUID,
        created_by: UUID,
        scheduled_at: datetime,
        details: Mapping[str, Any] | None = None,
    ) -> "Activity":
        if kind.is_note:
            raise NoteCannotBePlannedError()
        activity = cls(
            id=new_id(),
            account_id=account_id,
            activity_type_id=kind.id,
            owner_id=owner_id,
            created_by=created_by,
            status=ActivityStatus.PLANNED,
            scheduled_at=scheduled_at,
        )
        activity._apply_details({k: v for k, v in (details or {}).items() if k != "outcome"})
        return activity

    def follow_up(self, next_action: NextAction, *, now: datetime, is_note: bool) -> "Activity":
        """The planned activity created by "cierro la visita y dejo apuntada la próxima"."""
        next_action.validate(now=now, is_note=is_note)
        follow_up = Activity.plan(
            account_id=self.account_id,
            kind=ActivityKind(
                id=next_action.activity_type_id, is_note=False, counts_as_contact=True
            ),
            owner_id=self.owner_id,
            created_by=self.created_by,
            scheduled_at=next_action.scheduled_at,
            details={"contact_ids": self.contact_ids, "subject": next_action.subject},
        )
        follow_up.opportunity_id = self.opportunity_id
        return follow_up

    # --- lifecycle --------------------------------------------------------

    def complete(
        self,
        *,
        now: datetime,
        done_at: datetime | None = None,
        outcome: ActivityOutcome | None = None,
        notes: str | None = None,
        duration_minutes: int | None = None,
    ) -> None:
        self._require(ActivityStatus.PLANNED, "complete")
        self.status = ActivityStatus.DONE
        self.done_at = done_at or now
        if outcome is not None:
            self.outcome = outcome
        if notes is not None:
            self.notes = _clean(notes)
        if duration_minutes is not None:
            self.duration_minutes = _duration(duration_minutes)

    def cancel(self, reason: str) -> None:
        self._require(ActivityStatus.PLANNED, "cancel")
        cleaned = reason.strip()
        if not cleaned:
            raise CancelReasonRequiredError()
        self.status = ActivityStatus.CANCELLED
        self.cancel_reason = cleaned

    def reschedule(self, scheduled_at: datetime) -> None:
        self._require(ActivityStatus.PLANNED, "reschedule")
        self.scheduled_at = scheduled_at

    def _require(self, expected: ActivityStatus, action: str) -> None:
        if self.status != expected:
            raise InvalidActivityTransitionError(self.status.value, action)

    # --- editing ----------------------------------------------------------

    def ensure_editable(self, actor: User, *, now: datetime) -> None:
        if actor.role in {Role.ADMIN, Role.SALES_MANAGER}:
            return
        if actor.id != self.owner_id or actor.role != Role.SALES_REP:
            raise ActivityLockedError()
        if self.status == ActivityStatus.CANCELLED:
            raise ActivityLockedError()
        if self.status == ActivityStatus.DONE and self.done_at is not None:
            if now - self.done_at > EDIT_WINDOW:
                raise ActivityLockedError()

    def update_details(self, changes: Mapping[str, Any]) -> None:
        self._apply_details({k: v for k, v in changes.items() if k in DETAIL_FIELDS})

    def _apply_details(self, details: Mapping[str, Any]) -> None:
        for key, value in details.items():
            if key not in DETAIL_FIELDS:
                continue
            if key == "contact_ids":
                self.contact_ids = frozenset(value or ())
            elif key == "attendee_ids":
                attendees = frozenset(value or ())
                if self.owner_id in attendees:
                    raise OwnerCannotAttendError()
                self.attendee_ids = attendees
            elif key == "activity_type_id":
                if value is not None:
                    self.activity_type_id = value
            elif key == "duration_minutes":
                self.duration_minutes = None if value is None else _duration(int(value))
            elif key == "outcome":
                self.outcome = None if value is None else ActivityOutcome(value)
            elif key == "subject":
                subject = None if value is None else _clean(str(value))
                self.subject = subject[:MAX_SUBJECT_LENGTH] if subject else None
            elif key == "notes":
                self.notes = None if value is None else _clean(str(value))

    @property
    def occurred_at(self) -> datetime:
        return (
            self.done_at
            if self.status == ActivityStatus.DONE and self.done_at
            else self.scheduled_at
        )

    def snapshot(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "activity_type_id": self.activity_type_id,
            "owner_id": self.owner_id,
            "status": self.status,
            "scheduled_at": self.scheduled_at,
            "done_at": self.done_at,
            "duration_minutes": self.duration_minutes,
            "outcome": self.outcome,
            "subject": self.subject,
            "notes": self.notes,
            "cancel_reason": self.cancel_reason,
            "contact_ids": self.contact_ids,
            "attendee_ids": self.attendee_ids,
            "opportunity_id": self.opportunity_id,
        }


def _clean(value: str) -> str | None:
    cleaned = value.strip()
    return cleaned or None


def _duration(value: int) -> int:
    if value < MIN_DURATION or value > MAX_DURATION:
        raise ValidationFailedError(
            [
                {
                    "field": "duration_minutes",
                    "message": "Duration must be between 1 and 1440 minutes",
                    "code": "duration_invalid",
                }
            ]
        )
    return value
