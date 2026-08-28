from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import pytest

from app.domain.opportunities.entities import (
    AtRiskSource,
    Opportunity,
    OpportunityStatus,
    StageChange,
    default_close_date,
    generated_name,
)
from app.domain.opportunities.errors import (
    AtRiskNotSupportedError,
    InvalidOpportunityTransitionError,
    LineDuplicatedError,
    LineProductInactiveError,
    LossReasonRequiresBrandError,
    LossReasonRequiresNoteError,
    OpportunityClosedError,
    OpportunityHasLinesError,
    StageNotInPipelineError,
    TenderFieldsRequireTenderError,
)
from app.domain.reference.entities import Pipeline, PipelineStage
from app.domain.shared.errors import ValidationFailedError
from app.domain.shared.ids import new_id

NOW = datetime(2026, 8, 28, 10, 0, tzinfo=UTC)
ACCOUNT = new_id()
DIVISION = new_id()
ACTOR = new_id()


def stage(
    code: str,
    order: int,
    *,
    is_won: bool = False,
    is_lost: bool = False,
    is_at_risk: bool = False,
) -> PipelineStage:
    return PipelineStage(
        id=new_id(),
        code=code,
        name_es=code.title(),
        sort_order=order,
        probability=50,
        is_won=is_won,
        is_lost=is_lost,
        is_at_risk=is_at_risk,
    )


def equipment_pipeline() -> Pipeline:
    return Pipeline(
        id=new_id(),
        code="equipment",
        name_es="Equipos",
        sort_order=10,
        stages=[
            stage("contact", 1),
            stage("demo", 2),
            stage("quote", 3),
            stage("negotiation", 4),
            stage("won", 5, is_won=True),
            stage("lost", 6, is_lost=True),
        ],
    )


def consumables_pipeline() -> Pipeline:
    return Pipeline(
        id=new_id(),
        code="consumables",
        name_es="Consumibles",
        sort_order=20,
        stages=[
            stage("trial", 1),
            stage("first_order", 2),
            stage("recurring", 3, is_won=True),
            stage("at_risk", 4, is_at_risk=True),
            stage("lost", 5, is_lost=True),
        ],
    )


def by_code(pipeline: Pipeline, code: str) -> UUID:
    return next(s.id for s in pipeline.stages if s.code == code)


def status_of(opportunity: Opportunity) -> OpportunityStatus:
    """Erase mypy's literal narrowing: mutations happen inside aggregate methods."""
    return opportunity.status


def current(value: object) -> object:
    """Same purpose as `status_of` for any attribute read after a mutating call."""
    return value


def create(pipeline: Pipeline, **overrides: object) -> tuple[Opportunity, StageChange]:
    values: dict[str, object] = {
        "account_id": ACCOUNT,
        "account_name": "Clínica Tambre",
        "buys_via_tender": False,
        "division_id": DIVISION,
        "division_name": "Vascular",
        "pipeline": pipeline,
        "estimated_amount": "30000",
        "owner_id": ACTOR,
        "created_by": ACTOR,
        "now": NOW,
    }
    values.update(overrides)
    return Opportunity.create(**values)  # type: ignore[arg-type]


def test_create_applies_smart_defaults() -> None:
    pipeline = equipment_pipeline()
    opportunity, change = create(pipeline)

    assert opportunity.stage_id == by_code(pipeline, "contact")
    assert opportunity.status is OpportunityStatus.OPEN
    assert opportunity.name == "Clínica Tambre · Vascular · agosto 2026"
    assert opportunity.estimated_amount == Decimal("30000.00")
    assert opportunity.amount == Decimal("30000.00")
    assert opportunity.expected_close_date == date(2026, 11, 26)
    assert opportunity.is_tender is False
    assert opportunity.stage_entered_at == NOW
    assert change.from_stage_id is None and change.to_stage_id == opportunity.stage_id

    consumables, _ = create(consumables_pipeline())
    assert consumables.expected_close_date == date(2026, 9, 27)


def test_create_tender_defaults_and_validation() -> None:
    opportunity, _ = create(equipment_pipeline(), buys_via_tender=True)
    assert opportunity.is_tender is True

    with pytest.raises(TenderFieldsRequireTenderError):
        create(equipment_pipeline(), tender_deadline=date(2026, 9, 15))
    tender, _ = create(
        equipment_pipeline(),
        is_tender=True,
        tender_reference=" EXP-2026/44 ",
        tender_deadline=date(2026, 9, 15),
    )
    assert tender.tender_reference == "EXP-2026/44"


