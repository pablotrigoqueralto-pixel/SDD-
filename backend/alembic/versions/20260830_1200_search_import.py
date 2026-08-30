"""search & import: unaccent extension, immutable wrapper and expression indexes

Revision ID: 0008_search_import
Revises: 0007_quotes
Create Date: 2026-08-30 12:00:00+00:00

Reviewed by hand:
- `unaccent` is core contrib like pg_trgm; on managed PostgreSQL it may need a
  one-off superuser CREATE EXTENSION (documented in development_guide.md)
- `f_unaccent` is an IMMUTABLE wrapper (plain unaccent() is only STABLE) so the
  expression GIN trigram indexes below are legal
- downgrade drops the indexes and the function; the extension stays installed,
  consistent with how pg_trgm is handled
"""

from collections.abc import Sequence

from alembic import op

revision: str = "0008_search_import"
down_revision: str | None = "0007_quotes"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

CREATE_FUNCTION = """
CREATE OR REPLACE FUNCTION f_unaccent(text)
RETURNS text
LANGUAGE sql
IMMUTABLE PARALLEL SAFE STRICT
AS $$ SELECT public.unaccent('public.unaccent', $1) $$;
"""

INDEXES = (
    ("ix_accounts_name_unaccent_trgm", "accounts", "f_unaccent(name)"),
    (
        "ix_contacts_full_name_unaccent_trgm",
        "contacts",
        "f_unaccent(first_name || ' ' || last_name)",
    ),
    ("ix_opportunities_name_unaccent_trgm", "opportunities", "f_unaccent(name)"),
)


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")
    op.execute(CREATE_FUNCTION)
    for name, table, expression in INDEXES:
        op.execute(f"CREATE INDEX {name} ON {table} USING gin ({expression} gin_trgm_ops)")


def downgrade() -> None:
    for name, _table, _expression in INDEXES:
        op.execute(f"DROP INDEX IF EXISTS {name}")
    op.execute("DROP FUNCTION IF EXISTS f_unaccent(text)")
