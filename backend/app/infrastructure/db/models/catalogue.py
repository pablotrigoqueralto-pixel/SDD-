"""ORM models: product_families and products."""

from decimal import Decimal
from uuid import UUID

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Enum,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from app.domain.catalogue.entities import ProductKind
from app.infrastructure.db.models.base import (
    Base,
    IdentifiedMixin,
    TimestampedMixin,
    VersionedMixin,
)

KIND_ENUM = Enum(
    ProductKind, name="products_kind_enum", values_callable=lambda e: [m.value for m in e]
)


class ProductFamilyModel(IdentifiedMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "product_families"
    __table_args__ = (
        UniqueConstraint("name_es", "division_id", name="uq_product_families_name_division"),
        Index("ix_product_families_division_id", "division_id"),
    )

    code: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name_es: Mapped[str] = mapped_column(CITEXT, nullable=False)
    division_id: Mapped[UUID] = mapped_column(
        ForeignKey("divisions.id", ondelete="RESTRICT"), nullable=False
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )


class ProductModel(IdentifiedMixin, TimestampedMixin, VersionedMixin, Base):
    __tablename__ = "products"
    __table_args__ = (
        CheckConstraint("list_price >= 0", name="ck_products_list_price_positive"),
        CheckConstraint(
            "cost_price IS NULL OR cost_price >= 0", name="ck_products_cost_price_positive"
        ),
        CheckConstraint("length(name) BETWEEN 1 AND 200", name="ck_products_name_length"),
        Index("ix_products_family_id", "family_id"),
        Index("ix_products_brand_id", "brand_id"),
        Index("ix_products_kind", "kind"),
        Index("ix_products_is_active", "is_active"),
        Index(
            "ix_products_name_trgm",
            "name",
            postgresql_using="gin",
            postgresql_ops={"name": "gin_trgm_ops"},
        ),
        Index(
            "ix_products_sku_trgm",
            "sku",
            postgresql_using="gin",
            postgresql_ops={"sku": "gin_trgm_ops"},
        ),
    )

    sku: Mapped[str] = mapped_column(Text, unique=True, nullable=False)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    brand_id: Mapped[UUID] = mapped_column(
        ForeignKey("brands.id", ondelete="RESTRICT"), nullable=False
    )
    family_id: Mapped[UUID] = mapped_column(
        ForeignKey("product_families.id", ondelete="RESTRICT"), nullable=False
    )
    kind: Mapped[ProductKind] = mapped_column(KIND_ENUM, nullable=False)
    list_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    cost_price: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    unit: Mapped[str] = mapped_column(Text, nullable=False, default="ud", server_default="ud")
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True, server_default="true"
    )
    created_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
