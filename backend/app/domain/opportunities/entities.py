"""Opportunity aggregate: pipeline position, amounts, tender block, at-risk flag, lines."""

from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from enum import StrEnum
from uuid import UUID

from app.domain.catalogue.entities import normalise_price
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

NAME_MAX_LENGTH = 200
TENDER_REFERENCE_MAX_LENGTH = 100
CONSUMABLES_PIPELINE_CODE = "consumables"
EQUIPMENT_CLOSE_DAYS = 90
CONSUMABLES_CLOSE_DAYS = 30

SPANISH_MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


class OpportunityStatus(StrEnum):
    OPEN = "open"
    WON = "won"
    LOST = "lost"


class AtRiskSource(StrEnum):
    MANUAL = "manual"
    AUTOMATIC = "automatic"


@dataclass(frozen=True)
class StageChange:
    opportunity_id: UUID
    from_stage_id: UUID | None
    to_stage_id: UUID
    occurred_at: datetime
    actor_id: UUID | None = None
    seconds_in_previous_stage: int | None = None


@dataclass
class OpportunityLine:
    id: UUID
    product_id: UUID
    quantity: Decimal
    unit_price: Decimal
    sort_order: int

    @property
    def total(self) -> Decimal:
        return (self.quantity * self.unit_price).quantize(Decimal("0.01"))


def default_close_date(pipeline: Pipeline, today: date) -> date:
    days = (
        CONSUMABLES_CLOSE_DAYS
        if pipeline.code == CONSUMABLES_PIPELINE_CODE
        else EQUIPMENT_CLOSE_DAYS
    )
    return today + timedelta(days=days)


def generated_name(account_name: str, division_name: str, when: datetime) -> str:
    month = SPANISH_MONTHS[when.month - 1]
    return f"{account_name} · {division_name} · {month} {when.year}"[:NAME_MAX_LENGTH]


def _first_open_stage(pipeline: Pipeline) -> PipelineStage:
    for stage in pipeline.ordered_stages():
        if stage.is_open and not stage.is_at_risk and stage.is_active:
            return stage
    raise StageNotInPipelineError()


def _stage_of(pipeline: Pipeline, stage_id: UUID) -> PipelineStage:
    for stage in pipeline.stages:
        if stage.id == stage_id:
            return stage
    raise StageNotInPipelineError()


def _flag_stage(pipeline: Pipeline, *, won: bool = False, lost: bool = False) -> PipelineStage:
    for stage in pipeline.ordered_stages():
        if (won and stage.is_won) or (lost and stage.is_lost):
            return stage
    raise StageNotInPipelineError()


def _at_risk_stage(pipeline: Pipeline) -> PipelineStage | None:
    return next((s for s in pipeline.ordered_stages() if s.is_at_risk), None)


def _clean_name(name: str) -> str:
    clean = " ".join(name.split())
    if not clean or len(clean) > NAME_MAX_LENGTH:
        raise ValidationFailedError(
            [
                {
                    "field": "name",
                    "message": f"Name must have 1 to {NAME_MAX_LENGTH} characters",
                    "code": "name_invalid",
                }
            ]
        )
    return clean


