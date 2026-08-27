"""Shared FastAPI dependencies: settings, unit of work, services, current user, roles."""

from collections.abc import Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Header, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.application.auth.providers import PasswordAuthProvider
from app.application.auth.service import AuthConfig, AuthService
from app.application.territories.service import TerritoryService
from app.application.users.service import UserService
from app.domain.shared.errors import (
    PermissionDeniedError,
    PreconditionRequiredError,
    UnauthenticatedError,
    ValidationFailedError,
)
from app.domain.users.entities import User
from app.domain.users.roles import Role
from app.infrastructure.db.session import get_session
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.logging import set_actor_id
from app.infrastructure.security.jwt import AccessTokenCodec
from app.infrastructure.security.passwords import PasswordHasher
from app.infrastructure.settings import Settings

bearer_scheme = HTTPBearer(auto_error=False)


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_codec(request: Request) -> AccessTokenCodec:
    codec: AccessTokenCodec = request.app.state.codec
    return codec


def get_hasher(request: Request) -> PasswordHasher:
    hasher: PasswordHasher = request.app.state.hasher
    return hasher


def get_uow(session: Annotated[AsyncSession, Depends(get_session)]) -> SqlAlchemyUnitOfWork:
    return SqlAlchemyUnitOfWork(session)


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
CodecDep = Annotated[AccessTokenCodec, Depends(get_codec)]
HasherDep = Annotated[PasswordHasher, Depends(get_hasher)]
UowDep = Annotated[SqlAlchemyUnitOfWork, Depends(get_uow)]
SessionDep = Annotated[AsyncSession, Depends(get_session)]


def get_auth_service(
    uow: UowDep, hasher: HasherDep, codec: CodecDep, settings: SettingsDep
) -> AuthService:
    from datetime import timedelta

    return AuthService(
        uow,
        provider=PasswordAuthProvider(hasher),
        hasher=hasher,
        codec=codec,
        config=AuthConfig(
            max_failed_attempts=settings.max_failed_login_attempts,
            lockout=timedelta(minutes=settings.lockout_minutes),
            refresh_ttl=timedelta(days=settings.refresh_token_ttl_days),
        ),
    )


def get_user_service(uow: UowDep, hasher: HasherDep) -> UserService:
    return UserService(uow, hasher=hasher)


def get_territory_service(uow: UowDep) -> TerritoryService:
    return TerritoryService(uow)


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    codec: CodecDep,
    uow: UowDep,
) -> User:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise UnauthenticatedError("Missing bearer token")
    claims = codec.verify(credentials.credentials)
    user = await uow.users.get(claims.user_id)
    if user is None or not user.is_active:
        raise UnauthenticatedError("User is not active")
    set_actor_id(str(user.id))
    return user


CurrentUser = Annotated[User, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[..., Coroutine[Any, Any, User]]:
    allowed = frozenset(roles)

    async def dependency(user: CurrentUser) -> User:
        if user.role not in allowed:
            raise PermissionDeniedError("Your role cannot perform this action")
        return user

    return dependency


AdminUser = Annotated[User, Depends(require_roles(Role.ADMIN))]
StaffUser = Annotated[
    User, Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.BACK_OFFICE))
]


def if_match_version(
    if_match: Annotated[str | None, Header(alias="If-Match")] = None,
) -> int:
    """Optimistic locking: the client must send the version it read."""
    if if_match is None:
        raise PreconditionRequiredError()
    raw = if_match.strip().strip('"')
    if not raw.isdigit():
        raise ValidationFailedError(
            [
                {
                    "field": "If-Match",
                    "message": "Must be the integer version",
                    "code": "invalid_if_match",
                }
            ]
        )
    return int(raw)


ExpectedVersion = Annotated[int, Depends(if_match_version)]
