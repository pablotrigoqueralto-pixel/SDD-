from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domain.activities.entities import Activity, ActivityKind
from app.domain.catalogue.entities import Product, ProductKind
from app.domain.catalogue.errors import SkuLockedError
from app.domain.opportunities.entities import AtRiskSource, Opportunity, StageChange
from app.domain.reference.entities import Pipeline
from app.domain.shared.errors import ConcurrentModificationError
from app.infrastructure.db.repositories.accounts import SqlAlchemyAccountRepository
from app.infrastructure.db.repositories.activities import SqlAlchemyActivityRepository
from app.infrastructure.db.repositories.catalogue import SqlAlchemyProductRepository
from app.infrastructure.db.repositories.opportunities import SqlAlchemyOpportunityRepository
from app.infrastructure.db.repositories.reference import SqlAlchemyPipelineRepository
from app.infrastructure.db.seed import reference_id
from tests.integration.repositories.conftest import VASCULAR_ID, World, make_account

pytestmark = pytest.mark.integration

NOW = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)
EQUIPMENT_ID: UUID = reference_id("pipelines", "equipment")
CONSUMABLES_ID: UUID = reference_id("pipelines", "consumables")
VISIT_TYPE_ID: UUID = reference_id("activity_types", "visit")
HADECO_ID: UUID = reference_id("brands", "hadeco")
DOPPLERS_FAMILY_ID: UUID = reference_id("product_families", "dopplers")


async def load_pipeline(session: AsyncSession, pipeline_id: UUID) -> Pipeline:
    pipeline = await SqlAlchemyPipelineRepository(session).get(pipeline_id)
    assert pipeline is not None
    return pipeline


async def make_opportunity(
    session: AsyncSession,
    world: World,
    *,
    pipeline_id: UUID = EQUIPMENT_ID,
    **overrides: object,
) -> tuple[Opportunity, StageChange, Pipeline]:
    accounts = SqlAlchemyAccountRepository(session)
    account = make_account(
        f"Centro {overrides.pop('marker', '')}".strip() or "Centro O",
        territory_id=world.centro.id,
        owner_id=world.rep.id,
    )
    await accounts.add(account)
    pipeline = await load_pipeline(session, pipeline_id)
    values: dict[str, object] = {
        "account_id": account.id,
        "account_name": account.name,
        "buys_via_tender": False,
        "division_id": VASCULAR_ID,
        "division_name": "Vascular",
        "pipeline": pipeline,
        "estimated_amount": "30000",
        "owner_id": world.rep.id,
        "created_by": world.rep.id,
        "now": NOW,
    }
    values.update(overrides)
    opportunity, change = Opportunity.create(**values)  # type: ignore[arg-type]
    return opportunity, change, pipeline


async def test_round_trip_history_and_conflict(session: AsyncSession, world: World) -> None:
    repo = SqlAlchemyOpportunityRepository(session)
    opportunity, change, pipeline = await make_opportunity(
        session, world, is_tender=True, tender_reference="EXP-1", tender_deadline=date(2026, 9, 15)
    )

    await repo.add(opportunity)
    await repo.add_stage_change(change)

    stored = await repo.get(opportunity.id)
    assert stored is not None
    assert stored.name == opportunity.name
    assert stored.estimated_amount == Decimal("30000.00")
    assert stored.is_tender and stored.tender_reference == "EXP-1"
    assert stored.stage_entered_at == NOW

    move = stored.move_stage(
        pipeline,
        next(s.id for s in pipeline.stages if s.code == "demo"),
        actor_id=world.rep.id,
        now=NOW + timedelta(days=2),
    )
    await repo.save(stored, expected_version=1)
    await repo.add_stage_change(move)
    history = await repo.list_history(opportunity.id)
    assert history[0].to_stage_id == move.to_stage_id
    assert history[0].seconds_in_previous_stage == 2 * 86400
    assert history[-1].from_stage_id is None

    with pytest.raises(ConcurrentModificationError):
        await repo.save(stored, expected_version=1)


