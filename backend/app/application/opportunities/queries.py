"""Read side for opportunities: scoped list, account view and the pipeline board."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.application.activities.queries import BUSINESS_TIMEZONE
from app.application.shared.pagination import PageParams
from app.domain.opportunities.entities import OpportunityStatus
from app.domain.reference.entities import Pipeline, PipelineStage
from app.domain.shared.errors import NotFoundError
from app.infrastructure.db.models import (
    AccountModel,
    OpportunityModel,
    PipelineStageModel,
    UserModel,
)

OPPORTUNITY_SORT_FIELDS: set[str] = {
    "expected_close_date",
    "amount",
    "stage_entered_at",
    "updated_at",
    "name",
}
OPPORTUNITY_DEFAULT_SORT = "expected_close_date"
OPPORTUNITY_MAX_PAGE_SIZE = 100
BOARD_COLUMN_CAP = 50
TENDER_DUE_WINDOW_DAYS = 7

_OWNER = aliased(UserModel)


@dataclass(frozen=True)
class OpportunitySummary:
    id: UUID
    account_id: UUID
    account_name: str
    name: str
    pipeline_id: UUID
    stage_id: UUID
    stage_name: str
    division_id: UUID
    owner_id: UUID
    owner_name: str
    status: OpportunityStatus
    amount: Decimal
    expected_close_date: date
    is_tender: bool
    tender_deadline: date | None
    is_at_risk: bool
    stage_entered_at: datetime
    days_in_stage: int
    version: int
    updated_at: datetime | None


@dataclass(frozen=True)
class OpportunityFilters:
    status: OpportunityStatus | None = OpportunityStatus.OPEN
    pipeline_id: UUID | None = None
    stage_id: UUID | None = None
    division_id: UUID | None = None
    owner_id: UUID | None = None
    account_id: UUID | None = None
    is_tender: bool | None = None
    is_at_risk: bool | None = None
    close_from: date | None = None
    close_to: date | None = None
    q: str | None = None


@dataclass(frozen=True)
class OpportunityListResult:
    items: list[OpportunitySummary]
    total: int


@dataclass(frozen=True)
class BoardColumn:
    stage: PipelineStage
    count: int
    total_amount: Decimal
    items: list[OpportunitySummary]
    has_more: bool


@dataclass(frozen=True)
class ClosedSummary:
    won_count: int
    won_amount: Decimal
    lost_count: int


@dataclass(frozen=True)
class BoardResult:
    pipeline: Pipeline
    columns: list[BoardColumn]
    closed_this_month: ClosedSummary


def _base_select() -> Select[Any]:
    return (
        select(OpportunityModel, AccountModel.name, PipelineStageModel.name_es, _OWNER.full_name)
        .join(AccountModel, AccountModel.id == OpportunityModel.account_id)
        .join(PipelineStageModel, PipelineStageModel.id == OpportunityModel.stage_id)
        .join(_OWNER, _OWNER.id == OpportunityModel.owner_id)
    )


def _to_summary(row: Any, *, now: datetime) -> OpportunitySummary:
    model: OpportunityModel = row[0]
    return OpportunitySummary(
        id=model.id,
        account_id=model.account_id,
        account_name=row[1],
        name=model.name,
        pipeline_id=model.pipeline_id,
        stage_id=model.stage_id,
        stage_name=row[2],
        division_id=model.division_id,
        owner_id=model.owner_id,
        owner_name=row[3],
        status=model.status,
        amount=model.amount,
        expected_close_date=model.expected_close_date,
        is_tender=model.is_tender,
        tender_deadline=model.tender_deadline,
        is_at_risk=model.is_at_risk,
        stage_entered_at=model.stage_entered_at,
        days_in_stage=max(0, (now - model.stage_entered_at).days),
        version=model.version,
        updated_at=model.updated_at,
    )


def month_bounds(now: datetime) -> tuple[datetime, datetime]:
    """Start of the current and next Madrid month."""
    local = now.astimezone(BUSINESS_TIMEZONE)
    start = datetime.combine(local.date().replace(day=1), time.min, tzinfo=BUSINESS_TIMEZONE)
    next_month = (start + timedelta(days=32)).replace(day=1)
    return start, next_month


class OpportunityQueries:
    def __init__(self, session: AsyncSession, *, now: datetime | None = None) -> None:
        self._session = session
        self._now = now or datetime.now(UTC)

    async def list_page(
        self,
        params: PageParams,
        filters: OpportunityFilters,
        account_ids: Select[Any] | None,
    ) -> OpportunityListResult:
        base = self._apply_filters(_base_select(), filters, account_ids)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        statement = base.order_by(*self._order_by(params)).offset(params.offset).limit(params.limit)
        rows = (await self._session.execute(statement)).all()
        return OpportunityListResult(
            items=[_to_summary(row, now=self._now) for row in rows], total=int(total or 0)
        )

    async def for_account(self, account_id: UUID) -> list[OpportunitySummary]:
        statement = (
            _base_select()
            .where(OpportunityModel.account_id == account_id)
            .order_by(
                case((OpportunityModel.status == OpportunityStatus.OPEN, 0), else_=1),
                OpportunityModel.expected_close_date,
                OpportunityModel.id,
            )
        )
        rows = (await self._session.execute(statement)).all()
        return [_to_summary(row, now=self._now) for row in rows]

    async def get_summary(
        self, opportunity_id: UUID, account_ids: Select[Any] | None
    ) -> OpportunitySummary:
        base = _base_select().where(OpportunityModel.id == opportunity_id)
        if account_ids is not None:
            base = base.where(OpportunityModel.account_id.in_(account_ids))
        row = (await self._session.execute(base)).first()
        if row is None:
            raise NotFoundError("Opportunity not found")
        return _to_summary(row, now=self._now)

    async def board(
        self,
        pipeline: Pipeline,
        account_ids: Select[Any] | None,
        *,
        division_id: UUID | None = None,
        owner_id: UUID | None = None,
    ) -> BoardResult:
        # A card sits on the board while it is open, or while a won consumables row is at risk.
        member = (OpportunityModel.pipeline_id == pipeline.id) & (
            (OpportunityModel.status == OpportunityStatus.OPEN)
            | OpportunityModel.is_at_risk.is_(True)
        )
        conditions: list[ColumnElement[bool]] = [member]
        if division_id is not None:
            conditions.append(OpportunityModel.division_id == division_id)
        if owner_id is not None:
            conditions.append(OpportunityModel.owner_id == owner_id)
        if account_ids is not None:
            conditions.append(OpportunityModel.account_id.in_(account_ids))

        aggregate_rows = (
            await self._session.execute(
                select(
                    OpportunityModel.stage_id,
                    func.count(),
                    func.coalesce(func.sum(OpportunityModel.amount), 0),
                )
                .where(*conditions)
                .group_by(OpportunityModel.stage_id)
            )
        ).all()
        totals = {row[0]: (int(row[1]), Decimal(row[2])) for row in aggregate_rows}

        ranked = (
            select(
                OpportunityModel.id,
                func.row_number()
                .over(
                    partition_by=OpportunityModel.stage_id,
                    order_by=(OpportunityModel.stage_entered_at, OpportunityModel.id),
                )
                .label("rank"),
            )
            .where(*conditions)
            .subquery()
        )
        capped_ids = select(ranked.c.id).where(ranked.c.rank <= BOARD_COLUMN_CAP)
        rows = (
            await self._session.execute(
                _base_select()
                .where(OpportunityModel.id.in_(capped_ids))
                .order_by(OpportunityModel.stage_entered_at, OpportunityModel.id)
            )
        ).all()

        items_by_stage: dict[UUID, list[OpportunitySummary]] = {}
        for row in rows:
            summary = _to_summary(row, now=self._now)
            items_by_stage.setdefault(summary.stage_id, []).append(summary)

        columns: list[BoardColumn] = []
        for stage in pipeline.ordered_stages():
            if not stage.is_open or not stage.is_active:
                continue
            count, total_amount = totals.get(stage.id, (0, Decimal("0.00")))
            items = items_by_stage.get(stage.id, [])
            columns.append(
                BoardColumn(
                    stage=stage,
                    count=count,
                    total_amount=total_amount.quantize(Decimal("0.01")),
                    items=items,
                    has_more=count > len(items),
                )
            )
        return BoardResult(
            pipeline=pipeline,
            columns=columns,
            closed_this_month=await self._closed_this_month(pipeline, account_ids),
        )

    async def tenders_due(
        self, owner_id: UUID, *, window_days: int = TENDER_DUE_WINDOW_DAYS
    ) -> list[OpportunitySummary]:
        limit_date = self._now.astimezone(BUSINESS_TIMEZONE).date() + timedelta(days=window_days)
        statement = (
            _base_select()
            .where(
                OpportunityModel.owner_id == owner_id,
                OpportunityModel.status == OpportunityStatus.OPEN,
                OpportunityModel.is_tender.is_(True),
                OpportunityModel.tender_deadline.isnot(None),
                OpportunityModel.tender_deadline <= limit_date,
            )
            .order_by(OpportunityModel.tender_deadline, OpportunityModel.id)
        )
        rows = (await self._session.execute(statement)).all()
        return [_to_summary(row, now=self._now) for row in rows]

    async def at_risk(self, owner_id: UUID) -> list[OpportunitySummary]:
        statement = (
            _base_select()
            .where(OpportunityModel.owner_id == owner_id, OpportunityModel.is_at_risk.is_(True))
            .order_by(OpportunityModel.at_risk_since, OpportunityModel.id)
        )
        rows = (await self._session.execute(statement)).all()
        return [_to_summary(row, now=self._now) for row in rows]

    async def _closed_this_month(
        self, pipeline: Pipeline, account_ids: Select[Any] | None
    ) -> ClosedSummary:
        month_start, month_end = month_bounds(self._now)
        conditions: list[ColumnElement[bool]] = [OpportunityModel.pipeline_id == pipeline.id]
        if account_ids is not None:
            conditions.append(OpportunityModel.account_id.in_(account_ids))
        won_row = (
            await self._session.execute(
                select(func.count(), func.coalesce(func.sum(OpportunityModel.won_amount), 0)).where(
                    *conditions,
                    OpportunityModel.status == OpportunityStatus.WON,
                    OpportunityModel.won_at >= month_start,
                    OpportunityModel.won_at < month_end,
                )
            )
        ).one()
        lost_count = await self._session.scalar(
            select(func.count()).where(
                *conditions,
                OpportunityModel.status == OpportunityStatus.LOST,
                OpportunityModel.lost_at >= month_start,
                OpportunityModel.lost_at < month_end,
            )
        )
        return ClosedSummary(
            won_count=int(won_row[0]),
            won_amount=Decimal(won_row[1]).quantize(Decimal("0.01")),
            lost_count=int(lost_count or 0),
        )

    def _apply_filters(
        self,
        statement: Select[Any],
        filters: OpportunityFilters,
        account_ids: Select[Any] | None,
    ) -> Select[Any]:
        if account_ids is not None:
            statement = statement.where(OpportunityModel.account_id.in_(account_ids))
        if filters.status is not None:
            statement = statement.where(OpportunityModel.status == filters.status)
        if filters.pipeline_id is not None:
            statement = statement.where(OpportunityModel.pipeline_id == filters.pipeline_id)
        if filters.stage_id is not None:
            statement = statement.where(OpportunityModel.stage_id == filters.stage_id)
        if filters.division_id is not None:
            statement = statement.where(OpportunityModel.division_id == filters.division_id)
        if filters.owner_id is not None:
            statement = statement.where(OpportunityModel.owner_id == filters.owner_id)
        if filters.account_id is not None:
            statement = statement.where(OpportunityModel.account_id == filters.account_id)
        if filters.is_tender is not None:
            statement = statement.where(OpportunityModel.is_tender.is_(filters.is_tender))
        if filters.is_at_risk is not None:
            statement = statement.where(OpportunityModel.is_at_risk.is_(filters.is_at_risk))
        if filters.close_from is not None:
            statement = statement.where(OpportunityModel.expected_close_date >= filters.close_from)
        if filters.close_to is not None:
            statement = statement.where(OpportunityModel.expected_close_date <= filters.close_to)
        if filters.q and filters.q.strip():
            contains = f"%{filters.q.strip()}%"
            statement = statement.where(
                OpportunityModel.name.ilike(contains) | AccountModel.name.ilike(contains)
            )
        return statement

    @staticmethod
    def _order_by(params: PageParams) -> list[ColumnElement[Any]]:
        columns = {
            "expected_close_date": OpportunityModel.expected_close_date,
            "amount": OpportunityModel.amount,
            "stage_entered_at": OpportunityModel.stage_entered_at,
            "updated_at": OpportunityModel.updated_at,
            "name": OpportunityModel.name,
        }
        clauses: list[ColumnElement[Any]] = []
        for sort_field in params.sort:
            column = columns[sort_field.name]
            ordered = column.desc() if sort_field.descending else column.asc()
            clauses.append(ordered.nulls_last())
        clauses.append(OpportunityModel.id.asc())
        return clauses
