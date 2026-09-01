"""internal attendees on activities and the per-user notification inbox

Revision ID: 0011_attendees_notifications
Revises: 0010_specialties
Create Date: 2026-09-01 12:00:00+00:00

Reviewed by hand:
- `activity_attendees` mirrors `activity_contacts`: composite primary key, cascading from
  the activity (removing an activity removes its guest list) and RESTRICT on the user, so
  a user who attended something cannot be deleted silently
- `notifications` cascades from its recipient (a deleted user's inbox goes with them) and
  keeps `actor_id` on SET NULL: the notice still reads correctly when the person who
  caused it is gone
- the (user_id, read_at, created_at DESC) index is the shape of "my unread, newest first",
  which is the only way this table is ever read
- no backfill: notifications describe events, and no event happened before the table
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_attendees_notifications"
down_revision: str | None = "0010_specialties"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


GRANT_APP_ROLE = """
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'crm_app') THEN
        GRANT SELECT, INSERT, UPDATE, DELETE ON activity_attendees, notifications TO crm_app;
    END IF;
END
$$;
"""


def upgrade() -> None:
    op.create_table(
        "activity_attendees",
        sa.Column("activity_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.ForeignKeyConstraint(["activity_id"], ["activities.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("activity_id", "user_id"),
    )
    op.create_index("ix_activity_attendees_user_id", "activity_attendees", ["user_id"])

    op.create_table(
        "notifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("kind", sa.Text(), nullable=False),
        sa.Column("entity_type", sa.Text(), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("actor_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column(
            "payload", postgresql.JSONB(), nullable=False, server_default=sa.text("'{}'::jsonb")
        ),
        sa.Column("read_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_id"], ["users.id"], ondelete="SET NULL"),
    )
    op.create_index(
        "ix_notifications_inbox",
        "notifications",
        ["user_id", "read_at", sa.text("created_at DESC")],
    )
    op.execute(GRANT_APP_ROLE)


def downgrade() -> None:
    op.drop_index("ix_notifications_inbox", table_name="notifications")
    op.drop_table("notifications")
    op.drop_index("ix_activity_attendees_user_id", table_name="activity_attendees")
    op.drop_table("activity_attendees")
