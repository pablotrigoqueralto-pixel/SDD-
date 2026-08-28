import pytest
from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncEngine, async_sessionmaker

from app.infrastructure.db.models import (
    AccountTypeModel,
    ActivityTypeModel,
    BrandModel,
    LossReasonModel,
    PipelineDivisionModel,
    PipelineModel,
    PipelineStageModel,
)
from app.infrastructure.db.seed import DIVISIONS, reference_id, run_seed

pytestmark = pytest.mark.integration


async def test_seed_creates_all_reference_data(engine: AsyncEngine) -> None:
    await run_seed(engine)
    # ORM selects need a session (a Core connection would return raw columns).
    async with async_sessionmaker(engine)() as connection:
        account_types = (
            (
                await connection.execute(
                    select(AccountTypeModel).order_by(AccountTypeModel.sort_order)
                )
            )
            .scalars()
            .all()
        )
        activity_types = (
            (
                await connection.execute(
                    select(ActivityTypeModel).order_by(ActivityTypeModel.sort_order)
                )
            )
            .scalars()
            .all()
        )
        brands = (await connection.execute(select(BrandModel))).scalars().all()
        reasons = (
            (await connection.execute(select(LossReasonModel).order_by(LossReasonModel.sort_order)))
            .scalars()
            .all()
        )
        pipelines = (
            (await connection.execute(select(PipelineModel).order_by(PipelineModel.sort_order)))
            .scalars()
            .all()
        )
        stages = (
            (
                await connection.execute(
                    select(PipelineStageModel).order_by(
                        PipelineStageModel.pipeline_id, PipelineStageModel.sort_order
                    )
                )
            )
            .scalars()
            .all()
        )
        pipeline_divisions = (
            (await connection.execute(select(PipelineDivisionModel))).scalars().all()
        )

    assert [t.name_es for t in account_types] == [
        "Clínica FIV / laboratorio",
        "Hospital público",
        "Hospital privado",
        "Clínica o consulta privada",
        "Centro de podología / pie diabético",
        "Distribuidor",
    ]
    assert [t.code for t in account_types if t.buys_via_tender] == ["public_hospital"]
    assert [t.name_es for t in activity_types] == [
        "Visita",
        "Llamada",
        "Email",
        "Demo",
        "Formación",
        "Nota",
    ]
    assert [t.code for t in activity_types if not t.counts_as_contact] == ["note"]
    own = {b.code for b in brands if b.is_own and b.is_active}
    assert len(own) >= 13 and "three_gen" in own
    assert next(b.name for b in brands if b.code == "three_gen") == "3Gen"
    assert [r.code for r in reasons if r.requires_brand] == ["competitor"]
    assert [r.code for r in reasons if r.requires_note] == ["other"]
    assert [p.code for p in pipelines] == ["equipment", "consumables"]
    equipment = next(p for p in pipelines if p.code == "equipment")
    equipment_stages = [s for s in stages if s.pipeline_id == equipment.id]
    assert [(s.code, s.probability) for s in equipment_stages] == [
        ("contact", 10),
        ("demo", 30),
        ("quote", 50),
        ("negotiation", 70),
        ("won", 100),
        ("lost", 0),
    ]
    consumables = next(p for p in pipelines if p.code == "consumables")
    consumable_stages = [s for s in stages if s.pipeline_id == consumables.id]
    assert [s.code for s in consumable_stages if s.is_at_risk] == ["at_risk"]
    assert [s.code for s in consumable_stages if s.is_won] == ["recurring"]
    assert {row.division_id for row in pipeline_divisions} == {d.id for d in DIVISIONS}
    assert len(pipeline_divisions) == len(DIVISIONS)


async def test_seed_is_deterministic_and_idempotent(engine: AsyncEngine) -> None:
    await run_seed(engine)
    await run_seed(engine)
    async with engine.connect() as connection:
        brand_count = await connection.scalar(text("SELECT count(*) FROM brands WHERE is_own"))
        hadeco_id = await connection.scalar(text("SELECT id FROM brands WHERE code = 'hadeco'"))
        stage_count = await connection.scalar(text("SELECT count(*) FROM pipeline_stages"))

    assert brand_count == 13
    assert hadeco_id == reference_id("brands", "hadeco")
    assert stage_count == 11


async def test_reseed_preserves_admin_edits_and_refreshes_flags(engine: AsyncEngine) -> None:
    await run_seed(engine)
    async with engine.begin() as connection:
        await connection.execute(
            update(BrandModel).where(BrandModel.code == "hadeco").values(name="Hadeco Europe")
        )
        await connection.execute(
            update(PipelineStageModel)
            .where(PipelineStageModel.code == "demo")
            .values(probability=40, name_es="Demostración")
        )
        # A drifted semantic flag must be corrected by the seed.
        await connection.execute(
            update(LossReasonModel)
            .where(LossReasonModel.code == "competitor")
            .values(requires_brand=False)
        )

    await run_seed(engine)

    async with engine.connect() as connection:
        hadeco = await connection.scalar(text("SELECT name FROM brands WHERE code = 'hadeco'"))
        demo = (
            await connection.execute(
                text("SELECT probability, name_es FROM pipeline_stages WHERE code = 'demo'")
            )
        ).one()
        competitor = await connection.scalar(
            text("SELECT requires_brand FROM loss_reasons WHERE code = 'competitor'")
        )
    try:
        assert hadeco == "Hadeco Europe"
        assert (demo.probability, demo.name_es) == (40, "Demostración")
        assert competitor is True
    finally:
        async with engine.begin() as connection:
            await connection.execute(
                update(BrandModel).where(BrandModel.code == "hadeco").values(name="Hadeco")
            )
            await connection.execute(
                update(PipelineStageModel)
                .where(PipelineStageModel.code == "demo")
                .values(probability=30, name_es="Demo")
            )
