from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.application.contacts.queries import ContactSummary
from app.domain.accounts.entities import Account
from app.domain.contacts.entities import (
    ConsentRecord,
    ConsentSource,
    ConsentStatus,
    Contact,
    PreferredChannel,
)
from app.schemas.accounts import PhoneRead, PhoneWrite


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
    specialty_id: UUID | None
    email: str | None
    phones: list[PhoneRead]
    is_head_of_department: bool
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
            specialty_id=contact.specialty_id,
            email=contact.email,
            phones=[PhoneRead.from_entity(p) for p in contact.phones],
            is_head_of_department=contact.is_head_of_department,
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
    specialty_id: UUID | None = None
    email: str | None = Field(default=None, max_length=254)
    phones: list[PhoneWrite] | None = None
    is_head_of_department: bool | None = None
    preferred_channel: PreferredChannel | None = None
    notes: str | None = Field(default=None, max_length=4000)


DETAIL_KEYS = frozenset(
    {
        "job_title_id",
        "specialty_id",
        "email",
        "phones",
        "is_head_of_department",
        "preferred_channel",
        "notes",
    }
)


class ContactCreate(_ContactDetails):
    first_name: str = Field(min_length=1, max_length=100)
    last_name: str = Field(min_length=1, max_length=150)
    is_primary: bool = False
    consent: ConsentWrite | None = None

    def details(self) -> dict[str, Any]:
        values = {k: v for k, v in self.model_dump().items() if k in DETAIL_KEYS and v is not None}
        if self.phones is not None:
            values["phones"] = [phone.to_entity(index) for index, phone in enumerate(self.phones)]
        return values


class ContactUpdate(_ContactDetails):
    first_name: str | None = Field(default=None, min_length=1, max_length=100)
    last_name: str | None = Field(default=None, min_length=1, max_length=150)
    is_primary: bool | None = None
    is_active: bool | None = None
    consent: ConsentWrite | None = None

    def changes(self) -> dict[str, Any]:
        values = {
            key: getattr(self, key)
            for key in self.model_fields_set
            if key in DETAIL_KEYS or key in {"first_name", "last_name"}
        }
        if "phones" in values and values["phones"] is not None:
            values["phones"] = [
                phone.to_entity(index) for index, phone in enumerate(values["phones"])
            ]
        return values


class ContactSummaryRead(BaseModel):
    """One row of the global contacts list."""

    id: UUID
    first_name: str
    last_name: str
    account_id: UUID
    account_name: str
    job_title_id: UUID | None
    specialty_id: UUID | None
    is_head_of_department: bool
    primary_phone: str | None
    email: str | None
    is_active: bool

    @classmethod
    def from_summary(cls, summary: ContactSummary) -> "ContactSummaryRead":
        return cls(
            id=summary.id,
            first_name=summary.first_name,
            last_name=summary.last_name,
            account_id=summary.account_id,
            account_name=summary.account_name,
            job_title_id=summary.job_title_id,
            specialty_id=summary.specialty_id,
            is_head_of_department=summary.is_head_of_department,
            primary_phone=summary.primary_phone,
            email=summary.email,
            is_active=summary.is_active,
        )
