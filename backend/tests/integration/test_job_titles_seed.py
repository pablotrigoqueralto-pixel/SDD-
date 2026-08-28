import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.infrastructure.db.models import JobTitleModel
from app.infrastructure.db.seed import JOB_TITLES, reference_id, run_seed

pytestmark = pytest.mark.integration


async def _titles(engine: AsyncEngine) -> list[JobTitleModel]:
    async with async_sessionmaker(engine)() as session:
        statement = select(JobTitleModel).order_by(JobTitleModel.sort_order)
        return list((await session.execute(statement)).scalars().all())


async def test_seed_creates_eleven_job_titles_with_stable_ids(engine: AsyncEngine) -> None:
    await run_seed(engine)

    titles = await _titles(engine)

    assert [t.code for t in titles] == [code for code, _ in JOB_TITLES]
    assert titles[0].name_es == "Ginecólogo/a"
    assert titles[-1].code == "other"
    assert titles[0].id == reference_id("job_titles", "gynaecologist")
    assert all(t.is_active for t in titles)


async def test_reseed_is_idempotent_and_preserves_admin_edits(engine: AsyncEngine) -> None:
    await run_seed(engine)
    async with engine.begin() as connection:
        await connection.execute(
            update(JobTitleModel)
            .where(JobTitleModel.code == "purchasing")
            .values(name_es="Compras", is_active=False)
        )

    await run_seed(engine)

    titles = await _titles(engine)
    assert len(titles) == len(JOB_TITLES)
    purchasing = next(t for t in titles if t.code == "purchasing")
    assert purchasing.name_es == "Compras"
    assert purchasing.is_active is False
