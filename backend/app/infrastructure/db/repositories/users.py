"""SQLAlchemy implementations of UserRepository and RefreshTokenRepository."""

from collections.abc import Iterable
from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.domain.shared.errors import ConcurrentModificationError
from app.domain.users.entities import RefreshToken, User
from app.domain.users.errors import EmailAlreadyExistsError
from app.domain.users.value_objects import Email
from app.infrastructure.db.models import (
    RefreshTokenModel,
    UserDivisionModel,
    UserModel,
    UserTerritoryModel,
)
from app.infrastructure.db.repositories.results import rowcount_of


def user_to_entity(row: UserModel) -> User:
    return User(
        id=row.id,
        email=Email(row.email),
        full_name=row.full_name,
        role=row.role,
        password_hash=row.password_hash,
        is_active=row.is_active,
        identity_provider=row.identity_provider,
        external_id=row.external_id,
        failed_login_attempts=row.failed_login_attempts,
        locked_until=row.locked_until,
        territory_ids=frozenset(link.territory_id for link in row.territory_links),
        division_ids=frozenset(link.division_id for link in row.division_links),
        version=row.version,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def user_values(user: User) -> dict[str, object]:
    return {
        "email": user.email.value,
        "full_name": user.full_name,
        "password_hash": user.password_hash,
        "role": user.role,
        "is_active": user.is_active,
        "identity_provider": user.identity_provider,
        "external_id": user.external_id,
        "failed_login_attempts": user.failed_login_attempts,
        "locked_until": user.locked_until,
    }


_USER_LOAD = (selectinload(UserModel.territory_links), selectinload(UserModel.division_links))


class SqlAlchemyUserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get(self, user_id: UUID) -> User | None:
        statement = select(UserModel).options(*_USER_LOAD).where(UserModel.id == user_id)
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return user_to_entity(row) if row else None

    async def get_by_email(self, email: Email) -> User | None:
        statement = select(UserModel).options(*_USER_LOAD).where(UserModel.email == email.value)
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return user_to_entity(row) if row else None

    async def add(self, user: User) -> None:
        row = UserModel(id=user.id, **user_values(user))
        row.territory_links = [
            UserTerritoryModel(user_id=user.id, territory_id=territory_id)
            for territory_id in user.territory_ids
        ]
        row.division_links = [
            UserDivisionModel(user_id=user.id, division_id=division_id)
            for division_id in user.division_ids
        ]
        self._session.add(row)
        try:
            await self._session.flush()
        except IntegrityError as exc:
            if "users_email_key" in str(exc.orig):
                raise EmailAlreadyExistsError() from exc
            raise

    async def save(self, user: User, *, expected_version: int) -> None:
        statement = (
            update(UserModel)
            .where(UserModel.id == user.id, UserModel.version == expected_version)
            .values(**user_values(user), version=expected_version + 1)
        )
        try:
            result = await self._session.execute(statement)
        except IntegrityError as exc:
            if "users_email_key" in str(exc.orig):
                raise EmailAlreadyExistsError() from exc
            raise
        if rowcount_of(result) != 1:
            raise ConcurrentModificationError()
        await self._sync_links(user)
        user.version = expected_version + 1

    async def save_login_state(self, user: User) -> None:
        await self._session.execute(
            update(UserModel)
            .where(UserModel.id == user.id)
            .values(
                failed_login_attempts=user.failed_login_attempts,
                locked_until=user.locked_until,
            )
        )

    async def _sync_links(self, user: User) -> None:
        await self._session.execute(
            delete(UserTerritoryModel).where(UserTerritoryModel.user_id == user.id)
        )
        await self._session.execute(
            delete(UserDivisionModel).where(UserDivisionModel.user_id == user.id)
        )
        if user.territory_ids:
            await self._session.execute(
                insert(UserTerritoryModel),
                [
                    {"user_id": user.id, "territory_id": territory_id}
                    for territory_id in user.territory_ids
                ],
            )
        if user.division_ids:
            await self._session.execute(
                insert(UserDivisionModel),
                [
                    {"user_id": user.id, "division_id": division_id}
                    for division_id in user.division_ids
                ],
            )

    async def count_active_in_territory(self, territory_id: UUID) -> int:
        statement = (
            select(func.count())
            .select_from(UserTerritoryModel)
            .join(UserModel, UserModel.id == UserTerritoryModel.user_id)
            .where(UserTerritoryModel.territory_id == territory_id, UserModel.is_active.is_(True))
        )
        return int((await self._session.execute(statement)).scalar_one())


def refresh_token_to_entity(row: RefreshTokenModel) -> RefreshToken:
    return RefreshToken(
        id=row.id,
        user_id=row.user_id,
        token_hash=row.token_hash,
        expires_at=row.expires_at,
        used_at=row.used_at,
        revoked_at=row.revoked_at,
        replaced_by_id=row.replaced_by_id,
        user_agent=row.user_agent,
        ip=str(row.ip) if row.ip is not None else None,
        created_at=row.created_at,
    )


class SqlAlchemyRefreshTokenRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        statement = select(RefreshTokenModel).where(RefreshTokenModel.token_hash == token_hash)
        row = (await self._session.execute(statement)).scalar_one_or_none()
        return refresh_token_to_entity(row) if row else None

    async def add(self, token: RefreshToken) -> None:
        self._session.add(
            RefreshTokenModel(
                id=token.id,
                user_id=token.user_id,
                token_hash=token.token_hash,
                expires_at=token.expires_at,
                used_at=token.used_at,
                revoked_at=token.revoked_at,
                replaced_by_id=token.replaced_by_id,
                user_agent=token.user_agent,
                ip=token.ip,
            )
        )
        await self._session.flush()

    async def save(self, token: RefreshToken) -> None:
        await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.id == token.id)
            .values(
                used_at=token.used_at,
                revoked_at=token.revoked_at,
                replaced_by_id=token.replaced_by_id,
            )
        )

    async def revoke_all_for_user(self, user_id: UUID, *, now: datetime) -> int:
        result = await self._session.execute(
            update(RefreshTokenModel)
            .where(RefreshTokenModel.user_id == user_id, RefreshTokenModel.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        return int(rowcount_of(result))

    async def revoke_all_except(self, user_id: UUID, *, keep_id: UUID, now: datetime) -> int:
        result = await self._session.execute(
            update(RefreshTokenModel)
            .where(
                RefreshTokenModel.user_id == user_id,
                RefreshTokenModel.id != keep_id,
                RefreshTokenModel.revoked_at.is_(None),
            )
            .values(revoked_at=now)
        )
        return int(rowcount_of(result))


def ids_in(ids: Iterable[UUID]) -> list[UUID]:
    return list(set(ids))
