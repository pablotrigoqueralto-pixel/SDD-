"""Read side for activities: enriched views, the account timeline and the rep's day."""

from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import Select, case, func, literal, select, union_all
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
    OpportunityModel,
    OpportunityStageHistoryModel,
    PipelineStageModel,
    QuoteModel,
    UserModel,
)
from app.infrastructure.db.repositories.activities import activity_to_entity

BUSINESS_TIMEZONE = ZoneInfo("Europe/Madrid")
TIMELINE_KIND_ACTIVITY = "activity"
TIMELINE_KIND_STAGE = "opportunity_stage"
TIMELINE_KIND_CLOSED = "opportunity_closed"
TIMELINE_KIND_QUOTE_SENT = "quote_sent"
TIMELINE_KIND_QUOTE_ACCEPTED = "quote_accepted"
TIMELINE_KIND_QUOTE_REJECTED = "quote_rejected"
TIMELINE_QUOTE_KINDS = {
    TIMELINE_KIND_QUOTE_SENT,
    TIMELINE_KIND_QUOTE_ACCEPTED,
    TIMELINE_KIND_QUOTE_REJECTED,
}
TIMELINE_KINDS = {
    TIMELINE_KIND_ACTIVITY,
    TIMELINE_KIND_STAGE,
    TIMELINE_KIND_CLOSED,
} | TIMELINE_QUOTE_KINDS


def format_eur(amount: "Decimal") -> str:
    """ "24000.00" -> "24.000,00 €" (server-side titles only; screens format client-side)."""
    text = f"{amount:,.2f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".") + " \u20ac"


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
    opportunity_name: str | None = None


@dataclass(frozen=True)
class StageChangeView:
    """A stage-history row with the labels the timeline shows."""

    opportunity_id: UUID
    opportunity_name: str
    from_stage_name: str | None
    to_stage_name: str
    actor_name: str | None
    amount: Decimal
    is_won: bool
    is_lost: bool


@dataclass(frozen=True)
class QuoteEventView:
    """A quote status event with the labels the timeline shows."""

    quote_id: UUID
    display_number: str
    opportunity_id: UUID
    opportunity_name: str
    total: Decimal
    status: str


