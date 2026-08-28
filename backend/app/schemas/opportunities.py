"""Opportunity API schemas. Amounts travel as two-decimal strings."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.application.opportunities.queries import (
    BoardColumn,
    BoardResult,
    ClosedSummary,
    OpportunitySummary,
)
from app.application.opportunities.service import OpportunityDetail
from app.domain.opportunities.entities import (
    AtRiskSource,
    Opportunity,
    OpportunityLine,
    OpportunityStatus,
    StageChange,
)
from app.schemas.catalogue import Price, PriceInput
from app.schemas.reference import PipelineRead, PipelineStageRead


class OpportunityLineRead(BaseModel):
    id: UUID
    product_id: UUID
    quantity: Price
    unit_price: Price
    total: Price
    sort_order: int

    @classmethod
    def from_entity(cls, line: OpportunityLine) -> "OpportunityLineRead":
        return cls(
            id=line.id,
            product_id=line.product_id,
            quantity=line.quantity,
            unit_price=line.unit_price,
            total=line.total,
            sort_order=line.sort_order,
        )


class StageHistoryRead(BaseModel):
    from_stage_id: UUID | None
    to_stage_id: UUID
    actor_id: UUID | None
    occurred_at: datetime
    seconds_in_previous_stage: int | None

    @classmethod
    def from_change(cls, change: StageChange) -> "StageHistoryRead":
        return cls(
            from_stage_id=change.from_stage_id,
            to_stage_id=change.to_stage_id,
            actor_id=change.actor_id,
            occurred_at=change.occurred_at,
            seconds_in_previous_stage=change.seconds_in_previous_stage,
        )


class OpportunitySummaryRead(BaseModel):
    id: UUID
    account_id: UUID
    account_name: str
    name: str
    pipeline_id: UUID
    stage_id: UUID
    stage_name: str
    division_id: UUID
    owner_id: UUID
    owner_name: str
    status: OpportunityStatus
    amount: Price
    expected_close_date: date
    is_tender: bool
    tender_deadline: date | None
    is_at_risk: bool
    stage_entered_at: datetime
    days_in_stage: int
    version: int
    updated_at: datetime | None

    @classmethod
    def from_summary(cls, summary: OpportunitySummary) -> "OpportunitySummaryRead":
        return cls(
            id=summary.id,
            account_id=summary.account_id,
            account_name=summary.account_name,
            name=summary.name,
            pipeline_id=summary.pipeline_id,
            stage_id=summary.stage_id,
            stage_name=summary.stage_name,
            division_id=summary.division_id,
            owner_id=summary.owner_id,
            owner_name=summary.owner_name,
            status=summary.status,
            amount=summary.amount,
            expected_close_date=summary.expected_close_date,
            is_tender=summary.is_tender,
            tender_deadline=summary.tender_deadline,
            is_at_risk=summary.is_at_risk,
            stage_entered_at=summary.stage_entered_at,
            days_in_stage=summary.days_in_stage,
            version=summary.version,
            updated_at=summary.updated_at,
        )


class OpportunityRead(BaseModel):
    id: UUID
    account_id: UUID
    account_name: str
    pipeline_id: UUID
    pipeline_name: str
    stage_id: UUID
    stage_name: str
    division_id: UUID
    owner_id: UUID
    owner_name: str
    name: str
    description: str | None
    status: OpportunityStatus
    estimated_amount: Price
    amount: Price
    expected_close_date: date
    won_amount: Price | None
    won_at: datetime | None
    lost_at: datetime | None
    loss_reason_id: UUID | None
    competitor_brand_id: UUID | None
    loss_note: str | None
    is_tender: bool
    tender_reference: str | None
    tender_deadline: date | None
    estimated_award_date: date | None
    is_at_risk: bool
    at_risk_since: datetime | None
    at_risk_source: AtRiskSource | None
    stage_entered_at: datetime
    days_in_stage: int
    lines: list[OpportunityLineRead]
    stage_history: list[StageHistoryRead]
    version: int
    created_at: datetime | None
    updated_at: datetime | None

    @classmethod
    def build(
        cls,
        detail: OpportunityDetail,
        *,
        account_name: str,
        pipeline_name: str,
        stage_name: str,
        owner_name: str,
        now: datetime,
    ) -> "OpportunityRead":
        opportunity = detail.opportunity
        return cls(
            id=opportunity.id,
            account_id=opportunity.account_id,
            account_name=account_name,
            pipeline_id=opportunity.pipeline_id,
            pipeline_name=pipeline_name,
            stage_id=opportunity.stage_id,
            stage_name=stage_name,
            division_id=opportunity.division_id,
            owner_id=opportunity.owner_id,
            owner_name=owner_name,
            name=opportunity.name,
            description=opportunity.description,
            status=opportunity.status,
            estimated_amount=opportunity.estimated_amount,
            amount=opportunity.amount,
            expected_close_date=opportunity.expected_close_date,
            won_amount=opportunity.won_amount,
            won_at=opportunity.won_at,
            lost_at=opportunity.lost_at,
            loss_reason_id=opportunity.loss_reason_id,
            competitor_brand_id=opportunity.competitor_brand_id,
            loss_note=opportunity.loss_note,
            is_tender=opportunity.is_tender,
            tender_reference=opportunity.tender_reference,
            tender_deadline=opportunity.tender_deadline,
            estimated_award_date=opportunity.estimated_award_date,
            is_at_risk=opportunity.is_at_risk,
            at_risk_since=opportunity.at_risk_since,
            at_risk_source=opportunity.at_risk_source,
            stage_entered_at=opportunity.stage_entered_at,
            days_in_stage=opportunity.days_in_stage(now),
            lines=[OpportunityLineRead.from_entity(line) for line in opportunity.lines],
            stage_history=[StageHistoryRead.from_change(change) for change in detail.history],
            version=opportunity.version,
            created_at=opportunity.created_at,
            updated_at=opportunity.updated_at,
        )


class OpportunityCreate(BaseModel):
    account_id: UUID
    division_id: UUID
    estimated_amount: PriceInput
    pipeline_id: UUID | None = None
    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    expected_close_date: date | None = None
    is_tender: bool | None = None
    tender_reference: str | None = Field(default=None, max_length=100)
    tender_deadline: date | None = None
    estimated_award_date: date | None = None
    owner_id: UUID | None = None


class OpportunityUpdate(BaseModel):
    """PATCH: only provided fields change; stage, status and owner have their own commands."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=200)
    description: str | None = Field(default=None, max_length=2000)
    estimated_amount: PriceInput | None = None
    expected_close_date: date | None = None
    is_tender: bool | None = None
    tender_reference: str | None = Field(default=None, max_length=100)
    tender_deadline: date | None = None
    estimated_award_date: date | None = None

    def changes(self) -> dict[str, object]:
        provided = self.model_fields_set
        values = self.model_dump()
        return {key: values[key] for key in provided}


