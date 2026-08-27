"""Seed an administrator for end-to-end tests and first login (idempotent).

Usage: python -m app.tooling.e2e_seed
Env:   E2E_ADMIN_EMAIL (default admin@quermed.com), E2E_ADMIN_PASSWORD (required, >= 12 chars)
"""

import asyncio
import os
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.domain.users.value_objects import Email, validate_new_password
from app.infrastructure.db.repositories.users import SqlAlchemyUserRepository
from app.infrastructure.security.passwords import Argon2PasswordHasher
from app.infrastructure.settings import get_settings


async def ensure_admin(email: str, password: str) -> str:
    validate_new_password(password)
    engine = create_async_engine(get_settings().database_url)
    hasher = Argon2PasswordHasher()
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            repo = SqlAlchemyUserRepository(session)
            existing = await repo.get_by_email(Email(email))
            if existing is None:
                await repo.add(
                    User.create(
                        email=Email(email),
                        full_name="Administración Quermed",
                        role=Role.ADMIN,
                        password_hash=hasher.hash(password),
                    )
                )
                outcome = "created"
            else:
                existing.set_password_hash(hasher.hash(password))
                existing.activate()
                existing.change_role(Role.ADMIN, acting_user_id=existing.id)
                existing.reset_failed_logins()
                await repo.save(existing, expected_version=existing.version)
                outcome = "updated"
            await session.commit()
            return outcome
    finally:
        await engine.dispose()


def main() -> int:
    email = os.environ.get("E2E_ADMIN_EMAIL", "admin@quermed.com")
    password = os.environ.get("E2E_ADMIN_PASSWORD")
    if not password:
        sys.stderr.write("E2E_ADMIN_PASSWORD is required\n")
        return 2
    outcome = asyncio.run(ensure_admin(email, password))
    sys.stdout.write(f"admin {email} {outcome}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
