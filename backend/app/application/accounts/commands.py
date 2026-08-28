"""Input DTOs for account use cases."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from app.application.users.commands import UNSET


@dataclass(frozen=True)
class CreateAccount:
    name: str
    account_type_id: UUID
    province_code: str
    details: Mapping[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class UpdateAccount:
    """PATCH semantics: only keys present in `changes` are applied (None clears)."""

    expected_version: int
    changes: Mapping[str, Any]


@dataclass(frozen=True)
class AssignAccount:
    expected_version: int
    owner_id: UUID | object | None = UNSET
    territory_id: UUID | object | None = UNSET


@dataclass(frozen=True)
class AddressInput:
    label: str
    street: str
    postal_code: str
    city: str
    province_code: str
    notes: str | None = None


@dataclass(frozen=True)
class ReplaceAddresses:
    expected_version: int
    addresses: Sequence[AddressInput]
