from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.domain.accounts.entities import Account
from app.domain.contacts.entities import (
    ConsentRecord,
    ConsentSource,
    ConsentStatus,
    Contact,
    PreferredChannel,
)


class ConsentRead(BaseModel):
    status: ConsentStatus
    at: datetime | None
    source: ConsentSource | None
    recorded_by: UUID | None

    @classmethod
    def from_record(cls, record: ConsentRecord) -> "ConsentRead":
        return cls(
            status=record.status, at=record.at, source=record.source, recorded_by=record.recorded_by
        )


class ConsentWrite(BaseModel):
    status: ConsentStatus
    at: datetime | None = None
    source: ConsentSource | None = None


class ContactRead(BaseModel):
    id: UUID
    account_id: UUID
    account_name: str | None
    first_name: str
    last_name: str
    job_title_id: UUID | None
    division_id: UUID | None
    email: str | None
    mobile: str | None
    landline: str | None
    preferred_channel: PreferredChannel | None
    notes: str | None
    is_primary: bool
    is_active: bool
    consent: ConsentRead
    anonymised_at: datetime | None
    version: int
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_entity(cls, contact: Contact, account: Account | None = None) -> "ContactRead":
        return cls(
            id=contact.id,
            account_id=contact.account_id,
            account_name=account.name if account else None,
            first_name=contact.first_name,
            last_name=contact.last_name,
            job_title_id=contact.job_title_id,
            division_id=contact.division_id,
            email=contact.email,
            mobile=contact.mobile,
            landline=contact.landline,
            preferred_channel=contact.preferred_channel,
            notes=contact.notes,
            is_primary=contact.is_primary,
            is_active=contact.is_active,
            consent=ConsentRead.from_record(contact.consent),
            anonymised_at=contact.anonymised_at,
            version=contact.version,
            created_at=contact.created_at,
            updated_at=contact.updated_at,
        )


class _ContactDetails(BaseModel):
    job_title_id: UUID | None = None
    division_id: UUID | None = None
    email: str | None = Field(default=None, max_length=254)
    mobile: str | None = Field(default=None, max_length=30)
    landline: str | None = Field(default=None, max_length=30)
    preferred_channel: PreferredChannel | None = None
    notes: str | None = Field(default=None, max_length=4000)


DETAIL_KEYS = frozenset(
    {"job_title_id", "division_id", "email", "mobile", "landline", "preferred_channel", "notes"}
)


class ContactCreate(_ContactDetails):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=150)
    is_primary: bool = False
    consent: ConsentWrite | None = None

    def details(self) -> dict[str, Any]:
        return {k: v for k, v in self.model_dump().items() if k in DETAIL_KEYS and v is not None}


class ContactUpdate(_ContactDetails):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=150)
    is_primary: bool | None = None
    is_active: bool | None = None
    consent: ConsentWrite | None = None

    def changes(self) -> dict[str, Any]:
        return {
            key: getattr(self, key)
            for key in self.model_fields_set
            if key in DETAIL_KEYS or key in {"first_name", "last_name"}
        }
