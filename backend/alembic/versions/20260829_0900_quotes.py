"""quotes: quotes, lines, counters, pdfs, mail outbox and app settings

Revision ID: 0007_quotes
Revises: 0006_opportunities
Create Date: 2026-08-29 09:00:00+00:00

Reviewed by hand after autogenerate:
- both enums dropped on downgrade
- checks: status/timestamp consistency, vat whitelist, discount range, number/version > 0
- partial indexes: current versions per opportunity, expiring sent quotes
- app_settings seeded with quote condition defaults and the email template
- crm_app grants on the new tables (guarded: only when the role exists)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import JSONB

revision: str = "0007_quotes"
down_revision: str | None = "0006_opportunities"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


GRANT_APP_ROLE = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE
        ON quotes, quote_lines, quote_counters, quote_pdfs, mail_outbox, app_settings TO crm_app;
    END IF;
END
$$;
"""

SEED_SETTINGS = """
INSERT INTO app_settings (key, value) VALUES
    (
        'quote_conditions_defaults',
        '{"validez_dias": 30, "plazo_entrega": "4-6 semanas", '
        '"forma_pago": "Transferencia a 30 días", "garantia": "2 años"}'
    ),
    (
        'quote_email_template',
        '{"subject": "Presupuesto {numero} - Quermed", '
        '"body": "Estimado cliente:\\n\\nAdjuntamos el presupuesto {numero} para {centro}.\\n\\n'
        'Quedamos a su disposición para cualquier consulta.\\n\\nUn saludo,\\n{comercial}\\nQuermed S.L."}'
    )
ON CONFLICT (key) DO NOTHING;
"""


def upgrade() -> None:
    op.create_table(
        "quote_counters",
        sa.Column("year", sa.SmallInteger(), autoincrement=False, nullable=False),
        sa.Column("last_number", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("year"),
    )
    op.create_table(
        "app_settings",
        sa.Column("key", sa.Text(), nullable=False),
        sa.Column("value", JSONB(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("key"),
    )
    op.create_table(
        "quotes",
        sa.Column("opportunity_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=True),
        sa.Column("year", sa.SmallInteger(), nullable=False),
        sa.Column("number", sa.Integer(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("draft", "sent", "accepted", "rejected", name="quotes_status_enum"),
            nullable=False,
        ),
        sa.Column("conditions", JSONB(), nullable=False),
        sa.Column("total_base", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total_vat", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("total", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("valid_until", sa.Date(), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("rejection_note", sa.Text(), nullable=True),
        sa.Column("superseded_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("version_lock", sa.Integer(), server_default="1", nullable=False),
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
        sa.CheckConstraint("number > 0", name="ck_quotes_number_positive"),
        sa.CheckConstraint("version > 0", name="ck_quotes_version_positive"),
        sa.CheckConstraint("total_base >= 0", name="ck_quotes_total_base"),
        sa.CheckConstraint(
            "status <> 'sent' OR (sent_at IS NOT NULL AND valid_until IS NOT NULL)",
            name="ck_quotes_sent_requires_stamps",
        ),
        sa.CheckConstraint(
            "status <> 'accepted' OR accepted_at IS NOT NULL",
            name="ck_quotes_accepted_requires_stamp",
        ),
        sa.CheckConstraint(
            "status <> 'rejected' OR rejected_at IS NOT NULL",
            name="ck_quotes_rejected_requires_stamp",
        ),
        sa.CheckConstraint("status <> 'draft' OR sent_at IS NULL", name="ck_quotes_draft_not_sent"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["opportunity_id"], ["opportunities.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("year", "number", "version", name="uq_quotes_number_version"),
    )
    op.create_index(
        "ix_quotes_current_opportunity",
        "quotes",
        ["opportunity_id"],
        unique=False,
        postgresql_where="superseded_at IS NULL",
    )
    op.create_index(
        "ix_quotes_expiring",
        "quotes",
        ["valid_until"],
        unique=False,
        postgresql_where="status = 'sent' AND superseded_at IS NULL",
    )
    op.create_index("ix_quotes_owner_status", "quotes", ["owner_id", "status"], unique=False)
    op.create_table(
        "quote_lines",
        sa.Column("quote_id", sa.Uuid(), nullable=False),
        sa.Column("product_id", sa.Uuid(), nullable=True),
        sa.Column("description", sa.Text(), nullable=False),
        sa.Column("product_code", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("unit_price", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("discount_percent", sa.Numeric(precision=5, scale=2), nullable=False),
        sa.Column("vat_rate", sa.Numeric(precision=4, scale=2), nullable=False),
        sa.Column("unit_cost", sa.Numeric(precision=12, scale=2), nullable=True),
        sa.Column("position", sa.Integer(), nullable=False),
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
        sa.CheckConstraint("quantity > 0", name="ck_quote_lines_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_quote_lines_unit_price"),
        sa.CheckConstraint(
            "discount_percent >= 0 AND discount_percent <= 100", name="ck_quote_lines_discount"
        ),
        sa.CheckConstraint(
            "vat_rate IN (21.00, 10.00, 4.00, 0.00)", name="ck_quote_lines_vat_rate"
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_quote_lines_quote_id", "quote_lines", ["quote_id"], unique=False)
    op.create_index("ix_quote_lines_product_id", "quote_lines", ["product_id"], unique=False)
    op.create_table(
        "quote_pdfs",
        sa.Column("quote_id", sa.Uuid(), nullable=False),
        sa.Column("content", sa.LargeBinary(), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("quote_id"),
    )
    op.create_table(
        "mail_outbox",
        sa.Column("quote_id", sa.Uuid(), nullable=False),
        sa.Column("recipients", JSONB(), nullable=False),
        sa.Column("subject", sa.Text(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("sent", "failed", "skipped", name="mail_outbox_status_enum"),
            nullable=False,
        ),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["quote_id"], ["quotes.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_mail_outbox_quote_id", "mail_outbox", ["quote_id", "created_at"], unique=False
    )
    op.execute(SEED_SETTINGS)
    op.execute(GRANT_APP_ROLE)


def downgrade() -> None:
    op.drop_index("ix_mail_outbox_quote_id", table_name="mail_outbox")
    op.drop_table("mail_outbox")
    op.drop_table("quote_pdfs")
    op.drop_index("ix_quote_lines_product_id", table_name="quote_lines")
    op.drop_index("ix_quote_lines_quote_id", table_name="quote_lines")
    op.drop_table("quote_lines")
    op.drop_index("ix_quotes_owner_status", table_name="quotes")
    op.drop_index(
        "ix_quotes_expiring",
        table_name="quotes",
        postgresql_where="status = 'sent' AND superseded_at IS NULL",
    )
    op.drop_index(
        "ix_quotes_current_opportunity",
        table_name="quotes",
        postgresql_where="superseded_at IS NULL",
    )
    op.drop_table("quotes")
    op.drop_table("app_settings")
    op.drop_table("quote_counters")
    for enum_name in ("quotes_status_enum", "mail_outbox_status_enum"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
