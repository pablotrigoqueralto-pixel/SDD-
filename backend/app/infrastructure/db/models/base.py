"""Declarative base and column mixins shared by every ORM model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.domain.shared.ids import new_id


class Base(DeclarativeBase):
    pass


class IdentifiedMixin:
    id: Mapped[UUID] = mapped_column(primary_key=True, default=new_id)


class TimestampedMixin:
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class VersionedMixin:
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
