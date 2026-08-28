"""ORM models: opportunities, opportunity_lines and opportunity_stage_history."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.opportunities.entities import AtRiskSource, OpportunityStatus
from app.infrastructure.db.models.base import (
    Base,
    IdentifiedMixin,
    TimestampedMixin,
    VersionedMixin,
)

STATUS_ENUM = Enum(
    OpportunityStatus,
    name="opportunities_status_enum",
    values_callable=lambda e: [m.value for m in e],
)
AT_RISK_SOURCE_ENUM = Enum(
    AtRiskSource,
    name="opportunities_at_risk_source_enum",
    values_callable=lambda e: [m.value for m in e],
)


class OpportunityModel(IdentifiedMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "opportunities"
    __table_args__ = (
        CheckConstraint(
            "status <> 'won' OR won_at IS NOT NULL", name="ck_opportunities_won_requires_won_at"
        ),
        CheckConstraint(
            "status <> 'lost' OR (loss_reason_id IS NOT NULL AND lost_at IS NOT NULL)",
            name="ck_opportunities_lost_requires_reason",
        ),
        CheckConstraint(
            "is_tender OR (tender_reference IS NULL AND tender_deadline IS NULL "
            "AND estimated_award_date IS NULL)",
            name="ck_opportunities_tender_fields",
        ),
        CheckConstraint(
            "is_at_risk = (at_risk_since IS NOT NULL)", name="ck_opportunities_at_risk_since"
        ),
        CheckConstraint("estimated_amount >= 0", name="ck_opportunities_estimated_amount"),
        CheckConstraint("amount >= 0", name="ck_opportunities_amount"),
        Index("ix_opportunities_account_status", "account_id", "status"),
        Index("ix_opportunities_owner_status", "owner_id", "status"),
        Index("ix_opportunities_board", "pipeline_id", "stage_id", "status"),
        Index("ix_opportunities_close_date", "status", "expected_close_date"),
        Index(
            "ix_opportunities_tender_deadline",
            "tender_deadline",
            postgresql_where="is_tender AND status = 'open'",
        ),
        Index("ix_opportunities_at_risk", "is_at_risk", postgresql_where="is_at_risk"),
    )

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    pipeline_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipelines.id", ondelete="RESTRICT"), nullable=False
    )
    stage_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipeline_stages.id", ondelete="RESTRICT"), nullable=False
    )
    division_id: Mapped[UUID] = mapped_column(
        ForeignKey("divisions.id", ondelete="RESTRICT"), nullable=False
    )
    owner_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[OpportunityStatus] = mapped_column(STATUS_ENUM, nullable=False)
    estimated_amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    expected_close_date: Mapped[date] = mapped_column(Date, nullable=False)
    won_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    won_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    lost_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    loss_reason_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("loss_reasons.id", ondelete="RESTRICT"), nullable=True
    )
    competitor_brand_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("brands.id", ondelete="RESTRICT"), nullable=True
    )
    loss_note: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_tender: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    tender_reference: Mapped[str | None] = mapped_column(Text, nullable=True)
    tender_deadline: Mapped[date | None] = mapped_column(Date, nullable=True)
    estimated_award_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_at_risk: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    at_risk_since: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    at_risk_source: Mapped[AtRiskSource | None] = mapped_column(AT_RISK_SOURCE_ENUM, nullable=True)
    stage_entered_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    lines: Mapped[list["OpportunityLineModel"]] = relationship(
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
        order_by="OpportunityLineModel.sort_order",
    )


class OpportunityLineModel(IdentifiedMixin, TimestampedMixin, Base):
    __tablename__ = "opportunity_lines"
    __table_args__ = (
        UniqueConstraint("opportunity_id", "product_id", name="uq_opportunity_lines_product"),
        CheckConstraint("quantity > 0", name="ck_opportunity_lines_quantity"),
        CheckConstraint("unit_price >= 0", name="ck_opportunity_lines_unit_price"),
        Index("ix_opportunity_lines_opportunity_id", "opportunity_id"),
    )

    opportunity_id: Mapped[UUID] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False
    )
    product_id: Mapped[UUID] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class OpportunityStageHistoryModel(IdentifiedMixin, Base):
    __tablename__ = "opportunity_stage_history"
    __table_args__ = (
        Index("ix_opportunity_stage_history_timeline", "opportunity_id", "occurred_at"),
    )

    opportunity_id: Mapped[UUID] = mapped_column(
        ForeignKey("opportunities.id", ondelete="CASCADE"), nullable=False
    )
    from_stage_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("pipeline_stages.id", ondelete="RESTRICT"), nullable=True
    )
    to_stage_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipeline_stages.id", ondelete="RESTRICT"), nullable=False
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=True
    )
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    seconds_in_previous_stage: Mapped[int | None] = mapped_column(Integer, nullable=True)
