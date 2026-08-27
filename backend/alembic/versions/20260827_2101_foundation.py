"""foundation: users, refresh tokens, territories, divisions, scope links, audit log

Revision ID: 0001_foundation
Revises:
Create Date: 2026-08-27 21:01:52+00:00

Reviewed by hand after autogenerate:
- citext extension created first (case-insensitive unique email / territory name)
- refresh_tokens.created_at uses now() as a SQL function, not a literal
- audit_log is append-only: INSERT/SELECT granted to crm_app when that role exists
- downgrade drops the PostgreSQL enum types created by this revision
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0001_foundation"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

ROLE_ENUM = sa.Enum("sales_rep", "sales_manager", "back_office", "admin", name="users_role_enum")
IDENTITY_PROVIDER_ENUM = sa.Enum("password", "entra_id", name="users_identity_provider_enum")

# Only applied when the least-privilege application role exists (created by the seed / ops).
GRANT_AUDIT_LOG_APPEND_ONLY = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_app') THEN
        GRANT SELECT, INSERT ON audit_log TO crm_app;
    END IF;
END
$$;
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")

    op.create_table(
        "audit_log",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("actor_id", sa.Uuid(), nullable=True),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("changes", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_audit_log_actor",
        "audit_log",
        ["actor_id", sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_audit_log_entity",
        "audit_log",
        ["entity_type", "entity_id", sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_audit_log_occurred_at",
        "audit_log",
        [sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.execute(GRANT_AUDIT_LOG_APPEND_ONLY)

    op.create_table(
        "divisions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name_es", sa.Text(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    op.create_table(
        "territories",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", postgresql.CITEXT(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
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
        sa.UniqueConstraint("name"),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", postgresql.CITEXT(), nullable=False),
        sa.Column("full_name", sa.Text(), nullable=False),
        sa.Column("password_hash", sa.Text(), nullable=True),
        sa.Column("role", ROLE_ENUM, nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "identity_provider",
            IDENTITY_PROVIDER_ENUM,
            server_default="password",
            nullable=False,
        ),
        sa.Column("external_id", sa.Text(), nullable=True),
        sa.Column("failed_login_attempts", sa.Integer(), server_default="0", nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("email"),
        sa.UniqueConstraint(
            "identity_provider", "external_id", name="uq_users_provider_external_id"
        ),
    )
    op.create_index("ix_users_is_active", "users", ["is_active"], unique=False)
    op.create_index("ix_users_role", "users", ["role"], unique=False)

    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=128), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("replaced_by_id", sa.Uuid(), nullable=True),
        sa.Column("user_agent", sa.Text(), nullable=True),
        sa.Column("ip", postgresql.INET(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["replaced_by_id"], ["refresh_tokens.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("token_hash"),
    )
    op.create_index("ix_refresh_tokens_expires_at", "refresh_tokens", ["expires_at"], unique=False)
    op.create_index("ix_refresh_tokens_user_id", "refresh_tokens", ["user_id"], unique=False)

    op.create_table(
        "territory_provinces",
        sa.Column("territory_id", sa.Uuid(), nullable=False),
        sa.Column("province_code", sa.String(length=2), nullable=False),
        sa.CheckConstraint(
            "province_code ~ '^(0[1-9]|[1-4][0-9]|5[0-2])$'",
            name="ck_territory_provinces_code_format",
        ),
        sa.ForeignKeyConstraint(["territory_id"], ["territories.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("territory_id", "province_code"),
        # One territory per province: the smart default for account assignment relies on it.
        sa.UniqueConstraint("province_code", name="uq_territory_provinces_province_code"),
    )

    op.create_table(
        "user_divisions",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("division_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["division_id"], ["divisions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "division_id"),
    )

    op.create_table(
        "user_territories",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("territory_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["territory_id"], ["territories.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("user_id", "territory_id"),
    )


def downgrade() -> None:
    op.drop_table("user_territories")
    op.drop_table("user_divisions")
    op.drop_table("territory_provinces")
    op.drop_index("ix_refresh_tokens_user_id", table_name="refresh_tokens")
    op.drop_index("ix_refresh_tokens_expires_at", table_name="refresh_tokens")
    op.drop_table("refresh_tokens")
    op.drop_index("ix_users_role", table_name="users")
    op.drop_index("ix_users_is_active", table_name="users")
    op.drop_table("users")
    op.drop_table("territories")
    op.drop_table("divisions")
    op.drop_index("ix_audit_log_occurred_at", table_name="audit_log")
    op.drop_index("ix_audit_log_entity", table_name="audit_log")
    op.drop_index("ix_audit_log_actor", table_name="audit_log")
    op.drop_table("audit_log")
    IDENTITY_PROVIDER_ENUM.drop(op.get_bind(), checkfirst=True)
    ROLE_ENUM.drop(op.get_bind(), checkfirst=True)
    # The citext extension is intentionally left installed (shared, harmless).
