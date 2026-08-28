"""Input DTOs for opportunity use cases."""

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID


@dataclass(frozen=True)
class CreateOpportunity:
    account_id: UUID
    division_id: UUID
    estimated_amount: Decimal
    pipeline_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    expected_close_date: date | None = None
    is_tender: bool | None = None
    tender_reference: str | None = None
    tender_deadline: date | None = None
    estimated_award_date: date | None = None
    owner_id: UUID | None = None


@dataclass(frozen=True)
class UpdateOpportunity:
    """PATCH semantics: only keys present in `changes` are applied (None clears)."""

    expected_version: int
    changes: Mapping[str, Any]


@dataclass(frozen=True)
class WinOpportunity:
    expected_version: int
    won_amount: Decimal | None = None
    won_at: datetime | None = None


@dataclass(frozen=True)
class LoseOpportunity:
    expected_version: int
    loss_reason_id: UUID
    competitor_brand_id: UUID | None = None
    note: str | None = None


@dataclass(frozen=True)
class AddLine:
    expected_version: int
    product_id: UUID
    quantity: Decimal
    unit_price: Decimal | None = None


@dataclass(frozen=True)
class UpdateLine:
    expected_version: int
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
