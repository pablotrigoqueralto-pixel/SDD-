from datetime import UTC, datetime, timedelta

import pytest

from app.application.auth.providers import PasswordAuthProvider
from app.application.auth.service import AuthConfig, AuthService, ClientInfo
from app.application.auth.tokens import hash_refresh_token
from app.domain.shared.errors import UnauthenticatedError
from app.domain.users.entities import User
from app.domain.users.errors import (
    AccountLockedError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
    PasswordTooShortError,
)
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email
from app.infrastructure.security.jwt import AccessTokenCodec
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.fakes.security import FakePasswordHasher

SECRET = "unit-test-secret-unit-test-secret-0123456789"
EMAIL = Email("ana@quermed.com")
PASSWORD = "correct-horse-battery"
CLIENT = ClientInfo(user_agent="pytest", ip="10.0.0.1")


class FrozenClock:
    def __init__(self) -> None:
        self.now = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)

    def __call__(self) -> datetime:
        return self.now


@pytest.fixture
def uow() -> FakeUnitOfWork:
    return FakeUnitOfWork()


@pytest.fixture
def clock() -> FrozenClock:
    return FrozenClock()


@pytest.fixture
def service(uow: FakeUnitOfWork, clock: FrozenClock) -> AuthService:
    hasher = FakePasswordHasher()
    return AuthService(
        uow,
        provider=PasswordAuthProvider(hasher),
        hasher=hasher,
        codec=AccessTokenCodec(SECRET, 900, clock=clock),
        config=AuthConfig(max_failed_attempts=10, lockout=timedelta(minutes=15)),
        clock=clock,
    )


@pytest.fixture
async def user(uow: FakeUnitOfWork) -> User:
    user = User.create(
        email=EMAIL,
        full_name="Ana",
        role=Role.SALES_REP,
        password_hash=FakePasswordHasher().hash(PASSWORD),
    )
    await uow.users.add(user)
    return user


async def test_login_success_returns_tokens_and_audits(
    service: AuthService, uow: FakeUnitOfWork, user: User
) -> None:
    session = await service.login(EMAIL, PASSWORD, CLIENT)

    assert session.user.id == user.id
    assert session.expires_in == 900
    assert session.access_token
    stored = await uow.refresh_tokens.get_by_hash(hash_refresh_token(session.refresh_token))
    assert stored is not None and stored.user_id == user.id
    assert uow.actions() == ["auth.login_succeeded"]
    assert uow.committed_events[0].actor_id == user.id


async def test_login_wrong_password_counts_failure(
    service: AuthService, uow: FakeUnitOfWork, user: User
) -> None:
    with pytest.raises(InvalidCredentialsError):
        await service.login(EMAIL, "wrong-password-xx", CLIENT)

    stored = await uow.users.get(user.id)
    assert stored is not None and stored.failed_login_attempts == 1
    assert uow.actions() == ["auth.login_failed"]
    assert uow.committed_events[0].changes == {"ip": {"before": None, "after": "10.0.0.1"}}


async def test_login_unknown_email_is_indistinguishable(
    service: AuthService, uow: FakeUnitOfWork
) -> None:
    with pytest.raises(InvalidCredentialsError):
        await service.login(Email("nobody@quermed.com"), PASSWORD, CLIENT)

    assert uow.actions() == ["auth.login_failed"]
    assert uow.committed_events[0].entity_id is None


async def test_login_inactive_user_rejected(
    service: AuthService, uow: FakeUnitOfWork, user: User
) -> None:
    user.is_active = False
    await uow.users.save(user, expected_version=1)

    with pytest.raises(InvalidCredentialsError):
        await service.login(EMAIL, PASSWORD, CLIENT)


async def test_tenth_failure_locks_and_correct_password_is_rejected_until_unlock(
    service: AuthService, uow: FakeUnitOfWork, user: User, clock: FrozenClock
) -> None:
    for _ in range(10):
        with pytest.raises(InvalidCredentialsError):
            await service.login(EMAIL, "wrong-password-xx", CLIENT)

    assert "auth.locked_out" in uow.actions()
    with pytest.raises(AccountLockedError):
        await service.login(EMAIL, PASSWORD, CLIENT)

    clock.now += timedelta(minutes=15)
    session = await service.login(EMAIL, PASSWORD, CLIENT)
    assert session.user.failed_login_attempts == 0


async def test_success_resets_failure_counter(
    service: AuthService, uow: FakeUnitOfWork, user: User
) -> None:
    for _ in range(3):
        with pytest.raises(InvalidCredentialsError):
            await service.login(EMAIL, "wrong-password-xx", CLIENT)

    await service.login(EMAIL, PASSWORD, CLIENT)

    stored = await uow.users.get(user.id)
    assert stored is not None and stored.failed_login_attempts == 0


