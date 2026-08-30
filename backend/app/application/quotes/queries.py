"""Read side for quotes: scoped list of current versions, chains and expiring block."""

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, Text, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased

from app.application.activities.queries import BUSINESS_TIMEZONE
from app.application.shared.pagination import PageParams
from app.domain.quotes.entities import QuoteStatus
from app.infrastructure.db.models import (
    AccountModel,
    MailOutboxModel,
    OpportunityModel,
    QuoteModel,
    UserModel,
)

QUOTE_SORT_FIELDS: set[str] = {"created_at", "valid_until", "total", "status"}
QUOTE_DEFAULT_SORT = "-created_at"
QUOTE_MAX_PAGE_SIZE = 100
EXPIRING_WINDOW_DAYS = 7

_OWNER = aliased(UserModel)


@dataclass(frozen=True)
class QuoteSummary:
    id: UUID
    opportunity_id: UUID
    opportunity_name: str
    account_id: UUID
    account_name: str
    quote_number: str
    display_number: str
    revision: int
    status: QuoteStatus
    total: Decimal
    valid_until: date | None
    is_expired: bool
    owner_id: UUID
    owner_name: str
    version_lock: int
    sent_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None


@dataclass(frozen=True)
class QuoteFilters:
    status: QuoteStatus | None = None
    owner_id: UUID | None = None
    opportunity_id: UUID | None = None
    account_id: UUID | None = None
    expiring: bool = False
    q: str | None = None


@dataclass(frozen=True)
class QuoteListResult:
    items: list[QuoteSummary]
    total: int


@dataclass(frozen=True)
class QuoteVersionRef:
    id: UUID
    revision: int
    status: QuoteStatus
    sent_at: datetime | None


def quote_status_filter(value: str | None) -> QuoteStatus | None:
    if value in (None, "", "all"):
        return None
    return QuoteStatus(value)


def _base_select() -> Select[Any]:
    return (
        select(
            QuoteModel,
            OpportunityModel.name,
            AccountModel.name,
            _OWNER.full_name,
            OpportunityModel.account_id,
        )
        .join(OpportunityModel, OpportunityModel.id == QuoteModel.opportunity_id)
        .join(AccountModel, AccountModel.id == OpportunityModel.account_id)
        .join(_OWNER, _OWNER.id == QuoteModel.owner_id)
    )


def _display_number(year: int, number: int, revision: int) -> str:
    base = f"P-{year}-{number:04d}"
    return base if revision == 1 else f"{base}-v{revision}"


def _printed_number() -> ColumnElement[str]:
    """SQL twin of `quote_number` for text search."""
    return func.concat(
        "P-", cast(QuoteModel.year, Text), "-", func.lpad(cast(QuoteModel.number, Text), 4, "0")
    )


