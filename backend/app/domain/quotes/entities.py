"""Quote aggregate: yearly numbering, versions, discounted lines with VAT, freezing."""

from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from decimal import ROUND_HALF_UP, Decimal
from enum import StrEnum
from uuid import UUID

from app.domain.quotes.errors import (
    InvalidVatRateError,
    QuoteNotEditableError,
    QuoteSupersededError,
)
from app.domain.shared.errors import ValidationFailedError
from app.domain.shared.ids import new_id

DESCRIPTION_MAX_LENGTH = 300
DEFAULT_VALIDITY_DAYS = 30
ALLOWED_VAT_RATES = (Decimal("21.00"), Decimal("10.00"), Decimal("4.00"), Decimal("0.00"))
DEFAULT_VAT_RATE = Decimal("21.00")

CENTS = Decimal("0.01")


def round_half_up(value: Decimal) -> Decimal:
    """Two-decimal rounding as printed on Spanish invoices."""
    return value.quantize(CENTS, rounding=ROUND_HALF_UP)


class QuoteStatus(StrEnum):
    DRAFT = "draft"
    SENT = "sent"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


@dataclass(frozen=True)
class QuoteConditions:
    validez_dias: int = DEFAULT_VALIDITY_DAYS
    plazo_entrega: str | None = None
    forma_pago: str | None = None
    garantia: str | None = None

    def as_dict(self) -> dict[str, object]:
        return {
            "validez_dias": self.validez_dias,
            "plazo_entrega": self.plazo_entrega,
            "forma_pago": self.forma_pago,
            "garantia": self.garantia,
        }


@dataclass(frozen=True)
class QuoteLineDraft:
    """Raw line values as provided by the caller; validated by the aggregate."""

    description: str
    quantity: Decimal | int | str
    unit_price: Decimal | int | str
    discount_percent: Decimal | int | str = Decimal("0")
    vat_rate: Decimal | int | str = DEFAULT_VAT_RATE
    product_id: UUID | None = None
    product_code: str | None = None
    unit_cost: Decimal | int | str | None = None


@dataclass(frozen=True)
class VatBucket:
    rate: Decimal
    base: Decimal
    vat: Decimal


@dataclass
class QuoteLine:
    id: UUID
    description: str
    quantity: Decimal
    unit_price: Decimal
    discount_percent: Decimal
    vat_rate: Decimal
    position: int
    product_id: UUID | None = None
    product_code: str | None = None
    unit_cost: Decimal | None = None

    @property
    def base(self) -> Decimal:
        gross = self.quantity * self.unit_price
        return round_half_up(gross * (Decimal("1") - self.discount_percent / Decimal("100")))

    @property
    def vat(self) -> Decimal:
        return round_half_up(self.base * self.vat_rate / Decimal("100"))

    @property
    def cost(self) -> Decimal | None:
        if self.unit_cost is None:
            return None
        return round_half_up(self.quantity * self.unit_cost)


