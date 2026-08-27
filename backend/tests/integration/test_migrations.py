"""Migration round-trip: upgrade → downgrade → upgrade, then models and migrations agree."""

import pytest

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
