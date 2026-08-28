"""User aggregate root and refresh token entity."""

from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.domain.shared.ids import new_id
from app.domain.users.errors import CannotDemoteSelfError
from app.domain.users.roles import IdentityProvider, Role
from app.domain.users.value_objects import Email


@dataclass
class User:
    id: UUID
    email: Email
    full_name: str
    role: Role
    password_hash: str | None = None
    is_active: bool = True
    identity_provider: IdentityProvider = IdentityProvider.PASSWORD
    external_id: str | None = None
    failed_login_attempts: int = 0
    locked_until: datetime | None = None
    territory_ids: frozenset[UUID] = field(default_factory=frozenset)
    division_ids: frozenset[UUID] = field(default_factory=frozenset)
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        email: Email,
        full_name: str,
        role: Role,
        password_hash: str,
        territory_ids: frozenset[UUID] = frozenset(),
        division_ids: frozenset[UUID] = frozenset(),
    ) -> "User":
        return cls(
            id=new_id(),
            email=email,
            full_name=full_name,
            role=role,
            password_hash=password_hash,
            territory_ids=territory_ids,
            division_ids=division_ids,
        )

    # --- lifecycle -------------------------------------------------------

    def deactivate(self, *, acting_user_id: UUID) -> None:
        if acting_user_id == self.id:
            raise CannotDemoteSelfError()
        self.is_active = False

    def activate(self) -> None:
        self.is_active = True

    def change_role(self, new_role: Role, *, acting_user_id: UUID) -> None:
        if acting_user_id == self.id and self.role == Role.ADMIN and new_role != Role.ADMIN:
            raise CannotDemoteSelfError()
        self.role = new_role

    def rename(self, full_name: str) -> None:
        self.full_name = full_name.strip()

    def assign_scope(
        self, *, territory_ids: frozenset[UUID], division_ids: frozenset[UUID]
    ) -> None:
        self.territory_ids = territory_ids
        self.division_ids = division_ids

    def set_password_hash(self, password_hash: str) -> None:
        self.password_hash = password_hash

    # --- login protection -------------------------------------------------

    def is_locked(self, now: datetime) -> bool:
        return self.locked_until is not None and self.locked_until > now

    def record_failed_login(self, *, now: datetime, max_attempts: int, lockout: timedelta) -> bool:
        """Count a failure; returns True when this failure locks the account."""
        self.failed_login_attempts += 1
        if self.failed_login_attempts >= max_attempts:
            self.locked_until = now + lockout
            self.failed_login_attempts = 0
            return True
        return False

    def reset_failed_logins(self) -> None:
        self.failed_login_attempts = 0
        self.locked_until = None


@dataclass
class RefreshToken:
    id: UUID
    user_id: UUID
    token_hash: str
    expires_at: datetime
    used_at: datetime | None = None
    revoked_at: datetime | None = None
    replaced_by_id: UUID | None = None
    user_agent: str | None = None
    ip: str | None = None
    created_at: datetime | None = None

    @classmethod
    def issue(
        cls,
        *,
        user_id: UUID,
        token_hash: str,
        ttl: timedelta,
        user_agent: str | None,
        ip: str | None,
        now: datetime | None = None,
    ) -> "RefreshToken":
        return cls(
            id=new_id(),
            user_id=user_id,
            token_hash=token_hash,
            expires_at=(now or datetime.now(UTC)) + ttl,
            user_agent=user_agent,
            ip=ip,
        )

    def is_usable(self, now: datetime) -> bool:
        return self.used_at is None and self.revoked_at is None and self.expires_at > now

    def was_already_used(self) -> bool:
        return self.used_at is not None

    def mark_used(self, *, now: datetime, replaced_by_id: UUID) -> None:
        self.used_at = now
        self.replaced_by_id = replaced_by_id

    def revoke(self, *, now: datetime) -> None:
        if self.revoked_at is None:
            self.revoked_at = now
