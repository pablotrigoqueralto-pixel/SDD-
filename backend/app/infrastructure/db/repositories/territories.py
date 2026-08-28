"""SQLAlchemy implementations of TerritoryRepository and DivisionRepository."""

import re
from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.shared.errors import ConcurrentModificationError
from app.domain.territories.entities import Division, Territory
from app.domain.territories.errors import (
    ProvinceAlreadyAssignedError,
    TerritoryNameAlreadyExistsError,
)
from app.infrastructure.db.models import DivisionModel, TerritoryModel, TerritoryProvinceModel
from app.infrastructure.db.repositories.results import rowcount_of

PROVINCE_UNIQUE_CONSTRAINT = "uq_territory_provinces_province_code"
NAME_UNIQUE_CONSTRAINT = "territories_name_key"
PROVINCE_KEY_PATTERN = re.compile(r"\(province_code\)=\((\d{2})\)")


def territory_to_entity(row: TerritoryModel) -> Territory:
    return Territory(
        id=row.id,
        name=row.name,
        provinces=frozenset(link.province_code for link in row.province_links),
        is_active=row.is_active,
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


class SqlAlchemyTerritoryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, territory_id: UUID) -> Territory | None:
        statement = (
            select(TerritoryModel)
            .options(selectinload(TerritoryModel.province_links))
            .where(TerritoryModel.id == territory_id)
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return territory_to_entity(row) if row else None

    async def get_many(self, ids: Iterable[UUID]) -> list[Territory]:
        wanted = list(set(ids))
        if not wanted:
            return []
        statement = (
            select(TerritoryModel)
            .options(selectinload(TerritoryModel.province_links))
            .where(TerritoryModel.id.in_(wanted))
        )
        rows = (await self._session.execute(statement)).scalars().all()
        return [territory_to_entity(row) for row in rows]

    async def list_all(self) -> list[Territory]:
        statement = (
            select(TerritoryModel)
            .options(selectinload(TerritoryModel.province_links))
            .order_by(TerritoryModel.name)
        )
        rows = (await self._session.execute(statement)).scalars().all()
        return [territory_to_entity(row) for row in rows]

    async def add(self, territory: Territory) -> None:
        await self._ensure_provinces_free(territory)
        row = TerritoryModel(id=territory.id, name=territory.name, is_active=territory.is_active)
        row.province_links = [
            TerritoryProvinceModel(territory_id=territory.id, province_code=code)
            for code in territory.provinces
        ]
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            await self._raise_domain_error(exc, territory)

    async def save(self, territory: Territory, *, expected_version: int) -> None:
        await self._ensure_provinces_free(territory)
        statement = (
            update(TerritoryModel)
            .where(TerritoryModel.id == territory.id, TerritoryModel.version == expected_version)
            .values(
                name=territory.name,
                is_active=territory.is_active,
                version=expected_version + 1,
            )
        )
        try:
            result = await self._session.execute(statement)
            if rowcount_of(result) != 1:
                raise ConcurrentModificationError()
            await self._session.execute(
                delete(TerritoryProvinceModel).where(
                    TerritoryProvinceModel.territory_id == territory.id
                )
            )
            if territory.provinces:
                await self._session.execute(
                    insert(TerritoryProvinceModel),
                    [
                        {"territory_id": territory.id, "province_code": code}
                        for code in territory.provinces
                    ],
                )
        except IntegrityError as exc:
            await self._raise_domain_error(exc, territory)
        territory.version = expected_version + 1

    async def existing_ids(self, ids: Iterable[UUID]) -> frozenset[UUID]:
        wanted = list(set(ids))
        if not wanted:
            return frozenset()
        statement = select(TerritoryModel.id).where(TerritoryModel.id.in_(wanted))
        return frozenset((await self._session.execute(statement)).scalars().all())

    async def find_by_province(self, province_code: str) -> Territory | None:
        statement = (
            select(TerritoryModel)
            .options(selectinload(TerritoryModel.province_links))
            .join(TerritoryProvinceModel, TerritoryProvinceModel.territory_id == TerritoryModel.id)
            .where(TerritoryProvinceModel.province_code == province_code)
        )
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return territory_to_entity(row) if row else None

    async def _ensure_provinces_free(self, territory: Territory) -> None:
        """Explicit pre-check so the conflict can name the owning territory (the unique
        constraint remains the guarantee under concurrency)."""
        if not territory.provinces:
            return
        statement = (
            select(TerritoryProvinceModel.province_code, TerritoryModel.name)
            .join(TerritoryModel, TerritoryModel.id == TerritoryProvinceModel.territory_id)
            .where(
                TerritoryProvinceModel.province_code.in_(list(territory.provinces)),
                TerritoryModel.id != territory.id,
            )
            .order_by(TerritoryProvinceModel.province_code)
            .limit(1)
        )
        owner = (await self._session.execute(statement)).first()
        if owner is not None:
            raise ProvinceAlreadyAssignedError(owner.province_code, owner.name)

    async def _raise_domain_error(self, exc: IntegrityError, territory: Territory) -> None:
        message = str(exc.orig)
        if NAME_UNIQUE_CONSTRAINT in message:
            raise TerritoryNameAlreadyExistsError() from exc
        if PROVINCE_UNIQUE_CONSTRAINT in message:
            match = PROVINCE_KEY_PATTERN.search(message)
            code = match.group(1) if match else sorted(territory.provinces)[0]
            raise ProvinceAlreadyAssignedError(code, "another territory") from exc
        raise exc


class SqlAlchemyDivisionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_all(self) -> list[Division]:
        statement = select(DivisionModel).order_by(DivisionModel.sort_order)
        rows = (await self._session.execute(statement)).scalars().all()
        return [
            Division(id=row.id, code=row.code, name_es=row.name_es, sort_order=row.sort_order)
            for row in rows
        ]

    async def existing_ids(self, ids: Iterable[UUID]) -> frozenset[UUID]:
        wanted = list(set(ids))
        if not wanted:
            return frozenset()
        statement = select(DivisionModel.id).where(DivisionModel.id.in_(wanted))
        return frozenset((await self._session.execute(statement)).scalars().all())