async def test_refresh_rotates_token(service: AuthService, uow: FakeUnitOfWork, user: User) -> None:
    first = await service.login(EMAIL, PASSWORD, CLIENT)

    second = await service.refresh(first.refresh_token, CLIENT)

    assert second.refresh_token != first.refresh_token
    old = await uow.refresh_tokens.get_by_hash(hash_refresh_token(first.refresh_token))
    assert old is not None and old.was_already_used()
    new = await uow.refresh_tokens.get_by_hash(hash_refresh_token(second.refresh_token))
    assert new is not None and old.replaced_by_id == new.id


async def test_refresh_reuse_revokes_whole_family(
    service: AuthService, uow: FakeUnitOfWork, user: User
) -> None:
    first = await service.login(EMAIL, PASSWORD, CLIENT)
    second = await service.refresh(first.refresh_token, CLIENT)

    with pytest.raises(UnauthenticatedError):
        await service.refresh(first.refresh_token, CLIENT)

    with pytest.raises(UnauthenticatedError):
        await service.refresh(second.refresh_token, CLIENT)
    assert "auth.refresh_reuse_detected" in uow.actions()


async def test_refresh_expired_token_rejected(
    service: AuthService, uow: FakeUnitOfWork, user: User, clock: FrozenClock
) -> None:
    session = await service.login(EMAIL, PASSWORD, CLIENT)
    clock.now += timedelta(days=31)

    with pytest.raises(UnauthenticatedError):
        await service.refresh(session.refresh_token, CLIENT)


async def test_refresh_unknown_token_rejected(service: AuthService) -> None:
    with pytest.raises(UnauthenticatedError):
        await service.refresh("nope", CLIENT)


async def test_logout_revokes_token(service: AuthService, uow: FakeUnitOfWork, user: User) -> None:
    session = await service.login(EMAIL, PASSWORD, CLIENT)

    await service.logout(session.refresh_token, actor_id=user.id)

    with pytest.raises(UnauthenticatedError):
        await service.refresh(session.refresh_token, CLIENT)
    assert uow.actions()[-1] == "auth.logout"


async def test_change_password_revokes_other_sessions_and_redacts_audit(
    service: AuthService, uow: FakeUnitOfWork, user: User
) -> None:
    phone = await service.login(EMAIL, PASSWORD, CLIENT)
    laptop = await service.login(EMAIL, PASSWORD, CLIENT)

    await service.change_password(
        user.id,
        current_password=PASSWORD,
        new_password="new-passphrase-2026",
        keep_refresh_token=laptop.refresh_token,
    )

    with pytest.raises(UnauthenticatedError):
        await service.refresh(phone.refresh_token, CLIENT)
    await service.refresh(laptop.refresh_token, CLIENT)
    await service.login(EMAIL, "new-passphrase-2026", CLIENT)
    event = next(e for e in uow.committed_events if e.action == "user.password_changed")
    assert event.changes == {"password_hash": {"before": "[redacted]", "after": "[redacted]"}}


async def test_change_password_rejects_wrong_current(service: AuthService, user: User) -> None:
    with pytest.raises(InvalidCurrentPasswordError):
        await service.change_password(
            user.id,
            current_password="nope",
            new_password="new-passphrase-2026",
            keep_refresh_token=None,
        )


async def test_change_password_rejects_short_new(service: AuthService, user: User) -> None:
    with pytest.raises(PasswordTooShortError):
        await service.change_password(
            user.id, current_password=PASSWORD, new_password="short", keep_refresh_token=None
        )


def test_access_token_claims_round_trip(clock: FrozenClock, user: User) -> None:
    codec = AccessTokenCodec(SECRET, 900, clock=clock)

    token = codec.issue(user_id=user.id, role=Role.ADMIN)
    claims = codec.verify(token)

    assert claims.user_id == user.id
    assert claims.role == Role.ADMIN
    assert claims.expires_at == clock.now + timedelta(seconds=900)


def test_access_token_expired_or_tampered_is_unauthenticated(
    clock: FrozenClock, user: User
) -> None:
    codec = AccessTokenCodec(SECRET, 900, clock=clock)
    token = codec.issue(user_id=user.id, role=Role.ADMIN)

    with pytest.raises(UnauthenticatedError):
        AccessTokenCodec("another-secret-another-secret-0123456789", 900).verify(token)
    with pytest.raises(UnauthenticatedError):
        codec.verify(token + "x")

    clock.now += timedelta(seconds=901)
    with pytest.raises(UnauthenticatedError):
        AccessTokenCodec(SECRET, 900, clock=clock).verify(token)
