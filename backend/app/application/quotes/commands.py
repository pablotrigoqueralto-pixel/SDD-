"""Command payloads for quote use cases."""

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal
from uuid import UUID

from app.domain.quotes.entities import QuoteConditions
from app.domain.quotes.mail import MailRecipient


@dataclass(frozen=True)
class QuoteLineInput:
    description: str
    quantity: Decimal | int | str
    unit_price: Decimal | int | str | None = None
    discount_percent: Decimal | int | str = Decimal("0")
    vat_rate: Decimal | int | str = Decimal("21.00")
    product_id: UUID | None = None


@dataclass(frozen=True)
class CreateQuote:
    opportunity_id: UUID
    contact_id: UUID | None = None


@dataclass(frozen=True)
class UpdateQuoteDraft:
    expected_version: int
    contact_id: UUID | object | None = ...
    conditions: QuoteConditions | None = None
    valid_until: date | object | None = ...
    lines: list[QuoteLineInput] | None = None


@dataclass(frozen=True)
class SendQuote:
    expected_version: int
    recipients: list[MailRecipient] = field(default_factory=list)
    subject: str = ""
    body: str = ""
    valid_until: date | None = None
    skip_email: bool = False


@dataclass(frozen=True)
class AcceptQuote:
    expected_version: int
    occurred_on: date | None = None


@dataclass(frozen=True)
class RejectQuote:
    expected_version: int
    note: str | None = None
