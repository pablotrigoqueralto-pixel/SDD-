"""Authentication use cases: login, refresh, logout, password change."""

from dataclasses import dataclass
from datetime import datetime, timedelta
from uuid import UUID

from app.application.auth.providers import AuthProvider, Credentials
from app.application.auth.tokens import generate_refresh_token, hash_refresh_token
from app.application.shared.unit_of_work import UnitOfWork
from app.domain.shared.audit import diff_fields
from app.domain.shared.errors import UnauthenticatedError
from app.domain.users.entities import RefreshToken, User
from app.domain.users.errors import (
    AccountLockedError,
    InvalidCredentialsError,
    InvalidCurrentPasswordError,
)
from app.domain.users.value_objects import Email, validate_new_password
from app.infrastructure.security.jwt import AccessTokenCodec, Clock, utc_now
from app.infrastructure.security.passwords import PasswordHasher


@dataclass(frozen=True)
class AuthConfig:
    max_failed_attempts: int = 10
    lockout: timedelta = timedelta(minutes=15)
    refresh_ttl: timedelta = timedelta(days=30)


DEFAULT_AUTH_CONFIG = AuthConfig()


@dataclass(frozen=True)
class ClientInfo:
    user_agent: str | None = None
    ip: str | None = None


@dataclass(frozen=True)
class Session:
    access_token: str
    expires_in: int
    refresh_token: str
    user: User


