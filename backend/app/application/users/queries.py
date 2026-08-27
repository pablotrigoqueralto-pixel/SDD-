"""Read side for users: paginated, filtered listing straight from the ORM models."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.shared.pagination import PageParams
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.models import UserModel, UserTerritoryModel
from app.infrastructure.db.repositories.users import user_to_entity

USER_SORT_FIELDS: set[str] = {"full_name", "email", "role", "created_at"}
USER_DEFAULT_SORT = "full_name"


@dataclass(frozen=True)
class UserFilters:
    role: Role | None = None
    is_active: bool | None = None
    territory_id: UUID | None = None
    q: str | None = None


@dataclass(frozen=True)
class UserListResult:
    items: list[User]
    total: int


class UserQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_page(self, params: PageParams, filters: UserFilters) -> UserListResult:
        base = self._apply_filters(select(UserModel), filters)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        statement = (
            base.options(
                selectinload(UserModel.territory_links), selectinload(UserModel.division_links)
            )
            .order_by(*self._order_by(params))
            .offset(params.offset)
            .limit(params.limit)
        )
        rows = (await self._session.execute(statement)).scalars().all()
        return UserListResult(items=[user_to_entity(row) for row in rows], total=int(total or 0))

    @staticmethod
    def _apply_filters(
        statement: Select[tuple[UserModel]], filters: UserFilters
    ) -> Select[tuple[UserModel]]:
        if filters.role is not None:
            statement = statement.where(UserModel.role == filters.role)
        if filters.is_active is not None:
            statement = statement.where(UserModel.is_active.is_(filters.is_active))
        if filters.territory_id is not None:
            statement = statement.where(
                UserModel.id.in_(
                    select(UserTerritoryModel.user_id).where(
                        UserTerritoryModel.territory_id == filters.territory_id
                    )
                )
            )
        if filters.q:
            prefix = f"{filters.q.strip()}%"
            statement = statement.where(
                or_(UserModel.full_name.ilike(prefix), UserModel.email.ilike(prefix))
            )
        return statement

    @staticmethod
    def _order_by(params: PageParams) -> list[ColumnElement[Any]]:
        columns = {
            "full_name": UserModel.full_name,
            "email": UserModel.email,
            "role": UserModel.role,
            "created_at": UserModel.created_at,
        }
        clauses: list[ColumnElement[Any]] = []
        for field in params.sort:
            column = columns[field.name]
            clauses.append(column.desc() if field.descending else column.asc())
        clauses.append(UserModel.id.asc())  # deterministic tiebreak
        return clauses
