from datetime import date, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.application.activities.queries import (
    ActivityView,
    StageChangeView,
    TimelineEntry,
    TodayResult,
)
from app.domain.activities.entities import ActivityOutcome, ActivityStatus
from app.schemas.catalogue import Price
from app.schemas.opportunities import OpportunitySummaryRead


class NextActionWrite(BaseModel):
    activity_type_id: UUID
    scheduled_at: datetime
    subject: str | None = Field(default=None, max_length=120)


class ContactNameRead(BaseModel):
    id: UUID
    name: str


class ActivityRead(BaseModel):
    id: UUID
    account_id: UUID
    account_name: str
    activity_type_id: UUID
    activity_type_name: str
    owner_id: UUID
    owner_name: str
    status: ActivityStatus
    scheduled_at: datetime
    done_at: datetime | None
    duration_minutes: int | None
    outcome: ActivityOutcome | None
    subject: str | None
    notes: str | None
    cancel_reason: str | None
    opportunity_id: UUID | None
    opportunity_name: str | None
    contact_ids: list[UUID]
    contacts: list[ContactNameRead]
    next_activity_id: UUID | None
    version: int
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_view(cls, view: ActivityView, next_activity_id: UUID | None = None) -> "ActivityRead":
        activity = view.activity
        return cls(
            id=activity.id,
            account_id=activity.account_id,
            account_name=view.account_name,
            activity_type_id=activity.activity_type_id,
            activity_type_name=view.activity_type_name,
            owner_id=activity.owner_id,
            owner_name=view.owner_name,
            status=activity.status,
            scheduled_at=activity.scheduled_at,
            done_at=activity.done_at,
            duration_minutes=activity.duration_minutes,
            outcome=activity.outcome,
            subject=activity.subject,
            notes=activity.notes,
            cancel_reason=activity.cancel_reason,
            opportunity_id=activity.opportunity_id,
            opportunity_name=view.opportunity_name,
            contact_ids=sorted(activity.contact_ids, key=str),
            contacts=[ContactNameRead(id=c.id, name=c.name) for c in view.contacts],
            next_activity_id=next_activity_id or view.next_activity_id,
            version=activity.version,
            created_at=activity.created_at,
            updated_at=activity.updated_at,
        )


class _ActivityDetails(BaseModel):
    contact_ids: list[UUID] | None = None
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    outcome: ActivityOutcome | None = None
    subject: str | None = Field(default=None, max_length=120)
    notes: str | None = Field(default=None, max_length=4000)


DETAIL_KEYS = frozenset({"contact_ids", "duration_minutes", "outcome", "subject", "notes"})


class ActivityCreate(_ActivityDetails):
    account_id: UUID
    activity_type_id: UUID
    opportunity_id: UUID | None = None
    status: ActivityStatus = ActivityStatus.DONE
    scheduled_at: datetime | None = None
    owner_id: UUID | None = None
    next_action: NextActionWrite | None = None

    def details(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if k in DETAIL_KEYS and v is not None}


class ActivityUpdate(_ActivityDetails):
    activity_type_id: UUID | None = None
    opportunity_id: UUID | None = None

    def changes(self) -> dict[str, Any]:
        return {
            key: getattr(self, key)
            for key in self.model_fields_set
            if key in DETAIL_KEYS or key in ("activity_type_id", "opportunity_id")
        }


class ActivityComplete(BaseModel):
    done_at: datetime | None = None
    outcome: ActivityOutcome | None = None
    notes: str | None = Field(default=None, max_length=4000)
    duration_minutes: int | None = Field(default=None, ge=1, le=1440)
    next_action: NextActionWrite | None = None


class ActivityCancel(BaseModel):
    reason: str = Field(max_length=200)


class ActivityReschedule(BaseModel):
    scheduled_at: datetime


class StageChangeRead(BaseModel):
    opportunity_id: UUID
    opportunity_name: str
    from_stage_name: str | None
    to_stage_name: str
    actor_name: str | None
    amount: Price
    is_won: bool
    is_lost: bool

    @classmethod
    def from_view(cls, view: StageChangeView) -> "StageChangeRead":
        return cls(
            opportunity_id=view.opportunity_id,
            opportunity_name=view.opportunity_name,
            from_stage_name=view.from_stage_name,
            to_stage_name=view.to_stage_name,
            actor_name=view.actor_name,
            amount=view.amount,
            is_won=view.is_won,
            is_lost=view.is_lost,
        )


class TimelineEntryRead(BaseModel):
    id: UUID
    kind: str
    occurred_at: datetime
    title: str
    activity: ActivityRead | None = None
    stage_change: StageChangeRead | None = None

    @classmethod
    def from_entry(cls, entry: TimelineEntry) -> "TimelineEntryRead":
        return cls(
            id=entry.id,
            kind=entry.kind,
            occurred_at=entry.occurred_at,
            title=entry.title,
            activity=ActivityRead.from_view(entry.activity) if entry.activity else None,
            stage_change=(
                StageChangeRead.from_view(entry.stage_change) if entry.stage_change else None
            ),
        )


class WeekSummaryRead(BaseModel):
    done_by_type: dict[UUID, int]
    planned_remaining: int


class TodayRead(BaseModel):
    date: date
    today: list[ActivityRead]
    overdue: list[ActivityRead]
    week: WeekSummaryRead
    tenders_due: list[OpportunitySummaryRead] = Field(default_factory=list)
    at_risk: list[OpportunitySummaryRead] = Field(default_factory=list)

    @classmethod
    def from_result(cls, result: TodayResult) -> "TodayRead":
        return cls(
            date=result.date,
            today=[ActivityRead.from_view(v) for v in result.today],
            overdue=[ActivityRead.from_view(v) for v in result.overdue],
            week=WeekSummaryRead(
                done_by_type=result.week.done_by_type,
                planned_remaining=result.week.planned_remaining,
            ),
        )
