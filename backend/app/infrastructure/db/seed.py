"""Idempotent reference data seed.

Seeds the seven product divisions with stable ids and prepares the least-privilege
application role `crm_app` (append-only on audit_log). Safe to run repeatedly.

Usage: `make seed` or `python -m app.infrastructure.db.seed`.
"""

import asyncio
from dataclasses import dataclass
from uuid import UUID, uuid5

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.infrastructure.db.models import DivisionModel
from app.infrastructure.logging import get_logger
from app.infrastructure.settings import get_settings

DIVISION_NAMESPACE = UUID("6f1c2d3e-4a5b-4c6d-8e7f-90a1b2c3d4e5")
APP_ROLE = "crm_app"

logger = get_logger("seed")


@dataclass(frozen=True)
class DivisionSeed:
    code: str
    name_es: str
    sort_order: int

    @property
    def id(self) -> UUID:
        # Deterministic id so re-running the seed (or seeding another environment) never drifts.
        return uuid5(DIVISION_NAMESPACE, f"division:{self.code}")


DIVISIONS: tuple[DivisionSeed, ...] = (
    DivisionSeed("assisted_reproduction", "Reproducción asistida", 10),
    DivisionSeed("consumables", "Fungibles", 20),
    DivisionSeed("gynaecology", "Ginecología", 30),
    DivisionSeed("vascular", "Vascular", 40),
    DivisionSeed("neurology", "Neurología", 50),
    DivisionSeed("equipment", "Equipos", 60),
    DivisionSeed("carts_and_arms", "Carros y brazos soporte", 70),
)

# APP_ROLE is a constant identifier, never user input.
CREATE_APP_ROLE = f"""
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = '{APP_ROLE}') THEN
        CREATE ROLE {APP_ROLE} NOLOGIN;
    END IF;
END
$$;
"""  # noqa: S608

APP_ROLE_GRANTS: tuple[str, ...] = (
    f"GRANT USAGE ON SCHEMA public TO {APP_ROLE}",
    f"GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA public TO {APP_ROLE}",
    # audit_log is append-only for the application.
    f"REVOKE UPDATE, DELETE, TRUNCATE ON audit_log FROM {APP_ROLE}",
    f"GRANT SELECT, INSERT ON audit_log TO {APP_ROLE}",
)


async def seed_divisions(engine: AsyncEngine) -> int:
    statement = insert(DivisionModel).values(
        [
            {
                "id": division.id,
                "code": division.code,
                "name_es": division.name_es,
                "sort_order": division.sort_order,
            }
            for division in DIVISIONS
        ]
    )
    upsert = statement.on_conflict_do_update(
        index_elements=[DivisionModel.code],
        set_={"name_es": statement.excluded.name_es, "sort_order": statement.excluded.sort_order},
    )
    async with engine.begin() as connection:
        await connection.execute(upsert)
    return len(DIVISIONS)


async def prepare_app_role(engine: AsyncEngine) -> None:
    async with engine.begin() as connection:
        await connection.execute(text(CREATE_APP_ROLE))
        for grant in APP_ROLE_GRANTS:
            await connection.execute(text(grant))


async def run_seed(engine: AsyncEngine) -> None:
    count = await seed_divisions(engine)
    await prepare_app_role(engine)
    logger.info("seed_completed", divisions=count, app_role=APP_ROLE)


async def main() -> None:
    engine = create_async_engine(get_settings().database_url)
    try:
        await run_seed(engine)
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
