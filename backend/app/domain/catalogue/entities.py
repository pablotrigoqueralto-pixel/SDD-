"""Product aggregate: Sage article code, brand, family, kind and prices."""

import re
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.domain.catalogue.errors import PriceInvalidError, ProductFieldInvalidError, SkuLockedError
from app.domain.shared.ids import new_id

NAME_MAX_LENGTH = 200
UNIT_MAX_LENGTH = 20
DESCRIPTION_MAX_LENGTH = 2000
SKU_MAX_LENGTH = 50
DEFAULT_UNIT = "ud"
PRICE_QUANTUM = Decimal("0.01")

_WHITESPACE = re.compile(r"\s+")


class ProductKind(StrEnum):
    EQUIPMENT = "equipment"
    CONSUMABLE = "consumable"
    SERVICE = "service"


def normalise_sku(raw: str) -> str:
    """Trim, upper-case and collapse internal whitespace (Sage exports mix cases)."""
    sku = _WHITESPACE.sub(" ", raw.strip()).upper()
    if not sku:
        raise ProductFieldInvalidError("sku", "The Sage code is required")
    if len(sku) > SKU_MAX_LENGTH:
        raise ProductFieldInvalidError("sku", f"The Sage code exceeds {SKU_MAX_LENGTH} characters")
    return sku


def normalise_price(value: Decimal | int | str, *, field: str) -> Decimal:
    price = Decimal(value).quantize(PRICE_QUANTUM)
    if price < 0:
        raise PriceInvalidError(field)
    return price


def _clean_name(name: str) -> str:
    clean = _WHITESPACE.sub(" ", name.strip())
    if not clean or len(clean) > NAME_MAX_LENGTH:
        raise ProductFieldInvalidError("name", f"Name must have 1 to {NAME_MAX_LENGTH} characters")
    return clean


def _clean_unit(unit: str | None) -> str:
    clean = (unit or "").strip() or DEFAULT_UNIT
    if len(clean) > UNIT_MAX_LENGTH:
        raise ProductFieldInvalidError("unit", f"Unit exceeds {UNIT_MAX_LENGTH} characters")
    return clean


def _clean_description(description: str | None) -> str | None:
    clean = (description or "").strip() or None
    if clean is not None and len(clean) > DESCRIPTION_MAX_LENGTH:
        raise ProductFieldInvalidError(
            "description", f"Description exceeds {DESCRIPTION_MAX_LENGTH} characters"
        )
    return clean


@dataclass
class Product:
    id: UUID
    sku: str
    name: str
    brand_id: UUID
    family_id: UUID
    kind: ProductKind
    list_price: Decimal
    created_by: UUID
    cost_price: Decimal | None = None
    unit: str = DEFAULT_UNIT
    description: str | None = None
    is_active: bool = True
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    @classmethod
    def create(
        cls,
        *,
        sku: str,
        name: str,
        brand_id: UUID,
        family_id: UUID,
        kind: ProductKind,
        list_price: Decimal | int | str,
        created_by: UUID,
        cost_price: Decimal | int | str | None = None,
        unit: str | None = None,
        description: str | None = None,
        is_active: bool = True,
    ) -> "Product":
        return cls(
            id=new_id(),
            sku=normalise_sku(sku),
            name=_clean_name(name),
            brand_id=brand_id,
            family_id=family_id,
            kind=kind,
            list_price=normalise_price(list_price, field="list_price"),
            cost_price=(
                normalise_price(cost_price, field="cost_price") if cost_price is not None else None
            ),
            unit=_clean_unit(unit),
            description=_clean_description(description),
            is_active=is_active,
            created_by=created_by,
        )

    def change_sku(self, sku: str, *, referenced: bool) -> None:
        clean = normalise_sku(sku)
        if clean == self.sku:
            return
        if referenced:
            raise SkuLockedError()
        self.sku = clean

    def rename(self, name: str) -> None:
        self.name = _clean_name(name)

    def set_brand(self, brand_id: UUID) -> None:
        self.brand_id = brand_id

    def set_family(self, family_id: UUID) -> None:
        self.family_id = family_id

    def set_kind(self, kind: ProductKind) -> None:
        self.kind = kind

    def set_list_price(self, price: Decimal | int | str) -> None:
        self.list_price = normalise_price(price, field="list_price")

    def set_cost_price(self, price: Decimal | int | str | None) -> None:
        self.cost_price = normalise_price(price, field="cost_price") if price is not None else None

    def set_unit(self, unit: str | None) -> None:
        self.unit = _clean_unit(unit)

    def set_description(self, description: str | None) -> None:
        self.description = _clean_description(description)

    def activate(self) -> bool:
        """Returns True when the state changed (deactivate/activate are idempotent)."""
        changed = not self.is_active
        self.is_active = True
        return changed

    def deactivate(self) -> bool:
        changed = self.is_active
        self.is_active = False
        return changed

    def snapshot(self) -> dict[str, object]:
        return {
            "sku": self.sku,
            "name": self.name,
            "brand_id": self.brand_id,
            "family_id": self.family_id,
            "kind": self.kind,
            "list_price": str(self.list_price),
            "cost_price": str(self.cost_price) if self.cost_price is not None else None,
            "unit": self.unit,
            "description": self.description,
            "is_active": self.is_active,
        }
