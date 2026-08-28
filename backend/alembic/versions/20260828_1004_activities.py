"""activities: activities, activity_contacts and the account activity summary columns

Revision ID: 0004_activities
Revises: 0003_accounts_contacts
Create Date: 2026-08-28 10:04:17+00:00

Reviewed by hand after autogenerate:
- status/outcome enums dropped on downgrade
- checks: done requires done_at, cancelled requires a reason, outcome only when done
- indexes for the account timeline and the owner agenda ("Hoy")
- crm_app grants on the new tables (guarded: only when the role exists)
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0004_activities"
down_revision: str | None = "0003_accounts_contacts"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


GRANT_APP_ROLE = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON activities, activity_contacts TO crm_app;
    END IF;
END
$$;
"""


def upgrade() -> None:
    op.create_table(
        "activities",
        sa.Column("account_id", sa.Uuid(), nullable=False),
        sa.Column("activity_type_id", sa.Uuid(), nullable=False),
        sa.Column("owner_id", sa.Uuid(), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("planned", "done", "cancelled", name="activities_status_enum"),
            nullable=False,
        ),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("done_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_minutes", sa.SmallInteger(), nullable=True),
        sa.Column(
            "outcome",
            sa.Enum(
                "positive", "neutral", "negative", "no_contact", name="activities_outcome_enum"
            ),
            nullable=True,
        ),
        sa.Column("subject", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("cancel_reason", sa.Text(), nullable=True),
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
        sa.CheckConstraint("outcome IS NULL OR status = 'done'", name="ck_activities_outcome_done"),
        sa.CheckConstraint(
            "status <> 'cancelled' OR cancel_reason IS NOT NULL",
            name="ck_activities_cancelled_requires_reason",
        ),
        sa.CheckConstraint(
            "status <> 'done' OR done_at IS NOT NULL", name="ck_activities_done_requires_done_at"
        ),
        sa.CheckConstraint(
            "duration_minutes IS NULL OR (duration_minutes BETWEEN 1 AND 1440)",
            name="ck_activities_duration_range",
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["activity_type_id"], ["activity_types.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["owner_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_activities_account_timeline",
        "activities",
        ["account_id", sa.literal_column("scheduled_at DESC")],
        unique=False,
    )
    op.create_index(
        "ix_activities_activity_type_id", "activities", ["activity_type_id"], unique=False
    )
    op.create_index(
        "ix_activities_owner_agenda",
        "activities",
        ["owner_id", "status", "scheduled_at"],
        unique=False,
    )
    op.create_index("ix_activities_status", "activities", ["status"], unique=False)
    op.create_table(
        "activity_contacts",
        sa.Column("activity_id", sa.Uuid(), nullable=False),
        sa.Column("contact_id", sa.Uuid(), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["contact_id"], ["contacts.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("activity_id", "contact_id"),
    )
    op.add_column(
        "accounts", sa.Column("last_contact_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.add_column(
        "accounts", sa.Column("next_activity_at", sa.DateTime(timezone=True), nullable=True)
    )
    op.create_index(
        "ix_accounts_territory_last_contact",
        "accounts",
        ["territory_id", "last_contact_at"],
        unique=False,
    )
    op.execute(GRANT_APP_ROLE)


def downgrade() -> None:
    op.drop_index("ix_accounts_territory_last_contact", table_name="accounts")
    op.drop_column("accounts", "next_activity_at")
    op.drop_column("accounts", "last_contact_at")
    op.drop_table("activity_contacts")
    op.drop_index("ix_activities_status", table_name="activities")
    op.drop_index("ix_activities_owner_agenda", table_name="activities")
    op.drop_index("ix_activities_activity_type_id", table_name="activities")
    op.drop_index("ix_activities_account_timeline", table_name="activities")
    op.drop_table("activities")
    for enum_name in ("activities_status_enum", "activities_outcome_enum"):
        op.execute(f"DROP TYPE IF EXISTS {enum_name}")
