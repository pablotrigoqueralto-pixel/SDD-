import pytest

from app.domain.reference.entities import Brand, LossReason, Pipeline, PipelineStage
from app.domain.reference.errors import (
    LastActiveStageError,
    StageOrderInvalidError,
    StageProbabilityInvalidError,
)
from app.domain.shared.errors import NotFoundError
from app.domain.shared.ids import new_id


def test_brand_create_derives_code_and_trims_name() -> None:
    division = new_id()
    brand = Brand.create(name="  Cook Medical ", is_own=False, division_ids=frozenset({division}))

    assert brand.code == "cook_medical"
    assert brand.name == "Cook Medical"
    assert brand.is_own is False
    assert brand.division_ids == frozenset({division})
    assert brand.is_active and brand.version == 1


def test_brand_mutations() -> None:
    brand = Brand.create(name="Hadeco", is_own=True, division_ids=frozenset())

    brand.rename(" Hadeco Europe ")
    brand.set_own(False)
    brand.deactivate()

    assert (brand.name, brand.is_own, brand.is_active) == ("Hadeco Europe", False, False)
    brand.activate()
    assert brand.is_active


def test_loss_reason_create_and_rename() -> None:
    reason = LossReason.create(name="Cambio de proveedor", sort_order=7)

    assert reason.code == "cambio_de_proveedor"
    assert reason.sort_order == 7
    assert not reason.requires_brand and not reason.requires_note
    reason.rename("Cambio de proveedor ")
    reason.deactivate()
    assert reason.name_es == "Cambio de proveedor" and not reason.is_active


def make_pipeline() -> Pipeline:
    def stage(
        code: str, order: int, probability: int, *, is_won: bool = False, is_lost: bool = False
    ) -> PipelineStage:
        return PipelineStage(
            id=new_id(),
            code=code,
            name_es=code.title(),
            sort_order=order,
            probability=probability,
            is_won=is_won,
            is_lost=is_lost,
        )

    return Pipeline(
        id=new_id(),
        code="equipment",
        name_es="Equipos",
        sort_order=1,
        stages=[
            stage("contact", 1, 10),
            stage("demo", 2, 30),
            stage("won", 3, 100, is_won=True),
            stage("lost", 4, 0, is_lost=True),
        ],
    )


def test_update_stage_name_and_probability() -> None:
    pipeline = make_pipeline()
    demo = pipeline.ordered_stages()[1]

    updated = pipeline.update_stage(demo.id, name=" Demostración ", probability=40)

    assert updated.name_es == "Demostración"
    assert updated.probability == 40


@pytest.mark.parametrize("probability", [-1, 101])
def test_update_stage_rejects_probability_out_of_range(probability: int) -> None:
    pipeline = make_pipeline()

    with pytest.raises(StageProbabilityInvalidError) as exc_info:
        pipeline.update_stage(pipeline.stages[0].id, probability=probability)

    assert exc_info.value.code == "stage_probability_invalid"


def test_deactivating_keeps_at_least_one_open_stage() -> None:
    pipeline = make_pipeline()
    contact, demo = pipeline.ordered_stages()[:2]

    pipeline.update_stage(contact.id, is_active=False)
    with pytest.raises(LastActiveStageError):
        pipeline.update_stage(demo.id, is_active=False)

    pipeline.update_stage(contact.id, is_active=True)
    pipeline.update_stage(demo.id, is_active=False)
    assert not demo.is_active


def test_deactivating_a_closed_stage_is_not_limited() -> None:
    pipeline = make_pipeline()
    won = next(stage for stage in pipeline.stages if stage.is_won)

    pipeline.update_stage(won.id, is_active=False)

    assert not won.is_active


def test_unknown_stage() -> None:
    with pytest.raises(NotFoundError):
        make_pipeline().update_stage(new_id(), name="x")


def test_reorder_reassigns_contiguous_sort_order() -> None:
    pipeline = make_pipeline()
    contact, demo, won, lost = pipeline.ordered_stages()

    pipeline.reorder([demo.id, contact.id, won.id, lost.id])

    assert [stage.code for stage in pipeline.ordered_stages()] == ["demo", "contact", "won", "lost"]
    assert [stage.sort_order for stage in pipeline.ordered_stages()] == [1, 2, 3, 4]


@pytest.mark.parametrize(
    ("mutate", "message"),
    [
        (lambda ids: ids[:-1], "must be listed"),
        (lambda ids: [*ids, ids[0]], "must not repeat"),
        (lambda ids: [*ids[:-1], new_id()], "Unknown stages"),
    ],
)
def test_reorder_rejects_invalid_lists(mutate, message: str) -> None:  # type: ignore[no-untyped-def]
    pipeline = make_pipeline()
    ids = [stage.id for stage in pipeline.ordered_stages()]

    with pytest.raises(StageOrderInvalidError, match=message) as exc_info:
        pipeline.reorder(mutate(ids))

    assert exc_info.value.code == "stage_order_invalid"
    assert exc_info.value.status == 422
