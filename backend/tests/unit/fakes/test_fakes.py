"""The fakes must honour protocol semantics (LSP) — a few guard tests."""

import pytest

from app.domain.shared.errors import ConcurrentModificationError
from app.domain.territories.entities import Territory
from app.domain.territories.errors import ProvinceAlreadyAssignedError
from app.domain.users.entities import User
from app.domain.users.errors import EmailAlreadyExistsError
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email
from tests.unit.fakes import FakeUnitOfWork


def make_user(email: str) -> User:
    return User.create(email=Email(email), full_name="X", role=Role.SALES_REP, password_hash="h")


async def test_user_repository_rejects_duplicate_email_case_insensitively() -> None:
    uow = FakeUnitOfWork()
    await uow.users.add(make_user("ana@quermed.com"))

    with pytest.raises(EmailAlreadyExistsError):
        await uow.users.add(make_user("ANA@quermed.com"))


async def test_user_repository_save_enforces_version() -> None:
    uow = FakeUnitOfWork()
    user = make_user("ana@quermed.com")
    await uow.users.add(user)

    await uow.users.save(user, expected_version=1)
    assert user.version == 2

    with pytest.raises(ConcurrentModificationError):
        await uow.users.save(user, expected_version=1)


async def test_territory_repository_rejects_overlapping_provinces() -> None:
    uow = FakeUnitOfWork()
    await uow.territories.add(Territory.create(name="Centro", provinces=frozenset({"28"})))

    with pytest.raises(ProvinceAlreadyAssignedError) as exc_info:
        await uow.territories.add(Territory.create(name="Sur", provinces=frozenset({"28", "41"})))

    assert exc_info.value.province_code == "28"
    assert exc_info.value.territory_name == "Centro"


async def test_unit_of_work_drains_audit_on_commit_and_discards_on_rollback() -> None:
    uow = FakeUnitOfWork()
    uow.audit.record(entity_type="user", entity_id=None, action="a")
    await uow.commit()
    uow.audit.record(entity_type="user", entity_id=None, action="b")
    await uow.rollback()

    assert uow.actions() == ["a"]