@dataclass
class Opportunity:
    id: UUID
    account_id: UUID
    pipeline_id: UUID
    stage_id: UUID
    division_id: UUID
    owner_id: UUID
    created_by: UUID
    name: str
    status: OpportunityStatus
    estimated_amount: Decimal
    amount: Decimal
    expected_close_date: date
    stage_entered_at: datetime
    description: str | None = None
    won_amount: Decimal | None = None
    won_at: datetime | None = None
    lost_at: datetime | None = None
    loss_reason_id: UUID | None = None
    competitor_brand_id: UUID | None = None
    loss_note: str | None = None
    is_tender: bool = False
    tender_reference: str | None = None
    tender_deadline: date | None = None
    estimated_award_date: date | None = None
    is_at_risk: bool = False
    at_risk_since: datetime | None = None
    at_risk_source: AtRiskSource | None = None
    lines: list[OpportunityLine] = field(default_factory=list)
    version: int = 1
    created_at: datetime | None = None
    updated_at: datetime | None = None

    # --- creation ---------------------------------------------------------

    @classmethod
    def create(
        cls,
        *,
        account_id: UUID,
        account_name: str,
        buys_via_tender: bool,
        division_id: UUID,
        division_name: str,
        pipeline: Pipeline,
        estimated_amount: Decimal | int | str,
        owner_id: UUID,
        created_by: UUID,
        now: datetime,
        name: str | None = None,
        description: str | None = None,
        expected_close_date: date | None = None,
        is_tender: bool | None = None,
        tender_reference: str | None = None,
        tender_deadline: date | None = None,
        estimated_award_date: date | None = None,
    ) -> tuple["Opportunity", StageChange]:
        stage = _first_open_stage(pipeline)
        estimate = normalise_price(estimated_amount, field="estimated_amount")
        opportunity = cls(
            id=new_id(),
            account_id=account_id,
            pipeline_id=pipeline.id,
            stage_id=stage.id,
            division_id=division_id,
            owner_id=owner_id,
            created_by=created_by,
            name=_clean_name(name) if name else generated_name(account_name, division_name, now),
            status=OpportunityStatus.OPEN,
            estimated_amount=estimate,
            amount=estimate,
            expected_close_date=expected_close_date or default_close_date(pipeline, now.date()),
            stage_entered_at=now,
            description=_clean_text(description),
            is_tender=buys_via_tender if is_tender is None else is_tender,
        )
        opportunity._set_tender_fields(tender_reference, tender_deadline, estimated_award_date)
        change = StageChange(
            opportunity_id=opportunity.id,
            from_stage_id=None,
            to_stage_id=stage.id,
            occurred_at=now,
            actor_id=created_by,
        )
        return opportunity, change

    # --- lifecycle --------------------------------------------------------

    def move_stage(
        self, pipeline: Pipeline, stage_id: UUID, *, actor_id: UUID, now: datetime
    ) -> StageChange:
        self._ensure_open()
        target = _stage_of(self._own(pipeline), stage_id)
        if not target.is_open or target.is_at_risk:
            raise InvalidOpportunityTransitionError(
                "Won, lost and at-risk stages are reached through their own actions"
            )
        if target.id == self.stage_id:
            raise InvalidOpportunityTransitionError("The opportunity is already at this stage")
        return self._enter_stage(target.id, actor_id=actor_id, now=now)

    def win(
        self,
        pipeline: Pipeline,
        *,
        actor_id: UUID,
        now: datetime,
        won_amount: Decimal | int | str | None = None,
        won_at: datetime | None = None,
    ) -> StageChange:
        self._ensure_open()
        stage = _flag_stage(self._own(pipeline), won=True)
        self.status = OpportunityStatus.WON
        self.won_amount = (
            normalise_price(won_amount, field="won_amount")
            if won_amount is not None
            else self.amount
        )
        self.won_at = won_at or now
        return self._enter_stage(stage.id, actor_id=actor_id, now=now)

    def lose(
        self,
        pipeline: Pipeline,
        *,
        loss_reason_id: UUID,
        requires_brand: bool,
        requires_note: bool,
        actor_id: UUID,
        now: datetime,
        competitor_brand_id: UUID | None = None,
        note: str | None = None,
    ) -> StageChange:
        at_risk_churn = self.status is OpportunityStatus.WON and self.is_at_risk
        if self.status is not OpportunityStatus.OPEN and not at_risk_churn:
            raise OpportunityClosedError()
        if requires_brand and competitor_brand_id is None:
            raise LossReasonRequiresBrandError()
        clean_note = _clean_text(note)
        if requires_note and not clean_note:
            raise LossReasonRequiresNoteError()
        stage = _flag_stage(self._own(pipeline), lost=True)
        self.status = OpportunityStatus.LOST
        self.loss_reason_id = loss_reason_id
        self.competitor_brand_id = competitor_brand_id
        self.loss_note = clean_note
        self.lost_at = now
        self.won_amount = None
        self.won_at = None
        self._clear_at_risk()
        return self._enter_stage(stage.id, actor_id=actor_id, now=now)

    def reopen(
        self, pipeline: Pipeline, stage_id: UUID, *, actor_id: UUID, now: datetime
    ) -> StageChange:
        if self.status is OpportunityStatus.OPEN:
            raise InvalidOpportunityTransitionError("The opportunity is already open")
        target = _stage_of(self._own(pipeline), stage_id)
        if not target.is_open or target.is_at_risk:
            raise InvalidOpportunityTransitionError("Reopen targets an open stage")
        self.status = OpportunityStatus.OPEN
        self.won_amount = None
        self.won_at = None
        self.lost_at = None
        self.loss_reason_id = None
        self.competitor_brand_id = None
        self.loss_note = None
        self._clear_at_risk()
        return self._enter_stage(target.id, actor_id=actor_id, now=now)

    def set_at_risk(
        self,
        pipeline: Pipeline,
        flag: bool,
        *,
        source: AtRiskSource,
        actor_id: UUID | None,
        now: datetime,
    ) -> StageChange | None:
        at_risk_stage = _at_risk_stage(self._own(pipeline))
        if at_risk_stage is None or self.status is not OpportunityStatus.WON:
            raise AtRiskNotSupportedError()
        if flag:
            if self.is_at_risk:
                return None
            self.is_at_risk = True
            self.at_risk_since = now
            self.at_risk_source = source
            return self._enter_stage(at_risk_stage.id, actor_id=actor_id, now=now)
        if not self.is_at_risk:
            return None
        self._clear_at_risk()
        won_stage = _flag_stage(pipeline, won=True)
        return self._enter_stage(won_stage.id, actor_id=actor_id, now=now)

    # --- editing ----------------------------------------------------------

    def rename(self, name: str) -> None:
        self._ensure_open()
        self.name = _clean_name(name)

    def set_description(self, description: str | None) -> None:
        self._ensure_open()
        self.description = _clean_text(description)

    def set_estimated_amount(self, value: Decimal | int | str) -> None:
        self._ensure_open()
        if self.lines:
            raise OpportunityHasLinesError()
        self.estimated_amount = normalise_price(value, field="estimated_amount")
        self.recompute_amount()

    def set_expected_close_date(self, value: date) -> None:
        self._ensure_open()
        self.expected_close_date = value

    def set_tender(
        self,
        *,
        is_tender: bool | None = None,
        tender_reference: str | object | None = ...,
        tender_deadline: date | object | None = ...,
        estimated_award_date: date | object | None = ...,
    ) -> None:
        self._ensure_open()
        if is_tender is not None:
            self.is_tender = is_tender
        provided_reference = None if tender_reference is ... else tender_reference
        provided_deadline = None if tender_deadline is ... else tender_deadline
        provided_award = None if estimated_award_date is ... else estimated_award_date
        if not self.is_tender:
            # Turning the flag off clears the block; new values are only valid on tenders.
            if provided_reference or provided_deadline or provided_award:
                raise TenderFieldsRequireTenderError()
            self.tender_reference = None
            self.tender_deadline = None
            self.estimated_award_date = None
            return
        reference = self.tender_reference if tender_reference is ... else tender_reference
        deadline = self.tender_deadline if tender_deadline is ... else tender_deadline
        award = self.estimated_award_date if estimated_award_date is ... else estimated_award_date
        self._set_tender_fields(
            reference if isinstance(reference, str) or reference is None else None,
            deadline if isinstance(deadline, date) or deadline is None else None,
            award if isinstance(award, date) or award is None else None,
        )

    # --- lines ------------------------------------------------------------

    def add_line(
        self,
        *,
        product_id: UUID,
        quantity: Decimal | int | str,
        unit_price: Decimal | int | str,
        product_active: bool,
    ) -> OpportunityLine:
        self._ensure_open()
        if not product_active:
            raise LineProductInactiveError()
        if any(line.product_id == product_id for line in self.lines):
            raise LineDuplicatedError()
        line = OpportunityLine(
            id=new_id(),
            product_id=product_id,
            quantity=_quantity(quantity),
            unit_price=normalise_price(unit_price, field="unit_price"),
            sort_order=max((line.sort_order for line in self.lines), default=0) + 10,
        )
        self.lines.append(line)
        self.recompute_amount()
        return line

    def update_line(
        self,
        line_id: UUID,
        *,
        quantity: Decimal | int | str | None = None,
        unit_price: Decimal | int | str | None = None,
    ) -> OpportunityLine:
        self._ensure_open()
        line = self._line(line_id)
        if quantity is not None:
            line.quantity = _quantity(quantity)
        if unit_price is not None:
            line.unit_price = normalise_price(unit_price, field="unit_price")
        self.recompute_amount()
        return line

    def remove_line(self, line_id: UUID) -> None:
        self._ensure_open()
        line = self._line(line_id)
        self.lines.remove(line)
        self.recompute_amount()

    def recompute_amount(self) -> None:
        if self.lines:
            total = sum((line.total for line in self.lines), Decimal("0"))
            self.amount = total.quantize(Decimal("0.01"))
        else:
            self.amount = self.estimated_amount

    # --- helpers ----------------------------------------------------------

    def days_in_stage(self, now: datetime | None = None) -> int:
        reference = now or datetime.now(UTC)
        return max(0, (reference - self.stage_entered_at).days)

    def snapshot(self) -> dict[str, object]:
        return {
            "account_id": self.account_id,
            "pipeline_id": self.pipeline_id,
            "stage_id": self.stage_id,
            "division_id": self.division_id,
            "owner_id": self.owner_id,
            "name": self.name,
            "description": self.description,
            "status": self.status,
            "estimated_amount": str(self.estimated_amount),
            "amount": str(self.amount),
            "expected_close_date": self.expected_close_date,
            "won_amount": None if self.won_amount is None else str(self.won_amount),
            "won_at": self.won_at,
            "lost_at": self.lost_at,
            "loss_reason_id": self.loss_reason_id,
            "competitor_brand_id": self.competitor_brand_id,
            "loss_note": self.loss_note,
            "is_tender": self.is_tender,
            "tender_reference": self.tender_reference,
            "tender_deadline": self.tender_deadline,
            "estimated_award_date": self.estimated_award_date,
            "is_at_risk": self.is_at_risk,
            "at_risk_source": self.at_risk_source,
        }

    def _enter_stage(self, stage_id: UUID, *, actor_id: UUID | None, now: datetime) -> StageChange:
        change = StageChange(
            opportunity_id=self.id,
            from_stage_id=self.stage_id,
            to_stage_id=stage_id,
            occurred_at=now,
            actor_id=actor_id,
            seconds_in_previous_stage=max(0, int((now - self.stage_entered_at).total_seconds())),
        )
        self.stage_id = stage_id
        self.stage_entered_at = now
        return change

    def _ensure_open(self) -> None:
        if self.status is not OpportunityStatus.OPEN:
            raise OpportunityClosedError()

    def _own(self, pipeline: Pipeline) -> Pipeline:
        if pipeline.id != self.pipeline_id:
            raise StageNotInPipelineError()
        return pipeline

    def _line(self, line_id: UUID) -> OpportunityLine:
        for line in self.lines:
            if line.id == line_id:
                return line
        raise ValidationFailedError(
            [{"field": "line_id", "message": "Unknown line", "code": "line_not_found"}]
        )

    def _clear_at_risk(self) -> None:
        self.is_at_risk = False
        self.at_risk_since = None
        self.at_risk_source = None

    def _set_tender_fields(
        self, reference: str | None, deadline: date | None, award: date | None
    ) -> None:
        if not self.is_tender and (reference or deadline or award):
            raise TenderFieldsRequireTenderError()
        clean = _clean_text(reference)
        if clean and len(clean) > TENDER_REFERENCE_MAX_LENGTH:
            raise ValidationFailedError(
                [
                    {
                        "field": "tender_reference",
                        "message": f"Reference exceeds {TENDER_REFERENCE_MAX_LENGTH} characters",
                        "code": "tender_reference_invalid",
                    }
                ]
            )
        self.tender_reference = clean
        self.tender_deadline = deadline
        self.estimated_award_date = award


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return None
    cleaned = value.strip()
    return cleaned or None


def _quantity(value: Decimal | int | str) -> Decimal:
    quantity = Decimal(value).quantize(Decimal("0.01"))
    if quantity <= 0:
        raise ValidationFailedError(
            [
                {
                    "field": "quantity",
                    "message": "Quantity must be greater than zero",
                    "code": "quantity_invalid",
                }
            ]
        )
    return quantity
