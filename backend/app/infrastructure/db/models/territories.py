"""ORM models: territories, territory_provinces, divisions."""

from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.models.base import (
    Base,
    IdentifiedMixin,
    TimestampedMixin,
    VersionedMixin,
)

PROVINCE_CODE_CHECK = r"province_code ~ '^(0[1-9]|[1-4][0-9]|5[0-2])$'"


class TerritoryModel(IdentifiedMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "territories"

    name: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    province_links: Mapped[list["TerritoryProvinceModel"]] = relationship(
        cascade="all, delete-orphan", lazy="raise", passive_deletes=True
    )


class TerritoryProvinceModel(Base):
    __tablename__ = "territory_provinces"
    __table_args__ = (
        # One territory per province: the smart default for account assignment relies on it.
        UniqueConstraint("province_code", name="uq_territory_provinces_province_code"),
        CheckConstraint(PROVINCE_CODE_CHECK, name="ck_territory_provinces_code_format"),
    )

    territory_id: Mapped[UUID] = mapped_column(
        ForeignKey("territories.id", ondelete="CASCADE"), primary_key=True
    )
    province_code: Mapped[str] = mapped_column(String(2), primary_key=True)


class DivisionModel(IdentifiedMixin, Base):
    __tablename__ = "divisions"

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name_es: Mapped[str] = mapped_column(Text, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