def test_generated_name_and_close_date_helpers() -> None:
    assert generated_name("A", "B", datetime(2026, 1, 5, tzinfo=UTC)) == "A · B · enero 2026"
    assert default_close_date(consumables_pipeline(), date(2026, 8, 28)) == date(2026, 9, 27)


def test_move_stage_free_between_open_stages_only() -> None:
    pipeline = equipment_pipeline()
    opportunity, _ = create(pipeline)

    later = NOW + timedelta(days=6)
    change = opportunity.move_stage(pipeline, by_code(pipeline, "quote"), actor_id=ACTOR, now=later)
    assert change.seconds_in_previous_stage == 6 * 86400
    back = opportunity.move_stage(
        pipeline, by_code(pipeline, "demo"), actor_id=ACTOR, now=later + timedelta(hours=1)
    )
    assert back.to_stage_id == by_code(pipeline, "demo")
    assert opportunity.days_in_stage(later + timedelta(hours=1)) == 0

    with pytest.raises(InvalidOpportunityTransitionError):
        opportunity.move_stage(pipeline, by_code(pipeline, "won"), actor_id=ACTOR, now=later)
    with pytest.raises(InvalidOpportunityTransitionError):
        opportunity.move_stage(pipeline, by_code(pipeline, "demo"), actor_id=ACTOR, now=later)
    with pytest.raises(StageNotInPipelineError):
        opportunity.move_stage(pipeline, new_id(), actor_id=ACTOR, now=later)
    with pytest.raises(StageNotInPipelineError):
        opportunity.move_stage(
            consumables_pipeline(), by_code(pipeline, "demo"), actor_id=ACTOR, now=later
        )

    consumables = consumables_pipeline()
    trial, _ = create(consumables)
    with pytest.raises(InvalidOpportunityTransitionError):
        trial.move_stage(consumables, by_code(consumables, "at_risk"), actor_id=ACTOR, now=later)


def test_win_defaults_and_immutability() -> None:
    pipeline = equipment_pipeline()
    opportunity, _ = create(pipeline)

    change = opportunity.win(pipeline, actor_id=ACTOR, now=NOW)

    assert opportunity.status is OpportunityStatus.WON
    assert opportunity.won_amount == Decimal("30000.00") and opportunity.won_at == NOW
    assert change.to_stage_id == by_code(pipeline, "won")
    with pytest.raises(OpportunityClosedError):
        opportunity.move_stage(pipeline, by_code(pipeline, "demo"), actor_id=ACTOR, now=NOW)
    with pytest.raises(OpportunityClosedError):
        opportunity.rename("x")
    with pytest.raises(OpportunityClosedError):
        opportunity.add_line(product_id=new_id(), quantity=1, unit_price=1, product_active=True)
    with pytest.raises(OpportunityClosedError):
        opportunity.win(pipeline, actor_id=ACTOR, now=NOW)


def test_lose_requirements_and_reopen() -> None:
    pipeline = equipment_pipeline()
    opportunity, _ = create(pipeline)
    reason = new_id()

    with pytest.raises(LossReasonRequiresBrandError):
        opportunity.lose(
            pipeline,
            loss_reason_id=reason,
            requires_brand=True,
            requires_note=False,
            actor_id=ACTOR,
            now=NOW,
        )
    with pytest.raises(LossReasonRequiresNoteError):
        opportunity.lose(
            pipeline,
            loss_reason_id=reason,
            requires_brand=False,
            requires_note=True,
            actor_id=ACTOR,
            now=NOW,
            note="   ",
        )
    brand = new_id()
    opportunity.lose(
        pipeline,
        loss_reason_id=reason,
        requires_brand=True,
        requires_note=False,
        actor_id=ACTOR,
        now=NOW,
        competitor_brand_id=brand,
    )
    assert opportunity.status is OpportunityStatus.LOST
    assert opportunity.competitor_brand_id == brand and opportunity.lost_at == NOW

    change = opportunity.reopen(pipeline, by_code(pipeline, "negotiation"), actor_id=ACTOR, now=NOW)
    assert status_of(opportunity) is OpportunityStatus.OPEN
    assert current(opportunity.loss_reason_id) is None and current(opportunity.lost_at) is None
    assert change.to_stage_id == by_code(pipeline, "negotiation")
    with pytest.raises(InvalidOpportunityTransitionError):
        opportunity.reopen(pipeline, by_code(pipeline, "demo"), actor_id=ACTOR, now=NOW)


