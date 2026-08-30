"""ORM models: quotes, quote_lines, quote_counters, quote_pdfs, mail_outbox, app_settings."""

from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    Numeric,
    SmallInteger,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.quotes.entities import QuoteStatus
from app.infrastructure.db.models.base import Base, IdentifiedMixin, TimestampedMixin

QUOTE_STATUS_ENUM = Enum(
    QuoteStatus,
    name="quotes_status_enum",
    values_callable=lambda e: [m.value for m in e],
)

OUTBOX_STATUSES = ("sent", "failed", "skipped")
MAIL_OUTBOX_STATUS_ENUM = Enum(*OUTBOX_STATUSES, name="mail_outbox_status_enum")


class QuoteModel(IdentifiedMixin, TimestampedMixin, Base):
    __tablename__ = "quotes"
    __table_args__ = (
        UniqueConstraint("year", "number", "version", name="uq_quotes_number_version"),
        CheckConstraint("number > 0", name="ck_quotes_number_positive"),
        CheckConstraint("version > 0", name="ck_quotes_version_positive"),
        CheckConstraint("total_base >= 0", name="ck_quotes_total_base"),
        CheckConstraint(
            "status <> 'sent' OR (sent_at IS NOT NULL AND valid_until IS NOT NULL)",
            name="ck_quotes_sent_requires_stamps",
        ),
        CheckConstraint(
            "status <> 'accepted' OR accepted_at IS NOT NULL",
            name="ck_quotes_accepted_requires_stamp",
        ),
        CheckConstraint(
            "status <> 'rejected' OR rejected_at IS NOT NULL",
            name="ck_quotes_rejected_requires_stamp",
        ),
        CheckConstraint(
            "status <> 'draft' OR sent_at IS NULL",
            name="ck_quotes_draft_not_sent",
        ),
        Index(
            "ix_quotes_current_opportunity",
            "opportunity_id",
            postgresql_where="superseded_at IS NULL",
        ),
        Index(
            "ix_quotes_expiring",
            "valid_until",
            postgresql_where="status = 'sent' AND superseded_at IS NULL",
        ),
        Index("ix_quotes_owner_status", "owner_id", "status"),
    )

    opportunity_id: Mapped[UUID] = mapped_column(
        ForeignKey("opportunities.id", ondelete="RESTRICT"), nullable=False
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    contact_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("contacts.id", ondelete="SET NULL"), nullable=True
    )
    year: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[QuoteStatus] = mapped_column(QUOTE_STATUS_ENUM, nullable=False)
    conditions: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, default=dict)
    total_base: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total_vat: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    valid_until: Mapped[date | None] = mapped_column(Date, nullable=True)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    rejection_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    superseded_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    version_lock: Mapped[int] = mapped_column(
        Integer, nullable=False, default=1, server_default="1"
    )

    lines: Mapped[list["QuoteLineModel"]] = relationship(
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
        order_by="QuoteLineModel.position",
    )


class QuoteLineModel(IdentifiedMixin, TimestampedMixin, Base):
    __tablename__ = "quote_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="ck_quote_lines_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_quote_lines_unit_price"),
        CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100",
            name="ck_quote_lines_discount",
        ),
        CheckConstraint("vat_rate IN (21.00, 10.00, 4.00, 0.00)", name="ck_quote_lines_vat_rate"),
        Index("ix_quote_lines_quote_id", "quote_id"),
        Index("ix_quote_lines_product_id", "product_id"),
    )

    quote_id: Mapped[UUID] = mapped_column(
        ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="SET NULL"), nullable=True
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    product_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    quantity: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), nullable=False)
    vat_rate: Mapped[Decimal] = mapped_column(Numeric(4, 2), nullable=False)
    unit_cost: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    position: Mapped[int] = mapped_column(Integer, nullable=False)


class QuoteCounterModel(Base):
    __tablename__ = "quote_counters"

    year: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=False)
    last_number: Mapped[int] = mapped_column(Integer, nullable=False)


class QuotePdfModel(Base):
    __tablename__ = "quote_pdfs"

    quote_id: Mapped[UUID] = mapped_column(
        ForeignKey("quotes.id", ondelete="CASCADE"), primary_key=True
    )
    content: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class MailOutboxModel(IdentifiedMixin, Base):
    __tablename__ = "mail_outbox"
    __table_args__ = (Index("ix_mail_outbox_quote_id", "quote_id", "created_at"),)

    quote_id: Mapped[UUID] = mapped_column(
        ForeignKey("quotes.id", ondelete="CASCADE"), nullable=False
    )
    recipients: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, nullable=False)
    subject: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(MAIL_OUTBOX_STATUS_ENUM, nullable=False)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class AppSettingModel(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(Text, primary_key=True)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
