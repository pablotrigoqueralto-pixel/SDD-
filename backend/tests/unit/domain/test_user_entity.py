from datetime import UTC, datetime, timedelta

import pytest

from app.domain.shared.ids import new_id
from app.domain.users.entities import RefreshToken, User
from app.domain.users.errors import CannotDemoteSelfError
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email

NOW = datetime(2026, 8, 27, 12, 0, tzinfo=UTC)
LOCKOUT = timedelta(minutes=15)


def make_user(role: Role = Role.SALES_REP) -> User:
    return User.create(
        email=Email("ana@quermed.com"),
        full_name="Ana García",
        role=role,
        password_hash="hash",
    )


def test_create_sets_defaults() -> None:
    user = make_user()

    assert user.is_active is True
    assert user.failed_login_attempts == 0
    assert user.territory_ids == frozenset()
    assert user.version == 1


def test_deactivate_by_another_admin() -> None:
    user = make_user()

    user.deactivate(acting_user_id=new_id())

    assert user.is_active is False


def test_deactivate_self_raises_cannot_demote_self() -> None:
    user = make_user(Role.ADMIN)

    with pytest.raises(CannotDemoteSelfError):
        user.deactivate(acting_user_id=user.id)


def test_admin_cannot_change_own_role_away_from_admin() -> None:
    user = make_user(Role.ADMIN)

    with pytest.raises(CannotDemoteSelfError):
        user.change_role(Role.SALES_REP, acting_user_id=user.id)


def test_admin_can_change_another_users_role() -> None:
    user = make_user(Role.SALES_REP)

    user.change_role(Role.SALES_MANAGER, acting_user_id=new_id())

    assert user.role == Role.SALES_MANAGER


def test_failed_logins_lock_account_on_tenth_attempt() -> None:
    user = make_user()

    results = [
        user.record_failed_login(now=NOW, max_attempts=10, lockout=LOCKOUT) for _ in range(10)
    ]

    assert results[:9] == [False] * 9
    assert results[9] is True
    assert user.is_locked(NOW)
    assert user.is_locked(NOW + LOCKOUT - timedelta(seconds=1))
    assert not user.is_locked(NOW + LOCKOUT)
    assert user.failed_login_attempts == 0


def test_reset_failed_logins_clears_counter_and_lock() -> None:
    user = make_user()
    for _ in range(10):
        user.record_failed_login(now=NOW, max_attempts=10, lockout=LOCKOUT)

    user.reset_failed_logins()

    assert user.failed_login_attempts == 0
    assert not user.is_locked(NOW)


def test_refresh_token_lifecycle() -> None:
    token = RefreshToken.issue(
        user_id=new_id(), token_hash="h", ttl=timedelta(days=30), user_agent=None, ip=None
    )
    now = datetime.now(UTC)

    assert token.is_usable(now)

    replacement_id = new_id()
    token.mark_used(now=now, replaced_by_id=replacement_id)

    assert not token.is_usable(now)
    assert token.was_already_used()
    assert token.replaced_by_id == replacement_id


def test_refresh_token_expired_is_not_usable() -> None:
    token = RefreshToken.issue(
        user_id=new_id(), token_hash="h", ttl=timedelta(days=-1), user_agent=None, ip=None
    )

    assert not token.is_usable(datetime.now(UTC))
