import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.shared.errors import ConcurrentModificationError
from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.errors import EmailAlreadyExistsError
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email
from app.infrastructure.db.repositories.territories import (
    SqlAlchemyDivisionRepository,
    SqlAlchemyTerritoryRepository,
)
from app.infrastructure.db.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.db.seed import DIVISIONS

pytestmark = pytest.mark.integration


def make_user(email: str = "ana@quermed.com", **overrides: object) -> User:
    return User.create(
        email=Email(email),
        full_name="Ana García",
        role=Role.SALES_REP,
        password_hash="hash",
        **overrides,  # type: ignore[arg-type]
    )


async def test_add_and_get_by_id_and_email_case_insensitive(session: AsyncSession) -> None:
    repo = SqlAlchemyUserRepository(session)
    user = make_user("Ana@Quermed.com")

    await repo.add(user)

    by_id = await repo.get(user.id)
    by_email = await repo.get_by_email(Email("ANA@QUERMED.COM"))
    assert by_id is not None and by_email is not None
    assert by_id.email == Email("ana@quermed.com")
    assert by_email.id == user.id
    assert by_id.version == 1
    assert by_id.created_at is not None


async def test_add_duplicate_email_raises(session: AsyncSession) -> None:
    repo = SqlAlchemyUserRepository(session)
    await repo.add(make_user("ana@quermed.com"))

    with pytest.raises(EmailAlreadyExistsError):
        await repo.add(make_user("ANA@quermed.com"))


async def test_save_with_expected_version_increments_and_conflicts(
    session: AsyncSession,
) -> None:
    repo = SqlAlchemyUserRepository(session)
    user = make_user()
    await repo.add(user)

    user.rename("Ana G.")
    await repo.save(user, expected_version=1)
    assert user.version == 2

    reloaded = await repo.get(user.id)
    assert reloaded is not None
    assert reloaded.full_name == "Ana G."
    assert reloaded.version == 2

    with pytest.raises(ConcurrentModificationError):
        await repo.save(user, expected_version=1)


async def test_scope_links_are_persisted_and_synced(session: AsyncSession) -> None:
    users = SqlAlchemyUserRepository(session)
    territories = SqlAlchemyTerritoryRepository(session)
    divisions = SqlAlchemyDivisionRepository(session)
    centro = Territory.create(name="Centro", provinces=frozenset({"28"}))
    norte = Territory.create(name="Norte", provinces=frozenset({"48"}))
    await territories.add(centro)
    await territories.add(norte)
    division_ids = await divisions.existing_ids([division.id for division in DIVISIONS])
    vascular = next(division.id for division in DIVISIONS if division.code == "vascular")
    assert vascular in division_ids

    user = make_user(territory_ids=frozenset({centro.id}), division_ids=frozenset({vascular}))
    await users.add(user)
    loaded = await users.get(user.id)
    assert loaded is not None
    assert loaded.territory_ids == frozenset({centro.id})
    assert loaded.division_ids == frozenset({vascular})
    assert await users.count_active_in_territory(centro.id) == 1

    user.assign_scope(territory_ids=frozenset({norte.id}), division_ids=frozenset())
    await users.save(user, expected_version=1)
    resynced = await users.get(user.id)
    assert resynced is not None
    assert resynced.territory_ids == frozenset({norte.id})
    assert resynced.division_ids == frozenset()
    assert await users.count_active_in_territory(centro.id) == 0
