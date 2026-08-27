import pytest

from app.application.territories.service import (
    CreateTerritory,
    TerritoryService,
    UpdateTerritory,
)
from app.domain.shared.errors import ConcurrentModificationError, NotFoundError
from app.domain.shared.ids import new_id
from app.domain.territories.errors import (
    InvalidProvinceError,
    ProvinceAlreadyAssignedError,
    TerritoryInUseError,
)
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email
from tests.unit.fakes import FakeUnitOfWork

ADMIN_ID = new_id()


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def service(uow: FakeUnitOfWork) -> TerritoryService:
    return TerritoryService(uow)


async def test_create_territory_audits(service: TerritoryService, uow: FakeUnitOfWork) -> None:
    territory = await service.create(
        CreateTerritory(name="Centro", provinces=frozenset({"28", "45"})), acting_user_id=ADMIN_ID
    )

    assert territory.provinces == frozenset({"28", "45"})
    assert uow.actions() == ["territory.created"]
    assert uow.committed_events[0].changes["provinces"] == {"before": None, "after": ["28", "45"]}


async def test_create_rejects_invalid_province(service: TerritoryService) -> None:
    with pytest.raises(InvalidProvinceError):
        await service.create(
            CreateTerritory(name="X", provinces=frozenset({"99"})), acting_user_id=ADMIN_ID
        )


async def test_create_rejects_province_owned_by_another_territory(
    service: TerritoryService,
) -> None:
    await service.create(
        CreateTerritory(name="Centro", provinces=frozenset({"28"})), acting_user_id=ADMIN_ID
    )

    with pytest.raises(ProvinceAlreadyAssignedError) as exc_info:
        await service.create(
            CreateTerritory(name="Sur", provinces=frozenset({"28"})), acting_user_id=ADMIN_ID
        )

    assert exc_info.value.territory_name == "Centro"


async def test_update_changes_and_audits_only_when_something_changed(
    service: TerritoryService, uow: FakeUnitOfWork
) -> None:
    territory = await service.create(
        CreateTerritory(name="Centro", provinces=frozenset({"28"})), acting_user_id=ADMIN_ID
    )

    updated = await service.update(
        territory.id,
        UpdateTerritory(expected_version=1, provinces=frozenset({"28", "45"})),
        acting_user_id=ADMIN_ID,
    )
    unchanged = await service.update(
        territory.id, UpdateTerritory(expected_version=2), acting_user_id=ADMIN_ID
    )

    assert updated.version == 2 and unchanged.version == 3
    assert uow.actions() == ["territory.created", "territory.updated"]


async def test_update_stale_version_conflicts(service: TerritoryService) -> None:
    territory = await service.create(
        CreateTerritory(name="Centro", provinces=frozenset({"28"})), acting_user_id=ADMIN_ID
    )

    with pytest.raises(ConcurrentModificationError):
        await service.update(
            territory.id, UpdateTerritory(expected_version=5, name="X"), acting_user_id=ADMIN_ID
        )


async def test_update_unknown_territory(service: TerritoryService) -> None:
    with pytest.raises(NotFoundError):
        await service.update(
            new_id(), UpdateTerritory(expected_version=1, name="X"), acting_user_id=ADMIN_ID
        )


async def test_deactivate_with_active_users_is_rejected(
    service: TerritoryService, uow: FakeUnitOfWork
) -> None:
    territory = await service.create(
        CreateTerritory(name="Centro", provinces=frozenset({"28"})), acting_user_id=ADMIN_ID
    )
    rep = User.create(
        email=Email("rep@quermed.com"),
        full_name="Rep",
        role=Role.SALES_REP,
        password_hash="h",
        territory_ids=frozenset({territory.id}),
    )
    await uow.users.add(rep)

    with pytest.raises(TerritoryInUseError) as exc_info:
        await service.update(
            territory.id,
            UpdateTerritory(expected_version=1, is_active=False),
            acting_user_id=ADMIN_ID,
        )

    assert exc_info.value.active_user_count == 1


async def test_deactivate_without_users(service: TerritoryService) -> None:
    territory = await service.create(
        CreateTerritory(name="Centro", provinces=frozenset({"28"})), acting_user_id=ADMIN_ID
    )

    updated = await service.update(
        territory.id, UpdateTerritory(expected_version=1, is_active=False), acting_user_id=ADMIN_ID
    )

    assert updated.is_active is False
