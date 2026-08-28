"""Read side for activities: enriched views, the account timeline and the rep's day."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.application.shared.pagination import PageParams
from app.domain.activities.entities import Activity, ActivityStatus
from app.infrastructure.db.models import (
    AccountModel,
    ActivityContactModel,
    ActivityModel,
    ActivityTypeModel,
    ContactModel,
    UserModel,
)
from app.infrastructure.db.repositories.activities import activity_to_entity

BUSINESS_TIMEZONE = ZoneInfo("Europe/Madrid")
TIMELINE_KIND_ACTIVITY = "activity"


@dataclass(frozen=True)
class ContactName:
    id: UUID
    name: str


@dataclass(frozen=True)
class ActivityView:
    """An activity plus the labels every screen shows next to it."""

    activity: Activity
    account_name: str
    owner_name: str
    activity_type_name: str
    contacts: list[ContactName] = field(default_factory=list)
    next_activity_id: UUID | None = None


@dataclass(frozen=True)
class TimelineEntry:
    id: UUID
    kind: str
    occurred_at: datetime
    title: str
    activity: ActivityView


@dataclass(frozen=True)
class TimelineFilters:
    kind: str | None = None
    activity_type_id: UUID | None = None
    status: ActivityStatus | None = None


@dataclass(frozen=True)
class TimelineListResult:
    items: list[TimelineEntry]
    total: int


@dataclass(frozen=True)
class ActivityFilters:
    account_id: UUID | None = None
    owner_id: UUID | None = None
    status: ActivityStatus | None = None
    activity_type_id: UUID | None = None
    occurred_from: datetime | None = None
    occurred_to: datetime | None = None


@dataclass(frozen=True)
class ActivityListResult:
    items: list[ActivityView]
    total: int


@dataclass(frozen=True)
class WeekSummary:
    done_by_type: dict[UUID, int]
    planned_remaining: int


@dataclass(frozen=True)
class TodayResult:
    date: date
    today: list[ActivityView]
    overdue: list[ActivityView]
    week: WeekSummary


ACTIVITY_SORT_FIELDS: set[str] = {"scheduled_at"}
ACTIVITY_DEFAULT_SORT = "-scheduled_at"

_OWNER = aliased(UserModel)


def occurred_at_expression() -> Any:
    """`done_at` for done activities, `scheduled_at` otherwise."""
    return case(
        (
            (ActivityModel.status == ActivityStatus.DONE) & ActivityModel.done_at.isnot(None),
            ActivityModel.done_at,
        ),
        else_=ActivityModel.scheduled_at,
    )


def _base_select() -> Select[Any]:
    return (
        select(ActivityModel, AccountModel.name, _OWNER.full_name, ActivityTypeModel.name_es)
        .join(AccountModel, AccountModel.id == ActivityModel.account_id)
        .join(_OWNER, _OWNER.id == ActivityModel.owner_id)
        .join(ActivityTypeModel, ActivityTypeModel.id == ActivityModel.activity_type_id)
        .options(selectinload(ActivityModel.contact_links))
    )


async def _contact_names(
    session: AsyncSession, activity_ids: Sequence[UUID]
) -> dict[UUID, list[ContactName]]:
    if not activity_ids:
        return {}
    statement = (
        select(
            ActivityContactModel.activity_id,
            ContactModel.id,
            ContactModel.first_name,
            ContactModel.last_name,
        )
        .join(ContactModel, ContactModel.id == ActivityContactModel.contact_id)
        .where(ActivityContactModel.activity_id.in_(list(activity_ids)))
        .order_by(ContactModel.last_name, ContactModel.first_name)
    )
    names: dict[UUID, list[ContactName]] = defaultdict(list)
    for activity_id, contact_id, first, last in (await session.execute(statement)).all():
        names[activity_id].append(ContactName(contact_id, f"{first} {last}".strip()))
    return names


async def _views(session: AsyncSession, statement: Select[Any]) -> list[ActivityView]:
    rows = (await session.execute(statement)).all()
    names = await _contact_names(session, [row[0].id for row in rows])
    return [
        ActivityView(
            activity=activity_to_entity(row[0]),
            account_name=row[1],
            owner_name=row[2],
            activity_type_name=row[3],
            contacts=names.get(row[0].id, []),
        )
        for row in rows
    ]


async def load_activity_view(session: AsyncSession, activity_id: UUID) -> ActivityView | None:
    views = await _views(session, _base_select().where(ActivityModel.id == activity_id))
    return views[0] if views else None


class ActivityQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_page(
        self, params: PageParams, filters: ActivityFilters, account_ids: Select[Any] | None
    ) -> ActivityListResult:
        """`account_ids` is the scoped account id subquery (None = unrestricted)."""
        base = _base_select()
        if account_ids is not None:
            base = base.where(ActivityModel.account_id.in_(account_ids))
        if filters.account_id:
            base = base.where(ActivityModel.account_id == filters.account_id)
        if filters.owner_id:
            base = base.where(ActivityModel.owner_id == filters.owner_id)
        if filters.status:
            base = base.where(ActivityModel.status == filters.status)
        if filters.activity_type_id:
            base = base.where(ActivityModel.activity_type_id == filters.activity_type_id)
        if filters.occurred_from:
            base = base.where(ActivityModel.scheduled_at >= filters.occurred_from)
        if filters.occurred_to:
            base = base.where(ActivityModel.scheduled_at <= filters.occurred_to)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        descending = any(f.descending for f in params.sort)
        order = ActivityModel.scheduled_at.desc() if descending else ActivityModel.scheduled_at
        statement = (
            base.order_by(order, ActivityModel.id.desc()).offset(params.offset).limit(params.limit)
        )
        return ActivityListResult(
            items=await _views(self._session, statement), total=int(total or 0)
        )


class TimelineQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_page(
        self, account_id: UUID, params: PageParams, filters: TimelineFilters
    ) -> TimelineListResult:
        if filters.kind not in (None, TIMELINE_KIND_ACTIVITY):
            return TimelineListResult(items=[], total=0)  # unknown kinds are additive
        base = _base_select().where(ActivityModel.account_id == account_id)
        if filters.activity_type_id:
            base = base.where(ActivityModel.activity_type_id == filters.activity_type_id)
        if filters.status:
            base = base.where(ActivityModel.status == filters.status)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        statement = (
            base.order_by(occurred_at_expression().desc(), ActivityModel.id.desc())
            .offset(params.offset)
            .limit(params.limit)
        )
        views = await _views(self._session, statement)
        return TimelineListResult(
            items=[
                TimelineEntry(
                    id=view.activity.id,
                    kind=TIMELINE_KIND_ACTIVITY,
                    occurred_at=view.activity.occurred_at,
                    title=view.activity.subject or view.activity_type_name,
                    activity=view,
                )
                for view in views
            ],
            total=int(total or 0),
        )


def day_bounds(now: datetime) -> tuple[datetime, datetime, date]:
    """Start/end of the business day in Europe/Madrid that contains `now`."""
    local = now.astimezone(BUSINESS_TIMEZONE)
    start = datetime.combine(local.date(), time.min, tzinfo=BUSINESS_TIMEZONE)
    return start, start + timedelta(days=1), local.date()


def week_bounds(now: datetime) -> tuple[datetime, datetime]:
    local = now.astimezone(BUSINESS_TIMEZONE)
    monday = local.date() - timedelta(days=local.weekday())
    start = datetime.combine(monday, time.min, tzinfo=BUSINESS_TIMEZONE)
    return start, start + timedelta(days=7)


class TodayQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def for_user(self, user_id: UUID, *, now: datetime) -> TodayResult:
        day_start, day_end, today = day_bounds(now)
        week_start, week_end = week_bounds(now)
        planned = _base_select().where(
            ActivityModel.owner_id == user_id, ActivityModel.status == ActivityStatus.PLANNED
        )
        today_views = await _views(
            self._session,
            planned.where(
                ActivityModel.scheduled_at >= day_start, ActivityModel.scheduled_at < day_end
            ).order_by(ActivityModel.scheduled_at),
        )
        overdue_views = await _views(
            self._session,
            planned.where(ActivityModel.scheduled_at < day_start).order_by(
                ActivityModel.scheduled_at
            ),
        )
        done_rows = (
            await self._session.execute(
                select(ActivityModel.activity_type_id, func.count())
                .where(
                    ActivityModel.owner_id == user_id,
                    ActivityModel.status == ActivityStatus.DONE,
                    ActivityModel.done_at >= week_start,
                    ActivityModel.done_at < week_end,
                )
                .group_by(ActivityModel.activity_type_id)
            )
        ).all()
        planned_remaining = await self._session.scalar(
            select(func.count()).where(
                ActivityModel.owner_id == user_id,
                ActivityModel.status == ActivityStatus.PLANNED,
                ActivityModel.scheduled_at >= day_end,
                ActivityModel.scheduled_at < week_end,
            )
        )
        return TodayResult(
            date=today,
            today=today_views,
            overdue=overdue_views,
            week=WeekSummary(
                done_by_type={type_id: int(count) for type_id, count in done_rows},
                planned_remaining=int(planned_remaining or 0),
            ),
        )