async def test_lines_sync_and_product_reference_lock(session: AsyncSession, world: World) -> None:
    repo = SqlAlchemyOpportunityRepository(session)
    products = SqlAlchemyProductRepository(session)
    product = Product.create(
        sku="OPP-1",
        name="Doppler",
        brand_id=HADECO_ID,
        family_id=DOPPLERS_FAMILY_ID,
        kind=ProductKind.EQUIPMENT,
        list_price="12500",
        created_by=world.back_office.id,
    )
    await products.add(product)
    opportunity, change, _ = await make_opportunity(session, world, marker="L")
    await repo.add(opportunity)
    await repo.add_stage_change(change)

    assert await products.is_referenced(product.id) is False
    line = opportunity.add_line(
        product_id=product.id, quantity="2", unit_price="12500", product_active=True
    )
    await repo.save(opportunity, expected_version=1)

    stored = await repo.get(opportunity.id)
    assert stored is not None and stored.amount == Decimal("25000.00")
    assert [entry.id for entry in stored.lines] == [line.id]
    assert await products.is_referenced(product.id) is True
    with pytest.raises(SkuLockedError):
        product.change_sku("OPP-2", referenced=await products.is_referenced(product.id))

    stored.update_line(line.id, quantity="3")
    await repo.save(stored, expected_version=2)
    again = await repo.get(opportunity.id)
    assert again is not None and again.amount == Decimal("37500.00")

    again.remove_line(line.id)
    await repo.save(again, expected_version=3)
    empty = await repo.get(opportunity.id)
    assert empty is not None and empty.lines == [] and empty.amount == Decimal("30000.00")
    assert await products.is_referenced(product.id) is False


async def test_at_risk_candidates_rule(session: AsyncSession, world: World) -> None:
    repo = SqlAlchemyOpportunityRepository(session)
    activities = SqlAlchemyActivityRepository(session)
    threshold = NOW - timedelta(days=60)

    async def won_consumables(marker: str, *, updated: datetime) -> Opportunity:
        opportunity, change, pipeline = await make_opportunity(
            session, world, pipeline_id=CONSUMABLES_ID, marker=marker
        )
        opportunity.win(pipeline, actor_id=world.rep.id, now=updated)
        await repo.add(opportunity)
        await repo.add_stage_change(change)
        # updated_at is server-driven: backdate it directly for the rule.
        from sqlalchemy import update as sql_update

        from app.infrastructure.db.models import OpportunityModel

        await session.execute(
            sql_update(OpportunityModel)
            .where(OpportunityModel.id == opportunity.id)
            .values(updated_at=updated)
        )
        return opportunity

    silent = await won_consumables("S", updated=threshold - timedelta(days=5))
    fresh = await won_consumables("F", updated=NOW - timedelta(days=5))
    visited = await won_consumables("V", updated=threshold - timedelta(days=5))
    visit = Activity.record_done(
        account_id=visited.account_id,
        kind=ActivityKind(id=VISIT_TYPE_ID, is_note=False, counts_as_contact=True),
        owner_id=world.rep.id,
        created_by=world.rep.id,
        now=NOW - timedelta(days=3),
    )
    visit.opportunity_id = visited.id
    await activities.add(visit)

    equipment_won, eq_change, eq_pipeline = await make_opportunity(session, world, marker="E")
    equipment_won.win(eq_pipeline, actor_id=world.rep.id, now=NOW)
    await repo.add(equipment_won)
    await repo.add_stage_change(eq_change)

    flagged, flag_change, cons_pipeline = await make_opportunity(
        session, world, pipeline_id=CONSUMABLES_ID, marker="A"
    )
    flagged.win(cons_pipeline, actor_id=world.rep.id, now=NOW)
    flagged.set_at_risk(
        cons_pipeline, True, source=AtRiskSource.MANUAL, actor_id=world.rep.id, now=NOW
    )
    await repo.add(flagged)
    await repo.add_stage_change(flag_change)

    candidates = await repo.list_at_risk_candidate_ids(threshold=threshold)

    assert silent.id in candidates
    assert fresh.id not in candidates
    assert visited.id not in candidates
    assert equipment_won.id not in candidates
    assert flagged.id not in candidates