@dataclass
class Quote:
    id: UUID
    opportunity_id: UUID
    owner_id: UUID
    created_by: UUID
    year: int
    number: int
    version: int
    status: QuoteStatus
    conditions: QuoteConditions
    total_base: Decimal
    total_vat: Decimal
    total: Decimal
    contact_id: UUID | None = None
    valid_until: date | None = None
    sent_at: datetime | None = None
    accepted_at: datetime | None = None
    rejected_at: datetime | None = None
    rejection_note: str | None = None
    superseded_at: datetime | None = None
    lines: list[QuoteLine] = field(default_factory=list)
    version_lock: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # --- creation ---------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        opportunity_id: UUID,
        owner_id: UUID,
        created_by: UUID,
        year: int,
        number: int,
        conditions: QuoteConditions,
        lines: list[QuoteLineDraft],
        now: datetime,
        contact_id: UUID | None = None,
    ) -> "Quote":
        quote = cls(
            id=new_id(),
            opportunity_id=opportunity_id,
            owner_id=owner_id,
            created_by=created_by,
            year=year,
            number=number,
            version=1,
            status=QuoteStatus.DRAFT,
            conditions=conditions,
            total_base=Decimal("0.00"),
            total_vat=Decimal("0.00"),
            total=Decimal("0.00"),
            contact_id=contact_id,
        )
        quote.lines = [_build_line(draft, position) for position, draft in enumerate(lines)]
        quote._recompute_totals()
        return quote

    # --- identity ---------------------------------------------------------

    @property
    def quote_number(self) -> str:
        return f"P-{self.year}-{self.number:04d}"

    @property
    def display_number(self) -> str:
        if self.version == 1:
            return self.quote_number
        return f"{self.quote_number}-v{self.version}"

    # --- draft editing ----------------------------------------------------

    def update_draft(
        self,
        *,
        contact_id: UUID | object | None = ...,
        conditions: QuoteConditions | None = None,
        valid_until: date | object | None = ...,
    ) -> None:
        self._ensure_draft()
        if contact_id is not ...:
            self.contact_id = contact_id if isinstance(contact_id, UUID) else None
        if conditions is not None:
            self.conditions = conditions
        if valid_until is not ...:
            self.valid_until = valid_until if isinstance(valid_until, date) else None

    def replace_lines(self, drafts: list[QuoteLineDraft]) -> None:
        self._ensure_draft()
        self.lines = [_build_line(draft, position) for position, draft in enumerate(drafts)]
        self._recompute_totals()

    def ensure_deletable(self) -> None:
        self._ensure_draft()

    # --- lifecycle --------------------------------------------------------

    def send(self, *, now: datetime, valid_until: date | None = None) -> None:
        self._ensure_draft()
        self.status = QuoteStatus.SENT
        self.sent_at = now
        days = self.conditions.validez_dias or DEFAULT_VALIDITY_DAYS
        self.valid_until = valid_until or self.valid_until or now.date() + timedelta(days=days)

    def accept(self, *, now: datetime) -> None:
        self._ensure_sent()
        self.status = QuoteStatus.ACCEPTED
        self.accepted_at = now

    def reject(self, *, now: datetime, note: str | None = None) -> None:
        self._ensure_sent()
        self.status = QuoteStatus.REJECTED
        self.rejected_at = now
        self.rejection_note = _clean_text(note)

    def supersede_by_accept(self, *, now: datetime, note: str) -> bool:
        """Auto-reject an open sibling when another quote of the opportunity is accepted."""
        if self.status not in (QuoteStatus.DRAFT, QuoteStatus.SENT):
            return False
        self.status = QuoteStatus.REJECTED
        self.rejected_at = now
        self.rejection_note = note
        return True

    def revise(self, *, created_by: UUID, now: datetime) -> "Quote":
        if self.superseded_at is not None:
            raise QuoteSupersededError()
        if self.status not in (QuoteStatus.SENT, QuoteStatus.REJECTED):
            raise QuoteNotEditableError(
                "Only the current version of a sent or rejected quote can be revised"
            )
        revision = Quote(
            id=new_id(),
            opportunity_id=self.opportunity_id,
            owner_id=self.owner_id,
            created_by=created_by,
            year=self.year,
            number=self.number,
            version=self.version + 1,
            status=QuoteStatus.DRAFT,
            conditions=self.conditions,
            total_base=self.total_base,
            total_vat=self.total_vat,
            total=self.total,
            contact_id=self.contact_id,
        )
        revision.lines = [
            replace(line, id=new_id(), position=position)
            for position, line in enumerate(self.lines)
        ]
        self.superseded_at = now
        return revision

    # --- derived reads ----------------------------------------------------

    def is_expired(self, *, today: date) -> bool:
        return (
            self.status is QuoteStatus.SENT
            and self.valid_until is not None
            and self.valid_until < today
        )

    def vat_breakdown(self) -> list[VatBucket]:
        buckets: dict[Decimal, tuple[Decimal, Decimal]] = {}
        for line in self.lines:
            base, vat = buckets.get(line.vat_rate, (Decimal("0.00"), Decimal("0.00")))
            buckets[line.vat_rate] = (base + line.base, vat + line.vat)
        return [
            VatBucket(rate=rate, base=base, vat=vat)
            for rate, (base, vat) in sorted(buckets.items(), key=lambda item: item[0], reverse=True)
        ]

    def total_margin(self) -> Decimal | None:
        """Base minus cost; None when any line lacks a cost snapshot."""
        costs: list[Decimal] = []
        for line in self.lines:
            cost = line.cost
            if cost is None:
                return None
            costs.append(cost)
        return self.total_base - sum(costs, Decimal("0.00"))

    def snapshot(self) -> dict[str, object]:
        return {
            "opportunity_id": self.opportunity_id,
            "quote_number": self.quote_number,
            "version": self.version,
            "status": self.status,
            "owner_id": self.owner_id,
            "contact_id": self.contact_id,
            "conditions": self.conditions.as_dict(),
            "total_base": str(self.total_base),
            "total_vat": str(self.total_vat),
            "total": str(self.total),
            "valid_until": self.valid_until,
            "lines": [
                {
                    "description": line.description,
                    "quantity": str(line.quantity),
                    "unit_price": str(line.unit_price),
                    "discount_percent": str(line.discount_percent),
                    "vat_rate": str(line.vat_rate),
                    "product_id": line.product_id,
                }
                for line in self.lines
            ],
        }

    # --- internals --------------------------------------------------------

    def _recompute_totals(self) -> None:
        self.total_base = sum((line.base for line in self.lines), Decimal("0.00"))
        self.total_vat = sum((line.vat for line in self.lines), Decimal("0.00"))
        self.total = self.total_base + self.total_vat

    def _ensure_draft(self) -> None:
        if self.status is not QuoteStatus.DRAFT:
            raise QuoteNotEditableError()

    def _ensure_sent(self) -> None:
        if self.status is not QuoteStatus.SENT:
            raise QuoteNotEditableError("Only sent quotes can be accepted or rejected")


