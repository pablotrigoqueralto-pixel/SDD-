"""Dashboard read model: fixed aggregate SELECTs over existing tables (design D1/D4/D5).

Every KPI definition lives here and nowhere else. The queries are read-only and
scoped server-side: a sales rep sees their ownership, everyone else the company.
"""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from uuid import UUID

from sqlalchemy import ColumnElement, and_, case, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import InstrumentedAttribute

from app.application.dashboard.periods import ResolvedPeriod
from app.domain.opportunities.entities import OpportunityStatus
from app.domain.users.entities import User
from app.domain.users.roles import ROLES_WITH_FULL_VISIBILITY
from app.infrastructure.db.models import (
    AccountModel,
    ActivityModel,
    ActivityTypeModel,
    DivisionModel,
    OpportunityModel,
    PipelineStageModel,
    UserModel,
)

NEGLECTED_AFTER_DAYS = 60
NEGLECTED_CAP = 20
TWO_PLACES = Decimal("0.01")


@dataclass(frozen=True)
class WonKpi:
    amount: Decimal
    count: int
    previous_amount: Decimal
    previous_count: int


@dataclass(frozen=True)
class ConversionKpi:
    rate: float | None
    won: int
    closed: int
    previous_rate: float | None


@dataclass(frozen=True)
class MoneyKpi:
    amount: Decimal
    count: int


@dataclass(frozen=True)
class StageRow:
    stage_id: UUID
    name: str
    amount: Decimal
    count: int


@dataclass(frozen=True)
class BreakdownRow:
    id: UUID
    name: str
    won_amount: Decimal
    won_count: int
    forecast_amount: Decimal
    open_amount: Decimal
    conversion_rate: float | None


@dataclass(frozen=True)
class ActivityTypeCount:
    code: str
    name: str
    count: int


@dataclass(frozen=True)
class ActivityRow:
    user_id: UUID
    name: str
    total: int
    by_type: list[ActivityTypeCount]


@dataclass(frozen=True)
class NeglectedAccount:
    id: UUID
    name: str
    days_since_contact: int | None


@dataclass(frozen=True)
class NeglectedAccounts:
    total: int
    items: list[NeglectedAccount]


@dataclass(frozen=True)
class DashboardSummary:
    won: WonKpi
    conversion: ConversionKpi
    forecast: MoneyKpi
    open_pipeline: MoneyKpi


@dataclass(frozen=True)
class DashboardData:
    summary: DashboardSummary
    pipeline_by_stage: list[StageRow]
    by_division: list[BreakdownRow]
    by_rep: list[BreakdownRow] | None
    activity: list[ActivityRow]
    neglected_accounts: NeglectedAccounts


def _money(value: Decimal | None) -> Decimal:
    return (value or Decimal("0")).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)


def _rate(won: int, closed: int) -> float | None:
    return None if closed == 0 else won / closed


