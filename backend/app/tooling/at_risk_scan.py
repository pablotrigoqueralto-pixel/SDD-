"""Run the "En riesgo" scan once and print how many opportunities were flagged.

Usage: python -m app.tooling.at_risk_scan
Env:   AT_RISK_AFTER_DAYS (default 60)
"""

import asyncio
import sys

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.application.opportunities.at_risk import scan_at_risk
from app.infrastructure.db.unit_of_work import SqlAlchemyUnitOfWork
from app.infrastructure.settings import get_settings


async def run_once() -> int:
    settings = get_settings()
    engine = create_async_engine(settings.database_url)
    try:
        async with async_sessionmaker(engine, expire_on_commit=False)() as session:
            return await scan_at_risk(
                SqlAlchemyUnitOfWork(session), after_days=settings.at_risk_after_days
            )
    finally:
        await engine.dispose()


def main() -> int:
    flagged = asyncio.run(run_once())
    sys.stdout.write(f"{flagged}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
