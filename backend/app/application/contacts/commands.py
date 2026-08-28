"""Input DTOs for contact use cases."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.application.users.commands import UNSET
from app.domain.contacts.entities import ConsentSource, ConsentStatus


@dataclass(frozen=True)
class ConsentInput:
    status: ConsentStatus
    at: datetime | None = None
    source: ConsentSource | None = None


@dataclass(frozen=True)
class CreateContact:
    account_id: UUID
    first_name: str
    last_name: str
    details: Mapping[str, Any] = field(default_factory=dict)
    is_primary: bool = False
    consent: ConsentInput | None = None


@dataclass(frozen=True)
class UpdateContact:
    expected_version: int
    changes: Mapping[str, Any] = field(default_factory=dict)
    is_primary: bool | object = UNSET
    is_active: bool | object = UNSET
    consent: ConsentInput | None = None
