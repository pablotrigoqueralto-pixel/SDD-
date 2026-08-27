"""Visibility and edit policies shared by every business record.

Rule (constitution, change foundation-auth-roles):
- admin, sales_manager and back_office see every record;
- a sales_rep sees a record when they own it, or when the record's territory is in
  their territories and (if the record has a division) the division is in their divisions.
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
    """Any business record that can be filtered by ownership, territory and division."""

    @property
    def owner_id(self) -> UUID | None: ...

    @property
    def territory_id(self) -> UUID | None: ...

    @property
    def division_id(self) -> UUID | None: ...


def resolve_scope(user: User, territories: Iterable[Territory]) -> Scope:
    assigned = [territory for territory in territories if territory.id in user.territory_ids]
    province_codes = frozenset(code for territory in assigned for code in territory.provinces)
    return Scope(
        territory_ids=frozenset(territory.id for territory in assigned),
        province_codes=province_codes,
        division_ids=user.division_ids,
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
            # Back office write permissions are granted per entity by later changes.
            return False
        return _rep_can_access(user, scope, record)


def _rep_can_access(user: User, scope: Scope, record: Scoped) -> bool:
    if record.owner_id == user.id:
        return True
    if record.territory_id is None or record.territory_id not in scope.territory_ids:
        return False
    return record.division_id is None or record.division_id in scope.division_ids
