"""Input DTOs for catalogue use cases."""

from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from typing import Any
from uuid import UUID

from app.domain.catalogue.entities import ProductKind


@dataclass(frozen=True)
class CreateProduct:
    sku: str
    name: str
    brand_id: UUID
    family_id: UUID
    kind: ProductKind
    list_price: Decimal
    cost_price: Decimal | None = None
    unit: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class UpdateProduct:
    """PATCH semantics: only keys present in `changes` are applied (None clears)."""

    expected_version: int
    changes: Mapping[str, Any]


@dataclass(frozen=True)
class ImportProduct:
    """One row of the Sage export: brand by code or name, family by code."""

    sku: str
    name: str
    family_code: str
    kind: ProductKind
    list_price: Decimal
    brand_code: str | None = None
    brand_name: str | None = None
    cost_price: Decimal | None = None
    unit: str | None = None
    description: str | None = None
    is_active: bool = True