class StageMove(BaseModel):
    stage_id: UUID


class OpportunityWin(BaseModel):
    won_amount: PriceInput | None = None
    won_at: datetime | None = None


class OpportunityLose(BaseModel):
    loss_reason_id: UUID
    competitor_brand_id: UUID | None = None
    note: str | None = Field(default=None, max_length=2000)


class OpportunityReopen(BaseModel):
    stage_id: UUID


class AtRiskToggle(BaseModel):
    flag: bool


class OpportunityAssignment(BaseModel):
    owner_id: UUID


class LineCreate(BaseModel):
    product_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=10, decimal_places=2)
    unit_price: PriceInput | None = None


class LineUpdate(BaseModel):
    quantity: Decimal | None = Field(default=None, gt=0, max_digits=10, decimal_places=2)
    unit_price: PriceInput | None = None


class BoardColumnRead(BaseModel):
    stage: PipelineStageRead
    count: int
    total_amount: Price
    items: list[OpportunitySummaryRead]
    has_more: bool

    @classmethod
    def from_column(cls, column: BoardColumn) -> "BoardColumnRead":
        return cls(
            stage=PipelineStageRead.from_entity(column.stage),
            count=column.count,
            total_amount=column.total_amount,
            items=[OpportunitySummaryRead.from_summary(item) for item in column.items],
            has_more=column.has_more,
        )


class ClosedSummaryRead(BaseModel):
    won_count: int
    won_amount: Price
    lost_count: int

    @classmethod
    def from_summary(cls, summary: ClosedSummary) -> "ClosedSummaryRead":
        return cls(
            won_count=summary.won_count,
            won_amount=summary.won_amount,
            lost_count=summary.lost_count,
        )


class BoardRead(BaseModel):
    pipeline: PipelineRead
    columns: list[BoardColumnRead]
    closed_this_month: ClosedSummaryRead

    @classmethod
    def from_result(cls, result: BoardResult) -> "BoardRead":
        return cls(
            pipeline=PipelineRead.from_entity(result.pipeline),
            columns=[BoardColumnRead.from_column(column) for column in result.columns],
            closed_this_month=ClosedSummaryRead.from_summary(result.closed_this_month),
        )


def status_filter(value: str | None) -> OpportunityStatus | None:
    if value in (None, "", "open"):
        return OpportunityStatus.OPEN
    if value == "all":
        return None
    return OpportunityStatus(value)


__all__ = [
    "AtRiskToggle",
    "BoardRead",
    "LineCreate",
    "LineUpdate",
    "Opportunity",
    "OpportunityAssignment",
    "OpportunityCreate",
    "OpportunityLose",
    "OpportunityRead",
    "OpportunityReopen",
    "OpportunitySummaryRead",
    "OpportunityUpdate",
    "OpportunityWin",
    "StageMove",
    "status_filter",
]
