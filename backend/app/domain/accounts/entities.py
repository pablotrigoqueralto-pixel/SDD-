"""Account ("centro") aggregate root: primary address, additional addresses, links."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.domain.accounts.errors import (
    AddressLabelDuplicatedError,
    DuplicatePhoneError,
    InvalidPhoneExtensionError,
    PhoneLabelRequiredError,
    TooManyAddressesError,
)
from app.domain.accounts.value_objects import PhoneNumber, PostalCode, TaxId
from app.domain.shared.ids import new_id
from app.domain.territories.entities import validate_province_codes
from app.domain.users.value_objects import Email

MAX_ADDITIONAL_ADDRESSES = 10


@dataclass(frozen=True)
class PhoneEntry:
    """One labelled phone of an account or a contact (design D1/D10).

    The number is always E.164; the extension lives apart so the dialer can use
    it (`tel:+34915550001;ext=4021`) and so phone search keeps matching digits.
    """

    label: str
    number: str
    extension: str | None = None
    note: str | None = None

    @classmethod
    def create(
        cls,
        *,
        label: str,
        number: str,
        extension: str | None = None,
        note: str | None = None,
        field_name: str = "phones",
    ) -> "PhoneEntry":
        clean_label = label.strip()
        if not clean_label:
            raise PhoneLabelRequiredError(field_name)
        clean_extension = extension.strip() if extension else None
        if clean_extension is not None and clean_extension and not clean_extension.isdigit():
            raise InvalidPhoneExtensionError(field_name)
        clean_note = note.strip() if note else None
        return cls(
            label=clean_label,
            number=PhoneNumber(number, field=field_name).value,
            extension=clean_extension or None,
            note=clean_note or None,
        )


def normalise_phone_list(phones: Sequence[PhoneEntry]) -> list[PhoneEntry]:
    """Validate a whole list: order is priority, the first entry is the primary one."""
    seen: set[tuple[str, str]] = set()
    result: list[PhoneEntry] = []
    for phone in phones:
        key = (phone.label.casefold(), phone.number)
        if key in seen:
            raise DuplicatePhoneError(phone.label)
        seen.add(key)
        result.append(phone)
    return result


@dataclass(frozen=True)
class AdditionalAddress:
    label: str
    street: str
    postal_code: str
    city: str
    province_code: str
    notes: str | None = None

    @classmethod
    def create(
        cls,
        *,
        label: str,
        street: str,
        postal_code: str,
        city: str,
        province_code: str,
        notes: str | None = None,
    ) -> "AdditionalAddress":
        validate_province_codes(frozenset({province_code}))
        return cls(
            label=label.strip(),
            street=street.strip(),
            postal_code=PostalCode(postal_code, field="addresses.postal_code").value,
            city=city.strip(),
            province_code=province_code,
            notes=_clean_optional(notes),
        )

    def as_dict(self) -> dict[str, str | None]:
        return {
            "label": self.label,
            "street": self.street,
            "postal_code": self.postal_code,
            "city": self.city,
            "province_code": self.province_code,
            "notes": self.notes,
        }


def validate_additional_addresses(addresses: Sequence[AdditionalAddress]) -> None:
    if len(addresses) > MAX_ADDITIONAL_ADDRESSES:
        raise TooManyAddressesError(MAX_ADDITIONAL_ADDRESSES)
    seen: set[str] = set()
    for address in addresses:
        key = address.label.casefold()
        if key in seen:
            raise AddressLabelDuplicatedError(address.label)
        seen.add(key)


def _clean_optional(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


# Fields a PATCH may touch, with their normaliser. Owner/territory go through `assign`.
DETAIL_FIELDS: frozenset[str] = frozenset(
    {
        "name",
        "account_type_id",
        "province_code",
        "street",
        "postal_code",
        "city",
        "tax_id",
        "phones",
        "email",
        "website",
        "customer_code",
        "notes",
        "billing_notes",
        "division_ids",
        "brand_ids",
    }
)
ADMINISTRATIVE_FIELDS: frozenset[str] = frozenset(
    {
        "tax_id",
        "customer_code",
        "street",
        "postal_code",
        "city",
        "province_code",
        "phones",
        "email",
        "website",
        "billing_notes",
    }
)


@dataclass
class Account:
    id: UUID
    name: str
    account_type_id: UUID
    province_code: str
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    tax_id: str | None = None
    email: str | None = None
    website: str | None = None
    customer_code: str | None = None
    notes: str | None = None
    billing_notes: str | None = None
    territory_id: UUID | None = None
    owner_id: UUID | None = None
    division_ids: frozenset[UUID] = field(default_factory=frozenset)
    brand_ids: frozenset[UUID] = field(default_factory=frozenset)
    addresses: list[AdditionalAddress] = field(default_factory=list)
    phones: list[PhoneEntry] = field(default_factory=list)
    last_contact_at: datetime | None = None
    next_activity_at: datetime | None = None
    is_active: bool = True
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        name: str,
        account_type_id: UUID,
        province_code: str,
        territory_id: UUID | None,
        owner_id: UUID | None,
        details: Mapping[str, Any] | None = None,
    ) -> "Account":
        validate_province_codes(frozenset({province_code}))
        account = cls(
            id=new_id(),
            name=name.strip(),
            account_type_id=account_type_id,
            province_code=province_code,
            territory_id=territory_id,
            owner_id=owner_id,
        )
        if details:
            account.update_details(details)
        return account

    # --- details ---------------------------------------------------------

    def update_details(self, changes: Mapping[str, Any]) -> None:
        """Apply PATCH-style changes; keys outside DETAIL_FIELDS are ignored by design."""
        for key, value in changes.items():
            if key not in DETAIL_FIELDS:
                continue
            setattr(self, key, _normalise(key, value))

    def replace_addresses(self, addresses: Sequence[AdditionalAddress]) -> None:
        validate_additional_addresses(addresses)
        self.addresses = list(addresses)

    # --- assignment ------------------------------------------------------

    def assign(self, *, owner_id: UUID | None, territory_id: UUID | None) -> None:
        self.owner_id = owner_id
        self.territory_id = territory_id

    def territory_mismatch(self, province_territory_id: UUID | None) -> bool:
        """True when the province's territory differs from the assigned one."""
        return province_territory_id != self.territory_id

    # --- lifecycle -------------------------------------------------------

    def activate(self) -> None:
        self.is_active = True

    def deactivate(self) -> None:
        self.is_active = False

    def snapshot(self) -> dict[str, object]:
        return {
            "name": self.name,
            "account_type_id": self.account_type_id,
            "province_code": self.province_code,
            "street": self.street,
            "postal_code": self.postal_code,
            "city": self.city,
            "tax_id": self.tax_id,
            "phones": [p.number for p in self.phones],
            "email": self.email,
            "website": self.website,
            "customer_code": self.customer_code,
            "notes": self.notes,
            "billing_notes": self.billing_notes,
            "division_ids": self.division_ids,
            "brand_ids": self.brand_ids,
            "is_active": self.is_active,
        }


def _normalise(key: str, value: Any) -> Any:
    if key == "name":
        return str(value).strip()
    if key == "account_type_id":
        return value
    if key == "province_code":
        validate_province_codes(frozenset({str(value)}))
        return str(value)
    if key in {"division_ids", "brand_ids"}:
        return frozenset(value)
    if key == "phones":
        return normalise_phone_list(list(value or []))
    if value is None:
        return None
    text = str(value)
    if key == "tax_id":
        return TaxId(text).value
    if key == "postal_code":
        return PostalCode(text).value
    if key == "email":
        return Email(text).value
    return _clean_optional(text)
