import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from app.infrastructure.db.seed import APP_ROLE, DIVISIONS, run_seed

pytestmark = pytest.mark.integration


async def test_seed_is_idempotent_and_keeps_division_ids(engine: AsyncEngine) -> None:
    await run_seed(engine)
    async with engine.connect() as connection:
        first = (
            await connection.execute(text("SELECT code, id FROM divisions ORDER BY sort_order"))
        ).all()

    await run_seed(engine)
    async with engine.connect() as connection:
        second = (
            await connection.execute(text("SELECT code, id FROM divisions ORDER BY sort_order"))
        ).all()
        role_exists = (
            await connection.execute(
                text("SELECT 1 FROM pg_roles WHERE rolname = :name"), {"name": APP_ROLE}
            )
        ).scalar()

    assert len(first) == 7
    assert first == second
    assert [row.code for row in first] == [division.code for division in DIVISIONS]
    assert {row.id for row in first} == {division.id for division in DIVISIONS}
    assert role_exists == 1


async def test_app_role_cannot_update_or_delete_audit_log(engine: AsyncEngine) -> None:
    await run_seed(engine)
    async with engine.connect() as connection:
        for statement in ("UPDATE audit_log SET action = 'x'", "DELETE FROM audit_log"):
            # SET ROLE is transactional: re-issue it after every rollback.
            await connection.execute(text(f"SET ROLE {APP_ROLE}"))
            with pytest.raises(Exception, match="permission denied"):
                await connection.execute(text(statement))
            await connection.rollback()
