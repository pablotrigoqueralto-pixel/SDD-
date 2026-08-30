"""Global search: four bounded, scoped SELECTs — one per entity, grouped result."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.activities.queries import BUSINESS_TIMEZONE
from app.application.search.router import ParsedQuery
from app.domain.opportunities.entities import OpportunityStatus
from app.domain.quotes.entities import QuoteStatus
from app.infrastructure.db.models import (
    AccountModel,
    ContactModel,
    OpportunityModel,
    PipelineStageModel,
    QuoteModel,
)

GROUP_CAP = 5
CONTACT_GROUP_CAP = 10


@dataclass(frozen=True)
class AccountHit:
    id: UUID
    name: str
    city: str | None
    province_code: str
    is_active: bool


@dataclass(frozen=True)
class ContactHit:
    id: UUID
    account_id: UUID
    account_name: str
    full_name: str
    email: str | None
    mobile: str | None


@dataclass(frozen=True)
class OpportunityHit:
    id: UUID
    account_id: UUID
    account_name: str
    name: str
    stage_name: str
    status: OpportunityStatus
    amount: Decimal
    is_tender: bool


@dataclass(frozen=True)
class QuoteHit:
    id: UUID
    opportunity_id: UUID
    account_name: str
    display_number: str
    status: QuoteStatus
    is_expired: bool
    total: Decimal
    valid_until: date | None


@dataclass(frozen=True)
class SearchGroup[T]:
    items: list[T]
    total: int
    has_more: bool


@dataclass(frozen=True)
class SearchResults:
    accounts: SearchGroup[AccountHit]
    contacts: SearchGroup[ContactHit]
    opportunities: SearchGroup[OpportunityHit]
    quotes: SearchGroup[QuoteHit]


def _empty(cap: int = GROUP_CAP) -> SearchGroup[Any]:
    return SearchGroup(items=[], total=0, has_more=False)


def empty_results() -> SearchResults:
    return SearchResults(
        accounts=_empty(),
        contacts=_empty(CONTACT_GROUP_CAP),
        opportunities=_empty(),
        quotes=_empty(),
    )


def _unaccent_like(column: Any, text: str) -> ColumnElement[bool]:
    return func.f_unaccent(column).ilike(func.f_unaccent(f"%{text}%"))


def _digits(column: Any) -> ColumnElement[Any]:
    return func.regexp_replace(column, r"\D", "", "g")


class SearchQueries:
    def __init__(self, session: AsyncSession, *, now: datetime | None = None) -> None:
        self._session = session
        self._now = now or datetime.now(UTC)

    async def search(self, parsed: ParsedQuery, account_ids: Select[Any] | None) -> SearchResults:
        return SearchResults(
            accounts=await self._accounts(parsed, account_ids),
            contacts=await self._contacts(parsed, account_ids),
            opportunities=await self._opportunities(parsed, account_ids),
            quotes=await self._quotes(parsed, account_ids),
        )

    async def _group(
        self,
        statement: Select[Any],
        conditions: list[ColumnElement[bool]],
        order_by: list[Any],
        cap: int,
    ) -> tuple[list[Any], int, bool]:
        filtered = statement.where(or_(*conditions))
        total = await self._session.scalar(select(func.count()).select_from(filtered.subquery()))
        rows = (await self._session.execute(filtered.order_by(*order_by).limit(cap))).all()
        count = int(total or 0)
        return list(rows), count, count > len(rows)

    async def _accounts(
        self, parsed: ParsedQuery, account_ids: Select[Any] | None
    ) -> SearchGroup[AccountHit]:
        statement = select(AccountModel)
        if account_ids is not None:
            statement = statement.where(AccountModel.id.in_(account_ids))
        conditions: list[ColumnElement[bool]] = [_unaccent_like(AccountModel.name, parsed.text)]
        if parsed.tax_id:
            conditions.append(AccountModel.tax_id == parsed.tax_id)
        if parsed.email:
            conditions.append(AccountModel.email.ilike(f"{parsed.email}%"))
        if parsed.phone_digits:
            conditions.append(_digits(AccountModel.phone).like(f"%{parsed.phone_digits}%"))
        rows, total, has_more = await self._group(
            statement,
            conditions,
            [
                func.similarity(
                    func.f_unaccent(AccountModel.name), func.f_unaccent(parsed.text)
                ).desc(),
                AccountModel.name,
            ],
            GROUP_CAP,
        )
        items = [
            AccountHit(
                id=row[0].id,
                name=row[0].name,
                city=row[0].city,
                province_code=row[0].province_code,
                is_active=row[0].is_active,
            )
            for row in rows
        ]
        return SearchGroup(items=items, total=total, has_more=has_more)

    async def _contacts(
        self, parsed: ParsedQuery, account_ids: Select[Any] | None
    ) -> SearchGroup[ContactHit]:
        statement = select(ContactModel, AccountModel.name).join(
            AccountModel, AccountModel.id == ContactModel.account_id
        )
        if account_ids is not None:
            statement = statement.where(ContactModel.account_id.in_(account_ids))
        full_name = ContactModel.first_name + " " + ContactModel.last_name
        conditions: list[ColumnElement[bool]] = [_unaccent_like(full_name, parsed.text)]
        if parsed.email:
            conditions.append(ContactModel.email.ilike(f"{parsed.email}%"))
        if parsed.phone_digits:
            pattern = f"%{parsed.phone_digits}%"
            conditions.append(_digits(ContactModel.mobile).like(pattern))
            conditions.append(_digits(ContactModel.landline).like(pattern))
        rows, total, has_more = await self._group(
            statement,
            conditions,
            [ContactModel.updated_at.desc(), ContactModel.id],
            CONTACT_GROUP_CAP,
        )
        items = [
            ContactHit(
                id=row[0].id,
                account_id=row[0].account_id,
                account_name=row[1],
                full_name=f"{row[0].first_name} {row[0].last_name}".strip(),
                email=row[0].email,
                mobile=row[0].mobile,
            )
            for row in rows
        ]
        return SearchGroup(items=items, total=total, has_more=has_more)

    async def _opportunities(
        self, parsed: ParsedQuery, account_ids: Select[Any] | None
    ) -> SearchGroup[OpportunityHit]:
        statement = (
            select(OpportunityModel, AccountModel.name, PipelineStageModel.name_es)
            .join(AccountModel, AccountModel.id == OpportunityModel.account_id)
            .join(PipelineStageModel, PipelineStageModel.id == OpportunityModel.stage_id)
        )
        if account_ids is not None:
            statement = statement.where(OpportunityModel.account_id.in_(account_ids))
        conditions: list[ColumnElement[bool]] = [
            _unaccent_like(OpportunityModel.name, parsed.text),
            OpportunityModel.tender_reference.ilike(f"%{parsed.text}%"),
        ]
        rows, total, has_more = await self._group(
            statement,
            conditions,
            [OpportunityModel.updated_at.desc(), OpportunityModel.id],
            GROUP_CAP,
        )
        items = [
            OpportunityHit(
                id=row[0].id,
                account_id=row[0].account_id,
                account_name=row[1],
                name=row[0].name,
                stage_name=row[2],
                status=row[0].status,
                amount=row[0].amount,
                is_tender=row[0].is_tender,
            )
            for row in rows
        ]
        return SearchGroup(items=items, total=total, has_more=has_more)

    async def _quotes(
        self, parsed: ParsedQuery, account_ids: Select[Any] | None
    ) -> SearchGroup[QuoteHit]:
        statement = (
            select(QuoteModel, AccountModel.name)
            .join(OpportunityModel, OpportunityModel.id == QuoteModel.opportunity_id)
            .join(AccountModel, AccountModel.id == OpportunityModel.account_id)
            .where(QuoteModel.superseded_at.is_(None))
        )
        if account_ids is not None:
            statement = statement.where(OpportunityModel.account_id.in_(account_ids))
        conditions: list[ColumnElement[bool]] = [_unaccent_like(AccountModel.name, parsed.text)]
        if parsed.quote_number:
            year, number = parsed.quote_number
            year_match = QuoteModel.year == year
            conditions.append(
                (year_match & (QuoteModel.number == number)) if number is not None else year_match
            )
        rows, total, has_more = await self._group(
            statement,
            conditions,
            [QuoteModel.created_at.desc(), QuoteModel.id],
            GROUP_CAP,
        )
        today = self._now.astimezone(BUSINESS_TIMEZONE).date()
        items = [
            QuoteHit(
                id=row[0].id,
                opportunity_id=row[0].opportunity_id,
                account_name=row[1],
                display_number=(
                    f"P-{row[0].year}-{row[0].number:04d}"
                    + (f"-v{row[0].version}" if row[0].version > 1 else "")
                ),
                status=row[0].status,
                is_expired=(
                    row[0].status is QuoteStatus.SENT
                    and row[0].valid_until is not None
                    and row[0].valid_until < today
                ),
                total=row[0].total,
                valid_until=row[0].valid_until,
            )
            for row in rows
        ]
        return SearchGroup(items=items, total=total, has_more=has_more)
