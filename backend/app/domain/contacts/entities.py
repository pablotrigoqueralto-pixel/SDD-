"""Contact aggregate root with GDPR consent record and anonymisation."""

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any
from uuid import UUID

from app.domain.accounts.entities import PhoneEntry, normalise_phone_list
from app.domain.contacts.errors import (
    ConsentIncompleteError,
    ContactAnonymisedError,
    PreferredChannelMissingValueError,
)
from app.domain.shared.ids import new_id
from app.domain.users.value_objects import Email

ANONYMISED_FIRST_NAME = "Contacto"
ANONYMISED_LAST_NAME = "anonimizado"
ANONYMISED_FIELDS: tuple[str, ...] = (
    "first_name",
    "last_name",
    "email",
    "phones",
    "notes",
)


class PreferredChannel(StrEnum):
    EMAIL = "email"
    PHONE = "phone"


class ConsentStatus(StrEnum):
    UNKNOWN = "unknown"
    GRANTED = "granted"
    DENIED = "denied"


class ConsentSource(StrEnum):
    VERBAL = "verbal"
    EMAIL = "email"
    FORM = "form"
    IMPORTED = "imported"


@dataclass(frozen=True)
class ConsentRecord:
    status: ConsentStatus = ConsentStatus.UNKNOWN
    at: datetime | None = None
    source: ConsentSource | None = None
    recorded_by: UUID | None = None

    def __post_init__(self) -> None:
        if self.status != ConsentStatus.UNKNOWN and (self.at is None or self.source is None):
            raise ConsentIncompleteError()

    def as_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "at": self.at,
            "source": self.source,
            "recorded_by": self.recorded_by,
        }


DETAIL_FIELDS: frozenset[str] = frozenset(
    {
        "first_name",
        "last_name",
        "job_title_id",
        "specialty_id",
        "email",
        "phones",
        "preferred_channel",
        "is_head_of_department",
        "notes",
    }
)


@dataclass
class Contact:
    id: UUID
    account_id: UUID
    first_name: str
    last_name: str
    job_title_id: UUID | None = None
    specialty_id: UUID | None = None
    email: str | None = None
    phones: list[PhoneEntry] = field(default_factory=list)
    is_head_of_department: bool = False
    preferred_channel: PreferredChannel | None = None
    notes: str | None = None
    is_primary: bool = False
    is_active: bool = True
    consent: ConsentRecord = field(default_factory=ConsentRecord)
    anonymised_at: datetime | None = None
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        account_id: UUID,
        first_name: str,
        last_name: str,
        details: Mapping[str, Any] | None = None,
        is_primary: bool = False,
        consent: ConsentRecord | None = None,
    ) -> "Contact":
        contact = cls(
            id=new_id(),
            account_id=account_id,
            first_name=first_name.strip(),
            last_name=last_name.strip(),
            is_primary=is_primary,
        )
        if details:
            contact.update_details(details)
        if consent is not None:
            contact.consent = consent
        contact.validate_channels()
        return contact

    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def is_anonymised(self) -> bool:
        return self.anonymised_at is not None

    def _ensure_editable(self) -> None:
        if self.is_anonymised:
            raise ContactAnonymisedError()

    def update_details(self, changes: Mapping[str, Any]) -> None:
        self._ensure_editable()
        for key, value in changes.items():
            if key not in DETAIL_FIELDS:
                continue
            setattr(self, key, _normalise(key, value))

    def validate_channels(self) -> None:
        channel = self.preferred_channel
        if channel is None:
            return
        has_value = (
            bool(self.phones) if channel is PreferredChannel.PHONE else self.email is not None
        )
        if not has_value:
            raise PreferredChannelMissingValueError(channel.value)

    def record_consent(self, consent: ConsentRecord) -> None:
        self._ensure_editable()
        self.consent = consent

    def make_primary(self) -> None:
        self._ensure_editable()
        self.is_primary = True

    def demote(self) -> None:
        self.is_primary = False

    def activate(self) -> None:
        self._ensure_editable()
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False

    def anonymise(self, *, now: datetime) -> list[str]:
        """Erase personal data in place; returns the names of the cleared fields."""
        self._ensure_editable()
        self.first_name = ANONYMISED_FIRST_NAME
        self.last_name = ANONYMISED_LAST_NAME
        self.email = None
        self.phones = []
        self.notes = None
        self.preferred_channel = None
        self.is_primary = False
        self.is_active = False
        self.consent = ConsentRecord(
            status=ConsentStatus.DENIED,
            at=now,
            source=self.consent.source or ConsentSource.FORM,
            recorded_by=self.consent.recorded_by,
        )
        self.anonymised_at = now
        return list(ANONYMISED_FIELDS)

    def snapshot(self) -> dict[str, object]:
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "job_title_id": self.job_title_id,
            "specialty_id": self.specialty_id,
            "email": self.email,
            "phones": [p.number for p in self.phones],
            "is_head_of_department": self.is_head_of_department,
            "preferred_channel": self.preferred_channel,
            "notes": self.notes,
            "is_active": self.is_active,
        }


def _normalise(key: str, value: Any) -> Any:
    if key in {"first_name", "last_name"}:
        return str(value).strip()
    if value is None:
        return None
    if key in {"job_title_id", "specialty_id"}:
        return value
    if key == "preferred_channel":
        return PreferredChannel(value)
    if key == "phones":
        return normalise_phone_list(list(value or []))
    if key == "is_head_of_department":
        return bool(value)
    text = str(value)
    if key == "email":
        return Email(text).value
    cleaned = text.strip()
    return cleaned or None