@dataclass(frozen=True)
class TimelineEntry:
    id: UUID
    kind: str
    occurred_at: datetime
    title: str
    activity: ActivityView | None = None
    stage_change: StageChangeView | None = None
    quote_event: QuoteEventView | None = None


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
    opportunity_id: UUID | None = None
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
        select(
            ActivityModel,
            AccountModel.name,
            _OWNER.full_name,
            ActivityTypeModel.name_es,
            OpportunityModel.name.label("opportunity_name"),
        )
        .join(AccountModel, AccountModel.id == ActivityModel.account_id)
        .join(_OWNER, _OWNER.id == ActivityModel.owner_id)
        .join(ActivityTypeModel, ActivityTypeModel.id == ActivityModel.activity_type_id)
        .outerjoin(OpportunityModel, OpportunityModel.id == ActivityModel.opportunity_id)
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
            opportunity_name=row[4],
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
        if filters.opportunity_id:
            base = base.where(ActivityModel.opportunity_id == filters.opportunity_id)
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
        if filters.kind is not None and filters.kind not in TIMELINE_KINDS:
            return TimelineListResult(items=[], total=0)  # unknown kinds are additive
        include_activities = filters.kind in (None, TIMELINE_KIND_ACTIVITY)
        # Type/status filters only make sense for activities; other entries drop out then.
        activity_only_filters = filters.activity_type_id is not None or filters.status is not None
        include_history = (
            filters.kind in (None, TIMELINE_KIND_STAGE, TIMELINE_KIND_CLOSED)
            and not activity_only_filters
        )
        include_quotes = (
            filters.kind is None or filters.kind in TIMELINE_QUOTE_KINDS
        ) and not activity_only_filters

        sources: list[Select[Any]] = []
        if include_activities:
            activities = select(
                ActivityModel.id.label("item_id"),
                occurred_at_expression().label("occurred_at"),
                literal(TIMELINE_KIND_ACTIVITY).label("kind"),
            ).where(ActivityModel.account_id == account_id)
            if filters.activity_type_id:
                activities = activities.where(
                    ActivityModel.activity_type_id == filters.activity_type_id
                )
            if filters.status:
                activities = activities.where(ActivityModel.status == filters.status)
            sources.append(activities)
        if include_history:
            closed_expression = case(
                (
                    PipelineStageModel.is_won.is_(True) | PipelineStageModel.is_lost.is_(True),
                    literal(TIMELINE_KIND_CLOSED),
                ),
                else_=literal(TIMELINE_KIND_STAGE),
            )
            history = (
                select(
                    OpportunityStageHistoryModel.id.label("item_id"),
                    OpportunityStageHistoryModel.occurred_at.label("occurred_at"),
                    closed_expression.label("kind"),
                )
                .join(
                    OpportunityModel,
                    OpportunityModel.id == OpportunityStageHistoryModel.opportunity_id,
                )
                .join(
                    PipelineStageModel,
                    PipelineStageModel.id == OpportunityStageHistoryModel.to_stage_id,
                )
                .where(OpportunityModel.account_id == account_id)
            )
            if filters.kind == TIMELINE_KIND_STAGE:
                history = history.where(
                    PipelineStageModel.is_won.is_(False), PipelineStageModel.is_lost.is_(False)
                )
            elif filters.kind == TIMELINE_KIND_CLOSED:
                history = history.where(
                    PipelineStageModel.is_won.is_(True) | PipelineStageModel.is_lost.is_(True)
                )
            sources.append(history)
        if include_quotes:
            # One branch per status timestamp: the timestamps already are the events.
            for kind, column in (
                (TIMELINE_KIND_QUOTE_SENT, QuoteModel.sent_at),
                (TIMELINE_KIND_QUOTE_ACCEPTED, QuoteModel.accepted_at),
                (TIMELINE_KIND_QUOTE_REJECTED, QuoteModel.rejected_at),
            ):
                if filters.kind is not None and filters.kind != kind:
                    continue
                sources.append(
                    select(
                        QuoteModel.id.label("item_id"),
                        column.label("occurred_at"),
                        literal(kind).label("kind"),
                    )
                    .join(OpportunityModel, OpportunityModel.id == QuoteModel.opportunity_id)
                    .where(OpportunityModel.account_id == account_id, column.isnot(None))
                )
        if not sources:
            return TimelineListResult(items=[], total=0)

        union = sources[0] if len(sources) == 1 else union_all(*sources)
        union_subquery = union.subquery()
        total = await self._session.scalar(select(func.count()).select_from(union_subquery))
        page_rows = (
            await self._session.execute(
                select(union_subquery)
                .order_by(union_subquery.c.occurred_at.desc(), union_subquery.c.item_id.desc())
                .offset(params.offset)
                .limit(params.limit)
            )
        ).all()

        activity_ids = [row.item_id for row in page_rows if row.kind == TIMELINE_KIND_ACTIVITY]
        history_ids = [
            row.item_id
            for row in page_rows
            if row.kind in (TIMELINE_KIND_STAGE, TIMELINE_KIND_CLOSED)
        ]
        quote_ids = [row.item_id for row in page_rows if row.kind in TIMELINE_QUOTE_KINDS]
        activity_entries = await self._activity_entries(activity_ids)
        history_entries = await self._history_entries(history_ids)
        quote_entries = await self._quote_entries(quote_ids)
        entries: list[TimelineEntry] = []
        for row in page_rows:
            if row.kind == TIMELINE_KIND_ACTIVITY:
                entry = activity_entries.get(row.item_id)
            elif row.kind in TIMELINE_QUOTE_KINDS:
                entry = self._quote_entry(quote_entries.get(row.item_id), row.kind)
            else:
                entry = history_entries.get(row.item_id)
            if entry is not None:
                entries.append(entry)
        return TimelineListResult(items=entries, total=int(total or 0))

    async def _activity_entries(self, ids: Sequence[UUID]) -> dict[UUID, TimelineEntry]:
        if not ids:
            return {}
        views = await _views(self._session, _base_select().where(ActivityModel.id.in_(list(ids))))
        return {
            view.activity.id: TimelineEntry(
                id=view.activity.id,
                kind=TIMELINE_KIND_ACTIVITY,
                occurred_at=view.activity.occurred_at,
                title=view.activity.subject or view.activity_type_name,
                activity=view,
            )
            for view in views
        }

    async def _quote_entries(self, ids: Sequence[UUID]) -> dict[UUID, tuple[Any, str]]:
        if not ids:
            return {}
        rows = (
            await self._session.execute(
                select(QuoteModel, OpportunityModel.name)
                .join(OpportunityModel, OpportunityModel.id == QuoteModel.opportunity_id)
                .where(QuoteModel.id.in_(list(ids)))
            )
        ).all()
        return {row[0].id: (row[0], row[1]) for row in rows}

    @staticmethod
    def _quote_entry(data: tuple[Any, str] | None, kind: str) -> TimelineEntry | None:
        if data is None:
            return None
        quote, opportunity_name = data
        display = f"P-{quote.year}-{quote.number:04d}"
        if quote.version > 1:
            display = f"{display}-v{quote.version}"
        if kind == TIMELINE_KIND_QUOTE_SENT:
            occurred_at, verb = quote.sent_at, "enviado"
        elif kind == TIMELINE_KIND_QUOTE_ACCEPTED:
            occurred_at, verb = quote.accepted_at, "aceptado"
        else:
            occurred_at, verb = quote.rejected_at, "rechazado"
        if occurred_at is None:
            return None
        return TimelineEntry(
            id=quote.id,
            kind=kind,
            occurred_at=occurred_at,
            title=f"Presupuesto {display} {verb} · {format_eur(quote.total)}",
            quote_event=QuoteEventView(
                quote_id=quote.id,
                display_number=display,
                opportunity_id=quote.opportunity_id,
                opportunity_name=opportunity_name,
                total=quote.total,
                status=str(quote.status.value),
            ),
        )

    async def _history_entries(self, ids: Sequence[UUID]) -> dict[UUID, TimelineEntry]:
        if not ids:
            return {}
        from_stage = aliased(PipelineStageModel)
        rows = (
            await self._session.execute(
                select(
                    OpportunityStageHistoryModel,
                    OpportunityModel.name,
                    OpportunityModel.amount,
                    OpportunityModel.won_amount,
                    PipelineStageModel.name_es,
                    PipelineStageModel.is_won,
                    PipelineStageModel.is_lost,
                    from_stage.name_es,
                    UserModel.full_name,
                )
                .join(
                    OpportunityModel,
                    OpportunityModel.id == OpportunityStageHistoryModel.opportunity_id,
                )
                .join(
                    PipelineStageModel,
                    PipelineStageModel.id == OpportunityStageHistoryModel.to_stage_id,
                )
                .outerjoin(from_stage, from_stage.id == OpportunityStageHistoryModel.from_stage_id)
                .outerjoin(UserModel, UserModel.id == OpportunityStageHistoryModel.actor_id)
                .where(OpportunityStageHistoryModel.id.in_(list(ids)))
            )
        ).all()
        entries: dict[UUID, TimelineEntry] = {}
        for row in rows:
            history: OpportunityStageHistoryModel = row[0]
            opportunity_name, amount, won_amount = row[1], row[2], row[3]
            to_stage_name, is_won, is_lost = row[4], row[5], row[6]
            from_stage_name, actor_name = row[7], row[8]
            closed = bool(is_won or is_lost)
            entry_amount = won_amount if (is_won and won_amount is not None) else amount
            title = (
                f"{to_stage_name} · {format_eur(entry_amount)}"
                if closed
                else f"{opportunity_name} → {to_stage_name}"
            )
            entries[history.id] = TimelineEntry(
                id=history.id,
                kind=TIMELINE_KIND_CLOSED if closed else TIMELINE_KIND_STAGE,
                occurred_at=history.occurred_at,
                title=title,
                stage_change=StageChangeView(
                    opportunity_id=history.opportunity_id,
                    opportunity_name=opportunity_name,
                    from_stage_name=from_stage_name,
                    to_stage_name=to_stage_name,
                    actor_name=actor_name,
                    amount=entry_amount,
                    is_won=bool(is_won),
                    is_lost=bool(is_lost),
                ),
            )
        return entries


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
