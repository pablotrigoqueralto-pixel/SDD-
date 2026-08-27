"""Input DTOs for user use cases (validated shape comes from the API schemas)."""

from dataclasses import dataclass, field
from uuid import UUID

from app.domain.users.roles import Role

UNSET: object = object()


@dataclass(frozen=True)
class CreateUser:
    email: str
    full_name: str
    role: Role
    password: str
    territory_ids: frozenset[UUID] = field(default_factory=frozenset)
    division_ids: frozenset[UUID] = field(default_factory=frozenset)


@dataclass(frozen=True)
class UpdateUser:
    """PATCH semantics: None means 'clear', UNSET means 'unchanged'."""

    expected_version: int
    full_name: str | object = UNSET
    role: Role | object = UNSET
    is_active: bool | object = UNSET
    password: str | object = UNSET
    territory_ids: frozenset[UUID] | object = UNSET
    division_ids: frozenset[UUID] | object = UNSET