def _build_line(draft: QuoteLineDraft, position: int) -> QuoteLine:
    return QuoteLine(
        id=new_id(),
        description=_clean_description(draft.description),
        quantity=_quantity(draft.quantity),
        unit_price=_money(draft.unit_price, field="unit_price"),
        discount_percent=_discount(draft.discount_percent),
        vat_rate=_vat_rate(draft.vat_rate),
        position=position,
        product_id=draft.product_id,
        product_code=draft.product_code,
        unit_cost=None if draft.unit_cost is None else _money(draft.unit_cost, field="unit_cost"),
    )


def _clean_description(value: str) -> str:
    clean = " ".join(value.split())
    if not clean or len(clean) > DESCRIPTION_MAX_LENGTH:
        raise ValidationFailedError(
            [
                {
                    "field": "description",
                    "message": f"Description must have 1 to {DESCRIPTION_MAX_LENGTH} characters",
                    "code": "description_invalid",
                }
            ]
        )
    return clean


def _money(value: Decimal | int | str, *, field: str) -> Decimal:
    try:
        amount = Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)
    except ArithmeticError as exc:
        raise ValidationFailedError(
            [{"field": field, "message": "Invalid amount", "code": f"{field}_invalid"}]
        ) from exc
    if amount < 0:
        raise ValidationFailedError(
            [{"field": field, "message": "Amount must not be negative", "code": f"{field}_invalid"}]
        )
    return amount


def _quantity(value: Decimal | int | str) -> Decimal:
    quantity = Decimal(value).quantize(CENTS, rounding=ROUND_HALF_UP)
    if quantity <= 0:
        raise ValidationFailedError(
            [
                {
                    "field": "quantity",
                    "message": "Quantity must be greater than zero",
                    "code": "quantity_invalid",
                }
            ]
        )
    return quantity


def _discount(value: Decimal | int | str) -> Decimal:
    discount = Decimal(value).quantize(CENTS)
    if discount < 0 or discount > 100:
        raise ValidationFailedError(
            [
                {
                    "field": "discount_percent",
                    "message": "Discount must be between 0 and 100",
                    "code": "discount_invalid",
                }
            ]
        )
    return discount


def _vat_rate(value: Decimal | int | str) -> Decimal:
    rate = Decimal(value).quantize(CENTS)
    if rate not in ALLOWED_VAT_RATES:
        raise InvalidVatRateError()
    return rate


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None
