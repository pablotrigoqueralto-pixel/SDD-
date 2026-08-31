"""ensure_admin: idempotent creation and password reset of the initial administrator."""

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.users.errors import PasswordTooShortError
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email
from app.infrastructure.db.models import UserModel
from app.infrastructure.db.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.security.passwords import Argon2PasswordHasher
from app.tooling.bootstrap_admin import ensure_admin

pytestmark = pytest.mark.integration

EMAIL = "bootstrap@quermed.com"
FIRST_PASSWORD = "first-bootstrap-passphrase"
SECOND_PASSWORD = "second-bootstrap-passphrase"


async def admin_count(session: AsyncSession) -> int:
    result = await session.execute(
        select(func.count()).select_from(UserModel).where(UserModel.email == EMAIL)
    )
    return result.scalar_one()


async def test_creates_admin_with_working_password(session: AsyncSession) -> None:
    outcome = await ensure_admin(session, EMAIL, FIRST_PASSWORD)

    assert outcome == "created"
    user = await SqlAlchemyUserRepository(session).get_by_email(Email(EMAIL))
    assert user is not None and user.role is Role.ADMIN and user.is_active
    assert user.password_hash is not None
    assert Argon2PasswordHasher().verify(FIRST_PASSWORD, user.password_hash)


async def test_rerun_resets_password_without_duplicating(session: AsyncSession) -> None:
    await ensure_admin(session, EMAIL, FIRST_PASSWORD)

    outcome = await ensure_admin(session, EMAIL, SECOND_PASSWORD)

    assert outcome == "updated"
    assert await admin_count(session) == 1
    user = await SqlAlchemyUserRepository(session).get_by_email(Email(EMAIL))
    assert user is not None and user.password_hash is not None
    hasher = Argon2PasswordHasher()
    assert hasher.verify(SECOND_PASSWORD, user.password_hash)
    assert not hasher.verify(FIRST_PASSWORD, user.password_hash)


async def test_rejects_weak_password(session: AsyncSession) -> None:
    with pytest.raises(PasswordTooShortError):
        await ensure_admin(session, EMAIL, "short")
    assert await admin_count(session) == 0
