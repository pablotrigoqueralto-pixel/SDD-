"""Dashboard payload: one read-only panel per request (design D2)."""

from uuid import UUID

from pydantic import BaseModel

from app.application.dashboard.periods import DashboardPeriod, ResolvedPeriod
from app.application.dashboard.queries import DashboardData
from app.schemas.catalogue import Price


class PeriodRead(BaseModel):
    period: DashboardPeriod
    start: str
    end: str
    previous_start: str
    previous_end: str

    @classmethod
    def from_resolved(cls, resolved: ResolvedPeriod) -> "PeriodRead":
        return cls(
            period=resolved.period,
            start=resolved.current_start.isoformat(),
            end=resolved.current_end.isoformat(),
            previous_start=resolved.previous_start.isoformat(),
            previous_end=resolved.previous_end.isoformat(),
        )


class WonRead(BaseModel):
    amount: Price
    count: int
    previous_amount: Price
    previous_count: int


class ConversionRead(BaseModel):
    rate: float | None
    won: int
    closed: int
    previous_rate: float | None


class MoneyRead(BaseModel):
    amount: Price
    count: int


class SummaryRead(BaseModel):
    won: WonRead
    conversion: ConversionRead
    forecast: MoneyRead
    open_pipeline: MoneyRead


class StageRowRead(BaseModel):
    stage_id: UUID
    name: str
    amount: Price
    count: int


class BreakdownRowRead(BaseModel):
    id: UUID
    name: str
    won_amount: Price
    won_count: int
    forecast_amount: Price
    open_amount: Price
    conversion_rate: float | None


class ActivityTypeCountRead(BaseModel):
    code: str
    name: str
    count: int


class ActivityRowRead(BaseModel):
    user_id: UUID
    name: str
    total: int
    by_type: list[ActivityTypeCountRead]


class NeglectedAccountRead(BaseModel):
    id: UUID
    name: str
    days_since_contact: int | None


class NeglectedAccountsRead(BaseModel):
    total: int
    items: list[NeglectedAccountRead]


class DashboardRead(BaseModel):
    period: PeriodRead
    summary: SummaryRead
    pipeline_by_stage: list[StageRowRead]
    by_division: list[BreakdownRowRead]
    by_rep: list[BreakdownRowRead] | None
    activity: list[ActivityRowRead]
    neglected_accounts: NeglectedAccountsRead

    @classmethod
    def build(cls, resolved: ResolvedPeriod, data: DashboardData) -> "DashboardRead":
        return cls.model_validate(
            {
                "period": PeriodRead.from_resolved(resolved),
                "summary": data.summary,
                "pipeline_by_stage": data.pipeline_by_stage,
                "by_division": data.by_division,
                "by_rep": data.by_rep,
                "activity": data.activity,
                "neglected_accounts": data.neglected_accounts,
            },
            from_attributes=True,
        )
