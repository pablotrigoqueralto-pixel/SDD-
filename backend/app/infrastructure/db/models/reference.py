"""ORM models: account_types, activity_types, brands, loss_reasons, pipelines, stages."""

from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    SmallInteger,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.models.base import (
    Base,
    IdentifiedMixin,
    TimestampedMixin,
    VersionedMixin,
)


class AccountTypeModel(IdentifiedMixin, TimestampedMixin, Base):
    __tablename__ = "account_types"

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name_es: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    buys_via_tender: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


class ActivityTypeModel(IdentifiedMixin, TimestampedMixin, Base):
    __tablename__ = "activity_types"

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name_es: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    icon: Mapped[str] = mapped_column(Text, nullable=False)
    counts_as_contact: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


class BrandModel(IdentifiedMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "brands"
    __table_args__ = (
        Index("ix_brands_is_own", "is_own"),
        Index("ix_brands_is_active", "is_active"),
    )

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    is_own: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    division_links: Mapped[list["BrandDivisionModel"]] = relationship(
        cascade="all, delete-orphan", lazy="raise", passive_deletes=True
    )


class BrandDivisionModel(Base):
    __tablename__ = "brand_divisions"

    brand_id: Mapped[UUID] = mapped_column(
        ForeignKey("brands.id", ondelete="CASCADE"), primary_key=True
    )
    division_id: Mapped[UUID] = mapped_column(
        ForeignKey("divisions.id", ondelete="RESTRICT"), primary_key=True
    )


class LossReasonModel(IdentifiedMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "loss_reasons"

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name_es: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    requires_brand: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    requires_note: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


class PipelineModel(IdentifiedMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "pipelines"

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name_es: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)

    division_links: Mapped[list["PipelineDivisionModel"]] = relationship(
        cascade="all, delete-orphan", lazy="raise", passive_deletes=True
    )
    stages: Mapped[list["PipelineStageModel"]] = relationship(
        lazy="raise", order_by="PipelineStageModel.sort_order"
    )


class PipelineDivisionModel(Base):
    __tablename__ = "pipeline_divisions"
    __table_args__ = (
        # One default pipeline per division (smart default when creating an opportunity).
        UniqueConstraint("division_id", name="uq_pipeline_divisions_division_id"),
    )

    pipeline_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipelines.id", ondelete="CASCADE"), primary_key=True
    )
    division_id: Mapped[UUID] = mapped_column(
        ForeignKey("divisions.id", ondelete="RESTRICT"), primary_key=True
    )


class PipelineStageModel(IdentifiedMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "pipeline_stages"
    __table_args__ = (
        UniqueConstraint("pipeline_id", "code", name="uq_pipeline_stages_code"),
        # Deferred so a reorder can swap positions inside one transaction.
        UniqueConstraint(
            "pipeline_id",
            "sort_order",
            name="uq_pipeline_stages_sort_order",
            deferrable=True,
            initially="DEFERRED",
        ),
        CheckConstraint(
            "probability >= 0 AND probability <= 100", name="ck_pipeline_stages_probability"
        ),
        CheckConstraint("NOT (is_won AND is_lost)", name="ck_pipeline_stages_won_lost"),
    )

    pipeline_id: Mapped[UUID] = mapped_column(
        ForeignKey("pipelines.id", ondelete="RESTRICT"), nullable=False
    )
    code: Mapped[str] = mapped_column(Text, nullable=False)
    name_es: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    probability: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_won: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_lost: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_at_risk: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
