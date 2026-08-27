"""Repository protocols for territories and divisions."""

from collections.abc import Iterable
from typing import Protocol
from uuid import UUID

from app.domain.territories.entities import Division, Territory


class TerritoryRepository(Protocol):
    async def get(self, territory_id: UUID) -> Territory | None: ...

    async def get_many(self, ids: Iterable[UUID]) -> list[Territory]: ...

    async def list_all(self) -> list[Territory]: ...

    async def add(self, territory: Territory) -> None: ...

    async def save(self, territory: Territory, *, expected_version: int) -> None: ...

    async def existing_ids(self, ids: Iterable[UUID]) -> frozenset[UUID]: ...


class DivisionRepository(Protocol):
    async def list_all(self) -> list[Division]: ...

    async def existing_ids(self, ids: Iterable[UUID]) -> frozenset[UUID]: ...
