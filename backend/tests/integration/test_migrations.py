"""Migration round-trip: upgrade → downgrade → upgrade, then models and migrations agree."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.infrastructure.db.seed import DIVISIONS
from tests.integration.conftest import alembic

pytestmark = pytest.mark.integration


def test_migrations_round_trip_and_match_models(database_url: str) -> None:
    upgrade = alembic("upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr

    downgrade = alembic("downgrade", "base")
    assert downgrade.returncode == 0, downgrade.stderr

    upgrade_again = alembic("upgrade", "head")
    assert upgrade_again.returncode == 0, upgrade_again.stderr

    check = alembic("check")
    assert check.returncode == 0, f"models and migrations drifted:\n{check.stdout}\n{check.stderr}"
    assert "No new upgrade operations detected" in check.stdout


async def test_0010_maps_medical_divisions_and_leaves_the_rest_alone(database_url: str) -> None:
    """The four unambiguous divisions become specialties; the commercial ones do not.

    The catalogue is normally written by the application seed, which runs AFTER alembic on
    a deploy — the migration must therefore stand on its own, which is what this exercise
    over a database that has never been seeded verifies.
    """
    assert alembic("downgrade", "0009_phone_lists").returncode == 0
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            # The round trip leaves an unseeded database: create the few rows we need.
            account_type_id = (
                await connection.execute(
                    text(
                        "INSERT INTO account_types (id, code, name_es, sort_order)"
                        " VALUES (gen_random_uuid(), 'migration_0010', 'Migración 0010', 999)"
                        " RETURNING id"
                    )
                )
            ).scalar_one()
            # Seeded ids, never fresh ones: a division with a different id would break
            # the seed's pipeline links for every later test.
            divisions = {}
            for code in ("vascular", "consumables"):
                seeded = next(d for d in DIVISIONS if d.code == code)
                await connection.execute(
                    text(
                        "INSERT INTO divisions (id, code, name_es, sort_order)"
                        " VALUES (:id, :code, :name, :sort_order)"
                        " ON CONFLICT (code) DO NOTHING"
                    ),
                    {
                        "id": seeded.id,
                        "code": code,
                        "name": seeded.name_es,
                        "sort_order": seeded.sort_order,
                    },
                )
                divisions[code] = (
                    await connection.execute(
                        text("SELECT id FROM divisions WHERE code = :code"), {"code": code}
                    )
                ).scalar_one()
            account_id = (
                await connection.execute(
                    text(
                        "INSERT INTO accounts (id, name, account_type_id, province_code)"
                        " VALUES (gen_random_uuid(), 'Centro Migración 0010', :type_id, '28')"
                        " RETURNING id"
                    ),
                    {"type_id": account_type_id},
                )
            ).scalar_one()
            for last_name, code in (("Vascular", "vascular"), ("Consumibles", "consumables")):
                await connection.execute(
                    text(
                        "INSERT INTO contacts (id, account_id, first_name, last_name, division_id)"
                        " VALUES (gen_random_uuid(), :account_id, 'Test', :last_name, :division_id)"
                    ),
                    {
                        "account_id": account_id,
                        "last_name": last_name,
                        "division_id": divisions[code],
                    },
                )
    finally:
        await engine.dispose()  # the migration takes ACCESS EXCLUSIVE locks on contacts

    upgrade = alembic("upgrade", "head")
    assert upgrade.returncode == 0, upgrade.stderr
    assert "0010_specialties: 1 contacts mapped" in upgrade.stdout + upgrade.stderr

    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            rows = (
                await connection.execute(
                    text(
                        "SELECT c.last_name, s.code FROM contacts c"
                        " LEFT JOIN specialties s ON s.id = c.specialty_id"
                        " WHERE c.account_id = :account_id ORDER BY c.last_name"
                    ),
                    {"account_id": account_id},
                )
            ).all()
            assert [tuple(row) for row in rows] == [
                ("Consumibles", None),
                ("Vascular", "vascular_surgery"),
            ]
            await connection.execute(
                text("DELETE FROM contacts WHERE account_id = :id"), {"id": account_id}
            )
            await connection.execute(
                text("DELETE FROM accounts WHERE id = :id"), {"id": account_id}
            )
            await connection.execute(
                text("DELETE FROM account_types WHERE code = 'migration_0010'")
            )
    finally:
        await engine.dispose()


async def test_0011_creates_both_tables_with_their_cascades(database_url: str) -> None:
    """The guest list goes with its activity; a user's inbox goes with the user."""
    engine = create_async_engine(database_url)
    try:
        async with engine.begin() as connection:
            rules: dict[str, str] = dict(
                (  # type: ignore[arg-type]
                    await connection.execute(
                        text(
                            "SELECT tc.table_name || '.' || kcu.column_name, rc.delete_rule"
                            " FROM information_schema.table_constraints tc"
                            " JOIN information_schema.key_column_usage kcu"
                            "   ON kcu.constraint_name = tc.constraint_name"
                            " JOIN information_schema.referential_constraints rc"
                            "   ON rc.constraint_name = tc.constraint_name"
                            " WHERE tc.constraint_type = 'FOREIGN KEY'"
                            "   AND tc.table_name IN ('activity_attendees', 'notifications')"
                        )
                    )
                ).all()
            )
            assert rules["activity_attendees.activity_id"] == "CASCADE"
            assert rules["activity_attendees.user_id"] == "RESTRICT"
            assert rules["notifications.user_id"] == "CASCADE"
            assert rules["notifications.actor_id"] == "SET NULL"

            indexes = (
                (
                    await connection.execute(
                        text(
                            "SELECT indexname FROM pg_indexes"
                            " WHERE tablename IN ('activity_attendees', 'notifications')"
                        )
                    )
                )
                .scalars()
                .all()
            )
            assert "ix_notifications_inbox" in indexes
            assert "ix_activity_attendees_user_id" in indexes
    finally:
        await engine.dispose()
