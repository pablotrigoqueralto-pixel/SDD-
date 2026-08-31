"""ORM models: contacts and the append-only personal_data_access_log."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.contacts.entities import ConsentSource, ConsentStatus, PreferredChannel
from app.infrastructure.db.models.base import (
    Base,
    IdentifiedMixin,
    TimestampedMixin,
    VersionedMixin,
)

PREFERRED_CHANNEL_ENUM = Enum(
    PreferredChannel,
    name="contacts_preferred_channel_enum",
    values_callable=lambda e: [m.value for m in e],
)
CONSENT_STATUS_ENUM = Enum(
    ConsentStatus,
    name="contacts_consent_status_enum",
    values_callable=lambda e: [m.value for m in e],
)
CONSENT_SOURCE_ENUM = Enum(
    ConsentSource,
    name="contacts_consent_source_enum",
    values_callable=lambda e: [m.value for m in e],
)


class ContactModel(IdentifiedMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "contacts"
    __table_args__ = (
        Index(
            "ux_contacts_primary_per_account",
            "account_id",
            unique=True,
            postgresql_where=text("is_primary"),
        ),
        Index("ix_contacts_account_id", "account_id"),
        Index("ix_contacts_email", "email"),
        CheckConstraint(
            "consent_status = 'unknown' OR (consent_at IS NOT NULL AND consent_source IS NOT NULL)",
            name="ck_contacts_consent_complete",
        ),
        # `phone` cannot be checked here: the numbers live in contact_phones and a
        # CHECK cannot span tables. Contact.validate_channels() enforces it.
        CheckConstraint(
            "preferred_channel IS NULL"
            " OR preferred_channel = 'phone'"
            " OR (preferred_channel = 'email' AND email IS NOT NULL)",
            name="ck_contacts_preferred_channel_value",
        ),
    )

    account_id: Mapped[UUID] = mapped_column(
        ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    first_name: Mapped[str] = mapped_column(Text, nullable=False)
    last_name: Mapped[str] = mapped_column(Text, nullable=False)
    job_title_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("job_titles.id", ondelete="RESTRICT"), nullable=True
    )
    division_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("divisions.id", ondelete="RESTRICT"), nullable=True
    )
    email: Mapped[str | None] = mapped_column(CITEXT, nullable=True)
    is_head_of_department: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    preferred_channel: Mapped[PreferredChannel | None] = mapped_column(
        PREFERRED_CHANNEL_ENUM, nullable=True
    )
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_primary: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, server_default="false"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    consent_status: Mapped[ConsentStatus] = mapped_column(
        CONSENT_STATUS_ENUM,
        nullable=False,
        default=ConsentStatus.UNKNOWN,
        server_default=ConsentStatus.UNKNOWN.value,
    )
    consent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    consent_source: Mapped[ConsentSource | None] = mapped_column(CONSENT_SOURCE_ENUM, nullable=True)
    consent_recorded_by: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    anonymised_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    phones: Mapped[list["ContactPhoneModel"]] = relationship(
        cascade="all, delete-orphan",
        lazy="raise",
        passive_deletes=True,
        order_by="ContactPhoneModel.sort_order",
    )


class ContactPhoneModel(IdentifiedMixin, Base):
    """Labelled phone of a contact — personal data: anonymisation deletes these rows."""

    __tablename__ = "contact_phones"
    __table_args__ = (
        UniqueConstraint("contact_id", "sort_order", name="uq_contact_phones_sort_order"),
        UniqueConstraint("contact_id", "label", "number", name="uq_contact_phones_label_number"),
        Index("ix_contact_phones_contact_id", "contact_id"),
    )

    contact_id: Mapped[UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str] = mapped_column(CITEXT, nullable=False)
    number: Mapped[str] = mapped_column(Text, nullable=False)
    extension: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)


class PersonalDataAccessLogModel(IdentifiedMixin, Base):
    __tablename__ = "personal_data_access_log"
    __table_args__ = (
        Index("ix_personal_data_access_contact", "contact_id", text("occurred_at DESC")),
        Index("ix_personal_data_access_user", "user_id", text("occurred_at DESC")),
    )

    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    contact_id: Mapped[UUID] = mapped_column(
        ForeignKey("contacts.id", ondelete="RESTRICT"), nullable=False
    )
    trace_id: Mapped[str | None] = mapped_column(Text, nullable=True)
