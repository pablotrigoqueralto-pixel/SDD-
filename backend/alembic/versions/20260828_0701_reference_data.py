"""reference data: account/activity types, brands, loss reasons, pipelines and stages

Revision ID: 0002_reference_data
Revises: 0001_foundation
Create Date: 2026-08-28 07:01:45+00:00

Reviewed by hand after autogenerate: the deferrable unique constraint on
(pipeline_id, sort_order) is kept so reorders can swap positions in one transaction;
checks on probability and won/lost flags; one default pipeline per division.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002_reference_data"
down_revision: str | None = "0001_foundation"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "account_types",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name_es", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("buys_via_tender", sa.Boolean(), server_default="false", nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "activity_types",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name_es", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("icon", sa.Text(), nullable=False),
        sa.Column("counts_as_contact", sa.Boolean(), server_default="true", nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )
    op.create_table(
        "brands",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name", postgresql.CITEXT(), nullable=False),
        sa.Column("is_own", sa.Boolean(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name"),
    )
    op.create_index("ix_brands_is_active", "brands", ["is_active"], unique=False)
    op.create_index("ix_brands_is_own", "brands", ["is_own"], unique=False)
    op.create_table(
        "loss_reasons",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name_es", postgresql.CITEXT(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("requires_brand", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("requires_note", sa.Boolean(), server_default="false", nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name_es"),
    )
    op.create_table(
        "pipelines",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name_es", postgresql.CITEXT(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name_es"),
    )
    op.create_table(
        "brand_divisions",
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.Column("division_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["division_id"], ["divisions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("brand_id", "division_id"),
    )
    op.create_table(
        "pipeline_divisions",
        sa.Column("pipeline_id", sa.Uuid(), nullable=False),
        sa.Column("division_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["division_id"], ["divisions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["pipeline_id"], ["pipelines.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("pipeline_id", "division_id"),
        sa.UniqueConstraint("division_id", name="uq_pipeline_divisions_division_id"),
    )
    op.create_table(
        "pipeline_stages",
        sa.Column("pipeline_id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name_es", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("probability", sa.SmallInteger(), nullable=False),
        sa.Column("is_won", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_lost", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_at_risk", sa.Boolean(), server_default="false", nullable=False),
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
        sa.CheckConstraint("NOT (is_won AND is_lost)", name="ck_pipeline_stages_won_lost"),
        sa.CheckConstraint(
            "probability >= 0 AND probability <= 100", name="ck_pipeline_stages_probability"
        ),
        sa.ForeignKeyConstraint(["pipeline_id"], ["pipelines.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("pipeline_id", "code", name="uq_pipeline_stages_code"),
        sa.UniqueConstraint(
            "pipeline_id",
            "sort_order",
            deferrable=True,
            initially="DEFERRED",
            name="uq_pipeline_stages_sort_order",
        ),
    )


def downgrade() -> None:
    op.drop_table("pipeline_stages")
    op.drop_table("pipeline_divisions")
    op.drop_table("brand_divisions")
    op.drop_table("pipelines")
    op.drop_table("loss_reasons")
    op.drop_index("ix_brands_is_own", table_name="brands")
    op.drop_index("ix_brands_is_active", table_name="brands")
    op.drop_table("brands")
    op.drop_table("activity_types")
    op.drop_table("account_types")
