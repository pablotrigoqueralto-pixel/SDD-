"""Quote PDF document model and renderer protocol."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from typing import Protocol

from app.domain.quotes.entities import QuoteConditions, VatBucket


@dataclass(frozen=True)
class PdfLine:
    description: str
    product_code: str | None
    quantity: Decimal
    unit_price: Decimal
    discount_percent: Decimal
    vat_rate: Decimal
    base: Decimal


@dataclass(frozen=True)
class QuotePdfDocument:
    display_number: str
    issued_on: date
    valid_until: date | None
    account_name: str
    account_province: str | None
    contact_name: str | None
    owner_name: str
    owner_email: str
    conditions: QuoteConditions
    lines: list[PdfLine] = field(default_factory=list)
    vat_breakdown: list[VatBucket] = field(default_factory=list)
    total_base: Decimal = Decimal("0.00")
    total_vat: Decimal = Decimal("0.00")
    total: Decimal = Decimal("0.00")


class QuotePdfRenderer(Protocol):
    def render(self, document: QuotePdfDocument) -> bytes: ...
