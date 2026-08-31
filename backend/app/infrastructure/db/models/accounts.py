"""ORM models: accounts, account_addresses, account_divisions, account_brands, job_titles."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.db.models.base import (
    Base,
    IdentifiedMixin,
    TimestampedMixin,
    VersionedMixin,
)
from app.infrastructure.db.models.territories import PROVINCE_CODE_CHECK

POSTAL_CODE_CHECK = "postal_code ~ '^[0-9]{5}$'"


class AccountModel(IdentifiedMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(PROVINCE_CODE_CHECK, name="ck_accounts_province_code_format"),
        CheckConstraint(
            f"postal_code IS NULL OR {POSTAL_CODE_CHECK}", name="ck_accounts_postal_code_format"
        ),
        Index(
            "ux_accounts_tax_id", "tax_id", unique=True, postgresql_where=text("tax_id IS NOT NULL")
        ),
        Index("ix_accounts_customer_code", "customer_code"),
        Index("ix_accounts_territory_id", "territory_id"),
        Index("ix_accounts_owner_id", "owner_id"),
        Index("ix_accounts_account_type_id", "account_type_id"),
        Index("ix_accounts_province_code", "province_code"),
        Index("ix_accounts_is_active", "is_active"),
        Index("ix_accounts_territory_last_contact", "territory_id", "last_contact_at"),
        Index(
            "ix_accounts_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index(
            "ix_accounts_city_trgm",
            "city",
            postgresql_using="gin",
            postgresql_ops={"city": "gin_trgm_ops"},
        ),
    )

    name: Mapped[str] = mapped_column(Text, nullable=False)
    account_type_id: Mapped[UUID] = mapped_column(
        ForeignKey("account_types.id", ondelete="RESTRICT"), nullable=False
    )
    tax_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    street: Mapped[str | None] = mapped_column(Text, nullable=True)
    postal_code: Mapped[str | None] = mapped_column(String(5), nullable=True)
    city: Mapped[str | None] = mapped_column(Text, nullable=True)
    province_code: Mapped[str] = mapped_column(String(2), nullable=False)
    territory_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("territories.id", ondelete="SET NULL"), nullable=True
    )
    owner_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    customer_code: Mapped[str | None] = mapped_column(Text, nullable=True)
    email: Mapped[str | None] = mapped_column(CITEXT, nullable=True)
    website: Mapped[str | None] = mapped_column(Text, nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    billing_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    last_contact_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_activity_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )

    addresses: Mapped[list["AccountAddressModel"]] = relationship(
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
        order_by="AccountAddressModel.label",
    )
    division_links: Mapped[list["AccountDivisionModel"]] = relationship(
        cascade="all, delete-orphan", lazy="raise", passive_deletes=True
    )
    brand_links: Mapped[list["AccountBrandModel"]] = relationship(
        cascade="all, delete-orphan", lazy="raise", passive_deletes=True
    )
    phones: Mapped[list["AccountPhoneModel"]] = relationship(
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
        order_by="AccountPhoneModel.sort_order",
    )


class AccountAddressModel(IdentifiedMixin, Base):
    __tablename__ = "account_addresses"
    __table_args__ = (
        UniqueConstraint("account_id", "label", name="uq_account_addresses_label"),
        CheckConstraint(PROVINCE_CODE_CHECK, name="ck_account_addresses_province_code_format"),
        CheckConstraint(POSTAL_CODE_CHECK, name="ck_account_addresses_postal_code_format"),
        Index("ix_account_addresses_account_id", "account_id"),
    )

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(CITEXT, nullable=False)
    street: Mapped[str] = mapped_column(Text, nullable=False)
    postal_code: Mapped[str] = mapped_column(String(5), nullable=False)
    city: Mapped[str] = mapped_column(Text, nullable=False)
    province_code: Mapped[str] = mapped_column(String(2), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)


class AccountPhoneModel(IdentifiedMixin, Base):
    """Labelled phone of a centre; order is priority (first = primary)."""

    __tablename__ = "account_phones"
    __table_args__ = (
        UniqueConstraint("account_id", "sort_order", name="uq_account_phones_sort_order"),
        UniqueConstraint("account_id", "label", "number", name="uq_account_phones_label_number"),
        Index("ix_account_phones_account_id", "account_id"),
    )

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(CITEXT, nullable=False)
    number: Mapped[str] = mapped_column(Text, nullable=False)
    extension: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class AccountDivisionModel(Base):
    __tablename__ = "account_divisions"
    __table_args__ = (Index("ix_account_divisions_division_id", "division_id"),)

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    division_id: Mapped[UUID] = mapped_column(
        ForeignKey("divisions.id", ondelete="RESTRICT"), primary_key=True
    )


class AccountBrandModel(Base):
    __tablename__ = "account_brands"

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="CASCADE"), primary_key=True
    )
    brand_id: Mapped[UUID] = mapped_column(
        ForeignKey("brands.id", ondelete="RESTRICT"), primary_key=True
    )


class JobTitleModel(IdentifiedMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "job_titles"

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name_es: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


class SpecialtyModel(IdentifiedMixin, TimestampedMixin, VersionedMixin, Base):
    """Medical specialties catalogue (change 13): what a contact practises."""

    __tablename__ = "specialties"

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name_es: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
