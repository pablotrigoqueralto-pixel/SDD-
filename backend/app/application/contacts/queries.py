"""Read side for the global contacts list: scoped through the account, cumulative filters."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.shared.pagination import PageParams
from app.domain.shared.policies import ScopeFilter
from app.infrastructure.db.models import AccountModel, ContactModel, ContactPhoneModel
from app.infrastructure.db.repositories.scope import account_scope_predicate

CONTACT_SORT_FIELDS: set[str] = {"last_name", "first_name", "account_name", "updated_at"}
CONTACT_DEFAULT_SORT = "last_name"
CONTACT_MAX_PAGE_SIZE = 100


@dataclass(frozen=True)
class ContactFilters:
    """Repeated values of one filter combine with OR, different filters with AND."""

    q: str | None = None
    specialty_ids: list[UUID] = field(default_factory=list)
    account_ids: list[UUID] = field(default_factory=list)
    job_title_id: UUID | None = None
    is_head_of_department: bool | None = None
    is_active: bool | None = True


@dataclass(frozen=True)
class ContactSummary:
    id: UUID
    first_name: str
    last_name: str
    account_id: UUID
    account_name: str
    job_title_id: UUID | None
    specialty_id: UUID | None
    is_head_of_department: bool
    primary_phone: str | None
    email: str | None
    is_active: bool


@dataclass(frozen=True)
class ContactListResult:
    items: list[ContactSummary]
    total: int


def primary_phone_subquery() -> Any:
    """The contact's first labelled phone: what the list shows and dials."""
    return (
        select(ContactPhoneModel.number)
        .where(ContactPhoneModel.contact_id == ContactModel.id)
        .order_by(ContactPhoneModel.sort_order)
        .limit(1)
        .correlate(ContactModel)
        .scalar_subquery()
    )


class ContactQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_page(
        self, params: PageParams, filters: ContactFilters, scope: ScopeFilter | None
    ) -> ContactListResult:
        base = self._apply_filters(
            select(ContactModel.id)
            .join(AccountModel, AccountModel.id == ContactModel.account_id)
            .where(account_scope_predicate(scope)),
            filters,
        )
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        statement = (
            select(ContactModel, AccountModel.name, primary_phone_subquery().label("primary_phone"))
            .join(AccountModel, AccountModel.id == ContactModel.account_id)
            .where(ContactModel.id.in_(base))
            .order_by(*self._order_by(params))
            .offset(params.offset)
            .limit(params.limit)
        )
        rows = (await self._session.execute(statement)).all()
        return ContactListResult(
            items=[
                ContactSummary(
                    id=row[0].id,
                    first_name=row[0].first_name,
                    last_name=row[0].last_name,
                    account_id=row[0].account_id,
                    account_name=row[1],
                    job_title_id=row[0].job_title_id,
                    specialty_id=row[0].specialty_id,
                    is_head_of_department=row[0].is_head_of_department,
                    primary_phone=row[2],
                    email=row[0].email,
                    is_active=row[0].is_active,
                )
                for row in rows
            ],
            total=int(total or 0),
        )

    @staticmethod
    def _apply_filters(statement: Select[Any], filters: ContactFilters) -> Select[Any]:
        if filters.specialty_ids:
            statement = statement.where(ContactModel.specialty_id.in_(filters.specialty_ids))
        if filters.account_ids:
            statement = statement.where(ContactModel.account_id.in_(filters.account_ids))
        if filters.job_title_id is not None:
            statement = statement.where(ContactModel.job_title_id == filters.job_title_id)
        if filters.is_head_of_department is not None:
            statement = statement.where(
                ContactModel.is_head_of_department.is_(filters.is_head_of_department)
            )
        if filters.is_active is not None:
            statement = statement.where(ContactModel.is_active.is_(filters.is_active))
        if filters.q:
            statement = statement.where(_name_predicate(filters.q))
        return statement

    @staticmethod
    def _order_by(params: PageParams) -> list[ColumnElement[Any]]:
        # Names sort unaccented and case-folded: the database collation would otherwise
        # push "Álvarez" behind "Zamora", which reads as a bug to a Spanish user.
        columns: dict[str, Any] = {
            "last_name": _sortable(ContactModel.last_name),
            "first_name": _sortable(ContactModel.first_name),
            "account_name": _sortable(AccountModel.name),
            "updated_at": ContactModel.updated_at,
        }
        clauses: list[ColumnElement[Any]] = []
        for sort_field in params.sort:
            column = columns[sort_field.name]
            ordered = column.desc() if sort_field.descending else column.asc()
            clauses.append(ordered.nulls_last())
        if not any(f.name == "first_name" for f in params.sort):
            clauses.append(_sortable(ContactModel.first_name).asc())
        clauses.append(ContactModel.id.asc())
        return clauses


def _sortable(column: Any) -> Any:
    return func.lower(func.f_unaccent(column))


def _name_predicate(q: str) -> ColumnElement[bool]:
    """Accent- and case-insensitive over first name, last name and the full name."""
    term = f"%{q.strip()}%"
    full_name = ContactModel.first_name + " " + ContactModel.last_name
    return or_(
        func.f_unaccent(ContactModel.first_name).ilike(func.f_unaccent(term)),
        func.f_unaccent(ContactModel.last_name).ilike(func.f_unaccent(term)),
        func.f_unaccent(full_name).ilike(func.f_unaccent(term)),
    )
