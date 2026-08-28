"""accounts and contacts: accounts, addresses, links, job titles, contacts, access log

Revision ID: 0003_accounts_contacts
Revises: 0002_reference_data
Create Date: 2026-08-28 08:16:38+00:00

Reviewed by hand after autogenerate:
- pg_trgm extension for the name/city/contact-name trigram indexes (list search < 500 ms)
- partial unique indexes (tax_id when present, one primary contact per account)
- enums dropped on downgrade
- personal_data_access_log is append-only for crm_app (INSERT/SELECT only)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0003_accounts_contacts"
down_revision: str | None = "0002_reference_data"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


GRANT_ACCESS_LOG_APPEND_ONLY = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON accounts, account_addresses, account_divisions,
            account_brands, job_titles, contacts TO crm_app;
        GRANT SELECT, INSERT ON personal_data_access_log TO crm_app;
    END IF;
END
$$;
"""


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_table(
        "job_titles",
        sa.Column("code", sa.Text(), nullable=False),
        sa.Column("name_es", postgresql.CITEXT(), nullable=False),
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
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
        sa.UniqueConstraint("name_es"),
    )
    op.create_table(
        "accounts",
        sa.Column("name", sa.Text(), nullable=False),
        sa.Column("account_type_id", sa.Uuid(), nullable=False),
        sa.Column("tax_id", sa.Text(), nullable=True),
        sa.Column("street", sa.Text(), nullable=True),
        sa.Column("postal_code", sa.String(length=5), nullable=True),
        sa.Column("city", sa.Text(), nullable=True),
        sa.Column("province_code", sa.String(length=2), nullable=False),
        sa.Column("territory_id", sa.Uuid(), nullable=True),
        sa.Column("owner_id", sa.Uuid(), nullable=True),
        sa.Column("customer_code", sa.Text(), nullable=True),
        sa.Column("phone", sa.Text(), nullable=True),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("website", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "postal_code IS NULL OR postal_code ~ '^[0-9]{5}$'",
            name="ck_accounts_postal_code_format",
        ),
        sa.CheckConstraint(
            "province_code ~ '^(0[1-9]|[1-4][0-9]|5[0-2])$'",
            name="ck_accounts_province_code_format",
        ),
        sa.ForeignKeyConstraint(["account_type_id"], ["account_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["territory_id"], ["territories.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_accounts_account_type_id", "accounts", ["account_type_id"], unique=False)
    op.create_index(
        "ix_accounts_city_trgm",
        "accounts",
        ["city"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"city": "gin_trgm_ops"},
    )
    op.create_index("ix_accounts_customer_code", "accounts", ["customer_code"], unique=False)
    op.create_index("ix_accounts_is_active", "accounts", ["is_active"], unique=False)
    op.create_index(
        "ix_accounts_name_trgm",
        "accounts",
        ["name"],
        unique=False,
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.create_index("ix_accounts_owner_id", "accounts", ["owner_id"], unique=False)
    op.create_index("ix_accounts_province_code", "accounts", ["province_code"], unique=False)
    op.create_index("ix_accounts_territory_id", "accounts", ["territory_id"], unique=False)
    op.create_index(
        "ux_accounts_tax_id",
        "accounts",
        ["tax_id"],
        unique=True,
        postgresql_where=sa.text("tax_id IS NOT NULL"),
    )
    op.create_table(
        "account_addresses",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("label", postgresql.CITEXT(), nullable=False),
        sa.Column("street", sa.Text(), nullable=False),
        sa.Column("postal_code", sa.String(length=5), nullable=False),
        sa.Column("city", sa.Text(), nullable=False),
        sa.Column("province_code", sa.String(length=2), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.CheckConstraint(
            "postal_code ~ '^[0-9]{5}$'", name="ck_account_addresses_postal_code_format"
        ),
        sa.CheckConstraint(
            "province_code ~ '^(0[1-9]|[1-4][0-9]|5[0-2])$'",
            name="ck_account_addresses_province_code_format",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("account_id", "label", name="uq_account_addresses_label"),
    )
    op.create_index(
        "ix_account_addresses_account_id", "account_addresses", ["account_id"], unique=False
    )
    op.create_table(
        "account_brands",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("brand_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("account_id", "brand_id"),
    )
    op.create_table(
        "account_divisions",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("division_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["division_id"], ["divisions.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("account_id", "division_id"),
    )
    op.create_index(
        "ix_account_divisions_division_id", "account_divisions", ["division_id"], unique=False
    )
    op.create_table(
        "contacts",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("first_name", sa.Text(), nullable=False),
        sa.Column("last_name", sa.Text(), nullable=False),
        sa.Column("job_title_id", sa.Uuid(), nullable=True),
        sa.Column("division_id", sa.Uuid(), nullable=True),
        sa.Column("email", postgresql.CITEXT(), nullable=True),
        sa.Column("mobile", sa.Text(), nullable=True),
        sa.Column("landline", sa.Text(), nullable=True),
        sa.Column(
            "preferred_channel",
            sa.Enum("email", "mobile", "landline", name="contacts_preferred_channel_enum"),
            nullable=True,
        ),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default="false", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="true", nullable=False),
        sa.Column(
            "consent_status",
            sa.Enum("unknown", "granted", "denied", name="contacts_consent_status_enum"),
            server_default="unknown",
            nullable=False,
        ),
        sa.Column("consent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "consent_source",
            sa.Enum("verbal", "email", "form", "imported", name="contacts_consent_source_enum"),
            nullable=True,
        ),
        sa.Column("consent_recorded_by", sa.Uuid(), nullable=True),
        sa.Column("anonymised_at", sa.DateTime(timezone=True), nullable=True),
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
            "consent_status = 'unknown' OR (consent_at IS NOT NULL AND consent_source IS NOT NULL)",
            name="ck_contacts_consent_complete",
        ),
        sa.CheckConstraint(
            "preferred_channel IS NULL OR (preferred_channel = 'email' AND email IS NOT NULL) OR (preferred_channel = 'mobile' AND mobile IS NOT NULL) OR (preferred_channel = 'landline' AND landline IS NOT NULL)",
            name="ck_contacts_preferred_channel_value",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["consent_recorded_by"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["division_id"], ["divisions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["job_title_id"], ["job_titles.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_contacts_account_id", "contacts", ["account_id"], unique=False)
    op.create_index("ix_contacts_email", "contacts", ["email"], unique=False)
    op.create_index(
        "ux_contacts_primary_per_account",
        "contacts",
        ["account_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
    )
    op.create_table(
        "personal_data_access_log",
        sa.Column(
            "occurred_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.Column("trace_id", sa.Text(), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_personal_data_access_contact",
        "personal_data_access_log",
        ["contact_id", sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_personal_data_access_user",
        "personal_data_access_log",
        ["user_id", sa.literal_column("occurred_at DESC")],
        unique=False,
    )
    op.execute(GRANT_ACCESS_LOG_APPEND_ONLY)


def downgrade() -> None:
    op.drop_index("ix_personal_data_access_user", table_name="personal_data_access_log")
    op.drop_index("ix_personal_data_access_contact", table_name="personal_data_access_log")
    op.drop_table("personal_data_access_log")
    op.drop_index(
        "ux_contacts_primary_per_account",
        table_name="contacts",
        postgresql_where=sa.text("is_primary"),
    )
    op.drop_index("ix_contacts_email", table_name="contacts")
    op.drop_index("ix_contacts_account_id", table_name="contacts")
    op.drop_table("contacts")
    op.drop_index("ix_account_divisions_division_id", table_name="account_divisions")
    op.drop_table("account_divisions")
    op.drop_table("account_brands")
    op.drop_index("ix_account_addresses_account_id", table_name="account_addresses")
    op.drop_table("account_addresses")
    op.drop_index(
        "ux_accounts_tax_id", table_name="accounts", postgresql_where=sa.text("tax_id IS NOT NULL")
    )
    op.drop_index("ix_accounts_territory_id", table_name="accounts")
    op.drop_index("ix_accounts_province_code", table_name="accounts")
    op.drop_index("ix_accounts_owner_id", table_name="accounts")
    op.drop_index(
        "ix_accounts_name_trgm",
        table_name="accounts",
        postgresql_using="gin",
        postgresql_ops={"name": "gin_trgm_ops"},
    )
    op.drop_index("ix_accounts_is_active", table_name="accounts")
    op.drop_index("ix_accounts_customer_code", table_name="accounts")
    op.drop_index(
        "ix_accounts_city_trgm",
        table_name="accounts",
        postgresql_using="gin",
        postgresql_ops={"city": "gin_trgm_ops"},
    )
    op.drop_index("ix_accounts_account_type_id", table_name="accounts")
    op.drop_table("accounts")
    op.drop_table("job_titles")
    for enum_name in (
        "contacts_preferred_channel_enum",
        "contacts_consent_status_enum",
        "contacts_consent_source_enum",
    ):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
    # pg_trgm is intentionally left installed (shared, harmless).
