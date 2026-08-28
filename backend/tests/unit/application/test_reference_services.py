from datetime import UTC, datetime, timedelta

import pytest

from app.application.reference.commands import (
    CreateBrand,
    CreateLossReason,
    ReorderStages,
    UpdateBrand,
    UpdateLossReason,
    UpdateStage,
)
from app.application.reference.queries import ReferenceQueries, compute_etag
from app.application.reference.service import BrandService, LossReasonService, PipelineService
from app.domain.reference.entities import AccountType, Brand, LossReason, Pipeline, PipelineStage
from app.domain.reference.errors import (
    BrandNameAlreadyExistsError,
    LastActiveStageError,
    LossReasonNameAlreadyExistsError,
    StageOrderInvalidError,
)
from app.domain.shared.errors import ConcurrentModificationError, NotFoundError
from app.domain.shared.ids import new_id
from app.domain.territories.entities import Division
from app.domain.users.errors import UnknownReferenceError
from tests.unit.fakes import FakeUnitOfWork
from tests.unit.fakes.reference import InMemoryReferenceReadRepository
from tests.unit.fakes.repositories import InMemoryDivisionRepository

ADMIN = new_id()
VASCULAR = Division(id=new_id(), code="vascular", name_es="Vascular", sort_order=40)


@pytest.fixture
def uow() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    uow.divisions = InMemoryDivisionRepository([VASCULAR])
    return uow


async def test_brand_create_and_audit(uow: FakeUnitOfWork) -> None:
    brand = await BrandService(uow).create(
        CreateBrand(name="Cook Medical", is_own=False, division_ids=frozenset({VASCULAR.id})),
        acting_user_id=ADMIN,
    )

    assert brand.code == "cook_medical"
    assert uow.actions() == ["brand.created"]
    assert uow.committed_events[0].changes["is_own"] == {"before": None, "after": False}


async def test_brand_create_rejects_unknown_division_and_duplicate(uow: FakeUnitOfWork) -> None:
    service = BrandService(uow)
    with pytest.raises(UnknownReferenceError):
        await service.create(
            CreateBrand(name="X", is_own=True, division_ids=frozenset({new_id()})),
            acting_user_id=ADMIN,
        )
    await service.create(CreateBrand(name="Hadeco", is_own=True), acting_user_id=ADMIN)
    with pytest.raises(BrandNameAlreadyExistsError):
        await service.create(CreateBrand(name="HADECO", is_own=True), acting_user_id=ADMIN)


async def test_brand_update_audits_changes_and_deactivation(uow: FakeUnitOfWork) -> None:
    service = BrandService(uow)
    brand = await service.create(CreateBrand(name="Hadeco", is_own=True), acting_user_id=ADMIN)

    updated = await service.update(
        brand.id,
        UpdateBrand(expected_version=1, name="Hadeco Europe", is_active=False),
        acting_user_id=ADMIN,
    )

    assert updated.version == 2 and not updated.is_active
    assert uow.actions() == ["brand.created", "brand.updated", "brand.deactivated"]
    with pytest.raises(ConcurrentModificationError):
        await service.update(
            brand.id, UpdateBrand(expected_version=1, name="x"), acting_user_id=ADMIN
        )
    with pytest.raises(NotFoundError):
        await service.update(new_id(), UpdateBrand(expected_version=1), acting_user_id=ADMIN)


async def test_loss_reason_create_appends_and_update(uow: FakeUnitOfWork) -> None:
    service = LossReasonService(uow)
    await uow.loss_reasons.add(LossReason.create(name="Precio", sort_order=10))

    reason = await service.create(
        CreateLossReason(name="Cambio de proveedor"), acting_user_id=ADMIN
    )
    renamed = await service.update(
        reason.id,
        UpdateLossReason(expected_version=1, name="Cambio", is_active=False),
        acting_user_id=ADMIN,
    )

    assert reason.sort_order == 11
    assert renamed.name_es == "Cambio" and not renamed.is_active
    assert uow.actions() == ["loss_reason.created", "loss_reason.updated"]
    with pytest.raises(LossReasonNameAlreadyExistsError):
        await service.create(CreateLossReason(name="precio"), acting_user_id=ADMIN)


