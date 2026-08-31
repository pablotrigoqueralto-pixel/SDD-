from datetime import datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field

from app.application.accounts.queries import AccountSummary
from app.application.accounts.service import AccountView
from app.domain.accounts.entities import AdditionalAddress, PhoneEntry


class PhoneWrite(BaseModel):
    """One labelled phone; the array order is the priority (first = primary)."""

    label: str = Field(min_length=1, max_length=60)
    number: str = Field(min_length=3, max_length=30)
    extension: str | None = Field(default=None, max_length=10)
    note: str | None = Field(default=None, max_length=200)

    def to_entity(self, index: int = 0) -> PhoneEntry:
        """`index` lands in the error field (`phones.1`) so a client knows which row failed."""
        return PhoneEntry.create(
            label=self.label,
            number=self.number,
            extension=self.extension,
            note=self.note,
            field_name=f"phones.{index}",
        )


class PhoneRead(BaseModel):
    label: str
    number: str
    extension: str | None
    note: str | None

    @classmethod
    def from_entity(cls, phone: PhoneEntry) -> "PhoneRead":
        return cls(
            label=phone.label, number=phone.number, extension=phone.extension, note=phone.note
        )


class AddressRead(BaseModel):
    label: str
    street: str
    postal_code: str
    city: str
    province_code: str
    notes: str | None

    @classmethod
    def from_entity(cls, address: AdditionalAddress) -> "AddressRead":
        return cls(**address.as_dict())


class AddressWrite(BaseModel):
    label: str = Field(min_length=1, max_length=60)
    street: str = Field(min_length=1, max_length=200)
    postal_code: str = Field(min_length=5, max_length=5)
    city: str = Field(min_length=1, max_length=100)
    province_code: str = Field(min_length=2, max_length=2)
    notes: str | None = Field(default=None, max_length=500)


class AddressesReplace(BaseModel):
    addresses: list[AddressWrite] = Field(max_length=10)


class AccountSummaryRead(BaseModel):
    id: UUID
    name: str
    account_type_id: UUID
    city: str | None
    province_code: str
    territory_id: UUID | None
    territory_name: str | None
    owner_id: UUID | None
    owner_name: str | None
    is_active: bool
    territory_mismatch: bool
    primary_contact_name: str | None
    primary_phone: str | None
    last_contact_at: datetime | None
    next_activity_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_summary(cls, summary: AccountSummary) -> "AccountSummaryRead":
        return cls(
            id=summary.id,
            name=summary.name,
            account_type_id=summary.account_type_id,
            city=summary.city,
            province_code=summary.province_code,
            territory_id=summary.territory_id,
            territory_name=summary.territory_name,
            owner_id=summary.owner_id,
            owner_name=summary.owner_name,
            is_active=summary.is_active,
            territory_mismatch=summary.territory_mismatch,
            primary_contact_name=summary.primary_contact_name,
            primary_phone=summary.primary_phone,
            last_contact_at=summary.last_contact_at,
            next_activity_at=summary.next_activity_at,
            updated_at=summary.updated_at,
        )


class AccountRead(BaseModel):
    id: UUID
    name: str
    account_type_id: UUID
    province_code: str
    street: str | None
    postal_code: str | None
    city: str | None
    tax_id: str | None
    phones: list[PhoneRead]
    email: str | None
    website: str | None
    customer_code: str | None
    notes: str | None
    billing_notes: str | None
    territory_id: UUID | None
    territory_name: str | None
    owner_id: UUID | None
    owner_name: str | None
    territory_mismatch: bool
    division_ids: list[UUID]
    brand_ids: list[UUID]
    addresses: list[AddressRead]
    last_contact_at: datetime | None
    next_activity_at: datetime | None
    is_active: bool
    version: int
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_view(cls, view: AccountView) -> "AccountRead":
        account = view.account
        return cls(
            id=account.id,
            name=account.name,
            account_type_id=account.account_type_id,
            province_code=account.province_code,
            street=account.street,
            postal_code=account.postal_code,
            city=account.city,
            tax_id=account.tax_id,
            phones=[PhoneRead.from_entity(p) for p in account.phones],
            email=account.email,
            website=account.website,
            customer_code=account.customer_code,
            notes=account.notes,
            billing_notes=account.billing_notes,
            territory_id=account.territory_id,
            territory_name=view.territory_name,
            owner_id=account.owner_id,
            owner_name=view.owner_name,
            territory_mismatch=view.territory_mismatch,
            division_ids=sorted(account.division_ids, key=str),
            brand_ids=sorted(account.brand_ids, key=str),
            addresses=[AddressRead.from_entity(a) for a in account.addresses],
            last_contact_at=account.last_contact_at,
            next_activity_at=account.next_activity_at,
            is_active=account.is_active,
            version=account.version,
            created_at=account.created_at,
            updated_at=account.updated_at,
        )


class _AccountDetails(BaseModel):
    street: str | None = Field(default=None, max_length=200)
    postal_code: str | None = Field(default=None, max_length=10)
    city: str | None = Field(default=None, max_length=100)
    tax_id: str | None = Field(default=None, max_length=20)
    phones: list[PhoneWrite] | None = None
    email: str | None = Field(default=None, max_length=254)
    website: str | None = Field(default=None, max_length=200)
    customer_code: str | None = Field(default=None, max_length=50)
    notes: str | None = Field(default=None, max_length=4000)
    billing_notes: str | None = Field(default=None, max_length=4000)
    division_ids: list[UUID] | None = None
    brand_ids: list[UUID] | None = None


class AccountCreate(_AccountDetails):
    name: str = Field(min_length=1, max_length=200)
    account_type_id: UUID
    province_code: str = Field(min_length=2, max_length=2)

    def details(self) -> dict[str, Any]:
        values = {
            key: value
            for key, value in self.model_dump().items()
            if key not in {"name", "account_type_id", "province_code"} and value is not None
        }
        if self.phones is not None:
            values["phones"] = [phone.to_entity(index) for index, phone in enumerate(self.phones)]
        return values


class AccountUpdate(_AccountDetails):
    """Only fields present in the request body are applied (null clears optional ones)."""

    name: str | None = Field(default=None, min_length=1, max_length=200)
    account_type_id: UUID | None = None
    province_code: str | None = Field(default=None, min_length=2, max_length=2)
    is_active: bool | None = None
    # Present only to reject them explicitly (assignment_forbidden).
    owner_id: UUID | None = None
    territory_id: UUID | None = None

    def changes(self) -> dict[str, Any]:
        values = {key: getattr(self, key) for key in self.model_fields_set}
        if "phones" in values and values["phones"] is not None:
            values["phones"] = [
                phone.to_entity(index) for index, phone in enumerate(values["phones"])
            ]
        return values


class AccountAssignment(BaseModel):
    owner_id: UUID | None = None
    territory_id: UUID | None = None
