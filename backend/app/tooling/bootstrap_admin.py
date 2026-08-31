"""Bootstrap the initial production administrator (idempotent).

Usage: python -m app.tooling.bootstrap_admin
Env:   BOOTSTRAP_ADMIN_EMAIL (required), BOOTSTRAP_ADMIN_PASSWORD (required, >= 12 chars)

Re-running with the same email resets the password and reactivates the account
without ever creating a duplicate. The E2E seed tool reuses `ensure_admin`.
"""

import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email, validate_new_password
from app.infrastructure.db.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.security.passwords import Argon2PasswordHasher
from app.infrastructure.settings import get_settings


async def ensure_admin(
    session: AsyncSession,
    email: str,
    password: str,
    *,
    full_name: str = "Administración Quermed",
) -> str:
    """Create the admin or reset its password/role/state; returns 'created' or 'updated'."""
    validate_new_password(password)
    hasher = Argon2PasswordHasher()
    repo = SqlAlchemyUserRepository(session)
    existing = await repo.get_by_email(Email(email))
    if existing is None:
        await repo.add(
            User.create(
                email=Email(email),
                full_name=full_name,
                role=Role.ADMIN,
                password_hash=hasher.hash(password),
            )
        )
        return "created"
    existing.set_password_hash(hasher.hash(password))
    existing.activate()
    existing.change_role(Role.ADMIN, acting_user_id=existing.id)
    existing.reset_failed_logins()
    await repo.save(existing, expected_version=existing.version)
    return "updated"


async def run(email: str, password: str) -> str:
    """Engine-managing wrapper for the CLI entrypoints."""
    engine = create_async_engine(get_settings().database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            outcome = await ensure_admin(session, email, password)
            await session.commit()
            return outcome
    finally:
        await engine.dispose()


def main() -> int:
    email = os.environ.get("BOOTSTRAP_ADMIN_EMAIL")
    if not email:
        sys.stderr.write("BOOTSTRAP_ADMIN_EMAIL is required\n")
        return 2
    password = os.environ.get("BOOTSTRAP_ADMIN_PASSWORD")
    if not password:
        sys.stderr.write("BOOTSTRAP_ADMIN_PASSWORD is required\n")
        return 2
    outcome = asyncio.run(run(email, password))
    sys.stdout.write(f"admin {email} {outcome}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
