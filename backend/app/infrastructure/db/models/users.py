"""ORM models: users, refresh_tokens, user_territories, user_divisions."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import CITEXT, INET
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.domain.users.roles import IdentityProvider, Role
from app.infrastructure.db.models.base import (
    Base,
    IdentifiedMixin,
    TimestampedMixin,
    VersionedMixin,
)

ROLE_ENUM = Enum(Role, name="users_role_enum", values_callable=lambda e: [m.value for m in e])
IDENTITY_PROVIDER_ENUM = Enum(
    IdentityProvider,
    name="users_identity_provider_enum",
    values_callable=lambda e: [m.value for m in e],
)


class UserModel(IdentifiedMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "users"
    __table_args__ = (
        UniqueConstraint("identity_provider", "external_id", name="uq_users_provider_external_id"),
        Index("ix_users_role", "role"),
        Index("ix_users_is_active", "is_active"),
    )

    email: Mapped[str] = mapped_column(CITEXT, unique=True, nullable=False)
    full_name: Mapped[str] = mapped_column(Text, nullable=False)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    role: Mapped[Role] = mapped_column(ROLE_ENUM, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    identity_provider: Mapped[IdentityProvider] = mapped_column(
        IDENTITY_PROVIDER_ENUM,
        nullable=False,
        default=IdentityProvider.PASSWORD,
        server_default=IdentityProvider.PASSWORD.value,
    )
    external_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    failed_login_attempts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default="0"
    )
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    territory_links: Mapped[list["UserTerritoryModel"]] = relationship(
        cascade="all, delete-orphan", lazy="raise", passive_deletes=True
    )
    division_links: Mapped[list["UserDivisionModel"]] = relationship(
        cascade="all, delete-orphan", lazy="raise", passive_deletes=True
    )


class UserTerritoryModel(Base):
    __tablename__ = "user_territories"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    territory_id: Mapped[UUID] = mapped_column(
        ForeignKey("territories.id", ondelete="RESTRICT"), primary_key=True
    )


class UserDivisionModel(Base):
    __tablename__ = "user_divisions"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    division_id: Mapped[UUID] = mapped_column(
        ForeignKey("divisions.id", ondelete="RESTRICT"), primary_key=True
    )


class RefreshTokenModel(IdentifiedMixin, Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        Index("ix_refresh_tokens_user_id", "user_id"),
        Index("ix_refresh_tokens_expires_at", "expires_at"),
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    replaced_by_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("refresh_tokens.id", ondelete="SET NULL"), nullable=True
    )
    user_agent: Mapped[str | None] = mapped_column(Text, nullable=True)
    ip: Mapped[str | None] = mapped_column(INET, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
