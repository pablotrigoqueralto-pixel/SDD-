"""Read side for accounts: scoped, paginated, filtered listing."""

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.pagination import PageParams
from app.domain.accounts.value_objects import is_valid_tax_id
from app.domain.shared.policies import ScopeFilter
from app.infrastructure.db.models import (
    AccountDivisionModel,
    AccountModel,
    ContactModel,
    TerritoryModel,
    TerritoryProvinceModel,
    UserModel,
)
from app.infrastructure.db.repositories.scope import scoped_accounts

ACCOUNT_SORT_FIELDS: set[str] = {"name", "city", "updated_at"}
ACCOUNT_DEFAULT_SORT = "name"
ACCOUNT_MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class AccountFilters:
    q: str | None = None
    account_type_id: UUID | None = None
    territory_id: UUID | None = None
    owner_id: UUID | None = None
    division_id: UUID | None = None
    is_active: bool | None = True
    unassigned: bool = False


@dataclass(frozen=True)
class AccountSummary:
    id: UUID
    name: str
    account_type_id: UUID
    city: str | None
    province_code: str
    territory_id: UUID | None
    territory_name: str | None
    owner_id: UUID | None
    owner_name: str | None
    is_active: bool
    territory_mismatch: bool
    primary_contact_name: str | None
    updated_at: datetime | None


@dataclass(frozen=True)
class AccountListResult:
    items: list[AccountSummary]
    total: int


def province_territory_subquery() -> Any:
    """Territory currently owning the account's province (for the mismatch flag)."""
    return (
        select(TerritoryProvinceModel.territory_id)
        .where(TerritoryProvinceModel.province_code == AccountModel.province_code)
        .correlate(AccountModel)
        .scalar_subquery()
    )


def primary_contact_subquery() -> Any:
    return (
        select(ContactModel.first_name + " " + ContactModel.last_name)
        .where(ContactModel.account_id == AccountModel.id, ContactModel.is_primary.is_(True))
        .correlate(AccountModel)
        .scalar_subquery()
    )


class AccountQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_page(
        self, params: PageParams, filters: AccountFilters, scope: ScopeFilter | None
    ) -> AccountListResult:
        base = scoped_accounts(self._apply_filters(select(AccountModel), filters), scope)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        statement = (
            select(
                AccountModel,
                province_territory_subquery().label("province_territory_id"),
                primary_contact_subquery().label("primary_contact_name"),
                TerritoryModel.name,
                UserModel.full_name,
            )
            .outerjoin(TerritoryModel, TerritoryModel.id == AccountModel.territory_id)
            .outerjoin(UserModel, UserModel.id == AccountModel.owner_id)
            .where(AccountModel.id.in_(select(base.subquery().c.id)))
            .order_by(*self._order_by(params))
            .offset(params.offset)
            .limit(params.limit)
        )
        rows = (await self._session.execute(statement)).all()
        return AccountListResult(
            items=[
                AccountSummary(
                    id=row[0].id,
                    name=row[0].name,
                    account_type_id=row[0].account_type_id,
                    city=row[0].city,
                    province_code=row[0].province_code,
                    territory_id=row[0].territory_id,
                    territory_name=row[3],
                    owner_id=row[0].owner_id,
                    owner_name=row[4],
                    is_active=row[0].is_active,
                    territory_mismatch=row[1] != row[0].territory_id,
                    primary_contact_name=row[2],
                    updated_at=row[0].updated_at,
                )
                for row in rows
            ],
            total=int(total or 0),
        )

    @staticmethod
    def _apply_filters(statement: Select[Any], filters: AccountFilters) -> Select[Any]:
        if filters.account_type_id is not None:
            statement = statement.where(AccountModel.account_type_id == filters.account_type_id)
        if filters.territory_id is not None:
            statement = statement.where(AccountModel.territory_id == filters.territory_id)
        if filters.owner_id is not None:
            statement = statement.where(AccountModel.owner_id == filters.owner_id)
        if filters.unassigned:
            statement = statement.where(AccountModel.owner_id.is_(None))
        if filters.is_active is not None:
            statement = statement.where(AccountModel.is_active.is_(filters.is_active))
        if filters.division_id is not None:
            statement = statement.where(
                exists(
                    select(1).where(
                        AccountDivisionModel.account_id == AccountModel.id,
                        AccountDivisionModel.division_id == filters.division_id,
                    )
                ).correlate(AccountModel)
            )
        if filters.q:
            statement = statement.where(_text_predicate(filters.q))
        return statement

    @staticmethod
    def _order_by(params: PageParams) -> list[ColumnElement[Any]]:
        columns = {
            "name": AccountModel.name,
            "city": AccountModel.city,
            "updated_at": AccountModel.updated_at,
        }
        clauses: list[ColumnElement[Any]] = []
        for field in params.sort:
            column = columns[field.name]
            ordered = column.desc() if field.descending else column.asc()
            clauses.append(ordered.nulls_last())  # empty cities never float to the top
        clauses.append(AccountModel.id.asc())
        return clauses


def _text_predicate(q: str) -> ColumnElement[bool]:
    term = q.strip()
    contains = f"%{term}%"
    clauses: list[ColumnElement[bool]] = [
        AccountModel.name.ilike(contains),
        AccountModel.city.ilike(contains),
    ]
    normalised = "".join(ch for ch in term.upper() if ch.isalnum())
    if normalised and is_valid_tax_id(normalised):
        clauses.append(AccountModel.tax_id == normalised)
    return or_(*clauses)
