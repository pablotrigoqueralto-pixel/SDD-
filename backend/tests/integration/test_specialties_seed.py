"""The specialties catalogue: seeded insert-only, admin edits survive a re-seed."""

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.infrastructure.db.models import SpecialtyModel
from app.infrastructure.db.seed import SPECIALTIES, reference_id, run_seed

pytestmark = pytest.mark.integration


async def _specialties(engine: AsyncEngine) -> list[SpecialtyModel]:
    async with async_sessionmaker(engine)() as session:
        statement = select(SpecialtyModel).order_by(SpecialtyModel.sort_order)
        return list((await session.execute(statement)).scalars().all())


async def test_seed_creates_the_business_catalogue_with_stable_ids(engine: AsyncEngine) -> None:
    await run_seed(engine)

    specialties = await _specialties(engine)

    assert [s.code for s in specialties] == [code for code, _ in SPECIALTIES]
    assert len(specialties) == 12
    assert [s.name_es for s in specialties][:4] == [
        "Ginecología",
        "Reproducción asistida",
        "Embriología",
        "Cirugía Vascular",
    ]
    assert specialties[0].id == reference_id("specialties", "gynaecology")
    assert all(s.is_active for s in specialties)


async def test_reseed_is_idempotent_and_preserves_admin_edits(engine: AsyncEngine) -> None:
    await run_seed(engine)
    async with engine.begin() as connection:
        await connection.execute(
            update(SpecialtyModel)
            .where(SpecialtyModel.code == "podiatry")
            .values(name_es="Podología clínica", is_active=False)
        )
    try:
        await run_seed(engine)

        specialties = await _specialties(engine)
        assert len(specialties) == len(SPECIALTIES)  # no duplicates
        podiatry = next(s for s in specialties if s.code == "podiatry")
        assert podiatry.name_es == "Podología clínica"
        assert podiatry.is_active is False
    finally:
        # The edit is committed outside the test transaction: restore the seeded row.
        async with engine.begin() as connection:
            await connection.execute(
                update(SpecialtyModel)
                .where(SpecialtyModel.code == "podiatry")
                .values(name_es="Podología", is_active=True)
            )
