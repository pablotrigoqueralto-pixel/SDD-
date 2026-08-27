"""Read side for territories (with active user counts)."""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import ColumnElement, Select, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.application.shared.pagination import PageParams
from app.domain.territories.entities import Territory
from app.infrastructure.db.models import TerritoryModel, UserModel, UserTerritoryModel
from app.infrastructure.db.repositories.territories import territory_to_entity

TERRITORY_SORT_FIELDS: set[str] = {"name", "created_at"}
TERRITORY_DEFAULT_SORT = "name"


@dataclass(frozen=True)
class TerritoryFilters:
    is_active: bool | None = None
    q: str | None = None


@dataclass(frozen=True)
class TerritoryWithCount:
    territory: Territory
    user_count: int


@dataclass(frozen=True)
class TerritoryListResult:
    items: list[TerritoryWithCount]
    total: int


class TerritoryQueries:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_page(self, params: PageParams, filters: TerritoryFilters) -> TerritoryListResult:
        base = self._apply_filters(select(TerritoryModel), filters)
        total = await self._session.scalar(select(func.count()).select_from(base.subquery()))
        statement = (
            base.options(selectinload(TerritoryModel.province_links))
            .order_by(*self._order_by(params))
            .offset(params.offset)
            .limit(params.limit)
        )
        rows = (await self._session.execute(statement)).scalars().all()
        counts = await self._user_counts([row.id for row in rows])
        return TerritoryListResult(
            items=[
                TerritoryWithCount(territory_to_entity(row), counts.get(row.id, 0)) for row in rows
            ],
            total=int(total or 0),
        )

    async def get(self, territory_id: UUID) -> TerritoryWithCount | None:
        statement = (
            select(TerritoryModel)
            .options(selectinload(TerritoryModel.province_links))
            .where(TerritoryModel.id == territory_id)
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        if row is None:
            return None
        counts = await self._user_counts([row.id])
        return TerritoryWithCount(territory_to_entity(row), counts.get(row.id, 0))

    async def _user_counts(self, territory_ids: list[UUID]) -> dict[UUID, int]:
        if not territory_ids:
            return {}
        statement = (
            select(UserTerritoryModel.territory_id, func.count())
            .join(UserModel, UserModel.id == UserTerritoryModel.user_id)
            .where(
                UserTerritoryModel.territory_id.in_(territory_ids), UserModel.is_active.is_(True)
            )
            .group_by(UserTerritoryModel.territory_id)
        )
        rows = (await self._session.execute(statement)).all()
        return {row[0]: int(row[1]) for row in rows}

    @staticmethod
    def _apply_filters(
        statement: Select[tuple[TerritoryModel]], filters: TerritoryFilters
    ) -> Select[tuple[TerritoryModel]]:
        if filters.is_active is not None:
            statement = statement.where(TerritoryModel.is_active.is_(filters.is_active))
        if filters.q:
            statement = statement.where(TerritoryModel.name.ilike(f"{filters.q.strip()}%"))
        return statement

    @staticmethod
    def _order_by(params: PageParams) -> list[ColumnElement[Any]]:
        columns = {"name": TerritoryModel.name, "created_at": TerritoryModel.created_at}
        clauses: list[ColumnElement[Any]] = []
        for field in params.sort:
            column = columns[field.name]
            clauses.append(column.desc() if field.descending else column.asc())
        clauses.append(TerritoryModel.id.asc())
        return clauses