class AuthService:
    def __init__(
        self,
        uow: UnitOfWork,
        *,
        provider: AuthProvider,
        hasher: PasswordHasher,
        codec: AccessTokenCodec,
        config: AuthConfig = DEFAULT_AUTH_CONFIG,
        clock: Clock = utc_now,
    ) -> None:
        self._uow = uow
        self._provider = provider
        self._hasher = hasher
        self._codec = codec
        self._config = config
        self._clock = clock

    async def login(self, email: Email, password: str, client: ClientInfo) -> Session:
        now = self._clock()
        async with self._uow as uow:
            outcome = await self._provider.authenticate(uow, Credentials(email, password))
            user = outcome.user
            if user is None:
                uow.audit.record(
                    entity_type="user",
                    entity_id=None,
                    action="auth.login_failed",
                    changes={"ip": {"before": None, "after": client.ip}},
                )
                await uow.commit()
                raise InvalidCredentialsError()

            if user.is_locked(now):
                uow.audit.record(
                    entity_type="user",
                    entity_id=user.id,
                    action="auth.login_failed",
                    changes={"ip": {"before": None, "after": client.ip}},
                )
                await uow.commit()
                raise AccountLockedError()

            if not outcome.password_matches or not user.is_active:
                await self._register_failure(uow, user, client, now)
                await uow.commit()
                raise InvalidCredentialsError()

            if user.failed_login_attempts or user.locked_until is not None:
                user.reset_failed_logins()
                await uow.users.save_login_state(user)
            session = await self._open_session(uow, user, client)
            uow.audit.record(
                entity_type="user",
                entity_id=user.id,
                action="auth.login_succeeded",
                changes={"ip": {"before": None, "after": client.ip}},
                actor_id=user.id,
            )
            await uow.commit()
            return session

    async def refresh(self, raw_refresh_token: str, client: ClientInfo) -> Session:
        now = self._clock()
        async with self._uow as uow:
            token = await uow.refresh_tokens.get_by_hash(hash_refresh_token(raw_refresh_token))
            if token is None:
                raise UnauthenticatedError("Unknown refresh token")
            if token.was_already_used():
                # Reuse of a rotated token means it leaked: revoke the whole family.
                await uow.refresh_tokens.revoke_all_for_user(token.user_id, now=now)
                uow.audit.record(
                    entity_type="user",
                    entity_id=token.user_id,
                    action="auth.refresh_reuse_detected",
                )
                await uow.commit()
                raise UnauthenticatedError("Refresh token reuse detected")
            if not token.is_usable(now):
                raise UnauthenticatedError("Refresh token expired or revoked")

            user = await uow.users.get(token.user_id)
            if user is None or not user.is_active:
                raise UnauthenticatedError("User is not active")

            session = await self._open_session(uow, user, client)
            replacement = await uow.refresh_tokens.get_by_hash(
                hash_refresh_token(session.refresh_token)
            )
            if replacement is None:  # pragma: no cover - just persisted above
                raise UnauthenticatedError("Refresh token could not be rotated")
            token.mark_used(now=now, replaced_by_id=replacement.id)
            await uow.refresh_tokens.save(token)
            await uow.commit()
            return session

    async def logout(self, raw_refresh_token: str | None, *, actor_id: UUID | None) -> None:
        if raw_refresh_token is None:
            return
        now = self._clock()
        async with self._uow as uow:
            token = await uow.refresh_tokens.get_by_hash(hash_refresh_token(raw_refresh_token))
            if token is None:
                return
            token.revoke(now=now)
            await uow.refresh_tokens.save(token)
            uow.audit.record(
                entity_type="user", entity_id=token.user_id, action="auth.logout", actor_id=actor_id
            )
            await uow.commit()

    async def change_password(
        self,
        user_id: UUID,
        *,
        current_password: str,
        new_password: str,
        keep_refresh_token: str | None,
    ) -> None:
        validate_new_password(new_password)
        now = self._clock()
        async with self._uow as uow:
            user = await uow.users.get(user_id)
            if user is None or user.password_hash is None:
                raise UnauthenticatedError()
            if not self._hasher.verify(current_password, user.password_hash):
                raise InvalidCurrentPasswordError()
            before = {"password_hash": user.password_hash}
            user.set_password_hash(self._hasher.hash(new_password))
            await uow.users.save(user, expected_version=user.version)
            if keep_refresh_token is not None:
                kept = await uow.refresh_tokens.get_by_hash(hash_refresh_token(keep_refresh_token))
                if kept is not None:
                    await uow.refresh_tokens.revoke_all_except(user.id, keep_id=kept.id, now=now)
                else:
                    await uow.refresh_tokens.revoke_all_for_user(user.id, now=now)
            else:
                await uow.refresh_tokens.revoke_all_for_user(user.id, now=now)
            uow.audit.record(
                entity_type="user",
                entity_id=user.id,
                action="user.password_changed",
                changes=diff_fields(before, {"password_hash": user.password_hash}),
                actor_id=user.id,
            )
            await uow.commit()

    async def _register_failure(
        self, uow: UnitOfWork, user: User, client: ClientInfo, now: datetime
    ) -> None:
        locked = user.record_failed_login(
            now=now,
            max_attempts=self._config.max_failed_attempts,
            lockout=self._config.lockout,
        )
        await uow.users.save_login_state(user)
        uow.audit.record(
            entity_type="user",
            entity_id=user.id,
            action="auth.login_failed",
            changes={"ip": {"before": None, "after": client.ip}},
        )
        if locked:
            uow.audit.record(
                entity_type="user",
                entity_id=user.id,
                action="auth.locked_out",
                changes={"locked_until": {"before": None, "after": user.locked_until.isoformat()}}
                if user.locked_until
                else {},
            )

    async def _open_session(self, uow: UnitOfWork, user: User, client: ClientInfo) -> Session:
        raw = generate_refresh_token()
        token = RefreshToken.issue(
            user_id=user.id,
            token_hash=hash_refresh_token(raw),
            ttl=self._config.refresh_ttl,
            user_agent=client.user_agent,
            ip=client.ip,
            now=self._clock(),  # the injected clock, so expiry follows the test clock too
        )
        await uow.refresh_tokens.add(token)
        access_token = self._codec.issue(user_id=user.id, role=user.role)
        return Session(
            access_token=access_token,
            expires_in=self._codec.ttl_seconds,
            refresh_token=raw,
            user=user,
        )
