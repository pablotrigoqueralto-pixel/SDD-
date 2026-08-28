"""Visibility and edit policies shared by every business record.

Rule (constitution, changes foundation-auth-roles and accounts-contacts):
- admin, sales_manager and back_office see every record;
- a sales_rep sees a record when they own it, or when the record's territory is in
  their territories and the record's divisions are empty or intersect their divisions.

The same rule exists twice on purpose: `VisibilityPolicy` decides on a single loaded
record (writes), `ScopeFilter` is translated to SQL by repositories (lists, detail reads).
An integration test asserts both agree.
"""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from app.domain.territories.entities import Territory
from app.domain.users.entities import User
from app.domain.users.roles import ROLES_WITH_FULL_VISIBILITY, Role


@dataclass(frozen=True)
class Scope:
    territory_ids: frozenset[UUID]
    province_codes: frozenset[str]
    division_ids: frozenset[UUID]

    @property
    def is_empty(self) -> bool:
        return not self.territory_ids or not self.division_ids


class Scoped(Protocol):
    """Any business record that can be filtered by ownership, territory and divisions."""

    @property
    def owner_id(self) -> UUID | None: ...

    @property
    def territory_id(self) -> UUID | None: ...

    @property
    def division_ids(self) -> frozenset[UUID]: ...


def resolve_scope(user: User, territories: Iterable[Territory]) -> Scope:
    assigned = [territory for territory in territories if territory.id in user.territory_ids]
    province_codes = frozenset(code for territory in assigned for code in territory.provinces)
    return Scope(
        territory_ids=frozenset(territory.id for territory in assigned),
        province_codes=province_codes,
        division_ids=user.division_ids,
    )


@dataclass(frozen=True)
class ScopeFilter:
    """Predicate data for repositories: owner = user OR (territory in set AND divisions ok)."""

    user_id: UUID
    territory_ids: frozenset[UUID]
    division_ids: frozenset[UUID]

    @staticmethod
    def for_user(user: User, scope: Scope) -> "ScopeFilter | None":
        if user.role in ROLES_WITH_FULL_VISIBILITY:
            return None
        return ScopeFilter(
            user_id=user.id,
            territory_ids=scope.territory_ids,
            division_ids=scope.division_ids,
        )


class VisibilityPolicy:
    @staticmethod
    def can_read(user: User, scope: Scope, record: Scoped) -> bool:
        if user.role in ROLES_WITH_FULL_VISIBILITY:
            return True
        return _rep_can_access(user, scope, record)

    @staticmethod
    def can_write(user: User, scope: Scope, record: Scoped) -> bool:
        if user.role in {Role.ADMIN, Role.SALES_MANAGER}:
            return True
        if user.role == Role.BACK_OFFICE:
            # Back office write permissions are granted per entity by application services.
            return False
        return _rep_can_access(user, scope, record)


def _rep_can_access(user: User, scope: Scope, record: Scoped) -> bool:
    if record.owner_id == user.id:
        return True
    if record.territory_id is None or record.territory_id not in scope.territory_ids:
        return False
    return not record.division_ids or bool(record.division_ids & scope.division_ids)
