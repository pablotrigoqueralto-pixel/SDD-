import pytest
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from app.domain.reference.entities import Brand, LossReason
from app.domain.reference.errors import (
    BrandNameAlreadyExistsError,
    LossReasonNameAlreadyExistsError,
)
from app.domain.shared.errors import ConcurrentModificationError
from app.infrastructure.db.repositories.reference import (
    SqlAlchemyBrandRepository,
    SqlAlchemyLossReasonRepository,
    SqlAlchemyPipelineRepository,
    SqlAlchemyReferenceReadRepository,
)
from app.infrastructure.db.seed import DIVISIONS, run_seed

pytestmark = pytest.mark.integration

VASCULAR = next(d.id for d in DIVISIONS if d.code == "vascular")


@pytest.fixture(autouse=True)
async def seeded(engine: AsyncEngine) -> None:
    await run_seed(engine)


async def test_brand_add_get_list_and_filters(session: AsyncSession) -> None:
    repo = SqlAlchemyBrandRepository(session)
    cook = Brand.create(name="Cook Medical", is_own=False, division_ids=frozenset({VASCULAR}))

    await repo.add(cook)

    loaded = await repo.get(cook.id)
    assert loaded is not None
    assert loaded.division_ids == frozenset({VASCULAR})
    competitors = await repo.list_all(is_own=False, is_active=True)
    assert [b.name for b in competitors] == ["Cook Medical"]
    assert [b.name for b in await repo.list_all(q="co")] == ["Comen", "Cook Medical"]


async def test_brand_name_unique_case_insensitive(session: AsyncSession) -> None:
    repo = SqlAlchemyBrandRepository(session)

    with pytest.raises(BrandNameAlreadyExistsError):
        await repo.add(Brand.create(name="FERTIPRO", is_own=False, division_ids=frozenset()))


async def test_brand_save_syncs_divisions_and_checks_version(session: AsyncSession) -> None:
    repo = SqlAlchemyBrandRepository(session)
    brands = await repo.list_all(q="Hadeco")
    hadeco = brands[0]

    hadeco.rename("Hadeco Europe")
    hadeco.set_divisions(frozenset({VASCULAR}))
    await repo.save(hadeco, expected_version=hadeco.version - 0)

    reloaded = await repo.get(hadeco.id)
    assert reloaded is not None
    assert reloaded.name == "Hadeco Europe"
    assert reloaded.division_ids == frozenset({VASCULAR})
    assert reloaded.version == 2
    with pytest.raises(ConcurrentModificationError):
        await repo.save(hadeco, expected_version=1)


async def test_loss_reason_append_and_uniqueness(session: AsyncSession) -> None:
    repo = SqlAlchemyLossReasonRepository(session)

    order = await repo.next_sort_order()
    reason = LossReason.create(name="Cambio de proveedor", sort_order=order)
    await repo.add(reason)

    listed = await repo.list_all()
    assert listed[-1].code == "cambio_de_proveedor"
    assert order > max(r.sort_order for r in listed[:-1])
    with pytest.raises(LossReasonNameAlreadyExistsError):
        await repo.add(LossReason.create(name="precio", sort_order=order + 1))


async def test_pipeline_reorder_and_stage_save(session: AsyncSession) -> None:
    repo = SqlAlchemyPipelineRepository(session)
    pipelines = await repo.list_all()
    equipment = next(p for p in pipelines if p.code == "equipment")
    contact, demo = equipment.ordered_stages()[:2]

    equipment.reorder([demo.id, contact.id, *[s.id for s in equipment.ordered_stages()[2:]]])
    await repo.save(equipment, expected_version=equipment.version)
    equipment.update_stage(demo.id, probability=40)
    await repo.save_stage(equipment, demo.id, expected_version=demo.version)

    reloaded = await repo.get(equipment.id)
    assert reloaded is not None
    assert [s.code for s in reloaded.ordered_stages()][:2] == ["demo", "contact"]
    assert reloaded.stage(demo.id).probability == 40
    assert reloaded.stage(demo.id).version == 2
    assert reloaded.version == 2
    with pytest.raises(ConcurrentModificationError):
        await repo.save_stage(equipment, demo.id, expected_version=1)


async def test_read_repository_orders_types(session: AsyncSession) -> None:
    repo = SqlAlchemyReferenceReadRepository(session)

    account_types = await repo.account_types()
    activity_types = await repo.activity_types()

    assert account_types[0].code == "ivf_clinic" and account_types[1].buys_via_tender
    assert activity_types[-1].code == "note" and not activity_types[-1].counts_as_contact