class QuoteQueries:
    def __init__(self, session: AsyncSession, *, now: datetime | None = None) -> None:
        self._session = session
        self._now = now or datetime.now(UTC)

    @property
    def _today(self) -> date:
        return self._now.astimezone(BUSINESS_TIMEZONE).date()

    def _to_summary(self, row: Any) -> QuoteSummary:
        model: QuoteModel = row[0]
        return QuoteSummary(
            id=model.id,
            opportunity_id=model.opportunity_id,
            opportunity_name=row[1],
            account_id=row[4],
            account_name=row[2],
            quote_number=f"P-{model.year}-{model.number:04d}",
            display_number=_display_number(model.year, model.number, model.version),
            revision=model.version,
            status=model.status,
            total=model.total,
            valid_until=model.valid_until,
            is_expired=(
                model.status is QuoteStatus.SENT
                and model.valid_until is not None
                and model.valid_until < self._today
            ),
            owner_id=model.owner_id,
            owner_name=row[3],
            version_lock=model.version_lock,
            sent_at=model.sent_at,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    async def list_page(
        self,
        params: PageParams,
        filters: QuoteFilters,
        account_ids: Select[Any] | None,
    ) -> QuoteListResult:
        base = self._apply_filters(_base_select(), filters, account_ids)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        statement = base.order_by(*self._order_by(params)).offset(params.offset).limit(params.limit)
        rows = (await self._session.execute(statement)).all()
        return QuoteListResult(items=[self._to_summary(row) for row in rows], total=int(total or 0))

    async def for_opportunity(self, opportunity_id: UUID) -> list[QuoteSummary]:
        statement = (
            _base_select()
            .where(
                QuoteModel.opportunity_id == opportunity_id,
                QuoteModel.superseded_at.is_(None),
            )
            .order_by(QuoteModel.created_at.desc(), QuoteModel.id)
        )
        rows = (await self._session.execute(statement)).all()
        return [self._to_summary(row) for row in rows]

    async def version_chain(self, year: int, number: int) -> list[QuoteVersionRef]:
        statement = (
            select(QuoteModel.id, QuoteModel.version, QuoteModel.status, QuoteModel.sent_at)
            .where(QuoteModel.year == year, QuoteModel.number == number)
            .order_by(QuoteModel.version.desc())
        )
        rows = (await self._session.execute(statement)).all()
        return [
            QuoteVersionRef(id=row[0], revision=row[1], status=row[2], sent_at=row[3])
            for row in rows
        ]

    async def expiring_for_owner(
        self, owner_id: UUID, *, window_days: int = EXPIRING_WINDOW_DAYS
    ) -> list[QuoteSummary]:
        limit_date = self._today + timedelta(days=window_days)
        statement = (
            _base_select()
            .where(
                QuoteModel.owner_id == owner_id,
                QuoteModel.status == QuoteStatus.SENT,
                QuoteModel.superseded_at.is_(None),
                QuoteModel.valid_until.isnot(None),
                QuoteModel.valid_until <= limit_date,
            )
            .order_by(QuoteModel.valid_until, QuoteModel.id)
        )
        rows = (await self._session.execute(statement)).all()
        return [self._to_summary(row) for row in rows]

    async def count_for_opportunity(self, opportunity_id: UUID) -> int:
        total = await self._session.scalar(
            select(func.count()).where(
                QuoteModel.opportunity_id == opportunity_id,
                QuoteModel.superseded_at.is_(None),
            )
        )
        return int(total or 0)

    async def latest_email_status(self, quote_id: UUID) -> tuple[str, str | None] | None:
        statement = (
            select(MailOutboxModel.status, MailOutboxModel.error)
            .where(MailOutboxModel.quote_id == quote_id)
            .order_by(MailOutboxModel.created_at.desc())
            .limit(1)
        )
        row = (await self._session.execute(statement)).first()
        return (str(row[0]), row[1]) if row else None

    def _apply_filters(
        self,
        statement: Select[Any],
        filters: QuoteFilters,
        account_ids: Select[Any] | None,
    ) -> Select[Any]:
        statement = statement.where(QuoteModel.superseded_at.is_(None))
        if account_ids is not None:
            statement = statement.where(OpportunityModel.account_id.in_(account_ids))
        if filters.status is not None:
            statement = statement.where(QuoteModel.status == filters.status)
        if filters.owner_id is not None:
            statement = statement.where(QuoteModel.owner_id == filters.owner_id)
        if filters.opportunity_id is not None:
            statement = statement.where(QuoteModel.opportunity_id == filters.opportunity_id)
        if filters.account_id is not None:
            statement = statement.where(OpportunityModel.account_id == filters.account_id)
        if filters.expiring:
            statement = statement.where(
                QuoteModel.status == QuoteStatus.SENT,
                QuoteModel.valid_until.isnot(None),
                QuoteModel.valid_until <= self._today + timedelta(days=EXPIRING_WINDOW_DAYS),
            )
        if filters.q and filters.q.strip():
            contains = f"%{filters.q.strip()}%"
            statement = statement.where(
                _printed_number().ilike(contains) | AccountModel.name.ilike(contains)
            )
        return statement

    @staticmethod
    def _order_by(params: PageParams) -> list[ColumnElement[Any]]:
        columns = {
            "created_at": QuoteModel.created_at,
            "valid_until": QuoteModel.valid_until,
            "total": QuoteModel.total,
            "status": QuoteModel.status,
        }
        clauses: list[ColumnElement[Any]] = []
        for sort_field in params.sort:
            column = columns[sort_field.name]
            ordered = column.desc() if sort_field.descending else column.asc()
            clauses.append(ordered.nulls_last())
        clauses.append(QuoteModel.id.asc())
        return clauses
