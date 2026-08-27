from datetime import timedelta

import pytest

from app.application.users.commands import CreateUser, UpdateUser
from app.application.users.service import UserService
from app.domain.shared.errors import ConcurrentModificationError, NotFoundError
from app.domain.shared.ids import new_id
from app.domain.territories.entities import Division, Territory
from app.domain.users.entities import RefreshToken
from app.domain.users.errors import (
    CannotDemoteSelfError,
    EmailAlreadyExistsError,
    PasswordTooShortError,
    UnknownReferenceError,
)
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.fakes.repositories import InMemoryDivisionRepository
from tests.unit.fakes.security import FakePasswordHasher

ADMIN_ID = new_id()
VASCULAR = Division(id=new_id(), code="vascular", name_es="Vascular", sort_order=40)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.divisions = InMemoryDivisionRepository([VASCULAR])
    return uow


@pytest.fixture
async def centro(uow: FakeUnitOfWork) -> Territory:
    territory = Territory.create(name="Centro", provinces=frozenset({"28"}))
    await uow.territories.add(territory)
    return territory


@pytest.fixture
def service(uow: FakeUnitOfWork) -> UserService:
    return UserService(uow, hasher=FakePasswordHasher())


def create_command(**overrides: object) -> CreateUser:
    values: dict[str, object] = {
        "email": "Ana@Quermed.com",
        "full_name": " Ana García ",
        "role": Role.SALES_REP,
        "password": "correct-horse-battery",
    }
    values.update(overrides)
    return CreateUser(**values)  # type: ignore[arg-type]


async def test_create_user_hashes_password_and_audits(
    service: UserService, uow: FakeUnitOfWork, centro: Territory
) -> None:
    user = await service.create(
        create_command(territory_ids=frozenset({centro.id}), division_ids=frozenset({VASCULAR.id})),
        acting_user_id=ADMIN_ID,
    )

    assert user.email == Email("ana@quermed.com")
    assert user.full_name == "Ana García"
    assert user.password_hash == "hashed:correct-horse-battery"
    assert uow.actions() == ["user.created"]
    event = uow.committed_events[0]
    assert event.actor_id == ADMIN_ID
    assert event.changes["password_hash"] == {"before": "[redacted]", "after": "[redacted]"}
    assert event.changes["role"] == {"before": None, "after": "sales_rep"}


async def test_create_user_rejects_unknown_territory(service: UserService) -> None:
    with pytest.raises(UnknownReferenceError) as exc_info:
        await service.create(
            create_command(territory_ids=frozenset({new_id()})), acting_user_id=ADMIN_ID
        )

    assert exc_info.value.errors[0]["field"] == "territory_ids"
    assert exc_info.value.errors[0]["code"] == "unknown_reference"


async def test_create_user_rejects_unknown_division(service: UserService) -> None:
    with pytest.raises(UnknownReferenceError) as exc_info:
        await service.create(
            create_command(division_ids=frozenset({new_id()})), acting_user_id=ADMIN_ID
        )

    assert exc_info.value.errors[0]["field"] == "division_ids"


async def test_create_user_rejects_duplicate_email(service: UserService) -> None:
    await service.create(create_command(), acting_user_id=ADMIN_ID)

    with pytest.raises(EmailAlreadyExistsError):
        await service.create(create_command(email="ANA@quermed.com"), acting_user_id=ADMIN_ID)


async def test_create_user_rejects_short_password(service: UserService) -> None:
    with pytest.raises(PasswordTooShortError) as exc_info:
        await service.create(create_command(password="short"), acting_user_id=ADMIN_ID)

    assert exc_info.value.errors[0]["field"] == "password"


async def test_update_changes_fields_with_version_and_audits(
    service: UserService, uow: FakeUnitOfWork, centro: Territory
) -> None:
    user = await service.create(create_command(), acting_user_id=ADMIN_ID)

    updated = await service.update(
        user.id,
        UpdateUser(
            expected_version=1,
            full_name="Ana G.",
            role=Role.SALES_MANAGER,
            territory_ids=frozenset({centro.id}),
        ),
        acting_user_id=ADMIN_ID,
    )

    assert updated.version == 2
    assert updated.role == Role.SALES_MANAGER
    assert updated.territory_ids == frozenset({centro.id})
    actions = uow.actions()
    assert "user.scope_changed" in actions
    assert "user.updated" in actions
    updated_event = next(e for e in uow.committed_events if e.action == "user.updated")
    assert updated_event.changes["role"] == {"before": "sales_rep", "after": "sales_manager"}
    assert "territory_ids" not in updated_event.changes


async def test_update_with_stale_version_conflicts(service: UserService) -> None:
    user = await service.create(create_command(), acting_user_id=ADMIN_ID)

    with pytest.raises(ConcurrentModificationError):
        await service.update(
            user.id, UpdateUser(expected_version=99, full_name="X"), acting_user_id=ADMIN_ID
        )


async def test_update_unknown_user_is_not_found(service: UserService) -> None:
    with pytest.raises(NotFoundError):
        await service.update(
            new_id(), UpdateUser(expected_version=1, full_name="X"), acting_user_id=ADMIN_ID
        )


async def test_admin_cannot_deactivate_or_demote_self(service: UserService) -> None:
    admin = await service.create(create_command(role=Role.ADMIN), acting_user_id=ADMIN_ID)

    with pytest.raises(CannotDemoteSelfError):
        await service.update(
            admin.id, UpdateUser(expected_version=1, is_active=False), acting_user_id=admin.id
        )
    with pytest.raises(CannotDemoteSelfError):
        await service.update(
            admin.id, UpdateUser(expected_version=1, role=Role.SALES_REP), acting_user_id=admin.id
        )


async def test_deactivation_revokes_refresh_tokens_and_audits(
    service: UserService, uow: FakeUnitOfWork
) -> None:
    user = await service.create(create_command(), acting_user_id=ADMIN_ID)
    token = RefreshToken.issue(
        user_id=user.id, token_hash="h", ttl=timedelta(days=1), user_agent=None, ip=None
    )
    await uow.refresh_tokens.add(token)

    await service.update(
        user.id, UpdateUser(expected_version=1, is_active=False), acting_user_id=ADMIN_ID
    )

    stored = await uow.refresh_tokens.get_by_hash("h")
    assert stored is not None and stored.revoked_at is not None
    assert "user.deactivated" in uow.actions()


async def test_password_reset_revokes_tokens_and_never_logs_values(
    service: UserService, uow: FakeUnitOfWork
) -> None:
    user = await service.create(create_command(), acting_user_id=ADMIN_ID)

    await service.update(
        user.id,
        UpdateUser(expected_version=1, password="another-passphrase"),
        acting_user_id=ADMIN_ID,
    )

    reset = next(e for e in uow.committed_events if e.action == "user.password_reset")
    assert "another-passphrase" not in str(reset.changes)
    assert not any("hashed:" in str(e.changes) for e in uow.committed_events)


async def test_rename_self(service: UserService, uow: FakeUnitOfWork) -> None:
    user = await service.create(create_command(), acting_user_id=ADMIN_ID)

    renamed = await service.rename_self(user.id, "  Ana María ", expected_version=1)

    assert renamed.full_name == "Ana María"
    assert uow.actions()[-1] == "user.updated"
