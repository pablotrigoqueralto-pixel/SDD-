from collections.abc import Iterable
from copy import deepcopy
from datetime import datetime
from uuid import UUID

from app.domain.shared.errors import ConcurrentModificationError
from app.domain.territories.entities import Division, Territory
from app.domain.territories.errors import (
    ProvinceAlreadyAssignedError,
    TerritoryNameAlreadyExistsError,
)
from app.domain.users.entities import RefreshToken, User
from app.domain.users.errors import EmailAlreadyExistsError
from app.domain.users.value_objects import Email


class InMemoryUserRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, User] = {}

    async def get(self, user_id: UUID) -> User | None:
        row = self.rows.get(user_id)
        return deepcopy(row) if row else None

    async def get_by_email(self, email: Email) -> User | None:
        for row in self.rows.values():
            if row.email == email:
                return deepcopy(row)
        return None

    async def add(self, user: User) -> None:
        if any(row.email == user.email for row in self.rows.values()):
            raise EmailAlreadyExistsError()
        self.rows[user.id] = deepcopy(user)

    async def save(self, user: User, *, expected_version: int) -> None:
        current = self.rows.get(user.id)
        if current is None or current.version != expected_version:
            raise ConcurrentModificationError()
        user.version = expected_version + 1
        self.rows[user.id] = deepcopy(user)

    async def save_login_state(self, user: User) -> None:
        current = self.rows.get(user.id)
        if current is None:
            raise ConcurrentModificationError()
        current.failed_login_attempts = user.failed_login_attempts
        current.locked_until = user.locked_until

    async def count_active_in_territory(self, territory_id: UUID) -> int:
        return sum(
            1 for row in self.rows.values() if row.is_active and territory_id in row.territory_ids
        )


class InMemoryRefreshTokenRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, RefreshToken] = {}

    async def get_by_hash(self, token_hash: str) -> RefreshToken | None:
        for row in self.rows.values():
            if row.token_hash == token_hash:
                return deepcopy(row)
        return None

    async def add(self, token: RefreshToken) -> None:
        self.rows[token.id] = deepcopy(token)

    async def save(self, token: RefreshToken) -> None:
        self.rows[token.id] = deepcopy(token)

    async def revoke_all_for_user(self, user_id: UUID, *, now: datetime) -> int:
        count = 0
        for row in self.rows.values():
            if row.user_id == user_id and row.revoked_at is None:
                row.revoked_at = now
                count += 1
        return count

    async def revoke_all_except(self, user_id: UUID, *, keep_id: UUID, now: datetime) -> int:
        count = 0
        for row in self.rows.values():
            if row.user_id == user_id and row.id != keep_id and row.revoked_at is None:
                row.revoked_at = now
                count += 1
        return count


class InMemoryTerritoryRepository:
    def __init__(self) -> None:
        self.rows: dict[UUID, Territory] = {}

    async def get(self, territory_id: UUID) -> Territory | None:
        row = self.rows.get(territory_id)
        return deepcopy(row) if row else None

    async def get_many(self, ids: Iterable[UUID]) -> list[Territory]:
        wanted = set(ids)
        return [deepcopy(row) for row in self.rows.values() if row.id in wanted]

    async def list_all(self) -> list[Territory]:
        return [deepcopy(row) for row in self.rows.values()]

    async def add(self, territory: Territory) -> None:
        self._check_uniqueness(territory)
        self.rows[territory.id] = deepcopy(territory)

    async def save(self, territory: Territory, *, expected_version: int) -> None:
        current = self.rows.get(territory.id)
        if current is None or current.version != expected_version:
            raise ConcurrentModificationError()
        self._check_uniqueness(territory)
        territory.version = expected_version + 1
        self.rows[territory.id] = deepcopy(territory)

    async def existing_ids(self, ids: Iterable[UUID]) -> frozenset[UUID]:
        return frozenset(identifier for identifier in ids if identifier in self.rows)

    def _check_uniqueness(self, territory: Territory) -> None:
        for row in self.rows.values():
            if row.id == territory.id:
                continue
            if row.name.lower() == territory.name.lower():
                raise TerritoryNameAlreadyExistsError()
            overlap = row.provinces & territory.provinces
            if overlap:
                raise ProvinceAlreadyAssignedError(sorted(overlap)[0], row.name)


class InMemoryDivisionRepository:
    def __init__(self, divisions: Iterable[Division] = ()) -> None:
        self.rows: dict[UUID, Division] = {division.id: division for division in divisions}

    async def list_all(self) -> list[Division]:
        return sorted(self.rows.values(), key=lambda division: division.sort_order)

    async def existing_ids(self, ids: Iterable[UUID]) -> frozenset[UUID]:
        return frozenset(identifier for identifier in ids if identifier in self.rows)
