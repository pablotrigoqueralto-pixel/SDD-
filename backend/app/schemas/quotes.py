"""Quote API schemas. Amounts travel as two-decimal strings; cost is role-gated."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.application.quotes.queries import QuoteSummary, QuoteVersionRef
from app.domain.quotes.entities import Quote, QuoteConditions, QuoteLine, QuoteStatus
from app.schemas.catalogue import Price, PriceInput


class QuoteConditionsRead(BaseModel):
    validez_dias: int
    plazo_entrega: str | None
    forma_pago: str | None
    garantia: str | None

    @classmethod
    def from_entity(cls, conditions: QuoteConditions) -> "QuoteConditionsRead":
        return cls(
            validez_dias=conditions.validez_dias,
            plazo_entrega=conditions.plazo_entrega,
            forma_pago=conditions.forma_pago,
            garantia=conditions.garantia,
        )


class QuoteConditionsInput(BaseModel):
    validez_dias: int = Field(ge=1, le=365)
    plazo_entrega: str | None = Field(default=None, max_length=200)
    forma_pago: str | None = Field(default=None, max_length=200)
    garantia: str | None = Field(default=None, max_length=200)

    def to_entity(self) -> QuoteConditions:
        return QuoteConditions(
            validez_dias=self.validez_dias,
            plazo_entrega=self.plazo_entrega,
            forma_pago=self.forma_pago,
            garantia=self.garantia,
        )


class VatBucketRead(BaseModel):
    rate: Price
    base: Price
    vat: Price


def _line_fields(line: QuoteLine) -> dict[str, object]:
    return {
        "id": line.id,
        "product_id": line.product_id,
        "product_code": line.product_code,
        "description": line.description,
        "quantity": line.quantity,
        "unit_price": line.unit_price,
        "discount_percent": line.discount_percent,
        "vat_rate": line.vat_rate,
        "base": line.base,
        "vat": line.vat,
        "position": line.position,
    }


class QuoteLinePublicRead(BaseModel):
    id: UUID
    product_id: UUID | None
    product_code: str | None
    description: str
    quantity: Price
    unit_price: Price
    discount_percent: Price
    vat_rate: Price
    base: Price
    vat: Price
    position: int

    @classmethod
    def from_entity(cls, line: QuoteLine) -> "QuoteLinePublicRead":
        return cls.model_validate(_line_fields(line))


class QuoteLineRead(QuoteLinePublicRead):
    unit_cost: Price | None

    @classmethod
    def from_entity(cls, line: QuoteLine) -> "QuoteLineRead":
        return cls.model_validate({**_line_fields(line), "unit_cost": line.unit_cost})


class QuoteVersionRead(BaseModel):
    id: UUID
    revision: int
    status: QuoteStatus
    sent_at: datetime | None

    @classmethod
    def from_ref(cls, ref: QuoteVersionRef) -> "QuoteVersionRead":
        return cls(id=ref.id, revision=ref.revision, status=ref.status, sent_at=ref.sent_at)


class QuoteSummaryRead(BaseModel):
    id: UUID
    opportunity_id: UUID
    opportunity_name: str
    account_id: UUID
    account_name: str
    quote_number: str
    display_number: str
    revision: int
    status: QuoteStatus
    total: Price
    valid_until: date | None
    is_expired: bool
    owner_id: UUID
    owner_name: str
    version: int
    sent_at: datetime | None
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def from_summary(cls, summary: QuoteSummary) -> "QuoteSummaryRead":
        return cls(
            id=summary.id,
            opportunity_id=summary.opportunity_id,
            opportunity_name=summary.opportunity_name,
            account_id=summary.account_id,
            account_name=summary.account_name,
            quote_number=summary.quote_number,
            display_number=summary.display_number,
            revision=summary.revision,
            status=summary.status,
            total=summary.total,
            valid_until=summary.valid_until,
            is_expired=summary.is_expired,
            owner_id=summary.owner_id,
            owner_name=summary.owner_name,
            version=summary.version_lock,
            sent_at=summary.sent_at,
            created_at=summary.created_at,
            updated_at=summary.updated_at,
        )


def _quote_fields(
    quote: Quote,
    *,
    account_id: UUID,
    account_name: str,
    opportunity_name: str,
    owner_name: str,
    today: date,
    versions: list[QuoteVersionRef],
    email_status: str | None,
    email_error: str | None,
) -> dict[str, object]:
    return {
        "id": quote.id,
        "opportunity_id": quote.opportunity_id,
        "opportunity_name": opportunity_name,
        "account_id": account_id,
        "account_name": account_name,
        "quote_number": quote.quote_number,
        "display_number": quote.display_number,
        "revision": quote.version,
        "status": quote.status,
        "owner_id": quote.owner_id,
        "owner_name": owner_name,
        "contact_id": quote.contact_id,
        "conditions": QuoteConditionsRead.from_entity(quote.conditions),
        "total_base": quote.total_base,
        "total_vat": quote.total_vat,
        "total": quote.total,
        "vat_breakdown": [
            VatBucketRead(rate=bucket.rate, base=bucket.base, vat=bucket.vat)
            for bucket in quote.vat_breakdown()
        ],
        "valid_until": quote.valid_until,
        "is_expired": quote.is_expired(today=today),
        "sent_at": quote.sent_at,
        "accepted_at": quote.accepted_at,
        "rejected_at": quote.rejected_at,
        "rejection_note": quote.rejection_note,
        "superseded_at": quote.superseded_at,
        "versions": [QuoteVersionRead.from_ref(ref) for ref in versions],
        "email_status": email_status,
        "email_error": email_error,
        "version": quote.version_lock,
        "created_at": quote.created_at,
        "updated_at": quote.updated_at,
    }


class QuotePublicRead(BaseModel):
    id: UUID
    opportunity_id: UUID
    opportunity_name: str
    account_id: UUID
    account_name: str
    quote_number: str
    display_number: str
    revision: int
    status: QuoteStatus
    owner_id: UUID
    owner_name: str
    contact_id: UUID | None
    conditions: QuoteConditionsRead
    total_base: Price
    total_vat: Price
    total: Price
    vat_breakdown: list[VatBucketRead]
    valid_until: date | None
    is_expired: bool
    sent_at: datetime | None
    accepted_at: datetime | None
    rejected_at: datetime | None
    rejection_note: str | None
    superseded_at: datetime | None
    versions: list[QuoteVersionRead]
    email_status: str | None
    email_error: str | None
    version: int
    created_at: datetime | None
    updated_at: datetime | None
    lines: list[QuoteLinePublicRead]

    @classmethod
    def build(cls, quote: Quote, **context: object) -> "QuotePublicRead":
        fields = _quote_fields(quote, **context)  # type: ignore[arg-type]
        fields["lines"] = [QuoteLinePublicRead.from_entity(line) for line in quote.lines]
        return cls.model_validate(fields)


class QuoteRead(QuotePublicRead):
    lines: list[QuoteLineRead]  # type: ignore[assignment]
    total_margin: Price | None

    @classmethod
    def build(cls, quote: Quote, **context: object) -> "QuoteRead":
        fields = _quote_fields(quote, **context)  # type: ignore[arg-type]
        fields["lines"] = [QuoteLineRead.from_entity(line) for line in quote.lines]
        fields["total_margin"] = quote.total_margin()
        return cls.model_validate(fields)


class QuoteLineInputSchema(BaseModel):
    description: str = Field(min_length=1, max_length=300)
    quantity: PriceInput
    unit_price: PriceInput | None = None
    discount_percent: Decimal = Field(default=Decimal("0"), ge=0, le=100)
    vat_rate: Decimal = Decimal("21.00")
    product_id: UUID | None = None


class QuoteCreate(BaseModel):
    opportunity_id: UUID
    contact_id: UUID | None = None


class QuoteUpdate(BaseModel):
    """PATCH a draft: only provided fields change; `lines` replaces the whole list."""

    contact_id: UUID | None = None
    conditions: QuoteConditionsInput | None = None
    valid_until: date | None = None
    lines: list[QuoteLineInputSchema] | None = None


class MailRecipientInput(BaseModel):
    email: str = Field(min_length=3, max_length=200)
    name: str | None = Field(default=None, max_length=200)


class QuoteSend(BaseModel):
    recipients: list[MailRecipientInput] = Field(default_factory=list)
    subject: str = Field(default="", max_length=300)
    body: str = Field(default="", max_length=10000)
    valid_until: date | None = None
    skip_email: bool = False


class QuoteAccept(BaseModel):
    occurred_on: date | None = None


class QuoteReject(BaseModel):
    note: str | None = Field(default=None, max_length=2000)


class QuoteSettingsRead(BaseModel):
    conditions_defaults: dict[str, object]
    email_template: dict[str, object]


class QuoteEmailTemplateInput(BaseModel):
    subject: str = Field(min_length=1, max_length=300)
    body: str = Field(min_length=1, max_length=10000)


class QuoteSettingsUpdate(BaseModel):
    conditions_defaults: QuoteConditionsInput
    email_template: QuoteEmailTemplateInput
