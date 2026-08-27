import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.territories.entities import Territory
from app.domain.territories.errors import (
    ProvinceAlreadyAssignedError,
    TerritoryNameAlreadyExistsError,
)
from app.infrastructure.db.repositories.territories import SqlAlchemyTerritoryRepository

pytestmark = pytest.mark.integration


async def test_add_get_and_list(session: AsyncSession) -> None:
    repo = SqlAlchemyTerritoryRepository(session)
    centro = Territory.create(name="Centro", provinces=frozenset({"28", "45"}))

    await repo.add(centro)

    loaded = await repo.get(centro.id)
    assert loaded is not None
    assert loaded.provinces == frozenset({"28", "45"})
    assert [territory.id for territory in await repo.list_all()] == [centro.id]
    assert await repo.existing_ids([centro.id]) == frozenset({centro.id})


async def test_province_uniqueness_reports_owning_territory(session: AsyncSession) -> None:
    repo = SqlAlchemyTerritoryRepository(session)
    await repo.add(Territory.create(name="Centro", provinces=frozenset({"28"})))

    with pytest.raises(ProvinceAlreadyAssignedError) as exc_info:
        await repo.add(Territory.create(name="Sur", provinces=frozenset({"28", "41"})))

    assert exc_info.value.province_code == "28"
    assert exc_info.value.territory_name == "Centro"


async def test_name_uniqueness_is_case_insensitive(session: AsyncSession) -> None:
    repo = SqlAlchemyTerritoryRepository(session)
    await repo.add(Territory.create(name="Centro", provinces=frozenset({"28"})))

    with pytest.raises(TerritoryNameAlreadyExistsError):
        await repo.add(Territory.create(name="CENTRO", provinces=frozenset({"45"})))


async def test_save_replaces_provinces(session: AsyncSession) -> None:
    repo = SqlAlchemyTerritoryRepository(session)
    centro = Territory.create(name="Centro", provinces=frozenset({"28"}))
    await repo.add(centro)

    centro.set_provinces(frozenset({"45", "19"}))
    await repo.save(centro, expected_version=1)

    loaded = await repo.get(centro.id)
    assert loaded is not None
    assert loaded.provinces == frozenset({"45", "19"})
    assert loaded.version == 2