class DashboardQueries:
    def __init__(self, session: AsyncSession, *, now: datetime | None = None) -> None:
        self._session = session
        self._now = now or datetime.now(tz=UTC)

    async def load(self, period: ResolvedPeriod, actor: User) -> DashboardData:
        owner_id = None if actor.role in ROLES_WITH_FULL_VISIBILITY else actor.id
        summary = await self._summary(period, owner_id)
        return DashboardData(
            summary=summary,
            pipeline_by_stage=await self._pipeline_by_stage(owner_id),
            by_division=await self._breakdown(
                period, owner_id, OpportunityModel.division_id, DivisionModel.name_es, DivisionModel
            ),
            by_rep=(
                None
                if owner_id is not None
                else await self._breakdown(
                    period, owner_id, OpportunityModel.owner_id, UserModel.full_name, UserModel
                )
            ),
            activity=await self._activity(period, owner_id),
            neglected_accounts=await self._neglected(owner_id),
        )

    # -- filters -----------------------------------------------------------------

    @staticmethod
    def _owner_filter(owner_id: UUID | None) -> ColumnElement[bool]:
        return true() if owner_id is None else OpportunityModel.owner_id == owner_id

    @staticmethod
    def _won_in(start: datetime, end: datetime) -> ColumnElement[bool]:
        return and_(
            OpportunityModel.status == OpportunityStatus.WON,
            OpportunityModel.won_at >= start,
            OpportunityModel.won_at < end,
        )

    @staticmethod
    def _lost_in(start: datetime, end: datetime) -> ColumnElement[bool]:
        return and_(
            OpportunityModel.status == OpportunityStatus.LOST,
            OpportunityModel.lost_at >= start,
            OpportunityModel.lost_at < end,
        )

    @staticmethod
    def _open_closing_in(period: ResolvedPeriod) -> ColumnElement[bool]:
        return and_(
            OpportunityModel.status == OpportunityStatus.OPEN,
            OpportunityModel.expected_close_date >= period.current_start,
            OpportunityModel.expected_close_date < period.current_end,
        )

    @staticmethod
    def _weighted() -> ColumnElement[Decimal]:
        return OpportunityModel.amount * PipelineStageModel.probability / 100

    # -- sections ----------------------------------------------------------------

    async def _summary(self, period: ResolvedPeriod, owner_id: UUID | None) -> DashboardSummary:
        won_now = self._won_in(period.current_start_utc, period.current_end_utc)
        won_before = self._won_in(period.previous_start_utc, period.previous_end_utc)
        lost_now = self._lost_in(period.current_start_utc, period.current_end_utc)
        lost_before = self._lost_in(period.previous_start_utc, period.previous_end_utc)
        is_open = OpportunityModel.status == OpportunityStatus.OPEN

        row = (
            await self._session.execute(
                select(
                    func.coalesce(func.sum(OpportunityModel.won_amount).filter(won_now), 0),
                    func.count().filter(won_now),
                    func.coalesce(func.sum(OpportunityModel.won_amount).filter(won_before), 0),
                    func.count().filter(won_before),
                    func.count().filter(lost_now),
                    func.count().filter(lost_before),
                    func.coalesce(func.sum(OpportunityModel.amount).filter(is_open), 0),
                    func.count().filter(is_open),
                    func.coalesce(
                        func.sum(self._weighted()).filter(self._open_closing_in(period)), 0
                    ),
                    func.count().filter(self._open_closing_in(period)),
                )
                .select_from(OpportunityModel)
                .join(PipelineStageModel, PipelineStageModel.id == OpportunityModel.stage_id)
                .where(self._owner_filter(owner_id))
            )
        ).one()
        (
            won_amount,
            won_count,
            previous_amount,
            previous_count,
            lost_count,
            previous_lost,
            open_amount,
            open_count,
            forecast_amount,
            forecast_count,
        ) = row
        return DashboardSummary(
            won=WonKpi(_money(won_amount), won_count, _money(previous_amount), previous_count),
            conversion=ConversionKpi(
                rate=_rate(won_count, won_count + lost_count),
                won=won_count,
                closed=won_count + lost_count,
                previous_rate=_rate(previous_count, previous_count + previous_lost),
            ),
            forecast=MoneyKpi(_money(forecast_amount), forecast_count),
            open_pipeline=MoneyKpi(_money(open_amount), open_count),
        )

    async def _pipeline_by_stage(self, owner_id: UUID | None) -> list[StageRow]:
        rows = await self._session.execute(
            select(
                PipelineStageModel.id,
                PipelineStageModel.name_es,
                func.sum(OpportunityModel.amount),
                func.count(),
            )
            .join(OpportunityModel, OpportunityModel.stage_id == PipelineStageModel.id)
            .where(OpportunityModel.status == OpportunityStatus.OPEN, self._owner_filter(owner_id))
            .group_by(PipelineStageModel.id, PipelineStageModel.name_es)
            .order_by(func.min(PipelineStageModel.sort_order))
        )
        return [
            StageRow(stage_id=row[0], name=row[1], amount=_money(row[2]), count=row[3])
            for row in rows
        ]

    async def _breakdown(
        self,
        period: ResolvedPeriod,
        owner_id: UUID | None,
        group_column: InstrumentedAttribute[UUID],
        name_column: InstrumentedAttribute[str],
        name_model: type[DivisionModel] | type[UserModel],
    ) -> list[BreakdownRow]:
        won_now = self._won_in(period.current_start_utc, period.current_end_utc)
        lost_now = self._lost_in(period.current_start_utc, period.current_end_utc)
        is_open = OpportunityModel.status == OpportunityStatus.OPEN
        won_sum = func.coalesce(func.sum(OpportunityModel.won_amount).filter(won_now), 0)

        rows = await self._session.execute(
            select(
                group_column,
                name_column,
                won_sum,
                func.count().filter(won_now),
                func.count().filter(lost_now),
                func.coalesce(func.sum(self._weighted()).filter(self._open_closing_in(period)), 0),
                func.coalesce(func.sum(OpportunityModel.amount).filter(is_open), 0),
                func.count().filter(is_open),
            )
            .select_from(OpportunityModel)
            .join(PipelineStageModel, PipelineStageModel.id == OpportunityModel.stage_id)
            .join(name_model, name_model.id == group_column)
            .where(self._owner_filter(owner_id))
            .group_by(group_column, name_column)
            .having(
                or_(
                    func.count().filter(won_now) > 0,
                    func.count().filter(lost_now) > 0,
                    func.count().filter(is_open) > 0,
                )
            )
            .order_by(won_sum.desc(), name_column)
        )
        return [
            BreakdownRow(
                id=row[0],
                name=row[1],
                won_amount=_money(row[2]),
                won_count=row[3],
                forecast_amount=_money(row[5]),
                open_amount=_money(row[6]),
                conversion_rate=_rate(row[3], row[3] + row[4]),
            )
            for row in rows
        ]

    async def _activity(self, period: ResolvedPeriod, owner_id: UUID | None) -> list[ActivityRow]:
        done_filter = and_(
            ActivityModel.done_at.is_not(None),
            ActivityModel.done_at >= period.current_start_utc,
            ActivityModel.done_at < period.current_end_utc,
            true() if owner_id is None else ActivityModel.owner_id == owner_id,
        )
        rows = (
            await self._session.execute(
                select(
                    ActivityModel.owner_id,
                    UserModel.full_name,
                    ActivityTypeModel.code,
                    ActivityTypeModel.name_es,
                    func.count(),
                )
                .join(UserModel, UserModel.id == ActivityModel.owner_id)
                .join(ActivityTypeModel, ActivityTypeModel.id == ActivityModel.activity_type_id)
                .where(done_filter)
                .group_by(
                    ActivityModel.owner_id,
                    UserModel.full_name,
                    ActivityTypeModel.code,
                    ActivityTypeModel.name_es,
                    ActivityTypeModel.sort_order,
                )
                .order_by(ActivityTypeModel.sort_order)
            )
        ).all()

        grouped: dict[UUID, ActivityRow] = {}
        for user_id, full_name, code, type_name, count in rows:
            existing = grouped.get(user_id)
            counts = [*existing.by_type] if existing else []
            counts.append(ActivityTypeCount(code=code, name=type_name, count=count))
            grouped[user_id] = ActivityRow(
                user_id=user_id,
                name=full_name,
                total=(existing.total if existing else 0) + count,
                by_type=counts,
            )
        return sorted(grouped.values(), key=lambda row: (-row.total, row.name))

    async def _neglected(self, owner_id: UUID | None) -> NeglectedAccounts:
        cutoff = self._now - timedelta(days=NEGLECTED_AFTER_DAYS)
        neglected = and_(
            AccountModel.is_active.is_(True),
            true() if owner_id is None else AccountModel.owner_id == owner_id,
            or_(
                AccountModel.last_contact_at < cutoff,
                and_(AccountModel.last_contact_at.is_(None), AccountModel.created_at < cutoff),
            ),
        )
        total_query = select(func.count()).select_from(AccountModel).where(neglected)
        total = (await self._session.execute(total_query)).scalar_one()
        rows = await self._session.execute(
            select(AccountModel.id, AccountModel.name, AccountModel.last_contact_at)
            .where(neglected)
            .order_by(
                case((AccountModel.last_contact_at.is_(None), 0), else_=1),
                AccountModel.last_contact_at.asc(),
                AccountModel.name,
            )
            .limit(NEGLECTED_CAP)
        )
        items = [
            NeglectedAccount(
                id=row[0],
                name=row[1],
                days_since_contact=None if row[2] is None else (self._now - row[2]).days,
            )
            for row in rows
        ]
        return NeglectedAccounts(total=total, items=items)