def seeded_pipeline() -> Pipeline:
    def stage(code: str, order: int, prob: int, *, is_won: bool = False) -> PipelineStage:
        return PipelineStage(
            id=new_id(), code=code, name_es=code, sort_order=order, probability=prob, is_won=is_won
        )

    return Pipeline(
        id=new_id(),
        code="equipment",
        name_es="Equipos",
        sort_order=10,
        stages=[stage("contact", 1, 10), stage("demo", 2, 30), stage("won", 3, 100, is_won=True)],
    )


async def test_pipeline_rename_stage_update_and_reorder(uow: FakeUnitOfWork) -> None:
    pipeline = seeded_pipeline()
    uow.pipelines.rows[pipeline.id] = pipeline
    service = PipelineService(uow)
    contact, demo, won = pipeline.ordered_stages()

    renamed = await service.rename(
        pipeline.id, "Equipamiento", expected_version=1, acting_user_id=ADMIN
    )
    _, stage = await service.update_stage(
        pipeline.id, demo.id, UpdateStage(expected_version=1, probability=40), acting_user_id=ADMIN
    )
    reordered = await service.reorder(
        pipeline.id,
        ReorderStages(expected_version=2, stage_ids=[demo.id, contact.id, won.id]),
        acting_user_id=ADMIN,
    )

    assert renamed.name_es == "Equipamiento" and renamed.version == 2
    assert stage.probability == 40 and stage.version == 2
    assert [s.code for s in reordered.ordered_stages()] == ["demo", "contact", "won"]
    assert reordered.version == 3
    assert uow.actions() == [
        "pipeline.updated",
        "pipeline_stage.updated",
        "pipeline_stages.reordered",
    ]
    reorder_event = uow.committed_events[-1]
    assert reorder_event.changes["order"]["before"] == [str(contact.id), str(demo.id), str(won.id)]
    assert reorder_event.changes["order"]["after"] == [str(demo.id), str(contact.id), str(won.id)]


async def test_pipeline_guards(uow: FakeUnitOfWork) -> None:
    pipeline = seeded_pipeline()
    uow.pipelines.rows[pipeline.id] = pipeline
    service = PipelineService(uow)
    contact, demo, _ = pipeline.ordered_stages()

    await service.update_stage(
        pipeline.id,
        contact.id,
        UpdateStage(expected_version=1, is_active=False),
        acting_user_id=ADMIN,
    )
    with pytest.raises(LastActiveStageError):
        await service.update_stage(
            pipeline.id,
            demo.id,
            UpdateStage(expected_version=1, is_active=False),
            acting_user_id=ADMIN,
        )
    with pytest.raises(StageOrderInvalidError):
        await service.reorder(
            pipeline.id,
            ReorderStages(expected_version=1, stage_ids=[demo.id]),
            acting_user_id=ADMIN,
        )
    with pytest.raises(ConcurrentModificationError):
        await service.reorder(
            pipeline.id,
            ReorderStages(expected_version=9, stage_ids=[s.id for s in pipeline.stages]),
            acting_user_id=ADMIN,
        )
    assert uow.rollbacks == 3


async def test_reference_bundle_includes_inactive_and_orders_stages(uow: FakeUnitOfWork) -> None:
    now = datetime.now(UTC)
    uow.reference = InMemoryReferenceReadRepository(
        account_types=[
            AccountType(
                id=new_id(),
                code="b",
                name_es="B",
                sort_order=2,
                buys_via_tender=False,
                is_active=True,
                updated_at=now,
            ),
            AccountType(
                id=new_id(),
                code="a",
                name_es="A",
                sort_order=1,
                buys_via_tender=True,
                is_active=False,
                updated_at=now - timedelta(days=1),
            ),
        ]
    )
    inactive = Brand.create(name="Old", is_own=False, division_ids=frozenset())
    inactive.deactivate()
    await uow.brands.add(inactive)
    pipeline = seeded_pipeline()
    pipeline.stages.reverse()
    uow.pipelines.rows[pipeline.id] = pipeline

    bundle = await ReferenceQueries(uow).bundle()

    assert [t.code for t in bundle.account_types] == ["a", "b"]
    assert [b.is_active for b in bundle.brands] == [False]
    assert [s.sort_order for s in bundle.pipelines[0].stages] == [1, 2, 3]
    assert len(bundle.etag) == 32


def test_compute_etag_changes_with_timestamp_and_counts() -> None:
    now = datetime.now(UTC)
    base = compute_etag([now, None], [1, 2])

    assert compute_etag([now], [1, 2]) == base
    assert compute_etag([now + timedelta(seconds=1)], [1, 2]) != base
    assert compute_etag([now], [1, 3]) != base
