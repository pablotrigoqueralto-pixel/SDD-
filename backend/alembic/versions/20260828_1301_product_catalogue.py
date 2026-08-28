"""product catalogue: product_families and products

Revision ID: 0005_product_catalogue
Revises: 0004_activities
Create Date: 2026-08-28 13:01:00+00:00

Reviewed by hand after autogenerate:
- products_kind_enum dropped on downgrade
- checks: prices zero or positive, name length 1..200
- unique Sage code (normalised in the domain), trigram indexes on name and sku
- family name unique within its division; families/products are never deleted
- crm_app grants on the new tables (guarded: only when the role exists)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0005_product_catalogue"
down_revision: str | None = "0004_activities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


GRANT_APP_ROLE = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON product_families, products TO crm_app;
    END IF;
END
$$;
"""


def upgrade() -> None:
    op.create_table(
        "product_families",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name_es", postgresql.CITEXT(), nullable=False),
        sa.Column("division_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["division_id"], ["divisions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name_es", "division_id", name="uq_product_families_name_division"),
    )
    op.create_index(
        "ix_product_families_division_id", "product_families", ["division_id"], unique=False
    )
    op.create_table(
        "products",
        sa.Column("sku", sa.Text(), nullable=False),
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column(
            "kind",
            sa.Enum("equipment", "consumable", "service", name="products_kind_enum"),
            nullable=False,
        ),
        sa.Column("list_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("cost_price", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("unit", sa.Text(), server_default="ud", nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "cost_price IS NULL OR cost_price >= 0", name="ck_products_cost_price_positive"
        ),
        sa.CheckConstraint("length(name) BETWEEN 1 AND 200", name="ck_products_name_length"),
        sa.CheckConstraint("list_price >= 0", name="ck_products_list_price_positive"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["family_id"], ["product_families.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("sku"),
    )
    op.create_index("ix_products_brand_id", "products", ["brand_id"], unique=False)
    op.create_index("ix_products_family_id", "products", ["family_id"], unique=False)
    op.create_index("ix_products_is_active", "products", ["is_active"], unique=False)
    op.create_index("ix_products_kind", "products", ["kind"], unique=False)
    op.create_index(
        "ix_products_name_trgm",
        "products",
        ["name"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index(
        "ix_products_sku_trgm",
        "products",
        ["sku"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"sku": "gin_trgm_ops"},
    )
    op.execute(GRANT_APP_ROLE)


def downgrade() -> None:
    op.drop_index("ix_products_sku_trgm", table_name="products")
    op.drop_index("ix_products_name_trgm", table_name="products")
    op.drop_index("ix_products_kind", table_name="products")
    op.drop_index("ix_products_is_active", table_name="products")
    op.drop_index("ix_products_family_id", table_name="products")
    op.drop_index("ix_products_brand_id", table_name="products")
    op.drop_table("products")
    op.drop_index("ix_product_families_division_id", table_name="product_families")
    op.drop_table("product_families")
    op.execute("DROP TYPE IF EXISTS products_kind_enum")