def test_at_risk_lifecycle_and_churn() -> None:
    consumables = consumables_pipeline()
    equipment = equipment_pipeline()
    won, _ = create(consumables)
    won.win(consumables, actor_id=ACTOR, now=NOW)

    equipment_won, _ = create(equipment)
    equipment_won.win(equipment, actor_id=ACTOR, now=NOW)
    with pytest.raises(AtRiskNotSupportedError):
        equipment_won.set_at_risk(
            equipment, True, source=AtRiskSource.MANUAL, actor_id=ACTOR, now=NOW
        )

    still_open, _ = create(consumables)
    with pytest.raises(AtRiskNotSupportedError):
        still_open.set_at_risk(
            consumables, True, source=AtRiskSource.MANUAL, actor_id=ACTOR, now=NOW
        )

    change = won.set_at_risk(
        consumables, True, source=AtRiskSource.AUTOMATIC, actor_id=None, now=NOW
    )
    assert change is not None and change.to_stage_id == by_code(consumables, "at_risk")
    assert won.is_at_risk and current(won.at_risk_source) is AtRiskSource.AUTOMATIC
    assert status_of(won) is OpportunityStatus.WON
    assert (
        won.set_at_risk(consumables, True, source=AtRiskSource.MANUAL, actor_id=ACTOR, now=NOW)
        is None
    )

    cleared = won.set_at_risk(
        consumables, False, source=AtRiskSource.MANUAL, actor_id=ACTOR, now=NOW
    )
    assert cleared is not None and cleared.to_stage_id == by_code(consumables, "recurring")
    assert current(won.is_at_risk) is False and current(won.at_risk_since) is None

    won.set_at_risk(consumables, True, source=AtRiskSource.AUTOMATIC, actor_id=None, now=NOW)
    reason = new_id()
    won.lose(
        consumables,
        loss_reason_id=reason,
        requires_brand=False,
        requires_note=False,
        actor_id=ACTOR,
        now=NOW,
    )
    assert status_of(won) is OpportunityStatus.LOST and not won.is_at_risk


def test_lines_amount_rule() -> None:
    pipeline = equipment_pipeline()
    opportunity, _ = create(pipeline)
    product = new_id()

    line = opportunity.add_line(
        product_id=product, quantity="2", unit_price="12500.5", product_active=True
    )
    assert line.total == Decimal("25001.00")
    assert opportunity.amount == Decimal("25001.00")
    with pytest.raises(OpportunityHasLinesError):
        opportunity.set_estimated_amount("40000")
    with pytest.raises(LineDuplicatedError):
        opportunity.add_line(product_id=product, quantity=1, unit_price=1, product_active=True)
    with pytest.raises(LineProductInactiveError):
        opportunity.add_line(product_id=new_id(), quantity=1, unit_price=1, product_active=False)
    with pytest.raises(ValidationFailedError):
        opportunity.add_line(product_id=new_id(), quantity="0", unit_price=1, product_active=True)

    opportunity.update_line(line.id, quantity="3")
    assert opportunity.amount == Decimal("37501.50")
    opportunity.remove_line(line.id)
    assert opportunity.amount == Decimal("30000.00")
    opportunity.set_estimated_amount("40000")
    assert opportunity.amount == Decimal("40000.00")


def test_tender_editing_rules() -> None:
    pipeline = equipment_pipeline()
    opportunity, _ = create(pipeline)

    opportunity.set_tender(
        is_tender=True, tender_reference="EXP-1", tender_deadline=date(2026, 9, 15)
    )
    assert opportunity.tender_reference == "EXP-1"
    opportunity.set_tender(is_tender=False)
    assert (
        current(opportunity.tender_reference) is None
        and current(opportunity.tender_deadline) is None
    )
    with pytest.raises(TenderFieldsRequireTenderError):
        opportunity.set_tender(tender_reference="EXP-2")
    with pytest.raises(ValidationFailedError):
        opportunity.set_tender(is_tender=True, tender_reference="X" * 101)
