"""labelled phone lists, billing notes and the head-of-department flag

Revision ID: 0009_phone_lists
Revises: 0008_search_import
Create Date: 2026-08-31 18:00:00+00:00

Reviewed by hand:
- every existing value is copied before the old columns are dropped:
  accounts.phone -> "Principal", contacts.mobile -> "Móvil",
  contacts.landline -> "Fijo"; blanks and nulls produce no row, so contacts
  anonymised before this migration simply get no phones
- preferred_channel loses `mobile`/`landline` (they named the dropped columns)
  and both map to the new `phone` value; the enum type is rebuilt because
  PostgreSQL cannot remove values from an existing enum
- "Jefe de servicio" stops being a job title: the contacts holding it get
  is_head_of_department = true with their job_title_id cleared, and the
  catalogue row is DEACTIVATED, never deleted — audit rows reference it by id
- DOWNGRADE IS LOSSY: it restores the old columns from each owner's FIRST
  phone only; any second, third... phone is discarded. The nightly dump
  (deploy/backup.sh) is the real recovery path.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0009_phone_lists"
down_revision: str | None = "0008_search_import"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

HEAD_OF_DEPARTMENT_CODE = "head_of_department"

SET_HEAD_OF_DEPARTMENT = """
UPDATE contacts SET is_head_of_department = true, job_title_id = NULL
WHERE job_title_id IN (SELECT id FROM job_titles WHERE code = 'head_of_department')
"""

DEACTIVATE_JOB_TITLE = "UPDATE job_titles SET is_active = false WHERE code = 'head_of_department'"

REACTIVATE_JOB_TITLE = "UPDATE job_titles SET is_active = true WHERE code = 'head_of_department'"

COPY_ACCOUNT_PHONES = """
INSERT INTO account_phones (id, account_id, label, number, sort_order)
SELECT gen_random_uuid(), id, 'Principal', btrim(phone), 0
FROM accounts
WHERE phone IS NOT NULL AND btrim(phone) <> ''
"""

COPY_CONTACT_PHONES = """
INSERT INTO contact_phones (id, contact_id, label, number, sort_order)
SELECT gen_random_uuid(), id, %(label)s, btrim(%(column)s), %(order)s
FROM contacts
WHERE %(column)s IS NOT NULL AND btrim(%(column)s) <> ''
"""

RESTORE_ACCOUNT_PHONE = """
UPDATE accounts a
SET phone = p.number
FROM account_phones p
WHERE p.account_id = a.id AND p.sort_order = 0
"""

RESTORE_CONTACT_PHONE = """
UPDATE contacts c
SET %(column)s = p.number
FROM contact_phones p
WHERE p.contact_id = c.id AND lower(p.label) = %(label)s
"""


def _phone_table(name: str, owner: str) -> None:
    op.create_table(
        name,
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            owner,
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey(f"{owner[:-3]}s.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("label", postgresql.CITEXT(), nullable=False),
        sa.Column("number", sa.Text(), nullable=False),
        sa.Column("extension", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.UniqueConstraint(owner, "sort_order", name=f"uq_{name}_sort_order"),
        sa.UniqueConstraint(owner, "label", "number", name=f"uq_{name}_label_number"),
    )
    op.create_index(f"ix_{name}_{owner}", name, [owner])


def upgrade() -> None:
    _phone_table("account_phones", "account_id")
    _phone_table("contact_phones", "contact_id")

    op.add_column("accounts", sa.Column("billing_notes", sa.Text(), nullable=True))
    op.add_column(
        "contacts",
        sa.Column(
            "is_head_of_department",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )

    # --- copy existing values -------------------------------------------------
    op.execute(COPY_ACCOUNT_PHONES)
    op.execute(COPY_CONTACT_PHONES % {"label": "'Móvil'", "column": "mobile", "order": 0})
    op.execute(
        COPY_CONTACT_PHONES
        % {
            "label": "'Fijo'",
            "column": "landline",
            # a contact with both keeps the mobile first
            "order": "CASE WHEN mobile IS NULL OR btrim(mobile) = '' THEN 0 ELSE 1 END",
        }
    )

    # --- preferred_channel: mobile/landline collapse into phone ---------------
    # The old CHECK names the phone columns; it must go before they do.
    op.drop_constraint("ck_contacts_preferred_channel_value", "contacts", type_="check")
    op.execute(
        "ALTER TABLE contacts ALTER COLUMN preferred_channel TYPE text "
        "USING preferred_channel::text"
    )
    op.execute(
        "UPDATE contacts SET preferred_channel = 'phone' "
        "WHERE preferred_channel IN ('mobile', 'landline')"
    )
    op.execute("DROP TYPE contacts_preferred_channel_enum")
    op.execute("CREATE TYPE contacts_preferred_channel_enum AS ENUM ('email', 'phone')")
    op.execute(
        "ALTER TABLE contacts ALTER COLUMN preferred_channel "
        "TYPE contacts_preferred_channel_enum USING preferred_channel::contacts_preferred_channel_enum"
    )

    op.create_check_constraint(
        "ck_contacts_preferred_channel_value",
        "contacts",
        "preferred_channel IS NULL"
        " OR preferred_channel = 'phone'"
        " OR (preferred_channel = 'email' AND email IS NOT NULL)",
    )

    # --- head of department: flag set, job title cleared and deactivated ------
    op.execute(SET_HEAD_OF_DEPARTMENT)
    op.execute(DEACTIVATE_JOB_TITLE)

    op.drop_column("accounts", "phone")
    op.drop_column("contacts", "mobile")
    op.drop_column("contacts", "landline")


def downgrade() -> None:
    """Lossy: only the first phone of each account/contact survives."""
    op.add_column("accounts", sa.Column("phone", sa.Text(), nullable=True))
    op.add_column("contacts", sa.Column("mobile", sa.Text(), nullable=True))
    op.add_column("contacts", sa.Column("landline", sa.Text(), nullable=True))

    op.execute(RESTORE_ACCOUNT_PHONE)
    op.execute(RESTORE_CONTACT_PHONE % {"column": "mobile", "label": "'móvil'"})
    op.execute(RESTORE_CONTACT_PHONE % {"column": "landline", "label": "'fijo'"})

    op.drop_constraint("ck_contacts_preferred_channel_value", "contacts", type_="check")
    op.execute(
        "ALTER TABLE contacts ALTER COLUMN preferred_channel TYPE text "
        "USING preferred_channel::text"
    )
    op.execute("UPDATE contacts SET preferred_channel = 'mobile' WHERE preferred_channel = 'phone'")
    op.execute("DROP TYPE contacts_preferred_channel_enum")
    op.execute(
        "CREATE TYPE contacts_preferred_channel_enum AS ENUM ('email', 'mobile', 'landline')"
    )
    op.execute(
        "ALTER TABLE contacts ALTER COLUMN preferred_channel "
        "TYPE contacts_preferred_channel_enum USING preferred_channel::contacts_preferred_channel_enum"
    )

    op.create_check_constraint(
        "ck_contacts_preferred_channel_value",
        "contacts",
        "preferred_channel IS NULL"
        " OR (preferred_channel = 'email' AND email IS NOT NULL)"
        " OR (preferred_channel = 'mobile' AND mobile IS NOT NULL)"
        " OR (preferred_channel = 'landline' AND landline IS NOT NULL)",
    )

    op.execute(REACTIVATE_JOB_TITLE)

    op.drop_column("contacts", "is_head_of_department")
    op.drop_column("accounts", "billing_notes")
    op.drop_index("ix_contact_phones_contact_id", table_name="contact_phones")
    op.drop_table("contact_phones")
    op.drop_index("ix_account_phones_account_id", table_name="account_phones")
    op.drop_table("account_phones")
