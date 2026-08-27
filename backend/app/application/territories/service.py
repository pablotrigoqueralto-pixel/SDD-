"""Territory administration use cases."""

from dataclasses import dataclass
from uuid import UUID

from app.application.shared.unit_of_work import UnitOfWork
from app.application.users.commands import UNSET
from app.domain.shared.audit import diff_fields
from app.domain.shared.errors import NotFoundError
from app.domain.territories.entities import Territory


@dataclass(frozen=True)
class CreateTerritory:
    name: str
    provinces: frozenset[str]


@dataclass(frozen=True)
class UpdateTerritory:
    expected_version: int
    name: str | object = UNSET
    provinces: frozenset[str] | object = UNSET
    is_active: bool | object = UNSET


def _snapshot(territory: Territory) -> dict[str, object]:
    return {
        "name": territory.name,
        "provinces": territory.provinces,
        "is_active": territory.is_active,
    }


class TerritoryService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    async def create(self, command: CreateTerritory, *, acting_user_id: UUID) -> Territory:
        async with self._uow as uow:
            territory = Territory.create(name=command.name, provinces=command.provinces)
            await uow.territories.add(territory)
            uow.audit.record(
                entity_type="territory",
                entity_id=territory.id,
                action="territory.created",
                changes=diff_fields({}, _snapshot(territory)),
                actor_id=acting_user_id,
            )
            await uow.commit()
            return territory

    async def update(
        self, territory_id: UUID, command: UpdateTerritory, *, acting_user_id: UUID
    ) -> Territory:
        async with self._uow as uow:
            territory = await uow.territories.get(territory_id)
            if territory is None:
                raise NotFoundError("Territory not found")
            before = _snapshot(territory)
            if isinstance(command.name, str):
                territory.rename(command.name)
            if isinstance(command.provinces, frozenset):
                territory.set_provinces(command.provinces)
            if isinstance(command.is_active, bool):
                if command.is_active:
                    territory.activate()
                else:
                    active_users = await uow.users.count_active_in_territory(territory.id)
                    territory.deactivate(active_user_count=active_users)
            await uow.territories.save(territory, expected_version=command.expected_version)
            changes = diff_fields(before, _snapshot(territory))
            if changes:
                uow.audit.record(
                    entity_type="territory",
                    entity_id=territory.id,
                    action="territory.updated",
                    changes=changes,
                    actor_id=acting_user_id,
                )
            await uow.commit()
            return territory
