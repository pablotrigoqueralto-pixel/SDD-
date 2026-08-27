"""Repository protocols for the users context (implemented in infrastructure)."""

from collections.abc import Iterable
from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.users.entities import RefreshToken, User
from app.domain.users.value_objects import Email


class UserRepository(Protocol):
    async def get(self, user_id: UUID) -> User | None: ...

    async def get_by_email(self, email: Email) -> User | None: ...

    async def add(self, user: User) -> None: ...

    async def save(self, user: User, *, expected_version: int) -> None: ...

    async def save_login_state(self, user: User) -> None:
        """Persist failed_login_attempts / locked_until only: no version check, no version bump,
        so concurrent logins never conflict and admin edits are not disturbed."""
        ...

    async def count_active_in_territory(self, territory_id: UUID) -> int: ...


class RefreshTokenRepository(Protocol):
    async def get_by_hash(self, token_hash: str) -> RefreshToken | None: ...

    async def add(self, token: RefreshToken) -> None: ...

    async def save(self, token: RefreshToken) -> None: ...

    async def revoke_all_for_user(self, user_id: UUID, *, now: datetime) -> int: ...

    async def revoke_all_except(self, user_id: UUID, *, keep_id: UUID, now: datetime) -> int: ...


class ReferenceChecker(Protocol):
    """Answers 'which of these ids exist?' for reference data (territories, divisions)."""

    async def existing_ids(self, ids: Iterable[UUID]) -> frozenset[UUID]: ...
