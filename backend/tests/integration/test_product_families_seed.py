import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.infrastructure.db.models import ProductFamilyModel
from app.infrastructure.db.seed import PRODUCT_FAMILIES, division_id, reference_id, run_seed

pytestmark = pytest.mark.integration


async def _families(engine: AsyncEngine) -> list[ProductFamilyModel]:
    async with async_sessionmaker(engine)() as session:
        statement = select(ProductFamilyModel).order_by(
            ProductFamilyModel.division_id, ProductFamilyModel.sort_order
        )
        return list((await session.execute(statement)).scalars().all())


async def test_seed_creates_starter_families_per_division(engine: AsyncEngine) -> None:
    await run_seed(engine)

    families = await _families(engine)

    assert len(families) >= 12
    assert {f.code for f in families} == {code for _, code, _ in PRODUCT_FAMILIES}
    dopplers = next(f for f in families if f.code == "dopplers")
    assert dopplers.id == reference_id("product_families", "dopplers")
    assert dopplers.division_id == division_id("vascular")
    assert dopplers.name_es == "Dopplers"
    assert all(f.is_active for f in families)


async def test_reseed_preserves_admin_edits(engine: AsyncEngine) -> None:
    await run_seed(engine)
    async with engine.begin() as connection:
        await connection.execute(
            update(ProductFamilyModel)
            .where(ProductFamilyModel.code == "dopplers")
            .values(name_es="Doppler vascular", is_active=False)
        )
    try:
        await run_seed(engine)

        families = await _families(engine)
        assert len(families) == len(PRODUCT_FAMILIES)
        dopplers = next(f for f in families if f.code == "dopplers")
        assert dopplers.name_es == "Doppler vascular"
        assert dopplers.is_active is False
    finally:
        # The edit is committed outside the test transaction: restore the seeded row.
        async with engine.begin() as connection:
            await connection.execute(
                update(ProductFamilyModel)
                .where(ProductFamilyModel.code == "dopplers")
                .values(name_es="Dopplers", is_active=True)
            )
